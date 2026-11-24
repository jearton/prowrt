#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise native LuCI save/apply and Technitium linkage in the CI VM only."""
import hashlib
from html.parser import HTMLParser
import http.cookiejar
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = 'http://192.168.1.1'
PAGE = BASE + '/cgi-bin/luci/admin/services/openclash/config'
SOURCE = '/etc/openclash/config/editor-ci.yaml'
RUNTIME = '/etc/openclash/editor-ci.yaml'


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms, self.current = [], None

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == 'form':
            self.current = {'action': attrs.get('action', PAGE), 'fields': [], 'buttons': {}, 'textareas': []}
            self.forms.append(self.current)
        if self.current is None:
            return
        if tag == 'textarea':
            self.current['textareas'].append(attrs)
        if tag in ('input', 'button') and attrs.get('name') and 'disabled' not in attrs:
            kind = attrs.get('type', 'submit' if tag == 'button' else 'text')
            if kind == 'submit':
                self.current['buttons'][attrs['name']] = attrs.get('value', '1')
            elif kind not in ('file', 'button', 'reset') and (kind not in ('checkbox', 'radio') or 'checked' in attrs):
                self.current['fields'].append((attrs['name'], attrs.get('value', '')))

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


def fixture(large, reject):
    rule = 'REJECT' if reject else 'DIRECT'
    text = f'''mode: rule
log-level: info
ipv6: false
proxies: []
proxy-groups:
  - name: CI
    type: select
    proxies: [DIRECT, REJECT]
dns:
  enable: true
  enhanced-mode: redir-host
  nameserver: [rcode://success]
rules:
  - DOMAIN,firmware-upload.example,{rule}
  - MATCH,DIRECT
'''
    return (text + ('# 中文合法配置注释\n' * 9000 if large else '')).encode()


def main(directory):
    namespace = os.environ.get('OPENWRT_CI_NETNS', '')
    if not namespace or subprocess.check_output(['ip', 'netns', 'identify'], text=True).strip() != namespace:
        raise RuntimeError('This check must run inside the disposable CI network namespace')
    spec = importlib.util.spec_from_file_location('lan_vm', Path(__file__).with_name('lan-vm.py'))
    lab = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lab)
    guest = lab.Guest(directory)
    jar = http.cookiejar.CookieJar()
    browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    credentials = urllib.parse.urlencode({'luci_username': 'root',
        'luci_password': (directory / 'root-password').read_text()}).encode()
    browser.open(BASE + '/cgi-bin/luci/', data=credentials, timeout=15).read()
    if not any(c.name == 'sysauth_http' and not c.is_expired() for c in jar):
        raise RuntimeError('Native LuCI login did not establish a test session')

    def form():
        document = browser.open(PAGE, timeout=15).read().decode()
        if 'Unhandled exception' in document:
            raise RuntimeError('LuCI editor failed to render')
        parser = Forms()
        parser.feed(document)
        selected = next(f for f in parser.forms if any(t.get('id') == 'cbid.table.1.user' for t in f['textareas']))
        runtime = next(t for t in selected['textareas'] if t.get('id') == 'cbid.table.1.default')
        assert 'name' not in runtime, 'Readonly runtime YAML still participates in submission'
        assert any(name == 'token' for name, _ in selected['fields'])
        return selected

    def submit(content, action):
        selected = form()
        buttons = [key for key in selected['buttons'] if key.endswith('.' + action)]
        assert len(buttons) == 1, 'Unable to identify the native LuCI save/apply action'
        fields = selected['fields'] + [(buttons[0], selected['buttons'][buttons[0]])]
        boundary = 'ProWrtEditorBoundary20261124'
        data = bytearray()
        for name, value in fields:
            assert len(value.encode()) < 100 * 1024
            data += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        data += f'--{boundary}\r\nContent-Disposition: form-data; name="oc_editor_content"; filename="content.yaml"\r\nContent-Type: text/plain\r\n\r\n'.encode()
        data += content + f'\r\n--{boundary}--\r\n'.encode()
        target = urllib.parse.urljoin(PAGE, selected['action'])
        assert target.startswith(BASE + '/cgi-bin/luci/'), 'Unexpected form target'
        request = urllib.request.Request(target, data=bytes(data), headers={
            'Content-Type': 'multipart/form-data; boundary=' + boundary, 'Origin': BASE, 'Referer': PAGE})
        response = browser.open(request, timeout=25).read()
        assert b'Unhandled exception' not in response and b'maximum allow size' not in response
        actual = guest.run('sha256sum ' + SOURCE).split()[0]
        assert actual == hashlib.sha256(content).hexdigest(), 'Saved YAML was truncated or changed'

    def wait_for(script, seconds=90):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                return guest.run(script, timeout=8)
            except (RuntimeError, subprocess.TimeoutExpired):
                time.sleep(1)
        raise RuntimeError('OpenClash did not reach the expected configuration state')

    def tech_upstream():
        # Query the native API independently of the linkage helper. Output only
        # public forwarding fields, never the authentication response or token.
        return guest.run(r'''
token=$(curl -fsS --max-time 4 http://127.0.0.1:5380/api/user/login --data-urlencode user=admin --data-urlencode pass@/etc/technitium/setup-password | jsonfilter -e '@.token')
test -n "$token"
tech_api() {
    printf 'header = "Authorization: Bearer %s"\n' "$token" | curl -fsS --max-time 4 --config - "http://127.0.0.1:5380/api/$1"
}
trap 'tech_api user/logout >/dev/null' EXIT
tech_api settings/get | jsonfilter -e '@.response.forwarderProtocol' -e '@.response.forwarders[*]'
''').splitlines()

    guest.run('''
test ! -e /tmp/openclash-editor-ci
mkdir -m 700 /tmp/openclash-editor-ci
uci export openclash > /tmp/openclash-editor-ci/openclash.uci
uci set openclash.config.config_path=/etc/openclash/config/editor-ci.yaml
uci set openclash.config.operation_mode=redir-host
uci set openclash.config.en_mode=redir-host
uci set openclash.config.log_level=info
uci set openclash.config.enable_redirect_dns=0
uci set openclash.config.append_wan_dns=0
uci set openclash.config.append_default_dns=0
uci commit openclash
''')
    try:
        for content, target in [(fixture(True, False), SOURCE), (fixture(True, False), RUNTIME)]:
            guest.run("cat > " + target + " <<'OPENCLASH_CI_YAML'\n" + content.decode() + "OPENCLASH_CI_YAML\n")
        submit(fixture(False, False), 'Commit')
        submit(fixture(True, False), 'Commit')
        applied = fixture(True, True)
        assert len(applied) > 159133
        submit(applied, 'Apply')
        wait_for("pidof clash >/dev/null\ngrep -q 'OpenClash Start Successful' /tmp/openclash.log")
        # Exercise the new rule through the actual mixed proxy. Authentication
        # is read privately from this disposable VM's runtime YAML.
        guest.run("""ruby -ryaml -rjson -e '
v=YAML.load_file(ARGV[0],aliases:true)
cfg="proxy = "+JSON.generate("http://127.0.0.1:"+v["mixed-port"].to_s)+"\\nmax-time = 5\\nsilent\\n"
auth=Array(v["authentication"]).first
cfg += "proxy-user = "+JSON.generate(auth)+"\\n" if auth
IO.popen(["curl","--config","-","http://firmware-upload.example:19097/"],"r+") {|io|io.write(cfg);io.close_write;io.read}
' """ + RUNTIME + "\ngrep 'firmware-upload.example' /tmp/openclash.log | grep -q 'REJECT'")
        print(f'Native LuCI saved and applied {len(applied)} bytes; readonly comparison renders and the new REJECT rule matched', flush=True)

        page = browser.open(BASE + '/cgi-bin/luci/admin/services/openclash/settings', timeout=20).read()
        assert b'dns_link_zones' in page and b'Unhandled exception' not in page
        before = tech_upstream()
        assert before[0] == 'Tls', 'Expected untouched fresh-install DNS before opt-in'
        guest.run('''
uci set openclash.config.enable_redirect_dns=3
uci set openclash.config.enable_custom_dns=1
uci set openclash.config.custom_name_policy=1
uci set openclash.config.append_default_dns=0
uci set openclash.prowrt_dns_google.specific_group=CI
uci set openclash.prowrt_dns_cloudflare.specific_group=CI
uci commit openclash
echo CI-DNS-LINK-START >> /tmp/openclash.log
/etc/init.d/openclash restart >/dev/null 2>&1
''')
        wait_for("pidof clash >/dev/null\ngrep -q 'fixed-mihomo' /var/run/openclash-dns-link.json\n"
                 "awk '/CI-DNS-LINK-START/{seen=1;next} seen && /OpenClash Start Successful/{ok=1} END{exit !ok}' /tmp/openclash.log")
        assert tech_upstream() == ['Udp', '127.0.0.1:7874']
        guest.run('/etc/init.d/openclash stop >/dev/null 2>&1')
        assert tech_upstream() == ['Udp', '127.0.0.1:7874'], 'Stopping restored a public DNS upstream'
        assert guest.run('nslookup openwrt.lan 127.0.0.1').find('192.168.1.1') >= 0
        print('Redir-Host DNS preset and native Technitium linkage passed; stopping retained the fixed upstream and local answers', flush=True)
    finally:
        # This entire CI VM is discarded by check-fresh-lan.sh. Never import its
        # generated state, credentials or large test YAML into the release image.
        guest.run('/etc/init.d/openclash stop >/dev/null 2>&1 || true', timeout=30)


if __name__ == '__main__':
    main(Path(sys.argv[1]))

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Manage only the disposable, isolated CI VM used by check-fresh-lan."""

from pathlib import Path
import re
import json
import importlib.util
import secrets
import select
import socket
import subprocess
import sys
import time


class Guest:
    def __init__(self, directory):
        self.directory = Path(directory)

    def options(self):
        return ["-i", str(self.directory / "key"), "-p", "22",
                "-o", "BatchMode=yes", "-o", "ConnectTimeout=3",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "UserKnownHostsFile=" + str(self.directory / "known_hosts"),
                "-o", "LogLevel=ERROR"]

    def run(self, script, timeout=60):
        result = subprocess.run(
            ["ssh", *self.options(), "root@192.168.1.1", "sh -se"],
            input="set -eu\n" + script, text=True, capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout

    def upload(self, files):
        options = self.options()
        options[options.index("-p")] = "-P"
        subprocess.run(["scp", "-O", *options, *map(str, files),
                        "root@192.168.1.1:/tmp/technitium-test/"], check=True, timeout=120)

    def wait(self, previous_boot=None, serial=None):
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            # A connected, unread QEMU serial socket can stall console writes
            # during boot. Keep draining it while waiting for LAN SSH readiness.
            if serial is not None:
                while select.select([serial], [], [], 0)[0]:
                    if not serial.recv(65536):
                        raise RuntimeError("The VM closed its serial console")
            try:
                boot = self.run("cat /proc/sys/kernel/random/boot_id", timeout=5).strip()
                if previous_boot is None or previous_boot != boot:
                    return
            except (RuntimeError, subprocess.TimeoutExpired):
                pass
            time.sleep(2)
        raise RuntimeError("The isolated VM did not provide a new test SSH session")


def bootstrap(directory):
    key = directory / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    public_key = key.with_suffix(".pub").read_text().strip()
    deadline = time.monotonic() + 180
    serial = socket.socket(socket.AF_UNIX)
    while time.monotonic() < deadline:
        try:
            serial.connect(str(directory / "serial.sock"))
            break
        except (FileNotFoundError, ConnectionRefusedError):
            time.sleep(1)
    else:
        raise RuntimeError("The disposable VM serial socket did not open")
    with serial:
        serial.settimeout(2)
        output = b""
        sent = False
        while time.monotonic() < deadline:
            try:
                chunk = serial.recv(65536)
                if not chunk:
                    raise RuntimeError("The VM closed its serial console")
                output = (output + chunk)[-32768:]
            except socket.timeout:
                serial.sendall(b"\n")
                continue
            if b"Press Enter" in output or b"press Enter" in output:
                serial.sendall(b"\n")
            if b"root@OpenWrt" in output and not sent:
                command = (
                    "mkdir -p /etc/dropbear; printf '%s\\n' '" + public_key + "' "
                    ">> /etc/dropbear/authorized_keys; chmod 600 /etc/dropbear/authorized_keys; "
                    "/etc/init.d/dropbear start; printf '\\nBOOTSTRAP-%s\\n' READY\n")
                serial.sendall(command.encode())
                sent = True
            if b"BOOTSTRAP-READY" in output:
                Guest(directory).wait(serial=serial)
                return
    raise RuntimeError("Unable to bootstrap the disposable VM console")


def fixture(guest, packages, repo, ttyd_init):
    """Reproduce first initialization separately from the exact-image acceptance."""
    guest.run("""
until test -e /etc/technitium/provisioned; do sleep 1; done
mkdir -p /tmp/technitium-test
""", timeout=150)
    apks = list(packages.glob("*.apk"))
    assert len(apks) == 3  # Technitium APKs; certificate tools are in the pinned image.
    guest.upload(apks)
    # These two source files share a basename, so stream them to distinct paths.
    for source, target in [("etc/init.d/technitium-provision", "/etc/init.d/technitium-provision"),
                           ("usr/libexec/technitium-provision", "/usr/libexec/technitium-provision")]:
        content = (repo / "sources/full/files" / source).read_text()
        guest.run("cat > " + target + " <<'TECHNITIUM_CI_SOURCE'\n" + content +
                  "\nTECHNITIUM_CI_SOURCE\nchmod 755 " + target)
    guest.run("cat > /etc/init.d/ttyd <<'TTYD_CI_SOURCE'\n" + ttyd_init.read_text() +
              "\nTTYD_CI_SOURCE\nchmod 755 /etc/init.d/ttyd")
    guest.run("cat > /usr/libexec/ttyd-login <<'TTYD_LOGIN_CI_SOURCE'\n" +
              (ttyd_init.parent / "ttyd-login").read_text() +
              "\nTTYD_LOGIN_CI_SOURCE\nchmod 755 /usr/libexec/ttyd-login")
    guest.run((repo / "sources/full/files/etc/uci-defaults/93-ttyd-luci-session").read_text())
    guest.run("""
apk --no-network --repositories-file /dev/null --allow-untrusted add /tmp/technitium-test/*.apk
/etc/init.d/technitium stop
""")
    guest.run((repo / "sources/full/files/etc/uci-defaults/93-technitium-dns").read_text())
    guest.run("""
mv /etc/technitium /root/technitium-before-ci-firstboot
/etc/init.d/technitium enable
/etc/init.d/technitium-provision enable
""")
    boot = guest.run("cat /proc/sys/kernel/random/boot_id").strip()
    try:
        guest.run("reboot", timeout=10)
    except (RuntimeError, subprocess.TimeoutExpired):
        pass
    guest.wait(previous_boot=boot)
    print("The new packages and firmware initializer are running with fresh DNS state.", flush=True)


def dns_defaults(guest):
    output = guest.run(r"""
test -e /etc/technitium/provisioned
token=$(curl -fsS --max-time 5 -G http://127.0.0.1:5380/api/user/login \
  --data-urlencode user=admin --data-urlencode pass@/etc/technitium/setup-password | jsonfilter -e '@.token')
test -n "$token"
trap 'curl -fsS --max-time 5 -H "Authorization: Bearer $token" http://127.0.0.1:5380/api/user/logout >/dev/null' EXIT
curl -fsS --max-time 5 -H "Authorization: Bearer $token" http://127.0.0.1:5380/api/settings/get |
  jsonfilter -e '@.response.dnssecValidation' -e '@.response.forwarderProtocol' \
    -e '@.response.concurrentForwarding' -e '@.response.forwarderConcurrency' \
    -e '@.response.forwarders[*]'
""")
    assert output.splitlines() == ["false", "Tls", "true", "2",
                                   "dns.alidns.com:853 (223.5.5.5)",
                                   "dot.360.cn:853 (101.226.4.6)"], output
    print("Fresh native API defaults: DNSSEC off, two parallel certificate-verified DoT upstreams.", flush=True)


def forced_dns(guest):
    # TEST-NET-3 is deliberately unreachable beyond this isolated namespace.
    subprocess.run(["ip", "addr", "add", "192.168.1.3/32", "dev", "lan-test"], check=True)
    subprocess.run(["ip", "route", "add", "203.0.113.53/32", "via", "192.168.1.1", "dev", "lan-test"], check=True)

    def query(tcp=False):
        command = ["dig", "-b", "192.168.1.3", "@203.0.113.53", "openwrt.lan", "A",
                   "+short", "+time=2", "+tries=1"]
        if tcp:
            command.append("+tcp")
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return result.returncode == 0 and result.stdout.strip() == "192.168.1.1"

    assert query() and query(tcp=True), "An explicitly selected external resolver was not redirected"
    counters = guest.run("nft list chain inet fw4 dstnat_lan")
    hits = re.findall(r'counter packets (\d+).*comment "!fw4: Force LAN DNS to router"', counters)
    assert hits and sum(map(int, hits)) >= 2, "The LAN DNS redirect counters did not increase"
    # This source IP is used only for forced queries, so its statistics prove
    # that the application received the original client address without SNAT.
    guest.run(r"""
token=$(curl -fsS --max-time 5 -G http://127.0.0.1:5380/api/user/login \
  --data-urlencode user=admin --data-urlencode pass@/etc/technitium/setup-password | jsonfilter -e '@.token')
test -n "$token"
trap 'curl -fsS --max-time 5 -H "Authorization: Bearer $token" http://127.0.0.1:5380/api/user/logout >/dev/null' EXIT
for attempt in $(seq 1 16); do
    if curl -fsS --max-time 5 -G -H "Authorization: Bearer $token" \
      http://127.0.0.1:5380/api/dashboard/stats/getTop \
      --data-urlencode type=LastHour --data-urlencode statsType=TopClients --data-urlencode noReverseLookup=true |
      jsonfilter -e '@.response.topClients[*].name' | grep -qx 192.168.1.3; then
        exit 0
    fi
    sleep 5
done
exit 1
""", timeout=100)
    guest.run("uci set firewall.technitium_dns_redirect.enabled=0\nuci commit firewall\n/etc/init.d/firewall reload")
    try:
        defaults = Path(__file__).resolve().parent.parent / "sources/full/files/etc/uci-defaults/93-technitium-dns"
        guest.run(defaults.read_text())
        guest.run("test \"$(uci -q get firewall.technitium_dns_redirect.enabled)\" = 0")
        assert not query() and not query(tcp=True), "The disabled redirect still accepted external DNS requests"
    finally:
        guest.run("uci set firewall.technitium_dns_redirect.enabled=1\nuci commit firewall\n/etc/init.d/firewall reload")
    assert query() and query(tcp=True), "Restoring the DNS redirect failed"
    print("Forced UDP/TCP DNS increments firewall counters and preserves the original client IP; disabling, upgrade preservation and re-enabling work.", flush=True)


def diagnose(guest):
    print(guest.run(r"""
set +e
printf '\nCI guest boot and process state\n'
cat /proc/cmdline
ubus call service list '{"name":"technitium"}'
ubus call service list '{"name":"technitium-provision"}'
test -e /etc/technitium/provisioned && echo INITIALIZATION_COMPLETE
printf '\nListening sockets\n'
netstat -lntup
printf '\nTerminal authentication command\n'
uci -q get ttyd.@ttyd[0].command
uci -q get ttyd.@ttyd[0].luci_auth
printf '\nLAN and dnsmasq configuration\n'
uci -q get network.lan.ipaddr
uci -q show dhcp
uci -q show uhttpd
printf '\nTechnitium startup messages\n'
logread | grep -Ei 'technitium|dnsmasq|procd|uhttpd' | tail -n 60
for logfile in /tmp/technitium-logs/*.log; do
    test ! -f "$logfile" || tail -n 35 "$logfile"
done
printf '\nLocal DNS queries\n'
timeout 6 nslookup openwrt.lan 127.0.0.1
timeout 6 nslookup openwrt.lan 192.168.1.1
timeout 6 nslookup openwrt.lan 127.0.0.1:5353
printf '\nLAN firewall and routes\n'
nft list chain inet fw4 input
nft list chain inet fw4 input_lan
ip -4 route
printf '\nNative DNS configuration via API\n'
token=$(curl -fsS --max-time 5 -G http://127.0.0.1:5380/api/user/login \
  --data-urlencode user=admin --data-urlencode pass@/etc/technitium/setup-password | jsonfilter -e '@.token')
if test -n "$token"; then
    curl -fsS --max-time 5 -H "Authorization: Bearer $token" http://127.0.0.1:5380/api/settings/get |
      jsonfilter -e '@.response.dnsServerLocalEndPoints' -e '@.response.recursion' -e '@.response.preferIPv6'
    curl -fsS --max-time 5 -H "Authorization: Bearer $token" http://127.0.0.1:5380/api/zones/list |
      jsonfilter -e '@.response.zones[*].name'
    curl -fsS --max-time 5 -H "Authorization: Bearer $token" http://127.0.0.1:5380/api/user/logout >/dev/null
fi
true
""", timeout=50), flush=True)


if __name__ == "__main__":
    action, temporary = sys.argv[1:3]
    guest = Guest(temporary)
    if action == "bootstrap":
        bootstrap(Path(temporary))
    elif action == "check-ipv4":
        guest.run("grep -Eq '(^| )ipv6.disable=1( |$)' /proc/cmdline\ntest ! -s /proc/net/if_inet6")
        print("The guest kernel has IPv6 disabled and no IPv6 interface addresses.", flush=True)
    elif action == "build-identity":
        spec = importlib.util.spec_from_file_location("metadata", Path(__file__).with_name("build-metadata.py"))
        metadata = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metadata)
        actual = json.loads(guest.run("prowrt-version --json"))
        metadata.verify(Path(__file__).resolve().parent.parent, actual)
        assert guest.run("prowrt-version --short").strip() == actual["version"]
        panels = json.loads(guest.run("cat /usr/share/prowrt/openclash-ui.json"))
        for name in ('zashboard', 'metacubexd'):
            assert panels[name]['version'] == actual['dashboards'][name]['version']
            assert panels[name]['sha256'] == actual['dashboards'][name]['sha256']
        guest.run("test -r /rom/usr/share/prowrt/build.json\n"
                  "test -r /www/luci-static/resources/view/status/include/05_prowrt.js\n"
                  "test -r /usr/share/rpcd/acl.d/prowrt-version.json")
        print("Booted image reports the expected ProWrt version and source commit", flush=True)
    elif action == "forced-dns":
        forced_dns(guest)
    elif action == "dns-defaults":
        dns_defaults(guest)
    elif action == "terminal-password":
        password = secrets.token_hex(24)
        guest.run("printf '%s\\n' 'root:" + password + "' | chpasswd")
        password_file = Path(temporary) / "root-password"
        password_file.write_text(password)
        password_file.chmod(0o600)
        print("A disposable system password was set only on the test disk", flush=True)
    elif action == "fixture":
        fixture(guest, Path(sys.argv[3]), Path(__file__).resolve().parent.parent, Path(sys.argv[4]))
    elif action == "diagnose":
        diagnose(guest)
    else:
        raise SystemExit("Unknown disposable VM action")

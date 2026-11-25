#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Adapt the verified QuickStart LuCI entry without patching its Go binary."""
import hashlib
from pathlib import Path
import re
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]


def prepare(package):
    payload = package / 'payload'
    controller = payload / 'usr/lib/lua/luci/controller/istore_backend.lua'
    assets = payload / 'www/luci-static/quickstart'
    index = assets / 'index.js'
    template = payload / 'usr/lib/lua/luci/view/quickstart/main.htm'
    for source, expected in [(controller, 'b09764dc057569768008704ae8d22fe75a6ca5e515bdf59eb35f2d344317975e'),
                             (index, '3664beae40a15c2071eb201adbd67d8cb3b1b5aa0534559747cc6406a458af81'),
                             (template, '734ca12b4f2bc2a1803a123be249b33163ed0ad572548c6f2dcc40d3a5abb73b')]:
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('Review the QuickStart source before adapting device discovery: ' + source.name)
    text = controller.read_text()
    opening = 'function istore_backend()'
    gate = '''
  local path = http.urldecode((http.getenv("REQUEST_URI") or ""):match("^[^?]+") or "")
  local is_devices = http.getenv("REQUEST_METHOD") == "GET" and path:match("^/cgi%-bin/luci/istore/lanctrl/listDevices/?$")
  if http.getenv("REQUEST_METHOD") == "GET" and path:match("^/cgi%-bin/luci/istore/lingjing/snmpSummary/?$") then
    http.prepare_content("application/json")
    if not get_session() then
      http.status(401, "Authentication required")
      http.write_json({success=-1000,error="Authentication required"})
      return
    end
    http.write_json(require("luci.lingjing_snmp_summary").get())
    return
  end
  if http.getenv("REQUEST_METHOD") == "POST" and path:match("^/cgi%-bin/luci/istore/lanctrl/") then
    local discovery = require "luci.prowrt_quickstart_devices"
    local cursor = require("luci.model.uci").cursor()
    if cursor:get('quickstart','main','snmp_discovery') == '1' or discovery.readonly(discovery.interfaces(cursor)) then
      http.status(403, "Read-only discovery")
      http.prepare_content("application/json")
      http.write_json({success=-1000,error="Multi-interface discovery is read-only; use native management pages"})
      return
    end
  end
'''
    assert text.count(opening) == 1
    text = text.replace(opening, opening + gate, 1)
    text = text.replace('  for k, v in pairs(req.message.env) do',
                        '  if is_devices then input[#input+1] = "Accept-Encoding: identity" end\n  for k, v in pairs(req.message.env) do', 1)
    text = text.replace('and not string.find(k, "FORWARDED") then',
                        'and not string.find(k, "FORWARDED") and not (is_devices and k == "HTTP_ACCEPT_ENCODING") then', 1)
    old = '''  local body_buffer = linesrc(true)
  if chunked == 1 then
    ltn12.pump.all(chunksource(sock, body_buffer), http.write)
  else
    local body_source = ltn12.source.cat(ltn12.source.string(body_buffer), sock:blocksource())
    ltn12.pump.all(body_source, http.write)
  end'''
    new = '''  local body_buffer = linesrc(true)
  local body_source
  if chunked == 1 then
    body_source = chunksource(sock, body_buffer)
  else
    body_source = ltn12.source.cat(ltn12.source.string(body_buffer), sock:blocksource())
  end
  if is_devices and sdat ~= nil and num == 200 then
    local chunks, size = {}, 0
    local ok = ltn12.pump.all(body_source, function(chunk, err)
      if err then return nil, err end
      if chunk then
        size = size + #chunk
        if size > 1048576 then return nil, "Device response exceeds limit" end
        chunks[#chunks+1] = chunk
      end
      return 1
    end)
    http.prepare_content("application/json")
    if ok ~= 1 then
      http.status(502, "Device response failed")
      http.write_json({success=-1000,error="Unable to read the device-list response"})
    else
      http.write(require("luci.prowrt_quickstart_devices").response(table.concat(chunks)))
    end
  else
    ltn12.pump.all(body_source, http.write)
  end'''
    assert old in text
    text = text.replace(old, new, 1)
    javascript = index.read_text()
    start = 'const{data:kt}=yield G.DeviceMangement.listDevices.GET();kt.result&&'
    replacement = 'const{data:kt}=yield G.DeviceMangement.listDevices.GET();window.prowrtDevices?.clear();if(kt.success||!kt.result)throw new Error(kt.error||"Invalid device-list response");kt.result.prowrtReadOnly&&window.prowrtDevices?.readonly(!!kt.result.snmpDiscovery);kt.result&&'
    end = '}catch(kt){}finally{P.Close()}}),S='
    assert javascript.count(start) == 1 and javascript.count(end) == 1
    javascript = javascript.replace(start, replacement, 1).replace(end,
        '}catch(kt){p.value=[],m.value=[],window.prowrtDevices?.failure(kt)}finally{P.Close()}}),S=', 1)
    # Exact replacements are guarded by the upstream asset hash above. Do not
    # silently keep an iStore metadata installer for a built-in native service.
    baby = re.findall(r'\{icon:"baby",.*?alink:"/cgi-bin/luci/admin/services/appfilter"\},', javascript)
    assert len(baby) == 1
    javascript = javascript.replace(baby[0], '', 1)
    edits = {
        'if(R.icon=="speed")return m();': 'if(R.icon=="speed"){window.location.href="/cgi-bin/luci/admin/services/fastnet";return;}',
        'w(),h();const _=': 'const _=',
        '{id:"gateway",label:a("\\u6D6E\\u52A8\\u7F51\\u5173")},': '',
        'n({activeTab:x});const C=nt=>{x.value=nt}': 'n({activeTab:x});const C=nt=>{if(nt==="ip"){window.location.href="/cgi-bin/luci/admin/network/eqos";return;}x.value=nt}',
        'onClick:v=>l.value=m,class:lt({active:l.value===m})': 'onClick:v=>{if(m===2){window.location.href="/cgi-bin/luci/admin/network/eqos";return;}l.value=m},class:lt({active:l.value===m})',
        'd=()=>L(this,null,function*(){l.value=3,yield na(),u.value&&(u.value.activeTab="ip")})': 'd=()=>{window.location.href="/cgi-bin/luci/admin/network/eqos"}',
    }
    for before, after in edits.items():
        assert javascript.count(before) == 1, before
        javascript = javascript.replace(before, after, 1)
    recipe = package / 'Makefile'
    assert re.search(r'^PKG_RELEASE:=1$', recipe.read_text(), re.M)
    controller.write_text(text)
    index.write_text(javascript)
    shutil.copy2(REPO / 'packages/quickstart-devices/devices.lua', payload / 'usr/lib/lua/luci/prowrt_quickstart_devices.lua')
    shutil.copy2(REPO / 'packages/quickstart-devices/errors.js', assets / 'prowrt-devices.js')
    with (assets / 'prowrt-devices.js').open('a') as helper:
        helper.write((REPO / 'packages/quickstart-devices/home-count.js').read_text())
    digest = hashlib.sha256()
    for asset in sorted(p for p in assets.rglob('*') if p.is_file()):
        digest.update(asset.relative_to(assets).as_posix().encode() + b'\0' + asset.read_bytes())
    version = 'prowrt-' + digest.hexdigest()[:16]
    html = re.sub(r'v=istoreos-[a-f0-9]+', 'v=' + version, template.read_text())
    html = html.replace('<script type="module"', '<script src="/luci-static/quickstart/prowrt-devices.js?v=' + version + '"></script>\n<script type="module"', 1)
    template.write_text(html)
    makefile = re.sub(r'^PKG_RELEASE:=1$', 'PKG_RELEASE:=3', recipe.read_text(), flags=re.M)
    makefile, count = re.subn(r'^(  DEPENDS:=.*)$', r'\1 +prowrt-snmp-discovery +luci-app-fastnet +luci-app-eqos', makefile, flags=re.M)
    assert count == 1
    recipe.write_text(makefile)
    print('Prepared QuickStart LuCI r3 native service entries and SNMP hooks; Go binary unchanged; assets ' + version)


if __name__ == '__main__':
    prepare(Path(sys.argv[1]).resolve())

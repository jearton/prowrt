-- In-memory boundary checks; no collection or production cache mutation.
local json=require 'luci.jsonc'
local original=require 'nixio.fs'
local now=os.time()
local payload={generatedAt=now,devices={
 {ip='192.168.20.20',mac='00:11:22:33:44:55',observedAt=now,source='dell',vlan='20'},
 {ip='192.168.20.21',mac='00:11:22:33:44:56',observedAt=now-181,source='dell'},
 {ip='192.168.20.20',mac='00:11:22:33:44:55',observedAt=now,source='dell'}},sources={}}
package.loaded['nixio.fs']={stat=function() return {size=100} end,readfile=function() return json.stringify(payload) end}
local m=dofile(arg[1] or '/usr/lib/lua/luci/lingjing_quickstart_snmp.lua')
local r=m.merge({success=0,result={devices={}}})
assert(#r.result.devices==1 and r.result.prowrtReadOnly)
r=m.merge({success=0,result={devices={{ip='192.168.20.20',mac='aa:bb:cc:dd:ee:ff'}}}})
assert(#r.result.devices==1 and r.result.devices[1].mac=='aa:bb:cc:dd:ee:ff')
payload.generatedAt=now-181
r=m.merge({success=0,result={devices={}}});assert(#r.result.devices==0 and not r.result.snmpDiscovery.ready)
r=m.merge({success=-1000,error='Authentication failed'});assert(r.success==-1000 and r.error=='Authentication failed')
package.loaded['nixio.fs']=original
print('PASS: fresh merge, duplicate suppression, native precedence, per-row expiry, cache expiry, error preservation')

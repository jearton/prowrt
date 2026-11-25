-- Authenticated summary for the homepage. Reads local neighbors and recent cache only.
local M={}
function M.get()
 local fs=require 'nixio.fs';local util=require 'luci.util'
 local discovery=require 'luci.prowrt_quickstart_devices'
 local localRows,err=discovery.collect(discovery.interfaces(require('luci.model.uci').cursor()),function(name)return util.ubus('network.interface.'..name,'status',{})end,fs.readfile('/proc/net/arp') or '')
 if not localRows then return {success=-1000,error=err} end
 local r={success=0,result={devices=localRows}}
 local enabled=require('luci.model.uci').cursor():get('quickstart','main','snmp_discovery')=='1'
 if enabled then
  r=require('luci.lingjing_quickstart_snmp').merge(r)
 end
 local d=r.result.snmpDiscovery or {}
 return {success=0,result={total=#r.result.devices,localCount=#localRows-(d.count or 0),snmpCount=d.count or 0,snmpEnabled=enabled,ready=d.ready or false}}
end
return M

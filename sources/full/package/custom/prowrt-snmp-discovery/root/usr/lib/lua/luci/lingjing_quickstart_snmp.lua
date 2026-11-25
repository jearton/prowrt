-- Merge bounded, recent SNMP observations into an authenticated QuickStart response.
local M={}
function M.merge(value)
 if type(value)~='table' or value.success~=0 or type(value.result)~='table' then return value end
 local fs=require 'nixio.fs';local json=require 'luci.jsonc'
 local stat=fs.stat('/tmp/lingjing-snmp/clients.json')
 local data=stat and stat.size<=1048576 and json.parse(fs.readfile('/tmp/lingjing-snmp/clients.json') or '')
 local now=os.time();local result=value.result
 local dhcp=require 'luci.lingjing_dhcp_names'
 local names=dhcp.load(now)
 for _,device in ipairs(result.devices or {}) do dhcp.apply(names,device,now,false) end
 result.prowrtReadOnly=true
 result.snmpDiscovery={ready=false,sources={}}
 if type(data)~='table' or type(data.generatedAt)~='number' or now-data.generatedAt<0 or now-data.generatedAt>180 then return value end
 local seen={};for _,row in ipairs(result.devices or {}) do seen[row.ip]=true end
 local count=0
 for _,row in ipairs(data.devices or {}) do
  if type(row)=='table' and type(row.ip)=='string' and type(row.mac)=='string' and
   row.mac:match('^%x%x:%x%x:%x%x:%x%x:%x%x:%x%x$') and type(row.observedAt)=='number' and
   now-row.observedAt>=0 and now-row.observedAt<=180 and not seen[row.ip] then
   local device={ip=row.ip,mac=row.mac,hostname='SNMP · '..row.source..' · VLAN'..(row.vlan or '?')..(row.stale and ' · 上次采集' or ' · ARP记录'),
    intr='snmp',prowrtReadOnly=true,uploadSpeedStr='—',downloadSpeedStr='—',
    observedAt=row.observedAt,snmpSource=row.source,
    speedLimit={ip=row.ip,mac=row.mac,networkAccess=true},staticAssigned={assignedIP=row.ip,assignedMac=row.mac}}
   dhcp.apply(names,device,now,true)
   result.devices[#result.devices+1]=device
   count=count+1;seen[row.ip]=true
   if count>=4096 then break end
  end
 end
 result.snmpDiscovery={ready=true,count=count,sources=data.sources,generatedAt=data.generatedAt}
 return value
end
return M

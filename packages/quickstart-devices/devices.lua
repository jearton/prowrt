-- SPDX-License-Identifier: MIT
-- Read-only compatibility for the published QuickStart device-list API.
local M = {}
local function array(value) return setmetatable(value or {}, {__jsontype='array'}) end
local function ipv4(value)
    local a,b,c,d=tostring(value):match('^(%d+)%.(%d+)%.(%d+)%.(%d+)$')
    return a and tonumber(a)<=255 and tonumber(b)<=255 and tonumber(c)<=255 and tonumber(d)<=255
end

function M.interfaces(cursor)
    local value = cursor:get('quickstart', 'main', 'device_interfaces')
    if type(value)=='string' then
        local names={}; for name in value:gmatch('%S+') do names[#names+1]=name end;value=names
    end
    if type(value)~='table' or #value==0 then return {'lan'} end
    return value
end

function M.readonly(names) return #names~=1 or names[1]~='lan' end

function M.collect(names, status, arp)
    if #names>16 then return nil, 'Select at most 16 device-list interfaces' end
    local devices, seen, result = {}, {}, array()
    for _,name in ipairs(names) do
        if type(name)~='string' or not name:match('^[%w_%-]+$') then return nil, 'Invalid device-list interface' end
        local info=status(name)
        local device=info and (info.l3_device or info.device)
        if not device then return nil, 'Unable to read selected interface: '..name end
        devices[device]=devices[device] or name
    end
    for line in arp:gmatch('[^\n]+') do
        local ip,kind,flags,mac,mask,device=line:match('^(%S+)%s+(%S+)%s+(%S+)%s+(%S+)%s+(%S+)%s+(%S+)')
        local bits=tonumber(flags)
        if devices[device] and ipv4(ip) and bits and math.floor(bits/2)%2==1 and
           mac:match('^%x%x:%x%x:%x%x:%x%x:%x%x:%x%x$') and mac~='00:00:00:00:00:00' and not seen[ip] then
            seen[ip]=true
            result[#result+1]={intr=devices[device], ip=ip, mac=mac:upper(), prowrtReadOnly=true,
                speedLimit={ip=ip,mac=mac:upper(),networkAccess=true},
                staticAssigned={assignedIP=ip,assignedMac=mac:upper()}}
            if #result>4096 then return nil, 'Device-list result exceeds 4096 neighbors' end
        end
    end
    return result
end

function M.adapt(value, names, status, arp)
    if type(value)~='table' then return nil, 'Invalid QuickStart device-list response' end
    local code=value.success or 0
    if code~=0 then
        -- Only recover the proven empty-ARP exit status. Authentication failures
        -- and all unrelated backend failures retain their original response.
        if code~=-1000 or value.error~='exit status 1' then return value end
        local original=M.collect({'lan'},status,arp)
        if not original or #original~=0 then return value end
    elseif type(value.result)~='table' then
        return nil, 'Missing QuickStart device-list result'
    elseif not M.readonly(names) then
        if value.result.devices~=nil and type(value.result.devices)~='table' then return nil,'Invalid QuickStart devices' end
        value.result.devices=array(value.result.devices)
        -- The Go backend omits success for a successful response. Normalize
        -- that documented shape before passing it to the optional SNMP merge.
        value.success=0
        return value
    end
    local found,err=M.collect(names,status,arp)
    if not found then return nil,err end
    local result=type(value.result)=='table' and value.result or {}
    if result.devices~=nil and type(result.devices)~='table' then return nil,'Invalid QuickStart devices' end
    local selected,seen={},{}
    for _,name in ipairs(names) do selected[name]=true end
    local merged=array()
    for _,item in ipairs(result.devices or {}) do
        if type(item)~='table' then return nil,'Invalid QuickStart device entry' end
        if selected[item.intr or 'lan'] then merged[#merged+1]=item;seen[item.ip]=true end
    end
    for _,item in ipairs(found) do if not seen[item.ip] then merged[#merged+1]=item end end
    result.devices=merged;result.dhcpTags=array(result.dhcpTags)
    result.prowrtReadOnly=M.readonly(names)
    result.discoveryInterfaces=array(names)
    return {success=0,result=result}
end

function M.response(body)
    local json=require 'luci.jsonc'
    local cursor=require('luci.model.uci').cursor()
    local util=require 'luci.util'
    local fs=require 'nixio.fs'
    local native=json.parse(body)
    if type(native)=='table' and native.success and native.success~=0 and
       not (native.success==-1000 and native.error=='exit status 1') then return body end
    local arp=fs.readfile('/proc/net/arp')
    if not arp then return json.stringify({success=-1000,error='Unable to read the ARP table'}) end
    local value,err=M.adapt(native,M.interfaces(cursor),function(name)
        return util.ubus('network.interface.'..name,'status',{})
    end,arp)
    if value and cursor:get('quickstart','main','snmp_discovery')=='1' then
        value=require('luci.lingjing_quickstart_snmp').merge(value)
    end
    return json.stringify(value or {success=-1000,error=err})
end
return M

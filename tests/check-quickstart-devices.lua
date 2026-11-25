-- SPDX-License-Identifier: MIT
local m=dofile(arg[1])
local states={lan={l3_device='br-lan'},rescue={l3_device='br-rescue'}}
local function status(name) return states[name] end
local original={success=-1000,error='exit status 1'}
local value,err=m.adapt(original,{'lan'},status,'IP address HW type Flags HW address Mask Device\n')
assert(not err and value.success==0 and #value.result.devices==0)
assert(getmetatable(value.result.devices).__jsontype=='array')
assert(m.adapt(original,{'lan'},function()end,'')==original)
local other={success=-1000,error='unrelated failure'}
assert(m.adapt(other,{'lan'},status,'')==other)
local denied={success=-1001}
assert(m.adapt(denied,{'lan'},status,'')==denied)
local arp='192.168.1.2 0x1 0x2 02:00:00:00:00:02 * br-lan\n'..
 '192.168.7.2 0x1 0x6 02:00:00:00:00:03 * br-rescue\n'..
 '192.168.7.3 0x1 0x0 00:00:00:00:00:00 * br-rescue\n'..
 '192.168.8.1 0x1 0x2 02:00:00:00:00:04 * wan\n'
local native={success=0,result={devices={{intr='lan',ip='192.168.1.2',mac='02:00:00:00:00:02',vendor='Preserved'}}}}
local merged=m.adapt(native,{'lan','rescue'},status,arp)
assert(#merged.result.devices==2 and merged.result.devices[1].vendor=='Preserved')
assert(merged.result.devices[2].ip=='192.168.7.2' and merged.result.prowrtReadOnly)
assert(m.readonly({'rescue'}) and not m.readonly({'lan'}))
local omitted=m.adapt({result={devices={}}},{'lan'},status,arp)
assert(omitted.success==0 and type(omitted.result.devices)=='table')
local bad,why=m.adapt(native,{'missing'},status,arp)
assert(not bad and why:find('missing'))
bad,why=m.collect({'lan; command'},status,arp)
assert(not bad and why)
assert(#m.collect({'lan'},status,'192..168.1.2 0x1 0x2 02:00:00:00:00:02 * br-lan\n')==0)
print('QuickStart empty ARP, source interfaces, auth errors and real backend failures passed')

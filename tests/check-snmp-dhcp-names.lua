-- Pure in-memory checks; never touch DHCP leases or the production cache.
local n=require'luci.lingjing_dhcp_names';local t=1000;local a={}
assert(n.add(a,'192.168.30.11','AA-BB-CC-DD-EE-01',' Office-PC ','iKuai',t+30,t))
local r={ip='192.168.30.11',mac='aa:bb:cc:dd:ee:01'}
assert(n.apply(a,r,t,false) and r.hostname=='Office-PC' and r.hostnameSource=='iKuai')
assert(not n.apply(a,{ip=r.ip,mac='aa:bb:cc:dd:ee:02'},t,true))
assert(not n.apply(a,{ip='192.168.30.12',mac=r.mac},t,true))
assert(not n.apply(a,{ip=r.ip,mac=r.mac},t+31,true))
assert(not n.add(a,r.ip,r.mac,'expired','iKuai',t,t))
assert(not n.add(a,r.ip,'00:00:00:00:00:00','invalid','iKuai',t+30,t))
local native={ip=r.ip,mac=r.mac,hostname='Native-Name'}
assert(not n.apply(a,native,t,false) and native.hostname=='Native-Name')
assert(n.add(a,r.ip,r.mac,'Different-Name','Technitium',t+30,t))
assert(not n.apply(a,{ip=r.ip,mac=r.mac},t,true))
local fs=require'nixio.fs';local j=require'luci.jsonc';local c={generatedAt=t,names={example={name='Known'}}}
package.loaded['nixio.fs']={stat=function()return{size=100}end,readfile=function()return j.stringify(c)end}
assert(next(n.load(t))~=nil);c.generatedAt=t-181;assert(next(n.load(t))==nil)
c.generatedAt=t+1;assert(next(n.load(t))==nil)
package.loaded['nixio.fs']=fs
print('PASS: tuple match, MAC normalization, IP/MAC mismatch, expiry, invalid MAC, native precedence, conflict, stale/future cache')

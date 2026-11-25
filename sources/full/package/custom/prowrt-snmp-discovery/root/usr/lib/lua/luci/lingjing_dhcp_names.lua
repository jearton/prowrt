-- Pure matching/normalization plus bounded cache reads. DHCP names are data, never HTML.
local M={}
function M.mac(v)
 if type(v)~='string' then return end
 v=v:gsub('[:%.%-]',''):lower()
 if #v~=12 or not v:match('^%x+$') or v=='000000000000' or v=='ffffffffffff' then return end
 return v
end
function M.key(ip,mac)
 if type(ip)~='string' then return end
 local a,b,c,d=ip:match('^(%d+)%.(%d+)%.(%d+)%.(%d+)$')
 if not a or tonumber(a)>255 or tonumber(b)>255 or tonumber(c)>255 or tonumber(d)>255 then return end
 local m=M.mac(mac);if m then return ip..'|'..m end
end
function M.name(v)
 if type(v)~='string' then return end
 v=v:match('^%s*(.-)%s*$')
 if #v==0 or #v>253 or v:find('[%z\1-\31\127]') or v=='-' or v:lower()=='unknown' or v=='(none)' then return end
 return v
end
function M.add(index,ip,mac,name,source,expires,now)
 local k=M.key(ip,mac);name=M.name(name)
 if not k or not name or type(expires)~='number' or expires<=now then return false end
 local old=index[k]
 if old then
  if old.name:lower():gsub('%.$','')~=name:lower():gsub('%.$','') then old.conflict=true end
  old.expires=math.min(old.expires,expires)
 else index[k]={name=name,source=source,expires=expires} end
 return true
end
function M.load(now)
 local fs=require 'nixio.fs';local j=require 'luci.jsonc'
 local path='/tmp/lingjing-dhcp-names/names.json';local s=fs.stat(path)
 local c=s and s.size<=1048576 and j.parse(fs.readfile(path) or '')
 if type(c)~='table' or type(c.generatedAt)~='number' or now<c.generatedAt or now-c.generatedAt>180 or type(c.names)~='table' then return {} end
 return c.names
end
function M.apply(index,row,now,replace)
 local k=M.key(row.ip,row.mac);local x=k and index[k]
 if type(x)~='table' or x.conflict or type(x.expires)~='number' or x.expires<=now or not M.name(x.name) then return false end
 if not replace and M.name(row.hostname) then return false end
 row.hostname=x.name;row.hostnameSource=x.source;row.hostnameValidUntil=x.expires
 row.hostnameLeaseExpires=(x.source=='Technitium' or x.source=='iKuai') and x.expires or nil
 return true
end
return M

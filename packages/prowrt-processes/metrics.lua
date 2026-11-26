-- Read-only /proc enumeration, without shell commands or persistent samples.
local M={}
function M.parse_stat(s)
 if not s then return end
 local pid,comm,tail=s:match('^(%d+)%s+%((.*)%)%s+(.+)$')
 if not pid then return end
 local f={};for v in tail:gmatch('%S+') do f[#f+1]=v end
 local ut,st,start=tonumber(f[12]),tonumber(f[13]),tonumber(f[20])
 if not ut or not st or not start then return end
 return {pid=tonumber(pid),comm=comm,ticks=ut+st,start=start,state=f[1]}
end
function M.collect(fs)
 fs=fs or require 'nixio.fs'
 local total=0;local line=(fs.readfile('/proc/stat') or ''):match('^cpu%s+([^\n]+)')
 assert(line,'CPU counters unavailable')
 local i=0;for v in line:gmatch('%d+') do i=i+1;if i<=8 then total=total+tonumber(v) end end
 local mem=tonumber((fs.readfile('/proc/meminfo') or ''):match('MemTotal:%s+(%d+)'))
 assert(mem and mem>0,'Memory total unavailable')
 local users={}
 for name,id in (fs.readfile('/etc/passwd') or ''):gmatch('([^:\n]+):[^:\n]*:(%d+):[^\n]*') do users[id]=name end
 local rows={}
 for name in fs.dir('/proc') do
  if name:match('^%d+$') then
   local base='/proc/'..name;local p=M.parse_stat(fs.readfile(base..'/stat'))
   local status=fs.readfile(base..'/status')
   if p and status then
    local uid=status:match('\nUid:%s+(%d+)') or '?'
    local rss=tonumber(status:match('\nVmRSS:%s+(%d+)')) or 0
    local cmd=fs.readfile(base..'/cmdline') or ''
    cmd=cmd:gsub('%z',' '):gsub('%s+$',''):gsub('[%c]','?')
    p.command=cmd~='' and cmd or '['..p.comm..']';p.comm=nil
    p.user=users[uid] or uid;p.rss_kib=rss;p.memory_percent=rss/mem*100
    -- Reject mixed identities if PID exited/reused while reading status/cmdline.
    local after=M.parse_stat(fs.readfile(base..'/stat'))
    if after and after.start==p.start then rows[#rows+1]=p end
   end
  end
 end
 return {total_ticks=total,memory_total_kib=mem,processes=rows,cpu_basis='whole-machine',interval_seconds=5}
end
return M

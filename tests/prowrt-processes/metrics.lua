local M=assert(loadfile(arg[1]))()
local function stat(pid,name,ticks,start)
 local f={};for i=1,22 do f[i]='0' end
 f[1]='S';f[12]=tostring(ticks);f[13]='3';f[20]=tostring(start)
 return pid..' ('..name..') '..table.concat(f,' ')
end
local parsed=M.parse_stat(stat('123','a ) strange ( name',42,99))
assert(parsed.pid==123 and parsed.ticks==45 and parsed.start==99)
assert(not M.parse_stat('invalid'))
local fixture={['/proc/stat']='cpu  100 2 30 400 5 6 7 8 50 60\ncpu0 1 2 3',
 ['/proc/meminfo']='MemTotal: 10000 kB\n', ['/etc/passwd']='root:x:0:0:root:/root:/bin/ash\n',
 ['/proc/123/stat']=stat('123','normal',42,99), ['/proc/123/status']='Name: normal\nUid:\t0\t0\nVmRSS:\t1250 kB\n',
 ['/proc/123/cmdline']='a\0b\0', ['/proc/2/stat']=stat('2','kernel',0,1), ['/proc/2/status']='Name: kernel\nUid:\t0\n',
 ['/proc/999/stat']=stat('999','gone',4,2)}
local fs={readfile=function(p)return fixture[p]end,dir=function()local a={'123','2','999','self'};local i=0;return function()i=i+1;return a[i]end end}
local d=M.collect(fs)
assert(d.total_ticks==558 and #d.processes==2)
assert(d.processes[1].rss_kib==1250 and d.processes[1].memory_percent==12.5 and d.processes[1].user=='root')
assert(d.processes[1].command=='a b' and d.processes[2].rss_kib==0)
local reads=0;fs.readfile=function(p) if p=='/proc/123/stat' then reads=reads+1;return stat('123','normal',42,reads==1 and 99 or 100) end;return fixture[p] end
assert(#M.collect(fs).processes==1,'Reused PID must be omitted')
print('PASS: stat names, total CPU excludes guest duplication, RSS, users, kernel threads, exited/reused PIDs')

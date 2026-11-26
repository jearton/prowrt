module('luci.controller.prowrt_processes',package.seeall)
function index()
 local n=entry({'admin','status','prowrt_processes'},call('metrics'))
 n.leaf=true;n.acl_depends={'luci-mod-status-processes'}
end
function metrics()
 local h=require 'luci.http';local u=require 'luci.util'
 local cookie=h.getenv('HTTPS')=='on' and 'sysauth_https' or 'sysauth_http'
 local sid=h.getcookie(cookie) or h.getcookie('sysauth')
 local access=sid and u.ubus('session','access',{ubus_rpc_session=sid,scope='ubus',object='luci',['function']='getProcessList'})
 h.prepare_content('application/json');h.header('Cache-Control','no-store')
 if not access or access.access~=true then h.status(403,'Forbidden');h.write_json({error='Access denied'});return end
 if h.getenv('REQUEST_METHOD')~='GET' then h.status(405,'Method Not Allowed');h.write_json({error='GET required'});return end
 local ok,data=pcall(require('luci.prowrt_process_metrics').collect)
 if not ok then h.status(503,'Service Unavailable');h.write_json({error='Process metrics unavailable'});return end
 h.write_json(data)
end

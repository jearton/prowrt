local M = {}
local fs = require 'nixio.fs'
local sys = require 'luci.sys'
local util = require 'luci.util'
local json = require 'luci.jsonc'
local uci = require('luci.model.uci').cursor()
local cbi = require 'luci.cbi'
local Value, DynamicList, DummyValue = cbi.Value, cbi.DynamicList, cbi.DummyValue
local translate = require('luci.i18n').translate
local directory = '/etc/openclash/dns-link'

local function credentials()
    return json.parse(fs.readfile(directory .. '/credentials.json') or '{}') or {}
end

local function save_credential(key, value)
    if not value or value == '' then return end
    fs.mkdirr(directory)
    fs.chmod(directory, 448) -- 0700, before writing a temporary file
    local data = credentials()
    data[key] = value
    local path = directory .. '/credentials.json.tmp'
    if not fs.writefile(path, json.stringify(data)) then error('Unable to save DNS credentials') end
    fs.chmod(path, 384) -- 0600
    if not fs.rename(path, directory .. '/credentials.json') then error('Unable to save DNS credentials') end
end

function M.add_options(s)
    local function forward_option(kind, name, title, mode)
        local option = s:taboption('dns', kind, name, translate(title))
        option:depends('enable_redirect_dns', mode or '3')
        if not mode then option:depends('enable_redirect_dns', '4') end
        return option
    end
    local o = forward_option(DynamicList, 'dns_link_zones', 'DNS source firewall zones')
    o.datatype = 'uciname'
    o.default = 'lan'
    o.rmempty = false
    uci:foreach('firewall', 'zone', function(zone) if zone.name then o:value(zone.name) end end)
    o.description = translate('Choose all internal source zones, including internal uplinks. DNS query access and TCP/UDP 53 interception are configured only for these zones; management ports are unchanged.')

    o = forward_option(DynamicList, 'dns_link_sources', 'Optional DNS source subnets')
    o.datatype = 'cidr4'
    o.description = translate('Leave empty to allow every source in the selected internal zones. No fixed source IP is required.')

    o = forward_option(DynamicList, 'dns_link_endpoints', 'Local DNS IPv4 addresses')
    o.datatype = 'ip4addr'
    o.description = translate('Leave empty to preserve all local IPv4 DNS endpoints. Direct queries to these addresses keep their original destination; other TCP/UDP 53 requests are redirected to local port 53.')

    o = forward_option(Value, 'dns_link_api_port', 'Local DNS management API port')
    o.datatype = 'port'
    o.placeholder = 'Technitium: 5380 / AdGuard Home: 3000'
    o.description = translate('Connects only to 127.0.0.1. Leave empty for the selected service\'s default port. It does not change the service\'s listening port.')

    for _, item in ipairs({
        {'dns_link_token', 'technitium_token', '3', 'Technitium API token', true},
        {'dns_link_user', 'adguard_user', '4', 'AdGuard Home username', false},
        {'dns_link_password', 'adguard_password', '4', 'AdGuard Home password', true}
    }) do
        local key, masked = item[2], item[5]
        o = forward_option(Value, item[1], item[4], item[3])
        o.password = masked
        o.rmempty = true
        o.description = translate('Stored in a root-only credential file. Leave empty to retain the saved value. Technitium can also use its existing initial setup-password file if the initial administrator password is still valid.')
        function o.cfgvalue(self, section)
            return masked and '' or credentials()[key]
        end
        function o.write(self, section, value) save_credential(key, value) end
        function o.remove() end
    end

    o = s:taboption('dns', DummyValue, '_dns_link_status', translate('DNS linkage last applied state'))
    function o.cfgvalue()
        local state = json.parse(fs.readfile('/var/run/openclash-dns-link.json') or '{}') or {}
        return state.error or ((state.mode or 'not-applied') .. ' ' .. (state.service or '') .. ' ' .. (state.upstream or ''))
    end
end

return M

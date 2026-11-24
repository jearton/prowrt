# SPDX-License-Identifier: GPL-3.0-or-later
require 'minitest/autorun'
require 'tmpdir'
require 'socket'
require_relative '../sources/full/package/custom/luci-app-openclash/root/usr/share/openclash/dns_native_check'
require_relative '../sources/full/package/custom/luci-app-openclash/root/usr/share/openclash/dns_firewall'
require_relative '../sources/full/package/custom/luci-app-openclash/root/usr/share/openclash/dns_link'

class OpenClashDNSTest < Minitest::Test
  GROUP = '代理 分组'

  def test_native_preset_requires_the_user_selected_existing_group_and_never_mutates_yaml
    value = {'dns' => {'enhanced-mode' => 'redir-host', 'nameserver' => ['https://8.8.8.8/dns-query#' + GROUP]}, 'proxy-groups' => [{'name' => GROUP}]}
    original = Marshal.load(Marshal.dump(value))
    options = {'config.enable_custom_dns' => '1', 'prowrt_dns_google' => 'dns_servers', 'prowrt_dns_cloudflare' => 'dns_servers', 'prowrt_dns_google.specific_group' => GROUP, 'prowrt_dns_cloudflare.specific_group' => GROUP}
    get = proc { |name| options.fetch(name, '') }
    assert OpenClashNativeDNS.check(value, get)
    assert_equal original, value
    options['prowrt_dns_google.specific_group'] = 'missing'
    assert_raises(RuntimeError) { OpenClashNativeDNS.check(value, get) }
    assert_equal original, value
    options['config.enable_custom_dns'] = '0'
    refute OpenClashNativeDNS.check(value, get)
  end

  def test_firewall_plan_accepts_multiple_internal_zones_and_two_dns_addresses
    state = {'z1' => {'.type'=>'zone','name'=>'core'}, 'z2'=>{'.type'=>'zone','name'=>'ikuai'},
      'existing_dns'=>{'.type'=>'redirect','src'=>'core','src_dport'=>'53','dest_port'=>'53','dest_ip'=>'192.168.9.3','target'=>'DNAT','src_ip'=>['192.168.20.0/24']}}
    old = Marshal.load(Marshal.dump(state))
    plan, reused = OpenClashDNSFirewall.plan(state, ['core','ikuai'], [], ['192.168.9.3','192.168.8.2'])
    assert_equal old, state
    assert_equal ['existing_dns'], reused['core']
    refute plan.key?('prowrt_dns_redirect_core')
    assert_equal ['192.168.9.3','192.168.8.2'], plan['prowrt_dns_input_ikuai']['dest_ip']
    refute plan['prowrt_dns_input_ikuai'].key?('src_ip')
    assert_equal '!prowrt_dns_endpoints', plan['prowrt_dns_redirect_ikuai']['ipset']
    assert_equal '192.168.9.3', plan['prowrt_dns_redirect_ikuai']['dest_ip']
    assert_equal '53', plan['prowrt_dns_redirect_ikuai']['dest_port']
    assert_raises(OpenClashDNSLink::Failure) { OpenClashDNSFirewall.plan(state, ['unknown'], [], ['192.168.9.3']) }
    state['existing_dns']['dest_port']='7874'
    assert_raises(OpenClashDNSLink::Failure) { OpenClashDNSFirewall.plan(state, ['core'], [], ['192.168.9.3']) }
  end

  class API
    attr_reader :requests
    def initialize(service, state, reject_readback = false)
      @service, @state, @reject_readback, @requests = service, state, reject_readback, []
    end
    def request(path, method = 'GET', body = nil, auth = nil, form = false)
      @requests << [path, method, body, auth, form]
      if path == '/api/settings/set'
        @state = {'forwarders' => ['127.0.0.1:7874'], 'forwarderProtocol' => 'Udp'} unless @reject_readback
        return {'status' => 'ok'}
      elsif path == '/control/dns_config'
        @state = body unless @reject_readback
        return {}
      end
      @service == :technitium ? {'status' => 'ok', 'response' => @state} : @state
    end
  end

  def test_technitium_updates_only_forwarders_once_and_verifies_readback
    http = API.new(:technitium, {'forwarders' => ['old'], 'forwarderProtocol' => 'Tls'})
    adapter = OpenClashDNSLink::Technitium.new(http, {'technitium_token' => 'test-token'})
    original = nil
    assert OpenClashDNSLink.reconcile(adapter, '127.0.0.1:7874') { |before| original = before }
    assert_equal ['old'], original['forwarders']
    assert_equal 1, http.requests.count { |request| request[1] == 'POST' }
    assert_equal 'forwarders=127.0.0.1%3A7874&forwarderProtocol=Udp', http.requests.find { |request| request[1] == 'POST' }[2]
    refute OpenClashDNSLink.reconcile(adapter, '127.0.0.1:7874')
    assert_equal 1, http.requests.count { |request| request[1] == 'POST' }
    assert http.requests.all? { |request| request[3] == 'Bearer test-token' }
  end

  def test_adguard_clears_fallback_and_file_but_does_not_rewrite_clients_or_cache
    http = API.new(:adguard, {'upstream_dns' => ['old', '[/lan/]127.0.0.1:5353'], 'fallback_dns' => ['old-backup'], 'upstream_dns_file' => ''})
    adapter = OpenClashDNSLink::AdGuardHome.new(http, {'adguard_user' => 'admin', 'adguard_password' => 'test:secret'})
    assert OpenClashDNSLink.reconcile(adapter, '127.0.0.1:7874')
    body = http.requests.find { |request| request[1] == 'POST' }[2]
    assert_equal({'upstream_dns' => ['127.0.0.1:7874', '[/lan/]127.0.0.1:5353'], 'fallback_dns' => [], 'upstream_dns_file' => ''}, body)
    refute OpenClashDNSLink.reconcile(adapter, '127.0.0.1:7874')
    assert_equal 1, http.requests.count { |request| request[1] == 'POST' }
  end

  def test_readback_failure_is_not_reported_as_success
    http = API.new(:technitium, {'forwarders' => ['old'], 'forwarderProtocol' => 'Tls'}, true)
    adapter = OpenClashDNSLink::Technitium.new(http, {'technitium_token' => 'test-token'})
    assert_raises(OpenClashDNSLink::Failure) { OpenClashDNSLink.reconcile(adapter, '127.0.0.1:7874') }
  end

  def test_stopping_never_reads_or_modifies_resolver_or_uci
    OpenClashDNSLink.stub(:uci, proc { raise 'Stop must not read UCI or make any upstream changes' }) do
      OpenClashDNSLink.run('stopping')
    end
  end

  def test_jailed_service_listener_must_belong_to_the_selected_procd_tree
    parents = {'103'=>'102', '102'=>'101', '201'=>'1', '1'=>'0'}
    lookup = proc { |pid| parents.fetch(pid, '') }
    assert OpenClashDNSLink.service_process?('103', ['101'], lookup)
    assert OpenClashDNSLink.service_process?('101', ['101'], lookup)
    refute OpenClashDNSLink.service_process?('201', ['101'], lookup)
  end

  def test_default_disabled_profile_does_not_touch_dns_services
    OpenClashDNSLink.stub(:uci, proc { |_name, _fallback = ''| '0' }) do
      OpenClashDNSLink.run('preparing')
    end
  end

  def test_resolver_change_requires_its_own_validated_activation
    armed = {'service' => 'technitium', 'dns_port' => '7875'}
    %w[primary-start reconcile].each do |action|
      assert_nil OpenClashDNSLink.activation_port(action, 'adguardhome', armed, '9999')
      assert_nil OpenClashDNSLink.activation_port(action, 'technitium', {}, '9999')
      assert_equal '7875', OpenClashDNSLink.activation_port(action, 'technitium', armed, '9999')
    end
    assert_equal '7876', OpenClashDNSLink.activation_port('preparing', 'adguardhome', armed, '7876')
  end

  def test_curl_transport_sends_json_and_authorization_without_url_credentials
    server = TCPServer.new('127.0.0.1', 0)
    captured = nil
    worker = Thread.new do
      raise 'HTTP fixture timed out' unless IO.select([server], nil, nil, 10)
      socket = server.accept
      headers = +''
      headers << socket.read(1) until headers.end_with?("\r\n\r\n")
      length = headers[/Content-Length: (\d+)/i, 1].to_i
      captured = [headers, socket.read(length)]
      response = '{"ok":true}'
      socket.write("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: #{response.bytesize}\r\nConnection: close\r\n\r\n#{response}")
      socket.close
    end
    body = {'upstream_dns' => ['127.0.0.1:7874'], 'fixture' => '中文 " quoted'}
    result = OpenClashDNSLink::HTTP.new(server.addr[1]).request('/control/dns_config', 'POST', body, 'Bearer fixture-token')
    worker.value
    assert_equal({'ok' => true}, result)
    assert_equal "POST /control/dns_config HTTP/1.1", captured[0].lines.first.strip
    assert_includes captured[0], 'Authorization: Bearer fixture-token'
    assert_equal body, JSON.parse(captured[1])
  ensure
    server.close if server
    worker.kill if worker && worker.alive?
  end
end

#!/usr/bin/env ruby
# SPDX-License-Identifier: GPL-3.0-or-later
require 'json'

module OpenClashDNSLink
  class Failure < StandardError; end
  class AuthenticationFailure < Failure; end

  # curl receives credentials through stdin, never argv or a URL query.
  class HTTP
    def initialize(port)
      raise Failure, 'Invalid local API port' unless port.to_s.match?(/\A\d+\z/) && (1..65535).cover?(port.to_i)
      @base = "http://127.0.0.1:#{port}"
    end

    def request(path, method = 'GET', body = nil, authorization = nil, form = false)
      config = "silent\nshow-error\nconnect-timeout = 2\nmax-time = 6\nnoproxy = \"*\"\n"
      config += "header = #{JSON.generate('Authorization: ' + authorization)}\n" if authorization
      if body
        config += "header = #{JSON.generate('Content-Type: ' + (form ? 'application/x-www-form-urlencoded' : 'application/json'))}\n"
        config += "data = #{JSON.generate(form ? body : JSON.generate(body))}\n"
      end
      result = IO.popen(['curl', '--config', '-', '--request', method, '--write-out', "\n%{http_code}", @base + path], 'r+') do |io|
        io.write(config)
        io.close_write
        io.read(1024 * 1024 + 1)
      end
      raise Failure, 'Local DNS API unavailable' unless $?.success? && result && result.bytesize <= 1024 * 1024
      payload, _, code = result.rpartition("\n")
      raise AuthenticationFailure, 'Local DNS API authentication rejected' if %w[401 403].include?(code)
      raise Failure, 'Local DNS API request failed' unless code.match?(/\A2\d\d\z/)
      payload.strip.empty? ? {} : JSON.parse(payload)
    rescue JSON::ParserError
      raise Failure, 'Local DNS API returned invalid JSON'
    end
  end

  def self.escape(value)
    value.bytes.map { |byte| byte.chr.match?(/[A-Za-z0-9_.~-]/) ? byte.chr : '%%%02X' % byte }.join
  end

  class Technitium
    def initialize(http, credentials, password_path = '/etc/technitium/setup-password')
      @http = http
      @token = credentials['technitium_token']
      unless @token.to_s.empty?
        raise AuthenticationFailure, 'Invalid Technitium token format' unless @token.match?(/\A[A-Za-z0-9._-]+\z/)
        return
      end
      raise AuthenticationFailure, 'Configure a Technitium API token' unless File.file?(password_path)
      password = File.read(password_path).strip
      result = @http.request('/api/user/login', 'POST', 'user=admin&pass=' + OpenClashDNSLink.escape(password), nil, true)
      @token = result['token']
      raise AuthenticationFailure, 'Technitium login rejected; update API credentials' if @token.to_s.empty?
      @login_token = true
    end

    def api(path, body = nil)
      result = @http.request('/api/' + path, body ? 'POST' : 'GET', body, 'Bearer ' + @token, !!body)
      raise AuthenticationFailure, 'Technitium API rejected access; verify token permissions' unless result['status'] == 'ok'
      result['response'] || result
    end

    def current
      value = api('settings/get')
      {'forwarders' => value['forwarders'], 'forwarderProtocol' => value['forwarderProtocol']}
    end

    def desired(upstream)
      {'forwarders' => [upstream], 'forwarderProtocol' => 'Udp'}
    end

    def save(upstream)
      api('settings/set', 'forwarders=' + OpenClashDNSLink.escape(upstream) + '&forwarderProtocol=Udp')
    end

    def close
      api('user/logout') if @login_token
    rescue Failure
      nil
    end
  end

  class AdGuardHome
    def initialize(http, credentials)
      @http = http
      user, password = credentials.values_at('adguard_user', 'adguard_password')
      raise AuthenticationFailure, 'Configure AdGuard Home credentials' if user.to_s.empty? || password.to_s.empty?
      raise AuthenticationFailure, 'Invalid AdGuard Home username' if user.include?(':')
      @auth = 'Basic ' + [user + ':' + password].pack('m0')
    end

    def current
      value = @http.request('/control/dns_info', 'GET', nil, @auth)
      unless value['upstream_dns_file'].to_s.empty?
        raise Failure, 'Move upstream-file rules into AdGuard Home settings before enabling forwarding; the file is not overwritten'
      end
      @conditional = Array(value['upstream_dns']).select { |server| server.to_s.start_with?('[/') }
      {'upstream_dns' => value['upstream_dns'], 'fallback_dns' => value['fallback_dns'] || [], 'upstream_dns_file' => value['upstream_dns_file'].to_s}
    end

    def desired(upstream)
      {'upstream_dns' => [upstream] + Array(@conditional), 'fallback_dns' => [], 'upstream_dns_file' => ''}
    end

    def save(upstream)
      @http.request('/control/dns_config', 'POST', desired(upstream), @auth)
    end

    def close; end
  end

  # Only upstream fields are changed. Zones, leases, filtering and cache are
  # owned by the selected resolver and are not rewritten by this integration.
  def self.reconcile(adapter, upstream)
    before = adapter.current
    expected = adapter.desired(upstream)
    return false if before == expected
    yield before if block_given?
    adapter.save(upstream)
    raise Failure, 'Saved upstream readback mismatch' unless adapter.current == expected
    true
  ensure
    adapter.close
  end

  def self.uci(name, fallback = '')
    ['openclash.@overwrite[0].', 'openclash.config.'].each do |prefix|
      value = IO.popen(['uci', '-q', 'get', prefix + name], &:read).strip
      return value unless value.empty?
    end
    fallback
  end

  def self.atomic_json(path, value)
    temporary = "#{path}.#{Process.pid}"
    begin
      File.open(temporary, File::WRONLY | File::CREAT | File::EXCL, 0o600) { |file| file.write(JSON.generate(value) + "\n") }
      File.rename(temporary, path)
    ensure
      File.unlink(temporary) if File.exist?(temporary)
    end
  end

  def self.activation_port(action, service, armed, core_port)
    return core_port || uci('dns_port', '7874') if %w[preparing ready].include?(action)
    # Saving a different resolver selection must not reuse the previous
    # service's activation or redirect it before a validated core startup.
    return unless armed['service'] == service
    armed['dns_port']
  end

  def self.service_process?(pid, roots, parent = nil)
    parent ||= proc { |value| File.read('/proc/' + value + '/status')[/^PPid:\s+(\d+)/, 1].to_s }
    32.times do
      return true if roots.include?(pid)
      return false unless pid.match?(/\A[1-9]\d*\z/)
      previous, pid = pid, parent.call(pid)
      return false if pid.empty? || pid == previous
    end
    false
  rescue Errno::ENOENT
    false
  end

  def self.verify_listener(service, endpoints = nil)
    value = IO.popen(['ubus', 'call', 'service', 'list', JSON.generate({'name' => service})], &:read)
    instances = JSON.parse(value).dig(service, 'instances') || {}
    pids = instances.values.map { |instance| instance['pid'].to_s }.reject(&:empty?)
    rows = IO.popen(['netstat', '-lnptu'], err: File::NULL, &:read).lines.map(&:split)
    %w[tcp udp].each do |protocol|
      sockets = rows.select do |row|
        owner = row.find { |field| field.match?(/\A\d+\//) }.to_s.split('/').first.to_s
        row[0] == protocol && row[3].to_s.end_with?(':53') && service_process?(owner, pids)
      end.map { |row| row[3].sub(/:53\z/, '') }
      raise Failure, 'Start the selected DNS service on TCP/UDP port 53 before applying forwarding' if sockets.empty?
      if endpoints && !sockets.include?('0.0.0.0') && (endpoints - sockets).any?
        raise Failure, 'The selected DNS service does not listen on all chosen DNS addresses'
      end
    end
  end

  def self.run(action, primary_service = nil, core_port = nil)
    state_path = '/var/run/openclash-dns-link.json'
    if action == 'status'
      puts(File.file?(state_path) ? File.read(state_path) : '{"mode":"not-applied"}')
      return
    end
    raise Failure, 'Unknown DNS linkage action' unless %w[preparing ready reconcile primary-start stopping].include?(action)
    # Stop never restores, clears, or substitutes any resolver upstream.
    return if action == 'stopping'
    service = {'3' => 'technitium', '4' => 'adguardhome'}[uci('enable_redirect_dns', '0')]
    return unless service
    return if action == 'primary-start' && primary_service != service
    activation = '/etc/openclash/dns-link/activated'
    armed = File.file?(activation) ? JSON.parse(File.read(activation)) : {}
    port = activation_port(action, service, armed, core_port)
    return if port.nil?
    port = port.to_s
    raise Failure, 'Invalid Mihomo DNS port' unless port.match?(/\A\d+\z/) && (1..65535).cover?(port.to_i)
    directory = '/etc/openclash/dns-link'
    Dir.mkdir(directory, 0o700) unless Dir.exist?(directory)
    File.chmod(0o700, directory)
    # Only OpenClash's post-validation startup may arm linkage. Merely saving
    # a preset must not break a fresh installation before a valid core exists.
    return unless %w[preparing ready].include?(action) || File.file?(activation)
    credentials_path = directory + '/credentials.json'
    credentials = File.file?(credentials_path) ? JSON.parse(File.read(credentials_path)) : {}
    revision = [uci('dns_link_api_port', service == 'technitium' ? '5380' : '3000')] + [credentials_path, '/etc/technitium/setup-password'].map { |path| File.file?(path) ? [File.mtime(path).to_f, File.size(path)] : nil }
    previous = File.file?(state_path) ? JSON.parse(File.read(state_path)) : {}
    # Do not repeatedly submit rejected credentials from the existing watchdog.
    return false if previous['auth_error'] && previous['credential_revision'] == revision && previous['service'] == service
    File.open(directory + '/lock', File::RDWR | File::CREAT, 0o600) do |lock|
      unless lock.flock(File::LOCK_EX | File::LOCK_NB)
        raise Failure, 'DNS linkage is busy; retry OpenClash startup after the active task finishes' if action == 'preparing'
        return
      end
      api_port = uci('dns_link_api_port', service == 'technitium' ? '5380' : '3000')
      http = HTTP.new(api_port)
      # One bounded startup task; no new periodic process and no login retries.
      if action == 'primary-start'
        available = false
        10.times do
          begin
            http.request(service == 'technitium' ? '/api/status' : '/control/status')
            available = true
            break
          rescue AuthenticationFailure
            available = true
            break
          rescue Failure
            sleep 1
          end
        end
        raise Failure, 'Resolver startup API unavailable' unless available
      end
      verify_listener(service) if %w[preparing ready].include?(action)
      adapter = service == 'technitium' ? Technitium.new(http, credentials) : AdGuardHome.new(http, credentials)
      upstream = '127.0.0.1:' + port
      changed = reconcile(adapter, upstream) do |before|
        backup = directory + '/before-' + service + '.json'
        atomic_json(backup, {'service' => service, 'upstream' => before, 'saved_at' => Time.now.utc.strftime('%FT%TZ')}) unless File.exist?(backup)
      end
      atomic_json(activation, {'service' => service, 'dns_port' => port}) if %w[preparing ready].include?(action)
      state = {'mode' => 'fixed-mihomo', 'service' => service, 'upstream' => upstream, 'credential_revision' => revision}
      if changed || previous != state
        atomic_json(state_path, state)
        system('logger', '-t', 'openclash-dns-link', "service=#{service} mode=fixed-mihomo settings_changed=#{changed ? 1 : 0}")
      end
    end
  rescue Failure => error
    atomic_json(state_path, {'mode' => 'error', 'service' => service, 'auth_error' => error.is_a?(AuthenticationFailure), 'credential_revision' => revision, 'error' => error.message})
    raise
  end
end

if $PROGRAM_NAME == __FILE__
  begin
    # An authentication latch suppresses repeated logins but must still block
    # startup; returning success would leave a public upstream in use.
    exit 1 if OpenClashDNSLink.run(ARGV[0] || 'status', ARGV[1], ARGV[2]) == false
  rescue OpenClashDNSLink::Failure => error
    system('logger', '-t', 'openclash-dns-link', error.message)
    warn error.message
    exit 1
  rescue StandardError => error
    # Raw response/parser exceptions can contain credentials. Log type only.
    system('logger', '-t', 'openclash-dns-link', "DNS linkage failed (#{error.class}); no public DNS fallback")
    exit 1
  end
end

#!/usr/bin/env ruby
# SPDX-License-Identifier: GPL-3.0-or-later
require_relative 'dns_link'

module OpenClashDNSFirewall
  def self.command(*arguments)
    result = IO.popen(arguments, &:read)
    raise OpenClashDNSLink::Failure, 'DNS firewall command failed: ' + arguments.first unless $?.success?
    result
  end

  def self.config
    JSON.parse(command('ubus', 'call', 'uci', 'get', '{"config":"firewall"}')).fetch('values')
  end

  def self.local_addresses
    command('ip', '-o', '-4', 'addr', 'show').scan(/\binet (\d+\.\d+\.\d+\.\d+)\//).flatten.reject { |ip| ip.start_with?('127.') }.uniq.sort
  end

  def self.valid_ip?(value, cidr = false)
    ip, prefix = value.to_s.split('/', 2)
    return false unless ip && ip.match?(/\A\d+\.\d+\.\d+\.\d+\z/) && ip.split('.').all? { |part| part.to_i <= 255 }
    prefix.nil? || (cidr && prefix.match?(/\A\d+\z/) && (0..32).cover?(prefix.to_i))
  end

  def self.plan(existing, zones, sources, endpoints, target = endpoints.first)
    known = existing.values.select { |item| item['.type'] == 'zone' }.map { |item| item['name'] }
    raise OpenClashDNSLink::Failure, 'Choose existing internal DNS source zones' if zones.empty? || zones.any? { |zone| !zone.match?(/\A[A-Za-z0-9_-]+\z/) || !known.include?(zone) }
    raise OpenClashDNSLink::Failure, 'Invalid DNS source subnet or endpoint' unless sources.all? { |source| valid_ip?(source, true) } && !endpoints.empty? && endpoints.all? { |ip| valid_ip?(ip) }
    desired = {'prowrt_dns_endpoints' => {'.type' => 'ipset', 'name' => 'prowrt_dns_endpoints', 'family' => 'ipv4', 'match' => ['dest_ip'], 'entry' => endpoints}}
    reused = {}
    zones.each do |zone|
      redirects = existing.select do |_name, item|
        item['.type'] == 'redirect' && item['src'] == zone && item.fetch('enabled', '1') != '0' && item['src_dport'] == '53'
      end
      # Existing site-specific interception remains authoritative. Validate its
      # local destination, preserve its source restrictions and reuse it.
      redirects.each do |name, item|
        generated = (name.start_with?('prowrt_dns_redirect_') || name == 'technitium_dns_redirect') && item['name'].to_s.start_with?('ProWrt ')
        next if generated
        destination = item['dest_ip'].to_s
        unless item['target'] == 'DNAT' && item.fetch('dest_port', '53') == '53' && (destination.empty? || endpoints.include?(destination))
          raise OpenClashDNSLink::Failure, 'Conflicting DNS redirect in zone ' + zone + '; review existing firewall rules'
        end
      end
      reused[zone] = redirects.keys
      # Adopt the old ProWrt factory rule only when its unrestricted shape is
      # known. Custom site rules are reused without rewriting their contents.
      legacy = existing['technitium_dns_redirect']
      adopt = legacy && (legacy['name'] == 'Force LAN DNS to router' || legacy['name'].to_s.start_with?('ProWrt ')) && legacy['src'] == zone && legacy['src_dport'] == '53' && legacy['target'] == 'DNAT' && legacy['dest_port'] == '53' && (legacy['name'].to_s.start_with?('ProWrt ') || legacy['dest_ip'].to_s.empty? || endpoints.include?(legacy['dest_ip'])) && !legacy.key?('src_ip') && !legacy.key?('src_dip')
      owned = adopt ? 'technitium_dns_redirect' : 'prowrt_dns_redirect_' + zone
      if adopt || redirects.empty? || redirects.keys == [owned]
        desired[owned] = {'.type' => 'redirect', 'name' => 'ProWrt local DNS ' + zone, 'src' => zone,
          'proto' => ['tcp', 'udp'], 'src_dport' => '53', 'dest_port' => '53', 'target' => 'DNAT',
          'family' => 'ipv4', 'reflection' => '0', 'enabled' => '1', 'ipset' => '!prowrt_dns_endpoints'}
        desired[owned]['dest_ip'] = target if target
        desired[owned]['src_ip'] = sources unless sources.empty?
        reused[zone] = []
      end
      desired['prowrt_dns_input_' + zone] = {'.type' => 'rule', 'name' => 'ProWrt allow DNS ' + zone,
        'src' => zone, 'proto' => ['tcp', 'udp'], 'dest_ip' => endpoints, 'dest_port' => '53', 'family' => 'ipv4', 'target' => 'ACCEPT'}
      desired['prowrt_dns_input_' + zone]['src_ip'] = sources unless sources.empty?
    end
    [desired, reused]
  end

  def self.replace(name, item)
    command('uci', '-q', 'delete', 'firewall.' + name) if config.key?(name)
    return unless item
    command('uci', 'set', 'firewall.' + name + '=' + item.fetch('.type'))
    item.each do |key, value|
      next if key.start_with?('.')
      if value.is_a?(Array)
        value.each { |entry| command('uci', 'add_list', "firewall.#{name}.#{key}=#{entry}") }
      else
        command('uci', 'set', "firewall.#{name}.#{key}=#{value}")
      end
    end
    # A zone explicitly selected as internal must get DNS-only INPUT access
    # before generic WAN DNS rejection; never widen management-port access.
    command('uci', 'reorder', 'firewall.' + name + '=0') if name.start_with?('prowrt_dns_input_')
  end

  def self.apply
    service = {'3' => 'technitium', '4' => 'adguardhome'}[OpenClashDNSLink.uci('enable_redirect_dns', '0')]
    return unless service
    existing = config
    raise OpenClashDNSLink::Failure, 'Commit or discard pending firewall edits before applying DNS forwarding' unless command('uci', 'changes', 'firewall').strip.empty?
    zones = OpenClashDNSLink.uci('dns_link_zones', 'lan').split.uniq
    sources = OpenClashDNSLink.uci('dns_link_sources').split.uniq
    owned_addresses = local_addresses
    endpoints = OpenClashDNSLink.uci('dns_link_endpoints').split.uniq
    automatic_endpoints = endpoints.empty?
    endpoints = owned_addresses if endpoints.empty?
    raise OpenClashDNSLink::Failure, 'DNS endpoints must be local interface addresses' unless (endpoints - owned_addresses).empty?
    OpenClashDNSLink.verify_listener(service, endpoints)
    desired, reused = plan(existing, zones, sources, endpoints, automatic_endpoints ? nil : endpoints.first)
    path = '/etc/openclash/dns-link/firewall-before'
    File.open(path, File::WRONLY | File::CREAT | File::EXCL, 0o600) { |file| file.write(command('uci', 'export', 'firewall')) } unless File.exist?(path)
    changed = false
    touched = []
    begin
      desired.each do |name, item|
        actual = existing[name]&.reject { |key, _| key.start_with?('.') && key != '.type' }
        next if actual == item
        if existing.key?(name) && name.start_with?('prowrt_dns_') && actual && actual['name'].to_s !~ /\AProWrt |\Aprowrt_dns_endpoints\z/
          raise OpenClashDNSLink::Failure, 'Existing DNS section name collision: ' + name
        end
        touched << name
        changed = true
        replace(name, item)
      end
      # Remove only stale sections generated by this feature, never site rules.
      existing.each do |name, item|
        next unless (name == 'technitium_dns_redirect' || name.start_with?('prowrt_dns_redirect_', 'prowrt_dns_input_')) && item['name'].to_s.start_with?('ProWrt ')
        next if desired.key?(name)
        touched << name
        replace(name, nil)
        changed = true
      end
      if changed
        command('fw4', 'check')
        command('uci', 'commit', 'firewall')
        command('/etc/init.d/firewall', 'reload')
      end
      readback = config
      raise OpenClashDNSLink::Failure, 'DNS firewall readback failed' unless desired.all? { |name, item| readback[name]&.reject { |key, _| key.start_with?('.') && key != '.type' } == item }
      state = {'zones' => zones, 'endpoints' => endpoints, 'reused_redirects' => reused, 'changed' => changed,
        'managed_redirects' => desired.select { |_name, item| item['.type'] == 'redirect' }.keys}
      OpenClashDNSLink.atomic_json('/var/run/openclash-dns-firewall.json', state)
      OpenClashDNSLink.atomic_json('/etc/openclash/dns-link/firewall-managed.json', state)
    rescue StandardError
      command('uci', 'revert', 'firewall')
      # Restore only sections touched by this transaction, not unrelated rules.
      touched.uniq.each { |name| replace(name, existing[name]) }
      if changed
        command('uci', 'commit', 'firewall')
        command('/etc/init.d/firewall', 'reload')
      end
      raise
    end
  end

  def self.deactivate
    path = '/etc/openclash/dns-link/firewall-managed.json'
    return unless File.file?(path)
    raise OpenClashDNSLink::Failure, 'Commit pending firewall edits first' unless command('uci', 'changes', 'firewall').strip.empty?
    state = JSON.parse(File.read(path))
    existing = config
    changed = false
    touched = []
    Array(state['managed_redirects']).each do |name|
      item = existing[name]
      next unless item && item['name'].to_s.start_with?('ProWrt ') && item['dest_port'] == '53' && item['enabled'] != '0'
      command('uci', 'set', 'firewall.' + name + '.enabled=0')
      touched << name
      changed = true
    end
    if changed
      command('fw4', 'check')
      command('uci', 'commit', 'firewall')
      command('/etc/init.d/firewall', 'reload')
    end
  rescue StandardError
    if touched && !touched.empty?
      command('uci', 'revert', 'firewall')
      touched.each { |name| replace(name, existing[name]) }
      if changed
        command('uci', 'commit', 'firewall')
        command('/etc/init.d/firewall', 'reload')
      end
    end
    raise
  end
end

if $PROGRAM_NAME == __FILE__
  begin
    File.open('/var/run/openclash-dns-fw.lock', File::RDWR | File::CREAT, 0o600) do |lock|
      lock.flock(File::LOCK_EX)
      ARGV[0] == 'deactivate' ? OpenClashDNSFirewall.deactivate : OpenClashDNSFirewall.apply
    end
  rescue StandardError => error
    detail = error.is_a?(OpenClashDNSLink::Failure) ? error.message : error.class.to_s
    system('logger', '-t', 'openclash-dns-link', 'DNS firewall failed: ' + detail)
    warn 'DNS firewall failed: ' + detail
    exit 1
  end
end

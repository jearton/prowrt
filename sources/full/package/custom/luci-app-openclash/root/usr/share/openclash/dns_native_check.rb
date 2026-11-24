#!/usr/bin/env ruby
# SPDX-License-Identifier: GPL-3.0-or-later
require 'yaml'

module OpenClashNativeDNS
  def self.uci(key)
    IO.popen(['uci', '-q', 'get', 'openclash.' + key], &:read).strip
  end

  # Validate the ordinary OpenClash DNS server entries. Never create a proxy
  # group, generate its DNS configuration or choose an outbound on behalf of
  # the administrator. The preset is inactive until native custom DNS is on.
  def self.check(config, get = method(:uci))
    enabled = get.call('@overwrite[0].enable_custom_dns')
    enabled = get.call('config.enable_custom_dns') if enabled.empty?
    return false unless enabled == '1'
    entries = %w[prowrt_dns_google prowrt_dns_cloudflare]
    active = entries.select { |entry| get.call(entry) == 'dns_servers' && get.call(entry + '.enabled') != '0' }
    return false if active.empty?
    groups = Array(config['proxy-groups']).select { |item| item.is_a?(Hash) }.map { |item| item['name'] }
    active.each do |entry|
      group = get.call(entry + '.specific_group')
      raise 'Choose an existing proxy group for each native preset DNS server' if group.empty? || group == 'Disable' || group.match?(/[\x00-\x1f\x7f#&=?]/) || (!groups.include?(group) && group != 'GLOBAL')
      # Native OpenClash can silently drop an invalid selector. Require the
      # resulting DNS entry to retain the explicitly selected group.
      suffix = '#' + group
      raise 'The native DNS overwrite did not retain the selected proxy group' unless Array(config.dig('dns', 'nameserver')).any? { |server| server.to_s.end_with?(suffix) || server.to_s.include?(suffix + '&') }
    end
    raise 'The shared-resolver preset requires Redir-Host; choose it in OpenClash' unless config.dig('dns', 'enhanced-mode') == 'redir-host'
    true
  end
end

if $PROGRAM_NAME == __FILE__
  begin
    OpenClashNativeDNS.check(YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true))
  rescue StandardError => error
    detail = error.is_a?(RuntimeError) ? error.message : 'Unable to validate native DNS settings'
    warn detail
    exit 1
  end
end

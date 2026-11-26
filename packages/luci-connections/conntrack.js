// SPDX-License-Identifier: Apache-2.0
// Parser semantics follow LuCI's luci.sys.conntrack_list().
'use strict';
'require baseclass';

return baseclass.extend({
	protocols(lines) {
		const protocols = Object.create(null);
		for (const line of lines) {
			const m = line.match(/^([^# \t\n]+)\s+([0-9]+)\s+/);
			if (m) protocols[m[2]] = m[1];
		}
		return protocols;
	},

	address(address) {
		const groups = address.split(':');
		if (groups.length !== 8 || !groups.every(g => /^[0-9a-f]{1,4}$/i.test(g))) return address;
		const parts = groups.map(g => parseInt(g, 16).toString(16));
		let start = -1, size = 1;
		for (let i = 0; i < 8;) {
			if (parts[i] !== '0') { i++; continue; }
			let end = i;
			while (end < 8 && parts[end] === '0') end++;
			if (end - i > size) { start = i; size = end - i; }
			i = end;
		}
		if (start < 0) return parts.join(':');
		return parts.slice(0, start).join(':') + '::' + parts.slice(start + size).join(':');
	},

	parse(raw, protocols) {
		const connections = [];
		for (const line of raw.split('\n')) {
			const m = line.trim().match(/^(ipv[46]) +([0-9]+) +\S+ +([0-9]+)( +.+)$/);
			if (!m || /\bTIME_WAIT\b/.test(m[4])) continue;
			const timeout = m[4].match(/^ +(\d+)(?: |$)/);
			const item = { layer3: m[1], layer4: protocols[m[3]] || 'unknown', timeout: timeout ? +timeout[1] : 0, bytes: 0, packets: 0 };
			for (const kv of m[4].matchAll(/ (\w+)=(\S+)/g)) {
				const key = kv[1], value = kv[2];
				if (key === 'bytes' || key === 'packets') item[key] += Number(value) || 0;
				else if (key === 'src' || key === 'dst') item[key] ??= this.address(value);
				else if (key === 'sport' || key === 'dport') item[key] ??= +value;
				else item[key] = value;
			}
			if (!item.src || !item.dst) continue;
			if ((item.src === '127.0.0.1' && item.dst === '127.0.0.1') || (item.src === '::1' && item.dst === '::1')) continue;
			connections.push(item);
		}
		return connections;
	},

	sort(rows, column, descending, compare) {
		return rows.sort((a, b) => {
			const x = Array.isArray(a[column]) ? a[column][0] : a[column];
			const y = Array.isArray(b[column]) ? b[column][0] : b[column];
			const result = column === 4 ? Number(x) - Number(y) : compare(String(x), String(y));
			return descending ? -result : result;
		});
	},

	page(rows, index, size) {
		const pages = Math.max(1, Math.ceil(rows.length / size));
		const current = Math.min(Math.max(0, index), pages - 1);
		return { rows: rows.slice(current * size, (current + 1) * size), current, pages, total: rows.length };
	}
});

'use strict';
'require view';
'require poll';
'require request';
'require rpc';
'require fs';
'require ui';
'require tools.prowrt_conntrack_v1 as conntrack';

const callLuciRealtimeStats = rpc.declare({
	object: 'luci',
	method: 'getRealtimeStats',
	params: [ 'mode', 'device' ],
	expect: { result: [] }
});

const callNetworkRrdnsLookup = rpc.declare({
	object: 'network.rrdns',
	method: 'lookup',
	params: [ 'addrs', 'timeout', 'limit' ],
	expect: { '': {} }
});

const callLuciRpcGetHostHints = rpc.declare({
	object: 'luci-rpc',
	method: 'getHostHints',
	expect: { '': {} }
});

const callLuciRpcGetNetworkDevices = rpc.declare({
	object: 'luci-rpc',
	method: 'getNetworkDevices',
	expect: { '': {} }
});

const callLuciRpcGetDHCPLeases = rpc.declare({
	object: 'luci-rpc',
	method: 'getDHCPLeases',
	expect: { '': {} }
});

const graphPolls = [];
const pollInterval = 3;
const dns_cache = Object.create(null);
const service_cache = Object.create(null);
const ethers_cache = Object.create(null);
let ethers_cache_is_loaded = false;
let enableLookups = false;
let filterText = '';

const recheck_lookup_queue = {};

Math.log2 = Math.log2 || function(x) { return Math.log(x) * Math.LOG2E; };

return view.extend({
	load() {
		return Promise.all([
			this.loadSVG(L.resource('svg/connections.svg')),
			fs.lines('/etc/protocols')
		]);
	},

	updateGraph(svg, lines, cb) {
		const G = svg.firstElementChild;

		const view = document.querySelector('#view');

		const width  = view.offsetWidth - 2;
		const height = 300 - 2;
		const step   = 5;

		const data_wanted = Math.floor(width / step);

		const data_values = [];

		for (let line of lines)
			if (line != null)
				data_values.push([]);

		const info = {
			line_current: [],
			line_average: [],
			line_peak:    []
		};

		/* prefill datasets */
		for (let dv of data_values)
			for (let j = 0; j < data_wanted; j++)
					dv[j] = 0;

		/* plot horizontal time interval lines */
		for (let i = width % (step * 60); i < width; i += step * 60) {
			const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
			line.setAttribute('x1', i);
			line.setAttribute('y1', 0);
			line.setAttribute('x2', i);
			line.setAttribute('y2', '100%');
			line.setAttribute('style', 'stroke:black;stroke-width:0.1');

			const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
			text.setAttribute('x', i + 5);
			text.setAttribute('y', 15);
			text.setAttribute('style', 'fill:#eee; font-size:9pt; font-family:sans-serif; text-shadow:1px 1px 1px #000');
			text.appendChild(document.createTextNode(Math.round((width - i) / step / 60) + 'm'));

			G.appendChild(line);
			G.appendChild(text);
		}

		info.interval = pollInterval;
		info.timeframe = data_wanted / 60;

		graphPolls.push({
			svg:    svg,
			lines:  lines,
			cb:     cb,
			info:   info,
			width:  width,
			height: height,
			step:   step,
			values: data_values,
			timestamp: 0,
			fill: 1
		});
	},

	async updateConntrack(conn, renderOnly = false) {
			async function fetchServices() {
					if (!enableLookups) return;
					if (Object.keys(service_cache).length > 0) return;

					try {
							const rawData = await fs.read('/etc/services');
							const lines = rawData.split('\n');

							for (const line of lines) {
									const match = line.match(/^([\w-]+)\s+(\d+)\/(\w+)/);
									if (match) {
											const service = match[1].toUpperCase();
											const port = match[2];
											const protocol = match[3].toUpperCase();
											if (!(port in service_cache)) service_cache[port] = {};
											service_cache[port][protocol] = service;
									}
							}
					} catch (err) {
							console.error('Error fetching services:', err);
					}
			}

			function joinAddressWithPortOrServiceName(address, port, protocol) {
					if (!port) return address;
					if (enableLookups) {
							const service = service_cache[port]?.[protocol];
							if (service) return `${address}:${service}`;
					}
					return `${address}:${port}`;
			}

			await fetchServices();

			const lookup_queue = new Set();
			const rows = [];

			conn.sort((a, b) => b.bytes - a.bytes);

			for (const c of conn) {
					if ((c.src === '127.0.0.1' && c.dst === '127.0.0.1') ||
							(c.src === '::1' && c.dst === '::1'))
							continue;

					if (enableLookups) {
							if (!(c.src in dns_cache)) lookup_queue.add(c.src);
							if (!(c.dst in dns_cache)) lookup_queue.add(c.dst);
					}

					const src = enableLookups && (c.src in dns_cache) ? dns_cache[c.src] : (c.layer3 === 'ipv6' ? `[${c.src}]` : c.src);
					const dst = enableLookups && (c.dst in dns_cache) ? dns_cache[c.dst] : (c.layer3 === 'ipv6' ? `[${c.dst}]` : c.dst);
					const network = c.layer3.toUpperCase();
					const protocol = c.layer4.toUpperCase();
					const source = '%h'.format(joinAddressWithPortOrServiceName(src, c.sport, protocol));
					const destination = '%h'.format(joinAddressWithPortOrServiceName(dst, c.dport, protocol));
					const transfer = [c.bytes, '%1024.2mB (%d %s)'.format(c.bytes, c.packets, _('Pkts.'))];

					if (filterText) {
							const filterTextExpressions = filterText.split(' ');
							if (filterTextExpressions.some(el => el.toUpperCase() !== network && el.toUpperCase() !== protocol
									&& !c.src.includes(el) && !source.includes(el)
									&& !c.dst.includes(el) && !destination.includes(el))) {
									continue;
							}
					}

					rows.push([network, protocol, source, destination, transfer]);
			}

			this.connectionRows = conntrack.sort(rows, this.sortColumn, this.sortDescending, L.naturalCompare);
			this.renderPage();

			if (renderOnly || !enableLookups || lookup_queue.size === 0) return;

			const reduced_lookup_queue = lookup_queue.size > 100
					? new Set([...lookup_queue].slice(0, 100))
					: new Set(lookup_queue);

			async function softFailure(fn) {
					try {
							return await fn();
					} catch (err) {
							console.debug('Lookup failed:', err);
							return null;
					}
			}

			function updateDnsCache(addr, name) {
					if (!addr || !name) return;
					if (!(addr in dns_cache)) dns_cache[addr] = name;
					lookup_queue.delete(addr);
					reduced_lookup_queue.delete(addr);
			}

			// 1. DHCP Leases
			const leases = await softFailure(() => callLuciRpcGetDHCPLeases());
			if (leases && Object.keys(leases).length !== 0) {
					for (const lease of [...(leases.dhcp_leases || []), ...(leases.dhcp6_leases || [])]) {
							const addr = lease.ipaddr || lease.ip6addr;
							updateDnsCache(addr, lease.hostname);
					}
			}

			if (reduced_lookup_queue.size > 0) {
					// 2. Reverse DNS Lookup
					const dnsReplies = await softFailure(() => callNetworkRrdnsLookup([...reduced_lookup_queue], 5000, 1000));
					if (dnsReplies && Object.keys(dnsReplies).length !== 0) {
							for (const addr of Object.keys(dnsReplies)) updateDnsCache(addr, dnsReplies[addr]);
					}
			}

			if (reduced_lookup_queue.size > 0) {
					// 3. Resolve names via hints
					const hints = ethers_cache_is_loaded ? ethers_cache : await softFailure(() => callLuciRpcGetHostHints());

					if (hints && Object.keys(hints).length !== 0) {
							for (const [ether, obj] of Object.entries(hints)) {
									if (!ether || !obj?.name) continue;
									if (!(ether in ethers_cache) && Object.keys(obj).length !== 0) ethers_cache[ether] = obj;
									for (const addr of [...(obj.ipaddrs || []), ...(obj.ip6addrs || [])])
											updateDnsCache(addr, obj.name);
							}
							if (Object.keys(ethers_cache).length) ethers_cache_is_loaded = true;
					}
			}

			if (reduced_lookup_queue.size > 0) {
					// 4. Network devices
					const devices = await softFailure(() => callLuciRpcGetNetworkDevices());
					if (devices) {
							for (const device of Object.values(devices)) {
									if (!device.mac) continue;
									const name = ethers_cache[device.mac]?.name;
									if (!name) continue;
									for (const item of [...(device.ipaddrs || []), ...(device.ip6addrs || [])])
											updateDnsCache(item.address, name);
							}
					}
			}

			// Final cleanup for unresolved addresses
			for (const address of reduced_lookup_queue)
					if ((recheck_lookup_queue[address] || 0) > 2)
							dns_cache[address] = address.includes(':') ? `[${address}]` : address;
					else
							recheck_lookup_queue[address] = (recheck_lookup_queue[address] || 0) + 1;

			const btn = document.querySelector('.btn.toggle-lookups');
			if (btn) {
					btn.firstChild.data = enableLookups ? _('Disable DNS lookups') : _('Enable DNS lookups');
					btn.classList.remove('spinning');
					btn.disabled = false;
			}
	},

	async pollData() {
		poll.add(L.bind(async function() {
			const datasets = await Promise.all(graphPolls.map(() => L.resolveDefault(callLuciRealtimeStats('conntrack'), [])));
			for (let gi = 0; gi < graphPolls.length; gi++) {
				const ctx = graphPolls[gi];
				const data = datasets[gi];
				const values = ctx.values;
				const lines = ctx.lines;
				const info = ctx.info;

				let data_scale = 0;
				let data_wanted = Math.floor(ctx.width / ctx.step);
				let last_timestamp = NaN;

				for (let i = 0, di = 0; di < lines.length; di++) {
					if (lines[di] == null)
						continue;

					const multiply = (lines[di].multiply != null) ? lines[di].multiply : 1;
					const offset = (lines[di].offset != null) ? lines[di].offset : 0;

					for (let j = ctx.timestamp ? 0 : 1; j < data.length; j++) {
						/* skip overlapping entries */
						if (data[j][0] <= ctx.timestamp)
							continue;

						if (i == 0) {
							ctx.fill++;
							last_timestamp = data[j][0];
						}

						info.line_current[i] = data[j][di + 1] * multiply;
						info.line_current[i] -= Math.min(info.line_current[i], offset);
						values[i].push(info.line_current[i]);
					}

					i++;
				}

				/* cut off outdated entries */
				ctx.fill = Math.min(ctx.fill, data_wanted);

				for (let i = 0; i < values.length; i++) {
					const len = values[i].length;
					values[i] = values[i].slice(len - data_wanted, len);

					/* find peaks, averages */
					info.line_peak[i] = NaN;
					info.line_average[i] = 0;

					for (let j = 0; j < values[i].length; j++) {
						info.line_peak[i] = isNaN(info.line_peak[i]) ? values[i][j] : Math.max(info.line_peak[i], values[i][j]);
						info.line_average[i] += values[i][j];
					}

					info.line_average[i] = info.line_average[i] / ctx.fill;
				}

				info.peak = Math.max.apply(Math, info.line_peak);

				/* remember current timestamp, calculate horizontal scale */
				if (!isNaN(last_timestamp))
					ctx.timestamp = last_timestamp;

				const size = Math.floor(Math.log2(info.peak));
				const div = Math.pow(2, size - (size % 10));
				let mult = info.peak / div;
				mult = (mult < 5) ? 2 : ((mult < 50) ? 10 : ((mult < 500) ? 100 : 1000));

				info.peak = info.peak + (mult * div) - (info.peak % (mult * div));

				data_scale = ctx.height / info.peak;

				/* plot data */
				for (let i = 0, di = 0; di < lines.length; di++) {
					if (lines[di] == null)
						continue;

					const el = ctx.svg.firstElementChild.getElementById(lines[di].line);
					let pt = '0,' + ctx.height;
					let y = 0;

					if (!el)
						continue;

					for (let j = 0; j < values[i].length; j++) {
						let x = j * ctx.step;

						y = ctx.height - Math.floor(values[i][j] * data_scale);
						//y -= Math.floor(y % (1 / data_scale));

						y = isNaN(y) ? ctx.height : y;

						pt += ' ' + x + ',' + y;
					}

					pt += ' ' + ctx.width + ',' + y + ' ' + ctx.width + ',' + ctx.height;

					el.setAttribute('points', pt);

					i++;
				}

				info.label_25 = 0.25 * info.peak;
				info.label_50 = 0.50 * info.peak;
				info.label_75 = 0.75 * info.peak;

				if (typeof(ctx.cb) == 'function')
					ctx.cb(ctx.svg, info);
			}
		}, this), pollInterval);
		poll.add(() => this.refreshConnections(), 10);
	},

	renderPage() {
		const page = conntrack.page(this.connectionRows || [], this.currentPage, 100);
		this.currentPage = page.current;
		this.connectionTable.update(page.rows, E('em', _('No information available')));
		const info = document.querySelector('#connections-page');
		if (info) info.textContent = page.total ? `${page.current * 100 + 1}–${Math.min((page.current + 1) * 100, page.total)} / ${page.total}` : '0 / 0';
		document.querySelector('#connections-previous').disabled = page.current === 0;
		document.querySelector('#connections-next').disabled = page.current + 1 >= page.pages;
		this.connectionTable.node.dataset.totalConnections = page.total;
		this.connectionTable.node.querySelectorAll('th').forEach((th, index) => {
			if (index === this.sortColumn) th.setAttribute('data-sort-direction', this.sortDescending ? 'desc' : 'asc');
			else th.removeAttribute('data-sort-direction');
		});
	},

	refreshConnections() {
		if (this.listRequest) return this.listRequest;
		const status = document.querySelector('#connections-status');
		const button = document.querySelector('#connections-refresh');
		if (button) button.disabled = true;
		this.listRequest = fs.read_direct('/proc/net/nf_conntrack').then(async raw => {
			this.connections = conntrack.parse(raw, this.protocols);
			await this.updateConntrack(this.connections);
			status.className = '';
			status.textContent = `${_('Connections')}: ${this.connections.length} · ${new Date().toLocaleTimeString()}`;
		}).catch(error => {
			status.className = 'alert-message warning';
			status.textContent = `${_('Error')}: ${error.message}`;
		}).finally(() => {
			this.listRequest = null;
			if (button) button.disabled = false;
		});
		return this.listRequest;
	},

	loadSVG(src) {
		return request.get(src).then(function(response) {
			if (!response.ok)
				throw new Error(response.statusText);

			return E('div', {
				'style': 'width:100%;height:300px;border:1px solid #000;background:#fff'
			}, E(response.text()));
		});
	},

	render([svg, protocols]) {
		this.protocols = conntrack.protocols(protocols);
		this.currentPage = 0;
		this.sortColumn = 4;
		this.sortDescending = true;
		this.connectionRows = [];

		const v = E('div', { 'class': 'cbi-map', 'id': 'map' }, [
			E('h2', _('Connections')),
			E('div', {'class': 'cbi-map-descr'}, _('This page displays the active connections via this device.')),
			E('div', { 'class': 'cbi-section' }, [
				svg,
				E('div', { 'class': 'right' }, E('small', { 'id': 'scale' }, '-')),
				E('br'),

				E('table', { 'class': 'table', 'style': 'width:100%;table-layout:fixed' }, [
					E('tr', { 'class': 'tr' }, [
						E('td', { 'class': 'td right top' }, E('strong', { 'style': 'border-bottom:2px solid blue' }, [ _('UDP:') ])),
						E('td', { 'class': 'td', 'id': 'lb_udp_cur' }, [ '0' ]),

						E('td', { 'class': 'td right top' }, E('strong', {}, [ _('Average:') ])),
						E('td', { 'class': 'td', 'id': 'lb_udp_avg' }, [ '0' ]),

						E('td', { 'class': 'td right top' }, E('strong', {}, [ _('Peak:') ])),
						E('td', { 'class': 'td', 'id': 'lb_udp_peak' }, [ '0' ])
					]),
					E('tr', { 'class': 'tr' }, [
						E('td', { 'class': 'td right top' }, E('strong', { 'style': 'border-bottom:2px solid green' }, [ _('TCP:') ])),
						E('td', { 'class': 'td', 'id': 'lb_tcp_cur' }, [ '0' ]),

						E('td', { 'class': 'td right top' }, E('strong', {}, [ _('Average:') ])),
						E('td', { 'class': 'td', 'id': 'lb_tcp_avg' }, [ '0' ]),

						E('td', { 'class': 'td right top' }, E('strong', {}, [ _('Peak:') ])),
						E('td', { 'class': 'td', 'id': 'lb_tcp_peak' }, [ '0' ])
					]),
					E('tr', { 'class': 'tr' }, [
						E('td', { 'class': 'td right top' }, E('strong', { 'style': 'border-bottom:2px solid red' }, [ _('Other:') ])),
						E('td', { 'class': 'td', 'id': 'lb_otr_cur' }, [ '0' ]),

						E('td', { 'class': 'td right top' }, E('strong', {}, [ _('Average:') ])),
						E('td', { 'class': 'td', 'id': 'lb_otr_avg' }, [ '0' ]),

						E('td', { 'class': 'td right top' }, E('strong', {}, [ _('Peak:') ])),
						E('td', { 'class': 'td', 'id': 'lb_otr_peak' }, [ '0' ])
					])
				]),

				E('br'),

				E('div', { 
					id: 'settings-row',
					style: 'display: flex',
				}, [
					E('span', { 
						class: 'filter',
						style: 'flex: auto',
					}, [
						E('input', {
							id: 'filter-connections',
							type: 'text',
							placeholder: '192.168.1.15 / UDP 1.15 / :443',
							class: 'cbi-input-text',
							style: 'width: 100%',
							keyup: (ev) => {
								filterText = ev.currentTarget.value;
								clearTimeout(this.filterTimer);
								this.filterTimer = setTimeout(() => {
									this.currentPage = 0;
									this.updateConntrack(this.connections || [], true);
								}, 120);
						    }
						})
					]),
					E('span', { 
						class: 'right',
						style: 'flex: auto',
					}, [
						E('button', {
							'class': 'btn cbi-button cbi-button-apply toggle-lookups',
							'click': function(ev) {
								if (!enableLookups) {
									ev.currentTarget.classList.add('spinning');
									ev.currentTarget.disabled = true;
									enableLookups = true;
								}
								else {
									ev.currentTarget.firstChild.data = _('Enable DNS lookups');
									enableLookups = false;
								}

								this.blur();
							}
						}, [ enableLookups ? _('Disable DNS lookups') : _('Enable DNS lookups') ])
					]),
				]),

				E('br'),

				E('div', { 'class': 'cbi-section-node' }, [
					E('table', { 'class': 'table', 'id': 'connections' }, [
						E('tr', { 'class': 'tr table-titles' }, [
							E('th', { 'class': 'th col-2 hide-xs' }, [ _('Network') ]),
							E('th', { 'class': 'th col-2' }, [ _('Protocol') ]),
							E('th', { 'class': 'th col-7' }, [ _('Source') ]),
							E('th', { 'class': 'th col-7' }, [ _('Destination') ]),
							E('th', { 'class': 'th col-4' }, [ _('Transfer') ])
						]),
						E('tr', { 'class': 'tr placeholder' }, [
							E('td', { 'class': 'td' }, [
								E('em', {}, [ _('Collecting data...') ])
							])
						])
					])
				])
			])
		]);

		this.updateGraph(svg, [ { line: 'udp' }, { line: 'tcp' }, { line: 'other' } ], function(svg, info) {
			const G = svg.firstElementChild, tab = svg.parentNode;

			G.getElementById('label_25').firstChild.data = '%d'.format(info.label_25);
			G.getElementById('label_50').firstChild.data = '%d'.format(info.label_50);
			G.getElementById('label_75').firstChild.data = '%d'.format(info.label_75);

			tab.querySelector('#scale').firstChild.data = _('(%d minute window, %d second interval)').format(info.timeframe, info.interval);

			tab.querySelector('#lb_udp_cur').firstChild.data = '%d'.format(info.line_current[0]);
			tab.querySelector('#lb_udp_avg').firstChild.data = '%d'.format(info.line_average[0]);
			tab.querySelector('#lb_udp_peak').firstChild.data = '%d'.format(info.line_peak[0]);

			tab.querySelector('#lb_tcp_cur').firstChild.data = '%d'.format(info.line_current[1]);
			tab.querySelector('#lb_tcp_avg').firstChild.data = '%d'.format(info.line_average[1]);
			tab.querySelector('#lb_tcp_peak').firstChild.data = '%d'.format(info.line_peak[1]);

			tab.querySelector('#lb_otr_cur').firstChild.data = '%d'.format(info.line_current[2]);
			tab.querySelector('#lb_otr_avg').firstChild.data = '%d'.format(info.line_average[2]);
			tab.querySelector('#lb_otr_peak').firstChild.data = '%d'.format(info.line_peak[2]);
		});

		this.connectionTable = new ui.Table(v.querySelector('#connections'));
		// Sorting belongs to the entire snapshot, not the visible page.
		this.connectionTable.getActiveSortState = () => null;
		this.connectionTable.node.querySelectorAll('th').forEach((th, index) => {
			th.addEventListener('click', event => {
				event.stopImmediatePropagation();
				this.sortDescending = index === this.sortColumn ? !this.sortDescending : false;
				this.sortColumn = index;
				this.currentPage = 0;
				this.updateConntrack(this.connections || [], true);
			}, true);
		});
		v.querySelector('#connections').before(E('div', { 'class': 'cbi-section', 'id': 'connections-controls' }, [
			E('button', { id: 'connections-previous', class: 'btn cbi-button', disabled: true, click: () => { this.currentPage--; this.renderPage(); } }, _('Previous')),
			E('span', { id: 'connections-page', style: 'margin:0 1em', 'aria-live': 'polite' }, '0 / 0'),
			E('button', { id: 'connections-next', class: 'btn cbi-button', disabled: true, click: () => { this.currentPage++; this.renderPage(); } }, _('Next')),
			E('button', { id: 'connections-refresh', class: 'btn cbi-button', style: 'margin-left:1em', click: () => this.refreshConnections() }, _('Refresh')),
			E('div', { id: 'connections-status', role: 'status' }, _('Collecting data...'))
		]));
		this.pollData();

		return v;
	},

	handleSaveApply: null,
	handleSave: null,
	handleReset: null
});

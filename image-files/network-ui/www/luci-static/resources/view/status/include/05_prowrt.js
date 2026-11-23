'use strict';
'require baseclass';
'require fs';

return baseclass.extend({
	title: 'ProWrt',
	load: function() {
		return fs.read_direct('/rom/usr/share/prowrt/build.json').catch(function() {
			return fs.read_direct('/usr/share/prowrt/build.json');
		}).then(function(text) {
			try {
				var data = JSON.parse(text);
				return data && typeof data === 'object' && !Array.isArray(data) ? data : {};
			} catch (e) { return {}; }
		}).catch(function() { return {}; });
	},
	render: function(data) {
		var fields = [
			[ 'ProWrt', data.version || _('unknown version') ],
			[ _('Source revision'), (data.source_revision || '?') + (data.source_dirty ? ' (dirty)' : '') ],
			[ _('Source time'), data.source_time || '?' ],
			[ _('Build target'), data.target || '?' ],
			[ _('Build origin'), data.build_origin === 'github-actions'
				? 'GitHub Actions / ' + data.ci_run_id + ' / ' + data.ci_run_attempt
				: (data.build_origin || '?') ]
		];
		return E('table', { 'class': 'table' }, fields.map(function(field) {
			return E('tr', { 'class': 'tr' }, [
				E('td', { 'class': 'td left', 'width': '33%' }, [ field[0] ]),
				E('td', { 'class': 'td left' }, [ field[1] ])
			]);
		}));
	}
});

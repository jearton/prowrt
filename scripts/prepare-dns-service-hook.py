#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add one optional packaging callback; do not modify DNS server programs."""
import argparse
from pathlib import Path
import re


def install(package, service):
    init = package / 'files' / (service + '.init')
    marker = '# OpenClash optional DNS linkage startup callback'
    source = init.read_text()
    if marker in source:
        return
    if re.search(r'^service_started\s*\(', source, re.M):
        raise ValueError('Review the existing service_started hook before integrating DNS linkage')
    source += f'''
{marker}
service_started() {{
    if [ -f /usr/share/openclash/dns_link.rb ] && command -v ruby >/dev/null 2>&1; then
        # One bounded task after startup, no new daemon or periodic timer.
        ruby /usr/share/openclash/dns_link.rb primary-start {service} >/dev/null 2>&1 &
    fi
}}
'''
    recipe = package / 'Makefile'
    content = recipe.read_text()
    expected = '2' if service == 'technitium' else '1'
    if not re.search(r'^PKG_RELEASE:=' + expected + '$', content, re.M):
        raise ValueError('Review the upstream package revision before applying the lifecycle hook')
    init.write_text(source)
    recipe.write_text(re.sub(r'^PKG_RELEASE:=' + expected + '$', 'PKG_RELEASE:=' + str(int(expected) + 1), content, flags=re.M))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('service', choices=('technitium', 'adguardhome'))
    parser.add_argument('package', type=Path)
    args = parser.parse_args()
    install(args.package, args.service)

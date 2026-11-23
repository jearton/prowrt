#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Owned loopback-only Mihomo fixture with real persistent proxy connections."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import urllib.request


async def serve(args):
    args.directory.mkdir(parents=True, exist_ok=True)
    ui = args.root / 'usr/share/openclash/ui'
    alias = ui / 'zashboard-upgrade'
    if alias.exists() or alias.is_symlink():
        raise ValueError('Upgrade fixture path already exists')
    alias.symlink_to('zashboard-legacy', target_is_directory=True)
    state = args.directory / 'mihomo-state'
    state.mkdir()
    config = args.directory / 'config.yaml'
    config.write_text(f'''mixed-port: 17890
external-controller: 127.0.0.1:19090
external-ui: {json.dumps(str(ui.resolve()))}
allow-lan: true
bind-address: 127.0.0.1
mode: rule
log-level: silent
ipv6: false
profile:
  store-selected: false
dns:
  enable: false
proxies: []
proxy-groups:
  - name: QA
    type: select
    proxies: [DIRECT, REJECT]
rules:
  - MATCH,DIRECT
''')
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)
    connections = []

    async def target(reader, writer):
        try:
            await reader.read()
        except ConnectionError:
            pass
        finally:
            writer.close()

    async def control(reader, writer):
        try:
            request = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 5)
            if request.startswith(b'POST /upgrade HTTP/'):
                alias.unlink()
                alias.symlink_to('zashboard', target_is_directory=True)
                response = b'{"upgraded":true}'
                status = b'200 OK'
            else:
                response = b'{"error":"unsupported fixture operation"}'
                status = b'404 Not Found'
            writer.write(b'HTTP/1.1 ' + status + b'\r\nContent-Type: application/json\r\nContent-Length: ' +
                         str(len(response)).encode() + b'\r\nConnection: close\r\n\r\n' + response)
            await writer.drain()
        finally:
            writer.close()

    target_server = await asyncio.start_server(target, '127.0.0.1', 18080)
    control_server = await asyncio.start_server(control, '127.0.0.1', 19091)
    log = (args.directory / 'mihomo.log').open('wb')
    process = subprocess.Popen([str(args.core.resolve()), '-d', str(state), '-f', str(config)],
                               stdout=log, stderr=subprocess.STDOUT,
                               env={**os.environ, 'SAFE_PATHS': str(ui.resolve())})
    try:
        async def api(endpoint):
            def fetch():
                with urllib.request.urlopen('http://127.0.0.1:19090/' + endpoint, timeout=5) as response:
                    return json.load(response)
            return await loop.run_in_executor(None, fetch)

        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Fixture core exited; see private test log')
            try:
                version = await api('version')
                break
            except Exception:
                await asyncio.sleep(.2)
        else:
            raise RuntimeError('Fixture core did not become ready')

        # The controller can start before inbound listeners are ready.
        for _ in range(100):
            try:
                reader, writer = await asyncio.open_connection('127.0.0.1', 17890)
                writer.close()
                await writer.wait_closed()
                break
            except ConnectionRefusedError:
                await asyncio.sleep(.1)
        else:
            raise RuntimeError('The IPv4 loopback proxy listener did not become ready')

        semaphore = asyncio.Semaphore(80)

        async def connect():
            async with semaphore:
                reader, writer = await asyncio.open_connection('127.0.0.1', 17890)
                writer.write(b'CONNECT 127.0.0.1:18080 HTTP/1.1\r\nHost: 127.0.0.1:18080\r\n\r\n')
                await writer.drain()
                header = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 15)
                if b' 200 ' not in header.split(b'\r\n', 1)[0]:
                    writer.close()
                    raise RuntimeError('The fixture proxy rejected a local connection')
                connections.append((reader, writer))

        await asyncio.gather(*(connect() for _ in range(args.connections)))
        # The HTTP CONNECT acknowledgement can precede API registration.
        for _ in range(100):
            actual = await api('connections')
            if len(actual['connections']) == args.connections:
                break
            await asyncio.sleep(.1)
        else:
            raise RuntimeError(f"Expected {args.connections} live connections, got {len(actual['connections'])}")
        report = {'core': version, 'connections': len(actual['connections']),
                  'listen': ['127.0.0.1:17890', '127.0.0.1:18080', '127.0.0.1:19090', '127.0.0.1:19091']}
        (args.directory / 'ready.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report), flush=True)
        try:
            await asyncio.wait_for(stopped.wait(), timeout=600)
        except asyncio.TimeoutError:
            print('Owned fixture reached its ten-minute cleanup deadline', flush=True)
    finally:
        for _, writer in connections:
            writer.close()
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        target_server.close()
        control_server.close()
        await target_server.wait_closed()
        await control_server.wait_closed()
        alias.unlink(missing_ok=True)
        log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--connections', type=int, default=2250)
    asyncio.run(serve(parser.parse_args()))

#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# On-demand capture only. Never restarts a service or changes UCI/firewall.
set -u
umask 077
out=${1:-/tmp/uhttpd-evidence-$(date +%Y%m%d-%H%M%S)}
if [ -e "$out" ]; then
    echo 'Refusing to overwrite an existing evidence directory' >&2
    exit 2
fi
mkdir -m 700 "$out" || exit 1
snapshot() {
    date -u
    uptime
    cat /proc/meminfo
    for name in uhttpd rpcd ubusd; do
        for pid in $(pidof "$name" 2>/dev/null); do
            echo "PROCESS $name $pid"
            cat "/proc/$pid/status" "/proc/$pid/wchan" "/proc/$pid/syscall" 2>/dev/null
            ls -l "/proc/$pid/fd" 2>/dev/null
        done
    done
    for file in tcp tcp6 unix netlink; do
        echo "SOCKETS $file"
        cat "/proc/net/$file" 2>/dev/null
    done
}
snapshot > "$out/before.txt" 2>&1
# ACL permission lookup is read-only; do not create/login/destroy any session.
ubus -t 2 call session access '{"ubus_rpc_session":"00000000000000000000000000000000","object":"system","function":"board"}' > "$out/acl-probe.txt" 2>&1
printf 'exit=%s\n' "$?" >> "$out/acl-probe.txt"
if command -v curl >/dev/null 2>&1; then
    curl --noproxy '*' -sS --max-time 2 -o /dev/null -w 'http=%{http_code} seconds=%{time_total}\n' http://127.0.0.1/luci-static/resources/luci.js > "$out/static-probe.txt" 2>&1
    printf 'exit=%s\n' "$?" >> "$out/static-probe.txt"
fi
pid=$(pidof uhttpd 2>/dev/null | awk '{print $1}')
if [ -n "$pid" ] && command -v strace >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then
    # String length zero avoids capturing cookies, credentials and RPC payloads.
    timeout 8 strace -tt -T -s 0 -e trace=poll,ppoll,epoll_wait,epoll_pwait,epoll_ctl,accept,accept4,read,write,recvmsg,sendmsg -p "$pid" -o "$out/syscalls.txt" 2> "$out/strace-status.txt"
else
    echo 'strace/timeout unavailable or uhttpd not found; /proc evidence retained' > "$out/strace-status.txt"
fi
snapshot > "$out/after.txt" 2>&1
printf '%s\n' "$out"

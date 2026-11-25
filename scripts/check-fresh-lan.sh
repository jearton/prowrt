#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

# Keep the VM and its test client in their own network namespace. The TAP
# has no physical member, WAN, default route or route to the runner's LAN.
if [[ -z ${OPENWRT_CI_NETNS:-} ]]; then
    namespace="openwrt-ci-$$"
    sudo ip netns add "$namespace"
    trap 'sudo ip netns delete "$namespace"' EXIT
    sudo ip netns exec "$namespace" env OPENWRT_CI_NETNS="$namespace" \
        FRESH_LAN_FIXTURE_APKS="${FRESH_LAN_FIXTURE_APKS:-}" \
        FRESH_LAN_FIXTURE_TTYD_INIT="${FRESH_LAN_FIXTURE_TTYD_INIT:-}" \
        PROWRT_FIRMWARE_SOURCE="${PROWRT_FIRMWARE_SOURCE:-}" bash "$0" "$@"
    exit 0
fi
[[ $(ip netns identify $$) = "$OPENWRT_CI_NETNS" ]]
sysctl -q -w net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1
ip link set lo up
ip tuntap add dev lan-test mode tap
ip addr add 192.168.1.2/24 dev lan-test
ip link set lan-test up
[[ -z $(ip -4 route show default) ]]

test_dir=$(mktemp -d)
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
vm_pid=
cleanup() {
    status=$?
    if [[ $status != 0 && -n $vm_pid ]]; then
        if [[ -f "$test_dir/key" ]]; then
            python3 "$repo/scripts/lan-vm.py" diagnose "$test_dir" || true
        fi
        for endpoint in 80/cgi-bin/luci/ 7681/cgi-bin/luci/terminal-session/ 19999/v3/ 19999/api/v1/charts 5380/; do
            code=$(curl -ksS --noproxy '*' --connect-timeout 1 --max-time 2 -o /dev/null -w '%{http_code}' "http://192.168.1.1:$endpoint" 2>/dev/null || true)
            printf 'Guest endpoint %s returned HTTP %s\n' "$endpoint" "$code"
        done
        dig @192.168.1.1 openwrt.lan A +short +time=1 +tries=1 || true
        dig @192.168.1.1 openwrt.lan A +short +tcp +time=2 +tries=1 || true
        tcpdump -nn -r "$test_dir/lan.pcap" 'udp port 53 or tcp port 53' 2>/dev/null | tail -n 15 || true
    fi
    if [[ -n $vm_pid ]]; then
        kill "$vm_pid" 2>/dev/null || :
        wait "$vm_pid" 2>/dev/null || :
    fi
    if [[ $status != 0 && -f "$test_dir/serial.log" ]]; then
        tail -n 80 "$test_dir/serial.log"
    fi
    find "$test_dir" -type f -delete
    rm -f "$test_dir/serial.sock"
    rmdir "$test_dir"
}
trap cleanup EXIT

gzip -dc "$1" > "$test_dir/disk.img"
cp /usr/share/OVMF/OVMF_VARS_4M.fd "$test_dir/vars.fd"
lan=tap,id=lan,ifname=lan-test,script=no,downscript=no
qemu-system-x86_64 -machine q35 -accel kvm -accel tcg -smp 2 -m 1024 \
    -display none -monitor none \
    -chardev "socket,id=serial0,path=$test_dir/serial.sock,server=on,wait=off,logfile=$test_dir/serial.log" \
    -serial chardev:serial0 \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
    -drive "if=pflash,format=raw,file=$test_dir/vars.fd" \
    -drive "if=ide,format=raw,file=$test_dir/disk.img" \
    -netdev "$lan" -device e1000,netdev=lan \
    -object "filter-dump,id=lan-capture,netdev=lan,file=$test_dir/lan.pcap" &
vm_pid=$!
python3 "$repo/scripts/lan-vm.py" bootstrap "$test_dir"
if [[ -n ${FRESH_LAN_FIXTURE_APKS:-} ]]; then
    python3 "$repo/scripts/lan-vm.py" fixture "$test_dir" "$FRESH_LAN_FIXTURE_APKS" "$FRESH_LAN_FIXTURE_TTYD_INIT"
fi
python3 "$repo/scripts/lan-vm.py" check-ipv4 "$test_dir"
if [[ -f $repo/VERSION && -z ${FRESH_LAN_FIXTURE_APKS:-} ]]; then
    python3 "$repo/scripts/lan-vm.py" build-identity "$test_dir"
fi

fetch() {
    curl -fsSL --noproxy '*' --connect-timeout 2 --max-time 5 \
        "http://192.168.1.1:$1" -o "$2"
}

deadline=$((SECONDS + 300))
luci_http=http://192.168.1.1
terminal_path=/cgi-bin/luci/terminal-session/
terminal_http="http://192.168.1.1:7681$terminal_path"
status() {
    curl -ksS --noproxy '*' --connect-timeout 2 --max-time 5 -o /dev/null -w '%{http_code}' "$@"
}

until [[ $(status "$luci_http/cgi-bin/luci/" 2>/dev/null) = 403 ]] &&
    [[ $(status "$terminal_http" 2>/dev/null) = 403 ]] &&
    fetch 19999/v3/ "$test_dir/netdata.html" 2>/dev/null &&
    fetch 19999/api/v1/charts "$test_dir/charts.json" 2>/dev/null &&
    jq -e '.charts["system.cpu"] != null' "$test_dir/charts.json" >/dev/null &&
    fetch 5380/ "$test_dir/technitium.html" 2>/dev/null &&
    grep -q 'id="root"' "$test_dir/technitium.html" &&
    [[ $(dig @192.168.1.1 openwrt.lan A +short +time=1 +tries=1) = 192.168.1.1 ]]; do
    kill -0 "$vm_pid"
    if (( SECONDS >= deadline )); then
        echo 'Fresh LAN boot did not serve LuCI, ttyd, Netdata and native DNS' >&2
        exit 1
    fi
    sleep 3
done

python3 "$repo/scripts/lan-vm.py" dns-defaults "$test_dir"
if [[ -f $repo/fastnet.lock.json && -z ${FRESH_LAN_FIXTURE_APKS:-} ]]; then
    python3 "$repo/scripts/lan-vm.py" fastnet-defaults "$test_dir"
fi

login() {
    local -a password_args=(--data-urlencode "luci_password@$test_dir/root-password")
    # curl omits a name@file parameter when the file is empty.
    if [[ ! -s "$test_dir/root-password" ]]; then
        password_args=(--data-urlencode 'luci_password=')
    fi
    curl -ksS --noproxy '*' --connect-timeout 2 --max-time 5 \
        --cookie-jar "$2" --data-urlencode luci_username=root \
        "${password_args[@]}" "$1/cgi-bin/luci/" -o /dev/null
}

: > "$test_dir/root-password"
chmod 600 "$test_dir/root-password"
login "$luci_http" "$test_dir/http.cookies"
python3 "$repo/scripts/check-ttyd-login.py" "$test_dir/http.cookies" "$test_dir/root-password" empty
python3 "$repo/scripts/lan-vm.py" terminal-password "$test_dir"
login "$luci_http" "$test_dir/http.cookies"
if [[ -f $repo/VERSION && -z ${FRESH_LAN_FIXTURE_APKS:-} ]]; then
    session=$(awk '$6 == "sysauth_http" { print $7 }' "$test_dir/http.cookies")
    test -n "$session"
    curl -fsS --noproxy '*' --connect-timeout 2 --max-time 5 \
        --data-urlencode "sessionid=$session" --data-urlencode path=/rom/usr/share/prowrt/build.json \
        "$luci_http/cgi-bin/cgi-download" -o "$test_dir/luci-build.json"
    python3 "$repo/scripts/build-metadata.py" verify "$test_dir/luci-build.json" \
        --repo "${PROWRT_FIRMWARE_SOURCE:-$repo}"
    fetch 80/luci-static/resources/view/status/include/05_prowrt.js "$test_dir/prowrt-status.js"
    grep -q '/rom/usr/share/prowrt/build.json' "$test_dir/prowrt-status.js"
fi
curl -kfsS --noproxy '*' -b "$test_dir/http.cookies"     "$luci_http/cgi-bin/luci/admin/services/technitium" -o "$test_dir/technitium-luci.html"
grep -Eq 'technitium[./]status' "$test_dir/technitium-luci.html"
[[ $(dig @192.168.1.1 openwrt.lan A +short +tcp +time=2 +tries=1) = 192.168.1.1 ]]
[[ $(dig @192.168.1.1 -x 192.168.1.1 +short +time=2 +tries=1) = openwrt.lan. ]]
login https://192.168.1.1 "$test_dir/https.cookies"
# The old-image fixture cannot replace ttyd's binary. Check ALPN on exact builds.
if [[ -z ${FRESH_LAN_FIXTURE_APKS:-} ]]; then
    timeout 8 openssl s_client -connect 192.168.1.1:7681 -alpn h2,http/1.1 \
        </dev/null > "$test_dir/ttyd-alpn.txt" 2>&1
    grep -q 'ALPN protocol: http/1.1' "$test_dir/ttyd-alpn.txt"
fi
for scheme in http https; do
    cookie="$(awk -v name="sysauth_$scheme" '$6 == name { print $6 "=" $7 }' "$test_dir/$scheme.cookies")"
    test -n "$cookie"
    curl -kfsS --noproxy '*' -b "$cookie" "$scheme://192.168.1.1:7681$terminal_path" \
        -o "$test_dir/terminal.html"
    grep -qi ttyd "$test_dir/terminal.html"
done
[[ $(status -b "$cookie" "$terminal_http") = 403 ]]

python3 "$repo/scripts/check-ttyd-login.py" "$test_dir/http.cookies" "$test_dir/root-password" password
python3 "$repo/scripts/lan-vm.py" forced-dns "$test_dir"
if [[ -f $repo/VERSION && -z ${FRESH_LAN_FIXTURE_APKS:-} ]]; then
    python3 "$repo/scripts/check-openclash-live.py" "$test_dir"
fi
echo 'Fresh isolated IPv4 boot verified LuCI, Netdata, authorized ttyd, and the Technitium console and DNS on UDP/TCP'

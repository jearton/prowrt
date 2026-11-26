#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
umask 022

repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
if [[ $# != 2 || -e $1 || -e $2 ]]; then
    echo "Usage: $0 NEW_OPENWRT_DIRECTORY NEW_FIRMWARE_DIRECTORY" >&2
    exit 2
fi
tree="$(realpath -m -- "$1")"
out="$(realpath -m -- "$2")"
recipes="$repo/sources/full/package/custom"
patches="$repo/patches/custom-ipv4"
ui="$repo/packages/istoreos-ui-2026110611"
metrics="${OPENWRT_METRICS_DIR:-${out}.metrics}"
stage=source-and-feeds
stage_started=$SECONDS
python3 "$repo/scripts/build-metrics.py" "$metrics"
stage_end() {
    python3 "$repo/scripts/build-metrics.py" "$metrics" "$stage" "$((SECONDS - stage_started))"
}
stage_start() {
    stage_end
    stage=$1
    stage_started=$SECONDS
}
finish() {
    result=$?
    trap - EXIT
    if [[ -n $stage ]]; then
        state=success
        [[ $result == 0 ]] || state=failure
        python3 "$repo/scripts/build-metrics.py" "$metrics" "$stage" "$((SECONDS - stage_started))" --status "$state" || true
    fi
    if [[ -x $tree/staging_dir/host/bin/ccache ]]; then
        "$tree/staging_dir/host/bin/ccache" --show-log-stats > "$metrics/ccache.txt" 2>&1 || true
    fi
    exit "$result"
}
trap finish EXIT
export CCACHE_COMPILERCHECK=content
export CCACHE_MAXSIZE=2G
export CCACHE_STATSLOG="$metrics/ccache-stats.log"

readarray -t source < <(python3 - "$repo/sources.lock.json" <<'PY'
import json, sys
lock = json.load(open(sys.argv[1]))
for key in ("url", "ref", "commit"):
    print(lock["source"][key])
PY
)
git clone --depth 1 --branch "${source[1]}" "${source[0]}" "$tree"
cd "$tree"
test "$(git rev-parse HEAD)" = "${source[2]}"
python3 - "$repo/sources.lock.json" > feeds.conf <<'PY'
import json, sys
for feed in json.load(open(sys.argv[1]))["feeds"]:
    print(f'src-git {feed["name"]} {feed["url"]}^{feed["commit"]}')
PY
./scripts/feeds update -a
./scripts/feeds install -a
stage_start custom-packages-and-overlay
if [[ -n ${OPENWRT_CACHE_ROOT:-} ]]; then
    python3 "$repo/scripts/build-cache.py" prepare "$OPENWRT_CACHE_ROOT" "$tree" "$out"
fi

for package in "$recipes"/* netdata quickstart luci-app-quickstart luci-i18n-quickstart-zh-cn luci-app-weechat; do
    name=$(basename "$package")
    if find package/feeds -type l -name "$name" -print -quit | grep -q .; then
        ./scripts/feeds uninstall "$name"
    fi
done
# The custom recipe directory is named tailscale-core but provides tailscale.
if find package/feeds -type l -name tailscale -print -quit | grep -q .; then
    ./scripts/feeds uninstall tailscale
fi
mkdir -p package/custom files
cp -a "$recipes/." "$repo/packages/netdata" package/custom/
cp "$repo/sources/full/package/fastnet-meta.mk" package/fastnet-meta.mk
python3 "$repo/scripts/prepare-openclash.py" package/custom/luci-app-openclash
"$repo/scripts/prepare-technitium-luci.sh" package/custom
python3 "$repo/scripts/prepare-dns-service-hook.py" adguardhome feeds/packages/net/adguardhome
python3 "$repo/scripts/prepare-uhttpd.py" package/network/services/uhttpd
python3 "$repo/scripts/prepare-nlbwmon.py" feeds/packages/net/nlbwmon feeds/luci/applications/luci-app-nlbwmon
cp -a "$repo/sources/full/files/." files/
cp -a "$repo/image-files/network-ui/usr" "$repo/image-files/network-ui/www" files/
python3 "$repo/scripts/build-metadata.py" generate files/usr/share/prowrt/build.json

mkdir -p .ui-inputs
python3 - "$ui" "$tree" "$repo/scripts/build-cache.py" "${OPENWRT_CACHE_ROOT:-}" <<'PY'
import hashlib, json, pathlib, subprocess, sys, tempfile
ui = pathlib.Path(sys.argv[1])
tree = pathlib.Path(sys.argv[2])
meta = json.loads((ui / "ui-source.json").read_text())
base = "https://dl.istoreos.com/iStoreOS/x86_64_efi/"
with tempfile.TemporaryDirectory(dir=tree / ".ui-inputs") as path:
    source = pathlib.Path(path)
    cache = pathlib.Path(sys.argv[4]) / "assets" if sys.argv[4] else source / "cache"
    gz = pathlib.Path(subprocess.check_output([
        sys.executable, sys.argv[3], "fetch", base + meta["image"], meta["sha256"], str(cache),
    ], text=True).strip())
    (source / "image.gz").symlink_to(gz.resolve())
    with gz.open("rb") as artifact:
        if hashlib.file_digest(artifact, "sha256").hexdigest() != meta["sha256"]:
            raise SystemExit("Unexpected iStoreOS archive SHA-256")
    with (source / "image.raw").open("wb") as image:
        subprocess.run(["gzip", "-dc", str(gz)], stdout=image, check=True)
    subprocess.run([
        sys.executable, str(ui / "prepare-payload.py"), str(source),
        str(tree / ".ui-inputs/recipes"), "/usr/bin/unsquashfs",
        "quickstart", "luci-app-quickstart", "luci-i18n-quickstart-zh-cn",
    ], check=True)
PY
for name in quickstart luci-app-quickstart luci-i18n-quickstart-zh-cn; do
    cp -a ".ui-inputs/recipes/$name" package/custom/
done
sed -i 's/^PKG_RELEASE:=1$/PKG_RELEASE:=2/' package/custom/quickstart/Makefile
printf "\tlist module 'remoteDomain'\n" >> package/custom/quickstart/payload/etc/config/quickstart
python3 "$repo/scripts/prepare-quickstart-devices.py" package/custom/luci-app-quickstart

for name in netdata-config-readable netdata-container-network netdata-overview netdata-luci-bundled-dashboard; do
    git apply "$patches/$name.patch"
done
for name in luci-nftables-legacy-warning luci-filemanager-layout; do
    git -C feeds/luci apply "$patches/$name.patch"
done
git -C feeds/packages apply "$patches/golang-1.27.4.patch" "$patches/ttyd-luci-session.patch"
release=26.288.56989~75a306d
python3 "$repo/scripts/prepare-luci-connections.py" feeds/luci
python3 "$repo/scripts/prepare-prowrt-processes.py" feeds/luci
for module in applications/luci-app-filemanager; do
    sed -i "s|^include ../../luci.mk|PKG_VERSION:=$release\\nPKG_RELEASE:=1\\n\\ninclude ../../luci.mk|" "feeds/luci/$module/Makefile"
done
lmo_src=feeds/luci/modules/luci-base/src
make -C "$lmo_src" po2lmo
mkdir -p files/usr/lib/lua/luci/i18n
"$lmo_src/po2lmo" "$repo/image-files/network-ui/office-menus.zh-cn.po" files/usr/lib/lua/luci/i18n/office-menus.zh-cn.lmo
# This overlay contains only public, version-controlled defaults and UI files.
# A cache or archive created with umask 077 must not make / or /usr private.
find files -type f -name '._*' -delete
find files -type d -exec chmod 0755 {} +
find files -type f -perm -u=x -exec chmod 0755 {} +
find files -type f ! -perm -u=x -exec chmod 0644 {} +
stage_start configuration
# feeds uninstall refreshes an existing .config. Write the authoritative profile
# only after all custom recipes have been installed, then apply cache paths.
cp "$repo/profiles/network-ui.config" .config
if [[ -n ${OPENWRT_CACHE_ROOT:-} ]]; then
    python3 "$repo/scripts/build-cache.py" configure .config "$OPENWRT_CACHE_ROOT" "$tree" "$out"
fi
make defconfig
grep -Fx CONFIG_USE_APK=y .config
grep -Fx 'CONFIG_GRUB_BOOTOPTS="ipv6.disable=1"' .config
grep -Fx '# CONFIG_PACKAGE_dnsmasq_full_dhcpv6 is not set' .config
grep -Fx CONFIG_PACKAGE_luci-i18n-argon-config-zh-cn=y .config
grep -Fx CONFIG_PACKAGE_kmod-bonding=y .config
grep -Fx CONFIG_PACKAGE_px5g-mbedtls=y .config
grep -Fx CONFIG_PACKAGE_openssl-util=y .config
for package in fastnet luci-app-fastnet app-meta-fastnet prowrt-snmp-discovery snmp-utils-ssl technitium luci-app-technitium luci-i18n-technitium-zh-cn adguardhome luci-app-adguardhome; do
    grep -Fx "CONFIG_PACKAGE_${package}=y" .config
done
if grep -E '^CONFIG_PACKAGE_(docker|dockerd|docker-compose|containerd|runc|tini|luci-app-dockerman|luci-i18n-dockerman-[^=]*)=y$' .config; then
    echo 'A Docker package remains enabled' >&2
    exit 1
fi
if [[ ${OPENWRT_PREPARE_ONLY:-0} == 1 ]]; then
    echo 'Source, custom recipes, cache configuration and required package selections verified; no firmware compiled'
    exit 0
fi
jobs="${OPENWRT_JOBS:-$(nproc)}"
export GOPROXY='https://proxy.golang.org|direct'
stage_start downloads
make -j"$jobs" download
stage_start compilation
make -j"$jobs" V=s 2>&1 | tee build.log | awk '/^time:|[Ee][Rr][Rr][Oo][Rr]:|fatal error:|undefined reference|\*\*\*/ { print; fflush() }' ||
    { tail -n 180 build.log; exit 1; }
stage_start verification-and-export
target=bin/targets/x86/64
image=openwrt-x86-64-generic-squashfs-combined-efi.img.gz
manifest=openwrt-x86-64-generic.manifest
gzip -t "$target/$image"
rootfs=build_dir/target-x86_64_musl/linux-x86_64/root.squashfs
unsquash=staging_dir/host/bin/unsquashfs4
python3 "$repo/scripts/check-rootfs-permissions.py" "$unsquash" "$rootfs"
"$unsquash" -cat "$rootfs" usr/share/prowrt/build.json > .ui-inputs/build.json
cmp files/usr/share/prowrt/build.json .ui-inputs/build.json
python3 "$repo/scripts/build-metadata.py" verify .ui-inputs/build.json
"$unsquash" -cat "$rootfs" lib/apk/db/installed > .ui-inputs/installed
python3 - "$repo/manifests/$manifest" "$target/$manifest" .ui-inputs/installed <<'PY'
import re
import sys
def versions(path):
    with open(path) as stream:
        return dict(line.strip().split(" - ", 1) for line in stream)
old, new = map(versions, sys.argv[1:3])
old["kmod-bonding"] = old["kmod-macvlan"]
old["ttyd"] = "1.7.7-r6"
for name in ("uhttpd", "uhttpd-mod-ubus"):
    old[name] = "2026.08.24~373145f7-r2"
old["netdata"] = "2.13.0-r5"
old["luci-app-netdata"] = "0.1-r3"
old["luci-i18n-netdata-zh-cn"] = "0.1"
old["px5g-mbedtls"] = "11"
old["openssl-util"] = "3.5.9-r1"
old["libopenssl-conf"] = "3.5.9-r1"
old["luci-app-openclash"] = "0.48.002-r3"
for name in ("luci-base", "luci-mod-status"):
    old[name] = "26.288.56989~75a306d-r2"
for name in ("ruby-json", "ruby-ostruct", "ruby-set", "ruby-tsort"):
    old[name] = old["ruby"]
old["adguardhome"] = "0.107.79-r2"
old["nlbwmon"] = "2025.06.02~29236be6-r3"
old["luci-app-nlbwmon"] = "26.288.56989~75a306d-r3"
old["luci-app-quickstart"] = "0.12.10-r3"
old.update({"fastnet": "0.8.10-r4", "luci-app-fastnet": "0.8.10-r1",
            "luci-i18n-fastnet-zh-cn": "0", "app-meta-fastnet": "0.8.10-r23",
            "linkease-app-entry": "3.0.24-r1", "luci-lib-linkeaseauth": "1.2.1-r5",
            "prowrt-snmp-discovery": "1.0.0-r1", "snmp-utils-ssl": "5.9.4-r6",
            "libnetsnmp-ssl": "5.9.4-r6", "libpci": "3.14.0-r2"})
for name in ("docker", "dockerd", "docker-compose", "containerd", "runc", "tini",
             "luci-app-dockerman", "luci-i18n-dockerman-zh-cn"):
    old.pop(name, None)
    if name in new:
        raise SystemExit(f"Unexpected Docker package: {name}")
for name, version in {"technitium": "15.6.2-r3", "luci-app-technitium": "1.1.0-r1",
                      "luci-i18n-technitium-zh-cn": "1.0.0-r1"}.items():
    if name == "luci-i18n-technitium-zh-cn" and new.get(name):
        # LuCI gives translation packages their own source-derived version.
        version = new[name]
    old[name] = version
kernel_release = r"(\d+\.\d+\.\d+)~[a-f0-9]{32}(-r\d+)"
old_kernel, new_kernel = (re.fullmatch(kernel_release, packages["kernel"]) for packages in (old, new))
if not old_kernel or not new_kernel or old_kernel.groups() != new_kernel.groups():
    raise SystemExit(f"Unexpected kernel release: {new['kernel']}")
old["kernel"] = new["kernel"]
with open(sys.argv[3]) as apk_db:
    records = [dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
               for block in apk_db.read().split("\n\n")]
installed = {record["P"]: record for record in records if "P" in record}
for name in new:
    if name.startswith("kmod-") and f"kernel={new['kernel']}" not in installed[name].get("D", "").split():
        raise SystemExit(f"{name} does not match the packaged kernel ABI")
delta = {k: (old.get(k), new.get(k)) for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
if delta:
    raise SystemExit(f"Package manifest drift: {delta}")
print(f"Verified all {len(new)} package versions")
PY
mkdir -p "$out"
cp "$target/$image" "$target/$manifest" "$out/"
cp .ui-inputs/build.json "$out/build.json"
(cd "$out" && sha256sum -- "$image" "$manifest" build.json > SHA256SUMS)

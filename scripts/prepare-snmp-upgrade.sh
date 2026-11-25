#!/bin/sh
# SPDX-License-Identifier: MIT
# Run on the OLD OpenWrt before its first upgrade to the SNMP-integrated image.
set -eu
mode=${1:---check}
case "$mode" in --check|--prepare) ;; *) echo 'Usage: prepare-snmp-upgrade.sh [--check|--prepare]' >&2; exit 2;; esac
[ "$(id -u)" = 0 ] || { echo 'Run as root on the OpenWrt being upgraded' >&2; exit 1; }
[ -x /sbin/sysupgrade ] && [ -d /etc/config ] || { echo 'Not an OpenWrt upgrade environment' >&2; exit 1; }
umask 077
work=$(mktemp -d /tmp/prowrt-snmp-upgrade.XXXXXX)
trap 'rm -rf "$work"' EXIT HUP INT TERM
: > "$work/paths"
for entry in /etc/config/quickstart /etc/config/lingjing_snmp /etc/lingjing-snmp /etc/lingjing-dhcp-names /etc/init.d/lingjing-snmp /usr/libexec/lingjing-snmp-collect /usr/libexec/lingjing-dhcp-names-collect /etc/rc.d/*lingjing-snmp; do
 [ -e "$entry" ] || [ -L "$entry" ] || continue
 printf '%s\n' "$entry" >> "$work/paths"
done
if [ ! -e /etc/config/lingjing_snmp ] && [ ! -d /etc/lingjing-snmp ]; then
 echo 'No existing site SNMP installation found; no preservation change needed.'
 exit 0
fi
sysupgrade -l > "$work/current"
missing=0
while IFS= read -r entry; do
 if [ -d "$entry" ]; then
  find "$entry" -type f > "$work/children"
 else
  printf '%s\n' "$entry" > "$work/children"
 fi
 while IFS= read -r child; do
  if ! grep -Fxq "$child" "$work/current"; then
   printf 'Not currently preserved: %s\n' "$child"
   printf '%s\n' "$child" >> "$work/missing"
  fi
 done < "$work/children"
done < "$work/paths"
[ ! -f "$work/missing" ] || missing=1
if [ "$mode" = --check ]; then
 [ "$missing" = 0 ] && echo 'Site SNMP files already appear in the native upgrade list.'
 exit "$missing"
fi
stamp=$(date +%Y%m%d-%H%M%S)
rollback=/root/prowrt-sysupgrade-conf-before-$stamp
if [ -e /etc/sysupgrade.conf ]; then
 cp -p /etc/sysupgrade.conf "$rollback"
 cp -p /etc/sysupgrade.conf "$work/new"
else
 : > "$rollback.absent"
 : > "$work/new"
fi
restore_config() {
 if [ -e "$rollback.absent" ]; then rm -f /etc/sysupgrade.conf; else cp -p "$rollback" /etc/sysupgrade.conf; fi
}
while IFS= read -r entry; do
 grep -Fxq "$entry" "$work/new" || printf '%s\n' "$entry" >> "$work/new"
done < "$work/paths"
chmod 600 "$work/new"
cp "$work/new" /etc/sysupgrade.conf
chmod 600 /etc/sysupgrade.conf
if ! sysupgrade -l > "$work/after"; then restore_config; exit 1; fi
while IFS= read -r entry; do
 if [ -d "$entry" ]; then find "$entry" -type f > "$work/children"; else printf '%s\n' "$entry" > "$work/children"; fi
 while IFS= read -r child; do
  if ! grep -Fxq "$child" "$work/after"; then restore_config; echo 'Preservation verification failed; original sysupgrade.conf restored.' >&2; exit 1; fi
 done < "$work/children"
done < "$work/paths"
backup=/tmp/prowrt-before-upgrade-$stamp.tar.gz
if ! sysupgrade -b "$backup"; then restore_config; exit 1; fi
chmod 600 "$backup"
tar -tzf "$backup" > "$work/archive"
while IFS= read -r entry; do
 if [ -d "$entry" ]; then find "$entry" -type f > "$work/children"; else printf '%s\n' "$entry" > "$work/children"; fi
 while IFS= read -r child; do
  relative=${child#/}
  if ! grep -Fxq "$relative" "$work/archive" && ! grep -Fxq "./$relative" "$work/archive"; then
   restore_config; echo 'Backup archive is incomplete; original sysupgrade.conf restored.' >&2; exit 1
  fi
 done < "$work/children"
done < "$work/paths"
printf 'Verified private backup: %s\nCopy it OFF the router before flashing.\n' "$backup"
printf 'sysupgrade.conf rollback: %s (or remove it if %s.absent exists).\n' "$rollback" "$rollback"
echo 'Old QuickStart controller and static JavaScript are intentionally excluded; the new image provides compatible hooks.'

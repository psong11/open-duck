#!/usr/bin/env bash
# Run this on the Mac with a FRESHLY FLASHED card mounted, before first boot.
#
# It bakes a flight recorder into the image via cloud-init, so that when the Pi
# stops answering we do not have to interrogate it over a network that is the
# thing that is broken. Pop the card in the Mac and run read_blackbox.sh.
#
#   ./scripts/instrument_sd.sh
set -euo pipefail

BOOT=${BOOT:-/Volumes/bootfs}
HERE=$(cd "$(dirname "$0")" && pwd)

[ -d "$BOOT" ]           || { echo "!! $BOOT not mounted. Insert the card."; exit 1; }
[ -f "$BOOT/user-data" ] || { echo "!! no cloud-init user-data in $BOOT."; echo "   Reflash with Raspberry Pi Imager and APPLY OS CUSTOMISATION (hostname/user/wifi)."; exit 1; }

if ! grep -q "resize" "$BOOT/cmdline.txt"; then
  echo "!! This card has already booted once (no 'resize' left in cmdline.txt)."
  echo "   Instrumenting it is still fine, but cloud-init will NOT re-run, so"
  echo "   nothing below would be installed. Reflash first."
  exit 1
fi

ts=$(date +%Y%m%d-%H%M%S)
cp "$BOOT/user-data" "$BOOT/user-data.orig-$ts"
cp "$BOOT/config.txt" "$BOOT/config.txt.orig-$ts"
cp "$BOOT/cmdline.txt" "$BOOT/cmdline.txt.orig-$ts"

indent() { sed 's/^/      /' "$1"; }

tmp=$(mktemp)

# Everything above runcmd, unchanged (keeps Imager's user, password hash, key).
sed '/^runcmd:/,$d' "$BOOT/user-data" > "$tmp"

cat >> "$tmp" <<'YAML'

write_files:
  - path: /usr/local/bin/blackbox.sh
    permissions: '0755'
    owner: root:root
    content: |
YAML
indent "$HERE/pi/blackbox.sh" >> "$tmp"

cat >> "$tmp" <<'YAML'
  - path: /usr/local/bin/bootsnap.sh
    permissions: '0755'
    owner: root:root
    content: |
YAML
indent "$HERE/pi/bootsnap.sh" >> "$tmp"

cat >> "$tmp" <<'YAML'
  - path: /etc/systemd/system/blackbox.service
    permissions: '0644'
    content: |
      [Unit]
      Description=Black box state recorder
      DefaultDependencies=no
      After=local-fs.target
      RequiresMountsFor=/boot/firmware
      Before=shutdown.target
      Conflicts=shutdown.target

      [Service]
      Type=simple
      ExecStart=/usr/local/bin/blackbox.sh run
      ExecStop=/usr/local/bin/blackbox.sh stop
      RemainAfterExit=no
      Restart=always
      RestartSec=5
      TimeoutStopSec=15

      [Install]
      WantedBy=sysinit.target

  - path: /etc/systemd/system/bootsnap.service
    permissions: '0644'
    content: |
      [Unit]
      Description=Per-boot forensic snapshot to the boot partition
      After=multi-user.target

      [Service]
      Type=oneshot
      ExecStart=/usr/local/bin/bootsnap.sh
      TimeoutStartSec=300

      [Install]
      WantedBy=multi-user.target

  # Keep the journal across reboots. Without this, the log explaining why the
  # last boot died is erased by the boot that comes asking.
  - path: /etc/systemd/journald.conf.d/persistent.conf
    permissions: '0644'
    content: |
      [Journal]
      Storage=persistent
      SystemMaxUse=100M

  # Second, independent way in: USB gadget ethernet on link-local. Needs no
  # DHCP and no config on the Mac -- reachable over IPv6 link-local even when
  # wifi is dead. Unproven on this hardware; the black box is the real answer.
  - path: /etc/NetworkManager/system-connections/usb0.nmconnection
    permissions: '0600'
    owner: root:root
    content: |
      [connection]
      id=usb0
      type=ethernet
      interface-name=usb0
      autoconnect=true

      [ipv4]
      method=link-local

      [ipv6]
      method=link-local
YAML

# runcmd: Imager's entries first, then ours.
grep -q '^runcmd:' "$BOOT/user-data" \
  && sed -n '/^runcmd:/,$p' "$BOOT/user-data" >> "$tmp" \
  || echo "runcmd:" >> "$tmp"

cat >> "$tmp" <<'YAML'
  - [ mkdir, -p, /var/log/journal ]
  - [ systemd-tmpfiles, --create, --prefix, /var/log/journal ]
  - [ systemctl, restart, systemd-journald ]
  - [ systemctl, enable, blackbox.service ]
  - [ systemctl, enable, bootsnap.service ]
  - [ systemctl, start, blackbox.service ]
  - [ sh, -c, "mkdir -p /boot/firmware/blackbox; echo instrumented $(date -u +%FT%TZ) kernel=$(uname -r) >> /boot/firmware/blackbox/installed.txt; sync" ]
YAML

mv "$tmp" "$BOOT/user-data"

# USB gadget mode for the usb0 interface above.
grep -q '^dtoverlay=dwc2' "$BOOT/config.txt" || printf '\ndtoverlay=dwc2\n' >> "$BOOT/config.txt"
if ! grep -q 'modules-load=dwc2' "$BOOT/cmdline.txt"; then
  # cmdline.txt must stay exactly one line.
  perl -pi -e 's/\brootwait\b/rootwait modules-load=dwc2,g_ether/' "$BOOT/cmdline.txt"
fi

echo "installed. verifying:"
echo "  user-data lines : $(wc -l < "$BOOT/user-data")"
echo "  cmdline lines   : $(wc -l < "$BOOT/cmdline.txt")  (must be 1)"
grep -c '^  - path:' "$BOOT/user-data" | sed 's/^/  write_files     : /'
echo
echo "cmdline.txt:"; cat "$BOOT/cmdline.txt"
echo
echo "Eject with:  diskutil eject $BOOT"

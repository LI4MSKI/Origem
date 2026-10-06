#!/usr/bin/env bash
# Origem – ISO-Build
# Baut aus dem offiziellen Arch-"releng"-Profil + dem Origem-Overlay eine bootfähige ISO.
# Muss auf Arch Linux (oder im Arch-Docker-Container, siehe build-docker.sh) als root laufen.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK:-/tmp/origem-work}"
PROFILE="$WORK/profile"
OUT="${OUT:-$HERE/out}"

[[ $EUID -eq 0 ]] || { echo "Bitte als root starten: sudo ./build.sh"; exit 1; }
command -v mkarchiso >/dev/null || pacman -S --needed --noconfirm archiso

echo "==> Profil vorbereiten"
rm -rf "$WORK"; mkdir -p "$WORK" "$OUT"
cp -r /usr/share/archiso/configs/releng "$PROFILE"

# 1) Origem-Dateien über das Profil legen
cp -rT "$HERE/airootfs" "$PROFILE/airootfs"

# 2) Zusätzliche Pakete
grep -v '^\s*#' "$HERE/packages.origem" | sed '/^\s*$/d' >> "$PROFILE/packages.x86_64"
sort -u -o "$PROFILE/packages.x86_64" "$PROFILE/packages.x86_64"

# 3) multilib aktivieren (für Steam / 32-Bit-Grafiktreiber)
sed -i '/^#\[multilib\]/,/^#Include/ s/^#//' "$PROFILE/pacman.conf"

# In Containern (Docker, GitHub) kann pacman den Download-Sandbox nicht nutzen
if [[ -f /.dockerenv ]] && ! grep -q '^DisableSandbox' "$PROFILE/pacman.conf"; then
  sed -i '/^\[options\]/a DisableSandbox' "$PROFILE/pacman.conf"
  sed -i 's/^CheckSpace/#CheckSpace/' "$PROFILE/pacman.conf"
fi

# 4) Name, Version, Rechte
sed -i \
  -e 's/^iso_name=.*/iso_name="origem"/' \
  -e 's/^iso_label=.*/iso_label="ORIGEM_$(date +%Y%m)"/' \
  -e 's/^iso_publisher=.*/iso_publisher="Origem <https:\/\/github.com\/LI4MSKI>"/' \
  -e 's/^iso_application=.*/iso_application="Origem Live"/' \
  "$PROFILE/profiledef.sh"
cat >> "$PROFILE/profiledef.sh" <<'EOF'
file_permissions+=(
  ["/usr/bin/origem-shell"]="0:0:755"
  ["/usr/lib/origem/live-user.sh"]="0:0:755"
  ["/etc/sudoers.d/origem"]="0:0:440"
)
EOF

# 5) Dienste aktivieren
WANTS="$PROFILE/airootfs/etc/systemd/system/multi-user.target.wants"
mkdir -p "$WANTS"
ln -sf /usr/lib/systemd/system/ollama.service   "$WANTS/ollama.service"
ln -sf /usr/lib/systemd/system/vboxservice.service "$WANTS/vboxservice.service"
ln -sf /etc/systemd/system/origem-live-user.service "$WANTS/origem-live-user.service"

# 6) Bootmenü umbenennen
{ grep -rl "Arch Linux install medium" "$PROFILE"/{efiboot,syslinux,grub} 2>/dev/null || true; } \
  | xargs -r sed -i 's/Arch Linux install medium/Origem Live/g'

echo "==> ISO bauen (dauert je nach Internet 10–40 Minuten)"
mkarchiso -v -w "$WORK/build" -o "$OUT" "$PROFILE"
echo "==> Fertig: $(ls -1 "$OUT"/origem-*.iso | tail -1)"

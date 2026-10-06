# Auf dem ersten Bildschirm direkt in die Origem-Oberfläche starten
if [ -z "$WAYLAND_DISPLAY" ] && [ "$XDG_VTNR" = 1 ]; then
    # In virtuellen Maschinen (VirtualBox, VMware, QEMU) Einstellungen für VM-Grafik setzen
    mkdir -p ~/.config/hypr
    if [ "$(systemd-detect-virt)" != "none" ]; then
        cat > ~/.config/hypr/vm.conf <<'EOF'
cursor {
    no_hardware_cursors = true
}
decoration {
    blur {
        enabled = false
    }
}
EOF
    else
        echo "# kein VM-Modus" > ~/.config/hypr/vm.conf
    fi

    if command -v start-hyprland >/dev/null; then exec start-hyprland; else exec Hyprland; fi
fi

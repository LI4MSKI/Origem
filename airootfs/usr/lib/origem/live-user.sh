#!/bin/sh
# Legt im Live-System den Benutzer "origem" (ohne Passwort) an.
if ! id origem >/dev/null 2>&1; then
    useradd -m -G wheel,video,input,audio -s /bin/zsh origem
    passwd -d origem
fi

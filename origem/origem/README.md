# ◎ Origem

Ein eigenes Betriebssystem auf Arch-Linux-Basis – mit eigener Oberfläche, eingebauter lokaler KI und fertig für Gaming.

**Version 0.1 – Live-System.** Origem bootet vom USB-Stick oder in einer virtuellen Maschine direkt auf den Origem-Desktop.

## Was drin ist

| Bereich | Inhalt |
|---|---|
| Oberfläche | **Origem Shell** (selbst geschrieben, Python + GTK4) auf dem Hyprland-Fenstermanager: Leiste, App-Launcher, KI-Panel, eigener Hintergrund |
| KI | Ollama läuft als Dienst, das KI-Panel chattet komplett lokal mit dem Modell |
| Gaming | Steam (inkl. Proton), GameMode, MangoHud, 32-Bit-Treiber für AMD/Intel |
| Alltag | Firefox (Deutsch), Dateimanager Thunar, Terminal Kitty, PipeWire-Audio |

## Tastenkürzel

| Kürzel | Aktion |
|---|---|
| `SUPER + Leertaste` | App-Launcher |
| `SUPER + A` | KI-Panel |
| `SUPER + Enter` | Terminal |
| `SUPER + B` / `E` / `G` | Firefox / Dateien / Steam |
| `SUPER + Q` | Fenster schließen |
| `SUPER + F` / `V` | Vollbild / schwebend |
| `SUPER + 1–5` | Arbeitsfläche wechseln (`+ SHIFT`: Fenster verschieben) |
| `SUPER + Maus` | Fenster ziehen (links) / Größe ändern (rechts) |
| `SUPER + SHIFT + E` | Abmelden |

Mausrad auf der Lautstärke in der Leiste ändert die Lautstärke.

## ISO bauen

**Auf Arch Linux:**

```bash
sudo ./build.sh
```

**Auf Windows / einem anderen Linux** (Docker Desktop nötig, unter Windows aus WSL starten):

```bash
./build-docker.sh
```

Die fertige ISO landet in `out/origem-JJJJ.MM.TT-x86_64.iso` (ca. 3–4 GB). Der erste Build dauert je nach Internet 10–40 Minuten.

## Ausprobieren

- **Virtuelle Maschine:** VirtualBox oder VMware, mind. 4 GB RAM, 3D-Beschleunigung an, ISO als CD einlegen. Hyprland braucht funktionierende 3D-Grafik; wenn der Bildschirm schwarz bleibt, in VirtualBox den Grafikcontroller auf *VMSVGA* mit 3D stellen oder gleich echte Hardware nehmen.
- **Echter PC:** ISO mit [Ventoy](https://www.ventoy.net) oder Rufus auf einen USB-Stick, davon booten.

Beim ersten Start der KI im Terminal einmal das Modell laden:

```bash
ollama pull llama3.2:3b
```

Danach funktioniert `SUPER + A` offline. Ein anderes Modell stellst du in `~/.config/origem/config.json` ein:

```json
{ "model": "qwen2.5:7b" }
```

Hinweis: Im Live-System liegt alles im Arbeitsspeicher, das Modell ist nach dem Neustart wieder weg. Das ändert sich mit dem Installer.

## Projektaufbau

```
origem/
├── build.sh              ISO bauen (nimmt Arch "releng" + Origem-Overlay)
├── build-docker.sh       dasselbe im Docker-Container
├── packages.origem       zusätzliche Pakete
└── airootfs/             Dateien, die ins System kopiert werden
    ├── etc/os-release              Systemname "Origem"
    ├── etc/skel/                   Startdateien jedes neuen Benutzers
    │   ├── .config/hypr/hyprland.conf   Fenstermanager, Tastenkürzel, Animationen
    │   └── .zprofile                    startet die Oberfläche nach dem Login
    └── usr/lib/origem/
        ├── shell.py        die Origem-Oberfläche
        └── style.css       das Design
```

**Am Design schrauben ohne neue ISO:** Im laufenden Origem `/usr/lib/origem/style.css` bearbeiten und mit `pkill -f origem/shell.py; origem-shell &` neu starten.

## Bekannte Grenzen von 0.1

- NVIDIA-Grafikkarten: Pakete `nvidia-open`, `lib32-nvidia-utils` in `packages.origem` ergänzen.
- WLAN im Live-System per Terminal: `iwctl` → `station wlan0 connect <Netzname>`.
- Noch kein Installer, kein Login-Bildschirm, keine Einstellungs-App.

## Nächste Schritte

1. **Installer** – Origem auf die Festplatte installieren (Calamares oder eigener grafischer Installer)
2. **Einstellungen-App** – WLAN, Bluetooth, Bildschirm, Hintergrund
3. **Benachrichtigungen + Sperrbildschirm** im Origem-Stil
4. **KI tiefer einbauen** – Dateien durchsuchen, Apps per Sprache öffnen, eigenes Modell (Jarvis) als Option
5. **Eigenes Paket-Repo** auf GitHub, damit Origem-Updates per `pacman -Syu` kommen

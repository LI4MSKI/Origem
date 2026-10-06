#!/usr/bin/env python3
"""
◎ Origem Shell – die eigene Oberfläche von Origem.

Teile:
  • Hintergrund  – eigener Verlauf als Desktop
  • Leiste       – oben: Origem-Knopf, Arbeitsflächen, Uhr, Lautstärke, Akku, Netz, Power
  • Launcher     – SUPER+Leertaste: Apps suchen und starten
  • KI-Panel     – SUPER+A: Chat mit einem lokalen Modell über Ollama

Aufruf:  origem-shell                    startet die Oberfläche
         origem-shell --toggle launcher  öffnet/schließt den Launcher
         origem-shell --toggle ai        öffnet/schließt das KI-Panel
"""
import glob
import json
import os
import subprocess
import sys
import threading
import urllib.request

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402
from gi.repository import Gtk4LayerShell as LS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.expanduser("~/.config/origem/config.json")
DEFAULTS = {
    "model": "llama3.2:3b",
    "ollama_url": "http://127.0.0.1:11434",
    "workspaces": 5,
    "system_prompt": (
        "Du bist Origem, der eingebaute KI-Assistent des Betriebssystems Origem. "
        "Antworte auf Deutsch, freundlich, kurz und konkret."
    ),
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def run(cmd, timeout=1.0):
    """Befehl ausführen und Ausgabe zurückgeben ('' bei Fehler)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def spawn(*cmd):
    try:
        subprocess.Popen(cmd, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def layer_window(app, namespace, layer, anchors=(), keyboard=None, css_class=None):
    win = Gtk.ApplicationWindow(application=app)
    win.set_decorated(False)
    LS.init_for_window(win)
    LS.set_namespace(win, namespace)
    LS.set_layer(win, layer)
    for edge in anchors:
        LS.set_anchor(win, edge, True)
    if keyboard is not None:
        LS.set_keyboard_mode(win, keyboard)
    if css_class:
        win.add_css_class(css_class)
    return win


def on_escape(win, callback):
    ctrl = Gtk.EventControllerKey()

    def pressed(_c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            callback()
            return True
        return False

    ctrl.connect("key-pressed", pressed)
    win.add_controller(ctrl)


# ----------------------------------------------------------------- Leiste
class Panel:
    def __init__(self, shell):
        self.shell = shell
        E = LS.Edge
        self.win = layer_window(shell, "origem-panel", LS.Layer.TOP,
                                (E.TOP, E.LEFT, E.RIGHT), css_class="origem-panel")
        LS.auto_exclusive_zone_enable(self.win)
        for edge in (E.TOP, E.LEFT, E.RIGHT):
            LS.set_margin(self.win, edge, 8)

        bar = Gtk.CenterBox()
        bar.add_css_class("bar")

        # links: Logo + Arbeitsflächen
        left = Gtk.Box(spacing=6)
        logo = Gtk.Button(label="◎  Origem")
        logo.add_css_class("logo")
        logo.connect("clicked", lambda *_: shell.toggle("launcher"))
        left.append(logo)
        self.ws_buttons = []
        for n in range(1, shell.cfg["workspaces"] + 1):
            b = Gtk.Button(label=str(n))
            b.add_css_class("ws")
            b.connect("clicked", lambda _b, n=n: spawn("hyprctl", "dispatch", "workspace", str(n)))
            left.append(b)
            self.ws_buttons.append(b)
        bar.set_start_widget(left)

        # Mitte: Uhr
        self.clock = Gtk.Label()
        self.clock.add_css_class("clock")
        bar.set_center_widget(self.clock)

        # rechts: KI, Status, Power
        right = Gtk.Box(spacing=6)
        ai = Gtk.Button(label="✦ KI")
        ai.add_css_class("pill")
        ai.add_css_class("ai-btn")
        ai.connect("clicked", lambda *_: shell.toggle("ai"))
        right.append(ai)

        self.net = self._pill(right)
        self.vol = self._pill(right)
        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._on_volume_scroll)
        self.vol.add_controller(scroll)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: spawn("pavucontrol"))
        self.vol.add_controller(click)
        self.bat = self._pill(right)

        right.append(self._power_menu())
        bar.set_end_widget(right)

        self.win.set_child(bar)
        self.win.present()

        self.tick()
        GLib.timeout_add_seconds(1, self.tick)

    def _pill(self, box):
        lbl = Gtk.Label()
        lbl.add_css_class("pill")
        box.append(lbl)
        return lbl

    def _power_menu(self):
        btn = Gtk.MenuButton(label="⏻")
        btn.add_css_class("pill")
        btn.add_css_class("power")
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.add_css_class("menu")
        for text, cmd in (("Abmelden", ("hyprctl", "dispatch", "exit")),
                          ("Neu starten", ("systemctl", "reboot")),
                          ("Ausschalten", ("systemctl", "poweroff"))):
            b = Gtk.Button(label=text)
            b.connect("clicked", lambda _b, c=cmd: spawn(*c))
            box.append(b)
        pop.set_child(box)
        btn.set_popover(pop)
        return btn

    def _on_volume_scroll(self, _ctrl, _dx, dy):
        spawn("wpctl", "set-volume", "-l", "1", "@DEFAULT_AUDIO_SINK@", "5%+" if dy < 0 else "5%-")
        GLib.timeout_add(80, self._update_volume)
        return True

    def _update_volume(self):
        out = run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])  # "Volume: 0.40 [MUTED]"
        try:
            pct = round(float(out.split()[1]) * 100)
            self.vol.set_text("🔇 stumm" if "MUTED" in out else f"🔊 {pct}%")
        except (IndexError, ValueError):
            self.vol.set_text("🔊 –")
        return False

    def tick(self):
        now = GLib.DateTime.new_now_local()
        self.clock.set_text(now.format("%A, %d. %B   %H:%M"))

        # nur alle 3 Sekunden die langsameren Abfragen
        if now.get_second() % 3 == 0 or not self.vol.get_text():
            self._update_volume()

            bats = glob.glob("/sys/class/power_supply/BAT*/capacity")
            if bats:
                try:
                    with open(bats[0]) as f:
                        cap = f.read().strip()
                    with open(os.path.join(os.path.dirname(bats[0]), "status")) as f:
                        charging = f.read().strip() == "Charging"
                    self.bat.set_text(f"{'⚡' if charging else '🔋'} {cap}%")
                    self.bat.set_visible(True)
                except OSError:
                    self.bat.set_visible(False)
            else:
                self.bat.set_visible(False)

            online = bool(run(["ip", "-o", "route", "show", "default"]))
            self.net.set_text("🌐 online" if online else "⚠ offline")

            try:
                active = json.loads(run(["hyprctl", "activeworkspace", "-j"]) or "{}").get("id")
            except ValueError:
                active = None
            for i, b in enumerate(self.ws_buttons, start=1):
                if i == active:
                    b.add_css_class("active")
                else:
                    b.remove_css_class("active")
        return True


# --------------------------------------------------------------- Launcher
class Launcher:
    def __init__(self, shell):
        self.win = layer_window(shell, "origem-launcher", LS.Layer.OVERLAY,
                                keyboard=LS.KeyboardMode.EXCLUSIVE, css_class="origem-launcher")
        on_escape(self.win, self.hide)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        box.add_css_class("card")

        title = Gtk.Label(label="Was möchtest du starten?", xalign=0)
        title.add_css_class("title")
        box.append(title)

        self.search = Gtk.SearchEntry(placeholder_text="App suchen …")
        self.search.connect("search-changed", self.filter)
        self.search.connect("activate", self.launch_first)
        box.append(self.search)

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                max_children_per_line=5, min_children_per_line=3,
                                homogeneous=True, row_spacing=8, column_spacing=8)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(380)
        scroller.set_min_content_width(640)
        scroller.set_child(self.flow)
        box.append(scroller)

        self.win.set_child(box)
        self.apps = []

    def reload_apps(self):
        while (child := self.flow.get_first_child()) is not None:
            self.flow.remove(child)
        self.apps = []
        infos = [a for a in Gio.AppInfo.get_all() if a.should_show()]
        for info in sorted(infos, key=lambda a: a.get_display_name().lower()):
            tile = Gtk.Button()
            tile.add_css_class("app")
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            icon = Gtk.Image.new_from_gicon(info.get_icon()) if info.get_icon() else \
                Gtk.Image.new_from_icon_name("application-x-executable")
            icon.set_pixel_size(48)
            name = Gtk.Label(label=info.get_display_name(), ellipsize=Pango.EllipsizeMode.END, max_width_chars=14)
            inner.append(icon)
            inner.append(name)
            tile.set_child(inner)
            tile.connect("clicked", lambda _b, i=info: self.launch(i))
            self.flow.append(tile)
            child = self.flow.get_last_child()
            keywords = " ".join([info.get_display_name(), info.get_description() or "",
                                 info.get_executable() or ""]).lower()
            self.apps.append((child, info, keywords))

    def filter(self, *_):
        q = self.search.get_text().lower().strip()
        for child, _info, kw in self.apps:
            child.set_visible(q in kw)

    def launch_first(self, *_):
        for child, info, _kw in self.apps:
            if child.get_visible():
                self.launch(info)
                return

    def launch(self, info):
        try:
            info.launch(None, None)
        except GLib.Error as e:
            print("Start fehlgeschlagen:", e.message, file=sys.stderr)
        self.hide()

    def show(self):
        self.reload_apps()
        self.search.set_text("")
        self.win.present()
        self.search.grab_focus()

    def hide(self):
        self.win.set_visible(False)

    def toggle(self):
        self.hide() if self.win.get_visible() else self.show()


# ---------------------------------------------------------------- KI-Panel
class AIPanel:
    def __init__(self, shell):
        self.cfg = shell.cfg
        E = LS.Edge
        self.win = layer_window(shell, "origem-ai", LS.Layer.OVERLAY, (E.TOP, E.RIGHT, E.BOTTOM),
                                keyboard=LS.KeyboardMode.ON_DEMAND, css_class="origem-ai")
        for edge in (E.TOP, E.RIGHT, E.BOTTOM):
            LS.set_margin(self.win, edge, 12)
        self.win.set_default_size(420, -1)
        on_escape(self.win, self.hide)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        root.add_css_class("card")
        root.set_size_request(420, -1)

        head = Gtk.Box(spacing=8)
        t = Gtk.Label(label="✦ Origem KI", xalign=0, hexpand=True)
        t.add_css_class("title")
        head.append(t)
        model = Gtk.Label(label=self.cfg["model"])
        model.add_css_class("muted")
        head.append(model)
        clear = Gtk.Button(label="Neu")
        clear.add_css_class("pill")
        clear.connect("clicked", self.reset)
        head.append(clear)
        root.append(head)

        self.msgs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.scroller = Gtk.ScrolledWindow(vexpand=True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_child(self.msgs)
        root.append(self.scroller)

        self.entry = Gtk.Entry(placeholder_text="Frag mich etwas …  (Enter)")
        self.entry.connect("activate", self.send)
        root.append(self.entry)

        self.win.set_child(root)
        self.busy = False
        self.reset()

    def reset(self, *_):
        while (c := self.msgs.get_first_child()) is not None:
            self.msgs.remove(c)
        self.history = [{"role": "system", "content": self.cfg["system_prompt"]}]
        self.bubble("ai", "Hallo! Ich laufe komplett lokal auf deinem Rechner. Womit kann ich helfen?")

    def bubble(self, who, text):
        lbl = Gtk.Label(label=text, wrap=True, selectable=True, xalign=0)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lbl.add_css_class("bubble")
        lbl.add_css_class(who)
        lbl.set_halign(Gtk.Align.END if who == "user" else Gtk.Align.START)
        self.msgs.append(lbl)
        GLib.idle_add(self.scroll_down)
        return lbl

    def scroll_down(self):
        adj = self.scroller.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False

    def send(self, *_):
        text = self.entry.get_text().strip()
        if not text or self.busy:
            return
        self.entry.set_text("")
        self.bubble("user", text)
        self.history.append({"role": "user", "content": text})
        target = self.bubble("ai", "…")
        self.busy = True
        threading.Thread(target=self.ask, args=(target,), daemon=True).start()

    def ask(self, target):
        answer = ""
        body = json.dumps({"model": self.cfg["model"], "messages": self.history,
                           "stream": True}).encode()
        req = urllib.request.Request(self.cfg["ollama_url"] + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    answer += chunk.get("message", {}).get("content", "")
                    GLib.idle_add(self._update, target, answer)
                    if chunk.get("done"):
                        break
            self.history.append({"role": "assistant", "content": answer})
        except Exception as e:  # Netzwerk, fehlendes Modell, …
            msg = (f"Ich kann das Modell gerade nicht erreichen ({e}).\n\n"
                   f"Öffne ein Terminal (SUPER+Enter) und lade es einmalig herunter:\n"
                   f"ollama pull {self.cfg['model']}")
            self.history.pop()
            GLib.idle_add(self._update, target, msg)
        finally:
            self.busy = False

    def _update(self, label, text):
        label.set_text(text)
        self.scroll_down()
        return False

    def show(self):
        self.win.present()
        self.entry.grab_focus()

    def hide(self):
        self.win.set_visible(False)

    def toggle(self):
        self.hide() if self.win.get_visible() else self.show()


# ------------------------------------------------------------ Hintergrund
class Background:
    def __init__(self, shell):
        E = LS.Edge
        self.win = layer_window(shell, "origem-bg", LS.Layer.BACKGROUND,
                                (E.TOP, E.BOTTOM, E.LEFT, E.RIGHT), css_class="origem-bg")
        LS.set_exclusive_zone(self.win, -1)
        mark = Gtk.Label(label="◎", valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
        mark.add_css_class("bg-mark")
        self.win.set_child(mark)
        self.win.present()


# -------------------------------------------------------------- Anwendung
class Shell(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="os.origem.Shell",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.cfg = load_config()
        self.parts = {}

    def do_startup(self):
        Gtk.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_path(os.path.join(HERE, "style.css"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def build(self):
        if self.parts:
            return
        Background(self)
        self.parts["panel"] = Panel(self)
        self.parts["launcher"] = Launcher(self)
        self.parts["ai"] = AIPanel(self)

    def toggle(self, name):
        part = self.parts.get(name)
        if part:
            part.toggle()

    def do_command_line(self, cmdline):
        args = cmdline.get_arguments()[1:]
        self.build()
        if len(args) >= 2 and args[0] == "--toggle":
            self.toggle(args[1])
        return 0


if __name__ == "__main__":
    sys.exit(Shell().run(sys.argv))

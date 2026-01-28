"""
Winget (Compact List UI)
------------------------------------------------
GUI: customtkinter (Fluent-ish Windows 11 style)
Backend: PowerShell / winget (Winget-Installscript.ps1)

Optimiert für viele Apps:
- 3-Spalten Layout (Kategorien | App-Liste | Status/Deps)
- Suchfeld + Kategorie-Filter
- App-Liste als kompakte Zeilen
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Tuple

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

try:
    from PIL import Image
except ImportError:
    Image = None


# =============================================================================
# Configuration
# =============================================================================

README_URL = "https://github.com/SD-ITLab/Winget-Script"  # anpassen
LOGO_URL = "https://sd-itlab.de/"

BRAND_TEXT = "© 2026 SD-ITLab – MIT licensed"
BRAND_URL = "https://sd-itlab.de"

APP_TITLE = "Winget Deploy UI by SD-ITLab"
WINDOW_SIZE = "1120x620"

# Feste Maße für die App-Zeilen
ROW_WIDTH = 760
ROW_HEIGHT = 90  # kannst du bei Bedarf leicht anpassen
MID_WIDTH = 820   # feste Breite der mittleren Spalte (App-Liste)

# --- Fluent-ish (Windows 11) Light Palette ---
BG_WINDOW = "#F3F4F6"
BG_CARD = "#FFFFFF"
BG_CARD_SELECTED = "#E7F1FF"
BORDER_CARD = "#E5E7EB"
BORDER_CARD_SELECTED = "#3B82F6"
BG_RIGHT_PANEL = "#EFF4FF"
TEXT_MUTED = "#6B7280"
ACCENT = "#3B82F6"


# =============================================================================
# Paths (PyInstaller-safe)
# =============================================================================

def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def meipass_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", exe_dir())).resolve()


EXE_DIR: Path = exe_dir()
MEI_DIR: Path = meipass_dir()


def resource_path(filename: str) -> Path:
    return (MEI_DIR / filename).resolve()


LOGO_PATH = resource_path("logo.png")
ICON_PATH = resource_path("icon.ico")
# PowerShell-Script für Winget/AppInstaller/Install
WINGET_SETUP_PS = resource_path("winget-installscript.ps1")

# =============================================================================
# Helper, um das PowerShell-Skript aufzurufen
# =============================================================================

def _run_silent(cmd: list[str], timeout: int = 5) -> subprocess.CompletedProcess:
    """
    Führt einen Prozess ohne sichtbares Fenster aus (Windows).
    Gibt immer ein CompletedProcess zurück, stdout/stderr als Text.
    """
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def run_winget_ps_setup() -> None:
    """
    Führt das PowerShell-Backend im Setup-Modus aus, um
    Winget + App Installer + Abhängigkeiten zu installieren/aktualisieren.

    - nutzt genau WINGET_SETUP_PS
    - schreibt ein Log (winget-setup.log) ins EXE-/Script-Verzeichnis
    - wirft bei Fehlern eine RuntimeError mit Hinweis auf das Log
    """
    if not WINGET_SETUP_PS.exists():
        raise FileNotFoundError(f"Winget-Installscript nicht gefunden: {WINGET_SETUP_PS}")

    cmd = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(WINGET_SETUP_PS),
        "-SetupWinget",
    ]

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    log_path = EXE_DIR / "winget-setup.log"
    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(f"Command : {' '.join(cmd)}\n")
            f.write(f"PS1     : {WINGET_SETUP_PS}\n")
            f.write(f"Return  : {result.returncode}\n\n")

            f.write("=== STDOUT ===\n")
            f.write(result.stdout or "")
            f.write("\n\n=== STDERR ===\n")
            f.write(result.stderr or "")
    except Exception:
        # Wenn loggen scheitert, ist es nicht schlimm
        pass

    if result.returncode != 0:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        msg = stderr or stdout or f"Winget-Setup Fehlercode {result.returncode}"
        msg += f"\n\nDetails siehe Log-Datei:\n{log_path}"
        raise RuntimeError(msg)


def run_winget_ps_install(app_ids: list[str], on_event=None) -> tuple[list[str], list[str]]:
    if not app_ids:
        return ([], [])

    if not WINGET_SETUP_PS.exists():
        raise FileNotFoundError(f"Winget-Installscript nicht gefunden: {WINGET_SETUP_PS}")

    cmd = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(WINGET_SETUP_PS),
        *app_ids,  # <-- positional App-IDs
    ]

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    installed: list[str] = []
    failed: list[str] = []
    failed_ids_from_summary: list[str] = []

    # Marker-Parser
    re_start = re.compile(r"Installing app via winget:\s*(.+)$")
    re_ok = re.compile(r"App installed successfully:\s*(.+)$")
    re_failed = re.compile(r"FAILED_APPS:\s*(.+)$")

    # STDOUT live lesen
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\r\n")

        if on_event:
            on_event(("line", line))

        m = re_start.search(line)
        if m:
            current_id = m.group(1).strip()
            if on_event:
                on_event(("start", current_id))
            continue

        m = re_ok.search(line)
        if m:
            ok_id = m.group(1).strip()
            installed.append(ok_id)
            if on_event:
                on_event(("ok", ok_id))
            continue

        m = re_failed.search(line)
        if m:
            tail = m.group(1).strip()
            failed_ids_from_summary = [s.strip() for s in tail.split(",") if s.strip()]
            continue

    rc = proc.wait()

    stderr = ""
    if proc.stderr is not None:
        stderr = proc.stderr.read() or ""

    if failed_ids_from_summary:
        failed = failed_ids_from_summary

    if rc != 0 and not failed and not installed:
        short = "\n".join((stderr.strip() or "Unbekannter Fehler").splitlines()[:10])
        raise RuntimeError(f"Winget-Installation ist fehlgeschlagen:\n{short}")

    return (installed, failed)


# =============================================================================
# Domain Model
# =============================================================================

@dataclass(frozen=True)
class WingetPackage:
    id: str
    display_name: str
    description: str
    category: str
    default_selected: bool = False


PACKAGES: Dict[str, WingetPackage] = {
    # Office / Docs
    "libreoffice": WingetPackage("TheDocumentFoundation.LibreOffice", "LibreOffice", "Office-Suite (Open Source).", "Office", False),
    "openoffice":  WingetPackage("Apache.OpenOffice", "Apache OpenOffice", "Office-Suite (älter, kompatibel).", "Office", False),
    "onlyoffice":  WingetPackage("ONLYOFFICE.DesktopEditors", "ONLYOFFICE", "Office-Suite (modern, MS-kompatibel).", "Office", False),

    # PDF / Tools
    "pdf24":       WingetPackage("geeksoftwareGmbH.PDF24Creator", "PDF24 Creator", "PDF erstellen, zusammenfügen, Tools.", "Tools", False),
    "notepadpp":   WingetPackage("Notepad++.Notepad++", "Notepad++", "Text-/Code-Editor.", "Tools", False),
    "7zip":        WingetPackage("7zip.7zip", "7-Zip", "Packprogramm (7z/zip/rar).", "Tools", False),
    "everything":  WingetPackage("voidtools.Everything", "Everything", "Ultra-schnelle Dateisuche.", "Tools", False),

    # Mail / Runtime
    "thunderbird": WingetPackage("Mozilla.Thunderbird", "Thunderbird", "Kostenloser E-Mail-Client mit Kalender und Adressbuch.", "Kommunikation", False),
    "java":        WingetPackage("Oracle.JavaRuntimeEnvironment", "Java Runtime", "Benötigt für einige Programme.", "Runtimes", False),

    # Media
    "adobe":       WingetPackage("Adobe.Acrobat.Reader.64-bit", "Adobe Acrobat Reader", "PDF-Viewer von Adobe.", "Media", False),
    "vlc":         WingetPackage("VideoLAN.VLC", "VLC Media Player", "Media Player für fast alles.", "Media", False),
    "spotify":     WingetPackage("Spotify.Spotify", "Spotify", "Musik-Streaming.", "Media", False),
    "mpc-hc":      WingetPackage("clsid2.mpc-hc", "Media Player Classic", "Media Player Classic (leichter Player).", "Media", False),

    # Security
    "malwarebytes": WingetPackage("Malwarebytes.Malwarebytes", "Malwarebytes", "On-Demand Malware Scanner.", "Security", False),
    "avira":        WingetPackage("XPFD23M0L795KD", "Avira Security", "Kostenlose Antivirus- & Security-Suite (Store).", "Security", False),
    "avast":        WingetPackage("XPDNZJFNCR1B07", "Avast Free Antivirus", "Kostenloser Virenschutz (Store).", "Security", False),
    "avg":          WingetPackage("XP8BX2DWV7TF50", "AVG AntiVirus Free", "Kostenloser Virenschutz (Store).", "Security", False),

    # Remote
    "teamviewer":  WingetPackage("TeamViewer.TeamViewer", "TeamViewer", "Remote-Support Tool.", "Remote", False),
    "anydesk":     WingetPackage("AnyDesk.AnyDesk", "AnyDesk", "Remote-Support Tool.", "Remote", False),
    "rustdesk":    WingetPackage("RustDesk.RustDesk", "RustDesk", "Remote-Support (Selfhost möglich).", "Remote", False),

    # Browser
    "chrome":      WingetPackage("Google.Chrome", "Google Chrome", "Browser (Chromium).", "Browser", False),
    "firefox":     WingetPackage("Mozilla.Firefox", "Mozilla Firefox", "Browser (Standard).", "Browser", False),
    "brave":       WingetPackage("Brave.Brave", "Brave", "Browser (Privacy).", "Browser", False),
    "opera":       WingetPackage("Opera.Opera", "Opera", "Browser.", "Browser", False),
    "operagx":     WingetPackage("Opera.OperaGX", "Opera GX", "Browser (Gaming).", "Browser", False),

    # Cloud / Storage
    "dropbox":     WingetPackage("Dropbox.Dropbox", "Dropbox", "Cloud-Speicher & Dateisynchronisation.", "Cloud", False),
    "onedrive":    WingetPackage("Microsoft.OneDrive", "Microsoft OneDrive", "Cloud-Speicher von Microsoft.", "Cloud", False),
    "googledrive": WingetPackage("Google.GoogleDrive", "Google Drive for Desktop", "Google Drive Synchronisation.", "Cloud", False),

    # Graphics
    "gimp":        WingetPackage("GIMP.GIMP.3", "GIMP 3", "Bildbearbeitung (Open Source, Photoshop-Alternative).", "Graphics", False),
    "irfanview":   WingetPackage("IrfanSkiljan.IrfanView", "IrfanView", "Schneller Bildbetrachter.", "Graphics", False),
    "krita":       WingetPackage("KDE.Krita", "Krita", "Bildbearbeitung / Painting (Open Source).", "Graphics", False),
    "googleearth": WingetPackage("Google.EarthPro", "Google Earth Pro", "3D-Kartendarstellung, Satellitenbilder & Geodaten-Visualisierung.", "Graphics", False),

    # Communication
    "teams":       WingetPackage("Microsoft.Teams", "Microsoft Teams", "Chat, Meetings & Zusammenarbeit.", "Kommunikation", False),
    "zoom":        WingetPackage("Zoom.Zoom", "Zoom", "Video-Meetings & Webkonferenzen.", "Kommunikation", False),
    "whatsapp":    WingetPackage("9NKSQGP7F2NH", "WhatsApp Desktop", "WhatsApp für Windows.", "Kommunikation", False),
}


def sorted_keys_for_render(keys: List[str]) -> List[str]:
    """Alphabetische Sortierung nach Anzeigename."""
    return sorted(keys, key=lambda k: PACKAGES[k].display_name.lower())


class UiState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    FAIL = "fail"
    SKIP = "skip"


UI_STATUS_STYLE: Dict[UiState, Tuple[str, str]] = {
    UiState.PENDING: ("•", TEXT_MUTED),
    UiState.RUNNING: ("⏳", "#2563EB"),
    UiState.OK:      ("✔", "#16A34A"),
    UiState.FAIL:    ("✖", "#DC2626"),
    UiState.SKIP:    ("⏭", "#6B7280"),
}


class DepKey(Enum):
    WINGET = "winget"
    DESKTOP_APP_INSTALLER = "desktop_app_installer"
    POWERSHELL = "powershell"


DEP_LABELS: Dict[DepKey, str] = {
    DepKey.WINGET: "Winget verfügbar",
    DepKey.DESKTOP_APP_INSTALLER: "App Installer / Store Backend",
    DepKey.POWERSHELL: "PowerShell verfügbar",
}


# =============================================================================
# Dependency Checks (mit Versionsprüfung)
# =============================================================================

MIN_WINGET_VERSION = (1, 12, 0)  # aktuell ~1.20.x verfügbar


class WingetState(Enum):
    MISSING = "missing"
    OUTDATED = "outdated"
    OK = "ok"


def _parse_version(text: str):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def get_winget_state() -> tuple[WingetState, str | None]:
    try:
        result = _run_silent(["winget", "--version"], timeout=5)
    except Exception:
        return WingetState.MISSING, None

    if result.returncode != 0:
        return WingetState.MISSING, None

    txt = (result.stdout + result.stderr).strip()
    ver_tuple = _parse_version(txt)
    ver_str = ".".join(str(x) for x in ver_tuple) if ver_tuple else (txt or None)

    if ver_tuple is None:
        # Version nicht parsebar → wir gehen von "OK, aber unbekannte Version" aus
        return WingetState.OK, ver_str

    if ver_tuple < MIN_WINGET_VERSION:
        return WingetState.OUTDATED, ver_str

    return WingetState.OK, ver_str


def has_msstore_source() -> bool:
    try:
        result = _run_silent(["winget", "source", "list"], timeout=5)
        txt = (result.stdout or "") + (result.stderr or "")
        return "msstore" in txt.lower()
    except Exception:
        return False

def get_appinstaller_version() -> str | None:
    try:
        result = _run_silent(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-Command",
                "(Get-AppxPackage -Name Microsoft.DesktopAppInstaller | "
                "Select-Object -First 1 -ExpandProperty Version | "
                "ForEach-Object { $_.ToString() })",
            ],
            timeout=8,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    txt = (result.stdout or "").strip()
    return txt or None


def is_powershell_available() -> bool:
    cmds = ["powershell", "pwsh"]
    for cmd in cmds:
        try:
            result = _run_silent(
                [cmd, "-NoLogo", "-NoProfile", "-Command", "Write-Output 'ok'"],
                timeout=5,
            )
            if result.returncode == 0 and "ok" in (result.stdout or ""):
                return True
        except Exception:
            continue
    return False


# =============================================================================
# PackageRow Widget
# =============================================================================

class PackageRow(ctk.CTkFrame):
    """Kompakte Zeile: Checkbox | Name | Description."""

    def __init__(
        self,
        master,
        key: str,
        var: tk.BooleanVar,
        on_toggle,
        width: int = ROW_WIDTH,
        height: int = ROW_HEIGHT,
        corner_radius: int = 14,
    ):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=corner_radius,
            width=width,
            height=height,
        )

        # Frame nicht anhand des Inhalts vergrößern/verkleinern
        self.grid_propagate(False)

        self.key = key
        self.var = var
        self.on_toggle = on_toggle

        self.configure(border_width=1, border_color=BORDER_CARD)
        self.grid_columnconfigure(1, weight=1)

        pkg = PACKAGES[key]

        self.cb = ctk.CTkCheckBox(
            self,
            text="",
            variable=self.var,
            width=18,
            command=self._handle_toggle,
        )
        self.cb.grid(row=0, column=0, padx=(10, 8), pady=10, sticky="nw")

        self.title = ctk.CTkLabel(
            self,
            text=pkg.display_name,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w",
        )
        self.title.grid(row=0, column=1, sticky="nw", padx=(0, 10), pady=(8, 0))

        # Wrap auf feste Breite, damit Text nicht alles auseinanderzieht
        self.sub = ctk.CTkLabel(
            self,
            text=pkg.description,
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
            anchor="nw",
            justify="left",
            wraplength=width - 60,
        )
        self.sub.grid(row=1, column=1, sticky="nw", padx=(0, 10), pady=(0, 4))

        for w in (self, self.title, self.sub):
            w.bind("<Button-1>", self._on_click)

        self._update_style(self.var.get())

    def _on_click(self, _e=None):
        self.var.set(not self.var.get())
        self._handle_toggle()

    def _handle_toggle(self):
        self._update_style(self.var.get())
        if callable(self.on_toggle):
            self.on_toggle()

    def _update_style(self, selected: bool):
        try:
            if selected:
                self.configure(fg_color=BG_CARD_SELECTED, border_color=BORDER_CARD_SELECTED)
            else:
                self.configure(fg_color=BG_CARD, border_color=BORDER_CARD)
        except tk.TclError:
            pass

    def refresh(self):
        self._update_style(self.var.get())

    def set_width(self, width: int):
        """Passt Breite + Wraplength dynamisch an (Fix für initialen Breiten-Glitch)."""
        try:
            self.configure(width=width)
            self.sub.configure(wraplength=max(180, width - 60))
        except tk.TclError:
            pass


# =============================================================================
# Main App
# =============================================================================

class WingetInstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(1120, 620)
        self.resizable(False, False)
        self.configure(fg_color=BG_WINDOW)

        self._installing = False
        self._tk_icon_ref = None

        self.search_var = tk.StringVar(value="")
        self.category_var = tk.StringVar(value="Alle")

        self._winget_state: WingetState | None = None
        self._winget_version: str | None = None
        self._appinstaller_version: str | None = None

        self.package_vars: Dict[str, tk.BooleanVar] = {
            k: tk.BooleanVar(value=False) for k in PACKAGES
        }

        self.dep_labels: Dict[DepKey, ctk.CTkLabel] = {}
        self.rows: Dict[str, PackageRow] = {}
        self.cat_buttons: List[ctk.CTkButton] = []

        # Debounce-Handle für Resize-Events der Scroll-Canvas
        self._list_resize_after_id: str | None = None

        self._set_window_icon()
        self._build_layout()
        self._bind_hotkeys()

        # wichtig: HIER einmal initial rendern + danach Breite nochmal sauber ziehen
        self.after(0, self._initial_render)
        self.after(0, self._update_selected_count)

        # Dependencies separat prüfen
        self._check_dependencies_async()

    def _get_row_width(self) -> int:
        """Ermittelt die sinnvolle Breite für die App-Zeilen.

        Wichtig: NICHT mit einem festen Minimum arbeiten.
        Ein zu großes Minimum ist genau der Grund, warum die Zeilen beim ersten Start
        über den Rand hinauslaufen (Canvas-Breite ist dann kurzzeitig kleiner).
        """
        try:
            canvas = getattr(self.list_scroll, "_parent_canvas", None)
            if canvas is not None:
                w = int(canvas.winfo_width() or 0)
                if w > 50:
                    # Platz für Scrollbar + Innen-Padding abziehen
                    return max(1, w - 28)
        except Exception:
            pass
        # Fallback (wird kurz nach dem Start per Resize-Event korrigiert)
        return ROW_WIDTH

    def _on_list_canvas_configure(self, _event=None):
        """Wird bei Größenänderung der Scroll-Canvas getriggert.
        Wir debouncen und passen dann die bestehenden Rows an.
        """
        if self._list_resize_after_id is not None:
            try:
                self.after_cancel(self._list_resize_after_id)
            except Exception:
                pass
        self._list_resize_after_id = self.after(50, self._resize_rows_to_canvas)

    def _resize_rows_to_canvas(self):
        """Passt bereits gerenderte Rows an die aktuelle Canvas-Breite an."""
        self._list_resize_after_id = None

        if not self.rows:
            return

        new_w = self._get_row_width()
        if not new_w:
            return

        for r in self.rows.values():
            r.set_width(new_w)

    def _initial_render(self):
        """Erstes Rendering + Workaround fürs Breiten-Glitch."""

        # Layout / DPI vorberechnen lassen
        self.update_idletasks()

        # einmal sauber rendern, indem wir das machen,
        # was du sonst manuell tust: Kategorie kurz wechseln
        cats = sorted({p.category for p in PACKAGES.values()})

        if cats:
            first_cat = cats[0]        # z.B. "Browser"
            # kurz auf erste Kategorie…
            self._set_category(first_cat)
            # …und wieder zurück auf "Alle"
            self._set_category("Alle")
        else:
            # Fallback, falls nur "Alle" existiert
            self._set_category("Alle")

        self._update_selected_count()

        # Nach dem ersten Render nochmal Breite anhand der realen Canvas-Größe setzen
        self.after(80, self._resize_rows_to_canvas)

    # -------------------------------------------------------------------------
    # Window / Links
    # -------------------------------------------------------------------------

    def _open_url(self, url: str):
        try:
            webbrowser.open(url, new=2)
        except Exception as exc:
            messagebox.showinfo("Info", f"Link konnte nicht geöffnet werden:\n{exc}")

    def _set_window_icon(self):
        if not ICON_PATH.exists():
            return
        try:
            self.iconbitmap(str(ICON_PATH))
            return
        except Exception:
            pass
        try:
            img = tk.PhotoImage(file=str(ICON_PATH))
            self.iconphoto(True, img)
            self._tk_icon_ref = img
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Layout
    # -------------------------------------------------------------------------

    def _build_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_WINDOW)
        content.grid(row=0, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=0, minsize=190)
        content.grid_columnconfigure(1, weight=1)
        content.grid_columnconfigure(2, weight=0, minsize=320)

        # Left: Kategorien
        left = ctk.CTkFrame(content, fg_color=BG_WINDOW)
        left.grid(row=0, column=0, sticky="ns", padx=(16, 8), pady=10)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left,
            text="Kategorien",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(4, 6))

        cats = ["Alle"] + sorted({p.category for p in PACKAGES.values()})

        for i, cat in enumerate(cats, start=1):
            btn = ctk.CTkButton(
                left,
                text=cat,
                width=170,
                height=34,
                fg_color=BG_CARD if cat != "Alle" else BG_CARD_SELECTED,
                text_color="#111827",
                hover_color="#E5E7EB",
                border_width=1,
                border_color=BORDER_CARD if cat != "Alle" else BORDER_CARD_SELECTED,
                command=lambda c=cat: self._set_category(c),
            )
            btn.grid(row=i, column=0, sticky="ew", padx=4, pady=4)
            self.cat_buttons.append(btn)

        # Middle
        mid = ctk.CTkFrame(content, fg_color=BG_WINDOW, width=MID_WIDTH)
        mid.grid(row=0, column=1, sticky="nsew", padx=(8, 8), pady=10)
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_rowconfigure(2, weight=1)
        mid.grid_propagate(False)  # 🔥 wichtig: NICHT anhand Inhalt resizen

        ctk.CTkLabel(
            mid,
            text="Programme auswählen",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(4, 0))

        search_row = ctk.CTkFrame(mid, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", padx=4, pady=(6, 8))
        search_row.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_row,
            textvariable=self.search_var,
            placeholder_text="Suchen (z.B. 'Office', 'Firefox', 'PDF') …",
            height=36,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.selected_count_lbl = ctk.CTkLabel(
            search_row,
            text="Ausgewählt: 0",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=11),
        )
        self.selected_count_lbl.grid(row=0, column=1, sticky="e")

        self.search_var.trace_add("write", lambda *_: self._render_package_list())

        # Fester Wrapper (definiert die maximale Breite!)
        list_wrapper = ctk.CTkFrame(
            mid,
            width=MID_WIDTH,
            fg_color=BG_WINDOW,
        )
        list_wrapper.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 6))
        list_wrapper.grid_propagate(False)
        list_wrapper.grid_columnconfigure(0, weight=1)
        list_wrapper.grid_rowconfigure(0, weight=1)

        # ScrollableFrame lebt IM Wrapper
        self.list_scroll = ctk.CTkScrollableFrame(
            list_wrapper,
            fg_color=BG_WINDOW,
            corner_radius=0,
        )
        self.list_scroll.grid(row=0, column=0, sticky="nsew")
        self.list_scroll.grid_columnconfigure(0, weight=1)

        # 🔥 Fix: Wenn die Scroll-Canvas ihre echte Breite bekommt (nach dem ersten Draw),
        # passen wir die bereits gerenderten Zeilen an. Das verhindert das „zu lange Balken“-Problem.
        canvas = getattr(self.list_scroll, "_parent_canvas", None)
        if canvas is not None:
            canvas.bind("<Configure>", self._on_list_canvas_configure)

        # Right
        right = ctk.CTkFrame(content, fg_color=BG_WINDOW)
        right.grid(row=0, column=2, sticky="n", padx=(8, 16), pady=10)
        right.grid_columnconfigure(0, weight=1)

        logo_box = ctk.CTkFrame(
            right,
            fg_color=BG_RIGHT_PANEL,
            corner_radius=18,
            width=300,
            height=160,
            border_width=1,
            border_color=BORDER_CARD,
        )
        logo_box.grid(row=0, column=0, sticky="n", padx=4, pady=(4, 6))
        logo_box.grid_propagate(False)

        self.logo_label = ctk.CTkLabel(logo_box, text="")
        self.logo_label.place(relx=0.5, rely=0.5, anchor="center")
        self.logo_label.configure(cursor="hand2")
        self.logo_label.bind("<Button-1>", lambda e: self._open_url(LOGO_URL))
        self._load_logo()

        ctk.CTkLabel(
            right,
            text="Voraussetzungen",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=1, column=0, sticky="w", padx=6, pady=(6, 2))

        self.dep_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.dep_frame.grid(row=2, column=0, sticky="w", padx=6, pady=(0, 6))
        self._build_dep_labels()

        self.hint_lbl = ctk.CTkLabel(
            right,
            text="Hinweis:\nInstallation wird später\nüber PowerShell/Winget\nimplementiert.",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
            justify="left",
        )
        self.hint_lbl.grid(row=3, column=0, sticky="w", padx=6, pady=(6, 0))

        self.btn_fix_winget = ctk.CTkButton(
            right,
            text="Winget / App Installer aktualisieren",
            width=260,
            command=self._on_fix_winget,
        )
        self.btn_fix_winget.grid(row=4, column=0, sticky="ew", padx=6, pady=(10, 0))
        self.btn_fix_winget.configure(state="disabled")

        # Alle per winget verwaltbaren Programme aktualisieren
        self.btn_upgrade_all = ctk.CTkButton(
            right,
            text="Installierte Programme aktualisieren",
            width=260,
            command=self._on_upgrade_all,
        )
        self.btn_upgrade_all.grid(row=5, column=0, sticky="ew", padx=6, pady=(6, 0))
        self.btn_upgrade_all.configure(state="disabled")

        # Hinweis, dass nicht wirklich *alle* Programme erwischt werden
        self.upgrade_hint_lbl = ctk.CTkLabel(
            right,
            text=(
                "Hinweis:\n"
                "Es werden nur Programme aktualisiert,\n"
                "die über winget verwaltet werden können.\n"
                "Manuell installierte Software oder manche\n"
                "Store-Apps bleiben unverändert."
            ),
            font=ctk.CTkFont(size=9),
            text_color=TEXT_MUTED,
            justify="left",
        )
        self.upgrade_hint_lbl.grid(row=6, column=0, sticky="w", padx=6, pady=(4, 0))

        # Bottom bar
        bottom = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_WINDOW)
        bottom.grid(row=1, column=0, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=0)
        bottom.grid_columnconfigure(2, weight=0)
        bottom.grid_columnconfigure(3, weight=0)
        bottom.grid_columnconfigure(4, weight=0)

        self.progress = ctk.CTkProgressBar(
            bottom, progress_color=ACCENT, fg_color="#E5E7EB", height=10, corner_radius=999
        )
        self.progress.grid(row=0, column=0, columnspan=5, sticky="ew", padx=16, pady=(8, 4))
        self.progress.set(0.0)

        self.status_lbl = ctk.CTkLabel(bottom, text="Bereit.", text_color=TEXT_MUTED)
        self.status_lbl.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        self.footer_brand = ctk.CTkLabel(
            bottom,
            text=BRAND_TEXT,
            font=ctk.CTkFont(size=10),
            text_color=TEXT_MUTED,
            cursor="hand2",
        )
        self.footer_brand.grid(row=1, column=1, sticky="e", padx=(0, 12), pady=(0, 8))
        self.footer_brand.bind("<Button-1>", lambda e: self._open_url(BRAND_URL))
        self.footer_brand.bind("<Enter>", lambda e: self.footer_brand.configure(text_color=ACCENT))
        self.footer_brand.bind("<Leave>", lambda e: self.footer_brand.configure(text_color=TEXT_MUTED))

        self.btn_readme = ctk.CTkButton(bottom, text="Readme", width=100, command=lambda: self._open_url(README_URL))
        self.btn_readme.grid(row=1, column=2, padx=(0, 6), pady=(0, 8))

        self.btn_install = ctk.CTkButton(bottom, text="Installieren", width=110, command=self._on_install_clicked)
        self.btn_install.grid(row=1, column=3, padx=6, pady=(0, 8))

        self.btn_cancel = ctk.CTkButton(
            bottom,
            text="Abbrechen",
            width=110,
            fg_color=BG_CARD,
            text_color="#111827",
            hover_color="#E5E7EB",
            border_width=1,
            border_color="#D1D5DB",
            command=self.destroy,
        )
        self.btn_cancel.grid(row=1, column=4, padx=(6, 16), pady=(0, 8))

    def _load_logo(self):
        if Image is None:
            self.logo_label.configure(text="(Pillow fehlt)\n`pip install pillow`", text_color=TEXT_MUTED, justify="center")
            return
        if not LOGO_PATH.exists():
            self.logo_label.configure(text="CLS-Logo\n(logo.png nicht gefunden)", text_color=TEXT_MUTED, justify="center")
            return

        img = Image.open(LOGO_PATH)
        max_width, max_height = 260, 120
        img_ratio = img.width / img.height
        box_ratio = max_width / max_height
        if img_ratio > box_ratio:
            new_w = max_width
            new_h = int(max_width / img_ratio)
        else:
            new_h = max_height
            new_w = int(max_height * img_ratio)

        img = img.resize((new_w, new_h), Image.LANCZOS)
        self._logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(new_w, new_h))
        self.logo_label.configure(image=self._logo_img, text="")

    # -------------------------------------------------------------------------
    # Categories + Search + Rendering
    # -------------------------------------------------------------------------

    def _set_category(self, cat: str):
        self.category_var.set(cat)
        for b in self.cat_buttons:
            if b.cget("text") == cat:
                b.configure(fg_color=BG_CARD_SELECTED, border_color=BORDER_CARD_SELECTED)
            else:
                b.configure(fg_color=BG_CARD, border_color=BORDER_CARD)
        self._render_package_list()

    def _filtered_keys(self) -> List[str]:
        q = (self.search_var.get() or "").strip().lower()
        cat = self.category_var.get()

        keys = list(PACKAGES.keys())

        if cat and cat != "Alle":
            keys = [k for k in keys if PACKAGES[k].category == cat]

        if q:
            def match(k: str) -> bool:
                p = PACKAGES[k]
                hay = f"{p.display_name} {p.description} {p.id} {p.category}".lower()
                return q in hay
            keys = [k for k in keys if match(k)]

        return sorted_keys_for_render(keys)

    def _render_package_list(self):
        # vorhandene Widgets entfernen
        for child in self.list_scroll.winfo_children():
            child.destroy()
        self.rows.clear()

        keys = self._filtered_keys()

        # aktuelle Breite der Liste holen
        row_width = self._get_row_width()

        row = 0
        for k in keys:
            r = PackageRow(
                self.list_scroll,
                key=k,
                var=self.package_vars[k],
                on_toggle=self._update_selected_count,
                width=row_width,
                height=ROW_HEIGHT,
            )
            r.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
            self.rows[k] = r
            row += 1

        self._update_selected_count()

    def _update_selected_count(self):
        cnt = sum(1 for v in self.package_vars.values() if v.get())
        self.selected_count_lbl.configure(text=f"Ausgewählt: {cnt}")

    # -------------------------------------------------------------------------
    # Dependencies
    # -------------------------------------------------------------------------

    def _build_dep_labels(self):
        for row, dep in enumerate(DepKey):
            icon, color = UI_STATUS_STYLE[UiState.PENDING]
            lbl = ctk.CTkLabel(
                self.dep_frame,
                text=f"{icon}  {DEP_LABELS[dep]}",
                font=ctk.CTkFont(size=11),
                text_color=color,
                justify="left",
            )
            lbl.grid(row=row, column=0, sticky="w", pady=1)
            self.dep_labels[dep] = lbl

    def _set_dep_state(self, dep: DepKey, state: UiState):
        lbl = self.dep_labels.get(dep)
        if not lbl:
            return
        icon, color = UI_STATUS_STYLE[state]
        base_text = DEP_LABELS[dep]

        # Für App Installer / Store Backend auch die App-Installer-Version anzeigen, falls bekannt
        if dep == DepKey.DESKTOP_APP_INSTALLER:
            ver = getattr(self, "_appinstaller_version", None)
            if ver:
                base_text = f"{base_text} (v{ver})"

        lbl.configure(text=f"{icon}  {base_text}", text_color=color)

    def _update_winget_label(self, state: WingetState, version: str | None):
        lbl = self.dep_labels.get(DepKey.WINGET)
        if not lbl:
            return

        if state == WingetState.OK:
            ui_state = UiState.OK
            text = "Winget verfügbar"
        elif state == WingetState.OUTDATED:
            ui_state = UiState.FAIL
            text = "Winget veraltet"
        else:
            ui_state = UiState.FAIL
            text = "Winget nicht verfügbar"

        if version:
            text += f" (v{version})"

        icon, color = UI_STATUS_STYLE[ui_state]
        lbl.configure(text=f"{icon}  {text}", text_color=color)

    def _set_fix_button_state(self, enabled: bool):
        if hasattr(self, "btn_fix_winget"):
            self.btn_fix_winget.configure(state="normal" if enabled else "disabled")

    def _set_upgrade_all_state(self, enabled: bool):
        if hasattr(self, "btn_upgrade_all"):
            self.btn_upgrade_all.configure(state="normal" if enabled else "disabled")


    def _check_dependencies_async(self):
        threading.Thread(target=self._check_dependencies_worker, daemon=True).start()


    def _check_dependencies_worker(self):
        # 1) Winget-Status (CLI)
        state, ver = get_winget_state()
        self._winget_state = state
        self._winget_version = ver
        winget_ok = state == WingetState.OK

        # 2) PowerShell
        ps_ok = is_powershell_available()

        # 3) App Installer (Store / Systemkomponente)
        app_ver = get_appinstaller_version()
        self._appinstaller_version = app_ver
        app_ok = app_ver is not None

        # UI-Updates ins Tk-Thread schieben
        self.after(0, self._update_winget_label, state, ver)
        self.after(
            0,
            self._set_dep_state,
            DepKey.POWERSHELL,
            UiState.OK if ps_ok else UiState.FAIL,
        )

        # App Installer / Store Backend
        self.after(
            0,
            self._set_dep_state,
            DepKey.DESKTOP_APP_INSTALLER,
            UiState.OK if app_ok else UiState.FAIL,
        )

        # Fix-Button, wenn Winget fehlt/veraltet ODER App Installer fehlt
        need_fix = (state != WingetState.OK) or (not app_ok)
        self.after(0, self._set_fix_button_state, need_fix)

        can_upgrade = state == WingetState.OK
        self.after(0, self._set_upgrade_all_state, can_upgrade)


    def _on_fix_winget(self):
        """Winget / App Installer + Abhängigkeiten per Backend-Script fixen/aktualisieren."""
        if self._installing:
            return

        # Prüfen, ob das Script überhaupt existiert
        if not WINGET_SETUP_PS.exists():
            messagebox.showerror(
                "Fehler",
                f"Winget-Installscript nicht gefunden:\n{WINGET_SETUP_PS}",
            )
            return

        # Buttons sperren
        self.btn_fix_winget.configure(state="disabled")
        self.btn_install.configure(state="disabled")
        self.btn_readme.configure(state="disabled")

        # Visuelles Feedback
        self._set_dep_state(DepKey.WINGET, UiState.RUNNING)
        self._set_dep_state(DepKey.DESKTOP_APP_INSTALLER, UiState.RUNNING)
        self.status_lbl.configure(text="Winget / App Installer wird überprüft …")
        self.progress.set(0.0)

        def worker():
            try:
                # kleiner Fortschrittsbump
                self.after(0, self.progress.set, 0.25)

                # PowerShell-Setup ausführen
                run_winget_ps_setup()

                # Wenn wir hier sind: Exitcode == 0 → Script OK durchgelaufen
                def on_success():
                    self.progress.set(1.0)
                    self.status_lbl.configure(
                        text="Winget Installation / Aktualisierung beendet."
                    )
                    # Dependencies / Versionsanzeige rechts neu einlesen
                    self._check_dependencies_async()

                self.after(0, on_success)

            except Exception as exc:
                # Fehler aus run_winget_ps_setup → Text + Popup
                def on_error():
                    self.progress.set(1.0)
                    self.status_lbl.configure(
                        text="Fehler beim Winget / App Installer Setup."
                    )
                    self._set_dep_state(DepKey.WINGET, UiState.FAIL)
                    self._set_dep_state(DepKey.DESKTOP_APP_INSTALLER, UiState.FAIL)
                    messagebox.showerror(
                        "Fehler",
                        f"Fehler bei der Installation von Winget / App Installer:\n{exc}",
                    )

                self.after(0, on_error)

            finally:
                def re_enable():
                    self.btn_fix_winget.configure(state="normal")
                    self.btn_install.configure(state="normal")
                    self.btn_readme.configure(state="normal")

                self.after(0, re_enable)

        threading.Thread(target=worker, daemon=True).start()

    def _on_upgrade_all(self):
        if self._installing:
            return

        if not messagebox.askyesno(
            "Programme aktualisieren",
            "Es werden alle Programme aktualisiert,\n"
            "die über winget verwaltet werden können.\n\n"
            "Fortfahren?"
        ):
            return

        self._installing = True
        self.btn_install.configure(state="disabled")
        self.btn_fix_winget.configure(state="disabled")
        self.btn_upgrade_all.configure(state="disabled")
        self.btn_readme.configure(state="disabled")
        self.progress.set(0.0)
        self.status_lbl.configure(text="Aktualisiere Programme (winget) …")

        def worker():
            try:
                cmd = [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-File", str(WINGET_SETUP_PS),
                    "-UpgradeAll",
                ]

                stdout_lines: list[str] = []

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                assert proc.stdout is not None
                for raw in proc.stdout:
                    line = raw.rstrip("\r\n")
                    if not line:
                        continue

                    stdout_lines.append(line)

                    # Letzte Zeile im Status anzeigen
                    self.after(
                        0,
                        lambda l=line: self.status_lbl.configure(text=l[:140]),
                    )

                rc = proc.wait()

                # ---- Summary aus der PS-Ausgabe parsen ----
                updated: list[tuple[str, str, str, str]] = []
                not_updated: list[tuple[str, str, str, str]] = []
                inside = False
                had_none = False

                for line in stdout_lines:
                    if line == "UPGRADE_SUMMARY_BEGIN":
                        inside = True
                        continue
                    if line == "UPGRADE_SUMMARY_END":
                        inside = False
                        continue
                    if not inside:
                        continue

                    if line == "UPGRADE_NONE":
                        had_none = True
                        continue

                    if line.startswith("UPDATED_APP: "):
                        payload = line[len("UPDATED_APP: "):]
                        parts = [p.strip() for p in payload.split("|")]
                        name, appid, cur, avail = (parts + ["", "", "", ""])[:4]
                        updated.append((name, appid, cur, avail))
                    elif line.startswith("NOT_UPDATED_APP: "):
                        payload = line[len("NOT_UPDATED_APP: "):]
                        parts = [p.strip() for p in payload.split("|")]
                        name, appid, cur, avail = (parts + ["", "", "", ""])[:4]
                        not_updated.append((name, appid, cur, avail))

                def finish():
                    self.progress.set(1.0)

                    # Zählwerte aus den Listen
                    total_updated = len(updated)
                    total_not_updated = len(not_updated)
                    total = total_updated + total_not_updated

                    # Fall: keine aktualisierbaren Programme
                    if had_none and total == 0:
                        self.status_lbl.configure(
                            text="Fertig – keine aktualisierbaren Programme gefunden."
                        )
                        return

                    # Statuszeile mit (X/Y) Programme aktualisiert
                    if total > 0:
                        if rc == 0:
                            prefix = "Fertig ✅"
                        else:
                            prefix = "Fertig ⚠️"
                        self.status_lbl.configure(
                            text=f"{prefix} ({total_updated}/{total}) Programme aktualisiert."
                        )
                    else:
                        # Fallback, falls aus irgendeinem Grund keine Summary da ist
                        if rc == 0:
                            self.status_lbl.configure(
                                text="Fertig ✅ Programme wurden aktualisiert."
                            )
                        else:
                            self.status_lbl.configure(
                                text=f"Fertig ⚠️ ExitCode {rc} (nicht alle Updates möglich)"
                            )

                    # Popup-Zusammenfassung bauen (falls Marker vorhanden)
                    if total == 0:
                        return  # nichts zum Anzeigen

                    lines: list[str] = []

                    if updated:
                        lines.append("Aktualisierte Programme:\n")
                        for name, appid, cur, avail in updated:
                            if cur and avail:
                                lines.append(f"• {name} ({appid}) {cur} → {avail}")
                            else:
                                lines.append(f"• {name} ({appid})")
                        lines.append("")

                    if not_updated:
                        lines.append("Nicht aktualisiert / weiterhin als Update verfügbar:\n")
                        for name, appid, cur, avail in not_updated:
                            if cur and avail:
                                lines.append(f"• {name} ({appid}) {cur} → {avail}")
                            else:
                                lines.append(f"• {name} ({appid})")

                    messagebox.showinfo(
                        "Winget-Upgrade – Zusammenfassung",
                        "\n".join(lines),
                    )

                self.after(0, finish)

            except Exception as exc:
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Fehler",
                        f"Fehler beim Aktualisieren:\n{exc}",
                    ),
                )
            finally:
                def re_enable():
                    self._installing = False
                    self.btn_install.configure(state="normal")
                    self.btn_readme.configure(state="normal")
                    # Fix-/Upgrade-Button-Zustand neu prüfen
                    self._check_dependencies_async()

                self.after(0, re_enable)

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------------------------------------------------------
    # Install Flow
    # -------------------------------------------------------------------------

    def _on_install_clicked(self):
        if self._installing:
            return

        selected = [k for k, v in self.package_vars.items() if v.get()]
        if not selected:
            messagebox.showinfo("Hinweis", "Bitte wähle mindestens ein Programm aus.")
            return

        self._installing = True
        self.btn_install.configure(state="disabled")
        self.btn_readme.configure(state="disabled")
        self.progress.set(0.0)
        self.status_lbl.configure(text="Installation wird vorbereitet …")

        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        try:
            selected_keys = [k for k, v in self.package_vars.items() if v.get()]
            if not selected_keys:
                self.after(0, self._finish_success, 0, 0, 0)
                return

            app_ids = [PACKAGES[k].id for k in selected_keys]
            total = len(app_ids)

            # Maps für schöne Namen im Status
            id_to_name = {p.id: p.display_name for p in PACKAGES.values()}

            state = {"done": 0}

            def on_event(ev):
                kind = ev[0]

                if kind == "start":
                    cur_id = ev[1]
                    cur_name = id_to_name.get(cur_id, cur_id)
                    # Fortschritt = bereits fertig / total
                    done = state["done"]
                    prog = done / total if total else 0.0
                    self.after(0, self.progress.set, prog)
                    self.after(0, lambda: self.status_lbl.configure(
                        text=f"[{done}/{total}] Installiere: {cur_name}"
                    ))

                elif kind == "ok":
                    ok_id = ev[1]
                    state["done"] += 1
                    done = state["done"]
                    prog = done / total if total else 1.0
                    self.after(0, self.progress.set, prog)
                    self.after(0, lambda: self.status_lbl.configure(
                        text=f"{done}/{total} Programme installiert …"
                    ))

            # Startanzeige
            self.after(0, self.progress.set, 0.0)
            self.after(0, lambda: self.status_lbl.configure(text=f"Installiere {total} Programme …"))

            installed_ids, failed_ids = run_winget_ps_install(app_ids, on_event=on_event)

            ok = len(installed_ids)
            fail = len(failed_ids)

            self.after(0, self.progress.set, 1.0)

            # Fertig-Status + optional Warnung
            if fail > 0:
                # hübsche Liste
                pretty = []
                for fid in failed_ids:
                    pretty.append(f"• {id_to_name.get(fid, fid)}")
                msg = (
                    "Einige Programme konnten nicht installiert werden:\n\n"
                    + "\n".join(pretty)
                    + "\n\nAlle anderen Programme wurden installiert."
                )
                self.after(0, lambda: messagebox.showwarning("Teilweise fertig", msg))
                self.after(0, self._finish_success, ok, fail, total)
            else:
                self.after(0, self._finish_success, ok, 0, total)

        except Exception as exc:
            self.after(0, self._finish_error, exc)


    def _finish_success(self, ok: int = 0, fail: int = 0, total: int = 0):
        self._installing = False
        self.btn_install.configure(state="normal")
        self.btn_readme.configure(state="normal")

        if total == 0:
            self.status_lbl.configure(text="Fertig ✅")
            return

        if fail > 0:
            self.status_lbl.configure(text=f"Fertig ⚠️  {ok}/{total} installiert, {fail} übersprungen")
        else:
            self.status_lbl.configure(text=f"Fertig ✅  {ok}/{total} installiert")

    def _finish_error(self, exc: Exception):
        self._installing = False
        self.btn_install.configure(state="normal")
        self.btn_readme.configure(state="normal")
        self.status_lbl.configure(text="Fehler bei der Installation.")
        messagebox.showerror("Fehler", f"Fehler bei der Installation:\n{exc}")

    # -------------------------------------------------------------------------
    # Hotkeys
    # -------------------------------------------------------------------------

    def _bind_hotkeys(self):
        self.bind_all("<KeyPress>", self._on_key_press)

    def _on_key_press(self, event: tk.Event):
        # CTRL+A → alles auswählen
        if event.state & 0x4 and event.keysym.lower() == "a":
            for key, v in self.package_vars.items():
                v.set(True)
            for row in self.rows.values():
                row.refresh()
            self._update_selected_count()
            return

        # CTRL+D → alles abwählen
        if event.state & 0x4 and event.keysym.lower() == "d":
            for key, v in self.package_vars.items():
                v.set(False)
            for row in self.rows.values():
                row.refresh()
            self._update_selected_count()
            return

        # ENTER → installieren
        if event.keysym in ("Return", "KP_Enter"):
            self._on_install_clicked()
            return


def main():
    app = WingetInstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()


<img width="1122" height="652" alt="image" src="https://github.com/user-attachments/assets/bbfa4f25-44ab-4bf0-932d-e310014223d4" />

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://badgen.net/github/license/SD-ITLab/Winget-Script)

# Winget Deploy UI by SD-ITLab

## ✨ Beschreibung

Der **Winget Deploy UI by SD-ITLab** ist ein grafisches Installations-Tool auf Basis von  
**Microsoft winget** (Windows Package Manager).

Das Projekt kombiniert:
- eine **moderne Python-GUI**
- ein **robustes PowerShell-Backend**
- und **winget** für die automatisierte Softwareinstallation

Ziel ist eine **vollständig unbeaufsichtigte, stabile und fehlertolerante Installation**
mehrerer Programme – ideal für Neuinstallationen, Service-Fälle oder Firmen-PCs.

---

## 🚀 Highlights & Funktionen

- ✅ Automatische **Erkennung & Einrichtung von winget**
- ✅ Mehrfachauswahl von Programmen
- ✅ **Serielle Installation** (Programm für Programm)
- ✅ **Fehlertolerant**: einzelne fehlerhafte Pakete werden übersprungen
- ✅ Saubere Statusanzeige:  
  `x/y installiert`, `z übersprungen`
- ✅ Keine Log-Spam-Fehlermeldungen
- ✅ Silent / unattended Installationen
- ✅ Moderne GUI mit Kategorien & Suche

---

## 🧩 Technischer Aufbau

- **Frontend:** Python (GUI)
- **Backend:** PowerShell (`winget-installscript.ps1`)
- **Installer:** Microsoft winget (DesktopAppInstaller)

Das PowerShell-Skript übernimmt:
- Setup & Reparatur von winget (inkl. Abhängigkeiten)
- Installation einzelner Pakete
- saubere Rückmeldung über erfolgreiche & fehlgeschlagene Installationen

Die GUI wertet diese Rückmeldungen aus und stellt sie übersichtlich dar.

---

## 📦 Unterstützte Software (Auszug)

### 🌍 Browser
- Google Chrome
- Mozilla Firefox
- Brave
- Opera
- Opera GX

### 📝 Office & Dokumente
- LibreOffice
- ONLYOFFICE
- Apache OpenOffice
- Notepad++
- PDF24 Creator
- Adobe Acrobat Reader

### 🎵 Media & Multimedia
- VLC Media Player
- Media Player Classic (MPC-HC)
- Spotify *(abhängig von winget/Store-Verfügbarkeit)*

### 💬 Kommunikation
- Mozilla Thunderbird
- Microsoft Teams
- WhatsApp Desktop
- Zoom

### 🛠 Tools & Utilities
- 7-Zip
- Everything
- Malwarebytes

### 🔐 Remote & Sicherheit
- TeamViewer
- AnyDesk
- RustDesk
- Avira / Avast / AVG (Store-Versionen)

### ☁️ Cloud
- Google Drive
- Microsoft OneDrive
- Dropbox

*(Die vollständige Liste ist im Code konfigurierbar.)*

---

## 🧠 Funktionslogik

- Programme werden **nacheinander** installiert
- Bereits installierte Software wird übersprungen (winget-intern)
- Schlägt ein Paket fehl:
  - Installation läuft weiter
  - Das Programm wird als **„übersprungen“** markiert
- Am Ende erhält der Nutzer eine **klare Zusammenfassung**:
  - `Fertig ✅ 5/5 installiert`
  - oder  
    `Fertig ⚠️ 4/5 installiert, 1 übersprungen`

---

## ▶️ Verwendung

### Variante 1: GUI (empfohlen)
1. Anwendung als **Administrator** starten
2. Programme auswählen
3. **„Winget / App installieren“** klicken
4. Fortschritt & Status live verfolgen

### Variante 2: PowerShell (direkt)
```powershell
powershell.exe -ExecutionPolicy Bypass -File winget-installscript.ps1 Google.Chrome Mozilla.Firefox VideoLAN.VLC
```

---

## ⚠️ Hinweise

- Einige Pakete (z. B. **Spotify**) können abhängig von:
  - Windows-Version
  - Store-Zustand
  - Region  
  fehlschlagen  
  → diese werden **automatisch übersprungen**
- Das Tool nimmt **keine Systemänderungen außerhalb der Installation** vor
- Für den Einsatz in Firmenumgebungen empfohlen

---

## 📜 Lizenz

Dieses Projekt steht unter der **MIT License**.  
Frei nutzbar, modifizierbar und erweiterbar.

---

## 🤝 Mitwirken

Pull Requests, Ideen und Verbesserungen sind willkommen.  
Für Feedback oder Support: **SD-ITLab**

---

© 2026 **SD-ITLab** – MIT licensed


---

# ENGLISH

# Winget Deploy UI by SD-ITLab

## ✨ Description

**Winget Deploy UI by SD-ITLab** is a graphical software deployment tool based on  
**Microsoft winget** (Windows Package Manager).

The project combines:
- a **modern Python-based GUI**
- a **robust PowerShell backend**
- and **winget** for automated software installation

The goal is a **fully unattended, stable and fault-tolerant installation** of multiple applications – ideal for fresh Windows installations, service cases, and enterprise environments.

---

## 🚀 Features & Highlights

- ✅ Automatic **detection, setup and repair of winget**
- ✅ Multiple application selection
- ✅ **Sequential installation** (one application at a time)
- ✅ **Fault-tolerant**: failed packages are skipped instead of aborting
- ✅ Clear status reporting:  
  `x/y installed`, `z skipped`
- ✅ No log spam in error dialogs
- ✅ Silent / unattended installations
- ✅ Modern UI with categories and search

---

## 🧩 Technical Overview

- **Frontend:** Python (GUI)
- **Backend:** PowerShell (`winget-installscript.ps1`)
- **Installer:** Microsoft winget (DesktopAppInstaller)

The PowerShell backend handles:
- winget setup and recovery (including dependencies)
- installation of individual packages
- clean result reporting (successful / failed installations)

The GUI evaluates these results and presents them in a user-friendly way.

---

## 📦 Supported Software (Excerpt)

### 🌍 Browsers
- Google Chrome
- Mozilla Firefox
- Brave
- Opera
- Opera GX

### 📝 Office & Documents
- LibreOffice
- ONLYOFFICE
- Apache OpenOffice
- Notepad++
- PDF24 Creator
- Adobe Acrobat Reader

### 🎵 Media & Multimedia
- VLC Media Player
- Media Player Classic (MPC-HC)
- Spotify *(availability depends on winget / Microsoft Store)*

### 💬 Communication
- Mozilla Thunderbird
- Microsoft Teams
- WhatsApp Desktop
- Zoom

### 🛠 Tools & Utilities
- 7-Zip
- Everything
- Malwarebytes

### 🔐 Remote & Security
- TeamViewer
- AnyDesk
- RustDesk
- Avira / Avast / AVG (Store versions)

### ☁️ Cloud & Storage
- Google Drive
- Microsoft OneDrive
- Dropbox

*(The full package list is configurable in the source code.)*

---

## 🧠 How It Works

- Applications are installed **sequentially**
- Already installed software is skipped automatically (handled by winget)
- If a package fails:
  - installation continues
  - the application is marked as **skipped**
- After completion, the user receives a **clear summary**:
  - `Finished ✅ 5/5 installed`
  - or  
    `Finished ⚠️ 4/5 installed, 1 skipped`

---

## ▶️ Usage

### Option 1: GUI (recommended)
1. Start the application **as administrator**
2. Select the desired applications
3. Click **"Winget / Install apps"**
4. Follow progress and status in real time

### Option 2: PowerShell (direct)
```powershell
powershell.exe -ExecutionPolicy Bypass -File winget-installscript.ps1 Google.Chrome Mozilla.Firefox VideoLAN.VLC
```

---

## ⚠️ Notes

- Some packages (e.g. **Spotify**) may fail depending on:
  - Windows version
  - Microsoft Store state
  - region / account configuration  
  → such packages are **automatically skipped**
- The tool does **not modify system settings outside of application installation**
- Recommended for professional and enterprise environments

---

## 📜 License

This project is licensed under the **MIT License**.  
Free to use, modify and extend.

---

## 🤝 Contributing

Pull requests, ideas and improvements are welcome.  
For feedback or support: **SD-ITLab**

---

© 2026 **SD-ITLab** – MIT licensed

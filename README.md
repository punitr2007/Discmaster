# 💿 DiscMaster — Optical Media Copy, Recovery & Processing Studio

<div align="center">

![DiscMaster Icon](assets/discmaster.png)

[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-3584e4.svg?style=flat-square&logo=linux&logoColor=white)](https://github.com/punitr2007/Discmaster)
[![Python](https://img.shields.io/badge/Python-3.8%2B-26a269.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![UI Style](https://img.shields.io/badge/Interface-Classic%20GTK%20%2F%20Brasero-e5a50a.svg?style=flat-square&logo=gnome&logoColor=white)](https://github.com/punitr2007/Discmaster)
[![Engine](https://img.shields.io/badge/Engine-Low--Level%20XA%20%2B%20FFmpeg-c01c28.svg?style=flat-square&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![Package](https://img.shields.io/badge/Packaging-Portable%20AppImage-f6f8fa.svg?style=flat-square)](dist/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)

**A native, classic GTK/Brasero-inspired desktop studio designed to rip, recover, transcode, stitch, and inspect legacy optical media (VCD, DVD, Audio CD, BIN/CUE, and raw CD-ROM XA dumps).**

[Features](#-features-at-a-glance) • [Why DiscMaster?](#-the-optical-preservation-challenge) • [Architecture](#-technical-architecture) • [Getting Started](#-getting-started) • [AppImage](#-portable-linux-appimage)

</div>

---

## 📖 The Optical Preservation Challenge

Optical media (CDs, VCDs, DVDs) produced in the 1990s and 2000s are rapidly degrading due to disc rot, surface oxidation, dye degradation, and physical wear. Millions of irreplaceable recordings—family weddings, rare regional films, nostalgic music albums, and historical discourses—are trapped on formats that modern operating systems struggle to read:

- **Video CDs (`MPEGAV/*.DAT`)**: Utilize non-standard Mode 2 Form 2 CD-ROM sectors with 2352-byte structures and desynced MPEG-1 pack timestamps that stutter, freeze, or fail entirely in modern media players.
- **DVD Video Discs (`VIDEO_TS/*.VOB`)**: Fragmented across multiple 1 GB chapter files, often causing audio-video sync drift when crudely merged.
- **Audio CDs (CDDA)**: Contain virtual `.cda` descriptor links that cannot be copied via normal file managers without low-level sector reading.
- **Raw Disc Images (`.bin`, `.cue`, `.toc`)**: Low-level forensic dumps require specialized track splitting and sector header demuxing to be usable.

**DiscMaster** provides an all-in-one, clean, native desktop application engineered specifically for disc preservation. It integrates low-level binary sector demuxing with high-efficiency FFmpeg stream pipelines to recover legacy media into pristine, modern MP4/MKV video and MP3/WAV/FLAC audio.

---

## ✨ Features at a Glance

### 1. 💿 Live Optical Disc Ripper
- **Video CD (VCD)**: Scans mounted disc structures (`MPEGAV`), parses `.DAT` tracks, and transcodes them into standard high-compatibility H.264/AAC MP4.
- **DVD Video**: Auto-detects DVD title chapter sequences (`VTS_01_1.VOB` ... `VTS_01_N.VOB`) and concatenates them into a single continuous MP4 movie without synchronization loss.
- **Audio CD (CDDA)**: Direct digital audio extraction to high-bitrate **MP3** (320 kbps) or lossless **PCM WAV** (1411 kbps).
- **Hardware Drive Detection**: Auto-detects optical drives across Linux (`/dev/sr*`, `/dev/cdrom`, `lsblk` ROM devices) and Windows (PowerShell/CIM & WMIC).

### 2. 🔄 Image & Stream Converter
- **Native BIN + CUE Splitter**: Directly parses `.cue` sheet index timing and slices monolithic `.bin` images into individual tracks natively.
- **TOC → CUE Sheet Converter**: Converts `cdrdao` `.toc` tables into standard `.cue` cue sheets.
- **Mode A (Raw CD-ROM XA Demuxing)**: Strips raw 2352-byte sector wrappers (Sync, Header, Subheader, EDC/ECC) from raw disc dumps to restore valid MPEG streams.
- **Mode B (Timestamp Repair)**: Re-encodes jittery or corrupt Presentation Timestamps (PTS/DTS) to fix out-of-sync audio and frame freezes.
- **Mode C (Multi-Stream Merge & Repair)**: Concurrently processes and joins multiple raw XA chunks into a single gapless MP4.

### 3. 🎬 Video Stitcher
- Interactive playlist manager to re-order, add, and combine sequential video chapters.
- **Lossless Stream Concatenation** (instant) or **Force Re-encode** (normalizes mismatched aspect ratios, resolutions, and framerates).

### 4. 🎵 Audio Extractor
- Extract soundtracks and audio streams from any video or audio container (`.mp4`, `.mpg`, `.dat`, `.avi`, `.mkv`, `.mov`, `.wav`).
- Supports output to **MP3**, **WAV**, **FLAC**, and **AAC**.
- **Batch Processing Mode**: Select an entire directory and batch-convert all contained media files concurrently.

### 5. 📁 File Library & Technical Inspector
- Embedded workspace directory browser with direct media player integration (`xdg-open` / default OS player).
- Real-time `ffprobe` technical inspector displaying stream configurations, video/audio codecs, exact resolutions, framerates, channel layouts, durations, and bitrates.

---

## 🎨 Clean GTK / Brasero Desktop Aesthetics

DiscMaster features a classic GTK / Adwaita interface reminiscent of classic GNOME disc burning tools like **Brasero** and **Sound Juicer**:
- **Neutral Adwaita Palette**: High readability with dark charcoal typography on neutral desktop tones.
- **Full Desktop Menu Bar**: Quick access to operations, hardware refresh, and dependency diagnostics.
- **Structured Group Frames**: Clean layout with clear visual hierarchy and primary action buttons.
- **Collapsible Activity Log**: Dedicated diagnostic terminal drawer that can be toggled on/off to keep the interface uncluttered.

---

## 🛠️ Technical Architecture

```
┌──────────────────────────────────────────────────────────┐
│              DiscMaster Classic GTK Desktop UI           │
│   (Adwaita Theme / Desktop Menus / Thread-Safe Queues)   │
└────────┬────────────────────────────────────────┬────────┘
         │                                        │
         ▼                                        ▼
┌────────────────────────┐              ┌────────────────────────┐
│  discmaster_engine.py  │              │    FFmpeg / FFprobe    │
├────────────────────────┤              ├────────────────────────┤
│ • CD-ROM XA Demuxer    │              │ • Stream Concatenation │
│ • 2352-byte Sector XA  │              │ • H.264/AAC Transcode  │
│ • CUE/BIN Track Slicer │              │ • CDDA Audio Rip       │
│ • TOC-to-CUE Converter │              │ • Media Stream Probe   │
│ • Hardware Drive Probe │              │ • PTS/DTS Resync       │
└────────────────────────┘              └────────────────────────┘
```

### Low-Level CD-ROM XA Mode 2 Form 2 Sector Parsing
A standard Video CD raw sector consists of **2352 bytes**:
```
+----------------+----------------+-------------------+----------------------+-------------+
| Sync (12 bytes)| Header (4 byte)| Subheader (8 byte)| User Data (2324 byte)| EDC (4 byte)|
+----------------+----------------+-------------------+----------------------+-------------+
```
`discmaster_engine` scans for the sync sequence (`00 FF FF FF FF FF FF FF FF FF FF 00`) and the MPEG Pack Start Code (`00 00 01 BA`), extracting clean 2324-byte payload chunks to reconstruct standard compliant video streams that any modern video player or editing suite can read without artifacting.

---

## 🚀 Getting Started

### Prerequisites

#### Linux (Arch / CachyOS / Ubuntu / Debian / Fedora)
- **Python 3.8+**
- **Tkinter**:
  - *Arch / CachyOS / Manjaro*: `sudo pacman -S tk`
  - *Ubuntu / Debian*: `sudo apt install python3-tk`
  - *Fedora*: `sudo dnf install python3-tkinter`
- **FFmpeg & FFprobe**:
  - *Arch / CachyOS*: `sudo pacman -S ffmpeg`
  - *Ubuntu / Debian*: `sudo apt install ffmpeg`

#### Windows
- **Python 3.8+** (with Tcl/Tk enabled in installer)
- **FFmpeg** added to your system `PATH` (e.g., via `winget install Gyan.FFmpeg` or `choco install ffmpeg`).

---

## 📥 Installation & Running

### Option 1: Standalone Linux AppImage (Portable)
Download the latest `DiscMaster-x86_64.AppImage` from the [`dist/`](dist/) folder:
```bash
chmod +x DiscMaster-x86_64.AppImage
./DiscMaster-x86_64.AppImage
```

### Option 2: Run via Launcher Script
```bash
git clone https://github.com/punitr2007/Discmaster.git
cd Discmaster
chmod +x run.sh
./run.sh
```

### Option 3: Python directly
```bash
python3 discmaster.py
```

### Option 4: On Windows
Double-click `discmaster_run.bat` or run:
```cmd
python discmaster.py
```

---

## 🖥️ Desktop Integration (Linux)

To integrate DiscMaster into your Linux application launcher (GNOME, KDE Plasma, XFCE, etc.):

```bash
cp discmaster.desktop ~/.local/share/applications/
```

---

## 📦 Building the AppImage

To build the standalone portable Linux AppImage from source:

```bash
./build_appimage.sh
```
The compiled AppImage will be placed in `dist/DiscMaster-x86_64.AppImage`.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📜 License

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for more information.

<div align="center">
  <sub>Preserve your memories. Don't let your nostalgic media fade away into disc rot.</sub>
</div>

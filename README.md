# 💿 DiscMaster — Optical Copy, Recovery & Processing Studio

<div align="center">

![DiscMaster Icon](assets/discmaster.png)

[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows-blue.svg?style=flat-square)](https://github.com/punitr2007/Discmaster)
[![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-yellow.svg?style=flat-square)](LICENSE)
[![Package](https://img.shields.io/badge/Packaging-AppImage%20%7C%20Native-orange.svg?style=flat-square)](dist/)
[![FFmpeg](https://img.shields.io/badge/Engine-FFmpeg%20%26%20FFprobe-red.svg?style=flat-square)](https://ffmpeg.org/)

**A comprehensive, dark-themed digital preservation suite designed to rip, restore, transcode, stitch, and inspect legacy optical media (VCD, DVD, Audio CD, BIN/CUE, and raw CD-ROM XA dumps).**

</div>

---

## 📖 Why DiscMaster?

Optical media (CDs, VCDs, DVDs) from the 1990s and 2000s are rapidly degrading due to disc rot, surface oxidation, and mechanical wear. Millions of irreplaceable memories—family weddings, rare regional recordings, legacy religious discourses, and nostalgic concerts—are trapped on formats that modern operating systems struggle to read:

- **VCDs (`MPEGAV/*.DAT`)** utilize non-standard Mode 2 Form 2 CD-ROM sectors with proprietary 2352-byte structures and desynced MPEG-1 pack timestamps that stutter, freeze, or fail completely in contemporary media players.
- **DVD Video discs (`VIDEO_TS/*.VOB`)** are fragmented across multiple 1GB chapters, often causing audio-video drift when crudely merged.
- **Audio CDs (CDDA)** contain virtual `.cda` headers that cannot be copied via normal file managers without low-level sector reading.
- **Raw Disc Images (`.bin`, `.cue`, `.toc`)** extracted with low-level recovery tools require intricate track splitting and header stripping.

**DiscMaster** solves these challenges in a single, intuitive, native desktop application. It integrates low-level binary sector demuxing with high-efficiency FFmpeg pipeline processing to recover and preserve old optical media seamlessly into pristine, modern MP4/MKV video and MP3/WAV/FLAC audio.

---

## ✨ Features at a Glance

### 1. 📀 Live Optical Disc Ripper
- **Video CD (VCD)**: Auto-scans `MPEGAV` and transcodes raw `.DAT` tracks into high-compatibility `.mp4`.
- **DVD Video**: Detects DVD structure, automatically identifies title chapter sequences (`VTS_01_1.VOB` ... `VTS_01_N.VOB`), and concatenates them seamlessly into a single H.264/AAC movie without synchronization loss.
- **Audio CD (CDDA)**: Direct digital audio extraction to high-quality **MP3** (320kbps) or lossless **PCM WAV** (1411kbps).
- **Drive Auto-Detection**: Automatically detects physical optical drives on Linux (`/dev/sr*`, `/dev/cdrom`, `lsblk` ROM devices) and Windows (PowerShell/CIM & WMIC) as well as active disc mount paths.

### 2. 🔄 Image & Stream Converter
- **Native BIN + CUE Splitter**: Directly parses `.cue` sheet index timing and splits monolithic `.bin` images into individual tracks without needing third-party mounting tools.
- **TOC → CUE Sheet Converter**: Converts `cdrdao` `.toc` tables into standard `.cue` cue sheets.
- **Mode A (Raw CD-ROM XA Demuxing)**: Strips raw 2352-byte sector wrappers (Sync, Header, Subheader, EDC/ECC) from raw disc dumps to restore valid MPEG streams.
- **Mode B (Timestamp Repair)**: Corrects jittery or corrupt Presentation Timestamps (PTS/DTS) to fix out-of-sync audio and frame freezes.
- **Mode C (Multi-Stream Merge & Repair)**: Concurrently processes and joins multiple raw XA chunks into a single gapless MP4.

### 3. 🎬 Video Stitcher
- Interactive visual drag-and-drop playlist order manager.
- Re-order, add, and combine sequential video chapters.
- Dual-mode stitching: **Lossless Stream Concatenation** (instant) or **Force Re-encode** (normalizes mismatched aspect ratios, resolutions, and framerates).

### 4. 🎵 Audio Extractor
- Extract audio tracks from any video or audio format (`.mp4`, `.mpg`, `.dat`, `.avi`, `.mkv`, `.mov`, `.wav`).
- Supports output to **MP3**, **WAV**, **FLAC**, and **AAC**.
- **Batch Processing Mode**: Select an entire directory and convert all contained media files concurrently.

### 5. 🔍 Media Inspector & File Browser
- Embedded workspace directory browser with quick file launcher.
- Real-time `ffprobe` technical inspector displaying stream configurations, video/audio codecs, exact resolutions, framerates, channel layouts, durations, and bitrates.

---

## 🛠️ Technical Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   DiscMaster Tkinter GUI                 │
│  (Modern Dark Theme #0f172a / Thread-Safe Event Queues)  │
└────────┬────────────────────────────────────────┬────────┘
         │                                        │
         ▼                                        ▼
┌────────────────────────┐              ┌────────────────────────┐
│  discmaster_engine.py  │              │    FFmpeg / FFprobe    │
├────────────────────────┤              ├────────────────────────┤
│ • CD-ROM XA Parser     │              │ • Stream Concatenation │
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
No installation required! Download the latest `DiscMaster-x86_64.AppImage` from the [`dist/`](dist/) folder or release page:
```bash
chmod +x DiscMaster-x86_64.AppImage
./DiscMaster-x86_64.AppImage
```

### Option 2: Run via Launcher Script
```bash
# Clone the repository
git clone https://github.com/punitr2007/Discmaster.git
cd Discmaster

# Make executable and launch
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

## 🖥️ Desktop Menu Integration (Linux)

To integrate DiscMaster into your Linux application launcher (GNOME, KDE Plasma, XFCE, etc.):

```bash
# Copy desktop file to your user application directory
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
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📜 License

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for more information.

---

<div align="center">
  <sub>Preserve your memories. Don't let your nostalgic media fade away into disc rot.</sub>
</div>

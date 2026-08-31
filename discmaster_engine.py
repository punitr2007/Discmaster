#!/usr/bin/env python3
"""
discmaster_engine.py
───────────────────
Core processing logic for DiscMaster. Wraps and extends existing VCD,
TOC/CUE, stitch, and audio scripts into a unified Python module.
"""

import os
import sys
import re
import time
import struct
import subprocess
import tempfile
import glob
import json

SECTOR_SIZE = 2352
MPEG_PACK   = b'\x00\x00\x01\xba'
CD_SYNC     = b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00'

# Default VCD re-encode settings
VIDEO_CODEC   = "mpeg1video"
VIDEO_BITRATE = "1150k"
VIDEO_QUALITY = "3"
AUDIO_CODEC   = "mp2"
AUDIO_BITRATE = "224k"
AUDIO_RATE    = "44100"

def get_ffmpeg_path():
    """Check if ffmpeg is in PATH or workspace. Return command string."""
    # Simple check
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "ffmpeg"
    except FileNotFoundError:
        return None

def get_ffprobe_path():
    """Check if ffprobe is in PATH. Return command string."""
    try:
        subprocess.run(["ffprobe", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "ffprobe"
    except FileNotFoundError:
        return None

def detect_optical_drives():
    """
    Detect local optical (CD/DVD) drives and mounted media on Linux and Windows.
    Returns a list of dicts with keys: 'device_id', 'drive_letter', 'name'.
    """
    drives = []
    if sys.platform != 'win32':
        # Check standard Linux optical block devices
        for d in ['/dev/sr0', '/dev/sr1', '/dev/cdrom', '/dev/dvd']:
            if os.path.exists(d) and not any(drv['device_id'] == d for drv in drives):
                drives.append({
                    'device_id': d,
                    'drive_letter': d,
                    'name': f'Optical Drive ({os.path.basename(d)})'
                })

        # Query lsblk for CD/DVD rom devices and mount points
        try:
            res = subprocess.run(['lsblk', '-J', '-o', 'NAME,TYPE,MOUNTPOINT,MODEL,LABEL'], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                for dev in data.get('blockdevices', []):
                    if dev.get('type') in ('rom', 'cd'):
                        dev_path = f"/dev/{dev['name']}"
                        mnt = dev.get('mountpoint')
                        model = dev.get('model') or 'CD/DVD Drive'
                        label = dev.get('label') or ''
                        name_str = f"{model} [{label}]" if label else model
                        target = mnt if mnt else dev_path
                        if not any(drv['drive_letter'] == target for drv in drives):
                            drives.append({
                                'device_id': dev_path,
                                'drive_letter': target,
                                'name': name_str
                            })
        except Exception:
            pass

        # Also inspect current user mounts in /run/media/$USER or /media
        user = os.environ.get('USER', '')
        search_dirs = [f"/run/media/{user}", f"/media/{user}", "/media"]
        for sdir in search_dirs:
            if os.path.isdir(sdir):
                for entry in os.listdir(sdir):
                    mp = os.path.join(sdir, entry)
                    if os.path.isdir(mp):
                        # Check if it looks like a VCD, DVD, or CD (MPEGAV, VIDEO_TS, etc.)
                        if any(os.path.exists(os.path.join(mp, x)) for x in ['MPEGAV', 'mpegav', 'VIDEO_TS', 'video_ts', 'EXT']):
                            if not any(drv['drive_letter'] == mp for drv in drives):
                                drives.append({
                                    'device_id': mp,
                                    'drive_letter': mp,
                                    'name': f'Mounted Disc ({entry})'
                                })
        return drives

    try:
        # Run PowerShell command to list CD/DVD drives
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_CDROMDrive | Select-Object DeviceID, Drive, Name | ConvertTo-Json"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            # PowerShell ConvertTo-Json returns a dict if single item, list if multiple
            if isinstance(data, dict):
                data = [data]
            for item in data:
                drives.append({
                    'device_id': item.get('DeviceID', ''),
                    'drive_letter': item.get('Drive', ''),
                    'name': item.get('Name', 'CD/DVD Drive')
                })
        else:
            raise Exception("PowerShell execution failed or returned empty")
    except Exception as e:
        # Fallback to wmic if PowerShell fails or is restricted
        try:
            cmd = ["wmic", "cdrom", "get", "DeviceID,Drive,Name", "/format:list"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                current_drive = {}
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        if current_drive:
                            drives.append(current_drive)
                            current_drive = {}
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        if k == 'DeviceID':
                            current_drive['device_id'] = v
                        elif k == 'Drive':
                            current_drive['drive_letter'] = v
                        elif k == 'Name':
                            current_drive['name'] = v
                if current_drive:
                    drives.append(current_drive)
        except Exception:
            pass

    # Clean up and ensure drive letters end with colon
    for d in drives:
        if d.get('drive_letter') and not d['drive_letter'].endswith(':'):
            d['drive_letter'] += ':'
    return drives

# ── CUE & BIN Parsing & Splitting ──────────────────────────────────────────

def msf_to_frames(msf_str: str) -> int:
    """Convert MM:SS:FF to absolute frames (75 frames/sec)."""
    parts = list(map(int, msf_str.split(':')))
    if len(parts) != 3:
        raise ValueError(f"Invalid MSF format: {msf_str}")
    mm, ss, ff = parts
    return (mm * 60 + ss) * 75 + ff

def frames_to_msf(frames: int) -> str:
    ff = frames % 75
    total_secs = frames // 75
    ss = total_secs % 60
    mm = total_secs // 60
    return f"{mm:02d}:{ss:02d}:{ff:02d}"

def parse_cue(cue_path: str):
    """
    Parse a .cue file and extract track info.
    Returns: (bin_filename, list_of_tracks)
    Each track: {
        'number': int,
        'type': str,      # e.g., 'AUDIO', 'MODE2/2352', 'MODE1/2352'
        'start_frame': int,
        'index_01_frame': int
    }
    """
    if not os.path.exists(cue_path):
        raise FileNotFoundError(f"CUE file not found: {cue_path}")

    bin_file = None
    tracks = []
    current_track = None

    with open(cue_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # File line
            m_file = re.match(r'^FILE\s+"([^"]+)"\s+(\S+)', line, re.IGNORECASE)
            if not m_file:
                m_file = re.match(r'^FILE\s+(\S+)\s+(\S+)', line, re.IGNORECASE)
            if m_file:
                bin_file = m_file.group(1)
                continue

            # Track line
            m_track = re.match(r'^TRACK\s+(\d+)\s+(\S+)', line, re.IGNORECASE)
            if m_track:
                t_num = int(m_track.group(1))
                t_type = m_track.group(2).upper()
                current_track = {
                    'number': t_num,
                    'type': t_type,
                    'start_frame': 0,
                    'index_01_frame': 0
                }
                tracks.append(current_track)
                continue

            # Index line
            m_idx = re.match(r'^INDEX\s+(\d+)\s+([\d:]+)', line, re.IGNORECASE)
            if m_idx and current_track:
                idx_num = int(m_idx.group(1))
                msf = m_idx.group(2)
                frames = msf_to_frames(msf)
                if idx_num == 0:
                    current_track['start_frame'] = frames
                elif idx_num == 1:
                    current_track['index_01_frame'] = frames
                    # If start_frame wasn't set by INDEX 00, default it to INDEX 01
                    if current_track['start_frame'] == 0:
                        current_track['start_frame'] = frames

    return bin_file, tracks

def make_wav_header(data_size: int, sample_rate: int = 44100, num_channels: int = 2, bits_per_sample: int = 16) -> bytes:
    """Generate a standard 44-byte WAV RIFF header."""
    block_align = num_channels * (bits_per_sample // 8)
    byte_rate = sample_rate * block_align
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,              # Subchunk1Size
        1,               # AudioFormat (1 = PCM)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_size
    )
    return header

def split_bin_cue(cue_path: str, output_dir: str, convert_to_mpg: bool = True, logger=None):
    """
    Split a raw BIN CD image using its CUE sheet.
    Converts AUDIO tracks to playable .wav files.
    If convert_to_mpg is True, converts VCD MODE2 tracks to .mpg files by stripping XA headers.
    """
    bin_name, tracks = parse_cue(cue_path)
    if not bin_name:
        raise ValueError("No binary file specified in CUE file.")

    # Locate BIN file relative to CUE directory
    cue_dir = os.path.dirname(os.path.abspath(cue_path))
    bin_path = os.path.join(cue_dir, bin_name)

    if not os.path.exists(bin_path):
        # Try same name but case differences, or match first bin file in dir
        found = False
        for f in os.listdir(cue_dir):
            if f.lower() == bin_name.lower():
                bin_path = os.path.join(cue_dir, f)
                found = True
                break
        if not found:
            raise FileNotFoundError(f"BIN file not found: {bin_path}")

    bin_size = os.path.getsize(bin_path)
    total_frames = bin_size // SECTOR_SIZE

    if logger:
        logger(f"Splitting BIN: {bin_path} ({bin_size / (1024*1024):.1f} MB)")
        logger(f"Found {len(tracks)} tracks in CUE sheet.")

    os.makedirs(output_dir, exist_ok=True)

    for i, t in enumerate(tracks):
        track_num = t['number']
        track_type = t['type']
        start_frame = t['index_01_frame']

        # Determine end frame
        if i + 1 < len(tracks):
            # End frame is the index_01 frame of the next track
            end_frame = tracks[i+1]['index_01_frame']
        else:
            end_frame = total_frames

        length_frames = end_frame - start_frame
        if length_frames <= 0:
            if logger:
                logger(f"Track {track_num:02d}: Invalid or zero length. Skipping.")
            continue

        start_byte = start_frame * SECTOR_SIZE
        length_bytes = length_frames * SECTOR_SIZE

        if logger:
            logger(f"Track {track_num:02d}: Type={track_type}, Sector Range={start_frame} to {end_frame} ({length_frames} sectors)")

        # Perform extraction
        out_base = f"track_{track_num:02d}"

        with open(bin_path, 'rb') as f_in:
            f_in.seek(start_byte)

            if track_type == 'AUDIO':
                # Extract as WAV
                out_path = os.path.join(output_dir, f"{out_base}.wav")
                if logger:
                    logger(f"  -> Extracting Audio track to WAV: {os.path.basename(out_path)}")
                
                # Write WAV header then raw PCM
                pcm_data = f_in.read(length_bytes)
                wav_header = make_wav_header(len(pcm_data))
                with open(out_path, 'wb') as f_out:
                    f_out.write(wav_header)
                    f_out.write(pcm_data)

            elif 'MODE2' in track_type and convert_to_mpg:
                # Extract VCD video by stripping XA headers
                out_path = os.path.join(output_dir, f"{out_base}.mpg")
                if logger:
                    logger(f"  -> Extracting & Converting VCD track to MPG: {os.path.basename(out_path)}")

                written_sects = 0
                with open(out_path, 'wb') as f_out:
                    for _ in range(length_frames):
                        sector = f_in.read(SECTOR_SIZE)
                        if len(sector) < SECTOR_SIZE:
                            break
                        submode = sector[18]
                        if submode & 0x20:  # Form-2 sector
                            payload = sector[24:24 + 2324]
                            if payload[:4] == MPEG_PACK:
                                f_out.write(payload)
                                written_sects += 1

                mb = written_sects * 2324 / 1024 / 1024
                if logger:
                    logger(f"  -> Done: {written_sects:,} video sectors extracted ({mb:.1f} MB)")

            else:
                # Extract as raw BIN sector chunk
                out_path = os.path.join(output_dir, f"{out_base}.bin")
                if logger:
                    logger(f"  -> Extracting raw track chunk to BIN: {os.path.basename(out_path)}")

                chunk = f_in.read(length_bytes)
                with open(out_path, 'wb') as f_out:
                    f_out.write(chunk)

    if logger:
        logger("Split complete!\n")

# ── TOC to CUE Conversion ──────────────────────────────────────────────────

def convert_toc_to_cue(toc_path: str, cue_path: str = None, logger=None):
    """Convert a Brasero-style .toc file to a .cue sheet."""
    if cue_path is None:
        base = os.path.splitext(toc_path)[0]
        cue_path = base + ".cue"

    if logger:
        logger(f"Reading TOC file: {toc_path}")

    with open(toc_path, "r", encoding="utf-8", errors="replace") as f:
        toc_text = f.read()

    # Split into per-track blocks
    blocks = re.split(r"//\s*Track\s+\d+", toc_text)
    tracks = []
    track_num = 0

    for block in blocks[1:]:
        track_num += 1
        track = {"number": track_num, "offset": 0, "length": 0, "mode": "MODE2_RAW"}

        # TRACK MODE
        m = re.search(r"TRACK\s+(\S+)", block)
        if m:
            track["mode"] = m.group(1)

        # DATAFILE
        m_df = re.search(
            r'DATAFILE\s+"([^"]+)"\s+(?:#(\d+)\s+)?[\d:]+\s*//\s*length in bytes:\s*(\d+)',
            block
        )
        if m_df:
            track["datafile"] = m_df.group(1)
            track["offset"] = int(m_df.group(2)) if m_df.group(2) else 0
            track["length"] = int(m_df.group(3))
        else:
            if logger:
                logger(f"  [Warning] Could not parse DATAFILE line in track {track_num}")

        tracks.append(track)

    if not tracks:
        raise ValueError("No tracks found in TOC file.")

    datafile = tracks[0].get("datafile", "unknown.bin")
    lines = [f'FILE "{datafile}" BINARY']

    for t in tracks:
        abs_frames = t["offset"] // SECTOR_SIZE
        msf = frames_to_msf(abs_frames)

        raw_mode = t.get("mode", "MODE2_RAW")
        if raw_mode == "MODE2_RAW":
            cue_mode = "MODE2/2352"
        elif raw_mode in ("MODE1", "MODE1_RAW"):
            cue_mode = "MODE1/2352"
        elif raw_mode == "AUDIO":
            cue_mode = "AUDIO"
        else:
            cue_mode = "MODE2/2352"

        lines.append(f"")
        lines.append(f"  TRACK {t['number']:02d} {cue_mode}")
        lines.append(f"    INDEX 01 {msf}")

    cue_content = "\n".join(lines) + "\n"

    with open(cue_path, "w", encoding="utf-8") as f:
        f.write(cue_content)

    if logger:
        logger(f"Written CUE sheet: {cue_path}")
        logger(cue_content)
    return cue_path

# ── XA Video Extraction and Fixing ──────────────────────────────────────────

def is_xa_image(path: str) -> bool:
    """Detect raw CD-ROM XA image by sync pattern + sector-aligned size."""
    try:
        size = os.path.getsize(path)
        if size % SECTOR_SIZE != 0:
            return False
        with open(path, 'rb') as f:
            return f.read(12) == CD_SYNC
    except Exception:
        return False

def extract_xa_to_file(src_path: str, dst_path: str, label: str = "", logger=None, progress_update=None) -> int:
    """Strip 2352-byte CD-ROM sector headers from an XA image."""
    file_size   = os.path.getsize(src_path)
    total_sects = file_size // SECTOR_SIZE
    written = 0
    t0 = time.time()

    with open(src_path, 'rb') as fin, open(dst_path, 'wb') as fout:
        for idx in range(total_sects):
            sector = fin.read(SECTOR_SIZE)
            if len(sector) < SECTOR_SIZE:
                break
            submode = sector[18]
            if submode & 0x20:                      # Form-2 sector
                payload = sector[24:24 + 2324]
                if payload[:4] == MPEG_PACK:
                    fout.write(payload)
                    written += 1
            if idx % 10000 == 0 and total_sects > 0:
                pct = 100 * idx / total_sects
                if progress_update:
                    progress_update(pct)
                if logger and idx % 40000 == 0:
                    tag = f"[{label}] " if label else ""
                    logger(f"  {tag}Extracting payload: {pct:.1f}%")

    elapsed = time.time() - t0
    mb = written * 2324 / 1024 / 1024
    if logger:
        logger(f"  Done in {elapsed:.1f}s  ->  {written:,} sectors ({mb:.1f} MB)")
    return written

def probe_info(path: str):
    """Return (duration_seconds, size_bytes) via ffprobe, or (None, None)."""
    ffprobe = get_ffprobe_path()
    if not ffprobe:
        return None, None
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration,size",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip().split()
        return float(out[0]), int(out[1])
    except Exception:
        return None, None

def probe_video_bitrate(path: str) -> str:
    """Read the video bitrate from an XA-extracted raw MPEG stream."""
    ffprobe = get_ffprobe_path()
    if not ffprobe:
        return VIDEO_BITRATE
    cmd = [
        ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=bit_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    try:
        val = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
        bps = int(val)
        return f"{bps // 1000}k" if bps > 0 else VIDEO_BITRATE
    except Exception:
        return VIDEO_BITRATE

def reencode_video_ffmpeg(input_path: str, output_path: str, vbitrate: str = VIDEO_BITRATE,
                           width: int = 352, height: int = 288, logger=None, progress_callback=None, cancel_event=None):
    """Re-encode VCD video with clean timestamps using ffmpeg."""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg not found in PATH.")

    cmd = [
        ffmpeg, "-y",
        "-fflags", "+genpts+igndts",
        "-i", input_path,
        "-vf", f"scale={width}:{height},setpts=N/FRAME_RATE/TB",
        "-c:v", VIDEO_CODEC,
        "-b:v", vbitrate,
        "-q:v", VIDEO_QUALITY,
        "-af", "asetpts=N/SR/TB",
        "-c:a", AUDIO_CODEC,
        "-b:a", AUDIO_BITRATE,
        "-ar", AUDIO_RATE,
        output_path
    ]

    if logger:
        logger(f"Running ffmpeg: {' '.join(cmd)}")

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True)

    duration, _ = probe_info(input_path)
    
    while True:
        if cancel_event and cancel_event.is_set():
            process.terminate()
            if logger:
                logger("ffmpeg process cancelled by user.")
            return False

        line = process.stderr.readline()
        if not line:
            break
        
        if "time=" in line:
            m = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if m and duration and progress_callback:
                h, m_val, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
                curr_time = h * 3600 + m_val * 60 + s
                pct = min(100.0, (curr_time / duration) * 100)
                progress_callback(pct)

    process.wait()
    return process.returncode == 0

def reencode_concat_ffmpeg(raw_paths: list, output_path: str, vbitrate: str = VIDEO_BITRATE,
                           width: int = 352, height: int = 288, logger=None, progress_callback=None, cancel_event=None):
    """Concatenate and re-encode multiple raw MPEG paths."""
    tmp_dir = os.path.dirname(output_path)
    seg_mp4s = []
    try:
        # Phase 1: Re-encode segments to temp files
        for i, raw in enumerate(raw_paths, 1):
            if cancel_event and cancel_event.is_set():
                return False
            if logger:
                logger(f"Re-encoding segment {i}/{len(raw_paths)}: {os.path.basename(raw)}")
            seg_fd, seg_mp4 = tempfile.mkstemp(suffix=f".seg{i:02d}.mp4", dir=tmp_dir)
            os.close(seg_fd)
            seg_mp4s.append(seg_mp4)

            def sub_prog(pct):
                if progress_callback:
                    base_pct = ((i - 1) / len(raw_paths)) * 100
                    segment_contrib = (pct / len(raw_paths))
                    progress_callback(base_pct + segment_contrib)

            ok = reencode_video_ffmpeg(raw, seg_mp4, vbitrate, width, height, logger, sub_prog, cancel_event)
            if not ok:
                if logger:
                    logger(f"Error: Segment {i} re-encode failed.")
                return False

        if not seg_mp4s:
            return False

        if len(seg_mp4s) == 1:
            import shutil
            shutil.move(seg_mp4s[0], output_path)
            seg_mp4s.clear()
            return True

        # Phase 2: Concat demuxer
        list_fd, list_path = tempfile.mkstemp(suffix=".concat.txt", dir=tmp_dir)
        os.close(list_fd)
        with open(list_path, 'w') as lf:
            for p in seg_mp4s:
                lf.write(f"file '{p}'\n")

        if logger:
            logger(f"Joining {len(seg_mp4s)} segments with concat demuxer...")

        ffmpeg = get_ffmpeg_path()
        cmd = [
            ffmpeg, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            output_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        os.remove(list_path)
        return res.returncode == 0

    finally:
        for p in seg_mp4s:
            if os.path.exists(p):
                os.remove(p)

# ── Video Stitcher ─────────────────────────────────────────────────────────

def stitch_videos(input_files: list, output_path: str, reencode: bool = False, logger=None, progress_callback=None, cancel_event=None):
    """Concatenate videos using ffmpeg concat demuxer."""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg not found in PATH.")

    tmp_fd, list_path = tempfile.mkstemp(suffix=".stitch_list.txt")
    os.close(tmp_fd)

    try:
        with open(list_path, 'w', encoding='utf-8') as f:
            for p in input_files:
                abs_p = os.path.abspath(p).replace('\\', '/')
                f.write(f"file '{abs_p}'\n")

        if logger:
            logger(f"Created concat file at: {list_path}")
            logger("Files to stitch in order:")
            for f in input_files:
                logger(f"  -> {f}")

        if reencode:
            cmd = [
                ffmpeg, "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_path,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                output_path
            ]
        else:
            cmd = [
                ffmpeg, "-y",
                "-f", "concat", "-safe", "0",
                "-i", list_path,
                "-c", "copy",
                output_path
            ]

        if logger:
            logger(f"Stitch Mode: {'Re-encode' if reencode else 'Stream Copy'}")
            logger(f"Running stitch command: {' '.join(cmd)}")

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True)

        total_duration = 0.0
        for f in input_files:
            dur, _ = probe_info(f)
            if dur:
                total_duration += dur

        while True:
            if cancel_event and cancel_event.is_set():
                process.terminate()
                if logger:
                    logger("Stitch process cancelled.")
                return False

            line = process.stderr.readline()
            if not line:
                break
            
            if "time=" in line:
                m = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                if m and total_duration > 0 and progress_callback:
                    h, m_val, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
                    curr_time = h * 3600 + m_val * 60 + s
                    pct = min(100.0, (curr_time / total_duration) * 100)
                    progress_callback(pct)

        process.wait()
        return process.returncode == 0
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)

# ── Audio Extraction ────────────────────────────────────────────────────────

def extract_audio(input_file: str, output_path: str, format_type: str = "mp3", logger=None, progress_callback=None, cancel_event=None):
    """Extract audio from video file to MP3, WAV, FLAC, or AAC."""
    ffmpeg = get_ffmpeg_path()
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg not found in PATH.")

    cmd = [ffmpeg, "-y", "-i", input_file, "-vn"]

    if format_type == "mp3":
        cmd += ["-c:a", "libmp3lame", "-q:a", "2", output_path]
    elif format_type == "wav":
        cmd += ["-c:a", "pcm_s16le", "-ar", "44100", output_path]
    elif format_type == "flac":
        cmd += ["-c:a", "flac", output_path]
    elif format_type == "aac":
        cmd += ["-c:a", "aac", "-b:a", "192k", output_path]
    else:
        cmd += ["-c:a", "copy", output_path]

    if logger:
        logger(f"  Extracting Audio ({format_type.upper()}): {input_file} -> {output_path}")
        logger(f"Command: {' '.join(cmd)}")

    duration, _ = probe_info(input_file)

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True)

    while True:
        if cancel_event and cancel_event.is_set():
            process.terminate()
            if logger:
                logger("Audio extraction cancelled.")
            return False

        line = process.stderr.readline()
        if not line:
            break

        if "time=" in line:
            m = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if m and duration and progress_callback:
                h, m_val, s = float(m.group(1)), float(m.group(2)), float(m.group(3))
                curr_time = h * 3600 + m_val * 60 + s
                pct = min(100.0, (curr_time / duration) * 100)
                progress_callback(pct)

    process.wait()
    return process.returncode == 0

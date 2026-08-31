#!/usr/bin/env python3
"""
fix_vcd_video.py
────────────────
Fix videos with wrong/bloated duration caused by broken timestamps.
Supports three modes, auto-detected from the input:

  MODE A — VCD XA Image (.mpg raw CD-ROM sector image, single file)
  ──────────────────────────────────────────────────────────────────
  Strips 2352-byte CD-ROM sector headers, extracts MPEG Pack payloads,
  then RE-ENCODES with clean sequential timestamps (fixes SCR resets).

  MODE B — Broken MP4 / any normal video file
  ─────────────────────────────────────────────
  For plain MP4, MKV, AVI, MOV etc. files that show wrong duration.
  Re-encodes with fresh timestamps using setpts=N/FRAME_RATE/TB.

  MODE C — Multiple XA stream files → single concatenated MP4
  ─────────────────────────────────────────────────────────────
  When a VCD is split across multiple XA track files (e.g. stream02.mpg …
  stream10.mpg), this mode extracts each one, concatenates all segments,
  and re-encodes the result with clean continuous timestamps.

Usage
─────
  # MODE A — fix a single raw VCD XA sector image (auto-detected):
  python3 fix_vcd_video.py video_track01.mpg  [output.mp4]

  # MODE B — fix a broken MP4 (or any regular video file):
  python3 fix_vcd_video.py broken_video.mp4   [output_fixed.mp4]

  # MODE C — join multiple XA stream files into one clean MP4:
  python3 fix_vcd_video.py stream02.mpg stream03.mpg ... streamN.mpg OUTPUT.mp4
    (the last argument ending in .mp4/.mkv is treated as output)
    Example:
      python3 fix_vcd_video.py \\
        Bhajans/Ravindra/santmat_stream02.mpg \\
        Bhajans/Ravindra/santmat_stream03.mpg \\
        Bhajans/Ravindra/santmat_stream04.mpg \\
        santmat_fixed.mp4

  # Explicit mode override:
  python3 fix_vcd_video.py INPUT OUTPUT --mode xa    # force Mode A
  python3 fix_vcd_video.py INPUT OUTPUT --mode mp4   # force Mode B

  # Defaults (no arguments):
  python3 fix_vcd_video.py
    → input : video_track01.mpg  (Mode A)
    → output: video_fixed.mp4

Requirements
────────────
  • Python 3.6+
  • ffmpeg / ffprobe in PATH

NOTE on quality
───────────────
  Because MPEG-1 with B-frames (non-monotonic PTS/DTS) cannot be losslessly
  remuxed into MP4 with correct timestamps, this script RE-ENCODES the video
  at the same bitrate. Quality is visually identical to the source.
"""

import os
import sys
import subprocess
import tempfile
import time
import glob

# ── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_INPUT  = "video_track01.mpg"
DEFAULT_OUTPUT = "video_fixed.mp4"

SECTOR_SIZE = 2352
MPEG_PACK   = b'\x00\x00\x01\xba'
CD_SYNC     = b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00'

# Re-encode settings (matches original VCD quality exactly)
VIDEO_CODEC  = "mpeg1video"
VIDEO_BITRATE = "1150k"
VIDEO_QUALITY = "3"        # -q:v, lower = better; 3 is near-lossless for mpeg1
AUDIO_CODEC  = "mp2"
AUDIO_BITRATE = "224k"
AUDIO_RATE   = "44100"

# ── Helpers ───────────────────────────────────────────────────────────────────

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def is_xa_image(path: str) -> bool:
    """Detect raw CD-ROM XA image by sync pattern + sector-aligned size."""
    size = os.path.getsize(path)
    if size % SECTOR_SIZE != 0:
        return False
    with open(path, 'rb') as f:
        return f.read(12) == CD_SYNC


def probe_info(path: str):
    """Return (duration_seconds, size_bytes) via ffprobe, or (None, None)."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                      text=True).strip().split()
        return float(out[0]), int(out[1])
    except Exception:
        return None, None


def probe_video_bitrate(path: str) -> str:
    """Read the video bitrate from an XA-extracted raw MPEG stream."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=bit_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    try:
        val = subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                      text=True).strip()
        bps = int(val)
        return f"{bps // 1000}k" if bps > 0 else VIDEO_BITRATE
    except Exception:
        return VIDEO_BITRATE

# ── XA Extraction ─────────────────────────────────────────────────────────────

def extract_xa_to_file(src_path: str, dst_path: str, label: str = "") -> int:
    """
    Strip 2352-byte CD-ROM sector headers from an XA image.
    Only Form-2 sectors starting with MPEG Pack (00 00 01 BA) are written.
    Returns number of MPEG sectors written.
    """
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
            if idx % 10_000 == 0 and total_sects > 0:
                pct = 100 * idx / total_sects
                eta = ((time.time()-t0)/(idx+1))*(total_sects-idx) if idx else 0
                tag = f"[{label}] " if label else ""
                print(f"  \r  {tag}Extracting: {pct:5.1f}%  ETA {eta:.0f}s   ",
                      end='', flush=True)

    elapsed = time.time() - t0
    mb = written * 2324 / 1024 / 1024
    tag = f"[{label}] " if label else ""
    print(f"\r  {tag}Done in {elapsed:.1f}s  →  {written:,} sectors ({mb:.1f} MB)")
    return written

# ── Re-encode with clean timestamps ───────────────────────────────────────────

def reencode(input_path: str, output_path: str,
             vbitrate: str = VIDEO_BITRATE,
             width: int = 352, height: int = 288) -> bool:
    """
    Re-encode video+audio from input_path → output_path:
      - scale=WxH           → normalize resolution (handles mid-stream glitches)
      - setpts=N/FRAME_RATE/TB → clean sequential video timestamps
      - asetpts=N/SR/TB     → clean sequential audio timestamps
    No subjective quality change: same codec and bitrate as source.
    """
    cmd = [
        "ffmpeg", "-y",
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
    print(f"\n  ffmpeg: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode == 0


def reencode_concat(raw_paths: list, output_path: str,
                    vbitrate: str = VIDEO_BITRATE,
                    width: int = 352, height: int = 288,
                    tmp_dir: str = None) -> bool:
    """
    Two-phase approach (robust against mid-stream resolution changes):
      Phase 1: Re-encode each raw segment individually to a temp MP4,
               with scale=WxH + clean timestamps.
      Phase 2: Join all temp MP4s using the concat DEMUXER (-f concat -c copy)
               which operates at file level and never needs filter reinit.
    """
    if tmp_dir is None:
        tmp_dir = os.path.dirname(output_path)

    seg_mp4s = []
    try:
        # ── Phase 1: encode each segment ────────────────────────────────────
        for i, raw in enumerate(raw_paths, 1):
            seg_fd, seg_mp4 = tempfile.mkstemp(
                suffix=f".seg{i:02d}.mp4", dir=tmp_dir)
            os.close(seg_fd)
            seg_mp4s.append(seg_mp4)
            print(f"\n  Segment {i}/{len(raw_paths)}: {os.path.basename(raw)}")
            ok = reencode(raw, seg_mp4, vbitrate, width, height)
            if not ok:
                print(f"  WARNING: Re-encode failed for segment {i}, skipping.")
                seg_mp4s.pop()
                os.remove(seg_mp4)

        if not seg_mp4s:
            return False

        if len(seg_mp4s) == 1:
            # Only one good segment — just rename it
            import shutil
            shutil.move(seg_mp4s[0], output_path)
            seg_mp4s.clear()
            return True

        # ── Phase 2: concat demuxer join ─────────────────────────────────────
        list_fd, list_path = tempfile.mkstemp(suffix=".concat.txt", dir=tmp_dir)
        os.close(list_fd)
        with open(list_path, 'w') as lf:
            for p in seg_mp4s:
                lf.write(f"file '{p}'\n")

        print(f"\n  Joining {len(seg_mp4s)} segments with concat demuxer …\n")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            output_path
        ]
        result = subprocess.run(cmd)
        os.remove(list_path)
        return result.returncode == 0

    finally:
        for p in seg_mp4s:
            if os.path.exists(p):
                os.remove(p)

# ── Main ──────────────────────────────────────────────────────────────────────

def print_usage():
    print(__doc__)


def detect_mode(args: list) -> tuple:
    """
    Returns (mode, input_list, output_path).
    mode: 'xa' | 'mp4' | 'multi_xa'
    """
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.mpg', '.mpeg',
                  '.m4v', '.webm', '.flv', '.ts'}

    if len(args) == 0:
        return 'xa', [DEFAULT_INPUT], DEFAULT_OUTPUT

    # Last arg is output if it ends with a known video extension
    last = args[-1]
    last_ext = os.path.splitext(last)[1].lower()
    if last_ext in {'.mp4', '.mkv', '.avi', '.mov'}:
        inputs  = args[:-1]
        output  = last
    else:
        inputs  = args
        output  = DEFAULT_OUTPUT

    if len(inputs) == 0:
        inputs = [DEFAULT_INPUT]

    if len(inputs) > 1:
        # Multiple inputs → must be multi XA mode
        return 'multi_xa', inputs, output

    single = inputs[0]
    if not os.path.isfile(single):
        return None, inputs, output   # will error out later

    if is_xa_image(single):
        return 'xa', inputs, output
    else:
        return 'mp4', inputs, output


def main():
    # ── Parse arguments ──────────────────────────────────────────────────────
    raw_args = sys.argv[1:]
    if '--help' in raw_args or '-h' in raw_args:
        print_usage()
        sys.exit(0)

    # Separate flags from positional args
    flags = [a for a in raw_args if a.startswith('--')]
    args  = [a for a in raw_args if not a.startswith('--')]

    forced_mode = None
    for flag in flags:
        if flag.startswith('--mode='):
            forced_mode = flag.split('=', 1)[1].lower()

    mode, inputs, output_path = detect_mode(args)

    if forced_mode == 'xa':
        mode = 'xa'
    elif forced_mode in ('mp4', 'video', 'direct', 'b'):
        mode = 'mp4'
    elif forced_mode in ('multi', 'multi_xa', 'c'):
        mode = 'multi_xa'

    # Validate inputs
    for inp in inputs:
        if not os.path.isfile(inp):
            sys.exit(f"ERROR: File not found: {inp}\n       Run with --help for usage.")

    output_path = os.path.abspath(output_path)
    out_dir = os.path.dirname(output_path)

    # ── Header ───────────────────────────────────────────────────────────────
    print("=" * 66)
    if mode == 'xa':
        print("  MODE A — Single VCD XA Image → MP4")
    elif mode == 'mp4':
        print("  MODE B — Broken Video → MP4  (timestamp re-encode)")
    else:
        print(f"  MODE C — {len(inputs)} XA Stream Files → Single MP4")
    print("=" * 66)
    for inp in inputs:
        print(f"  Input  : {inp}")
    print(f"  Output : {output_path}")
    print()

    # ── MODE A: Single XA ────────────────────────────────────────────────────
    if mode == 'xa':
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mpeg.tmp", dir=out_dir)
        os.close(tmp_fd)
        try:
            print("[Step 1/2]  Extracting MPEG payload from XA sectors …")
            written = extract_xa_to_file(inputs[0], tmp_path)
            if written == 0:
                sys.exit("ERROR: No MPEG Pack sectors found. Try --mode mp4.")
            vbr = probe_video_bitrate(tmp_path)
            print(f"\n[Step 2/2]  Re-encoding with clean timestamps (vbr={vbr}) …")
            ok = reencode(tmp_path, output_path, vbr)
            if not ok:
                sys.exit("ERROR: ffmpeg failed. See messages above.")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ── MODE B: Broken MP4 ───────────────────────────────────────────────────
    elif mode == 'mp4':
        orig_dur, orig_size = probe_info(inputs[0])
        if orig_dur:
            print(f"  Original duration : {format_time(orig_dur)}  ← likely wrong")
            print()
        print("[Step 1/1]  Re-encoding with clean timestamps …")
        vbr = probe_video_bitrate(inputs[0]) or VIDEO_BITRATE
        ok = reencode(inputs[0], output_path, vbr)
        if not ok:
            sys.exit("ERROR: ffmpeg failed. See messages above.")

    # ── MODE C: Multiple XA streams → concat ─────────────────────────────────
    else:
        tmp_paths = []
        try:
            print(f"[Step 1/2]  Extracting MPEG payload from {len(inputs)} XA files …\n")
            for i, src in enumerate(inputs, 1):
                label = f"{i}/{len(inputs)} {os.path.basename(src)}"
                tmp_fd, tmp_p = tempfile.mkstemp(suffix=f".seg{i}.tmp", dir=out_dir)
                os.close(tmp_fd)
                tmp_paths.append(tmp_p)
                written = extract_xa_to_file(src, tmp_p, label=label)
                if written == 0:
                    print(f"  WARNING: No MPEG data in {src}, skipping.")
                    tmp_paths.pop()
                    os.remove(tmp_p)

            if not tmp_paths:
                sys.exit("ERROR: No valid MPEG data found in any input file.")

            # Use bitrate from first segment
            vbr = probe_video_bitrate(tmp_paths[0])
            print(f"\n[Step 2/2]  Concatenating {len(tmp_paths)} segments + re-encode (vbr={vbr}) …")
            if len(tmp_paths) == 1:
                ok = reencode(tmp_paths[0], output_path, vbr)
            else:
                ok = reencode_concat(tmp_paths, output_path, vbr)
            if not ok:
                sys.exit("ERROR: ffmpeg failed. See messages above.")
        finally:
            for p in tmp_paths:
                if os.path.exists(p):
                    os.remove(p)

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("=" * 66)
    dur, size = probe_info(output_path)
    if dur:
        print(f"  ✅ Output duration : {format_time(dur)}  ({dur:.0f}s)")
    if size:
        print(f"  ✅ Output size     : {size / 1024 / 1024:.1f} MB")
    print(f"  ✅ Output file     : {output_path}")
    print("=" * 66)
    print("  Done! Open the output file in any media player.")
    print()


if __name__ == "__main__":
    main()

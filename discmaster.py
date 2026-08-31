#!/usr/bin/env python3
"""
discmaster.py
─────────────
Modern, dark-themed Tkinter GUI for DiscMaster.
Wraps discmaster_engine.py with an intuitive, multi-tab interface.
"""

import os
import sys
import threading
import queue
import glob
from tkinter import ttk, filedialog, messagebox
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

# Import engine
try:
    import discmaster_engine as engine
except ImportError:
    # If run in subfolders, append parent dir
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import discmaster_engine as engine

# Theme & Colors
COLOR_BG = "#0f172a"          # Dark slate
COLOR_SURFACE = "#1e293b"     # Lighter slate
COLOR_TEXT = "#f8fafc"        # Off-white
COLOR_TEXT_MUTED = "#94a3b8"  # Gray
COLOR_PRIMARY = "#6366f1"     # Indigo
COLOR_PRIMARY_HOVER = "#4f46e5"
COLOR_ACCENT = "#c084fc"      # Purple/Lavender
COLOR_SUCCESS = "#22c55e"     # Green
COLOR_ERROR = "#ef4444"       # Red
COLOR_CONSOLE_BG = "#020617"  # Very dark console background

class DiscMasterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DiscMaster — Optical Copy & Processing Studio")
        self.geometry("960x700")
        self.configure(bg=COLOR_BG)

        # Application state
        self.cancel_event = threading.Event()
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.active_thread = None
        self.stitch_files_list = []

        # Default paths
        self.workspace_dir = os.path.dirname(os.path.abspath(__file__))

        self.setup_styles()
        self.build_ui()
        
        # Check dependencies
        self.check_system_dependencies()

        # Start queue processing
        self.after(100, self.process_queues)

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Main window configure
        style.configure(".",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_SURFACE,
            font=("Segoe UI", 10)
        )

        # Frame styles
        style.configure("TFrame", background=COLOR_BG)
        style.configure("Surface.TFrame", background=COLOR_SURFACE)

        # Tab styles (Notebook)
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("TNotebook.Tab",
            background=COLOR_SURFACE,
            foreground=COLOR_TEXT_MUTED,
            padding=[15, 8],
            font=("Segoe UI", 10, "bold"),
            borderwidth=0
        )
        style.map("TNotebook.Tab",
            background=[("selected", COLOR_PRIMARY)],
            foreground=[("selected", COLOR_TEXT)]
        )

        # Label styles
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        style.configure("Surface.TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT)
        style.configure("Header.TLabel",
            background=COLOR_BG,
            foreground=COLOR_ACCENT,
            font=("Segoe UI", 16, "bold")
        )
        style.configure("Subheader.TLabel",
            background=COLOR_BG,
            foreground=COLOR_TEXT_MUTED,
            font=("Segoe UI", 10, "italic")
        )

        # Button styles
        style.configure("TButton",
            background=COLOR_PRIMARY,
            foreground=COLOR_TEXT,
            borderwidth=0,
            padding=[12, 6],
            font=("Segoe UI", 10, "bold")
        )
        style.map("TButton",
            background=[("active", COLOR_PRIMARY_HOVER), ("disabled", COLOR_SURFACE)],
            foreground=[("disabled", COLOR_TEXT_MUTED)]
        )

        style.configure("Accent.TButton",
            background=COLOR_ACCENT,
            foreground=COLOR_BG,
            font=("Segoe UI", 10, "bold")
        )
        style.map("Accent.TButton",
            background=[("active", "#a855f7")]
        )

        style.configure("Cancel.TButton",
            background=COLOR_ERROR,
            foreground=COLOR_TEXT,
            font=("Segoe UI", 10, "bold")
        )
        style.map("Cancel.TButton",
            background=[("active", "#dc2626")]
        )

        # Combobox / Entry styles
        style.configure("TCombobox", fieldbackground=COLOR_SURFACE, background=COLOR_SURFACE, foreground=COLOR_TEXT)
        style.configure("TEntry", fieldbackground=COLOR_SURFACE, foreground=COLOR_TEXT, borderwidth=1)

        # Progressbar
        style.configure("TProgressbar",
            thickness=15,
            troughcolor=COLOR_SURFACE,
            background=COLOR_PRIMARY,
            borderwidth=0
        )

    def check_system_dependencies(self):
        ffmpeg = engine.get_ffmpeg_path()
        ffprobe = engine.get_ffprobe_path()
        
        dep_msg = []
        if not ffmpeg:
            dep_msg.append("• ffmpeg was not found in system PATH. Video transcoding and extraction features will fail.")
        if not ffprobe:
            dep_msg.append("• ffprobe was not found in system PATH. Media details detection will be disabled.")
            
        if dep_msg:
            self.write_log("[SYSTEM WARNING] Missing dependencies:\n" + "\n".join(dep_msg) + "\n\nPlease ensure ffmpeg and ffprobe are installed and in your environment PATH variables.\n", is_error=True)

    def build_ui(self):
        # Master grid container
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        main_container = ttk.Frame(self, padding=10)
        main_container.grid(row=0, column=0, sticky="nsew")
        main_container.grid_rowconfigure(1, weight=1)
        main_container.grid_columnconfigure(0, weight=1)

        # Header Title Area
        header_frame = ttk.Frame(main_container)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        lbl_title = ttk.Label(header_frame, text="DISCMASTER", style="Header.TLabel")
        lbl_title.pack(side="left")
        
        lbl_subtitle = ttk.Label(header_frame, text=" — Copy, Rip & Video/Audio Processing Suite", style="Subheader.TLabel")
        lbl_subtitle.pack(side="left", padx=5, pady=(5, 0))

        # Shared Console and Progress Footer (Created before tabs to allow early logging)
        footer_frame = ttk.Frame(main_container, padding=(0, 10, 0, 0))
        footer_frame.grid(row=2, column=0, sticky="ew")
        footer_frame.grid_columnconfigure(0, weight=1)

        # Console Log
        self.console = ScrolledText(footer_frame, height=8, bg=COLOR_CONSOLE_BG, fg=COLOR_TEXT, 
                                    font=("Consolas", 9), insertbackground=COLOR_TEXT, borderwidth=0)
        self.console.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        self.console.tag_config("error", foreground=COLOR_ERROR)
        self.console.tag_config("success", foreground=COLOR_SUCCESS)
        self.console.tag_config("info", foreground=COLOR_ACCENT)

        # Progress elements
        self.progress_val = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(footer_frame, variable=self.progress_val, maximum=100, mode="determinate")
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=(0, 10))

        self.btn_cancel = ttk.Button(footer_frame, text="Cancel Active Task", style="Cancel.TButton", command=self.cancel_active_task)
        self.btn_cancel.grid(row=1, column=1, sticky="e")
        self.btn_cancel.state(["disabled"])

        # 5-Tab Notebook
        self.notebook = ttk.Notebook(main_container)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        # Create the tab frames
        self.tab_rip = ttk.Frame(self.notebook, padding=10)
        self.tab_convert = ttk.Frame(self.notebook, padding=10)
        self.tab_stitch = ttk.Frame(self.notebook, padding=10)
        self.tab_audio = ttk.Frame(self.notebook, padding=10)
        self.tab_browser = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_rip, text="Live Disc Ripper")
        self.notebook.add(self.tab_convert, text="Image Converter")
        self.notebook.add(self.tab_stitch, text="Video Stitcher")
        self.notebook.add(self.tab_audio, text="Audio Extractor")
        self.notebook.add(self.tab_browser, text="File Library")

        self.build_tab_rip()
        self.build_tab_convert()
        self.build_tab_stitch()
        self.build_tab_audio()
        self.build_tab_browser()

    # ── TAB 1: Live Disc Ripper ────────────────────────────────────────────

    def build_tab_rip(self):
        self.tab_rip.grid_rowconfigure(2, weight=1)
        self.tab_rip.grid_columnconfigure(0, weight=1)

        # Drives section
        drives_frame = ttk.LabelFrame(self.tab_rip, text=" Detected Optical Drives ", padding=10)
        drives_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        drives_frame.grid_columnconfigure(0, weight=1)

        self.drive_select = ttk.Combobox(drives_frame, state="readonly")
        self.drive_select.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        btn_refresh = ttk.Button(drives_frame, text="Scan Drives", command=self.scan_drives)
        btn_refresh.grid(row=0, column=1, sticky="e")

        # Initial drive scan
        self.scan_drives()

        # Rip settings
        rip_settings = ttk.LabelFrame(self.tab_rip, text=" Ripping Mode & Target ", padding=10)
        rip_settings.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        rip_settings.grid_columnconfigure(1, weight=1)

        # Ripping Type Options
        ttk.Label(rip_settings, text="Select Rip Type:").grid(row=0, column=0, sticky="w", pady=5)
        self.rip_type = tk.StringVar(value="VCD")
        
        modes_frame = ttk.Frame(rip_settings)
        modes_frame.grid(row=0, column=1, columnspan=2, sticky="w")
        
        r1 = ttk.Radiobutton(modes_frame, text="Video CD (VCD) to MP4", variable=self.rip_type, value="VCD", command=self.on_rip_type_change)
        r1.pack(side="left", padx=(0, 15))
        r2 = ttk.Radiobutton(modes_frame, text="Audio CD to MP3/WAV", variable=self.rip_type, value="CDDA", command=self.on_rip_type_change)
        r2.pack(side="left", padx=(0, 15))
        r3 = ttk.Radiobutton(modes_frame, text="DVD Movie to MP4", variable=self.rip_type, value="DVD", command=self.on_rip_type_change)
        r3.pack(side="left")

        # Sub-options frame for Audio CD format
        self.audio_rip_opts = ttk.Frame(rip_settings)
        self.audio_rip_opts.grid(row=1, column=0, columnspan=3, sticky="w", pady=5)
        ttk.Label(self.audio_rip_opts, text="Audio Format:").pack(side="left", padx=(0, 10))
        self.audio_rip_format = tk.StringVar(value="mp3")
        ttk.Radiobutton(self.audio_rip_opts, text="MP3 (High Quality)", variable=self.audio_rip_format, value="mp3").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(self.audio_rip_opts, text="WAV (Lossless PCM)", variable=self.audio_rip_format, value="wav").pack(side="left")
        self.audio_rip_opts.grid_remove() # Hide by default

        # Output Folder Picker
        ttk.Label(rip_settings, text="Destination Folder:").grid(row=2, column=0, sticky="w", pady=5)
        self.rip_output_entry = ttk.Entry(rip_settings)
        self.rip_output_entry.grid(row=2, column=1, sticky="ew", padx=(0, 10))
        self.rip_output_entry.insert(0, self.workspace_dir)

        btn_browse = ttk.Button(rip_settings, text="Browse...", command=lambda: self.browse_folder(self.rip_output_entry))
        btn_browse.grid(row=2, column=2, sticky="e")

        # Action Buttons Frame
        action_frame = ttk.Frame(self.tab_rip)
        action_frame.grid(row=2, column=0, sticky="n", pady=20)

        btn_rip = ttk.Button(action_frame, text="Start Ripping Process", style="Accent.TButton", command=self.start_ripping)
        btn_rip.pack(pady=10)

    def scan_drives(self):
        drives = engine.detect_optical_drives()
        if drives:
            list_vals = [f"{d['drive_letter']} ({d['name']})" for d in drives]
            self.drive_select['values'] = list_vals
            self.drive_select.current(0)
            self.write_log(f"[INFO] Scanning Drives: Detected {len(drives)} drive(s).\n")
        else:
            self.drive_select['values'] = ["No physical optical drives detected"]
            self.drive_select.current(0)
            self.write_log("[INFO] Drive detection scanned: No optical drives connected.\n")

    def on_rip_type_change(self):
        if self.rip_type.get() == "CDDA":
            self.audio_rip_opts.grid()
        else:
            self.audio_rip_opts.grid_remove()

    def browse_folder(self, entry_widget):
        folder = filedialog.askdirectory(initialdir=entry_widget.get())
        if folder:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, os.path.abspath(folder))

    def start_ripping(self):
        drive_str = self.drive_select.get()
        if not drive_str or "No physical" in drive_str:
            messagebox.showwarning("Optical Drive Missing", "Please select or connect a valid optical CD/DVD drive first.")
            return

        drive_letter = drive_str.split(" ")[0].strip()
        output_dir = self.rip_output_entry.get().strip()
        rip_type = self.rip_type.get()

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create output directory: {e}")
                return

        self.btn_cancel.state(["!disabled"])
        self.cancel_event.clear()
        self.progress_val.set(0)

        if rip_type == "VCD":
            self.active_thread = threading.Thread(target=self.thread_rip_vcd, args=(drive_letter, output_dir))
        elif rip_type == "DVD":
            self.active_thread = threading.Thread(target=self.thread_rip_dvd, args=(drive_letter, output_dir))
        else:
            self.active_thread = threading.Thread(target=self.thread_rip_cdda, args=(drive_letter, output_dir))
        
        self.active_thread.start()

    def thread_rip_vcd(self, drive_letter, output_dir):
        self.log_queue.put("[RIPPING VCD] Scanning VCD directory structure...\n")
        mpegav_path = os.path.join(drive_letter, "MPEGAV")
        if not os.path.exists(mpegav_path):
            # Try lowercase or fallback
            mpegav_path = os.path.join(drive_letter, "mpegav")
            if not os.path.exists(mpegav_path):
                self.log_queue.put(f"[ERROR] Could not find VCD video directory MPEGAV on drive {drive_letter}. Ensure VCD disc is present.\n")
                self.progress_queue.put(0)
                self.log_queue.put("VCD Rip Failed.\n")
                return

        dat_files = glob.glob(os.path.join(mpegav_path, "*.DAT")) + glob.glob(os.path.join(mpegav_path, "*.dat"))
        if not dat_files:
            self.log_queue.put("[ERROR] No VCD video tracks (*.DAT files) found in drive directory.\n")
            return

        self.log_queue.put(f"[INFO] Found {len(dat_files)} video track(s) on VCD.\n")
        for i, dat_file in enumerate(dat_files, 1):
            if self.cancel_event.is_set():
                break
            out_file = os.path.join(output_dir, f"VCD_Track_{i:02d}.mp4")
            self.log_queue.put(f"[INFO] Processing VCD track {i}: {os.path.basename(dat_file)} → {os.path.basename(out_file)}\n")
            
            # Since VCD DAT files are basically raw MPEG-1 video with standard timestamps, we can convert
            # using engine.reencode_video_ffmpeg directly
            def update_progress(pct):
                self.progress_queue.put(pct)

            success = engine.reencode_video_ffmpeg(
                input_path=dat_file,
                output_path=out_file,
                logger=lambda msg: self.log_queue.put(msg + "\n"),
                progress_callback=update_progress,
                cancel_event=self.cancel_event
            )
            if success:
                self.log_queue.put(f"[SUCCESS] Transcoded VCD track {i} saved successfully!\n")
            else:
                self.log_queue.put(f"[WARNING] Transcoding failed for VCD track {i}.\n")

        self.log_queue.put("VCD Ripping complete.\n")
        self.progress_queue.put(100)

    def thread_rip_dvd(self, drive_letter, output_dir):
        self.log_queue.put("[RIPPING DVD] Checking DVD file structure...\n")
        video_ts = os.path.join(drive_letter, "VIDEO_TS")
        if not os.path.exists(video_ts):
            self.log_queue.put(f"[ERROR] Could not find DVD video directory VIDEO_TS on drive {drive_letter}.\n")
            return

        out_file = os.path.join(output_dir, "DVD_Rip_Output.mp4")
        self.log_queue.put(f"[INFO] Extracting DVD primary video titles to: {out_file}\n")

        ffmpeg = engine.get_ffmpeg_path()
        # Find all primary VOB sequences (usually VTS_01_1.VOB etc. join sequentially)
        vob_files = sorted(glob.glob(os.path.join(video_ts, "VTS_0[1-9]_[1-9].VOB")))
        if not vob_files:
            self.log_queue.put("[WARNING] No main title VOB files discovered. Ripping raw ISO or IFO isn't fully supported. Trying to map drive directly.\n")
            # Attempt to map drive directly
            cmd = [ffmpeg, "-y", "-i", f"concat:{video_ts}/VTS_01_1.VOB|{video_ts}/VTS_01_2.VOB", "-c:v", "libx264", "-preset", "fast", out_file]
        else:
            self.log_queue.put(f"[INFO] Found {len(vob_files)} main video VOB segments. Concatenating...\n")
            # Build concatenation string
            concat_str = "concat:" + "|".join(vob_files)
            cmd = [ffmpeg, "-y", "-i", concat_str, "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", out_file]

        self.log_queue.put(f"Executing: {' '.join(cmd)}\n")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        while True:
            if self.cancel_event.is_set():
                process.terminate()
                self.log_queue.put("DVD rip cancelled by user.\n")
                break
            line = process.stderr.readline()
            if not line:
                break
            if "time=" in line:
                self.log_queue.put(line.strip() + "\n")
        
        process.wait()
        if process.returncode == 0:
            self.log_queue.put("[SUCCESS] DVD main titles extracted to MP4 successfully!\n")
        else:
            self.log_queue.put("[ERROR] DVD extraction failed.\n")
        self.progress_queue.put(100)

    def thread_rip_cdda(self, drive_letter, output_dir):
        self.log_queue.put(f"[RIPPING AUDIO CD] Attempting CDDA rip on drive {drive_letter}...\n")
        fmt = self.audio_rip_format.get()
        
        # Audio CDs on Windows cannot be accessed via simple copy since .cda are virtual links.
        # We try calling ffmpeg with cdda input if supported
        ffmpeg = engine.get_ffmpeg_path()
        
        # On Windows, drive letter format for cdda is 'cdda://[drive_letter]:'
        # Or cdda://D
        letter_clean = drive_letter.replace(":", "").strip()
        
        self.log_queue.put(f"[INFO] Ripping tracks using cdda protocol on drive {letter_clean}...\n")
        # Try to rip multiple tracks (typically track 1 up to 30)
        ripped_count = 0
        for track in range(1, 40):
            if self.cancel_event.is_set():
                break
            out_file = os.path.join(output_dir, f"track_{track:02d}.{fmt}")
            
            # command pattern: ffmpeg -f cdda -track_num X -i [drive_letter] output
            # Actually, standard ffmpeg syntax is: ffmpeg -i cdda://[drive_letter]:[track] output
            # For example: ffmpeg -i cdda://D:2 output.wav
            cmd = [ffmpeg, "-y", "-i", f"cdda://{letter_clean}:{track}", out_file]
            
            self.log_queue.put(f"Ripping track {track}: Command: {' '.join(cmd)}\n")
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                self.log_queue.put(f"[SUCCESS] Extracted track {track} successfully → {os.path.basename(out_file)}\n")
                ripped_count += 1
            else:
                # If track 1 fails, the drive might not have an Audio CD, or format is unsupported
                if track == 1:
                    self.log_queue.put("[ERROR] Track 1 rip failed. The drive might be empty, or your ffmpeg version does not support Windows cdda:// protocol.\n")
                    self.log_queue.put("Hint: You can rip the disc as a raw image (.bin/.cue) using tools like ImgBurn, then use the 'Image Converter' tab to split it into tracks natively.\n")
                    break
                else:
                    # Normal: reached end of CD tracks
                    self.log_queue.put(f"[INFO] Completed audio CD tracks. Total tracks ripped: {ripped_count}\n")
                    break
        
        self.progress_queue.put(100)

    # ── TAB 2: Image/File Converter ────────────────────────────────────────

    def build_tab_convert(self):
        self.tab_convert.grid_rowconfigure(2, weight=1)
        self.tab_convert.grid_columnconfigure(0, weight=1)

        # Mode Selector
        conv_modes = ttk.LabelFrame(self.tab_convert, text=" Select Operation Mode ", padding=10)
        conv_modes.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        conv_modes.grid_columnconfigure(0, weight=1)

        self.conv_mode_var = tk.StringVar(value="BIN_SPLIT")
        
        # Grid of modes
        r1 = ttk.Radiobutton(conv_modes, text="Split BIN + CUE sheet into individual tracks (NATIVE)", variable=self.conv_mode_var, value="BIN_SPLIT", command=self.on_conv_mode_change)
        r1.grid(row=0, column=0, sticky="w", pady=2)
        r2 = ttk.Radiobutton(conv_modes, text="Mode A: Raw VCD XA sector file (.mpg raw CD image) → MP4", variable=self.conv_mode_var, value="MODE_A", command=self.on_conv_mode_change)
        r2.grid(row=1, column=0, sticky="w", pady=2)
        r3 = ttk.Radiobutton(conv_modes, text="Mode B: Fix broken MP4 (re-encode timestamps)", variable=self.conv_mode_var, value="MODE_B", command=self.on_conv_mode_change)
        r3.grid(row=2, column=0, sticky="w", pady=2)
        r4 = ttk.Radiobutton(conv_modes, text="Mode C: Concat multiple raw VCD XA files → single MP4", variable=self.conv_mode_var, value="MODE_C", command=self.on_conv_mode_change)
        r4.grid(row=3, column=0, sticky="w", pady=2)
        r5 = ttk.Radiobutton(conv_modes, text="Convert TOC sheet → CUE sheet", variable=self.conv_mode_var, value="TOC_CUE", command=self.on_conv_mode_change)
        r5.grid(row=4, column=0, sticky="w", pady=2)

        # Inputs section
        inputs_frame = ttk.LabelFrame(self.tab_convert, text=" Source & Target Options ", padding=10)
        inputs_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        inputs_frame.grid_columnconfigure(1, weight=1)

        # File input picker
        self.lbl_src_file = ttk.Label(inputs_frame, text="Select Source File:")
        self.lbl_src_file.grid(row=0, column=0, sticky="w", pady=5)
        self.conv_src_entry = ttk.Entry(inputs_frame)
        self.conv_src_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.btn_conv_src = ttk.Button(inputs_frame, text="Select File", command=self.select_conv_source)
        self.btn_conv_src.grid(row=0, column=2, sticky="e")

        # Multi-file inputs (only for Mode C)
        self.lbl_multi_files = ttk.Label(inputs_frame, text="Mode C Source Files:")
        self.conv_multi_entry = ttk.Entry(inputs_frame)
        self.btn_conv_multi = ttk.Button(inputs_frame, text="Select Multiple Files", command=self.select_conv_multi_sources)

        # Output file/directory picker
        self.lbl_dst = ttk.Label(inputs_frame, text="Destination Folder:")
        self.lbl_dst.grid(row=1, column=0, sticky="w", pady=5)
        self.conv_dst_entry = ttk.Entry(inputs_frame)
        self.conv_dst_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.conv_dst_entry.insert(0, self.workspace_dir)
        self.btn_conv_dst = ttk.Button(inputs_frame, text="Select Folder", command=self.select_conv_dest)
        self.btn_conv_dst.grid(row=1, column=2, sticky="e")

        # Action Buttons
        action_frame = ttk.Frame(self.tab_convert)
        action_frame.grid(row=2, column=0, sticky="n", pady=10)

        btn_run = ttk.Button(action_frame, text="Execute Conversion", style="Accent.TButton", command=self.start_conversion)
        btn_run.pack()

    def on_conv_mode_change(self):
        mode = self.conv_mode_var.get()
        # Reset and rearrange inputs based on selected mode
        if mode == "BIN_SPLIT":
            self.lbl_src_file.config(text="Select CUE Sheet File:")
            self.lbl_dst.config(text="Destination Folder:")
            self.lbl_multi_files.grid_remove()
            self.conv_multi_entry.grid_remove()
            self.btn_conv_multi.grid_remove()
            self.lbl_src_file.grid()
            self.conv_src_entry.grid()
            self.btn_conv_src.grid()
            self.btn_conv_dst.config(text="Select Folder", command=self.select_conv_dest)
        elif mode == "TOC_CUE":
            self.lbl_src_file.config(text="Select TOC File:")
            self.lbl_dst.config(text="Target CUE Output File:")
            self.lbl_multi_files.grid_remove()
            self.conv_multi_entry.grid_remove()
            self.btn_conv_multi.grid_remove()
            self.lbl_src_file.grid()
            self.conv_src_entry.grid()
            self.btn_conv_src.grid()
            self.btn_conv_dst.config(text="Select Save File", command=self.select_conv_dest_file)
        elif mode == "MODE_C":
            # Show multi files
            self.lbl_src_file.grid_remove()
            self.conv_src_entry.grid_remove()
            self.btn_conv_src.grid_remove()
            
            self.lbl_multi_files.grid(row=0, column=0, sticky="w", pady=5)
            self.conv_multi_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
            self.btn_conv_multi.grid(row=0, column=2, sticky="e")
            self.lbl_dst.config(text="Target MP4 Output File:")
            self.btn_conv_dst.config(text="Select Save File", command=self.select_conv_dest_file)
        else: # MODE_A or MODE_B
            self.lbl_src_file.config(text="Select Input Video File:")
            self.lbl_dst.config(text="Target MP4 Output File:")
            self.lbl_multi_files.grid_remove()
            self.conv_multi_entry.grid_remove()
            self.btn_conv_multi.grid_remove()
            self.lbl_src_file.grid()
            self.conv_src_entry.grid()
            self.btn_conv_src.grid()
            self.btn_conv_dst.config(text="Select Save File", command=self.select_conv_dest_file)

    def select_conv_source(self):
        mode = self.conv_mode_var.get()
        if mode == "BIN_SPLIT":
            ftype = [("CUE Sheets", "*.cue")]
        elif mode == "TOC_CUE":
            ftype = [("TOC Files", "*.toc")]
        else:
            ftype = [("All Video files", "*.mp4;*.bin;*.mpg;*.mpeg;*.avi;*.mkv;*.mov"), ("All Files", "*.*")]
        
        file_path = filedialog.askopenfilename(initialdir=self.workspace_dir, filetypes=ftype)
        if file_path:
            self.conv_src_entry.delete(0, tk.END)
            self.conv_src_entry.insert(0, os.path.abspath(file_path))

    def select_conv_multi_sources(self):
        ftypes = [("VCD Streams/MPEG", "*.mpg;*.mpeg;*.bin;*.dat"), ("All Files", "*.*")]
        files = filedialog.askopenfilenames(initialdir=self.workspace_dir, filetypes=ftypes)
        if files:
            files_abs = [os.path.abspath(f) for f in files]
            self.conv_multi_entry.delete(0, tk.END)
            self.conv_multi_entry.insert(0, "; ".join(files_abs))

    def select_conv_dest(self):
        folder = filedialog.askdirectory(initialdir=self.workspace_dir)
        if folder:
            self.conv_dst_entry.delete(0, tk.END)
            self.conv_dst_entry.insert(0, os.path.abspath(folder))

    def select_conv_dest_file(self):
        mode = self.conv_mode_var.get()
        if mode == "TOC_CUE":
            ftype = [("CUE Sheets", "*.cue")]
            def_ext = ".cue"
        else:
            ftype = [("MP4 Video", "*.mp4"), ("Matroska Video", "*.mkv")]
            def_ext = ".mp4"
            
        file_path = filedialog.asksaveasfilename(initialdir=self.workspace_dir, filetypes=ftype, defaultextension=def_ext)
        if file_path:
            self.conv_dst_entry.delete(0, tk.END)
            self.conv_dst_entry.insert(0, os.path.abspath(file_path))

    def start_conversion(self):
        mode = self.conv_mode_var.get()
        src = self.conv_src_entry.get().strip() if mode != "MODE_C" else self.conv_multi_entry.get().strip()
        dst = self.conv_dst_entry.get().strip()

        if not src:
            messagebox.showwarning("Missing Inputs", "Please select source file(s) first.")
            return
        if not dst:
            messagebox.showwarning("Missing Inputs", "Please specify destination location.")
            return

        self.btn_cancel.state(["!disabled"])
        self.cancel_event.clear()
        self.progress_val.set(0)

        self.active_thread = threading.Thread(target=self.thread_convert, args=(mode, src, dst))
        self.active_thread.start()

    def thread_convert(self, mode, src, dst):
        try:
            if mode == "BIN_SPLIT":
                self.log_queue.put(f"[CONVERSION] Executing Native CUE/BIN Splitting...\n")
                engine.split_bin_cue(
                    cue_path=src,
                    output_dir=dst,
                    convert_to_mpg=True,
                    logger=lambda msg: self.log_queue.put(msg + "\n")
                )
                self.progress_queue.put(100)
                
            elif mode == "TOC_CUE":
                self.log_queue.put(f"[CONVERSION] Converting TOC file {os.path.basename(src)} → CUE...\n")
                res_cue = engine.convert_toc_to_cue(
                    toc_path=src,
                    cue_path=dst,
                    logger=lambda msg: self.log_queue.put(msg + "\n")
                )
                self.progress_queue.put(100)
                self.log_queue.put(f"[SUCCESS] CUE sheet written: {res_cue}\n")

            elif mode == "MODE_A":
                self.log_queue.put(f"[CONVERSION: MODE A] Extracting and transcodig VCD XA Image {os.path.basename(src)}...\n")
                # Step 1: raw extract
                tmp_dir = os.path.dirname(dst)
                import tempfile
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mpeg.tmp", dir=tmp_dir)
                os.close(tmp_fd)
                
                try:
                    self.log_queue.put("[Step 1/2] Stripping raw CD-ROM sector XA headers...\n")
                    written = engine.extract_xa_to_file(
                        src_path=src,
                        dst_path=tmp_path,
                        logger=lambda msg: self.log_queue.put(msg + "\n"),
                        progress_update=lambda pct: self.progress_queue.put(pct * 0.4) # 40% contribution
                    )
                    
                    if written == 0 or self.cancel_event.is_set():
                        self.log_queue.put("[ERROR] No MPEG sectors found or task was cancelled.\n")
                        return

                    # Step 2: re-encode
                    vbr = engine.probe_video_bitrate(tmp_path)
                    self.log_queue.put(f"[Step 2/2] Transcoding to clean sequential timestamps (VBR: {vbr})...\n")
                    
                    def reencode_prog(pct):
                        self.progress_queue.put(40 + (pct * 0.6)) # Remaining 60%

                    ok = engine.reencode_video_ffmpeg(
                        input_path=tmp_path,
                        output_path=dst,
                        vbitrate=vbr,
                        logger=lambda msg: self.log_queue.put(msg + "\n"),
                        progress_callback=reencode_prog,
                        cancel_event=self.cancel_event
                    )
                    if ok:
                        self.log_queue.put(f"[SUCCESS] Mode A Processing Complete: {dst}\n")
                    else:
                        self.log_queue.put("[ERROR] ffmpeg transcoding failed.\n")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                self.progress_queue.put(100)

            elif mode == "MODE_B":
                self.log_queue.put(f"[CONVERSION: MODE B] Fixing video timestamps for: {os.path.basename(src)}...\n")
                vbr = engine.probe_video_bitrate(src)
                
                def prog(pct):
                    self.progress_queue.put(pct)

                ok = engine.reencode_video_ffmpeg(
                    input_path=src,
                    output_path=dst,
                    vbitrate=vbr,
                    logger=lambda msg: self.log_queue.put(msg + "\n"),
                    progress_callback=prog,
                    cancel_event=self.cancel_event
                )
                if ok:
                    self.log_queue.put(f"[SUCCESS] Mode B Video Fixed: {dst}\n")
                else:
                    self.log_queue.put("[ERROR] Timestamp fix failed.\n")
                self.progress_queue.put(100)

            elif mode == "MODE_C":
                self.log_queue.put(f"[CONVERSION: MODE C] Joining and fixing multiple XA streams...\n")
                files_list = [f.strip() for f in src.split(";")]
                self.log_queue.put(f"Source paths:\n" + "\n".join([f"  → {p}" for p in files_list]) + "\n")
                
                # Extract and concat
                tmp_paths = []
                try:
                    self.log_queue.put("[Step 1/2] Stripping XA headers on all files...\n")
                    tmp_dir = os.path.dirname(dst)
                    for idx, src_p in enumerate(files_list, 1):
                        if self.cancel_event.is_set():
                            break
                        label = f"{idx}/{len(files_list)} {os.path.basename(src_p)}"
                        tmp_fd, tmp_p = tempfile.mkstemp(suffix=f".seg{idx}.tmp", dir=tmp_dir)
                        os.close(tmp_fd)
                        tmp_paths.append(tmp_p)

                        engine.extract_xa_to_file(
                            src_path=src_p,
                            dst_path=tmp_p,
                            label=label,
                            logger=lambda msg: self.log_queue.put(msg + "\n")
                        )
                    
                    if not tmp_paths or self.cancel_event.is_set():
                        return

                    # Re-encode and concat
                    vbr = engine.probe_video_bitrate(tmp_paths[0])
                    self.log_queue.put(f"[Step 2/2] Concatenating + Transcoding (VBR: {vbr})...\n")
                    
                    def prog_c(pct):
                        self.progress_queue.put(pct)

                    ok = engine.reencode_concat_ffmpeg(
                        raw_paths=tmp_paths,
                        output_path=dst,
                        vbitrate=vbr,
                        logger=lambda msg: self.log_queue.put(msg + "\n"),
                        progress_callback=prog_c,
                        cancel_event=self.cancel_event
                    )
                    if ok:
                        self.log_queue.put(f"[SUCCESS] Mode C Multistream stitch complete: {dst}\n")
                    else:
                        self.log_queue.put("[ERROR] Multistream stitch failed.\n")
                finally:
                    for p in tmp_paths:
                        if os.path.exists(p):
                            os.remove(p)
                self.progress_queue.put(100)
        except Exception as e:
            self.log_queue.put(f"[ERROR] Task encounter exceptions: {e}\n", is_error=True)
            self.progress_queue.put(0)

    # ── TAB 3: Video Stitcher ──────────────────────────────────────────────

    def build_tab_stitch(self):
        self.tab_stitch.grid_rowconfigure(1, weight=1)
        self.tab_stitch.grid_columnconfigure(0, weight=1)

        # File listbox controls
        list_frame = ttk.LabelFrame(self.tab_stitch, text=" Selected Video Segments (in stitch order) ", padding=10)
        list_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.stitch_listbox = tk.Listbox(list_frame, bg=COLOR_CONSOLE_BG, fg=COLOR_TEXT, 
                                         selectbackground=COLOR_PRIMARY, selectforeground=COLOR_TEXT, borderwidth=0)
        self.stitch_listbox.grid(row=0, column=0, sticky="nsew")

        # Scrollbar for listbox
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.stitch_listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.stitch_listbox.config(yscrollcommand=sb.set)

        # Control panel on right
        control_frame = ttk.Frame(self.tab_stitch, padding=5)
        control_frame.grid(row=0, column=1, sticky="ns")

        btn_add = ttk.Button(control_frame, text="Add Videos...", command=self.stitch_add_files)
        btn_add.pack(fill="x", pady=2)
        btn_remove = ttk.Button(control_frame, text="Remove Selected", command=self.stitch_remove_file)
        btn_remove.pack(fill="x", pady=2)
        btn_clear = ttk.Button(control_frame, text="Clear List", command=self.stitch_clear_list)
        btn_clear.pack(fill="x", pady=2)
        
        ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=10)

        btn_up = ttk.Button(control_frame, text="Move Track Up", command=lambda: self.stitch_move_file(-1))
        btn_up.pack(fill="x", pady=2)
        btn_down = ttk.Button(control_frame, text="Move Track Down", command=lambda: self.stitch_move_file(1))
        btn_down.pack(fill="x", pady=2)

        # Settings below
        settings_frame = ttk.LabelFrame(self.tab_stitch, text=" Stitching Mode & Output ", padding=10)
        settings_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)
        settings_frame.grid_columnconfigure(1, weight=1)

        self.stitch_reencode_var = tk.BooleanVar(value=False)
        chk_reencode = ttk.Checkbutton(settings_frame, text="Force re-encode videos (Slow, fixes mixed dimensions/resolutions)", variable=self.stitch_reencode_var)
        chk_reencode.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 5))

        ttk.Label(settings_frame, text="Output File Path:").grid(row=1, column=0, sticky="w")
        self.stitch_out_entry = ttk.Entry(settings_frame)
        self.stitch_out_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.stitch_out_entry.insert(0, os.path.join(self.workspace_dir, "stitched_output.mp4"))

        btn_out_browse = ttk.Button(settings_frame, text="Browse Save...", command=self.stitch_browse_output)
        btn_out_browse.grid(row=1, column=2, sticky="e")

        # Action Buttons
        action_btn_frame = ttk.Frame(self.tab_stitch)
        action_btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        btn_stitch = ttk.Button(action_btn_frame, text="Stitch Video Clips", style="Accent.TButton", command=self.start_stitch)
        btn_stitch.pack()

    def stitch_add_files(self):
        ftype = [("Video Files", "*.mp4;*.mpg;*.mpeg;*.avi;*.mkv;*.mov"), ("All Files", "*.*")]
        paths = filedialog.askopenfilenames(initialdir=self.workspace_dir, filetypes=ftype)
        if paths:
            for p in paths:
                p_abs = os.path.abspath(p)
                if p_abs not in self.stitch_files_list:
                    self.stitch_files_list.append(p_abs)
                    self.stitch_listbox.insert(tk.END, os.path.basename(p_abs))

    def stitch_remove_file(self):
        sel = self.stitch_listbox.curselection()
        if sel:
            idx = sel[0]
            self.stitch_listbox.delete(idx)
            self.stitch_files_list.pop(idx)

    def stitch_clear_list(self):
        self.stitch_listbox.delete(0, tk.END)
        self.stitch_files_list.clear()

    def stitch_move_file(self, direction):
        sel = self.stitch_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if 0 <= new_idx < len(self.stitch_files_list):
            # Swap items in list
            self.stitch_files_list[idx], self.stitch_files_list[new_idx] = self.stitch_files_list[new_idx], self.stitch_files_list[idx]
            
            # Refresh listbox
            self.stitch_listbox.delete(0, tk.END)
            for f in self.stitch_files_list:
                self.stitch_listbox.insert(tk.END, os.path.basename(f))
            self.stitch_listbox.select_set(new_idx)

    def stitch_browse_output(self):
        file_path = filedialog.asksaveasfilename(initialdir=self.workspace_dir, filetypes=[("MP4 Video", "*.mp4"), ("MKV Video", "*.mkv")], defaultextension=".mp4")
        if file_path:
            self.stitch_out_entry.delete(0, tk.END)
            self.stitch_out_entry.insert(0, os.path.abspath(file_path))

    def start_stitch(self):
        if len(self.stitch_files_list) < 2:
            messagebox.showwarning("Incomplete List", "Stitch operation requires at least 2 files.")
            return

        out_path = self.stitch_out_entry.get().strip()
        if not out_path:
            messagebox.showwarning("Missing Output", "Please choose target output file path.")
            return

        self.btn_cancel.state(["!disabled"])
        self.cancel_event.clear()
        self.progress_val.set(0)

        reencode = self.stitch_reencode_var.get()
        self.active_thread = threading.Thread(target=self.thread_stitch, args=(self.stitch_files_list, out_path, reencode))
        self.active_thread.start()

    def thread_stitch(self, files, out_p, reencode):
        self.log_queue.put("[STITCH] Initiating video concatenation...\n")
        
        def prog(pct):
            self.progress_queue.put(pct)

        success = engine.stitch_videos(
            input_files=files,
            output_path=out_p,
            reencode=reencode,
            logger=lambda msg: self.log_queue.put(msg + "\n"),
            progress_callback=prog,
            cancel_event=self.cancel_event
        )

        if success:
            self.log_queue.put(f"[SUCCESS] Videos successfully stitched: {out_p}\n")
        else:
            self.log_queue.put("[ERROR] Stitch process failed or cancelled.\n")
        
        self.progress_queue.put(100)

    # ── TAB 4: Audio Extractor ─────────────────────────────────────────────

    def build_tab_audio(self):
        self.tab_audio.grid_columnconfigure(0, weight=1)

        # Source Frame
        src_frame = ttk.LabelFrame(self.tab_audio, text=" Source Settings ", padding=10)
        src_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        src_frame.grid_columnconfigure(1, weight=1)

        self.audio_batch_var = tk.BooleanVar(value=False)
        chk_batch = ttk.Checkbutton(src_frame, text="Batch Process Mode (extract audio from all files in a folder)", variable=self.audio_batch_var, command=self.on_audio_batch_change)
        chk_batch.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.lbl_audio_src = ttk.Label(src_frame, text="Select Source File:")
        self.lbl_audio_src.grid(row=1, column=0, sticky="w")
        self.audio_src_entry = ttk.Entry(src_frame)
        self.audio_src_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.btn_audio_src_browse = ttk.Button(src_frame, text="Select File", command=self.audio_browse_src)
        self.btn_audio_src_browse.grid(row=1, column=2, sticky="e")

        # Destination Frame
        dst_frame = ttk.LabelFrame(self.tab_audio, text=" Output Settings ", padding=10)
        dst_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        dst_frame.grid_columnconfigure(1, weight=1)

        # Audio Format choices
        ttk.Label(dst_frame, text="Target Audio Format:").grid(row=0, column=0, sticky="w", pady=5)
        self.audio_format_select = ttk.Combobox(dst_frame, state="readonly", values=["mp3", "wav", "flac", "aac"])
        self.audio_format_select.grid(row=0, column=1, sticky="w")
        self.audio_format_select.current(0)
        self.audio_format_select.bind("<<ComboboxSelected>>", self.on_audio_format_change)

        # Output Target Picker
        self.lbl_audio_dst = ttk.Label(dst_frame, text="Target Output File:")
        self.lbl_audio_dst.grid(row=1, column=0, sticky="w", pady=5)
        self.audio_dst_entry = ttk.Entry(dst_frame)
        self.audio_dst_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.audio_dst_entry.insert(0, os.path.join(self.workspace_dir, "extracted_audio.mp3"))
        
        self.btn_audio_dst_browse = ttk.Button(dst_frame, text="Select Path", command=self.audio_browse_dst)
        self.btn_audio_dst_browse.grid(row=1, column=2, sticky="e")

        # Action Buttons
        action_btn_frame = ttk.Frame(self.tab_audio)
        action_btn_frame.grid(row=2, column=0, pady=20)

        btn_extract = ttk.Button(action_btn_frame, text="Extract Audio", style="Accent.TButton", command=self.start_audio_extract)
        btn_extract.pack()

    def on_audio_batch_change(self):
        batch = self.audio_batch_var.get()
        if batch:
            self.lbl_audio_src.config(text="Select Source Folder:")
            self.btn_audio_src_browse.config(text="Select Folder", command=self.audio_browse_src_dir)
            self.lbl_audio_dst.config(text="Target Save Folder:")
            self.btn_audio_dst_browse.config(text="Select Folder", command=self.audio_browse_dst_dir)
            
            # Update path defaults to folder
            self.audio_dst_entry.delete(0, tk.END)
            self.audio_dst_entry.insert(0, self.workspace_dir)
        else:
            self.lbl_audio_src.config(text="Select Source File:")
            self.btn_audio_src_browse.config(text="Select File", command=self.audio_browse_src)
            self.lbl_audio_dst.config(text="Target Output File:")
            self.btn_audio_dst_browse.config(text="Select File", command=self.audio_browse_dst)
            
            self.audio_dst_entry.delete(0, tk.END)
            self.audio_dst_entry.insert(0, os.path.join(self.workspace_dir, "extracted_audio.mp3"))

    def on_audio_format_change(self, event=None):
        if not self.audio_batch_var.get():
            fmt = self.audio_format_select.get()
            curr_path = self.audio_dst_entry.get().strip()
            if curr_path:
                base, _ = os.path.splitext(curr_path)
                self.audio_dst_entry.delete(0, tk.END)
                self.audio_dst_entry.insert(0, f"{base}.{fmt}")

    def audio_browse_src(self):
        ftype = [("Media Files (Video/Audio)", "*.mp4;*.mpg;*.mpeg;*.avi;*.mkv;*.mov;*.wav;*.mp3;*.dat"), ("All Files", "*.*")]
        path = filedialog.askopenfilename(initialdir=self.workspace_dir, filetypes=ftype)
        if path:
            self.audio_src_entry.delete(0, tk.END)
            self.audio_src_entry.insert(0, os.path.abspath(path))

    def audio_browse_src_dir(self):
        folder = filedialog.askdirectory(initialdir=self.workspace_dir)
        if folder:
            self.audio_src_entry.delete(0, tk.END)
            self.audio_src_entry.insert(0, os.path.abspath(folder))

    def audio_browse_dst_dir(self):
        folder = filedialog.askdirectory(initialdir=self.workspace_dir)
        if folder:
            self.audio_dst_entry.delete(0, tk.END)
            self.audio_dst_entry.insert(0, os.path.abspath(folder))

    def audio_browse_dst(self):
        fmt = self.audio_format_select.get()
        ftypes = [("Audio Files", f"*.{fmt}")]
        path = filedialog.asksaveasfilename(initialdir=self.workspace_dir, filetypes=ftypes, defaultextension=f".{fmt}")
        if path:
            self.audio_dst_entry.delete(0, tk.END)
            self.audio_dst_entry.insert(0, os.path.abspath(path))

    def start_audio_extract(self):
        src = self.audio_src_entry.get().strip()
        dst = self.audio_dst_entry.get().strip()
        
        if not src:
            messagebox.showwarning("Missing Inputs", "Please select source file or folder first.")
            return
        if not dst:
            messagebox.showwarning("Missing Inputs", "Please select destination output.")
            return

        self.btn_cancel.state(["!disabled"])
        self.cancel_event.clear()
        self.progress_val.set(0)

        fmt = self.audio_format_select.get()
        is_batch = self.audio_batch_var.get()

        self.active_thread = threading.Thread(target=self.thread_audio_extract, args=(src, dst, fmt, is_batch))
        self.active_thread.start()

    def thread_audio_extract(self, src, dst, fmt, is_batch):
        if is_batch:
            self.log_queue.put(f"[AUDIO EXTRACTION] Batch mode triggered on folder: {src}\n")
            # Discover files
            media_exts = ['*.mp4', '*.mpg', '*.mpeg', '*.avi', '*.mkv', '*.mov', '*.wav', '*.dat']
            files = []
            for ext in media_exts:
                files.extend(glob.glob(os.path.join(src, ext)))
                files.extend(glob.glob(os.path.join(src, ext.upper())))
            
            # Unique lists
            files = sorted(list(set(files)))
            if not files:
                self.log_queue.put("[WARNING] No media files detected in source folder.\n")
                self.progress_queue.put(100)
                return

            self.log_queue.put(f"[INFO] Discovered {len(files)} files to extract.\n")
            for i, f in enumerate(files, 1):
                if self.cancel_event.is_set():
                    break
                base_name = os.path.splitext(os.path.basename(f))[0]
                out_file = os.path.join(dst, f"{base_name}.{fmt}")
                self.log_queue.put(f"[BATCH {i}/{len(files)}] Processing: {os.path.basename(f)} → {os.path.basename(out_file)}\n")
                
                success = engine.extract_audio(
                    input_file=f,
                    output_path=out_file,
                    format_type=fmt,
                    logger=lambda msg: self.log_queue.put(msg + "\n"),
                    cancel_event=self.cancel_event
                )
                if success:
                    self.log_queue.put(f"[SUCCESS] Audio extracted: {os.path.basename(out_file)}\n")
                else:
                    self.log_queue.put(f"[WARNING] Extraction failed on {os.path.basename(f)}.\n")
                self.progress_queue.put((i / len(files)) * 100)

            self.log_queue.put("[INFO] Batch extraction complete.\n")
        else:
            self.log_queue.put(f"[AUDIO EXTRACTION] Extracting single audio file: {os.path.basename(src)}\n")
            
            def prog(pct):
                self.progress_queue.put(pct)

            success = engine.extract_audio(
                input_file=src,
                output_path=dst,
                format_type=fmt,
                logger=lambda msg: self.log_queue.put(msg + "\n"),
                progress_callback=prog,
                cancel_event=self.cancel_event
            )
            if success:
                self.log_queue.put(f"[SUCCESS] Audio file extracted to: {dst}\n")
            else:
                self.log_queue.put("[ERROR] Audio extraction failed.\n")
            
            self.progress_queue.put(100)

    # ── TAB 5: File Browser & Metadata ─────────────────────────────────────

    def build_tab_browser(self):
        self.tab_browser.grid_rowconfigure(1, weight=1)
        self.tab_browser.grid_columnconfigure(0, weight=1)
        self.tab_browser.grid_columnconfigure(1, weight=1)

        # Column 1: Files List
        files_frame = ttk.LabelFrame(self.tab_browser, text=" Workspace Directory Browser ", padding=10)
        files_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        files_frame.grid_rowconfigure(1, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)

        # Folder picker
        pick_frame = ttk.Frame(files_frame)
        pick_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        pick_frame.grid_columnconfigure(0, weight=1)

        self.browser_dir_entry = ttk.Entry(pick_frame)
        self.browser_dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.browser_dir_entry.insert(0, self.workspace_dir)

        btn_browse = ttk.Button(pick_frame, text="Choose Dir", command=self.browser_change_dir)
        btn_browse.grid(row=0, column=1, sticky="e")

        self.browser_listbox = tk.Listbox(files_frame, bg=COLOR_CONSOLE_BG, fg=COLOR_TEXT, 
                                          selectbackground=COLOR_PRIMARY, selectforeground=COLOR_TEXT, borderwidth=0)
        self.browser_listbox.grid(row=1, column=0, sticky="nsew")
        self.browser_listbox.bind("<<ListboxSelect>>", self.on_browser_file_selected)

        sb = ttk.Scrollbar(files_frame, orient="vertical", command=self.browser_listbox.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.browser_listbox.config(yscrollcommand=sb.set)

        # Load workspace directory list initially
        self.refresh_browser_list()

        # Column 2: Metadata Display
        meta_frame = ttk.LabelFrame(self.tab_browser, text=" Media Inspector & Metadata ", padding=10)
        meta_frame.grid(row=0, column=1, rowspan=2, sticky="nsew")
        meta_frame.grid_rowconfigure(0, weight=1)
        meta_frame.grid_columnconfigure(0, weight=1)

        self.meta_text = ScrolledText(meta_frame, bg=COLOR_CONSOLE_BG, fg=COLOR_TEXT, 
                                      font=("Consolas", 9), insertbackground=COLOR_TEXT, borderwidth=0)
        self.meta_text.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        
        # Action controls below metadata
        controls_frame = ttk.Frame(meta_frame)
        controls_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        btn_open = ttk.Button(controls_frame, text="Play/Open File", command=self.browser_open_file)
        btn_open.pack(side="left", padx=5)

        btn_refresh_meta = ttk.Button(controls_frame, text="Re-scan File", command=self.on_browser_file_selected)
        btn_refresh_meta.pack(side="left", padx=5)

    def browser_change_dir(self):
        folder = filedialog.askdirectory(initialdir=self.browser_dir_entry.get())
        if folder:
            self.browser_dir_entry.delete(0, tk.END)
            self.browser_dir_entry.insert(0, os.path.abspath(folder))
            self.refresh_browser_list()

    def refresh_browser_list(self):
        path = self.browser_dir_entry.get().strip()
        self.browser_listbox.delete(0, tk.END)
        if not os.path.exists(path):
            return

        try:
            for item in sorted(os.listdir(path)):
                # List directories and standard media/ripping extension formats
                full_p = os.path.join(path, item)
                if os.path.isdir(full_p):
                    self.browser_listbox.insert(tk.END, f"[DIR] {item}")
                elif os.path.splitext(item)[1].lower() in ['.mp4', '.mkv', '.bin', '.cue', '.toc', '.dat', '.mpg', '.mpeg', '.avi', '.wav', '.mp3']:
                    self.browser_listbox.insert(tk.END, item)
        except Exception as e:
            self.browser_listbox.insert(tk.END, f"Error: {e}")

    def on_browser_file_selected(self, event=None):
        sel = self.browser_listbox.curselection()
        if not sel:
            return
        
        item = self.browser_listbox.get(sel[0])
        current_dir = self.browser_dir_entry.get().strip()
        
        if item.startswith("[DIR]"):
            dir_name = item.replace("[DIR] ", "").strip()
            target_path = os.path.join(current_dir, dir_name)
            self.meta_text.delete(1.0, tk.END)
            self.meta_text.insert(tk.END, f"Directory Details:\n\nPath: {target_path}\nItems: {len(os.listdir(target_path))}")
            return
        
        full_path = os.path.join(current_dir, item)
        
        self.meta_text.delete(1.0, tk.END)
        self.meta_text.insert(tk.END, f"Inspecting: {item}\n")
        self.meta_text.insert(tk.END, f"File Size: {os.path.getsize(full_path) / (1024*1024):.2f} MB\n")
        self.meta_text.insert(tk.END, "────────────────────────────────────────────────────────────\n")

        # Run ffprobe information
        ffprobe = engine.get_ffprobe_path()
        if not ffprobe:
            self.meta_text.insert(tk.END, "[WARNING] ffprobe missing. Detailed codecs & streams metadata unavailable.")
            return

        def run_probe():
            try:
                cmd = [
                    ffprobe, "-v", "quiet",
                    "-show_format", "-show_streams",
                    "-print_format", "json",
                    full_path
                ]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    data = json.loads(res.stdout)
                    
                    # Custom formatting
                    out_lines = []
                    fmt = data.get('format', {})
                    out_lines.append(f"Format: {fmt.get('format_long_name', fmt.get('format_name', 'Unknown'))}")
                    
                    dur = fmt.get('duration')
                    if dur:
                        out_lines.append(f"Duration: {float(dur):.2f} seconds ({float(dur)//60:.0f}m {float(dur)%60:.1f}s)")
                        
                    bitrate = fmt.get('bit_rate')
                    if bitrate:
                        out_lines.append(f"Overall Bitrate: {int(bitrate)//1000} kbps")
                    
                    out_lines.append("\nStreams Details:")
                    for idx, stream in enumerate(data.get('streams', [])):
                        s_type = stream.get('codec_type')
                        codec = stream.get('codec_long_name', stream.get('codec_name', 'Unknown'))
                        out_lines.append(f"  Stream #{idx} ({s_type}): {codec}")
                        if s_type == 'video':
                            out_lines.append(f"    Resolution: {stream.get('width')}x{stream.get('height')}")
                            out_lines.append(f"    Framerate: {stream.get('r_frame_rate')} fps")
                        elif s_type == 'audio':
                            out_lines.append(f"    Sample Rate: {stream.get('sample_rate')} Hz")
                            out_lines.append(f"    Channels: {stream.get('channels')}")

                    self.safe_insert_meta("\n".join(out_lines))
                else:
                    self.safe_insert_meta(f"ffprobe lookup failed.\n{res.stderr}")
            except Exception as e:
                self.safe_insert_meta(f"Error inspecting metadata: {e}")

        # Probe in a separate thread so UI does not stutter
        threading.Thread(target=run_probe).start()

    def safe_insert_meta(self, txt):
        self.after(0, lambda: self._insert_meta(txt))

    def _insert_meta(self, txt):
        self.meta_text.insert(tk.END, txt)

    def browser_open_file(self):
        sel = self.browser_listbox.curselection()
        if not sel:
            return
        
        item = self.browser_listbox.get(sel[0])
        current_dir = self.browser_dir_entry.get().strip()
        
        if item.startswith("[DIR]"):
            dir_name = item.replace("[DIR] ", "").strip()
            self.browser_dir_entry.delete(0, tk.END)
            self.browser_dir_entry.insert(0, os.path.abspath(os.path.join(current_dir, dir_name)))
            self.refresh_browser_list()
            return

        full_path = os.path.join(current_dir, item)
        self.write_log(f"[INFO] Opening file: {full_path}\n")
        try:
            # Cross platform open file
            if sys.platform == 'win32':
                os.startfile(full_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', full_path])
            else:
                subprocess.run(['xdg-open', full_path])
        except Exception as e:
            messagebox.showerror("Error Opening File", f"Could not launch default player for: {full_path}\nError: {e}")

    # ── LOGGING & HELPERS ──────────────────────────────────────────────────

    def cancel_active_task(self):
        if messagebox.askyesno("Cancel Active Task", "Are you sure you want to stop/terminate the running conversion/transcoding process?"):
            self.cancel_event.set()
            self.log_queue.put("[CANCELLED] User requested cancellation. Stopping active thread...\n", is_error=True)
            self.btn_cancel.state(["disabled"])

    def write_log(self, text, is_error=False, is_success=False, is_info=False):
        if not hasattr(self, 'console'):
            print(text, end="", flush=True)
            return
        try:
            tag = None
            if is_error:
                tag = "error"
            elif is_success:
                tag = "success"
            elif is_info:
                tag = "info"
                
            self.console.insert(tk.END, text, tag)
            self.console.see(tk.END)
        except Exception:
            pass

    def process_queues(self):
        # Process log queue
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                is_err = "[ERROR]" in msg or "[CANCELLED]" in msg
                is_ok = "[SUCCESS]" in msg
                is_inf = "[INFO]" in msg or "[Step" in msg
                self.write_log(msg, is_error=is_err, is_success=is_ok, is_info=is_inf)
            except queue.Empty:
                break

        # Process progress queue
        while not self.progress_queue.empty():
            try:
                pct = self.progress_queue.get_nowait()
                self.progress_val.set(pct)
                if pct >= 100 or pct <= 0:
                    self.btn_cancel.state(["disabled"])
            except queue.Empty:
                break

        # Repeat
        self.after(100, self.process_queues)

if __name__ == "__main__":
    app = DiscMasterApp()
    app.mainloop()

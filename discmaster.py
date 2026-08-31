#!/usr/bin/env python3
"""
discmaster.py
─────────────
Classic GTK / Brasero-inspired desktop UI for DiscMaster.
Wraps discmaster_engine.py with an intuitive, multi-tab optical media recovery and processing studio.
"""

import os
import sys
import threading
import queue
import glob
import subprocess
import json
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from tkinter.scrolledtext import ScrolledText

# Import engine
try:
    import discmaster_engine as engine
except ImportError:
    # If run in subfolders, append parent dir
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import discmaster_engine as engine

# ── Classic GTK / Adwaita Desktop Theme Palette ─────────────────────────────
COLOR_BG = "#f5f6f7"          # Classic GTK / Adwaita window background
COLOR_SURFACE = "#ffffff"     # White content card / entry / listbox surface
COLOR_HEADER = "#ebecee"      # Header bar background
COLOR_HEADER_BORDER = "#d5d8dc"
COLOR_BORDER = "#cfd3d8"      # Clean GTK widget border
COLOR_BORDER_FOCUS = "#3584e4"# Focus blue
COLOR_TEXT = "#2e3436"        # Dark charcoal primary text (GNOME/GTK standard)
COLOR_TEXT_MUTED = "#5c616c"  # Secondary muted slate
COLOR_PRIMARY = "#3584e4"     # GNOME Adwaita Blue (Suggested Action)
COLOR_PRIMARY_HOVER = "#1c71d8"
COLOR_PRIMARY_ACTIVE = "#185fb4"
COLOR_BUTTON_BG = "#f0f2f4"   # Standard push button background
COLOR_BUTTON_HOVER = "#e4e7eb"
COLOR_BUTTON_ACTIVE = "#d3d8de"
COLOR_BUTTON_BORDER = "#bfc5cc"
COLOR_SUCCESS = "#26a269"     # GNOME Green
COLOR_WARNING = "#e5a50a"     # GNOME Amber
COLOR_ERROR = "#c01c28"       # GNOME Red / Destructive
COLOR_CONSOLE_BG = "#24292e"  # Adwaita dark terminal charcoal
COLOR_CONSOLE_FG = "#f6f8fa"  # Terminal light text
COLOR_CONSOLE_SEL = "#388bfd" # Terminal selection blue
COLOR_LIST_SEL = "#3584e4"    # Listbox selection blue


class DiscMasterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DiscMaster — Optical Copy, Recovery & Processing Studio")
        self.geometry("980x720")
        self.minsize(860, 600)
        self.configure(bg=COLOR_BG)

        # Set window icon if available
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "discmaster.png")
        if os.path.exists(icon_path):
            try:
                self.iconphoto(True, tk.PhotoImage(file=icon_path))
            except Exception:
                pass

        # Application state
        self.cancel_event = threading.Event()
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        self.active_thread = None
        self.stitch_files_list = []
        self.console_visible = True

        # Default paths
        self.workspace_dir = os.path.dirname(os.path.abspath(__file__))

        self.setup_styles()
        self.build_menu_bar()
        self.build_ui()
        
        # Check dependencies
        self.check_system_dependencies()

        # Keyboard shortcuts
        self.bind_shortcuts()

        # Start queue processing
        self.after(100, self.process_queues)

    def setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Determine best available system sans-serif font
        avail_families = tkfont.families()
        chosen_font = "Sans"
        for f in ["Inter", "Cantarell", "Ubuntu", "DejaVu Sans", "Liberation Sans", "Segoe UI"]:
            if f in avail_families:
                chosen_font = f
                break

        self.font_main = (chosen_font, 10)
        self.font_bold = (chosen_font, 10, "bold")
        self.font_sm = (chosen_font, 9)
        self.font_sm_italic = (chosen_font, 9, "italic")
        self.font_header = (chosen_font, 13, "bold")
        self.font_mono = ("DejaVu Sans Mono" if "DejaVu Sans Mono" in avail_families else "Consolas" if "Consolas" in avail_families else "monospace", 9)

        # Main window defaults
        style.configure(".",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_SURFACE,
            font=self.font_main
        )

        # Frame styles
        style.configure("TFrame", background=COLOR_BG)
        style.configure("Surface.TFrame", background=COLOR_SURFACE)
        style.configure("Header.TFrame", background=COLOR_HEADER)
        style.configure("Card.TFrame", background=COLOR_SURFACE, relief="solid", borderwidth=1)

        # LabelFrame styles (Classic GTK Group Box)
        style.configure("TLabelframe",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            borderwidth=1,
            relief="solid",
            lightcolor=COLOR_BORDER,
            darkcolor=COLOR_BORDER
        )
        style.configure("TLabelframe.Label",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            font=self.font_bold
        )

        # Tab styles (GTK Adwaita Notebook)
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("TNotebook.Tab",
            background="#e4e7eb",
            foreground=COLOR_TEXT_MUTED,
            padding=[14, 7],
            font=self.font_bold,
            borderwidth=1,
            relief="flat"
        )
        style.map("TNotebook.Tab",
            background=[("selected", COLOR_SURFACE), ("active", "#edeef0")],
            foreground=[("selected", COLOR_PRIMARY), ("active", COLOR_TEXT)],
            bordercolor=[("selected", COLOR_BORDER)]
        )

        # Label styles
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=self.font_main)
        style.configure("Surface.TLabel", background=COLOR_SURFACE, foreground=COLOR_TEXT, font=self.font_main)
        style.configure("Muted.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_MUTED, font=self.font_sm)
        style.configure("Status.TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=self.font_sm)
        
        style.configure("HeaderTitle.TLabel",
            background=COLOR_HEADER,
            foreground=COLOR_TEXT,
            font=self.font_header
        )
        style.configure("HeaderSub.TLabel",
            background=COLOR_HEADER,
            foreground=COLOR_TEXT_MUTED,
            font=self.font_sm_italic
        )

        # Standard Push Button (GTK bevel look)
        style.configure("TButton",
            background=COLOR_BUTTON_BG,
            foreground=COLOR_TEXT,
            borderwidth=1,
            relief="raised",
            padding=[10, 5],
            font=self.font_main
        )
        style.map("TButton",
            background=[("pressed", COLOR_BUTTON_ACTIVE), ("active", COLOR_BUTTON_HOVER), ("disabled", "#f0f2f4")],
            foreground=[("disabled", "#a0a4a8")],
            relief=[("pressed", "sunken"), ("!pressed", "raised")]
        )

        # Primary / Suggested Action Button (GTK Adwaita Blue)
        style.configure("Suggested.TButton",
            background=COLOR_PRIMARY,
            foreground="#ffffff",
            borderwidth=1,
            relief="raised",
            padding=[14, 6],
            font=self.font_bold
        )
        style.map("Suggested.TButton",
            background=[("pressed", COLOR_PRIMARY_ACTIVE), ("active", COLOR_PRIMARY_HOVER), ("disabled", "#9bbfe9")],
            foreground=[("disabled", "#f0f4f8")]
        )
        # Compatibility alias
        style.configure("Accent.TButton",
            background=COLOR_PRIMARY,
            foreground="#ffffff",
            borderwidth=1,
            relief="raised",
            padding=[14, 6],
            font=self.font_bold
        )
        style.map("Accent.TButton",
            background=[("pressed", COLOR_PRIMARY_ACTIVE), ("active", COLOR_PRIMARY_HOVER), ("disabled", "#9bbfe9")],
            foreground=[("disabled", "#f0f4f8")]
        )

        # Destructive Action Button (GTK Red)
        style.configure("Destructive.TButton",
            background=COLOR_ERROR,
            foreground="#ffffff",
            borderwidth=1,
            relief="raised",
            padding=[10, 5],
            font=self.font_bold
        )
        style.map("Destructive.TButton",
            background=[("pressed", "#a51d24"), ("active", "#e01b24"), ("disabled", "#e8a7ad")],
            foreground=[("disabled", "#ffffff")]
        )
        # Compatibility alias
        style.configure("Cancel.TButton",
            background=COLOR_ERROR,
            foreground="#ffffff",
            borderwidth=1,
            relief="raised",
            padding=[10, 5],
            font=self.font_bold
        )
        style.map("Cancel.TButton",
            background=[("pressed", "#a51d24"), ("active", "#e01b24"), ("disabled", "#e8a7ad")],
            foreground=[("disabled", "#ffffff")]
        )

        # Radio & Check buttons
        style.configure("TRadiobutton", background=COLOR_BG, foreground=COLOR_TEXT, font=self.font_main)
        style.configure("TCheckbutton", background=COLOR_BG, foreground=COLOR_TEXT, font=self.font_main)

        # Combobox / Entry styles
        style.configure("TCombobox", fieldbackground=COLOR_SURFACE, background=COLOR_BUTTON_BG, foreground=COLOR_TEXT, padding=4)
        style.configure("TEntry", fieldbackground=COLOR_SURFACE, foreground=COLOR_TEXT, borderwidth=1, padding=4)

        # Progressbar
        style.configure("TProgressbar",
            thickness=14,
            troughcolor="#e2e5e8",
            background=COLOR_PRIMARY,
            borderwidth=1,
            relief="flat"
        )

        # Separator
        style.configure("TSeparator", background=COLOR_BORDER)

    def build_menu_bar(self):
        menubar = tk.Menu(self, bg=COLOR_HEADER, fg=COLOR_TEXT, activebackground=COLOR_PRIMARY, activeforeground="#ffffff")
        self.config(menu=menubar)

        # Disc / File Menu
        menu_disc = tk.Menu(menubar, tearoff=0, bg=COLOR_SURFACE, fg=COLOR_TEXT, activebackground=COLOR_PRIMARY, activeforeground="#ffffff")
        menubar.add_cascade(label="Disc", menu=menu_disc)
        menu_disc.add_command(label="Scan Optical Drives", accelerator="Ctrl+R", command=self.scan_drives)
        menu_disc.add_command(label="Open Workspace Folder", accelerator="Ctrl+O", command=self.open_workspace_dir)
        menu_disc.add_separator()
        menu_disc.add_command(label="Exit", accelerator="Ctrl+Q", command=self.quit)

        # Tools Menu
        menu_tools = tk.Menu(menubar, tearoff=0, bg=COLOR_SURFACE, fg=COLOR_TEXT, activebackground=COLOR_PRIMARY, activeforeground="#ffffff")
        menubar.add_cascade(label="Tools", menu=menu_tools)
        menu_tools.add_command(label="Live Disc Ripper", accelerator="Ctrl+1", command=lambda: self.notebook.select(0))
        menu_tools.add_command(label="Image Converter", accelerator="Ctrl+2", command=lambda: self.notebook.select(1))
        menu_tools.add_command(label="Video Stitcher", accelerator="Ctrl+3", command=lambda: self.notebook.select(2))
        menu_tools.add_command(label="Audio Extractor", accelerator="Ctrl+4", command=lambda: self.notebook.select(3))
        menu_tools.add_command(label="File Library & Inspector", accelerator="Ctrl+5", command=lambda: self.notebook.select(4))
        menu_tools.add_separator()
        menu_tools.add_command(label="Check Dependencies", command=self.show_dependencies_dialog)

        # View Menu
        menu_view = tk.Menu(menubar, tearoff=0, bg=COLOR_SURFACE, fg=COLOR_TEXT, activebackground=COLOR_PRIMARY, activeforeground="#ffffff")
        menubar.add_cascade(label="View", menu=menu_view)
        menu_view.add_command(label="Toggle Activity Log", accelerator="Ctrl+L", command=self.toggle_console)
        menu_view.add_command(label="Clear Activity Log", accelerator="Ctrl+K", command=self.clear_console)
        menu_view.add_separator()
        menu_view.add_command(label="Refresh Workspace Files", accelerator="F5", command=self.refresh_browser_list)

        # Help Menu
        menu_help = tk.Menu(menubar, tearoff=0, bg=COLOR_SURFACE, fg=COLOR_TEXT, activebackground=COLOR_PRIMARY, activeforeground="#ffffff")
        menubar.add_cascade(label="Help", menu=menu_help)
        menu_help.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts_dialog)
        menu_help.add_separator()
        menu_help.add_command(label="About DiscMaster", command=self.show_about_dialog)

    def bind_shortcuts(self):
        self.bind("<Control-r>", lambda e: self.scan_drives())
        self.bind("<Control-R>", lambda e: self.scan_drives())
        self.bind("<Control-o>", lambda e: self.open_workspace_dir())
        self.bind("<Control-O>", lambda e: self.open_workspace_dir())
        self.bind("<Control-q>", lambda e: self.quit())
        self.bind("<Control-Q>", lambda e: self.quit())
        self.bind("<Control-l>", lambda e: self.toggle_console())
        self.bind("<Control-L>", lambda e: self.toggle_console())
        self.bind("<Control-k>", lambda e: self.clear_console())
        self.bind("<Control-K>", lambda e: self.clear_console())
        self.bind("<F5>", lambda e: self.refresh_browser_list())
        self.bind("<Control-1>", lambda e: self.notebook.select(0))
        self.bind("<Control-2>", lambda e: self.notebook.select(1))
        self.bind("<Control-3>", lambda e: self.notebook.select(2))
        self.bind("<Control-4>", lambda e: self.notebook.select(3))
        self.bind("<Control-5>", lambda e: self.notebook.select(4))

    def build_ui(self):
        # Master grid container
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header Bar (Classic GTK Toolbar/HeaderBar style)
        header_bar = ttk.Frame(self, style="Header.TFrame", padding=(14, 8))
        header_bar.grid(row=0, column=0, sticky="ew")
        header_bar.grid_columnconfigure(1, weight=1)

        # Left branding
        brand_frame = ttk.Frame(header_bar, style="Header.TFrame")
        brand_frame.grid(row=0, column=0, sticky="w")
        
        lbl_icon = ttk.Label(brand_frame, text="💿", style="HeaderTitle.TLabel", font=("Sans", 16))
        lbl_icon.pack(side="left", padx=(0, 8))

        title_sub_frame = ttk.Frame(brand_frame, style="Header.TFrame")
        title_sub_frame.pack(side="left")
        
        lbl_title = ttk.Label(title_sub_frame, text="DiscMaster", style="HeaderTitle.TLabel")
        lbl_title.pack(anchor="w")
        
        lbl_subtitle = ttk.Label(title_sub_frame, text="Optical Copy, Recovery & Processing Studio", style="HeaderSub.TLabel")
        lbl_subtitle.pack(anchor="w")

        # Right Quick Controls
        quick_frame = ttk.Frame(header_bar, style="Header.TFrame")
        quick_frame.grid(row=0, column=2, sticky="e")

        self.lbl_drive_chip = ttk.Label(quick_frame, text="🔍 Drive: Scanning...", style="HeaderSub.TLabel")
        self.lbl_drive_chip.pack(side="left", padx=(0, 10))

        btn_top_scan = ttk.Button(quick_frame, text="🔄 Scan Drives", command=self.scan_drives)
        btn_top_scan.pack(side="left", padx=(0, 6))

        self.btn_toggle_log = ttk.Button(quick_frame, text="📋 Hide Log", command=self.toggle_console)
        self.btn_toggle_log.pack(side="left")

        # Header separator line
        sep_header = ttk.Separator(self, orient="horizontal")
        sep_header.grid(row=0, column=0, sticky="sew")

        # Main Workspace Container
        main_container = ttk.Frame(self, padding=(10, 8, 10, 8))
        main_container.grid(row=1, column=0, sticky="nsew")
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)

        # 5-Tab GTK Notebook
        self.notebook = ttk.Notebook(main_container)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # Create tab frames
        self.tab_rip = ttk.Frame(self.notebook, padding=12)
        self.tab_convert = ttk.Frame(self.notebook, padding=12)
        self.tab_stitch = ttk.Frame(self.notebook, padding=12)
        self.tab_audio = ttk.Frame(self.notebook, padding=12)
        self.tab_browser = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.tab_rip, text=" 💿 Live Disc Ripper ")
        self.notebook.add(self.tab_convert, text=" 🔄 Image Converter ")
        self.notebook.add(self.tab_stitch, text=" 🎬 Video Stitcher ")
        self.notebook.add(self.tab_audio, text=" 🎵 Audio Extractor ")
        self.notebook.add(self.tab_browser, text=" 📁 File Library ")

        self.build_tab_rip()
        self.build_tab_convert()
        self.build_tab_stitch()
        self.build_tab_audio()
        self.build_tab_browser()

        # Shared Console and Progress Footer
        self.footer_frame = ttk.Frame(self, padding=(10, 0, 10, 8))
        self.footer_frame.grid(row=2, column=0, sticky="ew")
        self.footer_frame.grid_columnconfigure(0, weight=1)

        # Collapsible Console Container
        self.console_container = ttk.Frame(self.footer_frame)
        self.console_container.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.console_container.grid_columnconfigure(0, weight=1)

        # Console Header bar with actions
        console_bar = ttk.Frame(self.console_container)
        console_bar.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        console_bar.grid_columnconfigure(0, weight=1)

        lbl_console_title = ttk.Label(console_bar, text="Activity Log & Diagnostic Output", style="Muted.TLabel")
        lbl_console_title.grid(row=0, column=0, sticky="w")

        btn_clear_log = ttk.Button(console_bar, text="Clear", command=self.clear_console, padding=[6, 2])
        btn_clear_log.grid(row=0, column=1, sticky="e")

        # Console Log Widget (Styled Adwaita Terminal)
        self.console = ScrolledText(self.console_container, height=6, bg=COLOR_CONSOLE_BG, fg=COLOR_CONSOLE_FG, 
                                    font=self.font_mono, insertbackground="#ffffff", 
                                    selectbackground=COLOR_CONSOLE_SEL, selectforeground="#ffffff",
                                    relief="solid", borderwidth=1, padx=6, pady=4)
        self.console.grid(row=1, column=0, sticky="ew")
        self.console.tag_config("error", foreground="#ff7b72")
        self.console.tag_config("success", foreground="#7ee787")
        self.console.tag_config("info", foreground="#79c0ff")
        self.console.tag_config("warning", foreground="#ffa657")

        # Status & Progress Toolbar
        status_bar = ttk.Frame(self.footer_frame)
        status_bar.grid(row=1, column=0, sticky="ew")
        status_bar.grid_columnconfigure(1, weight=1)

        self.status_icon_lbl = ttk.Label(status_bar, text="●", foreground=COLOR_SUCCESS, font=("Sans", 10, "bold"))
        self.status_icon_lbl.grid(row=0, column=0, padx=(0, 5))

        self.status_msg_lbl = ttk.Label(status_bar, text="Ready", style="Status.TLabel")
        self.status_msg_lbl.grid(row=0, column=1, sticky="w")

        # Progress elements
        self.progress_val = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(status_bar, variable=self.progress_val, maximum=100, mode="determinate", length=220)
        self.progress_bar.grid(row=0, column=2, padx=(10, 10))

        self.btn_cancel = ttk.Button(status_bar, text="Cancel Task", style="Destructive.TButton", command=self.cancel_active_task)
        self.btn_cancel.grid(row=0, column=3, sticky="e")
        self.btn_cancel.state(["disabled"])

    # ── TAB 1: Live Disc Ripper ────────────────────────────────────────────

    def build_tab_rip(self):
        self.tab_rip.grid_rowconfigure(2, weight=1)
        self.tab_rip.grid_columnconfigure(0, weight=1)

        # Drives section
        drives_frame = ttk.LabelFrame(self.tab_rip, text=" Detected Optical Hardware ", padding=12)
        drives_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        drives_frame.grid_columnconfigure(0, weight=1)

        self.drive_select = ttk.Combobox(drives_frame, state="readonly")
        self.drive_select.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        btn_refresh = ttk.Button(drives_frame, text="Rescan Drives", command=self.scan_drives)
        btn_refresh.grid(row=0, column=1, sticky="e")

        # Initial drive scan
        self.scan_drives()

        # Rip settings
        rip_settings = ttk.LabelFrame(self.tab_rip, text=" Ripping Mode & Destination ", padding=12)
        rip_settings.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        rip_settings.grid_columnconfigure(1, weight=1)

        # Ripping Type Options
        ttk.Label(rip_settings, text="Select Disc Type:").grid(row=0, column=0, sticky="w", pady=6)
        self.rip_type = tk.StringVar(value="VCD")
        
        modes_frame = ttk.Frame(rip_settings)
        modes_frame.grid(row=0, column=1, columnspan=2, sticky="w")
        
        r1 = ttk.Radiobutton(modes_frame, text="Video CD (VCD) → MP4", variable=self.rip_type, value="VCD", command=self.on_rip_type_change)
        r1.pack(side="left", padx=(0, 18))
        r2 = ttk.Radiobutton(modes_frame, text="Audio CD (CDDA) → MP3/WAV", variable=self.rip_type, value="CDDA", command=self.on_rip_type_change)
        r2.pack(side="left", padx=(0, 18))
        r3 = ttk.Radiobutton(modes_frame, text="DVD Video → MP4", variable=self.rip_type, value="DVD", command=self.on_rip_type_change)
        r3.pack(side="left")

        # Sub-options frame for Audio CD format
        self.audio_rip_opts = ttk.Frame(rip_settings)
        self.audio_rip_opts.grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 6))
        ttk.Label(self.audio_rip_opts, text="Audio Quality Format:").pack(side="left", padx=(0, 10))
        self.audio_rip_format = tk.StringVar(value="mp3")
        ttk.Radiobutton(self.audio_rip_opts, text="MP3 (High Quality 320kbps)", variable=self.audio_rip_format, value="mp3").pack(side="left", padx=(0, 12))
        ttk.Radiobutton(self.audio_rip_opts, text="WAV (Lossless PCM 1411kbps)", variable=self.audio_rip_format, value="wav").pack(side="left")
        self.audio_rip_opts.grid_remove() # Hide by default

        # Output Folder Picker
        ttk.Label(rip_settings, text="Destination Folder:").grid(row=2, column=0, sticky="w", pady=6)
        self.rip_output_entry = ttk.Entry(rip_settings)
        self.rip_output_entry.grid(row=2, column=1, sticky="ew", padx=(0, 10))
        self.rip_output_entry.insert(0, self.workspace_dir)

        btn_browse = ttk.Button(rip_settings, text="Browse...", command=lambda: self.browse_folder(self.rip_output_entry))
        btn_browse.grid(row=2, column=2, sticky="e")

        # Action Buttons Frame
        action_frame = ttk.Frame(self.tab_rip)
        action_frame.grid(row=2, column=0, sticky="n", pady=15)

        btn_rip = ttk.Button(action_frame, text="▶ Start Ripping Process", style="Suggested.TButton", command=self.start_ripping)
        btn_rip.pack(ipady=3)

    def scan_drives(self):
        drives = engine.detect_optical_drives()
        if drives:
            list_vals = [f"{d['drive_letter']} ({d['name']})" for d in drives]
            self.drive_select['values'] = list_vals
            self.drive_select.current(0)
            self.lbl_drive_chip.config(text=f"💿 Drive: {drives[0]['drive_letter']}")
            self.write_log(f"[INFO] Scanning Optical Drives: Detected {len(drives)} drive(s).\n", is_info=True)
        else:
            self.drive_select['values'] = ["No physical optical drives detected"]
            self.drive_select.current(0)
            self.lbl_drive_chip.config(text="⚠️ No Optical Drive")
            self.write_log("[INFO] Drive detection scanned: No optical drives connected.\n", is_info=True)

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
        self.set_status("Ripping optical disc...", is_busy=True)

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
            mpegav_path = os.path.join(drive_letter, "mpegav")
            if not os.path.exists(mpegav_path):
                self.log_queue.put(f"[ERROR] Could not find VCD video directory MPEGAV on drive {drive_letter}. Ensure VCD disc is mounted.\n")
                self.progress_queue.put(0)
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
        vob_files = sorted(glob.glob(os.path.join(video_ts, "VTS_0[1-9]_[1-9].VOB")))
        if not vob_files:
            self.log_queue.put("[WARNING] No main title VOB files discovered. Attempting fallback stream...\n")
            cmd = [ffmpeg, "-y", "-i", f"concat:{video_ts}/VTS_01_1.VOB|{video_ts}/VTS_01_2.VOB", "-c:v", "libx264", "-preset", "fast", out_file]
        else:
            self.log_queue.put(f"[INFO] Found {len(vob_files)} main video VOB segments. Concatenating...\n")
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
        ffmpeg = engine.get_ffmpeg_path()
        letter_clean = drive_letter.replace(":", "").strip()
        
        self.log_queue.put(f"[INFO] Ripping tracks using cdda protocol on drive {letter_clean}...\n")
        ripped_count = 0
        for track in range(1, 40):
            if self.cancel_event.is_set():
                break
            out_file = os.path.join(output_dir, f"track_{track:02d}.{fmt}")
            cmd = [ffmpeg, "-y", "-i", f"cdda://{letter_clean}:{track}", out_file]
            
            self.log_queue.put(f"Ripping track {track}: Command: {' '.join(cmd)}\n")
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                self.log_queue.put(f"[SUCCESS] Extracted track {track} successfully → {os.path.basename(out_file)}\n")
                ripped_count += 1
            else:
                if track == 1:
                    self.log_queue.put("[ERROR] Track 1 rip failed. The drive might be empty or media unsupported.\n")
                    self.log_queue.put("Hint: You can rip the disc as a raw image (.bin/.cue) using cdrdao/readcd, then use 'Image Converter' tab to split it.\n")
                    break
                else:
                    self.log_queue.put(f"[INFO] Completed audio CD tracks. Total tracks ripped: {ripped_count}\n")
                    break
        
        self.progress_queue.put(100)

    # ── TAB 2: Image/File Converter ────────────────────────────────────────

    def build_tab_convert(self):
        self.tab_convert.grid_rowconfigure(2, weight=1)
        self.tab_convert.grid_columnconfigure(0, weight=1)

        # Mode Selector
        conv_modes = ttk.LabelFrame(self.tab_convert, text=" Select Operation Mode ", padding=12)
        conv_modes.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        conv_modes.grid_columnconfigure(0, weight=1)

        self.conv_mode_var = tk.StringVar(value="BIN_SPLIT")
        
        r1 = ttk.Radiobutton(conv_modes, text="Split BIN + CUE sheet into individual tracks (NATIVE CUE PARSER)", variable=self.conv_mode_var, value="BIN_SPLIT", command=self.on_conv_mode_change)
        r1.grid(row=0, column=0, sticky="w", pady=3)
        r2 = ttk.Radiobutton(conv_modes, text="Mode A: Raw VCD XA sector file (.mpg raw CD image) → MP4", variable=self.conv_mode_var, value="MODE_A", command=self.on_conv_mode_change)
        r2.grid(row=1, column=0, sticky="w", pady=3)
        r3 = ttk.Radiobutton(conv_modes, text="Mode B: Fix broken MP4 video (re-encode timestamps PTS/DTS)", variable=self.conv_mode_var, value="MODE_B", command=self.on_conv_mode_change)
        r3.grid(row=2, column=0, sticky="w", pady=3)
        r4 = ttk.Radiobutton(conv_modes, text="Mode C: Concatenate multiple raw VCD XA files → single MP4", variable=self.conv_mode_var, value="MODE_C", command=self.on_conv_mode_change)
        r4.grid(row=3, column=0, sticky="w", pady=3)
        r5 = ttk.Radiobutton(conv_modes, text="Convert TOC sheet → Standard CUE sheet", variable=self.conv_mode_var, value="TOC_CUE", command=self.on_conv_mode_change)
        r5.grid(row=4, column=0, sticky="w", pady=3)

        # Inputs section
        inputs_frame = ttk.LabelFrame(self.tab_convert, text=" Source & Target Parameters ", padding=12)
        inputs_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        inputs_frame.grid_columnconfigure(1, weight=1)

        # File input picker
        self.lbl_src_file = ttk.Label(inputs_frame, text="Select CUE Sheet File:")
        self.lbl_src_file.grid(row=0, column=0, sticky="w", pady=6)
        self.conv_src_entry = ttk.Entry(inputs_frame)
        self.conv_src_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.btn_conv_src = ttk.Button(inputs_frame, text="Select File...", command=self.select_conv_source)
        self.btn_conv_src.grid(row=0, column=2, sticky="e")

        # Multi-file inputs (only for Mode C)
        self.lbl_multi_files = ttk.Label(inputs_frame, text="Mode C Source Files:")
        self.conv_multi_entry = ttk.Entry(inputs_frame)
        self.btn_conv_multi = ttk.Button(inputs_frame, text="Select Files...", command=self.select_conv_multi_sources)

        # Output file/directory picker
        self.lbl_dst = ttk.Label(inputs_frame, text="Destination Folder:")
        self.lbl_dst.grid(row=1, column=0, sticky="w", pady=6)
        self.conv_dst_entry = ttk.Entry(inputs_frame)
        self.conv_dst_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.conv_dst_entry.insert(0, self.workspace_dir)
        self.btn_conv_dst = ttk.Button(inputs_frame, text="Select Folder...", command=self.select_conv_dest)
        self.btn_conv_dst.grid(row=1, column=2, sticky="e")

        # Action Buttons
        action_frame = ttk.Frame(self.tab_convert)
        action_frame.grid(row=2, column=0, sticky="n", pady=15)

        btn_run = ttk.Button(action_frame, text="▶ Execute Conversion", style="Suggested.TButton", command=self.start_conversion)
        btn_run.pack(ipady=3)

    def on_conv_mode_change(self):
        mode = self.conv_mode_var.get()
        if mode == "BIN_SPLIT":
            self.lbl_src_file.config(text="Select CUE Sheet File:")
            self.lbl_dst.config(text="Destination Folder:")
            self.lbl_multi_files.grid_remove()
            self.conv_multi_entry.grid_remove()
            self.btn_conv_multi.grid_remove()
            self.lbl_src_file.grid()
            self.conv_src_entry.grid()
            self.btn_conv_src.grid()
            self.btn_conv_dst.config(text="Select Folder...", command=self.select_conv_dest)
        elif mode == "TOC_CUE":
            self.lbl_src_file.config(text="Select TOC File:")
            self.lbl_dst.config(text="Target CUE Output File:")
            self.lbl_multi_files.grid_remove()
            self.conv_multi_entry.grid_remove()
            self.btn_conv_multi.grid_remove()
            self.lbl_src_file.grid()
            self.conv_src_entry.grid()
            self.btn_conv_src.grid()
            self.btn_conv_dst.config(text="Select File...", command=self.select_conv_dest_file)
        elif mode == "MODE_C":
            self.lbl_src_file.grid_remove()
            self.conv_src_entry.grid_remove()
            self.btn_conv_src.grid_remove()
            
            self.lbl_multi_files.grid(row=0, column=0, sticky="w", pady=6)
            self.conv_multi_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
            self.btn_conv_multi.grid(row=0, column=2, sticky="e")
            self.lbl_dst.config(text="Target MP4 Output File:")
            self.btn_conv_dst.config(text="Select File...", command=self.select_conv_dest_file)
        else:
            self.lbl_src_file.config(text="Select Input Video File:")
            self.lbl_dst.config(text="Target MP4 Output File:")
            self.lbl_multi_files.grid_remove()
            self.conv_multi_entry.grid_remove()
            self.btn_conv_multi.grid_remove()
            self.lbl_src_file.grid()
            self.conv_src_entry.grid()
            self.btn_conv_src.grid()
            self.btn_conv_dst.config(text="Select File...", command=self.select_conv_dest_file)

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
        self.set_status("Converting media stream...", is_busy=True)

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
                self.log_queue.put(f"[CONVERSION: MODE A] Extracting and transcoding VCD XA Image {os.path.basename(src)}...\n")
                tmp_dir = os.path.dirname(dst)
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mpeg.tmp", dir=tmp_dir)
                os.close(tmp_fd)
                
                try:
                    self.log_queue.put("[Step 1/2] Stripping raw CD-ROM sector XA headers...\n")
                    written = engine.extract_xa_to_file(
                        src_path=src,
                        dst_path=tmp_path,
                        logger=lambda msg: self.log_queue.put(msg + "\n"),
                        progress_update=lambda pct: self.progress_queue.put(pct * 0.4)
                    )
                    
                    if written == 0 or self.cancel_event.is_set():
                        self.log_queue.put("[ERROR] No MPEG sectors found or task was cancelled.\n")
                        return

                    vbr = engine.probe_video_bitrate(tmp_path)
                    self.log_queue.put(f"[Step 2/2] Transcoding to clean sequential timestamps (VBR: {vbr})...\n")
                    
                    def reencode_prog(pct):
                        self.progress_queue.put(40 + (pct * 0.6))

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
            self.log_queue.put(f"[ERROR] Task encountered exception: {e}\n")
            self.progress_queue.put(0)

    # ── TAB 3: Video Stitcher ──────────────────────────────────────────────

    def build_tab_stitch(self):
        self.tab_stitch.grid_rowconfigure(0, weight=1)
        self.tab_stitch.grid_columnconfigure(0, weight=1)

        # File listbox controls
        list_frame = ttk.LabelFrame(self.tab_stitch, text=" Selected Video Segments (in Concatenation Order) ", padding=10)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.stitch_listbox = tk.Listbox(list_frame, bg=COLOR_SURFACE, fg=COLOR_TEXT, 
                                         selectbackground=COLOR_LIST_SEL, selectforeground="#ffffff", 
                                         relief="solid", borderwidth=1, font=self.font_main, activestyle="none")
        self.stitch_listbox.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.stitch_listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.stitch_listbox.config(yscrollcommand=sb.set)

        # Control panel on right
        control_frame = ttk.Frame(self.tab_stitch, padding=(0, 5))
        control_frame.grid(row=0, column=1, sticky="ns")

        btn_add = ttk.Button(control_frame, text="➕ Add Videos...", command=self.stitch_add_files)
        btn_add.pack(fill="x", pady=2)
        btn_remove = ttk.Button(control_frame, text="➖ Remove Selected", command=self.stitch_remove_file)
        btn_remove.pack(fill="x", pady=2)
        btn_clear = ttk.Button(control_frame, text="🗑️ Clear List", command=self.stitch_clear_list)
        btn_clear.pack(fill="x", pady=2)
        
        ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=10)

        btn_up = ttk.Button(control_frame, text="▲ Move Up", command=lambda: self.stitch_move_file(-1))
        btn_up.pack(fill="x", pady=2)
        btn_down = ttk.Button(control_frame, text="▼ Move Down", command=lambda: self.stitch_move_file(1))
        btn_down.pack(fill="x", pady=2)

        # Settings below
        settings_frame = ttk.LabelFrame(self.tab_stitch, text=" Output Settings ", padding=12)
        settings_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
        settings_frame.grid_columnconfigure(1, weight=1)

        self.stitch_reencode_var = tk.BooleanVar(value=False)
        chk_reencode = ttk.Checkbutton(settings_frame, text="Force re-encode videos (Normalizes mismatched aspect ratios & dimensions)", variable=self.stitch_reencode_var)
        chk_reencode.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(settings_frame, text="Output File Path:").grid(row=1, column=0, sticky="w")
        self.stitch_out_entry = ttk.Entry(settings_frame)
        self.stitch_out_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.stitch_out_entry.insert(0, os.path.join(self.workspace_dir, "stitched_output.mp4"))

        btn_out_browse = ttk.Button(settings_frame, text="Browse Save...", command=self.stitch_browse_output)
        btn_out_browse.grid(row=1, column=2, sticky="e")

        # Action Buttons
        action_btn_frame = ttk.Frame(self.tab_stitch)
        action_btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        btn_stitch = ttk.Button(action_btn_frame, text="▶ Stitch Video Clips", style="Suggested.TButton", command=self.start_stitch)
        btn_stitch.pack(ipady=3)

    def stitch_add_files(self):
        ftype = [("Video Files", "*.mp4;*.mpg;*.mpeg;*.avi;*.mkv;*.mov"), ("All Files", "*.*")]
        paths = filedialog.askopenfilenames(initialdir=self.workspace_dir, filetypes=ftype)
        if paths:
            for p in paths:
                p_abs = os.path.abspath(p)
                if p_abs not in self.stitch_files_list:
                    self.stitch_files_list.append(p_abs)
                    self.stitch_listbox.insert(tk.END, f"{len(self.stitch_files_list)}. {os.path.basename(p_abs)}")

    def stitch_remove_file(self):
        sel = self.stitch_listbox.curselection()
        if sel:
            idx = sel[0]
            self.stitch_files_list.pop(idx)
            self._refresh_stitch_listbox()

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
            self.stitch_files_list[idx], self.stitch_files_list[new_idx] = self.stitch_files_list[new_idx], self.stitch_files_list[idx]
            self._refresh_stitch_listbox()
            self.stitch_listbox.select_set(new_idx)

    def _refresh_stitch_listbox(self):
        self.stitch_listbox.delete(0, tk.END)
        for i, f in enumerate(self.stitch_files_list, 1):
            self.stitch_listbox.insert(tk.END, f"{i}. {os.path.basename(f)}")

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
        self.set_status("Stitching video segments...", is_busy=True)

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
        src_frame = ttk.LabelFrame(self.tab_audio, text=" Source Settings ", padding=12)
        src_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        src_frame.grid_columnconfigure(1, weight=1)

        self.audio_batch_var = tk.BooleanVar(value=False)
        chk_batch = ttk.Checkbutton(src_frame, text="Batch Process Mode (Extract audio from all files in directory)", variable=self.audio_batch_var, command=self.on_audio_batch_change)
        chk_batch.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.lbl_audio_src = ttk.Label(src_frame, text="Select Source File:")
        self.lbl_audio_src.grid(row=1, column=0, sticky="w")
        self.audio_src_entry = ttk.Entry(src_frame)
        self.audio_src_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.btn_audio_src_browse = ttk.Button(src_frame, text="Select File...", command=self.audio_browse_src)
        self.btn_audio_src_browse.grid(row=1, column=2, sticky="e")

        # Destination Frame
        dst_frame = ttk.LabelFrame(self.tab_audio, text=" Output Format & Destination ", padding=12)
        dst_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        dst_frame.grid_columnconfigure(1, weight=1)

        # Audio Format choices
        ttk.Label(dst_frame, text="Target Audio Format:").grid(row=0, column=0, sticky="w", pady=6)
        self.audio_format_select = ttk.Combobox(dst_frame, state="readonly", values=["mp3", "wav", "flac", "aac"])
        self.audio_format_select.grid(row=0, column=1, sticky="w")
        self.audio_format_select.current(0)
        self.audio_format_select.bind("<<ComboboxSelected>>", self.on_audio_format_change)

        # Output Target Picker
        self.lbl_audio_dst = ttk.Label(dst_frame, text="Target Output File:")
        self.lbl_audio_dst.grid(row=1, column=0, sticky="w", pady=6)
        self.audio_dst_entry = ttk.Entry(dst_frame)
        self.audio_dst_entry.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.audio_dst_entry.insert(0, os.path.join(self.workspace_dir, "extracted_audio.mp3"))
        
        self.btn_audio_dst_browse = ttk.Button(dst_frame, text="Select Path...", command=self.audio_browse_dst)
        self.btn_audio_dst_browse.grid(row=1, column=2, sticky="e")

        # Action Buttons
        action_btn_frame = ttk.Frame(self.tab_audio)
        action_btn_frame.grid(row=2, column=0, pady=15)

        btn_extract = ttk.Button(action_btn_frame, text="▶ Extract Audio", style="Suggested.TButton", command=self.start_audio_extract)
        btn_extract.pack(ipady=3)

    def on_audio_batch_change(self):
        batch = self.audio_batch_var.get()
        if batch:
            self.lbl_audio_src.config(text="Select Source Folder:")
            self.btn_audio_src_browse.config(text="Select Folder...", command=self.audio_browse_src_dir)
            self.lbl_audio_dst.config(text="Target Save Folder:")
            self.btn_audio_dst_browse.config(text="Select Folder...", command=self.audio_browse_dst_dir)
            
            self.audio_dst_entry.delete(0, tk.END)
            self.audio_dst_entry.insert(0, self.workspace_dir)
        else:
            self.lbl_audio_src.config(text="Select Source File:")
            self.btn_audio_src_browse.config(text="Select File...", command=self.audio_browse_src)
            self.lbl_audio_dst.config(text="Target Output File:")
            self.btn_audio_dst_browse.config(text="Select Path...", command=self.audio_browse_dst)
            
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
        self.set_status("Extracting audio...", is_busy=True)

        fmt = self.audio_format_select.get()
        is_batch = self.audio_batch_var.get()

        self.active_thread = threading.Thread(target=self.thread_audio_extract, args=(src, dst, fmt, is_batch))
        self.active_thread.start()

    def thread_audio_extract(self, src, dst, fmt, is_batch):
        if is_batch:
            self.log_queue.put(f"[AUDIO EXTRACTION] Batch mode triggered on folder: {src}\n")
            media_exts = ['*.mp4', '*.mpg', '*.mpeg', '*.avi', '*.mkv', '*.mov', '*.wav', '*.dat']
            files = []
            for ext in media_exts:
                files.extend(glob.glob(os.path.join(src, ext)))
                files.extend(glob.glob(os.path.join(src, ext.upper())))
            
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
        self.tab_browser.grid_rowconfigure(0, weight=1)
        self.tab_browser.grid_columnconfigure(0, weight=1)
        self.tab_browser.grid_columnconfigure(1, weight=1)

        # Column 1: Files List
        files_frame = ttk.LabelFrame(self.tab_browser, text=" Workspace Directory Explorer ", padding=10)
        files_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        files_frame.grid_rowconfigure(1, weight=1)
        files_frame.grid_columnconfigure(0, weight=1)

        # Folder picker bar
        pick_frame = ttk.Frame(files_frame)
        pick_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        pick_frame.grid_columnconfigure(0, weight=1)

        self.browser_dir_entry = ttk.Entry(pick_frame)
        self.browser_dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.browser_dir_entry.insert(0, self.workspace_dir)

        btn_browse = ttk.Button(pick_frame, text="Browse...", command=self.browser_change_dir)
        btn_browse.grid(row=0, column=1, sticky="e")

        self.browser_listbox = tk.Listbox(files_frame, bg=COLOR_SURFACE, fg=COLOR_TEXT, 
                                          selectbackground=COLOR_LIST_SEL, selectforeground="#ffffff", 
                                          relief="solid", borderwidth=1, font=self.font_main, activestyle="none")
        self.browser_listbox.grid(row=1, column=0, sticky="nsew")
        self.browser_listbox.bind("<<ListboxSelect>>", self.on_browser_file_selected)

        sb = ttk.Scrollbar(files_frame, orient="vertical", command=self.browser_listbox.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.browser_listbox.config(yscrollcommand=sb.set)

        self.refresh_browser_list()

        # Column 2: Metadata Display
        meta_frame = ttk.LabelFrame(self.tab_browser, text=" Media Inspector & ffprobe Metadata ", padding=10)
        meta_frame.grid(row=0, column=1, sticky="nsew")
        meta_frame.grid_rowconfigure(0, weight=1)
        meta_frame.grid_columnconfigure(0, weight=1)

        self.meta_text = ScrolledText(meta_frame, bg=COLOR_SURFACE, fg=COLOR_TEXT, 
                                      font=self.font_mono, insertbackground=COLOR_TEXT, 
                                      relief="solid", borderwidth=1, padx=6, pady=4)
        self.meta_text.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        
        # Action controls below metadata
        controls_frame = ttk.Frame(meta_frame)
        controls_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        btn_open = ttk.Button(controls_frame, text="▶ Play / Open File", command=self.browser_open_file)
        btn_open.pack(side="left", padx=(0, 6))

        btn_refresh_meta = ttk.Button(controls_frame, text="🔄 Re-scan", command=self.on_browser_file_selected)
        btn_refresh_meta.pack(side="left")

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
            items = sorted(os.listdir(path))
            dirs = [d for d in items if os.path.isdir(os.path.join(path, d))]
            files = [f for f in items if not os.path.isdir(os.path.join(path, f)) and os.path.splitext(f)[1].lower() in ['.mp4', '.mkv', '.bin', '.cue', '.toc', '.dat', '.mpg', '.mpeg', '.avi', '.wav', '.mp3', '.flac', '.aac']]
            
            for d in dirs:
                self.browser_listbox.insert(tk.END, f"📁 {d}")
            for f in files:
                self.browser_listbox.insert(tk.END, f"📄 {f}")
        except Exception as e:
            self.browser_listbox.insert(tk.END, f"Error: {e}")

    def on_browser_file_selected(self, event=None):
        sel = self.browser_listbox.curselection()
        if not sel:
            return
        
        raw_item = self.browser_listbox.get(sel[0])
        current_dir = self.browser_dir_entry.get().strip()
        
        if raw_item.startswith("📁 "):
            dir_name = raw_item[3:].strip()
            target_path = os.path.join(current_dir, dir_name)
            self.meta_text.delete(1.0, tk.END)
            try:
                sub_items = len(os.listdir(target_path))
            except Exception:
                sub_items = "N/A"
            self.meta_text.insert(tk.END, f"Directory Details:\n\nPath: {target_path}\nItems: {sub_items}\n\n(Double-click or click Play/Open to navigate inside)")
            return
        
        item = raw_item[3:].strip() if raw_item.startswith("📄 ") else raw_item
        full_path = os.path.join(current_dir, item)
        if not os.path.exists(full_path):
            return
        
        self.meta_text.delete(1.0, tk.END)
        self.meta_text.insert(tk.END, f"File: {item}\n")
        self.meta_text.insert(tk.END, f"Path: {full_path}\n")
        self.meta_text.insert(tk.END, f"File Size: {os.path.getsize(full_path) / (1024*1024):.2f} MB\n")
        self.meta_text.insert(tk.END, "────────────────────────────────────────────────────────────\n")

        ffprobe = engine.get_ffprobe_path()
        if not ffprobe:
            self.meta_text.insert(tk.END, "[WARNING] ffprobe missing. Detailed stream metadata unavailable.")
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
                    
                    out_lines = []
                    fmt = data.get('format', {})
                    out_lines.append(f"Format: {fmt.get('format_long_name', fmt.get('format_name', 'Unknown'))}")
                    
                    dur = fmt.get('duration')
                    if dur:
                        out_lines.append(f"Duration: {float(dur):.2f}s ({float(dur)//60:.0f}m {float(dur)%60:.1f}s)")
                        
                    bitrate = fmt.get('bit_rate')
                    if bitrate:
                        out_lines.append(f"Bitrate: {int(bitrate)//1000} kbps")
                    
                    out_lines.append("\nStreams:")
                    for idx, stream in enumerate(data.get('streams', [])):
                        s_type = stream.get('codec_type')
                        codec = stream.get('codec_long_name', stream.get('codec_name', 'Unknown'))
                        out_lines.append(f"  Stream #{idx} [{s_type.upper()}]: {codec}")
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

        threading.Thread(target=run_probe, daemon=True).start()

    def safe_insert_meta(self, txt):
        self.after(0, lambda: self._insert_meta(txt))

    def _insert_meta(self, txt):
        self.meta_text.insert(tk.END, txt)

    def browser_open_file(self):
        sel = self.browser_listbox.curselection()
        if not sel:
            return
        
        raw_item = self.browser_listbox.get(sel[0])
        current_dir = self.browser_dir_entry.get().strip()
        
        if raw_item.startswith("📁 "):
            dir_name = raw_item[3:].strip()
            self.browser_dir_entry.delete(0, tk.END)
            self.browser_dir_entry.insert(0, os.path.abspath(os.path.join(current_dir, dir_name)))
            self.refresh_browser_list()
            return

        item = raw_item[3:].strip() if raw_item.startswith("📄 ") else raw_item
        full_path = os.path.join(current_dir, item)
        self.write_log(f"[INFO] Opening file: {full_path}\n", is_info=True)
        try:
            if sys.platform == 'win32':
                os.startfile(full_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', full_path])
            else:
                subprocess.run(['xdg-open', full_path])
        except Exception as e:
            messagebox.showerror("Error Opening File", f"Could not launch default player for: {full_path}\nError: {e}")

    # ── LOGGING & CONSOLE CONTROLS ─────────────────────────────────────────

    def toggle_console(self):
        if self.console_visible:
            self.console_container.grid_remove()
            self.console_visible = False
            self.btn_toggle_log.config(text="📋 Show Log")
        else:
            self.console_container.grid()
            self.console_visible = True
            self.btn_toggle_log.config(text="📋 Hide Log")

    def clear_console(self):
        self.console.delete(1.0, tk.END)

    def cancel_active_task(self):
        if messagebox.askyesno("Cancel Active Task", "Are you sure you want to stop/terminate the running conversion/transcoding process?"):
            self.cancel_event.set()
            self.log_queue.put("[CANCELLED] User requested cancellation. Stopping active thread...\n")
            self.btn_cancel.state(["disabled"])
            self.set_status("Operation cancelled.", is_busy=False)

    def set_status(self, text, is_busy=False):
        self.status_msg_lbl.config(text=text)
        if is_busy:
            self.status_icon_lbl.config(text="⏳", foreground=COLOR_WARNING)
        else:
            self.status_icon_lbl.config(text="●", foreground=COLOR_SUCCESS)

    def write_log(self, text, is_error=False, is_success=False, is_info=False, is_warn=False):
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
            elif is_warn:
                tag = "warning"
                
            self.console.insert(tk.END, text, tag)
            self.console.see(tk.END)
        except Exception:
            pass

    def process_queues(self):
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                is_err = "[ERROR]" in msg or "[CANCELLED]" in msg
                is_ok = "[SUCCESS]" in msg
                is_inf = "[INFO]" in msg or "[Step" in msg or "[RIPPING" in msg or "[CONVERSION" in msg or "[STITCH" in msg or "[AUDIO" in msg
                is_warn = "[WARNING]" in msg
                self.write_log(msg, is_error=is_err, is_success=is_ok, is_info=is_inf, is_warn=is_warn)
                
                if "[INFO]" in msg or "[Step" in msg or "[RIPPING" in msg:
                    clean_line = msg.strip().replace("[INFO] ", "").replace("[RIPPING VCD] ", "").replace("[RIPPING DVD] ", "")
                    if len(clean_line) < 60:
                        self.set_status(clean_line, is_busy=True)
            except queue.Empty:
                break

        while not self.progress_queue.empty():
            try:
                pct = self.progress_queue.get_nowait()
                self.progress_val.set(pct)
                if pct >= 100:
                    self.btn_cancel.state(["disabled"])
                    self.set_status("Operation completed successfully.", is_busy=False)
                elif pct <= 0:
                    self.btn_cancel.state(["disabled"])
                    self.set_status("Ready", is_busy=False)
            except queue.Empty:
                break

        self.after(100, self.process_queues)

    # ── SYSTEM & HELP DIALOGS ──────────────────────────────────────────────

    def check_system_dependencies(self):
        ffmpeg = engine.get_ffmpeg_path()
        ffprobe = engine.get_ffprobe_path()
        
        dep_msg = []
        if not ffmpeg:
            dep_msg.append("• ffmpeg was not found in system PATH. Video transcoding and extraction features will fail.")
        if not ffprobe:
            dep_msg.append("• ffprobe was not found in system PATH. Media details detection will be disabled.")
            
        if dep_msg:
            self.write_log("[SYSTEM WARNING] Missing dependencies:\n" + "\n".join(dep_msg) + "\n\nPlease ensure ffmpeg and ffprobe are installed and in your environment PATH variables.\n", is_warn=True)

    def show_dependencies_dialog(self):
        ffmpeg = engine.get_ffmpeg_path()
        ffprobe = engine.get_ffprobe_path()
        
        status_ffmpeg = f"Found ({ffmpeg})" if ffmpeg else "MISSING (Please install ffmpeg)"
        status_ffprobe = f"Found ({ffprobe})" if ffprobe else "MISSING (Please install ffprobe)"
        
        info = f"System Dependency Diagnostics:\n\n• FFmpeg: {status_ffmpeg}\n• FFprobe: {status_ffprobe}\n• Python Version: {sys.version.split()[0]}\n• Platform: {sys.platform}"
        messagebox.showinfo("System Dependencies", info)

    def open_workspace_dir(self):
        folder = filedialog.askdirectory(initialdir=self.workspace_dir)
        if folder:
            self.workspace_dir = os.path.abspath(folder)
            self.rip_output_entry.delete(0, tk.END)
            self.rip_output_entry.insert(0, self.workspace_dir)
            self.conv_dst_entry.delete(0, tk.END)
            self.conv_dst_entry.insert(0, self.workspace_dir)
            self.browser_dir_entry.delete(0, tk.END)
            self.browser_dir_entry.insert(0, self.workspace_dir)
            self.refresh_browser_list()
            self.write_log(f"[INFO] Workspace updated: {self.workspace_dir}\n", is_info=True)

    def show_shortcuts_dialog(self):
        msg = (
            "DiscMaster Keyboard Shortcuts:\n\n"
            "• Ctrl + R : Scan optical drives\n"
            "• Ctrl + O : Open workspace folder\n"
            "• Ctrl + L : Toggle Activity Log (Show/Hide)\n"
            "• Ctrl + K : Clear Activity Log\n"
            "• F5       : Refresh File Explorer\n"
            "• Ctrl + 1 : Switch to Live Disc Ripper\n"
            "• Ctrl + 2 : Switch to Image Converter\n"
            "• Ctrl + 3 : Switch to Video Stitcher\n"
            "• Ctrl + 4 : Switch to Audio Extractor\n"
            "• Ctrl + 5 : Switch to File Library\n"
            "• Ctrl + Q : Quit application"
        )
        messagebox.showinfo("Keyboard Shortcuts", msg)

    def show_about_dialog(self):
        msg = (
            "DiscMaster v2.0\n"
            "Optical Copy, Recovery & Processing Studio\n\n"
            "A native GTK/GNOME-styled preservation suite to rip, restore, "
            "transcode, stitch, and inspect legacy optical media (VCD, DVD, Audio CD, BIN/CUE).\n\n"
            "Engine: discmaster_engine (Low-level CD-ROM XA Demuxer + FFmpeg)\n"
            "License: Apache License 2.0\n"
            "GitHub: https://github.com/punitr2007/Discmaster"
        )
        messagebox.showinfo("About DiscMaster", msg)


if __name__ == "__main__":
    app = DiscMasterApp()
    app.mainloop()

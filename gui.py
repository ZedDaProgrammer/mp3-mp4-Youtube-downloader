import os
import time
import shutil
import queue
from pathlib import Path
import customtkinter as ctk
import yt_dlp
from concurrent.futures import ThreadPoolExecutor

# Set CustomTkinter window preferences
ctk.set_appearance_mode("Dark")  # Modes: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue", "green", "dark-blue"

class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Koinloader - YouTube Downloader")
        self.geometry("640x560")
        self.resizable(False, False)
        
        # Premium Slate Dark Background
        self.configure(fg_color="#090d16")

        # State Variables
        self.video_info = None
        self.active_download_job = None
        self.downloads_dir = self.get_download_path()
        self.ffmpeg_available = False
        self.ffmpeg_dir = None
        self.cookies_path = None
        
        # Thread Pool and Queue controls
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.download_queue = queue.Queue()
        self.cancel_requested = False
        self.pause_requested = False

        # Build UI
        self.create_widgets()

        # Check FFmpeg asynchronously to keep GUI loading instant
        self.status_label.configure(text="Checking system components...")
        self.stats_frame.pack_forget()
        self.progressbar.configure(mode="indeterminate")
        self.progressbar.start()
        self.progress_frame.pack(fill="x", padx=40, pady=5)
        
        # Disable analyze button during system checks to prevent race conditions
        self.analyze_btn.configure(state="disabled", text="Checking...")
        self.executor.submit(self.bg_check_ffmpeg)

    def get_download_path(self):
        """Returns standard Windows Downloads path, falling back to home dir."""
        try:
            import winreg
            sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                return winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
        except Exception:
            return str(Path.home() / "Downloads")

    def truncate_string(self, text, max_len=55):
        """Optimized string truncation using fast slicing representation."""
        if not text or len(text) <= max_len:
            return text
        return f"{text[:25]}...{text[-27:]}"

    def change_download_dir(self):
        from tkinter import filedialog
        selected_dir = filedialog.askdirectory(
            parent=self,
            title="Select Download Directory",
            initialdir=self.downloads_dir
        )
        if selected_dir:
            self.downloads_dir = selected_dir
            display_path = self.truncate_string(selected_dir)
            self.dir_label.configure(text=f"Save to: {display_path}")

    def load_cookies_file(self):
        from tkinter import filedialog
        selected_file = filedialog.askopenfilename(
            parent=self,
            title="Select Netscape Cookies File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if selected_file:
            self.cookies_path = selected_file
            display_name = os.path.basename(selected_file)
            display_name = self.truncate_string(display_name, 30)
            self.cookies_label.configure(text=f"Cookies: {display_name}")

    def format_size(self, bytes_val):
        if not bytes_val or bytes_val <= 0:
            return "Unknown Size"
        if bytes_val >= 1024 * 1024 * 1024:
            return f"{bytes_val / (1024*1024*1024):.1f} GB"
        elif bytes_val >= 1024 * 1024:
            return f"{bytes_val / (1024*1024):.1f} MB"
        elif bytes_val >= 1024:
            return f"{bytes_val / 1024:.0f} KB"
        else:
            return f"{bytes_val} B"

    def bg_check_ffmpeg(self):
        """Checks FFmpeg availability and locates its directory for native config."""
        # 1. Check local ./bin folder first for portability
        local_bin = os.path.join(os.getcwd(), "bin")
        if os.path.exists(local_bin):
            ffmpeg_bin = os.path.join(local_bin, "ffmpeg.exe") if os.name == 'nt' else os.path.join(local_bin, "ffmpeg")
            if os.path.exists(ffmpeg_bin):
                self.ffmpeg_dir = local_bin
                self.ffmpeg_available = True
                self.after(0, self.update_ffmpeg_status, "FFmpeg: Detected (Local ./bin)")
                return

        # 2. Check AppData npm directory fallbacks
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            npm_dirs = [
                os.path.join(appdata, "npm", "node_modules", "@ffmpeg-installer", "win32-x64"),
                os.path.join(appdata, "npm", "node_modules", "@ffmpeg-installer", "ffmpeg", "node_modules", "@ffmpeg-installer", "win32-x64"),
                os.path.join(appdata, "npm", "node_modules", "@ffprobe-installer", "win32-x64"),
                os.path.join(appdata, "npm", "node_modules", "@ffprobe-installer", "ffprobe", "node_modules", "@ffprobe-installer", "win32-x64")
            ]
            for path in npm_dirs:
                if os.path.exists(os.path.join(path, "ffmpeg.exe")) or os.path.exists(os.path.join(path, "ffmpeg")):
                    self.ffmpeg_dir = path
                    self.ffmpeg_available = True
                    self.after(0, self.update_ffmpeg_status, "FFmpeg: Detected (Local Package)")
                    return

        # 3. Check system PATH
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg is not None:
            self.ffmpeg_dir = os.path.dirname(sys_ffmpeg)
            self.ffmpeg_available = True
            self.after(0, self.update_ffmpeg_status, "FFmpeg: Detected (System PATH)")
            return

        # 4. Fallback to static_ffmpeg package
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
            sys_ffmpeg = shutil.which("ffmpeg")
            if sys_ffmpeg is not None:
                self.ffmpeg_dir = os.path.dirname(sys_ffmpeg)
                self.ffmpeg_available = True
                self.after(0, self.update_ffmpeg_status, "FFmpeg: Detected (Static)")
                return
        except Exception:
            pass

        # 5. Fallback: No FFmpeg
        self.ffmpeg_available = False
        self.ffmpeg_dir = None
        self.after(0, self.update_ffmpeg_status, "FFmpeg: Missing (Max quality 720p, Audio saved as M4A)")

    def update_ffmpeg_status(self, message):
        self.progressbar.stop()
        self.progressbar.configure(mode="determinate")
        self.progress_frame.pack_forget()
        self.stats_frame.pack(fill="x", padx=10, pady=5)
        self.ffmpeg_status_label.configure(text=message)
        if not self.ffmpeg_available:
            self.ffmpeg_status_label.configure(text_color="#f59e0b") # Warning color
            self.mp3_download_btn.configure(text="Download M4A Audio")
            self.mp3_dropdown_label.configure(text="Audio Quality:")
            self.mp3_quality_menu.configure(values=["Original / Best Quality"])
            self.mp3_quality_menu.set("Original / Best Quality")
        else:
            self.ffmpeg_status_label.configure(text_color="#10b981") # Success color
            
        # Re-enable the Analyze button now that checks are finished
        self.analyze_btn.configure(state="normal", text="Analyze")

    def create_widgets(self):
        # Header Label
        self.header_label = ctk.CTkLabel(
            self, 
            text="Koinloader", 
            text_color="#f1f5f9",
            font=ctk.CTkFont(family="Outfit", size=32, weight="bold")
        )
        self.header_label.pack(pady=(15, 2))

        self.subtitle_label = ctk.CTkLabel(
            self, 
            text="Convert YouTube videos to MP3 & MP4", 
            text_color="#64748b",
            font=ctk.CTkFont(family="Outfit", size=14)
        )
        self.subtitle_label.pack(pady=(0, 10))

        # FFmpeg Status Label
        self.ffmpeg_status_label = ctk.CTkLabel(
            self,
            text="Checking system components...",
            text_color="#64748b",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.ffmpeg_status_label.pack(pady=(0, 10))

        # Search Frame
        self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.search_frame.pack(fill="x", padx=40, pady=5)

        self.url_entry = ctk.CTkEntry(
            self.search_frame, 
            placeholder_text="Paste YouTube URL link here...",
            height=45,
            fg_color="#131b2e",
            text_color="#f1f5f9",
            placeholder_text_color="#475569",
            border_color="#1e293b",
            font=ctk.CTkFont(size=13)
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.analyze_btn = ctk.CTkButton(
            self.search_frame,
            text="Analyze",
            width=100,
            height=45,
            fg_color="#4f46e5",
            hover_color="#4338ca",
            text_color="#f1f5f9",
            font=ctk.CTkFont(weight="bold"),
            command=self.start_analyze
        )
        self.analyze_btn.pack(side="right")

        # Info Frame (hidden by default)
        self.info_frame = ctk.CTkFrame(
            self, 
            corner_radius=16,
            fg_color="#131b2e",
            border_color="#1e293b",
            border_width=1
        )
        
        self.title_label = ctk.CTkLabel(
            self.info_frame, 
            text="", 
            text_color="#f1f5f9",
            wraplength=500, 
            justify="left",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        self.title_label.pack(anchor="w", padx=20, pady=(15, 5))

        self.channel_label = ctk.CTkLabel(
            self.info_frame, 
            text="", 
            text_color="#06b6d4",
            font=ctk.CTkFont(size=13)
        )
        self.channel_label.pack(anchor="w", padx=20, pady=(0, 5))

        self.duration_label = ctk.CTkLabel(
            self.info_frame, 
            text="", 
            text_color="#94a3b8",
            font=ctk.CTkFont(size=12)
        )
        self.duration_label.pack(anchor="w", padx=20, pady=(0, 15))

        # Tabview for Downloads (inside info frame)
        self.tabview = ctk.CTkTabview(
            self.info_frame, 
            height=180,
            fg_color="#0f172a",
            segmented_button_fg_color="#1e293b",
            segmented_button_selected_color="#4f46e5",
            segmented_button_selected_hover_color="#4338ca",
            segmented_button_unselected_color="#131b2e",
            segmented_button_unselected_hover_color="#1e293b",
            text_color="#cbd5e1"
        )
        self.tabview.pack(fill="x", padx=20, pady=(0, 15))
        
        self.tab_mp4 = self.tabview.add("MP4 Video")
        self.tab_mp3 = self.tabview.add("MP3 Audio")

        # MP4 Tab Layout
        self.mp4_dropdown_label = ctk.CTkLabel(self.tab_mp4, text="Select Video Quality:", text_color="#f1f5f9")
        self.mp4_dropdown_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

        self.mp4_quality_menu = ctk.CTkOptionMenu(
            self.tab_mp4, 
            width=180, 
            fg_color="#131b2e",
            button_color="#1e293b",
            button_hover_color="#334155",
            dropdown_fg_color="#131b2e",
            dropdown_text_color="#cbd5e1",
            dropdown_hover_color="#1e293b",
            values=["720p", "360p"]
        )
        self.mp4_quality_menu.grid(row=0, column=1, padx=20, pady=(15, 5), sticky="w")

        self.mp4_download_btn = ctk.CTkButton(
            self.tab_mp4, 
            text="Download Video", 
            fg_color="#059669", 
            hover_color="#047857",
            text_color="#f1f5f9",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.start_download("mp4")
        )
        self.mp4_download_btn.grid(row=1, column=0, columnspan=2, padx=20, pady=(15, 10), sticky="ew")

        # MP3 Tab Layout
        self.mp3_dropdown_label = ctk.CTkLabel(self.tab_mp3, text="Select Audio Bitrate:", text_color="#f1f5f9")
        self.mp3_dropdown_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

        self.mp3_quality_menu = ctk.CTkOptionMenu(
            self.tab_mp3, 
            width=180, 
            fg_color="#131b2e",
            button_color="#1e293b",
            button_hover_color="#334155",
            dropdown_fg_color="#131b2e",
            dropdown_text_color="#cbd5e1",
            dropdown_hover_color="#1e293b",
            values=["320 kbps (High)", "256 kbps", "192 kbps (Medium)", "128 kbps (Low)"]
        )
        self.mp3_quality_menu.set("320 kbps (High)")
        self.mp3_quality_menu.grid(row=0, column=1, padx=20, pady=(15, 5), sticky="w")

        self.mp3_download_btn = ctk.CTkButton(
            self.tab_mp3, 
            text="Download Audio", 
            fg_color="#4f46e5", 
            hover_color="#4338ca",
            text_color="#f1f5f9",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.start_download("mp3")
        )
        self.mp3_download_btn.grid(row=1, column=0, columnspan=2, padx=20, pady=(15, 10), sticky="ew")

        # Progress Frame (hidden/visible as needed)
        self.progress_frame = ctk.CTkFrame(
            self, 
            corner_radius=16, 
            fg_color="#131b2e",
            border_color="#1e293b",
            border_width=1
        )
        
        self.status_label = ctk.CTkLabel(
            self.progress_frame, 
            text="Downloading video...", 
            text_color="#f1f5f9",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.status_label.pack(anchor="w", padx=10, pady=(5, 5))

        # Progressbar
        self.progressbar = ctk.CTkProgressBar(
            self.progress_frame,
            progress_color="#4f46e5",
            fg_color="#1e293b"
        )
        self.progressbar.pack(fill="x", padx=10, pady=5)
        self.progressbar.set(0)

        # Status stats (Speed / ETA / Percent)
        self.stats_frame = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=10, pady=5)

        self.speed_label = ctk.CTkLabel(self.stats_frame, text="Speed: 0 KB/s", text_color="#cbd5e1")
        self.speed_label.pack(side="left")

        self.eta_label = ctk.CTkLabel(self.stats_frame, text="ETA: unknown", text_color="#cbd5e1")
        self.eta_label.pack(side="right")

        self.percent_label = ctk.CTkLabel(self.stats_frame, text="0%", text_color="#f1f5f9", font=ctk.CTkFont(weight="bold"))
        self.percent_label.pack(side="top")

        # Control Frame (Pause / Cancel Buttons side-by-side)
        self.controls_frame = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        self.controls_frame.pack(pady=(10, 0), fill="x", padx=10)

        self.pause_btn = ctk.CTkButton(
            self.controls_frame,
            text="Pause",
            fg_color="#d97706",
            hover_color="#b45309",
            text_color="#f1f5f9",
            font=ctk.CTkFont(weight="bold"),
            command=self.toggle_pause
        )
        self.pause_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.cancel_btn = ctk.CTkButton(
            self.controls_frame,
            text="Cancel",
            fg_color="#dc2626",
            hover_color="#b91c1c",
            text_color="#f1f5f9",
            font=ctk.CTkFont(weight="bold"),
            command=self.request_cancel
        )
        self.cancel_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # Credits Label
        self.credits_label = ctk.CTkLabel(
            self,
            text="Created by ZeD",
            text_color="#475569",
            font=ctk.CTkFont(family="Outfit", size=10, weight="bold")
        )
        self.credits_label.pack(side="bottom", pady=(5, 10))

        # Settings selection frame (Save directory & Cookies selector)
        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_frame.pack(side="bottom", fill="x", padx=40, pady=(5, 5))
        
        # Row 1: Directory Selection
        self.dir_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.dir_row.pack(fill="x", pady=2)
        
        display_path = self.truncate_string(self.downloads_dir)
        self.dir_label = ctk.CTkLabel(
            self.dir_row, 
            text=f"Save to: {display_path}", 
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.dir_label.pack(side="left", fill="x", expand=True)
        
        self.dir_btn = ctk.CTkButton(
            self.dir_row,
            text="Browse...",
            width=80,
            height=28,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#f1f5f9",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.change_download_dir
        )
        self.dir_btn.pack(side="right", padx=(10, 0))

        # Row 2: Cookies Selection
        self.cookies_row = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.cookies_row.pack(fill="x", pady=2)
        
        self.cookies_label = ctk.CTkLabel(
            self.cookies_row, 
            text="Cookies: Not loaded (Uses anonymous queries)", 
            text_color="#cbd5e1",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.cookies_label.pack(side="left", fill="x", expand=True)
        
        self.cookies_btn = ctk.CTkButton(
            self.cookies_row,
            text="Load cookies...",
            width=80,
            height=28,
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#f1f5f9",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.load_cookies_file
        )
        self.cookies_btn.pack(side="right", padx=(10, 0))

    # Threaded URL Analysis
    def start_analyze(self):
        url = self.url_entry.get().strip()
        if not url:
            return

        self.analyze_btn.configure(state="disabled", text="Analyzing...")
        self.info_frame.pack_forget()
        
        # Show progress frame for analysis
        self.progress_frame.pack(fill="x", padx=40, pady=15)
        self.stats_frame.pack_forget()
        self.controls_frame.pack_forget()  # Hide controls during analysis
        self.progressbar.configure(mode="indeterminate")
        self.progressbar.set(0)
        self.progressbar.start()
        self.status_label.configure(text="Analyzing video link...")

        self.executor.submit(self.bg_analyze, url)

    def bg_analyze(self, url):
        # Optimized single pass option extraction
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'check_formats': 'cached',
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'socket_timeout': 10,
            'retries': 5,
        }
        if self.ffmpeg_dir:
            ydl_opts['ffmpeg_location'] = self.ffmpeg_dir
        if self.cookies_path:
            ydl_opts['cookiefile'] = self.cookies_path
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError("No video metadata could be retrieved.")
                
                # Check if it returned a playlist structure
                if info.get('_type') == 'playlist':
                    entries = info.get('entries', [])
                    if not entries:
                        raise ValueError("No video entries found in this playlist.")
                        
                    # Extract list of entry URLs
                    playlist_urls = [
                        e_url for entry in entries if entry and (
                            (e_url := entry.get('url') or entry.get('webpage_url')) or
                            (entry.get('id') and (e_url := f"https://www.youtube.com/watch?v={entry.get('id')}"))
                        )
                    ]
                                
                    if not playlist_urls:
                        raise ValueError("No valid video URLs found in this playlist.")
                        
                    duration_str = f"{len(playlist_urls)} videos"
                    sorted_labels = ["1080p", "720p", "480p", "360p", "240p", "144p"]
                    resolution_map = {res: res.replace("p", "") for res in sorted_labels}
                    
                    self.video_info = {
                        "url": url,
                        "title": f"Playlist: {info.get('title', 'Unknown Playlist')}",
                        "uploader": info.get("uploader") or info.get("publisher") or "Various Creators",
                        "duration": duration_str,
                        "resolutions": sorted_labels,
                        "resolution_map": resolution_map,
                        "is_playlist": True,
                        "playlist_entries": playlist_urls
                    }
                else:
                    # Single video: reuse flat extract. Fall back to full only if formats missing.
                    formats = info.get("formats", [])
                    if not formats:
                        ydl_opts_full = {
                            'extract_flat': False,
                            'skip_download': True,
                            'noplaylist': True,
                            'socket_timeout': 10,
                            'retries': 5,
                        }
                        if self.ffmpeg_dir:
                            ydl_opts_full['ffmpeg_location'] = self.ffmpeg_dir
                        if self.cookies_path:
                            ydl_opts_full['cookiefile'] = self.cookies_path
                            
                        with yt_dlp.YoutubeDL(ydl_opts_full) as ydl_full:
                            info = ydl_full.extract_info(url, download=False)
                            formats = info.get("formats", [])

                    duration_secs = info.get("duration", 0)
                    if duration_secs:
                        mins, secs = divmod(duration_secs, 60)
                        hours, mins = divmod(mins, 60)
                        duration_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"
                    else:
                        duration_str = "Unknown"

                    # Vectorized categorisation using optimized comprehensions
                    audio_formats = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") and f.get("acodec") != "none" and f.get("format_id")]
                    video_formats = [f for f in formats if f.get("vcodec") and f.get("vcodec") != "none" and f.get("format_id")]

                    # 1. Size helper
                    def get_est_size(f, dur):
                        fs = f.get("filesize") or f.get("filesize_approx")
                        if not fs and dur:
                            br = f.get("abr") or f.get("tbr") or 128
                            fs = int(br * 1000 * dur / 8)
                        return fs or 0

                    max_audio_filesize = max((get_est_size(f, duration_secs) for f in audio_formats), default=0)

                    # 2. Extract standard resolution standard mapping
                    standards = [144, 240, 360, 480, 720, 1080, 1440, 2160, 4320]
                    
                    def parse_video_format(f, dur, max_aud, ffmpeg_avail):
                        h = f.get("height") or 0
                        w = f.get("width") or 0
                        if not h:
                            return None
                        acodec = f.get("acodec")
                        if not ffmpeg_avail and (not acodec or acodec == "none"):
                            return None
                        res_val = min(w, h) if w and h else h
                        if res_val < 144:
                            return None
                            
                        closest_std = min(standards, key=lambda s: abs(s - res_val))
                        fps = f.get("fps") or 30
                        fps_suffix = "60" if fps >= 50 else ""
                        base_label = f"{closest_std}p{fps_suffix}"
                        
                        tbr = f.get("tbr") or f.get("vbr") or 0
                        fs = f.get("filesize") or f.get("filesize_approx")
                        if not fs and tbr and dur:
                            fs = int(tbr * 1000 * dur / 8)
                        fs = fs or 0
                        
                        if fs and ffmpeg_avail and (not acodec or acodec == "none"):
                            fs += max_aud
                            
                        vcodec = f.get("vcodec") or ""
                        codec_score = 3 if "av01" in vcodec else (2 if "vp09" in vcodec or "vp9" in vcodec else 1)
                        
                        return {
                            "label": base_label,
                            "fmt_id": f.get("format_id"),
                            "filesize": fs,
                            "tbr": tbr,
                            "codec_score": codec_score
                        }

                    parsed_videos = [parsed for f in video_formats if (parsed := parse_video_format(f, duration_secs, max_audio_filesize, self.ffmpeg_available))]
                    
                    best_video_by_res = {}
                    for pv in parsed_videos:
                        lbl = pv["label"]
                        if lbl not in best_video_by_res or (pv["tbr"], pv["codec_score"]) > (best_video_by_res[lbl]["tbr"], best_video_by_res[lbl]["codec_score"]):
                            best_video_by_res[lbl] = pv
                            
                    resolution_map = {
                        f"{lbl} (~{self.format_size(pv['filesize'])})": pv["fmt_id"]
                        for lbl, pv in best_video_by_res.items()
                    }

                    # 3. Extract best audio streams by standard bitrate tiers
                    audio_standards = [96, 128, 192, 256, 320]
                    
                    def parse_audio_format(f, dur):
                        abr = f.get("abr") or f.get("tbr")
                        if not abr:
                            return None
                        closest_abr = min(audio_standards, key=lambda a: abs(a - abr))
                        fs = f.get("filesize") or f.get("filesize_approx")
                        if not fs and dur:
                            fs = int(abr * 1000 * dur / 8)
                        fs = fs or 0
                        return {
                            "standard": closest_abr,
                            "fmt_id": f.get("format_id"),
                            "filesize": fs,
                            "abr": abr
                        }

                    parsed_audios = [parsed for f in audio_formats if (parsed := parse_audio_format(f, duration_secs))]
                    
                    best_audio_by_bitrate = {}
                    for pa in parsed_audios:
                        std = pa["standard"]
                        if std not in best_audio_by_bitrate or pa["abr"] > best_audio_by_bitrate[std]["abr"]:
                            best_audio_by_bitrate[std] = pa
                            
                    audio_map = {
                        f"{std} kbps (Native, ~{self.format_size(pa['filesize'])})": (pa["fmt_id"], std)
                        for std, pa in best_audio_by_bitrate.items()
                    }

                    # Sort video labels
                    def label_sort_key(label):
                        parts = label.split()[0]
                        height_str = parts.replace("p60", "").replace("p", "")
                        try:
                            height = int(height_str)
                        except ValueError:
                            height = 0
                        has_60 = 1 if "60" in parts else 0
                        return (height, has_60)
                        
                    sorted_labels = sorted(resolution_map.keys(), key=label_sort_key, reverse=True)
                    if not sorted_labels:
                        sorted_labels = ["720p (~15 MB)", "360p (~5 MB)"]
                        resolution_map = {sorted_labels[0]: "best", sorted_labels[1]: "best"}
                        
                    # Sort audio labels descending by bitrate
                    def audio_sort_key(label):
                        try:
                            return int(label.split()[0])
                        except ValueError:
                            return 0
                            
                    sorted_audio_labels = sorted(audio_map.keys(), key=audio_sort_key, reverse=True)

                    self.video_info = {
                        "url": url,
                        "title": info.get("title", "Unknown Title"),
                        "uploader": info.get("uploader", "Unknown Channel"),
                        "duration": duration_str,
                        "resolutions": sorted_labels,
                        "resolution_map": resolution_map,
                        "audio_resolutions": sorted_audio_labels,
                        "audio_map": audio_map,
                        "is_playlist": False
                    }
                    
                # Update UI inside Tkinter safe block
                self.after(0, self.update_ui_after_analysis)
        except Exception as e:
            self.after(0, lambda: self.show_alert("Error", f"Invalid Video or Verification Failed:\n{str(e)}", is_error=True))

    def update_ui_after_analysis(self):
        self.analyze_btn.configure(state="normal", text="Analyze")
        
        # Stop and hide progress frame
        self.progressbar.stop()
        self.progressbar.configure(mode="determinate")
        self.progress_frame.pack_forget()
        
        # Restore stats and controls packing
        self.stats_frame.pack(fill="x", padx=10, pady=5)
        self.controls_frame.pack(pady=(10, 0), fill="x", padx=10)
        
        # Populate widgets
        self.title_label.configure(text=self.video_info["title"])
        self.channel_label.configure(text=f"Channel: {self.video_info['uploader']}")
        self.duration_label.configure(text=f"Duration: {self.video_info['duration']}")
        
        # Populate resolutions
        self.mp4_quality_menu.configure(values=self.video_info["resolutions"])
        self.mp4_quality_menu.set(self.video_info["resolutions"][0])

        # Populate audio bitrates dynamically if available
        if "audio_resolutions" in self.video_info and self.video_info["audio_resolutions"] and self.ffmpeg_available:
            self.mp3_quality_menu.configure(values=self.video_info["audio_resolutions"])
            self.mp3_quality_menu.set(self.video_info["audio_resolutions"][0])
        else:
            if not self.ffmpeg_available:
                self.mp3_quality_menu.configure(values=["Original / Best Quality"])
                self.mp3_quality_menu.set("Original / Best Quality")
            else:
                self.mp3_quality_menu.configure(values=["320 kbps (High)", "256 kbps", "192 kbps (Medium)", "128 kbps (Low)"])
                self.mp3_quality_menu.set("320 kbps (High)")

        # Show info frame
        self.info_frame.pack(fill="x", padx=40, pady=10)

    def show_alert(self, title, message, is_error=False):
        """Unified, thread-safe dialog window for warnings, errors, and info alerts."""
        if is_error:
            self.analyze_btn.configure(state="normal", text="Analyze")
            
            # Stop and hide progress frame on error
            self.progressbar.stop()
            self.progressbar.configure(mode="determinate")
            self.progress_frame.pack_forget()
            
        # Build custom dialog window
        alert_win = ctk.CTkToplevel(self)
        alert_win.title(title)
        # Adjust dimensions dynamically for longer error tracebacks
        geometry = "420x200" if is_error else "380x170"
        alert_win.geometry(geometry)
        alert_win.attributes("-topmost", True)
        
        wraplength = 380 if is_error else 340
        lbl = ctk.CTkLabel(alert_win, text=message, wraplength=wraplength, font=ctk.CTkFont(size=13))
        lbl.pack(pady=25 if is_error else 20, padx=20)
        
        btn = ctk.CTkButton(alert_win, text="OK", width=80, command=alert_win.destroy)
        btn.pack(pady=(0, 10))

    def push_progress_event(self, data):
        """Pushes updates securely from execution threads back to Tkinter event loop."""
        self.after(0, self.update_progress_ui, data)

    # Threaded Downloads via Queue
    def start_download(self, download_type):
        if not self.video_info:
            return

        url = self.video_info["url"]
        
        # Disable analyze button during download
        self.analyze_btn.configure(state="disabled")
        
        # Hide Info Frame to make room for progress bar
        self.info_frame.pack_forget()

        # Show Progress Section
        self.progress_frame.pack(fill="x", padx=40, pady=15)
        self.stats_frame.pack(fill="x", padx=10, pady=5)
        self.controls_frame.pack(pady=(10, 0), fill="x", padx=10)
        self.progressbar.configure(mode="determinate")
        self.progressbar.set(0)
        self.percent_label.configure(text="0%")
        self.speed_label.configure(text="Speed: 0 KB/s")
        self.eta_label.configure(text="ETA: unknown")
        self.status_label.configure(text="Connecting to YouTube...")

        # Setup job controls
        self.cancel_requested = False
        self.pause_requested = False
        self.pause_btn.configure(text="Pause", fg_color="#d97706", hover_color="#b45309", state="normal")
        self.cancel_btn.configure(state="normal")

        # Setup job status variables
        self.active_download_job = {
            "status": "pending",
            "progress": 0.0,
            "speed": "0 KB/s",
            "eta": "unknown",
            "error": None,
            "done": False,
            "errors": [],
            "successful_count": 0,
            "current_index": 0,
            "current_title": "Initializing..."
        }

        # Quality config
        if download_type == "mp3":
            if self.ffmpeg_available:
                raw_quality = self.mp3_quality_menu.get()
                if self.video_info and "audio_map" in self.video_info and raw_quality in self.video_info["audio_map"]:
                    fmt_id, abr_int = self.video_info["audio_map"][raw_quality]
                    quality = f"{fmt_id}:{abr_int}"
                else:
                    quality = raw_quality.split()[0]  # e.g., "320"
            else:
                quality = "best"
        else:
            raw_quality = self.mp4_quality_menu.get()
            if self.video_info and "resolution_map" in self.video_info:
                quality = self.video_info["resolution_map"].get(raw_quality, raw_quality.replace("p", ""))
            else:
                quality = raw_quality.replace("p", "")

        # Queue setup and Worker initialization
        is_playlist = self.video_info.get("is_playlist", False) if self.video_info else False
        playlist_entries = self.video_info.get("playlist_entries", []) if self.video_info else []

        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
            except queue.Empty:
                break

        if is_playlist:
            for idx, entry_url in enumerate(playlist_entries):
                self.download_queue.put((idx, entry_url))
        else:
            self.download_queue.put((0, url))

        self.executor.submit(self.bg_download_worker, download_type, quality)

    def bg_download_worker(self, download_type, quality):
        is_playlist = self.video_info.get("is_playlist", False) if self.video_info else False
        total_videos = self.download_queue.qsize()
        success_count = 0
        failed_entries = []
        last_update_time = 0.0

        def hook(d):
            nonlocal last_update_time
            
            # Safe exit if user cancelled
            if self.cancel_requested:
                raise yt_dlp.utils.DownloadError("Download cancelled by user")

            # Pause mechanism by blocking the execution thread
            while self.pause_requested and not self.cancel_requested:
                self.push_progress_event({
                    "status": "paused",
                    "message": f"Paused at video {success_count + len(failed_entries) + 1} of {total_videos}..."
                })
                time.sleep(0.1)

            if self.cancel_requested:
                raise yt_dlp.utils.DownloadError("Download cancelled by user")

            # Restore status if resuming
            if self.active_download_job and self.active_download_job["status"] == "paused":
                self.active_download_job["status"] = "downloading"
            
            current_title = "Unknown Title"
            if d.get('info_dict'):
                current_title = d['info_dict'].get('title', 'Unknown Title')
                if self.active_download_job:
                    self.active_download_job["current_title"] = current_title

            current_time = time.time()
            status = d['status']
            if status == 'downloading':
                # Throttle updates to at most once every 100ms
                if current_time - last_update_time < 0.1:
                    return
                last_update_time = current_time

                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                video_percent = (downloaded / total * 100.0) if total > 0 else (
                    (d.get('fragment_index', 0) / d.get('fragment_count', 1) * 100.0) if d.get('fragment_count') else 0.0
                )
                
                # Overall progress calculation
                if is_playlist:
                    percent = ((success_count + len(failed_entries)) / total_videos * 100.0) + (video_percent / total_videos)
                    status_text = f"Downloading video {success_count + len(failed_entries) + 1} of {total_videos}...\n{current_title}"
                else:
                    percent = video_percent
                    status_text = f"Downloading: {current_title}"
                
                speed = d.get('speed')
                eta = d.get('eta')
                
                speed_str = "0 KB/s"
                if speed:
                    speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed > 1024 * 1024 else f"{speed / 1024:.1f} KB/s"
                eta_str = f"{eta}s" if eta else "unknown"
                
                self.push_progress_event({
                    "status": "downloading",
                    "progress": percent,
                    "speed": speed_str,
                    "eta": eta_str,
                    "message": status_text
                })
            elif status == 'finished':
                percent = ((success_count + len(failed_entries) + 1) / total_videos * 100.0) if is_playlist else 100.0
                status_text = f"Finished downloading video {success_count + len(failed_entries) + 1} of {total_videos}..." if is_playlist else "Finalizing file (converting or merging)..."
                
                self.push_progress_event({
                    "status": "processing",
                    "progress": percent,
                    "message": status_text
                })

        # Base configuration
        ydl_opts = {
            'progress_hooks': [hook],
            'outtmpl': os.path.join(self.downloads_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'concurrent_fragment_downloads': 10,  # Speed optimization: 10 parallel fragments
            'buffersize': 1024 * 1024,
            'http_chunk_size': 10485760,
            # Socket & anti-throttling tuning
            'socket_timeout': 10,
            'retries': 5,
            'fragment_retries': 5,
            'download_archive': os.path.join(self.downloads_dir, 'koinloader_archive.txt'), # Prevent duplicate downloads
            'http_headers': {
                'Connection': 'keep-alive',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            }
        }
        if self.ffmpeg_dir:
            ydl_opts['ffmpeg_location'] = self.ffmpeg_dir
        if self.cookies_path:
            ydl_opts['cookiefile'] = self.cookies_path

        # Enable external downloader aria2c if it's available on system path or local bin
        aria2c_path = shutil.which("aria2c")
        if aria2c_path is None:
            local_aria2c = os.path.join(os.getcwd(), "bin", "aria2c.exe") if os.name == 'nt' else os.path.join(os.getcwd(), "bin", "aria2c")
            if os.path.exists(local_aria2c):
                aria2c_path = local_aria2c

        if aria2c_path is not None:
            ydl_opts.update({
                'external_downloader': aria2c_path,
                'external_downloader_args': [
                    '--min-split-size=1M',
                    '--max-connection-per-server=16',
                    '--split=16',
                    '--max-concurrent-downloads=5',
                    '--file-allocation=none'
                ]
            })

        has_atomicparsley = (shutil.which("AtomicParsley") is not None or 
                             shutil.which("atomicparsley") is not None)

        # Format and post-processor setups
        if download_type == "mp3":
            if ":" in quality:
                fmt_id, target_abr = quality.split(":")
            else:
                fmt_id = 'bestaudio/best'
                target_abr = quality  # e.g., "320"
                
            if self.ffmpeg_available:
                ydl_opts.update({
                    'format': fmt_id,
                    'writethumbnail': True,
                    'postprocessors': [
                        {
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': target_abr,
                        },
                        {
                            'key': 'FFmpegThumbnailsConvertor',
                            'format': 'jpg',
                        },
                        {
                            'key': 'FFmpegMetadata',
                            'add_metadata': True,
                        },
                        {
                            'key': 'FFmpegEmbedThumbnail',
                        }
                    ],
                })
            else:
                ydl_opts.update({
                    'format': 'bestaudio[ext=m4a]/best',
                })
        else:  # mp4
            if is_playlist:
                if self.ffmpeg_available:
                    format_str = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={quality}]+bestaudio/best'
                else:
                    format_str = f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best'
            else:
                if self.ffmpeg_available:
                    if quality == "best":
                        format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
                    else:
                        format_str = f'{quality}+bestaudio[ext=m4a]/{quality}+bestaudio/best'
                else:
                    if quality == "best":
                        format_str = 'best[ext=mp4]/best'
                    else:
                        format_str = f'{quality}/best'
                        
            ydl_opts.update({
                'format': format_str,
            })
            
            if self.ffmpeg_available:
                ydl_opts.update({
                    'merge_output_format': 'mp4',
                })
                if has_atomicparsley:
                    ydl_opts.update({
                        'writethumbnail': True,
                        'postprocessors': [
                            {
                                'key': 'FFmpegThumbnailsConvertor',
                                'format': 'jpg',
                            },
                            {
                                'key': 'FFmpegMetadata',
                                'add_metadata': True,
                            },
                            {
                                'key': 'FFmpegEmbedThumbnail',
                            }
                        ]
                    })
                else:
                    ydl_opts.update({
                        'postprocessors': [
                            {
                                'key': 'FFmpegMetadata',
                                'add_metadata': True,
                            }
                        ]
                    })

        # Process the queue worker loop
        try:
            while not self.download_queue.empty():
                if self.cancel_requested:
                    raise yt_dlp.utils.DownloadError("Download cancelled by user")

                # Handle pause checking before popping next video
                while self.pause_requested and not self.cancel_requested:
                    self.push_progress_event({
                        "status": "paused",
                        "message": f"Paused at video {success_count + len(failed_entries) + 1} of {total_videos}..."
                    })
                    time.sleep(0.1)

                if self.cancel_requested:
                    raise yt_dlp.utils.DownloadError("Download cancelled by user")

                try:
                    idx, entry_url = self.download_queue.get_nowait()
                except queue.Empty:
                    break

                self.push_progress_event({
                    "status": "downloading",
                    "progress": ((success_count + len(failed_entries)) / total_videos * 100.0),
                    "message": f"Downloading video {idx + 1} of {total_videos}..."
                })

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([entry_url])
                    success_count += 1
                    if self.active_download_job:
                        self.active_download_job["successful_count"] = success_count
                except Exception as e:
                    if self.cancel_requested or "cancelled" in str(e).lower():
                        self.download_queue.task_done()
                        raise yt_dlp.utils.DownloadError("Download cancelled by user")
                    
                    # Store individual error and proceed
                    failed_entries.append((entry_url, str(e)))
                    if self.active_download_job:
                        self.active_download_job["errors"].append((entry_url, str(e)))

                self.download_queue.task_done()

            # Compile final outcomes
            done_status = "completed"
            err_msg = None
            err_summary = None

            if failed_entries:
                summary_lines = [f"- {url_val}: {self.truncate_string(err_val, 80)}" for url_val, err_val in failed_entries]
                err_summary = f"Successfully downloaded {success_count} of {total_videos} videos.\n\nErrors encountered:\n" + "\n".join(summary_lines)
                if success_count > 0:
                    done_status = "partial_success"
                else:
                    done_status = "failed"
                    err_msg = "All video downloads failed.\n\n" + err_summary

            self.push_progress_event({
                "status": done_status,
                "error": err_msg,
                "error_summary": err_summary,
                "done": True
            })

        except Exception as e:
            done_status = "cancelled" if (self.cancel_requested or "cancelled" in str(e).lower()) else "failed"
            self.push_progress_event({
                "status": done_status,
                "error": str(e),
                "done": True
            })

    def update_progress_ui(self, data):
        """Processes progress updates securely inside Tkinter safe block."""
        if not self.active_download_job:
            return

        self.active_download_job.update(data)
        job = self.active_download_job
        is_playlist = self.video_info.get("is_playlist", False) if self.video_info else False
        
        if job["status"] == "downloading":
            self.status_label.configure(text=job.get("message", "Downloading audio/video streams..."))
            self.progressbar.set(job["progress"] / 100.0)
            self.percent_label.configure(text=f"{job['progress']:.1f}%")
            self.speed_label.configure(text=f"Speed: {job['speed']}")
            self.eta_label.configure(text=f"ETA: {job['eta']}")
            
        elif job["status"] == "paused":
            self.status_label.configure(text=job.get("message", "Download paused by user."))
            self.speed_label.configure(text="Speed: Paused")
            self.eta_label.configure(text="ETA: Paused")
            
        elif job["status"] == "processing":
            self.status_label.configure(text=job.get("message", "Finalizing formats (Muxing / Encoding)..."))
            self.progressbar.set(job["progress"] / 100.0 if is_playlist else 1.0)
            self.percent_label.configure(text=f"{job['progress']:.1f}%" if is_playlist else "100%")
            self.speed_label.configure(text="Speed: ---")
            self.eta_label.configure(text="ETA: ---")

        elif job["status"] == "completed":
            self.status_label.configure(text="Download Complete! Saved to Downloads.")
            self.progressbar.set(1.0)
            self.percent_label.configure(text="100%")
            self.speed_label.configure(text="Speed: ---")
            self.eta_label.configure(text="ETA: ---")
            
            # Hide progress bar and restore info frame
            self.progress_frame.pack_forget()
            self.info_frame.pack(fill="x", padx=40, pady=10)
            
            # Re-enable inputs
            self.analyze_btn.configure(state="normal")
            self.mp4_download_btn.configure(state="normal")
            self.mp3_download_btn.configure(state="normal")
            
            self.active_download_job = None
            self.show_success_popup()

        elif job["status"] == "partial_success":
            self.status_label.configure(text="Download complete with some errors.")
            self.progressbar.set(1.0)
            self.percent_label.configure(text="100%")
            self.speed_label.configure(text="Speed: ---")
            self.eta_label.configure(text="ETA: ---")
            
            self.progress_frame.pack_forget()
            self.info_frame.pack(fill="x", padx=40, pady=10)
            
            # Re-enable inputs
            self.analyze_btn.configure(state="normal")
            self.mp4_download_btn.configure(state="normal")
            self.mp3_download_btn.configure(state="normal")
            
            summary = job.get("error_summary", "Some videos in the playlist failed to download.")
            self.active_download_job = None
            self.show_alert("Error", f"Playlist Complete (with errors):\n\n{summary}", is_error=True)

        elif job["status"] == "cancelled":
            self.status_label.configure(text="Download cancelled by user.")
            self.progressbar.set(0)
            
            self.progress_frame.pack_forget()
            self.info_frame.pack(fill="x", padx=40, pady=10)
            
            # Re-enable inputs
            self.analyze_btn.configure(state="normal")
            self.mp4_download_btn.configure(state="normal")
            self.mp3_download_btn.configure(state="normal")
            
            self.active_download_job = None
            self.show_alert("Cancelled", "The download operation has been cancelled.")

        elif job["status"] == "failed":
            self.status_label.configure(text="Download failed.")
            self.progressbar.set(0)
            
            self.progress_frame.pack_forget()
            self.info_frame.pack(fill="x", padx=40, pady=10)
            
            # Re-enable inputs
            self.analyze_btn.configure(state="normal")
            self.mp4_download_btn.configure(state="normal")
            self.mp3_download_btn.configure(state="normal")
            
            err_msg = job["error"]
            self.active_download_job = None
            self.show_alert("Error", f"Download Error:\n{err_msg}", is_error=True)

    def toggle_pause(self):
        if not self.active_download_job:
            return
            
        if self.pause_requested:
            self.pause_requested = False
            self.pause_btn.configure(text="Pause", fg_color="#d97706", hover_color="#b45309")
        else:
            self.pause_requested = True
            self.pause_btn.configure(text="Resume", fg_color="#059669", hover_color="#047857")

    def request_cancel(self):
        self.cancel_requested = True
        self.status_label.configure(text="Cancelling download...")
        self.cancel_btn.configure(state="disabled")
        self.pause_btn.configure(state="disabled")

    def show_success_popup(self):
        success_win = ctk.CTkToplevel(self)
        success_win.title("Finished")
        success_win.geometry("380x170")
        success_win.attributes("-topmost", True)
        
        msg = "Success!\n\nYour file has been downloaded directly into your system Downloads folder."
        if not self.ffmpeg_available:
            msg += "\n\n(Note: Saved audio format is M4A as FFmpeg was not detected)"
            
        lbl = ctk.CTkLabel(
            success_win, 
            text=msg,
            wraplength=340,
            font=ctk.CTkFont(size=13)
        )
        lbl.pack(pady=20, padx=20)
        
        btn = ctk.CTkButton(success_win, text="Close", width=80, command=success_win.destroy)
        btn.pack(pady=(0, 10))

    def on_closing(self):
        self.cancel_requested = True
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            self.executor.shutdown(wait=False)
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = DownloaderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

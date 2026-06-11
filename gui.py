import os
import sys
import threading
import shutil
from pathlib import Path
import customtkinter as ctk
import yt_dlp

# Set CustomTkinter window preferences
ctk.set_appearance_mode("Dark")  # Modes: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue", "green", "dark-blue"

class DownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("StreamVault - YouTube Downloader")
        self.geometry("640x560")
        self.resizable(False, False)

        # State Variables
        self.video_info = None
        self.active_download_job = None
        self.downloads_dir = self.get_download_path()
        self.ffmpeg_available = False

        # Build UI
        self.create_widgets()

        # Check FFmpeg asynchronously to keep GUI loading instant
        self.status_label.configure(text="Checking system components...")
        self.stats_frame.pack_forget()
        self.progressbar.configure(mode="indeterminate")
        self.progressbar.start()
        self.progress_frame.pack(fill="x", padx=40, pady=5)
        threading.Thread(target=self.bg_check_ffmpeg, daemon=True).start()

        # Start background polling loop
        self.poll_active = True
        self.poll_progress()

    def get_download_path(self):
        """Returns standard Windows Downloads path, falling back to home dir."""
        try:
            import winreg
            sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
                return winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
        except Exception:
            return str(Path.home() / "Downloads")

    def change_download_dir(self):
        from tkinter import filedialog
        selected_dir = filedialog.askdirectory(
            parent=self,
            title="Select Download Directory",
            initialdir=self.downloads_dir
        )
        if selected_dir:
            self.downloads_dir = selected_dir
            display_path = selected_dir
            if len(display_path) > 55:
                display_path = display_path[:25] + "..." + display_path[-27:]
            self.dir_label.configure(text=f"Save to: {display_path}")

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
        """Checks if FFmpeg is available on PATH, in npm installer, or via static_ffmpeg."""
        # 1. Check if npm-installed ffmpeg/ffprobe exist in AppData (direct and nested structures)
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            # Direct structure (npm install -g @ffmpeg-installer/win32-x64)
            npm_ffmpeg_dir_1 = os.path.join(appdata, "npm", "node_modules", "@ffmpeg-installer", "win32-x64")
            npm_ffprobe_dir_1 = os.path.join(appdata, "npm", "node_modules", "@ffprobe-installer", "win32-x64")
            
            # Nested structure (npm install -g @ffmpeg-installer/ffmpeg)
            npm_ffmpeg_dir_2 = os.path.join(appdata, "npm", "node_modules", "@ffmpeg-installer", "ffmpeg", "node_modules", "@ffmpeg-installer", "win32-x64")
            npm_ffprobe_dir_2 = os.path.join(appdata, "npm", "node_modules", "@ffprobe-installer", "ffprobe", "node_modules", "@ffprobe-installer", "win32-x64")

            for path in [npm_ffmpeg_dir_1, npm_ffmpeg_dir_2]:
                if os.path.exists(path):
                    os.environ["PATH"] = path + os.pathsep + os.environ["PATH"]
                    break
            for path in [npm_ffprobe_dir_1, npm_ffprobe_dir_2]:
                if os.path.exists(path):
                    os.environ["PATH"] = path + os.pathsep + os.environ["PATH"]
                    break

        # 2. Check if ffmpeg is on system PATH (including the npm paths we just added)
        if shutil.which("ffmpeg") is not None:
            self.ffmpeg_available = True
            self.after(0, self.update_ffmpeg_status, "FFmpeg: Detected (Local Package)")
            return

        # 3. Try static_ffmpeg as final fallback
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
            if shutil.which("ffmpeg") is not None:
                self.ffmpeg_available = True
                self.after(0, self.update_ffmpeg_status, "FFmpeg: Detected (Static)")
                return
        except Exception:
            pass

        # 4. Fallback: No FFmpeg
        self.ffmpeg_available = False
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

    def create_widgets(self):
        # Header Label
        self.header_label = ctk.CTkLabel(
            self, 
            text="StreamVault", 
            font=ctk.CTkFont(family="Outfit", size=32, weight="bold")
        )
        self.header_label.pack(pady=(15, 2))

        self.subtitle_label = ctk.CTkLabel(
            self, 
            text="Convert YouTube videos to MP3 & MP4", 
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Outfit", size=14)
        )
        self.subtitle_label.pack(pady=(0, 10))

        # FFmpeg Status Label
        self.ffmpeg_status_label = ctk.CTkLabel(
            self,
            text="Checking system components...",
            text_color="#94a3b8",
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
            font=ctk.CTkFont(size=13)
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.analyze_btn = ctk.CTkButton(
            self.search_frame,
            text="Analyze",
            width=100,
            height=45,
            font=ctk.CTkFont(weight="bold"),
            command=self.start_analyze
        )
        self.analyze_btn.pack(side="right")

        # Info Frame (hidden by default)
        self.info_frame = ctk.CTkFrame(self, corner_radius=16)
        
        self.title_label = ctk.CTkLabel(
            self.info_frame, 
            text="", 
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
        self.tabview = ctk.CTkTabview(self.info_frame, height=180)
        self.tabview.pack(fill="x", padx=20, pady=(0, 15))
        
        self.tab_mp4 = self.tabview.add("MP4 Video")
        self.tab_mp3 = self.tabview.add("MP3 Audio")

        # MP4 Tab Layout
        self.mp4_dropdown_label = ctk.CTkLabel(self.tab_mp4, text="Select Video Quality:")
        self.mp4_dropdown_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

        self.mp4_quality_menu = ctk.CTkOptionMenu(self.tab_mp4, width=160, values=["720p", "360p"])
        self.mp4_quality_menu.grid(row=0, column=1, padx=20, pady=(15, 5), sticky="w")

        self.mp4_download_btn = ctk.CTkButton(
            self.tab_mp4, 
            text="Download Video", 
            fg_color="#10b981", 
            hover_color="#059669",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.start_download("mp4")
        )
        self.mp4_download_btn.grid(row=1, column=0, columnspan=2, padx=20, pady=(15, 10), sticky="ew")

        # MP3 Tab Layout
        self.mp3_dropdown_label = ctk.CTkLabel(self.tab_mp3, text="Select Audio Bitrate:")
        self.mp3_dropdown_label.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

        self.mp3_quality_menu = ctk.CTkOptionMenu(
            self.tab_mp3, 
            width=160, 
            values=["320 kbps (High)", "256 kbps", "192 kbps (Medium)", "128 kbps (Low)"]
        )
        self.mp3_quality_menu.set("320 kbps (High)")
        self.mp3_quality_menu.grid(row=0, column=1, padx=20, pady=(15, 5), sticky="w")

        self.mp3_download_btn = ctk.CTkButton(
            self.tab_mp3, 
            text="Download Audio", 
            fg_color="#8b5cf6", 
            hover_color="#7c3aed",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.start_download("mp3")
        )
        self.mp3_download_btn.grid(row=1, column=0, columnspan=2, padx=20, pady=(15, 10), sticky="ew")

        # Progress Frame (hidden/visible as needed)
        self.progress_frame = ctk.CTkFrame(self, corner_radius=16, fg_color="transparent")
        
        self.status_label = ctk.CTkLabel(
            self.progress_frame, 
            text="Downloading video...", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.status_label.pack(anchor="w", padx=10, pady=(5, 5))

        # Progressbar
        self.progressbar = ctk.CTkProgressBar(self.progress_frame)
        self.progressbar.pack(fill="x", padx=10, pady=5)
        self.progressbar.set(0)

        # Status stats (Speed / ETA / Percent)
        self.stats_frame = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=10, pady=5)

        self.speed_label = ctk.CTkLabel(self.stats_frame, text="Speed: 0 KB/s", text_color="#94a3b8")
        self.speed_label.pack(side="left")

        self.eta_label = ctk.CTkLabel(self.stats_frame, text="ETA: unknown", text_color="#94a3b8")
        self.eta_label.pack(side="right")

        self.percent_label = ctk.CTkLabel(self.stats_frame, text="0%", font=ctk.CTkFont(weight="bold"))
        self.percent_label.pack(side="top")

        # Credits Label
        self.credits_label = ctk.CTkLabel(
            self,
            text="Created by ZeD",
            text_color="#64748b",
            font=ctk.CTkFont(family="Outfit", size=10, weight="bold")
        )
        self.credits_label.pack(side="bottom", pady=(5, 10))

        # Directory selection frame
        self.dir_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dir_frame.pack(side="bottom", fill="x", padx=40, pady=(5, 5))
        
        display_path = self.downloads_dir
        if len(display_path) > 55:
            display_path = display_path[:25] + "..." + display_path[-27:]
            
        self.dir_label = ctk.CTkLabel(
            self.dir_frame, 
            text=f"Save to: {display_path}", 
            text_color="#94a3b8",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.dir_label.pack(side="left", fill="x", expand=True)
        
        self.dir_btn = ctk.CTkButton(
            self.dir_frame,
            text="Browse...",
            width=80,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self.change_download_dir
        )
        self.dir_btn.pack(side="right", padx=(10, 0))

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
        self.progressbar.configure(mode="indeterminate")
        self.progressbar.set(0)
        self.progressbar.start()
        self.status_label.configure(text="Analyzing video link...")

        threading.Thread(target=self.bg_analyze, args=(url,), daemon=True).start()

    def bg_analyze(self, url):
        # We start with flat extraction to quickly check if it is a playlist
        ydl_opts = {
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'check_formats': 'cached',
            'youtube_include_dash_manifest': False,
            'youtube_include_hls_manifest': False,
            'socket_timeout': 10,
            'retries': 5,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Check if it returned a playlist structure
                if info.get('_type') == 'playlist':
                    entries = info.get('entries', [])
                    if not entries:
                        raise ValueError("No video entries found in this playlist.")
                        
                    playlist_urls = []
                    for entry in entries:
                        if entry:
                            # entry can be a dict or a string URL
                            e_url = entry.get('url') or entry.get('webpage_url')
                            if not e_url and entry.get('id'):
                                e_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                            if e_url:
                                playlist_urls.append(e_url)
                                
                    if not playlist_urls:
                        raise ValueError("No valid video URLs found in this playlist.")
                        
                    duration_str = f"{len(playlist_urls)} videos"
                    sorted_labels = ["1080p", "720p", "480p", "360p", "240p", "144p"]
                    resolution_map = {
                        "1080p": "1080",
                        "720p": "720",
                        "480p": "480",
                        "360p": "360",
                        "240p": "240",
                        "144p": "144"
                    }
                    
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
                    # Single video: re-extract with full metadata to retrieve format details
                    ydl_opts_full = {
                        'extract_flat': False,
                        'skip_download': True,
                        'noplaylist': True,
                        'check_formats': 'cached',
                        'youtube_include_dash_manifest': False,
                        'youtube_include_hls_manifest': False,
                        'socket_timeout': 10,
                        'retries': 5,
                    }
                    with yt_dlp.YoutubeDL(ydl_opts_full) as ydl_full:
                        info = ydl_full.extract_info(url, download=False)
                        
                    # Format durations and get seconds for size calculation
                    duration_secs = info.get("duration", 0)
                    if duration_secs:
                        mins, secs = divmod(duration_secs, 60)
                        hours, mins = divmod(mins, 60)
                        duration_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"
                    else:
                        duration_str = "Unknown"

                    # Get formats
                    formats = info.get("formats", [])
                    
                    # 1. First, find best audio-only stream size to add to video size estimations
                    max_audio_filesize = 0
                    max_audio_bitrate = 128
                    for f in formats:
                        vcodec = f.get("vcodec")
                        acodec = f.get("acodec")
                        if vcodec == "none" and acodec and acodec != "none":
                            abr = f.get("abr") or f.get("tbr") or 128
                            fs = f.get("filesize") or f.get("filesize_approx")
                            if not fs and abr and duration_secs:
                                fs = int(abr * 1000 * duration_secs / 8)
                            if fs and fs > max_audio_filesize:
                                max_audio_filesize = fs
                                max_audio_bitrate = abr

                    # 2. Extract video resolutions and map them with size estimations
                    resolution_map = {}
                    for f in formats:
                        w = f.get("width")
                        h = f.get("height")
                        vcodec = f.get("vcodec")
                        acodec = f.get("acodec")
                        fps = f.get("fps")
                        fmt_id = f.get("format_id")
                        
                        # Ensure it's a valid video format and has a format ID
                        if not h or not fmt_id:
                            continue
                        if not vcodec or vcodec == "none":
                            continue
                            
                        # If ffmpeg is missing, only include combined formats
                        if not self.ffmpeg_available:
                            if not acodec or acodec == "none":
                                continue
                                
                        # Calculate resolution label
                        if w and h:
                            res_label = min(w, h)
                        else:
                            res_label = h
                            
                        # Ignore extremely low resolutions under 144
                        if res_label < 144:
                            continue
                            
                        # Map to nearest standard resolution
                        standards = [144, 240, 360, 480, 720, 1080, 1440, 2160, 4320]
                        closest_std = min(standards, key=lambda s: abs(s - res_label))
                        
                        fps_suffix = "60" if fps and fps >= 50 else ""
                        base_label = f"{closest_std}p{fps_suffix}"
                        
                        # Estimate total size of this video format
                        filesize = f.get("filesize") or f.get("filesize_approx")
                        vbr = f.get("vbr") or f.get("tbr")
                        if not filesize and vbr and duration_secs:
                            filesize = int(vbr * 1000 * duration_secs / 8)
                            
                        # Add max audio size if adaptive video (separate streams)
                        if filesize and self.ffmpeg_available and (not acodec or acodec == "none"):
                            filesize += max_audio_filesize
                            
                        size_text = self.format_size(filesize)
                        label_str = f"{base_label} (~{size_text})"
                        
                        resolution_map[label_str] = fmt_id
                    
                    # 3. Extract audio bitrates and map them with size annotations
                    audio_map = {}
                    for f in formats:
                        vcodec = f.get("vcodec")
                        acodec = f.get("acodec")
                        fmt_id = f.get("format_id")
                        
                        # We only want native audio-only formats
                        if vcodec != "none" or not acodec or acodec == "none" or not fmt_id:
                            continue
                            
                        abr = f.get("abr") or f.get("tbr")
                        if not abr:
                            continue
                            
                        filesize = f.get("filesize") or f.get("filesize_approx")
                        if not filesize and duration_secs:
                            filesize = int(abr * 1000 * duration_secs / 8)
                            
                        abr_int = int(abr)
                        size_text = self.format_size(filesize)
                        label_str = f"{abr_int} kbps (Native, ~{size_text})"
                        
                        audio_map[label_str] = (fmt_id, abr_int)

                    # Sort video keys
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
            self.after(0, lambda: self.show_error(f"Invalid Video or Verification Failed:\n{str(e)}"))

    def update_ui_after_analysis(self):
        self.analyze_btn.configure(state="normal", text="Analyze")
        
        # Stop and hide progress frame
        self.progressbar.stop()
        self.progressbar.configure(mode="determinate")
        self.progress_frame.pack_forget()
        
        # Restore stats frame packaging for downloads
        self.stats_frame.pack(fill="x", padx=10, pady=5)
        
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

    def show_error(self, message):
        self.analyze_btn.configure(state="normal", text="Analyze")
        
        # Stop and hide progress frame on error
        self.progressbar.stop()
        self.progressbar.configure(mode="determinate")
        self.progress_frame.pack_forget()
        self.stats_frame.pack(fill="x", padx=10, pady=5)
        
        # Show a temporary popup message box
        err_win = ctk.CTkToplevel(self)
        err_win.title("Error")
        err_win.geometry("380x170")
        err_win.attributes("-topmost", True)
        
        lbl = ctk.CTkLabel(err_win, text=message, wraplength=340, font=ctk.CTkFont(size=13))
        lbl.pack(pady=20, padx=20)
        
        btn = ctk.CTkButton(err_win, text="OK", width=80, command=err_win.destroy)
        btn.pack(pady=(0, 10))

    # Threaded Downloads
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
        self.progressbar.configure(mode="determinate")
        self.progressbar.set(0)
        self.percent_label.configure(text="0%")
        self.speed_label.configure(text="Speed: 0 KB/s")
        self.eta_label.configure(text="ETA: unknown")
        self.status_label.configure(text="Connecting to YouTube...")

        # Setup job status variables
        self.active_download_job = {
            "status": "pending",
            "progress": 0.0,
            "speed": "0 KB/s",
            "eta": "unknown",
            "error": None,
            "done": False
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

        threading.Thread(
            target=self.bg_download, 
            args=(url, download_type, quality), 
            daemon=True
        ).start()

    def bg_download(self, url, download_type, quality):
        is_playlist = self.video_info.get("is_playlist", False) if self.video_info else False
        playlist_entries = self.video_info.get("playlist_entries", []) if self.video_info else []
        total_videos = len(playlist_entries) if is_playlist else 1
        
        current_video_idx = 0
        current_title = "Initializing..."

        def hook(d):
            nonlocal current_video_idx, current_title
            
            if d.get('info_dict'):
                current_title = d['info_dict'].get('title', 'Unknown Title')
                
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    video_percent = (downloaded / total * 100.0)
                elif d.get('fragment_count'):
                    frag_index = d.get('fragment_index', 0)
                    frag_count = d.get('fragment_count', 1)
                    video_percent = (frag_index / frag_count * 100.0)
                else:
                    video_percent = 0.0
                
                # Overall progress calculation
                if is_playlist:
                    percent = (current_video_idx / total_videos * 100.0) + (video_percent / total_videos)
                    status_text = f"Downloading video {current_video_idx + 1} of {total_videos}...\n({current_title})"
                else:
                    percent = video_percent
                    status_text = f"Downloading: {current_title}"
                
                speed = d.get('speed')
                eta = d.get('eta')
                
                speed_str = "0 KB/s"
                if speed:
                    if speed > 1024 * 1024:
                        speed_str = f"{speed / (1024*1024):.1f} MB/s"
                    else:
                        speed_str = f"{speed / 1024:.1f} KB/s"
                        
                eta_str = f"{eta}s" if eta else "unknown"
                
                self.active_download_job.update({
                    "status": "downloading",
                    "progress": percent,
                    "speed": speed_str,
                    "eta": eta_str,
                    "message": status_text
                })
            elif d['status'] == 'finished':
                if is_playlist:
                    percent = ((current_video_idx + 1) / total_videos * 100.0)
                    status_text = f"Finished downloading video {current_video_idx + 1} of {total_videos}..."
                else:
                    percent = 100.0
                    status_text = "Finalizing file (converting or merging)..."
                    
                self.active_download_job.update({
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
            'download_archive': os.path.join(self.downloads_dir, 'streamvault_archive.txt'), # Prevent duplicate downloads
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

        # Enable external downloader aria2c if it's available on system path!
        if shutil.which("aria2c") is not None:
            ydl_opts.update({
                'external_downloader': 'aria2c',
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
                    'format': fmt_id,
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
                # Embedding thumbnails in MP4 containers requires AtomicParsley
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

        try:
            if is_playlist:
                for idx, entry_url in enumerate(playlist_entries):
                    current_video_idx = idx
                    # Set status update before parsing/downloading this entry
                    self.active_download_job.update({
                        "message": f"Downloading video {idx + 1} of {total_videos}..."
                    })
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([entry_url])
            else:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            
            self.active_download_job["done"] = True
            self.active_download_job["status"] = "completed"
        except Exception as e:
            self.active_download_job["done"] = True
            self.active_download_job["status"] = "failed"
            self.active_download_job["error"] = str(e)

    # Progress Polling (Thread-Safe UI update)
    def poll_progress(self):
        if not self.poll_active:
            return

        if self.active_download_job:
            job = self.active_download_job
            is_playlist = self.video_info.get("is_playlist", False) if self.video_info else False
            
            if job["status"] == "downloading":
                self.status_label.configure(text=job.get("message", "Downloading audio/video streams..."))
                self.progressbar.set(job["progress"] / 100.0)
                self.percent_label.configure(text=f"{job['progress']:.1f}%")
                self.speed_label.configure(text=f"Speed: {job['speed']}")
                self.eta_label.configure(text=f"ETA: {job['eta']}")
                
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
                
                # Reset job
                self.active_download_job = None
                
                # Success alert popup
                self.show_success_popup()

            elif job["status"] == "failed":
                self.status_label.configure(text="Download failed.")
                self.progressbar.set(0)
                
                # Hide progress bar and restore info frame
                self.progress_frame.pack_forget()
                self.info_frame.pack(fill="x", padx=40, pady=10)
                
                # Re-enable inputs
                self.analyze_btn.configure(state="normal")
                self.mp4_download_btn.configure(state="normal")
                self.mp3_download_btn.configure(state="normal")
                
                err_msg = job["error"]
                self.active_download_job = None
                self.show_error(f"Download Error: {err_msg}")

        # Recurse after 100ms
        self.after(100, self.poll_progress)

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
        self.poll_active = False
        self.destroy()

if __name__ == "__main__":
    app = DownloaderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

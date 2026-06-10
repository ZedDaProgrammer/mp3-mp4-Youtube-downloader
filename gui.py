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
        self.progress_frame.pack_forget()
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

        # Directory footer
        self.footer_label = ctk.CTkLabel(
            self, 
            text=f"Files will save directly to: {self.downloads_dir}", 
            text_color="#64748b",
            font=ctk.CTkFont(size=11)
        )
        self.footer_label.pack(side="bottom", pady=15)

    # Threaded URL Analysis
    def start_analyze(self):
        url = self.url_entry.get().strip()
        if not url:
            return

        self.analyze_btn.configure(state="disabled", text="Analyzing...")
        self.info_frame.pack_forget()
        self.progress_frame.pack_forget()

        threading.Thread(target=self.bg_analyze, args=(url,), daemon=True).start()

    def bg_analyze(self, url):
        # Enforce 'noplaylist': True to only check the specific video and prevent downloading playlists
        ydl_opts = {
            'extract_flat': False,
            'skip_download': True,
            'noplaylist': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Check if it returned a playlist structure instead of a single video
                if info.get('_type') == 'playlist':
                    # Extract the first video if it parsed a playlist or default to error
                    entries = info.get('entries', [])
                    if entries:
                        info = entries[0]
                    else:
                        raise ValueError("No video entries found in this link.")

                # Format durations
                duration = info.get("duration", 0)
                if duration:
                    mins, secs = divmod(duration, 60)
                    hours, mins = divmod(mins, 60)
                    duration_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"
                else:
                    duration_str = "Unknown"

                # Extract resolutions
                formats = info.get("formats", [])
                heights = set()
                for f in formats:
                    h = f.get("height")
                    # If ffmpeg is missing, only include combined formats (both audio and video codecs are not none)
                    if not self.ffmpeg_available:
                        if h and f.get("vcodec") != "none" and f.get("acodec") != "none" and h >= 144:
                            heights.add(h)
                    else:
                        if h and f.get("vcodec") != "none" and h >= 144:
                            heights.add(h)
                
                sorted_res = sorted(list(heights), reverse=True)
                res_options = [f"{h}p" for h in sorted_res] if sorted_res else ["720p", "360p"]

                self.video_info = {
                    "url": url,
                    "title": info.get("title", "Unknown Title"),
                    "uploader": info.get("uploader", "Unknown Channel"),
                    "duration": duration_str,
                    "resolutions": res_options
                }

                # Update UI inside Tkinter safe block
                self.after(0, self.update_ui_after_analysis)

        except Exception as e:
            self.after(0, lambda: self.show_error(f"Invalid Video or Verification Failed:\n{str(e)}"))

    def update_ui_after_analysis(self):
        self.analyze_btn.configure(state="normal", text="Analyze")
        
        # Populate widgets
        self.title_label.configure(text=self.video_info["title"])
        self.channel_label.configure(text=f"Channel: {self.video_info['uploader']}")
        self.duration_label.configure(text=f"Duration: {self.video_info['duration']}")
        
        # Populate resolutions
        self.mp4_quality_menu.configure(values=self.video_info["resolutions"])
        self.mp4_quality_menu.set(self.video_info["resolutions"][0])

        # Show info frame
        self.info_frame.pack(fill="x", padx=40, pady=10)

    def show_error(self, message):
        self.analyze_btn.configure(state="normal", text="Analyze")
        
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
        
        # Disable analyze and download inputs
        self.analyze_btn.configure(state="disabled")
        self.mp4_download_btn.configure(state="disabled")
        self.mp3_download_btn.configure(state="disabled")

        # Show Progress Section
        self.progress_frame.pack(fill="x", padx=40, pady=15)
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
                quality = raw_quality.split()[0]  # e.g., "320"
            else:
                quality = "best"
        else:
            raw_quality = self.mp4_quality_menu.get()
            quality = raw_quality.replace("p", "")

        threading.Thread(
            target=self.bg_download, 
            args=(url, download_type, quality), 
            daemon=True
        ).start()

    def bg_download(self, url, download_type, quality):
        def hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                percent = (downloaded / total * 100) if total > 0 else 0
                
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
                    "eta": eta_str
                })
            elif d['status'] == 'finished':
                self.active_download_job.update({
                    "status": "processing",
                    "progress": 100.0,
                    "message": "Finalizing file (converting or merging)..."
                })

        # ydl_opts enforces single video parsing with 'noplaylist': True
        ydl_opts = {
            'progress_hooks': [hook],
            'outtmpl': os.path.join(self.downloads_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'concurrent_fragment_downloads': 5,  # Speed optimization: Download 5 fragments in parallel
            'buffersize': 1024 * 1024,           # Speed optimization: Use a 1MB buffer size for disk writes
            'http_chunk_size': 10485760,         # Speed optimization: Ask for 10MB chunks from YouTube
        }

        if download_type == "mp3":
            if self.ffmpeg_available:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': quality,
                    }],
                })
            else:
                # Force fallback format to best single-audio stream (saves as M4A or WebM)
                ydl_opts.update({
                    'format': 'bestaudio/best',
                })
        else:  # mp4
            if self.ffmpeg_available:
                ydl_opts.update({
                    'format': f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={quality}]+bestaudio/best',
                    'merge_output_format': 'mp4',
                })
            else:
                # Force single combined format (video + audio in one file) to bypass FFmpeg requirement
                ydl_opts.update({
                    'format': f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best',
                })

        try:
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
            
            if job["status"] == "downloading":
                self.status_label.configure(text="Downloading audio/video streams...")
                self.progressbar.set(job["progress"] / 100.0)
                self.percent_label.configure(text=f"{job['progress']:.1f}%")
                self.speed_label.configure(text=f"Speed: {job['speed']}")
                self.eta_label.configure(text=f"ETA: {job['eta']}")
                
            elif job["status"] == "processing":
                self.status_label.configure(text="Finalizing formats (Muxing / Encoding)...")
                self.progressbar.set(1.0)
                self.percent_label.configure(text="100%")
                self.speed_label.configure(text="Speed: ---")
                self.eta_label.configure(text="ETA: ---")

            elif job["status"] == "completed":
                self.status_label.configure(text="Download Complete! Saved to Downloads.")
                self.progressbar.set(1.0)
                self.percent_label.configure(text="100%")
                self.speed_label.configure(text="Speed: ---")
                self.eta_label.configure(text="ETA: ---")
                
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

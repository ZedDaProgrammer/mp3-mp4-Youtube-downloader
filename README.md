# Koinloader — YouTube Downloader

**Koinloader** is a custom, high-performance desktop YouTube downloader application written in Python. It features a stunning modern Dark-Slate interface built using CustomTkinter, backed by the scraping capabilities of `yt-dlp` and asynchronous media delivery pipelines.

---

## Key Features

### Peak Performance & Resource Efficiency
*   **Single-Pass Metadata Extraction**: Parses video links in a single request, cutting URL analysis time in half compared to multi-pass structures.
*   **Vectorized Hot Loops**: Utilizes list/dictionary comprehensions and pre-filtering generator expressions to group format configurations and compute size estimates instantly.
*   **Zero Idle CPU Overhead**: Progress hooks are throttled to a maximum frequency of 100ms, completely replacing background thread polling loops with event-driven safe mainloop callbacks.
*   **Automatic Memory Cleanup**: Re-instantiates context handlers on a per-video basis within the download queue, ensuring complete garbage collection of RAM cache after each video in a playlist completes.

### Robust Threading & Queue Controls
*   **Fluid Responsive UI**: Scopes all network and IO bounds through a managed `ThreadPoolExecutor` workspace, keeping the Tkinter interface completely non-blocking.
*   **Queue-Based Worker**: Sequentially consumes downloads from a background queue, preventing parallel bandwidth congestion.
*   **Thread-Safe Pause / Resume & Cancel**: 
    *   **Pause / Resume**: Synchronously blocks download execution loops in the background thread (suspending socket reads) and resumes instantly when unblocked.
    *   **Cancel**: Sets cancellation flags and raises custom `DownloadError` exceptions inside the progress hook to abort processes cleanly.

### Hardened Error Isolation
*   **Playlist Isolation**: Wraps individual downloads in playlists inside independent context handlers. If a single video fails (due to region lock, private status, or deletion), Koinloader logs the error, increments the overall progress bar, and proceeds to the next entry.
*   **Comprehensive Diagnostics**: Compiles errors encountered during playlist runs and outputs a detailed diagnostic popup window at the end.
*   **Reliable Formats Fallback**: Automatically requests `bestaudio[ext=m4a]/best` if FFmpeg is missing, ensuring output audio is playable natively on Windows without conversion errors.

### Advanced Portability & Bypass Options
*   **Netscape Cookies (`cookies.txt`)**: Includes a native picker dialog to load browser cookies, bypassing `403 Forbidden` limits, age restrictions, and anti-bot speed throttling.
*   **Offline Portability Scan (`./bin`)**: Checks the workspace `./bin/` folder first for binary dependencies (`ffmpeg`, `ffprobe`, `aria2c`), skipping system PATH setup.
*   **Aria2c Muxer Support**: Detects and directs parallel segment streaming via `aria2c` directly from the local `./bin` directory or system PATH for 3x–5x faster download speeds.

---

## Installation & Launch

### Prerequisites
*   Python 3.8 or newer installed on your machine.
*   (Optional) [FFmpeg](https://ffmpeg.org/) and [aria2c](https://aria2.github.io/) for high-resolution muxing and download acceleration.

### Quick Start
To launch the application directly, execute the wrapper script corresponding to your shell:
*   **Windows PowerShell**:
    ```powershell
    .\run.ps1
    ```
*   **Windows Command Prompt**:
    ```cmd
    run.bat
    ```
These scripts will automatically create a Python virtual environment (`venv`), install the requirements, and start the GUI.

---

## Offline Portability & Accelerators
To run Koinloader fully portable without modifying your system's environment variables:
1. Create a `bin` folder in the project root directory.
2. Drop `ffmpeg.exe` and `ffprobe.exe` inside it.
3. Drop `aria2c.exe` inside it.

Koinloader will automatically discover these binaries on startup, update the status to `FFmpeg: Detected (Local ./bin)`, and enable parallel-connection downloading.

---

## Standalone Native Compilation
To package Koinloader into a standalone, single executable native binary for Windows (removing virtualenv dependencies and Tkinter startup lag):
1. Open PowerShell in the root directory.
2. Run the build script:
    ```powershell
    .\build.ps1
    ```
This utilizes **Nuitka** to compile the codebase to C++ structures and outputs a optimized portable build inside the `dist/` directory.

---

## Automated Test Suite
A headless pytest suite is included to validate the application's behavior under stressful situations (including race conditions, network drops, and corrupted playlists) without launching any graphical windows.

To execute the tests, run:
```powershell
.\venv\Scripts\python -m pytest test_gui.py
```

---

## Credits
Created by **ZeD**

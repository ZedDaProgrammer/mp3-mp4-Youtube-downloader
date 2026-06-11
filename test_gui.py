import pytest
from unittest.mock import MagicMock, patch
import yt_dlp
from pathlib import Path
from gui import DownloaderApp

# Mock customtkinter before instantiating DownloaderApp in tests
# to prevent opening actual graphic OS windows and bypass Tcl/Font initialization.
@pytest.fixture(autouse=True)
def mock_ctk_display():
    with patch('customtkinter.CTk.__init__', return_value=None), \
         patch('customtkinter.CTk.geometry'), \
         patch('customtkinter.CTk.title'), \
         patch('customtkinter.CTk.configure'), \
         patch('customtkinter.CTk.resizable'), \
         patch('customtkinter.CTk.mainloop'), \
         patch('customtkinter.CTk.after', side_effect=lambda delay, callback, *args: callback(*args)), \
         patch('customtkinter.CTk.destroy'), \
         patch('customtkinter.CTkFont'), \
         patch('customtkinter.CTkLabel'), \
         patch('customtkinter.CTkEntry'), \
         patch('customtkinter.CTkButton'), \
         patch('customtkinter.CTkFrame'), \
         patch('customtkinter.CTkProgressBar'), \
         patch('customtkinter.CTkTabview'), \
         patch('customtkinter.CTkOptionMenu'), \
         patch('customtkinter.CTkToplevel'):
        yield

@pytest.fixture(autouse=True)
def mock_ytdl(mocker):
    """Globally mock yt_dlp.YoutubeDL inside the gui module to prevent real network calls."""
    mock_instance = MagicMock()
    # Configure context manager to return the same mock instance
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.extract_info.return_value = {
        "_type": "video",
        "title": "Mock Video Title",
        "uploader": "Mock Channel",
        "duration": 180,
        "formats": [
            {"format_id": "137", "height": 1080, "width": 1920, "vcodec": "av01", "acodec": "none", "tbr": 2000},
            {"format_id": "140", "height": None, "width": None, "vcodec": "none", "acodec": "mp4a", "abr": 128}
        ]
    }
    mock_instance.download.return_value = 0
    return mocker.patch("gui.yt_dlp.YoutubeDL", return_value=mock_instance)

@pytest.fixture
def app():
    # Instantiate the DownloaderApp with display mocked
    app = DownloaderApp()
    yield app
    # Clean up executor on teardown
    app.on_closing()

def test_button_clicks_race_condition(app):
    """Verifies that rapid clicks on the Analyze button maintain correct disabled/enabled states."""
    app.url_entry.get = MagicMock(return_value="https://youtube.com/watch?v=mock_video")
    
    # Mock executor.submit to prevent actual background execution
    app.executor.submit = MagicMock()
    
    # Simulate first click
    app.start_analyze()
    assert app.analyze_btn.configure.call_args_list[-1][1]["state"] == "disabled"
    
    # Second click during active analysis should execute safely
    app.start_analyze()
    assert app.analyze_btn.configure.call_args_list[-1][1]["state"] == "disabled"

def test_network_drops_and_throttling_config(app, mock_ytdl):
    """Verifies that network configurations for timeouts and retries are passed to yt_dlp options."""
    app.video_info = {
        "url": "https://youtube.com/watch?v=mock_video",
        "is_playlist": False
    }
    
    # Populate the queue
    app.download_queue.put((0, "https://youtube.com/watch?v=mock_video"))
    
    # Run the worker directly in the test thread for synchronous execution
    app.bg_download_worker("mp4", "720")
    
    # Verify the mocked YoutubeDL was called and options were passed correctly
    assert mock_ytdl.called
    called_opts = mock_ytdl.call_args[0][0]
    assert called_opts["socket_timeout"] == 10
    assert called_opts["retries"] == 5
    assert called_opts["fragment_retries"] == 5

def test_corrupted_playlist_isolation(app, mocker, mock_ytdl):
    """Verifies that if one item in a playlist fails, the loop continues and logs partial success."""
    app.video_info = {
        "url": "https://youtube.com/playlist?list=mock_playlist",
        "is_playlist": True,
        "playlist_entries": [
            "https://youtube.com/watch?v=video1",
            "https://youtube.com/watch?v=video2_corrupt",
            "https://youtube.com/watch?v=video3"
        ]
    }
    
    # Mock download method to raise exception only for video2
    def mock_download(url_list):
        if "video2_corrupt" in url_list[0]:
            raise Exception("Video is private or deleted")
        return 0
        
    mock_instance = mock_ytdl.return_value
    mock_instance.download.side_effect = mock_download
    
    # Initialize download job state manually for synchronous testing
    app.active_download_job = {
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
    
    # Intercept progress events to prevent synchronous cleanup/reset to None
    events = []
    app.push_progress_event = events.append
    
    # Populate the queue
    for idx, entry in enumerate(app.video_info["playlist_entries"]):
        app.download_queue.put((idx, entry))
        
    # Run the worker directly in the test thread for synchronous verification
    app.bg_download_worker("mp4", "720")
    
    # Verify the download engine isolated the error and processed other files
    assert app.active_download_job["successful_count"] == 2
    assert len(app.active_download_job["errors"]) == 1
    assert events[-1]["status"] == "partial_success"
    assert "video2_corrupt" in events[-1]["error_summary"]

def test_bg_analyze_valid_url(app, mock_ytdl):
    """Verifies that bg_analyze successfully processes valid URL metadata extraction."""
    app.ffmpeg_available = True
    mock_instance = mock_ytdl.return_value
    mock_instance.extract_info.return_value = {
        "_type": "video",
        "title": "Mock Video Title",
        "uploader": "Mock Channel",
        "duration": 180,
        "formats": [
            {"format_id": "137", "height": 1080, "width": 1920, "vcodec": "av01", "acodec": "none", "tbr": 2000},
            {"format_id": "140", "height": None, "width": None, "vcodec": "none", "acodec": "mp4a", "abr": 128}
        ]
    }
    
    app.bg_analyze("https://www.youtube.com/watch?v=valid_id")
    
    assert app.video_info is not None
    assert app.video_info["title"] == "Mock Video Title"
    assert app.video_info["uploader"] == "Mock Channel"
    assert app.video_info["duration"] == "3:00"
    assert "1080p" in app.video_info["resolutions"][0]

def test_bg_analyze_garbage_string(app, mock_ytdl):
    """Verifies that bg_analyze handles invalid URLs/garbage strings by displaying show_alert."""
    mock_instance = mock_ytdl.return_value
    mock_instance.extract_info.side_effect = Exception("Unsupported URL or extraction failure")
    
    app.show_alert = MagicMock()
    
    app.bg_analyze("garbage_string")
    
    app.show_alert.assert_called_once()
    args, kwargs = app.show_alert.call_args
    assert args[0] == "Error"
    assert "Invalid Video or Verification Failed" in args[1]
    assert kwargs.get("is_error") is True

def test_get_download_path_success():
    """Verifies standard Downloads path retrieval when winreg lookup succeeds."""
    import winreg
    mock_key = MagicMock()
    with patch.object(winreg, 'OpenKey', return_value=mock_key), \
         patch.object(winreg, 'QueryValueEx', return_value=["C:\\MockUser\\Downloads", 1]):
        app = DownloaderApp()
        assert app.get_download_path() == "C:\\MockUser\\Downloads"
        app.on_closing()

def test_get_download_path_fallback():
    """Verifies home directory fallback path when winreg fails/raises an exception."""
    import winreg
    with patch.object(winreg, 'OpenKey', side_effect=OSError("mock registry failure")):
        app = DownloaderApp()
        expected = str(Path.home() / "Downloads")
        assert app.get_download_path() == expected
        app.on_closing()

def test_bg_download_worker_network_error(app, mock_ytdl):
    """Verifies that bg_download_worker handles connection limits / network errors gracefully."""
    app.video_info = {
        "url": "https://youtube.com/watch?v=mock_video",
        "is_playlist": False
    }
    app.active_download_job = {
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
    app.download_queue.put((0, "https://youtube.com/watch?v=mock_video"))
    
    mock_instance = mock_ytdl.return_value
    mock_instance.download.side_effect = Exception("HTTP Error 429: Too Many Requests")
    
    events = []
    app.push_progress_event = events.append
    
    app.bg_download_worker("mp4", "720")
    
    assert len(events) > 0
    assert events[-1]["status"] == "failed"
    assert "Too Many Requests" in events[-1]["error"]

# Tango Studio

A simple audio player which supports playlist management and browsing local audio files.

## Features

- Play audio files (MP3, WAV, FLAC, OGG, M4A).
- Load single files, multiple files, or playlists (M3U / M3U8).
- Browse folders to add multiple songs.
- Two-list interface:
  - Left: Playlist (queue to play).
  - Right: Browser (files in a selected folder).
- Add songs from the browser to the playlist.
- Remove songs from either list with `Delete` key.
- Playback controls: Play, Pause/Resume, Stop, Previous, Next.
- Automatic next track playback.
- Volume control.
- Display current playback time and total track duration.
- Save playlists (Save / Save As).

## Installation

1. Install Python 3.8 or later.
2. Install VLC media player:
   - **Windows**: No action required (VLC is bundled with the application).
   - **macOS**: `brew install vlc`
   - **Linux**: `sudo apt-get install vlc` (Ubuntu/Debian) or equivalent for your distribution
3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Run the Python script:

```bash
python main.py
```

2. Use the File menu to open files, multiple files, playlists, or folders.
3. Select songs in the browser (right list) and click `Add ->` to add them to the playlist.
4. Use the playback controls to play, pause, stop, or navigate tracks.
5. Save your playlist using `Save` or `Save As` from the File menu.
6. Remove songs from either list by selecting them and pressing the `Delete` key.

## Dependencies

- Python 3.8+
- [python-vlc](https://pypi.org/project/python-vlc/) - Python bindings for VLC
- [mutagen](https://pypi.org/project/mutagen/) - Audio metadata reader
- VLC media player (bundled on Windows, must be installed separately on macOS/Linux)

## File Structure

- `main.py`: Entry point for the application.
- `app/`: Core application logic and state management.
- `ui/`: User interface components (windows, views, controls).
- `audio/`: Audio playback handling.
- `plugins/`: Bundled VLC plugins (Windows only).
- `themes/`: Theme definitions and management.
- `README.md`: Documentation for the tool.

## Notes

- Only local files are supported in the playlist.
- The tool supports common audio formats: MP3, WAV, FLAC, OGG, M4A.
- Playback time is updated every 0.5 seconds.

## License

See the [LICENSE](LICENSE) file for details.


# Valkyria

A simple audio player which supports playlist management and browsing
local audio files.

## Features

Valkyria features include:

-   Play audio files (MP3, WAV, FLAC, OGG, M4A).
-   Load single files, multiple files, or playlists (M3U / M3U8).
-   Browse folders to add multiple songs in the playback list.
-   Playback controls: Play, Pause/Resume, Stop, Previous, Next.
-   Automatic next track playback.
-   Metadata display and editing.
-   Metadata album images booklet
-   Save playlists (Save / Save As).

For the full list of the available features please refer to the user guide documentation (link below).

## Supported Formats

-   MP3
-   WAV
-   FLAC
-   OGG
-   M4A / AAC

## Installation

1.  Install Python 3.8 or later.
2.  Install Python dependencies:

``` bash
pip install -r requirements.txt
```

## Usage

1.  Run the Python script:

``` bash
python main.py
```

2.  Use the File menu to open files, multiple files, playlists, or
    folders.
3.  Select songs in the browser (right list) and click `Add ->` to add
    them to the playlist.
4.  Use the playback controls to play, pause, stop, or navigate tracks.
5.  Save your playlist using `Save` or `Save As` from the File menu.
6.  Remove songs from either list by selecting them and pressing the
    `Delete` key.

## Dependencies

-   Python 3.8+
-   sounddevice
-   soundfile
-   numpy
-   scipy
-   mutagen
-   librosa

## File Structure

-   `main.py`: Entry point for the application.
-   `app/`: Core application logic and state management.
-   `ui/`: User interface components (windows, views, controls).
-   `audio/`: Audio playback handling.
-   `themes/`: Theme definitions and management.
-   `README.md`: Documentation for the tool.

## Documentation

Comprehensive documentation is available within the application and in the `docs/` folder:

### User Guide
Complete guide covering all features, controls, and workflows. Access via **Help → Documentation → User Guide** in the application, or view the file directly here: [User Guide](docs/user_guide.md).

### BPM Analysis
Detailed technical documentation about the automatic tempo detection system. Access via **Help → Documentation → BPM Analysis** in the application, or view the file directly here: [BPM Analysis](docs/bpm_analysis.md).


## Troubleshooting

### MP3/MP4 files don't show waveforms or display ffmpeg warnings

**Symptoms:**
- No waveform appears in the seekbar for MP3/MP4 files
- Warning message: `Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work`

**Cause:**
MP3 and MP4 are compressed formats that require the `ffmpeg` codec for decoding. If ffmpeg is not installed or not accessible, these files cannot be processed.

**Solution:**
Install ffmpeg for your operating system:

**Windows:**
```bash
choco install ffmpeg
```
Or download directly from [ffmpeg.org](https://ffmpeg.org/download.html)

**Linux:**
```bash
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Important:** After installing ffmpeg, **restart the application** for PATH changes to take effect.

**Verify installation:**
```bash
ffmpeg -version
```

If the command returns version information, ffmpeg is correctly installed and accessible.

## License

See the LICENSE file for details.

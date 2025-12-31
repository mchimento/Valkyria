# Tango Studio

A simple audio player which supports playlist management and browsing
local audio files.

## Features

-   Play audio files (MP3, WAV, FLAC, OGG, M4A).
-   Load single files, multiple files, or playlists (M3U / M3U8).
-   Browse folders to add multiple songs in the playback list.
-   Playback controls: Play, Pause/Resume, Stop, Previous, Next.
-   Automatic next track playback.
-   Metadata display and editing.
-   Metadata album images booklet
-   Save playlists (Save / Save As).

## 🎧 Automatic BPM (Tempo) Analysis

Tango Studio can automatically analyze and store the **BPM (Beats Per
Minute)** of your music files. This enables DJ-style features such as
tempo sorting, smart playlists, and smooth beat-matched transitions.

### What is BPM?

BPM represents the musical tempo of a track --- how fast the beat moves
--- and is different from audio quality metrics such as *kbps*. BPM is a
musical property and must be computed from the audio signal itself.

### How BPM is Calculated

Tango Studio uses the **librosa** audio analysis library to estimate BPM
directly from the sound waveform.

1. **Audio Decoding**
   - The audio file is decoded into a mono waveform at a fixed sample rate.
   - For MP3 files, a short segment is first decoded using FFmpeg to ensure reliable analysis.

2. **Onset Strength Detection**
   - librosa computes an onset strength envelope.
   - This highlights moments where musical energy suddenly increases (such as drum hits, kicks, and claps).
   - These peaks represent the rhythmic pulse of the track.

3. **Tempogram Analysis**
   - A tempogram is generated from the onset envelope.
   - The tempogram measures repeating rhythmic patterns over time and reveals the dominant beat periodicities in the song.

4. **Global Tempo Estimation**
   - The strongest rhythmic periodicity is selected from the tempogram.
   - This produces a **raw physical tempo value** expressed in BPM.

5. **Optional Tempo Normalization**
   - Tango Studio can optionally normalize the raw tempo into a musically perceived BPM range.
   - This resolves common half-tempo and double-tempo ambiguities and allows BPM values to match professional DJ software.
   - Normalization is controlled by user preference and can be disabled to expose the raw tempo.

6. **Metadata Storage**
   - The resulting BPM value can be written back into the audio file’s metadata.
   - BPM is always stored in its raw form, i.e. not normalized.
   - Once analyzed, BPM is cached inside the file and does not need to be recomputed again.

### Supported Formats

-   MP3
-   WAV
-   FLAC
-   OGG
-   M4A / AAC

## Installation

1.  Install Python 3.8 or later.
2.  Install VLC media player:
    -   **Windows**: No action required (VLC is bundled with the
        application).
    -   **macOS**: `brew install vlc`
    -   **Linux**: `sudo apt-get install vlc` (Ubuntu/Debian) or
        equivalent for your distribution
3.  Install Python dependencies:

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
-   python-vlc
-   mutagen
-   librosa
-   VLC media player (bundle included on Windows distribution)

## File Structure

-   `main.py`: Entry point for the application.
-   `app/`: Core application logic and state management.
-   `ui/`: User interface components (windows, views, controls).
-   `audio/`: Audio playback handling.
-   `plugins/`: Bundled VLC plugins (Windows only).
-   `themes/`: Theme definitions and management.
-   `README.md`: Documentation for the tool.

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

## Notes

-   Only local files are supported in the playlist.

## License

See the LICENSE file for details.

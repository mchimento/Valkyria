# Tango Studio User Guide

Welcome to **Tango Studio**, a modern audio player with advanced features for music enthusiasts and DJs.

## Table of Contents

* [Getting Started](#getting-started)
  * [Opening Audio Files](#opening-audio-files)
  * [Supported Formats](#supported-formats)
* [Playback Controls](#playback-controls)
  * [Basic Controls](#basic-controls)
  * [Volume Control](#volume-control)
  * [Repeat Modes](#repeat-modes)
* [Playlist Management](#playlist-management)
  * [Adding Songs](#adding-songs)
  * [Organizing Your Playlist](#organizing-your-playlist)
  * [Saving Playlists](#saving-playlists)
* [Audio Effects](#audio-effects)
  * [Equalizer](#equalizer)
  * [Vocal Remover](#vocal-remover)
  * [Compressor](#compressor)
  * [Spatializer](#spatializer)
* [Playback Features](#playback-features)
  * [Crossfade](#crossfade)
  * [Play on Double-Click](#play-on-double-click)
* [Track Information](#track-information)
* [BPM Analysis](#bpm-analysis)
* [Themes](#themes)
* [Keyboard Shortcuts](#keyboard-shortcuts)
* [Audio Devices](#audio-devices)
* [Browser View](#browser-view)
* [Tips & Tricks](#tips--tricks)
* [Troubleshooting](#troubleshooting)

---

## Getting Started

### Opening Audio Files

Tango Studio provides multiple convenient methods to build your music library and playlists. Each method is optimized for different workflows:

* **Open File** (Ctrl+O) - Opens a file dialog to select a single audio file. Best for adding individual tracks or when you want precise control over what gets added.
* **Open Multiple Files** (Ctrl+M) - Opens a file dialog allowing multiple selection. Hold Ctrl or Shift to select multiple files at once. Ideal for adding several specific tracks from a folder without adding the entire folder.
* **Open Folder** (Ctrl+F) - Recursively scans a folder and all its subfolders for audio files, automatically adding them to the playlist. Perfect for importing entire album folders or music collections organized in subdirectories.
* **Open Playlist** (Ctrl+L) - Load an existing M3U or M3U8 playlist file. Supports both relative and absolute file paths, making it ideal for portable playlists or shared music collections.

When you open files or folders, Tango Studio automatically filters for supported audio formats and skips unsupported file types. The status bar will display the number of files successfully added.

### Supported Formats

Tango Studio supports a wide range of audio formats to accommodate various quality preferences and use cases:

| Format | Type | Best Use Case |
|--------|------|---------------|
| **MP3** | Lossy compression | Universal compatibility, reasonable file size, good for large collections |
| **WAV** | Uncompressed | Studio-quality, editing, archival. Large file sizes |
| **FLAC** | Lossless compression | Audiophile listening, archival with reduced file size compared to WAV |
| **OGG** | Lossy compression | Open-source alternative to MP3, good quality-to-size ratio |
| **M4A** | Lossy/Lossless | iTunes/Apple ecosystem, AAC encoding, good mobile compatibility |

All formats support embedded metadata (title, artist, album, artwork, BPM) which Tango Studio reads and displays throughout the interface.

## Playback Controls

### Basic Controls

Tango Studio provides intuitive playback controls accessible via buttons, keyboard shortcuts, and the waveform seekbar:

* **Play/Pause** (Spacebar) - Toggles between playing and paused states. If stopped, Play will start from the beginning of the current track. If paused, Play resumes from the paused position.
* **Stop** (S) - Completely stops playback and resets the position to the beginning. Useful when you want to restart a track from scratch or clear the current playback state.
* **Previous** (Left Arrow) - Jumps to the previous track in the playlist. If pressed within the first 3 seconds of a track, it goes to the previous track; otherwise, it restarts the current track.
* **Next** (Right Arrow) - Advances to the next track in the playlist. Respects repeat mode settings.
* **Seek** - Click anywhere on the waveform seekbar to instantly jump to that position in the track. The waveform provides visual feedback showing the audio amplitude, making it easy to navigate to specific sections (intro, chorus, bridge, etc.).

The waveform seekbar displays a real-time representation of the audio file's amplitude envelope, helping you visualize the song structure and identify quiet or loud sections at a glance.

### Volume Control

Fine-grained volume control ensures comfortable listening levels across different tracks:

* **Volume Slider** - Drag the slider or click on the track to set a specific volume level (0-100%)
* **Mouse Wheel** - Hover over the volume slider and use the mouse wheel for quick incremental adjustments
* **Mute** (M) - Instantly toggles between current volume and complete silence. Useful for quick interruptions without losing your volume setting
* **Volume Step Shortcuts** - Use dedicated keyboard shortcuts for precise +/- volume adjustments

Volume changes apply in real-time without interrupting playback. The volume setting persists across sessions.

### Repeat Modes

Choose from three repeat modes accessible from **Playback → Repeat Mode** menu:

1. **No Repeat** - Plays through the playlist once and stops at the end. Best for listening to albums or curated playlists in order.
2. **Repeat One** - Loops the currently playing track indefinitely. Perfect for focusing on a specific song, practicing lyrics, or analyzing musical elements.
3. **Repeat All** - After the last track finishes, playback automatically returns to the first track and continues indefinitely. Ideal for background music or unattended playback.

The current repeat mode persists across application restarts.

## Playlist Management

### Adding Songs

Tango Studio offers flexible methods to build and modify your playlist during playback:

* **Add** - Appends selected songs from the browser view to the end of the current playlist. The playlist order remains unchanged.
* **Add Below** - Inserts selected songs immediately after the currently playing track. This is perfect for queuing up songs you want to hear next without disrupting the remaining playlist.
* **Double-click in Browser** - Double-clicking a song in the browser view adds it to the playlist. The specific behavior (play immediately or just add) can be configured in Playback Features.
* **Duplicate Detection** - Tango Studio automatically prevents adding duplicate entries. If you try to add a song already in the playlist, it will be silently skipped.

### Organizing Your Playlist

Keep your playlist organized with powerful management tools:

* **Shuffle** (Ctrl+H) - Randomizes the entire playlist order while preserving the currently playing track's position. Great for discovering forgotten gems in large collections.
* **Sort by Title** (Ctrl+T) - Alphabetically sorts all tracks by their title metadata. Useful for finding specific songs in large playlists.
* **Sort by Artist** (Ctrl+R) - Groups tracks by artist name alphabetically. Perfect for album-oriented listening or when you want to hear all tracks from a specific artist together.
* **Move Up/Down** (Ctrl+Up/Down) - Manually reorder selected tracks by moving them up or down in the playlist. Supports multi-selection for moving multiple tracks at once.
* **Remove Selected** (Delete) - Removes one or more selected tracks from the playlist without deleting the actual files from disk.
* **Clear** (Ctrl+C) - Removes all tracks from the playlist after confirmation. Use this to start fresh without closing the application.

All organization operations update the playlist view immediately and preserve your current playback position whenever possible.

### Saving Playlists

Playlists can be saved and loaded for later use:

* **Save Playlist** (Ctrl+S) - Saves changes to the currently loaded playlist file. If no file is currently loaded, behaves like "Save Playlist As".
* **Save Playlist As** (Ctrl+Shift+S) - Opens a save dialog to create a new playlist file or overwrite an existing one.
* **M3U8 Format** - Playlists are saved in the widely-compatible M3U8 format (UTF-8 encoded M3U), which can be opened in most media players and DJ software.

Playlist files store file paths (absolute by default) and can be edited in any text editor. Relative paths are supported for portable playlists that can be moved between different computers.

## Audio Effects

Access the audio effects panel from **Tools → Audio Effects and Filters**. All effects process audio in real-time and can be enabled/disabled independently. Effects are applied in the following order: Equalizer → Compressor → Vocal Remover → Spatializer.

### Equalizer

The 10-band graphic equalizer allows precise frequency-specific adjustments for tonal balance and acoustic compensation.

#### Frequency Bands

| Band | Frequency | Typical Instruments/Sounds |
|------|-----------|----------------------------|
| 1 | 32 Hz | Sub-bass, kick drum fundamental, room rumble |
| 2 | 64 Hz | Bass guitar fundamental, deep bass notes |
| 3 | 125 Hz | Bass guitar presence, male vocal warmth |
| 4 | 250 Hz | Vocal body, snare drum body, guitar thickness |
| 5 | 500 Hz | Vocal clarity, snare attack, guitar presence |
| 6 | 1 kHz | Vocal intelligibility, guitar definition |
| 7 | 2 kHz | Vocal presence, snare snap, cymbal attack |
| 8 | 4 kHz | Vocal brilliance, hi-hat detail, clarity |
| 9 | 8 kHz | Cymbal shimmer, vocal air, string detail |
| 10 | 16 kHz | Extreme highs, ambiance, "air" |

#### Controls

* **Gain Sliders** - Adjust each band from -12 dB (cut) to +12 dB (boost)
* **Enable/Disable** - Toggle the entire equalizer on/off to A/B compare the effect
* **Reset Button** - Returns all bands to 0 dB (flat response)

#### Usage Tips

* **Room Compensation** - If your room has bass buildup, cut the 32-125 Hz range by 2-4 dB
* **Vocal Presence** - Boost 2-4 kHz by 2-3 dB to make vocals stand out in the mix
* **Harsh Reduction** - If cymbals or high frequencies sound harsh, cut 4-8 kHz by 2-3 dB
* **Warmth** - Boost 125-250 Hz by 2-3 dB for added warmth and body
* **Avoid Extremes** - Boosts beyond 6 dB can cause distortion; start with small adjustments (2-3 dB)

The equalizer uses high-quality bi-quad IIR filters with linear phase response to minimize artifacts and phase shifts.

### Vocal Remover

Removes or attenuates center-panned vocals from stereo tracks, useful for karaoke or isolating instrumental parts.

#### How It Works

The vocal remover uses phase inversion (also called "mid-side cancellation"). Most professional recordings pan lead vocals to the center (equal in both left and right channels), while instruments are panned around the stereo field. By subtracting the common signal between channels, centered elements are reduced or eliminated.

#### Controls

* **Enable/Disable** - Toggle the effect on/off
* **Strength** - Adjust removal intensity from 0% (no effect) to 100% (maximum removal)

#### Limitations and Tips

* **Effectiveness Varies** - Works best on professionally mixed tracks with centered vocals. May not work well on:
  * Live recordings or bootlegs with non-standard mixing
  * Tracks with heavily reverbed vocals that bleed into the sides
  * Mono recordings (no stereo information to process)
* **Stereo Width Loss** - Some stereo width may be lost as the effect removes center information
* **Bass Reduction** - Bass frequencies are often centered and may be attenuated along with vocals
* **Optimal Setting** - Start at 50% strength and adjust based on the track. Some songs need 80-100% for good vocal removal.

### Compressor

Dynamic range compression automatically reduces the difference between loud and soft parts, resulting in more consistent perceived volume.

#### Parameters

| Parameter | Range | Description | Typical Settings |
|-----------|-------|-------------|------------------|
| **Threshold** | -40 dB to 0 dB | Level above which compression begins. Lower values = more compression | -20 to -12 dB for moderate compression |
| **Ratio** | 1:1 to 20:1 | Compression amount. Higher ratios = more aggressive. 1:1 = no compression | 2:1 to 4:1 for music, 10:1+ for limiting |
| **Attack** | 1 ms to 100 ms | How quickly compression engages after threshold is exceeded | 5-20 ms for most music, 1-5 ms for drums |
| **Release** | 10 ms to 1000 ms | How quickly compression disengages after signal drops below threshold | 50-200 ms for music, faster for speech |

#### How Compression Works

When the audio signal exceeds the threshold, the compressor reduces the gain according to the ratio setting. For example, with a 4:1 ratio:
* If the signal exceeds the threshold by 4 dB, it's reduced to exceed by only 1 dB
* The result is a "compressed" dynamic range, where loud parts are quieter relative to soft parts

#### Usage Tips

* **Subtle Enhancement** - Start with threshold at -18 dB, ratio at 3:1, attack at 10 ms, release at 100 ms
* **Consistent Volume** - For playlists with varying track volumes, use moderate compression (3:1-4:1 ratio)
* **Avoid Over-Compression** - Ratios above 8:1 can make music sound lifeless and fatiguing
* **Fast Attack for Drums** - Shorter attack times (1-5 ms) help control drum transients
* **Slow Attack for Punch** - Longer attack times (20-50 ms) preserve drum impact and attack

The compressor includes automatic makeup gain to compensate for the overall volume reduction caused by compression.

### Spatializer

Enhances or reduces the stereo width of the audio, creating a wider or more focused soundstage.

#### Controls

* **Enable/Disable** - Toggle the effect on/off
* **Width** - Adjust stereo width from 0% (mono) to 200% (ultra-wide stereo)

#### Width Settings

| Setting | Result | Use Case |
|---------|--------|----------|
| 0% | Mono | Check for phase issues, focus audio, simulate single speaker |
| 50% | Narrowed stereo | Subtle focusing, headphone fatigue reduction |
| 100% | Original stereo | Bypass/disable the effect |
| 120-150% | Widened stereo | Enhanced spaciousness, immersive listening on speakers |
| 160-200% | Ultra-wide | Maximum spaciousness, can sound unnatural on headphones |

#### Technical Details

The spatializer uses mid-side processing to independently control center (mid) and side signals:
* **Mid Signal** - Mono sum of left and right channels (centered content)
* **Side Signal** - Difference between left and right channels (stereo content)

Increasing width boosts the side signal relative to mid signal, creating a wider stereo image. Decreasing width does the opposite.

#### Usage Tips

* **Headphone Enhancement** - 120-140% width can create a more speaker-like experience on headphones
* **Correct Phase Issues** - Reducing width to 80-90% can help tracks with phase problems sound clearer
* **Check in Mono** - Set width to 0% to check how a track sounds in mono (useful for DJ mixing)
* **Avoid Extremes** - Settings above 150% can cause phase issues and unnatural sound, especially on headphones

## Playback Features

Access advanced playback options from **Tools → Playback Features**.

### Crossfade

Smooth transitions between tracks by fading out the ending track while simultaneously fading in the next track. This creates a seamless, DJ-style listening experience without gaps.

#### Settings

* **Enable/Disable** - Toggle crossfading on/off
* **Duration** - Set crossfade length from 0 to 10 seconds

#### How It Works

When crossfade is enabled:
1. The current track begins fading out when it reaches the point where [Duration] seconds remain
2. The next track begins fading in simultaneously
3. Both tracks play together during the crossfade period, creating a smooth blend

#### Usage Tips

* **Typical Settings** - 3-5 seconds works well for most music
* **Longer Crossfades** - 8-10 seconds for ambient or electronic music with long outros/intros
* **Shorter Crossfades** - 1-2 seconds for quick transitions or when tracks have abrupt endings
* **Disable for Podcasts** - Crossfading is generally not suitable for spoken content or live albums

Crossfade respects repeat mode settings. In "Repeat One" mode, the track will crossfade into itself.

### Play on Double-Click

Controls the behavior when double-clicking a song in the playlist.

#### Options

* **Enabled** - Double-clicking a playlist item immediately starts playing that track
* **Disabled** - Double-clicking only selects the track without changing playback

#### Use Cases

* **Enable** - For quick access and immediate playback (traditional media player behavior)
* **Disable** - When you frequently select tracks for metadata viewing or batch operations and don't want accidental playback changes

## Track Information

Access detailed track metadata from **Playback → Operations → Track Information** (Ctrl+I), or right-click a track in the playlist and select "Track Information".

The Track Information window displays comprehensive metadata and technical details:

#### Metadata Fields

* **Title** - Song title from file metadata
* **Artist** - Performing artist or band name
* **Album** - Album or release name
* **Album Artist** - Album-level artist (may differ from track artist on compilations)
* **Year** - Release year
* **Genre** - Musical genre classification
* **Track Number** - Position in the album
* **Comment** - User-defined text notes

#### Technical Information

* **Duration** - Total track length in minutes:seconds
* **Bitrate** - Audio encoding bitrate in kbps (higher generally means better quality)
* **Sample Rate** - Audio sampling frequency in Hz (44.1 kHz is CD quality)
* **Channels** - Stereo (2) or Mono (1)
* **Format** - File container format (MP3, FLAC, WAV, etc.)
* **File Size** - Total file size on disk
* **File Path** - Complete path to the file's location

#### BPM Information

* **BPM** - Beats per minute (tempo). May be blank if not analyzed or stored in metadata
* **Analyze Button** - Click to trigger automatic BPM detection

#### Album Artwork

If embedded in the file metadata, the album artwork is displayed at full resolution. You can also access artwork via **Playback → Operations → Show Album Booklet** (Ctrl+B).

## BPM Analysis

Tango Studio includes sophisticated automatic BPM (Beats Per Minute) detection. For detailed technical information about how BPM analysis works, see the dedicated **BPM Analysis** documentation in the Help menu.

### Quick Start Guide

1. **Play or select a track** - The track must be in the playlist
2. **Click "Analyze BPM"** - Button appears in the status bar when a track is loaded
3. **Wait for analysis** - Progress indicated by "Analyzing..." status. Typically takes 5-30 seconds depending on file length and CPU speed
4. **Review the result** - BPM value is displayed in the status bar and track info
5. **Save to file** - Click "Save BPM" to write the value permanently to the file's metadata

### BPM Display

BPM values are shown in multiple locations:
* **Status Bar** - Displays BPM of currently playing track
* **Playlist** - Optional BPM column (can be enabled in preferences)
* **Track Information** - Detailed metadata window

### BPM Normalization

BPM analysis sometimes produces "half-time" (too slow) or "double-time" (too fast) results. Tango Studio includes optional automatic normalization to bring BPM values into the musically perceived range (80-180 BPM for most music).

**Normalization can be enabled/disabled in Preferences:**
* **Enabled** - BPM values are automatically adjusted to match human-perceived tempo (matches professional DJ software)
* **Disabled** - Raw, unprocessed BPM values from the analysis algorithm

**Note**: Stored BPM values are always in their raw form. Normalization only affects display.

### Usage Tips

* **Batch Analysis** - Analyze your entire library during idle time, then use BPM values for sorting or DJ mixing
* **CPU Intensive** - BPM analysis is computationally demanding. Don't analyze many tracks while recording or in other CPU-intensive tasks
* **File Format Note** - BPM can be saved to MP3, FLAC, M4A, and OGG files. WAV files do not natively support metadata tags

## Themes

Tango Studio includes carefully crafted dark and light themes for comfortable viewing in any environment.

### Switching Themes

1. Open **Tools → Preferences** (Ctrl+P)
2. Select your preferred theme from the dropdown
3. Click **Apply** to immediately switch themes

### Theme Characteristics

| Feature | Dark Theme | Light Theme |
|---------|-----------|-------------|
| **Background** | Deep charcoal (#1E1E1E) | Soft white (#FAFAFA) |
| **Text** | Light gray (#FFFFFF) | Dark gray (#000000) |
| **Accents** | Blue (#0078D4) | Blue (#0078D4) |
| **Best For** | Low-light environments, extended listening sessions, reduced eye strain | Well-lit rooms, daytime use, maximum contrast |

Both themes are fully integrated across the entire application:
* Main window and playlist
* All dialog windows and popups
* Browser view
* Audio effects panel
* Documentation windows
* Status bars and controls

Your theme preference is saved and automatically restored when you restart the application.

## Keyboard Shortcuts

Master these shortcuts for efficient navigation and control:

Master these shortcuts for efficient navigation and control:

### File Operations
* **Ctrl+O** - Open File
* **Ctrl+M** - Open Multiple Files
* **Ctrl+F** - Open Folder
* **Ctrl+L** - Open Playlist
* **Ctrl+S** - Save Playlist
* **Ctrl+Shift+S** - Save Playlist As

### Playback
* **Spacebar** - Play/Pause
* **S** - Stop
* **Left Arrow** - Previous Track
* **Right Arrow** - Next Track
* **M** - Mute

### Playlist
* **Ctrl+H** - Shuffle
* **Ctrl+T** - Sort by Title
* **Ctrl+R** - Sort by Artist
* **Ctrl+Up** - Move Selected Up
* **Ctrl+Down** - Move Selected Down
* **Delete** - Remove Selected
* **Ctrl+C** - Clear Playlist
* **Ctrl+I** - Track Information
* **Ctrl+B** - Show Album Booklet

### View
* **F9** - Toggle Playlist Visibility
* **F10** - Toggle Browser Visibility

### Other
* **Ctrl+P** - Preferences
* **F1** - About
* **Alt+F4** - Quit

## Audio Devices

Tango Studio automatically detects all available audio output devices on your system. Select your preferred device from **Tools → Audio Device**.

### Device Selection

* The current system default device is marked with "(system default)"
* Click any device to immediately switch audio output
* Changes apply in real-time without interrupting playback
* Selected device persists across application restarts

### Common Use Cases

* **Multiple Audio Interfaces** - Switch between built-in speakers, USB DACs, or professional audio interfaces
* **Headphones vs. Speakers** - Quickly toggle between different output devices
* **ASIO Devices** - Professional audio interfaces with ASIO drivers are supported on Windows

### Troubleshooting

If a device doesn't appear in the list:
* Ensure the device is properly connected and recognized by your OS
* Restart Tango Studio after connecting new audio hardware
* Check device drivers are up to date

## Browser View

The browser view provides a convenient file explorer integrated directly into Tango Studio for browsing and adding music to your playlist.

### Navigation

* **Browse Folder** - Open a directory browser to navigate your music library
* **Browse Files** - Open a file picker to select specific audio files
* **Current Directory** - Displays the currently browsed folder path
* **Parent Directory** - Navigate up one folder level

### Adding to Playlist

Once you've browsed to a folder containing audio files:

* **Select Files** - Click to select individual files, Ctrl+Click for multiple selection, Shift+Click for range selection
* **Add Button** - Adds selected files to the end of the playlist
* **Add Below Button** - Inserts selected files after the currently playing track
* **Double-Click** - Behavior depends on "Play on Double-Click" setting

### Browser Tips

* **Drag and Drop** - Drag files from the browser directly onto the playlist (feature availability may vary)
* **Filter by Type** - Browser automatically shows only supported audio formats
* **Quick Access** - Keep browser view visible (F10) for instant access to your music library
* **Folder Bookmarks** - Use Browse Folder to quickly jump to frequently-accessed directories

## Tips & Tricks

### Performance

* **Large Playlists** - For playlists with 1000+ tracks, sorting and shuffling operations may take a moment to complete. The application remains responsive during these operations.
* **BPM Analysis** - BPM analysis is CPU-intensive. For best results, analyze tracks during idle time rather than while recording, gaming, or performing other CPU-intensive tasks.
* **Memory Usage** - Tango Studio loads metadata on demand and caches it efficiently. Even very large libraries (10,000+ files) are handled smoothly.

### File Management

* **Organized Libraries** - Maintain a consistent folder structure (e.g., Artist → Album → Tracks) for easier browsing
* **Metadata Quality** - Ensure files have accurate ID3 tags for better organization and display
* **Backup Playlists** - Regularly save important playlists. Consider using relative paths for portable playlists
* **M3U8 Compatibility** - Tango Studio's playlists work in VLC, foobar2000, and most other players

### Audio Quality

* **Lossless for Archival** - Use FLAC or WAV for your music archive; convert to lossy formats only for portable devices
* **320 kbps MP3** - Generally indistinguishable from lossless for most listeners
* **Sample Rate** - 44.1 kHz is sufficient for music; higher rates mainly benefit production work
* **Equalizer Best Practices** - Start with small adjustments (2-3 dB) and use your ears. Avoid excessive boosting which can cause distortion and fatigue

### Workflow Optimization

* **Keyboard-Driven** - Learn the essential keyboard shortcuts (Spacebar, S, arrows, Ctrl+H) for hands-free control
* **Browser Layout** - Adjust the window to show both playlist and browser simultaneously for efficient library navigation
* **Queue Management** - Use "Add Below" to build a queue of upcoming tracks without restructuring your entire playlist
* **Theme for Time of Day** - Switch to dark theme for evening listening sessions to reduce eye strain
* **Crossfade for Parties** - Enable 5-7 second crossfade for seamless background music

## Troubleshooting

### Audio Issues

**Problem**: No sound output

**Solutions**:

* Verify system volume is not muted (check both Tango Studio and OS volume mixer)
* Confirm correct audio device is selected in Tools → Audio Device
* Test with a different audio file to rule out file corruption
* Ensure audio drivers are up to date
* Try restarting Tango Studio

**Problem**: Crackling, popping, or distortion

**Solutions**:

* Reduce equalizer boost levels (try setting all bands to 0 dB)
* Disable compressor or reduce ratio/threshold
* Check CPU usage - high CPU load can cause audio dropouts
* Try increasing audio buffer size (may require OS-level settings)
* Switch to a different audio device
* Update audio drivers

### Playlist Issues

**Problem**: Playlist won't load from M3U/M3U8 file

**Solutions**:
* Open the .m3u8 file in a text editor to check for formatting errors
* Verify file paths in the playlist are correct (files haven't been moved or deleted)
* Try absolute paths instead of relative paths or vice versa
* Check file encoding (should be UTF-8 for M3U8)
* Recreate the playlist from scratch if corrupted

**Problem**: Tracks in wrong order after sorting

**Solutions**:

* Ensure metadata (title/artist tags) is correct - sorting uses metadata, not filenames
* Try sorting by a different field
* Manually reorder with Move Up/Down if metadata can't be fixed

### BPM Analysis Issues

**Problem**: BPM analysis fails or returns no result

**Solutions**:

* Ensure the audio file is not corrupted - try playing it fully
* Verify sufficient CPU resources are available
* Try analyzing a simpler track first (electronic music with clear beats)
* Check file format is supported (MP3, FLAC, WAV, OGG, M4A)
* For very long tracks (>10 minutes), analysis may take several minutes

**Problem**: BPM result is clearly wrong (half or double the correct value)

**Solutions**:

* This is a common issue with tempo detection algorithms
* Enable BPM normalization in Preferences to automatically correct common errors
* Manually correct the BPM value if needed (feature may be added in future updates)
* Some genres (jazz, classical, ambient) may not have consistent tempo

**Problem**: Cannot save BPM to file

**Solutions**:

* Ensure file is not read-only (check file permissions)
* WAV files don't support metadata tags - convert to FLAC for metadata support
* Some file systems (FAT32, network drives) may have permission issues
* Try copying the file to a local drive with write permissions

### General Issues

**Problem**: Application won't start or crashes on startup

**Solutions**:

* Delete the config file (see app data folder) to reset to defaults
* Ensure all dependencies are installed (check requirements.txt)
* Check for Windows updates and install pending updates
* Try running as administrator (right-click → Run as administrator)
* Check application logs for error details

**Problem**: High memory usage

**Solutions**:

* This is usually normal for large playlists
* Clear playlist and reload only needed tracks
* Restart application to free accumulated memory
* Check for memory leaks (report if memory grows indefinitely)

**Problem**: Settings not saving between sessions

**Solutions**:

* Ensure Tango Studio has write permissions to its configuration directory
* Check available disk space
* Try running as administrator
* Configuration file may be corrupted - delete it to reset

---

**Version**: 1.0.0
**Last Updated**: January 2026

Thank you for using Tango Studio!

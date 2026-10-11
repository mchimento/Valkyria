<p align="center">
  <img src="../assets/logo-no-background.png" alt="Valkyria" width="240"/>
</p>

# User Guide

Welcome to **Valkyria**, a modern audio player with playback features for music enthusiasts and DJs.

## Table of Content

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
* [Browser View](#browser-view)
  * [Navigation](#navigation)
  * [Adding to Playlist](#adding-to-playlist)
  * [Song Preview](#song-preview)
* [Live Audio Analysis Panel](#live-audio-analysis-panel)
  * [LUFS (Loudness Units relative to Full Scale)](#lufs-loudness-units-relative-to-full-scale)
  * [LUFS Overall](#lufs-overall)
  * [PEAK dBFS](#peak-dbfs)
  * [LIMIT (Limiter Activity)](#limit-limiter-activity)
  * [BPM Analysis](#bpm-analysis)
  * [KEY (Musical Key)](#key-musical-key)
  * [ENERGY (Energy Analyser)](#energy-energy-analyser)
* [Audio Effects](#audio-effects)
  * [Equalizer](#equalizer)
  * [Compressor](#compressor)
  * [Spatializer](#spatializer)
  * [Vocal Remover](#vocal-remover)
* [Playback Features](#playback-features)
  * [Early Track Advance](#early-track-advance)
  * [Fade In](#fade-in)
  * [Fade Out](#fade-out)
  * [Silence Detection](#silence-detection)
  * [Play After Current Song](#play-after-current-song)
  * [Play on Double-Click](#play-on-double-click)
  * [Play For Time](#play-for-time)
* [Playlist Generator](#playlist-generator)
  * [Concepts](#concepts)
  * [Building the Structure](#building-the-structure)
  * [Group Rules](#group-rules)
  * [Global Rules](#global-rules)
  * [Order Modes](#order-modes)
  * [Templates](#templates)
  * [Generating](#generating)
  * [Tips](#tips)
* [Themes](#themes)
* [Keyboard Shortcuts](#keyboard-shortcuts)
* [Audio Devices](#audio-devices)
* [Tips & Tricks](#tips--tricks)
* [Troubleshooting](#troubleshooting)

---

## Getting Started

### Opening Audio Files

Valkyria provides multiple convenient methods to build your music library and playlists. Each method is optimized for different workflows:

* **Open File** (Ctrl+O): Opens a file dialog to select a single audio file. Best for adding individual tracks or when you want precise control over what gets added.
* **Open Multiple Files** (Ctrl+M): Opens a file dialog allowing multiple selection. Hold Ctrl or Shift to select multiple files at once. Ideal for adding several specific tracks from a folder without adding the entire folder.
* **Open Folder** (Ctrl+F): Recursively scans a folder and all its subfolders for audio files, automatically adding them to the playlist. Perfect for importing entire album folders or music collections organized in subdirectories.
* **Open Playlist** (Ctrl+L): Load an existing M3U or M3U8 playlist file. Supports both relative and absolute file paths, making it ideal for portable playlists or shared music collections.

When you open files or folders, Valkyria automatically filters for supported audio formats and skips unsupported file types. The status bar will display the number of files successfully added.

### Supported Formats

Valkyria supports a wide range of audio formats to accommodate various quality preferences and use cases:

| Format | Type | Best Use Case |
|--------|------|---------------|
| **MP3** | Lossy compression | Universal compatibility, reasonable file size, good for large collections |
| **WAV** | Uncompressed | Studio-quality, editing, archival. Large file sizes |
| **FLAC** | Lossless compression | Audiophile listening, archival with reduced file size compared to WAV |
| **OGG** | Lossy compression | Open-source alternative to MP3, good quality-to-size ratio |
| **M4A** | Lossy/Lossless | iTunes/Apple ecosystem, AAC encoding, good mobile compatibility |

All formats support embedded metadata (title, artist, album, artwork, BPM) which Valkyria reads and displays throughout the interface.

## Playback Controls

### Basic Controls

Valkyria provides intuitive playback controls accessible via buttons, keyboard shortcuts, and the waveform seekbar:

* **Play/Pause** (Spacebar): Toggles between playing and paused states. If stopped, Play will start from the beginning of the current track. If paused, Play resumes from the paused position.
* **Stop** (S): Completely stops playback and resets the position to the beginning. Useful when you want to restart a track from scratch or clear the current playback state.
* **Previous** (Left Arrow): Jumps to the previous track in the playlist. If pressed within the first 3 seconds of a track, it goes to the previous track; otherwise, it restarts the current track.
* **Next** (Right Arrow): Advances to the next track in the playlist. Respects repeat mode settings.
* **Seek**: Click anywhere on the waveform seekbar to instantly jump to that position in the track. The waveform provides visual feedback showing the audio amplitude, making it easy to navigate to specific sections (intro, chorus, bridge, etc.).

The waveform seekbar displays a real-time representation of the audio file's amplitude envelope, helping you visualize the song structure and identify quiet or loud sections at a glance.

### Volume Control

Fine-grained volume control ensures comfortable listening levels across different tracks:

* **Volume Slider**: Drag the slider or click on the track to set a specific volume level (0-100%)
* **Mouse Wheel**: Hover over the volume slider and use the mouse wheel for quick incremental adjustments
* **Mute** (M): Instantly toggles between current volume and complete silence. Useful for quick interruptions without losing your volume setting
* **Volume Step Shortcuts**: Use dedicated keyboard shortcuts for precise +/- volume adjustments

Volume changes apply in real-time without interrupting playback. The volume setting persists across sessions.

### Repeat Modes

Choose from three repeat modes accessible from **Playback → Repeat Mode** menu:

1. **No Repeat**: Plays through the playlist once and stops at the end. Best for listening to albums or curated playlists in order.
2. **Repeat One**: Loops the currently playing track indefinitely. Perfect for focusing on a specific song, practicing lyrics, or analyzing musical elements.
3. **Repeat All**: After the last track finishes, playback automatically returns to the first track and continues indefinitely. Ideal for background music or unattended playback.

The current repeat mode persists across application restarts.

## Playlist Management

### Adding Songs

Valkyria offers flexible methods to build and modify your playlist during playback:

* **Add**: Appends selected songs from the browser view to the end of the current playlist. The playlist order remains unchanged.
* **Add Below**: Inserts selected songs immediately after the currently playing track. This is perfect for queuing up songs you want to hear next without disrupting the remaining playlist.
* **Double-click in Browser**: Double-clicking a song in the browser view adds it to the playlist. The specific behavior (play immediately or just add) can be configured in Playback Features.
* **Duplicate Detection**: Valkyria automatically prevents adding duplicate entries. If you try to add a song already in the playlist, it will be silently skipped.

### Organizing Your Playlist

Keep your playlist organized with powerful management tools:

* **Shuffle** (Ctrl+H): Randomizes the entire playlist order while preserving the currently playing track's position. Great for discovering forgotten gems in large collections.
* **Sort by Title** (Ctrl+T): Alphabetically sorts all tracks by their title metadata. Useful for finding specific songs in large playlists.
* **Sort by Artist** (Ctrl+R): Groups tracks by artist name alphabetically. Perfect for album-oriented listening or when you want to hear all tracks from a specific artist together.
* **Move Up/Down** (Ctrl+Up/Down): Manually reorder selected tracks by moving them up or down in the playlist. Supports multi-selection for moving multiple tracks at once.
* **Remove Selected** (Delete): Removes one or more selected tracks from the playlist without deleting the actual files from disk.
* **Clear** (Ctrl+C): Removes all tracks from the playlist after confirmation. Use this to start fresh without closing the application.

All organization operations update the playlist view immediately and preserve your current playback position whenever possible.

### Saving Playlists

Playlists can be saved and loaded for later use:

* **Save Playlist** (Ctrl+S): Saves changes to the currently loaded playlist file. If no file is currently loaded, behaves like "Save Playlist As".
* **Save Playlist As** (Ctrl+Shift+S): Opens a save dialog to create a new playlist file or overwrite an existing one.
* **M3U8 Format**: Playlists are saved in the widely-compatible M3U8 format (UTF-8 encoded M3U), which can be opened in most media players and DJ software.

Playlist files store file paths (absolute by default) and can be edited in any text editor. Relative paths are supported for portable playlists that can be moved between different computers.

## Browser View

The browser view provides a convenient file explorer integrated directly into Valkyria for browsing and adding music to your playlist.

### Navigation

* **Browse Folder**: Open a directory browser to navigate your music library
* **Browse Files**: Open a file picker to select specific audio files
* **Current Directory**: Displays the currently browsed folder path
* **Parent Directory**: Navigate up one folder level

### Adding to Playlist

Once you've browsed to a folder containing audio files:

* **Select Files**: Click to select individual files, Ctrl+Click for multiple selection, Shift+Click for range selection
* **Add Button**: Adds selected files to the end of the playlist
* **Add Below Button**: Inserts selected files after the currently selected track in the playlist. If nothing is selected in the playlist, files are inserted after the currently playing track.
* **Double-Click**: Previews, i.e. plays in secondary audio device if available, the selected file (see [Song Preview](#song-preview) below).

You can also drag songs from the browser view and drop them in the playback queue.

### Song Preview

The browser includes a built-in audio preview that lets you audition files through a secondary audio device without interrupting main playback.

#### Preview Output Device

A **Preview output** dropdown appears above the file list. It lists all available audio output devices **except** the one currently used by the main player, so preview audio is always routed to a different device.

* If only one audio output device is connected, the preview controls are disabled automatically.
* The dropdown updates whenever you change the main player's output device via **Settings → Audio Device**.

#### Previewing a File

* **Double-click** any file in the browser list to start previewing it. Double-clicking the same file again stops the preview.
* The **▶** button starts (or restarts) preview playback for the currently selected file.
* The **⏹** button stops playback immediately.

Preview playback is independent from the main playlist — starting a preview does not affect the currently playing track, and stopping the preview does not pause or stop the main player.

### Browser Tips

* **Drag and Drop**: Drag files from the browser directly onto the playlist
* **Quick Access**: Keep browser view visible (F10) for instant access to your music library

## Live Audio Analysis Panel

The Live Audio Analysis Panel is located at the bottom-right corner of Valkyria and provides real-time audio metrics and track information during playback. This professional-grade metering suite helps you monitor loudness levels, understand track characteristics, and make informed decisions about audio processing.

### Audio Metering (Left Column)

#### LUFS (Loudness Units relative to Full Scale)

Displays the momentary loudness of the currently playing audio in real-time. This measurement updates approximately 20 times per second and represents the perceived loudness of the audio content.

* **Range**: -60.0 to 0.0 LUFS
* **Update Rate**: ~50ms refresh interval
* **Independence**: Unaffected by application volume, system volume, or audio effects
* **Purpose**: Measures the true loudness of the source audio file

**Typical LUFS Values:**

| Range | Description |
|-------|-------------|
| **-6 to 0 LUFS** | Very loud (modern pop, EDM, heavily compressed tracks) |
| **-12 to -6 LUFS** | Loud (rock, commercial radio, most streaming-ready tracks) |
| **-18 to -12 LUFS** | Moderate (well-mastered albums, classical with dynamics) |
| **-30 to -18 LUFS** | Quiet (speech, ambient, acoustic recordings) |
| **Below -30 LUFS** | Very quiet (silence, room noise, intros/outros) |

#### LUFS (Overall)

Displays the integrated loudness measurement for the entire track from start to finish. This value represents the average perceived loudness across the complete duration of the song.

* **Calculation**: Continuously accumulated from track start
* **Purpose**: Shows overall track loudness for comparison and mastering reference
* **Usage**: Helps identify tracks that need volume normalization or remastering

**Comparing LUFS and Overall:**
* **LUFS**: Fluctuates moment-to-moment (quiet verses vs. loud choruses)
* **Overall**: Stable average that converges as more of the track plays

#### PEAK dBFS

Displays the maximum instantaneous sample level in the audio stream as a real-time visual bar meter. Unlike numerical displays, the visual bar provides instant feedback on headroom and clipping risk.

* **Display**: Horizontal bar that fills from left to right
* **Range**: -60.0 to 0.0 dBFS
* **Update Rate**: ~50ms refresh interval
* **Independence**: Unaffected by application volume or system volume settings
* **Purpose**: Monitors headroom and prevents digital clipping
* **Warning**: Bar approaching full (red) indicates risk of clipping/distortion

**Peak Level Color Coding:**

* **Blue** (0-40%): Low level (-60 to -24 dBFS) - Quiet signal, no immediate concern but may indicate recording issues
* **Green** (40-70%): Good level (-24 to -12 dBFS) - Healthy signal with adequate headroom, optimal for mastered tracks
* **Red** (70-100%): Hot signal (-12 to 0 dBFS) - Normal for heavily compressed material but watch for clipping

**Peak Level Guide:**

| Range | Color | Status | Action |
|-------|-------|--------|--------|
| **-12 to 0 dBFS** | Red | Hot signal | Normal for mastered tracks. Watch for 0 dBFS |
| **-24 to -12 dBFS** | Green | Good level | Healthy signal with adequate headroom |
| **-40 to -24 dBFS** | Blue | Low level | Consider increasing gain or checking source |
| **Below -40 dBFS** | Blue | Very low | Likely a problem with the recording or file |

**How Peak Differs from LUFS:**

| Metric | Peak dBFS | LUFS |
|--------|-----------|------|
| **Measurement** | Maximum instantaneous sample | Perceived loudness (averaged) |
| **Response** | Immediate peak detection | Smoothed over time |
| **Purpose** | Headroom monitoring, clipping detection | Loudness perception analysis |

**Reading the Peak Meter:**

The peak meter provides instant visual feedback that helps you monitor signal headroom at a glance:

* **Consistently Blue**: Low-level recording, may need gain adjustment or signal boost
* **Mostly Green with Occasional Red Spikes**: Normal dynamic tracks with good average level and occasional peaks
* **Consistently Red**: Compressed/limited material with little dynamic range, watch for clipping
* **Filling Completely**: Risk of digital clipping and distortion

**Technical Details:**

* **Calculation Method**: Maximum absolute sample value per audio block
* **Scale Factor**: dBFS values (-60..0) are normalized to 0-1 range for bar visualization
* **Measurement Point**: Calculated from source audio after effects but before volume adjustment
* **Performance**: Minimal CPU impact; calculated alongside LUFS and Energy measurements

**Usage Tips:**

* Use the peak meter in combination with LUFS for complete loudness analysis
* Monitor peak during playback to ensure no unexpected clipping occurs
* Color-coded display eliminates need to watch numerical values
* Perfect for identifying mix issues (excessive peaks vs. low average level)

#### LIMIT (Limiter Activity)

LIMIT is a visual bar graph showing compression/limiting activity or signal intensity.

* **Display**: Horizontal bar that fills from left to right
* **Color Coding**:
  * Blue (0-40%): Low activity
  * Green (40-70%): Moderate activity
  * Red (70-100%): High activity
* **Purpose**: Visual feedback for dynamics monitoring

This meter can be used to monitor how "aggressive" or dynamic the audio content is, helping you understand the compression characteristics of the source material.

#### BPM Analysis

BPM (Beats Per Minute) analysis displays the tempo of the currently playing track. For detailed technical information about how BPM analysis works, see the dedicated **BPM Analysis** documentation in the Help menu.

* **Source**: Read from file metadata or calculated via BPM analysis
* **Display**: Shows "--" when BPM is unavailable or not yet analyzed
* **Normalization**: Optional automatic adjustment to perceptually accurate tempo range (configurable in Preferences)
* **Usage**: Essential for DJ mixing, tempo-based playlists, workout music

**How to Populate BPM:**

1. Ensure track is loaded in the playlist and playing
2. Wait for BPM estimation to complete (typically 3-25 seconds)
3. Click "Save BPM" to permanently store the value in file metadata

**BPM Normalization**

BPM analysis sometimes produces "half-time" (too slow) or "double-time" (too fast) results. Valkyria includes optional automatic normalization to bring BPM values into the musically perceived range (80-180 BPM for most music).

**Normalization can be enabled/disabled in Preferences:**

* **Enabled**: BPM values are automatically adjusted to match human-perceived tempo (matches professional DJ software)
* **Disabled**: Raw, unprocessed BPM values from the analysis algorithm

**Note**: Stored BPM values are always in their raw form. Normalization only affects display.

**Usage Tips**

* **Batch Analysis**: Analyze your entire library during idle time, then use BPM values for sorting or DJ mixing
* **CPU Intensive**: BPM analysis is computationally demanding. Don't analyze many tracks while recording or in other CPU-intensive tasks
* **File Format Note**: BPM can be saved to MP3, FLAC, M4A, and OGG files. WAV files do not natively support metadata tags

#### KEY (Musical Key)

Displays the musical key/tonality of the track using Camelot wheel notation for convenient DJ mixing.

* **Source**: Read from file metadata or calculated using the "Calculate Key" control (analysis).
* **Display**: Shown using the **Camelot wheel** format when available (e.g., `8A` for A minor, `8B` for C major). If Camelot cannot be determined, the raw key (e.g., `Am`, `C`) is shown.
* **Entry behavior**: The Key input field shows the Camelot code (display-only) for easier DJ use; when you save metadata, the original raw key string is written to the file (no Camelot tag is written).
* **Usage**: Harmonic mixing for DJs, music theory analysis, key-compatible playlist creation

**Common Key Notations:**

* Major keys: C, D, E, F, G, A, B (with sharps # or flats b)
* Minor keys: Cm, Dm, Em, Fm, Gm, Am, Bm (with sharps # or flats b)

**Camelot wheel**

Codes useful for harmonic mixing:

| Raw Key | Camelot |
|---------|---------|
| C       | 8B      |
| Am      | 8A      |
| G       | 9B      |
| Em      | 9A      |
| D       | 10B     |
| Bm      | 10A     |
| A       | 11B     |
| F#m     | 11A     |
| E       | 12B     |
| C#m     | 12A     |

Key information must be present in the audio file's metadata tags. Valkyria does not automatically detect musical key.

#### ENERGY (Energy Analyser)

The Energy Analyser is a real-time intensity meter that visualizes the dynamic energy of the currently playing audio. Unlike LUFS which measures perceived loudness, the energy meter shows the instantaneous power or "intensity" of the audio signal, helping you understand the track's dynamics and energy flow.

* **Display**: Horizontal bar graph that fills from left to right
* **Range**: 0.0 (silence) to 1.0 (maximum energy)
* **Update Rate**: ~50ms refresh interval
* **Color Coding**:
  * **Blue** (0-40%): Low energy - Quiet passages, ambient sections, intros, soft verses
  * **Green** (40-70%): Medium energy - Normal verses, moderate dynamics, typical music content
  * **Red** (70-100%): High energy - Loud choruses, drops, climaxes, heavy instrumentation
* **Independence**: Unaffected by application volume or system volume settings

**How Energy Differs from LUFS:**

| Metric | LUFS | Energy |
|--------|------|--------|
| **Measurement** | Perceived loudness (averaged) | Instantaneous signal power |
| **Response** | Smoothed over time | Instant response to dynamics |
| **Scale** | Logarithmic (dB) | Linear (0-1) |
| **Purpose** | Track loudness monitoring | Dynamic intensity visualization |

**Practical Applications:**

* **DJ Mixing**: Identify energy peaks and valleys for seamless transitions and mix points
* **Song Structure Analysis**: Visually identify verses (low/medium), choruses (high), bridges, and breakdowns
* **Energy Matching**: Select tracks with similar energy profiles for playlist continuity
* **Practice and Performance**: Monitor energy flow for timing cues during live performances or rehearsals
* **Track Selection**: Quickly assess if a track's energy matches the desired mood or context

**Reading the Energy Meter:**

The energy meter provides instant visual feedback that helps you understand track dynamics at a glance:

* **Consistently Low** (Blue): Ambient, acoustic, ballads, or quiet background music
* **Moderate with Peaks** (Green/Blue with Red spikes): Dynamic tracks with loud/soft contrast
* **Consistently High** (Red): Compressed, "loud" modern productions, EDM, heavy rock
* **Gradual Build** (Blue→Green→Red): Tracks with build-ups leading to drops or climaxes

**Technical Details:**

* **Measurement Independence**: LUFS and Peak measurements are calculated from the source audio after effects but before volume/muting is applied, ensuring accurate readings regardless of playback volume
* **Thread Safety**: All meter updates are performed in a thread-safe manner, preventing UI blocking or audio dropouts
* **Precision**: LUFS calculations use industry-standard RMS-to-dBFS conversion algorithms for broadcast-quality loudness metering
* **Performance**: Real-time audio analysis has negligible CPU impact and does not affect audio quality or latency

**Usage Tips:**

* Use the energy meter in combination with LUFS for complete dynamic analysis
* High energy doesn't necessarily mean high LUFS - a dynamic track can have high peak energy but moderate average LUFS
* The color-coded display makes it easy to spot energy transitions without watching numbers
* Perfect for visual cueing when beatmatching or preparing DJ transitions

## Audio Effects

Access the audio effects panel from **Tools → Audio Effects and Filters**. All effects process audio in real-time and can be enabled/disabled independently. Effects are applied in the following order: Equalizer → Compressor → Vocal Remover → Spatializer.

### Equalizer

The 10-band graphic equalizer allows precise frequency-specific adjustments for tonal balance and acoustic compensation.

#### Frequency Bands

| Band | Frequency | Typical Instruments/Sounds |
|------|-----------|----------------------------|
| 1 | 60 Hz | Sub-bass, kick drum fundamental, deep bass |
| 2 | 170 Hz | Bass guitar fundamental, bass warmth |
| 3 | 310 Hz | Bass clarity, guitar body, lower midrange |
| 4 | 600 Hz | Vocal warmth, guitar thickness, midrange body |
| 5 | 1 kHz | Vocal intelligibility, guitar definition, presence |
| 6 | 3 kHz | Vocal clarity, snare attack, upper midrange |
| 7 | 6 kHz | Vocal brightness, cymbal attack, definition |
| 8 | 12 kHz | Hi-hat detail, cymbal shimmer, high presence |
| 9 | 14 kHz | Air and space, extreme highs, brilliance |
| 10 | 16 kHz | Ultra-highs, ambiance, "sparkle" |

#### Controls

* **Gain Sliders**: Adjust each band from -12 dB (cut) to +12 dB (boost)
* **Enable/Disable**: Toggle the entire equalizer on/off to A/B compare the effect
* **Reset Button**: Returns all bands to 0 dB (flat response)

#### Usage Tips

* **Room Compensation**: If your room has bass buildup, cut the 60-170 Hz range by 2-4 dB
* **Vocal Presence**: Boost 1-3 kHz by 2-3 dB to make vocals stand out in the mix
* **Harsh Reduction**: If cymbals or high frequencies sound harsh, cut 6-12 kHz by 2-3 dB
* **Warmth**: Boost 170-310 Hz by 2-3 dB for added warmth and body
* **Avoid Extremes**: Boosts beyond 6 dB can cause distortion; start with small adjustments (2-3 dB)

The equalizer uses high-quality bi-quad IIR filters with linear phase response to minimize artifacts and phase shifts.

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

* **Subtle Enhancement**: Start with threshold at -18 dB, ratio at 3:1, attack at 10 ms, release at 100 ms
* **Consistent Volume**: For playlists with varying track volumes, use moderate compression (3:1-4:1 ratio)
* **Avoid Over-Compression**: Ratios above 8:1 can make music sound lifeless and fatiguing
* **Fast Attack for Drums**: Shorter attack times (1-5 ms) help control drum transients
* **Slow Attack for Punch**: Longer attack times (20-50 ms) preserve drum impact and attack

The compressor includes automatic makeup gain to compensate for the overall volume reduction caused by compression.

### Spatializer

Creates a sense of space and depth by combining stereo width control with a simple room ambience simulation. This effect enhances the perceived size of the listening environment and can make tracks sound more immersive.

#### Controls

* **Enable/Disable**: Toggle the effect on/off
* **Size**: Room size simulation (0.0-1.0, default 0.85)
* **Width**: Stereo width control (0.0-1.0, default 0.5)
* **Wet**: Amount of ambience effect (0.0-1.0, default 0.4)
* **Dry**: Amount of original signal (0.0-1.0, default 0.5)
* **Damp**: Reverb decay control (0.0-1.0, default 0.5)

#### How It Works

The spatializer combines two audio processing techniques:

1. **Stereo Width Control**: Uses mid-side processing to adjust the stereo image width
2. **Cross-Delay Ambience**: Creates a sense of space through subtle delays and feedback

#### Parameter Guide

| Parameter | Range | Effect |
|-----------|-------|--------|
| **Size** | 0.0-1.0 | Controls delay time (0-100ms). Higher values create larger room feel |
| **Width** | 0.0-1.0 | Stereo spread. 0.5 = original width, 1.0 = enhanced stereo |
| **Wet** | 0.0-1.0 | Amount of ambience added. Higher = more spacious |
| **Dry** | 0.0-1.0 | Amount of original sound preserved. Usually keep near 0.5 |
| **Damp** | 0.0-1.0 | Reverb decay. Higher = longer, more natural decay |

#### Recommended Settings

| Use Case | Size | Width | Wet | Dry | Damp |
|----------|------|-------|-----|-----|------|
| **Subtle Enhancement** | 0.7 | 0.6 | 0.3 | 0.7 | 0.4 |
| **Concert Hall Feel** | 0.9 | 0.8 | 0.5 | 0.5 | 0.6 |
| **Intimate Room** | 0.5 | 0.4 | 0.2 | 0.8 | 0.3 |
| **Maximum Immersion** | 1.0 | 1.0 | 0.6 | 0.4 | 0.7 |

#### Usage Tips

* **Headphone Listening**: Increase Width to 0.7-0.8 and Wet to 0.4-0.5 for better spatial imaging
* **Speaker Listening**: Moderate settings work best; avoid extreme Width values
* **Problem Tracks**: If a track sounds too dry or boxy, try Size 0.8, Wet 0.3
* **Live Recordings**: Can add warmth and space to sterile live recordings
* **Avoid Overuse**: Too much Wet can make tracks sound washed out or muddy

#### Technical Details

The effect processes audio in two stages:

1. **Mid-Side Width Processing**: Separates mono (mid) and stereo (side) components, then recombines them with adjustable width
2. **Cross-Feed Delay**: Creates subtle echoes by feeding delayed left channel to right and vice versa, with controlled feedback for natural decay

### Vocal Remover

Removes or attenuates vocals from stereo tracks using advanced frequency-selective processing, useful for karaoke, instrumental practice, or vocal isolation.

#### How It Works

Unlike simple phase-cancellation methods, this vocal remover uses sophisticated signal processing:

1. **Mid-Side Decomposition**: Separates the audio into center (mono) and side (stereo difference) components
2. **Frequency-Selective Filtering**: Applies a precision band-stop filter (200Hz-8kHz) to the center channel only
3. **Intensity Blending**: Mixes filtered and unfiltered center channel based on intensity setting
4. **Stereo Reconstruction**: Recombines processed center with original side channel

#### Controls

* **Enable/Disable**: Toggle the effect on/off
* **Intensity**: Adjust removal strength from 0.0 (no effect) to 1.0 (maximum removal)

#### Technical Details

The effect targets the typical vocal frequency range (200Hz-8kHz) while preserving:

* **Bass frequencies** (<200Hz): Kick drums, bass guitar, etc.
* **High frequencies** (>8kHz): Cymbals, high hats, air sounds
* **Stereo imaging**: Side channel remains untouched

#### Usage Tips

* **Professional Recordings**: Works best on studio-mixed tracks with centered lead vocals
* **Live Recordings**: Less effective due to non-standard panning and room acoustics
* **Reverberant Vocals**: May not fully remove vocals that bleed into the stereo field
* **Mono Sources**: No effect on mono recordings (requires stereo information)
* **Optimal Settings**: Start at 0.5 intensity; increase to 0.8-1.0 for stubborn vocals

#### Limitations

* **Not Perfect**: Some vocal energy may remain due to stereo bleed or unusual mixing
* **Frequency Overlap**: Instruments in the 200Hz-8kHz range may be affected
* **Processing Latency**: Introduces slight delay due to IIR filtering
* **Not Real-time**: Best used for offline processing or when precise vocal removal is needed

## Playback Features

Access advanced playback options from **Tools → Playback Features**.

### Early Track Advance

Skips the last stretch of the current track and starts the next one early, instead of waiting for it to reach its natural end. This avoids playing through a long trailing silence or dead air before the next track begins.

Note: this does **not** overlap or blend the two tracks — the current one stops and the next one starts, just earlier than it otherwise would. If you're after an actual DJ-style blended transition, this isn't that.

#### Settings

* **Enable/Disable**: Toggle early advance on/off
* **Duration**: Set how many seconds before the natural end it should switch, from 0 to 10 seconds

#### How It Works

When enabled, the app watches the remaining time on the current track. Once it drops to [Duration] seconds or less, it advances to the next track immediately — the same transition that would happen at a natural track end, just triggered a few seconds sooner.

#### Usage Tips

* **Typical Settings**: 3-5 seconds works well for most music
* **Longer Windows**: 8-10 seconds for tracks with long fade-outs or trailing silence you want to skip past
* **Shorter Windows**: 1-2 seconds if you only want to trim a small gap
* **Disable for Podcasts**: Cutting in early is generally not suitable for spoken content or live albums, where the natural ending matters

Early Track Advance respects repeat mode settings. In "Repeat One" mode, it restarts the same track early rather than letting it play to the end — and doing so resets repeat mode back to "No Repeat", so it won't keep looping.

### Fade In

Gradually increase volume from silence at the beginning of each track, creating a smooth entry and reducing jarring starts.

#### Settings

* **Enable/Disable**: Toggle fade in on/off
* **Duration**: Set fade in length from 0 to 10 seconds (default: 3 seconds)

#### How It Works

When fade in is enabled, each track starts at zero volume and gradually increases to full volume over the specified duration. This creates a gentle, professional-sounding introduction to every track.

#### Usage Tips

* **Typical Settings**: 3-4 seconds provides a smooth start without feeling sluggish
* **Quick Fade**: 1-2 seconds for minimal fade while still avoiding abrupt starts
* **Dramatic Entrance**: 5-8 seconds for ambient, classical, or cinematic tracks
* **Disable for Live Albums**: Fade in may affect the natural flow of live recordings
* **Session Only**: Fade in settings are cached during your session but not automatically saved to disk. Use the "Save" button in Playback Features to persist changes.

### Fade Out

Gradually decrease volume to silence at the end of each track, creating a smooth exit and preventing abrupt endings.

#### Settings

* **Enable/Disable**: Toggle fade out on/off
* **Duration**: Set fade out length from 0 to 10 seconds (default: 3 seconds)

#### How It Works

When fade out is enabled, the track begins fading out when it reaches the point where [Duration] seconds remain. The volume gradually decreases to silence, creating a gentle conclusion.

#### Usage Tips

* **Typical Settings**: 3-4 seconds works well for most music
* **Quick Fade**: 1-2 seconds for subtle endings
* **Extended Fade**: 5-8 seconds for tracks with long natural outros or ambient music
* **Combine with Early Track Advance**: Fade out works independently of early track advance. You can use both together — fade out smooths the last moment of audio that actually plays, early advance decides when that moment is
* **Session Only**: Fade out settings are cached during your session but not automatically saved to disk. Use the "Save" button in Playback Features to persist changes.

#### Fade In/Out vs. Early Track Advance

| Feature | Fade In | Fade Out | Early Track Advance |
|---------|---------|----------|-----------|
| **Applies To** | Track start | Track end | Track transitions |
| **Behavior** | Silence → Full volume | Full volume → Silence | Switches to the next track early |
| **Use Case** | Smooth track entry | Smooth track exit | Skip trailing silence/dead air |
| **Can Combine** | Yes | Yes | Yes |

### Silence Detection

Automatically skips to the next track when the current track ends with prolonged silence, preventing dead air in your listening experience.

#### Settings

* **Enable/Disable**: Toggle silence detection on/off
* **Threshold**: -50 dBFS (fixed)
* **Duration**: 3 seconds (fixed)

#### How It Works

When silence detection is enabled, Valkyria continuously monitors the audio level during playback. If the audio level stays below -50 dBFS (essentially silence) for 3 consecutive seconds, the player automatically advances to the next track.

#### Technical Details

* **Detection Method**: RMS-based audio level analysis
* **Threshold**: -50 dBFS (approximately 0.3% of full scale amplitude)
* **Duration**: 3 seconds of continuous silence required before triggering
* **Reset**: Silence counter resets whenever audio rises above the threshold
* **Thread Safe**: Detection runs in the audio callback without blocking playback

#### Usage Tips

* **Always Active**: Once enabled, silence detection works on all tracks automatically
* **No False Triggers**: The 3-second duration prevents skipping during musical pauses or quiet passages
* **Respects Repeat Mode**: Works correctly with "Repeat One" and "Repeat All" modes
* **Independent of Volume**: Detection measures source audio level, not playback volume
* **Session Only**: Silence detection setting is cached during your session but not automatically saved to disk. Use the "Save" button in Playback Features to persist changes.

#### Limitations

* **Very Quiet Tracks**: Extremely quiet ambient or noise tracks below -50 dBFS may trigger premature skipping
* **Intentional Silence**: Tracks with artistic silence (e.g., John Cage's "4'33"") will be skipped
* **Live Recordings**: Applause or crowd noise usually prevents false triggers, but very quiet venue recordings may be affected

### Play After Current Song

Move selected tracks to play immediately after the currently playing song, allowing you to queue up tracks without disrupting your playlist order.

#### Access Methods

* **Playback Menu**: **Playback → Operations → Play After Current Song** (Ctrl+Shift+A)
* **Context Menu**: Right-click any track in the playlist and select "Play After Current Song"

#### How It Works

When you select one or more tracks and use "Play After Current Song":

1. The selected tracks are removed from their current positions
2. They are inserted immediately after the currently playing track
3. The current track continues playing uninterrupted
4. The selected tracks will play next, in their original relative order
5. The remaining playlist order is preserved

#### Behavior Details

* **Multiple Selection**: Select multiple tracks to queue them all in sequence
* **Order Preservation**: Selected tracks maintain their relative order when moved
* **Current Track Ignored**: If the currently playing track is in your selection, it's ignored (can't place after itself)

### Play on Double-Click

Controls the behavior when double-clicking a song in the playlist.

#### Options

* **Enabled**: Double-clicking a playlist item immediately starts playing that track
* **Disabled**: Double-clicking only selects the track without changing playback

#### Use Cases

* **Enable**: For quick access and immediate playback (traditional media player behavior)
* **Disable**: When you frequently select tracks for metadata viewing or batch operations and don't want accidental playback changes

### Play For Time

Set a specific playback duration for any track in the playlist. When the playback reaches the specified time limit, it will automatically skip to the next track, regardless of the song's actual duration.

#### Setting a Time Limit

**From the Main Menu:**
1. Select a song in the playlist
2. Go to **Playback → Operations → Play for time...**
3. Choose a preset (10s, 30s, 1m, 2m) or enter a custom value in seconds
4. Click "Set Limit"

**From the Context Menu:**
1. Right-click on any song in the playlist
2. Select **⏱ Play for time...**
3. Choose a preset or enter a custom value
4. Click "Set Limit"

#### Clearing a Time Limit

**From the Main Menu:**
1. Select a song with a time limit
2. Go to **Playback → Operations → Clear time limit**

**From the Context Menu:**
1. Right-click on a song with a time limit
2. Select **✖ Clear time limit**

#### Visual Indicators

**Playlist Duration Column:**
When a time limit is set, the Duration column displays the limit with a clock icon:
* `⏱ 30s` (instead of the normal duration like `3:45`)

**Status Bar:**
When playing a song with a time limit, the status bar shows the limit next to the duration:
* `3:45 [⏱ 30s] • 320 kbps`

## Playlist Generator

The Playlist Generator builds structured playlists automatically from your music library. Open it via **Tools → Playlist Generator**.

Instead of manually picking songs, you define *groups* of source material and the rules that govern how songs are selected and interleaved. The generator produces a ready-to-use playlist or populates the browser for further review.

### Concepts

**Groups** represent musical categories (e.g., "Tangos", "Vals", "Milongas"). The generator alternates between groups in round-robin order.

**Subgroups** are subdivisions of a group — typically one per orchestra, album, or mood. They let the generator vary the source within a group from round to round.

**Sources** are the actual files the generator draws from: individual audio files, folders, or M3U playlists.

**Rounds** are the fundamental unit of generation. In each round, every group contributes a fixed number of songs (`Songs per round`), then the cycle repeats.

### Building the Structure

#### Adding Groups and Subgroups

* **+ Group**: Creates a new named group. Double-click a group in the tree to rename it.
* **+ Subgroup**: Creates a named subgroup inside the selected group. Double-click to rename.
* **↑ Up / ↓ Down**: Reorders the selected item within its parent.
* **Rename / Remove**: Rename or delete the selected group, subgroup, or source.

#### Loading Songs

Three buttons load songs into the structure. The target is determined automatically based on what is selected in the tree:

| Selection | Result |
|---|---|
| Nothing selected | A new numbered group ("Group 1", "Group 2", …) is created with a Default subgroup |
| Group with no subgroups | Songs go into a "Default" subgroup created inside that group |
| Group with existing subgroups | A new numbered subgroup ("Subgroup 1", "Subgroup 2", …) is created inside the group |
| Subgroup selected | Songs are added directly to that subgroup (extending it) |
| Source selected | Songs are added to the source's parent subgroup |

* **Load Files**: Pick one or more individual audio files (MP3, WAV, FLAC, OGG, M4A).
* **Load Folder**: Pick a folder. All audio files are found recursively, including subdirectories.
* **Load M3U**: Pick one or more M3U/M3U8 playlists and import their tracks.

Opening the file dialog without selecting anything first automatically creates a new group, so you never need to manually add a group before loading.

### Group Rules

Select a group (or anything inside it) to edit its rules in the right panel.

* **Songs per round**: How many songs this group contributes in each round. Default is 1.
* **BPM range**: Leave both fields blank to accept any tempo. Fill one or both to restrict the pool to songs within that BPM window. Songs without BPM metadata are excluded when a filter is active.
* **Key**: Filter the pool to songs in a specific musical key. Set to "Any" to disable.

BPM and key filters are applied when building the pool before generation, so they work with all order modes.

### Global Rules

These settings apply to the entire generated playlist.

* **Total songs**: The maximum number of songs to generate. Set to "Unlimited" for no cap.
* **Total duration**: The maximum total running time in minutes. Set to "Unlimited" for no cap.
* **Allow repeats**: When unchecked (default), each song appears at most once regardless of how many groups reference the same files.
* **Order mode**: Controls how songs are sequenced within and across groups. See [Order Modes](#order-modes) below.

### Order Modes

#### Original order within groups
Songs within each group are presented in alphabetical order by filename. The round-robin interleaving is deterministic and repeatable.

#### Shuffle within groups
Each group's full pool is shuffled once before generation begins. The round-robin interleaving pattern (e.g., 4 tangos then 1 val) is preserved, but which specific songs appear in each round is random.

#### Fully random
All groups are merged into a single pool which is then shuffled. Group boundaries, `Songs per round` settings, and subgroup structure are all ignored. Every song has an equal chance of appearing at any position.

#### Random subgroup per round
Designed for structured variety within categories. In each round, the generator picks a subgroup at random for each group, then takes `Songs per round` tracks from that subgroup. The next round uses a *different* subgroup, cycling through all available subgroups in a randomly shuffled order before repeating. Songs within each subgroup are shuffled.

**Example — Tango DJ set with orchestras as subgroups:**

| Round | Group "Tangos" (4 songs) | Group "Vals" (1 song) |
|---|---|---|
| 1 | Subgroup "D'Arienzo" | Subgroup "Canaro" |
| 2 | Subgroup "Pugliese" | Subgroup "Di Sarli" |
| 3 | Subgroup "Troilo" | Subgroup "Canaro" (cycles back) |
| 4 | Subgroup "D'Arienzo" (cycles back) | Subgroup "Lomuto" |

If a group has no subgroups, it behaves identically to the "Shuffle within groups" mode.

### Templates

Templates save and restore a complete generator configuration (groups, subgroups, sources, all rules).

* **Save / Save As…**: Save the current configuration under a name.
* **Load**: Restore the selected template from the dropdown.
* **Delete**: Remove the selected template permanently.

Templates are stored locally and persist across application restarts. Use them to maintain different configurations for different event types (milonga, practice, practica).

### Generating

Click **Generate Playlist** to build the playlist. Generation runs in the background; a summary (song count and total duration) appears in the status bar when complete.

A dialog then asks where to send the result:

* **Replace Playlist**: Clears the current playlist and fills it with the generated songs.
* **Append to Playlist**: Adds the generated songs after the last track in the current playlist.
* **Send to Browser**: Loads the generated songs into the browser view so you can preview and selectively add them to the playlist.
* **Cancel**: Discards the result without changing anything.

### Tips

* Build one group per dance style and one subgroup per orchestra. Use "Random subgroup per round" to produce authentic tandas without manual curation.
* Load Folder is recursive — point it at a top-level artist or genre folder and it will find all audio files inside.
* Set a Total duration limit to generate a playlist that fills exactly one event's worth of music.
* Save a template before experimenting so you can restore your baseline configuration.

## Track Information

Access detailed track metadata from **Playback → Operations → Track Information** (Ctrl+I), or right-click a track in the playlist and select "Track Information".

The Track Information window displays comprehensive metadata and technical details:

#### Metadata Fields

* **Title**: Song title from file metadata
* **Artist**: Performing artist or band name
* **Album**: Album or release name
* **Album Artist**: Album-level artist (may differ from track artist on compilations)
* **Year**: Release year
* **Genre**: Musical genre classification
* **Track Number**: Position in the album
* **Comment**: User-defined text notes

#### Technical Information

* **Duration**: Total track length in minutes:seconds
* **Bitrate**: Audio encoding bitrate in kbps (higher generally means better quality)
* **Sample Rate**: Audio sampling frequency in Hz (44.1 kHz is CD quality)
* **Channels**: Stereo (2) or Mono (1)
* **Format**: File container format (MP3, FLAC, WAV, etc.)
* **File Size**: Total file size on disk
* **File Path**: Complete path to the file's location

#### BPM Information

* **BPM**: Beats per minute (tempo). May be blank if not analyzed or stored in metadata
* **Analyze Button**: Click to trigger automatic BPM detection

#### Album Artwork

If embedded in the file metadata, the album artwork is displayed at full resolution. You can also access artwork via **Playback → Operations → Show Album Booklet** (Ctrl+B).


## Themes

Valkyria includes carefully crafted dark and light themes for comfortable viewing in any environment.

### Switching Themes

1. Open **Tools → Preferences** (Ctrl+P)
2. Select your preferred theme from the dropdown
3. Click **Apply** to immediately switch themes

### Theme Characteristics

| Feature | Dark Theme | Light Theme |
|---------|-----------|-------------|
| **Background** | Deep charcoal (#1E1E1E) | Soft white (#FAFAFA) |
| **Text** | Light gray (#FFFFFF) | Dark gray (#000000) |
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

* **Ctrl+O**: Open File
* **Ctrl+M**: Open Multiple Files
* **Ctrl+F**: Open Folder
* **Ctrl+L**: Open Playlist
* **Ctrl+S**: Save Playlist
* **Ctrl+Shift+S**: Save Playlist As

### Playback

* **Spacebar**: Play/Pause
* **S**: Stop
* **Left Arrow**: Previous Track
* **Right Arrow**: Next Track
* **M**: Mute

### Playlist

* **Ctrl+H**: Shuffle
* **Ctrl+T**: Sort by Title
* **Ctrl+R**: Sort by Artist
* **Ctrl+Up**: Move Selected Up
* **Ctrl+Down**: Move Selected Down
* **Ctrl+Shift+A**: Play After Current Song
* **Delete**: Remove Selected
* **Ctrl+C**: Clear Playlist
* **Ctrl+I**: Track Information
* **Ctrl+B**: Show Album Booklet

### View

* **F9**: Toggle Playlist Visibility
* **F10**: Toggle Browser Visibility
* **F11**: Toggle Live Audio Analysis Panel (Show/Hide)

### Other

* **Ctrl+P**: Preferences
* **F7**: Audio Effects and Filters
* **F8**: Playback Features
* **F1**: About
* **Alt+F4**: Quit

## Audio Devices

Valkyria automatically detects all available audio output devices on your system. Select your preferred device from **Tools → Audio Device**.

### Device Selection

* The current system default device is marked with "(system default)"
* Click any device to immediately switch audio output
* Changes apply in real-time without interrupting playback
* Selected device persists across application restarts

### Common Use Cases

* **Multiple Audio Interfaces**: Switch between built-in speakers, USB DACs, or professional audio interfaces
* **Headphones vs. Speakers**: Quickly toggle between different output devices
* **ASIO Devices**: Professional audio interfaces with ASIO drivers are supported on Windows

### Troubleshooting

If a device doesn't appear in the list:
* Ensure the device is properly connected and recognized by your OS
* Restart Valkyria after connecting new audio hardware
* Check device drivers are up to date

## Tips & Tricks

### Performance

* **Large Playlists**: For playlists with 1000+ tracks, sorting and shuffling operations may take a moment to complete. The application remains responsive during these operations.
* **BPM Analysis**: BPM analysis is CPU-intensive. For best results, analyze tracks during idle time rather than while recording, gaming, or performing other CPU-intensive tasks.
* **Memory Usage**: Valkyria loads metadata on demand and caches it efficiently. Even very large libraries (10,000+ files) are handled smoothly.

### File Management

* **Organized Libraries**: Maintain a consistent folder structure (e.g., Artist → Album → Tracks) for easier browsing
* **Metadata Quality**: Ensure files have accurate ID3 tags for better organization and display
* **Backup Playlists**: Regularly save important playlists. Consider using relative paths for portable playlists
* **M3U8 Compatibility**: Valkyria's playlists work in VLC, foobar2000, and most other players

### Audio Quality

* **Lossless for Archival**: Use FLAC or WAV for your music archive; convert to lossy formats only for portable devices
* **320 kbps MP3**: Generally indistinguishable from lossless for most listeners
* **Sample Rate**: 44.1 kHz is sufficient for music; higher rates mainly benefit production work
* **Equalizer Best Practices**: Start with small adjustments (2-3 dB) and use your ears. Avoid excessive boosting which can cause distortion and fatigue

### Workflow Optimization

* **Keyboard-Driven**: Learn the essential keyboard shortcuts (Spacebar, S, arrows, Ctrl+H) for hands-free control
* **Browser Layout**: Adjust the window to show both playlist and browser simultaneously for efficient library navigation
* **Queue Management**: Use "Add Below" to build a queue of upcoming tracks without restructuring your entire playlist
* **Theme for Time of Day**: Switch to dark theme for evening listening sessions to reduce eye strain
* **Early Track Advance for Parties**: Enable a 5-7 second early advance to avoid trailing dead air between tracks in background music

## Troubleshooting

### Audio Issues

**Problem**: No sound output

**Solutions**:

* Verify system volume is not muted (check both Valkyria and OS volume mixer)
* Confirm correct audio device is selected in Tools → Audio Device
* Test with a different audio file to rule out file corruption
* Ensure audio drivers are up to date
* Try restarting Valkyria

**Problem**: Crackling, popping, or distortion

**Solutions**:

* Reduce equalizer boost levels (try setting all bands to 0 dB)
* Disable compressor or reduce ratio/threshold
* Check CPU usage (high CPU load can cause audio dropouts)
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

* Ensure metadata (title/artist tags) is correct, e.g. sorting uses metadata, not filenames
* Try sorting by a different field
* Manually reorder with Move Up/Down if metadata can't be fixed

### BPM Analysis Issues

**Problem**: BPM analysis fails or returns no result

**Solutions**:

* Ensure the audio file is not corrupted. Try playing it fully
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
* WAV files don't support metadata tags. Convert to FLAC for metadata support
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

* Ensure Valkyria has write permissions to its configuration directory
* Check available disk space
* Try running as administrator
* Configuration file may be corrupted. Delete it to reset

---

**Version**: 1.0.0
**Last Updated**: January 2026

Thank you for using Valkyria!

# BPM Analysis Documentation

## Table of Contents

- [Introduction](#introduction)
- [What is BPM?](#what-is-bpm)
- [How BPM is Calculated](#how-bpm-is-calculated)
- [Analysis Process](#analysis-process)
- [Using BPM Analysis](#using-bpm-analysis)
- [BPM Normalization](#bpm-normalization)
- [Technical Details](#technical-details)
- [Limitations and Accuracy](#limitations-and-accuracy)
- [Troubleshooting](#troubleshooting)

---

## Introduction

Tango Studio can automatically analyze and store the BPM (Beats Per Minute) of your music files. This enables DJ-style features such as tempo sorting, smart playlists, beat-matched transitions, and harmonic mixing.

BPM detection is powered by the industry-standard **librosa** audio analysis library, which uses sophisticated signal processing techniques to estimate tempo directly from the audio waveform.

## What is BPM?

**BPM (Beats Per Minute)** represents the musical tempo of a track — how fast the beat moves. It measures the number of quarter-note beats that occur in one minute of music.

### Key Points

- BPM is a **musical property**, not a technical audio property like bitrate or sample rate
- It must be **computed from the audio signal** itself through analysis
- Different musical genres have characteristic BPM ranges:
  - **Hip-Hop**: 70-110 BPM
  - **House**: 120-130 BPM
  - **Techno**: 125-135 BPM
  - **Drum & Bass**: 160-180 BPM
  - **Dubstep**: 140 BPM (half-time feel at 70 BPM)

### BPM vs. Bitrate

It's important to distinguish BPM from audio quality metrics:

| Property | Measures | Typical Values |
|----------|----------|----------------|
| **BPM** | Musical tempo (speed of the beat) | 80-180 BPM |
| **kbps** | Audio encoding quality (file size/quality) | 128-320 kbps |

BPM is independent of audio quality — a high-quality FLAC file and a low-quality MP3 of the same song will have identical BPM values.

## How BPM is Calculated

Tango Studio uses the **librosa** audio analysis library to estimate BPM directly from the sound waveform. This is the same library used by researchers, music information retrieval systems, and professional audio analysis tools.

### The Challenge

Tempo detection is computationally complex because:

1. **Multiple interpretations** - A 140 BPM track could be perceived as 70 BPM (half-time) or 280 BPM (double-time)
2. **Genre variations** - Different musical styles emphasize different rhythmic elements
3. **Complex rhythms** - Syncopation, polyrhythms, and tempo changes complicate analysis
4. **Audio quality** - Compressed audio, noise, and reverb can obscure rhythmic patterns

### Librosa's Approach

Librosa uses a multi-stage process that analyzes the audio signal in both the time and frequency domains to identify repeating rhythmic patterns that correspond to the musical beat.

## Analysis Process

The BPM detection algorithm follows these steps:

### 1. Audio Decoding

**What Happens**: The audio file is decoded into a mono waveform at a fixed sample rate (typically 22.05 kHz).

**Why Mono?**: Tempo is a monophonic property — it doesn't vary between left and right channels. Converting to mono reduces computational complexity by half.

**MP3 Optimization**: For MP3 files, a short segment is first decoded using FFmpeg to ensure reliable analysis. This pre-decode step helps avoid artifacts from VBR (Variable Bit Rate) encoding.

**Technical Detail**: Downsampling to 22.05 kHz is sufficient for tempo detection because rhythmic information exists primarily in lower frequency bands (below 10 kHz).

### 2. Onset Strength Detection

**What Happens**: Librosa computes an **onset strength envelope** from the waveform. This is a time-series representation of how "energetic" or "punchy" the audio is at each moment.

**What are Onsets?**: Onsets are moments where musical energy suddenly increases — drum hits, bass kicks, snare claps, piano attacks, etc. These are the rhythmic "events" that define the beat.

**Processing**:
- The audio is divided into short frames (typically 23 ms each)
- Each frame is analyzed with a Mel-frequency spectrogram
- Spectral flux (energy change between consecutive frames) is computed
- Result: A curve showing where rhythmic energy peaks occur

**Example**: In a typical house track, the onset envelope shows clear peaks on each kick drum hit (every beat) and snare hit (backbeat).

### 3. Tempogram Analysis

**What Happens**: A **tempogram** is generated from the onset envelope. The tempogram is a 2D representation showing how strong different tempo hypotheses are over time.

**How It Works**:
- A bank of comb filters is applied to the onset envelope
- Each filter is tuned to a specific tempo (e.g., 90 BPM, 120 BPM, 140 BPM)
- Filters resonate (give high output) when the onset pattern matches their tempo
- Result: A time-frequency representation where bright regions indicate strong tempo evidence

**Visualization**: If you could see a tempogram, you'd see horizontal "stripes" at BPM values where the music has consistent rhythm.

### 4. Global Tempo Estimation

**What Happens**: The strongest rhythmic periodicity is selected from the tempogram and converted into BPM.

**Process**:
- The tempogram is averaged across time to get a single tempo strength curve
- The peak in this curve corresponds to the most likely tempo
- This tempo (in Hz) is converted to BPM
- Secondary peaks are analyzed to detect tempo changes or alternative interpretations

**Confidence**: Librosa also computes a confidence score based on how sharp and isolated the peak is. Tracks with clear, steady beats produce high confidence; tracks with tempo changes or weak beats produce lower confidence.

### 5. Optional Tempo Normalization

**What Happens**: Tango Studio can optionally normalize the raw tempo into a musically perceived BPM range.

**The Problem**: Algorithms often produce "correct but perceptually wrong" results:
- **Half-time**: A 140 BPM track detected as 70 BPM
- **Double-time**: An 80 BPM track detected as 160 BPM

**The Solution**: Normalization applies musical heuristics to adjust BPM values into the expected range (typically 80-180 BPM for most music).

**Control**: Normalization is controlled by user preference and can be disabled to expose the raw algorithm output.

### 6. Metadata Storage

**What Happens**: The resulting BPM value is written back into the audio file's metadata using the **Mutagen** library.

**Storage Format**:
- BPM is stored in the standard "BPM" ID3 tag (MP3), Vorbis comment (OGG/FLAC), or iTunes metadata (M4A)
- Values are always stored as integers (rounded to nearest whole number)
- **Raw values are stored** — normalization is only applied for display, not storage

**Caching**: Once analyzed, the BPM is embedded in the file and doesn't need to be recomputed. It will be instantly available on next load.

**Portability**: Saved BPM values are readable by other music software (iTunes, Traktor, Rekordbox, Serato, foobar2000, MusicBee, etc.).

## Using BPM Analysis

### Quick Start

1. **Load a track** - Play or select a track in the playlist
2. **Start analysis** - Click the "Analyze BPM" button in the status bar
3. **Wait for completion** - The button shows "Analyzing..." and becomes disabled
4. **Review result** - The detected BPM is displayed in the status bar and track metadata
5. **Save to file** - Click "Save BPM" to write the value permanently to the file metadata

### Analysis Time

Typical analysis times (on modern CPU):

| Track Length | Analysis Time |
|--------------|---------------|
| 3 minutes | 5-10 seconds |
| 5 minutes | 8-15 seconds |
| 10 minutes | 15-30 seconds |
| 30 minutes | 1-2 minutes |

Analysis is CPU-intensive. For best results, analyze during idle time rather than while gaming, video editing, or running other CPU-heavy tasks.

### Batch Processing

For large libraries:

1. **Prepare a playlist** - Add all tracks you want to analyze
2. **Analyze one by one** - Work through the playlist, analyzing each track
3. **Save progress** - BPM is saved to file immediately, so you can stop and resume anytime
4. **Verify results** - Enable the BPM column in playlist view to see all values at once

**Future Enhancement**: Automatic batch processing may be added in a future update.

### Viewing BPM Values

BPM is displayed in multiple locations:

- **Status Bar** - Shows BPM of currently playing track
- **Playlist View** - Optional BPM column (enable in preferences)
- **Track Information** - Full metadata window (Ctrl+I)
- **File Metadata** - Readable by tag editors and other music software

## BPM Normalization

### The Half-Time / Double-Time Problem

Tempo detection algorithms face an ambiguity: given a repeating rhythm, is the "beat" the fastest pulse, or a slower pulse that groups multiple fast events?

**Example**: A drum & bass track at 174 BPM has:
- **High-hat** hits every 87 BPM (half-time)
- **Snare** hits every 87 BPM (on the backbeat)
- **Kick drum** patterns at 174 BPM

An algorithm might detect 87 BPM (following the snare) even though DJs and dancers perceive 174 BPM (following the kick).

### How Normalization Works

When enabled, normalization applies these rules:

1. **Too Slow** - If detected BPM < 80, multiply by 2 (or 4 if still < 80)
2. **Too Fast** - If detected BPM > 180, divide by 2 (or 4 if still > 180)
3. **Target Range** - Aim for 80-180 BPM, the perceptually typical tempo range

### Normalization Settings

**Enable in Preferences**:
- **Enabled (Default)** - BPM values are automatically adjusted to match human-perceived tempo. Results will match professional DJ software (Traktor, Rekordbox, Serato).
- **Disabled** - Shows raw, unprocessed BPM values from librosa. Useful for academic analysis or debugging.

### Important Notes

- **Display Only** - Normalization only affects what you see. The raw value is always saved to the file.
- **Manual Override** - You can manually edit BPM values if the algorithm gets it wrong
- **Genre Specific** - Some genres (jazz, classical, experimental) may benefit from disabled normalization

## Technical Details

### Audio Processing Pipeline

```
Audio File (MP3/FLAC/WAV/etc.)
    ↓
FFmpeg Decode → PCM Audio (22.05 kHz, Mono)
    ↓
Mel-Spectrogram → Frequency-Time Representation
    ↓
Spectral Flux → Onset Strength Envelope
    ↓
Autocorrelation → Tempogram (Tempo × Time)
    ↓
Peak Detection → BPM Estimation
    ↓
Optional Normalization → Display BPM
    ↓
Mutagen → Save to File Metadata
```

### Librosa Configuration

Tango Studio uses librosa with these parameters:

- **Sample Rate**: 22,050 Hz (sufficient for tempo detection)
- **Hop Length**: 512 samples (~23 ms frames at 22.05 kHz)
- **Win Length**: 2048 samples (analysis window size)
- **Tempo Range**: 30-300 BPM search space
- **Onset Method**: Spectral flux with adaptive thresholding

### Accuracy and Confidence

Librosa provides a confidence score alongside the BPM estimate:

| Confidence | Interpretation | Typical Tracks |
|------------|----------------|----------------|
| **High (>0.8)** | Strong, unambiguous tempo | Electronic dance music, steady rock/pop |
| **Medium (0.5-0.8)** | Clear tempo with some ambiguity | Jazz with swing, tracks with tempo changes |
| **Low (<0.5)** | Weak or inconsistent tempo | Ambient, classical, experimental, rubato passages |

**Note**: Tango Studio currently doesn't expose the confidence score in the UI, but it's used internally to validate results.

## Limitations and Accuracy

### When BPM Analysis Works Well

- **Electronic Dance Music** - House, techno, trance, drum & bass: typically 95%+ accurate
- **Pop and Rock** - Steady 4/4 time signatures with clear drums: typically 90%+ accurate
- **Hip-Hop** - Clear beat patterns: typically 85%+ accurate

### When BPM Analysis May Struggle

| Challenge | Example Genres | Workaround |
|-----------|----------------|------------|
| **Tempo Changes** | Classical, progressive rock | Use average tempo or manual entry |
| **Rubato** | Romantic era piano, ballads | Manual BPM entry based on perceived average |
| **Polyrhythms** | African drumming, jazz fusion | May detect a different pulse than intended |
| **Weak Percussion** | Ambient, atmospheric electronic | Algorithm may lock onto subtle rhythmic elements |
| **Half-time Grooves** | Dubstep, trap, downtempo | Enable normalization or manually adjust ×2 |

### Expected Accuracy

Based on librosa benchmarks and real-world testing:

- **Exact BPM**: 70-85% of tracks (within 1 BPM of human reference)
- **Close BPM**: 90-95% of tracks (within 2-3 BPM or off by factor of 2)
- **Usable for DJ mixing**: 95%+ after normalization and spot-checking

### Manual Correction

If the detected BPM is incorrect:

1. **Try normalization** - Enable/disable normalization preference and re-analyze
2. **Manual multiplication** - If result is half or double the correct value, multiply/divide by 2
3. **Reference tempo** - Use an online BPM counter or tap tempo tool for ground truth
4. **Edit metadata** - Use a tag editor (Mp3tag, MusicBrainz Picard) to manually set the BPM field

## Troubleshooting

### Analysis Fails or Returns No Result

**Causes**:
- File corruption or unreadable format
- Insufficient CPU resources
- Extremely long track (>30 minutes)

**Solutions**:
- Verify file plays correctly in the player
- Close other CPU-intensive applications
- Try analyzing a short test track first
- Check file format is supported (MP3, FLAC, WAV, OGG, M4A)

### BPM Result is Clearly Wrong

**Causes**:
- Half-time or double-time detection (common with drum & bass, dubstep, some hip-hop)
- Tempo changes during the track
- Complex polyrhythmic patterns

**Solutions**:
- Toggle BPM normalization in Preferences
- Multiply or divide result by 2 manually
- Compare with online BPM databases (MusicBrainz, Discogs)
- Use a manual tap tempo tool for verification

### Cannot Save BPM to File

**Causes**:
- File is read-only (check permissions)
- File format doesn't support metadata (rare with modern formats)
- File is on a read-only filesystem (CD, locked network drive)

**Solutions**:
- Right-click file → Properties → Uncheck "Read-only"
- Copy file to a writable location (local hard drive)
- Ensure you have write permissions to the file's directory
- For WAV files, consider converting to FLAC (WAV has limited metadata support)

### Analysis is Very Slow

**Causes**:
- High CPU usage from other applications
- Very long audio file (>10 minutes)
- Slow or fragmented hard drive

**Solutions**:
- Close background applications
- Analyze shorter tracks first
- Consider analyzing during idle time (overnight for large libraries)
- Upgrade to an SSD if using mechanical hard drive

### BPM Doesn't Match Professional DJ Software

**Causes**:
- Different normalization strategies
- Different analysis algorithms
- Tango Studio stores raw values, other software may display normalized values

**Solutions**:
- Enable BPM normalization in Tango Studio preferences
- Check if other software has normalization settings
- Use the same BPM field (some software uses "TBPM" vs "BPM" tags)
- Manually verify with tap tempo if needed

---

## Further Reading

### Academic Background

BPM detection is an active area of research in Music Information Retrieval (MIR). For deeper understanding:

- **librosa Documentation**: https://librosa.org/doc/latest/generated/librosa.beat.beat_track.html
- **MIREX Tempo Evaluation**: Music Information Retrieval Evaluation eXchange annual competition
- **Ellis, D. P. W. (2007)**: "Beat Tracking by Dynamic Programming" - foundational algorithm

### Related Features

- **Beatmatching**: Future updates may include automatic crossfade alignment based on BPM
- **Tempo Visualization**: Future updates may display BPM-synchronized waveform grid lines
- **Key Detection**: Harmonic mixing (key detection) is a planned feature for future releases

---

**Thank you for using Tango Studio's BPM Analysis!**

For questions or issues, consult the main User Guide or contact support.
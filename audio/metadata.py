"""
Metadata handling module for audio files.
Consolidates all metadata extraction, manipulation, and display logic.
"""

from mutagen import File as MutagenFile
from mutagen.id3 import APIC, GEOB, ID3, TXXX, TBPM, ID3NoHeaderError
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover

import shutil, tempfile, subprocess, math, os, glob, io
from PIL import Image
import librosa
import numpy as np
from math import log

class MetadataExtractor:
    """Handles extraction and manipulation of audio file metadata."""

    def __init__(self):
        self._cache = {}
        self._bpm_listeners = []

    def get_metadata(self, filepath):
        """
        Get metadata for a file, using cache for performance.

        Args:
            filepath (str): Path to the audio file

        Returns:
            dict: Dictionary containing metadata fields (title, artist, album, duration, etc.)
        """
        if filepath in self._cache:
            return self._cache[filepath]

        metadata = {}
        try:
            audio = MutagenFile(filepath, easy=True)
            if audio:
                # Extract basic metadata
                metadata["title"] = str(audio.get("title", [os.path.basename(filepath)])[0])
                metadata["artist"] = str(audio.get("artist", ["Unknown Artist"])[0])
                metadata["album"] = str(audio.get("album", ["Unknown Album"])[0])

                # Format duration
                duration = audio.info.length if hasattr(audio.info, 'length') else 0
                if duration:
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    metadata["duration"] = f"{minutes:02d}:{seconds:02d}"
                    metadata["duration_s"] = int(duration)  # Keep seconds for calculations
                else:
                    metadata["duration"] = ""
                    metadata["duration_s"] = None

                # Bitrate (some formats)
                bitrate = None
                try:
                    if hasattr(audio.info, 'bitrate') and audio.info.bitrate:
                        # mutagen gives bits per second for many formats
                        bitrate = int(audio.info.bitrate // 1000)
                except Exception:
                    bitrate = None
                metadata["bitrate"] = bitrate

                # Format: mime or extension
                fmt = None
                try:
                    # Try to infer format from class name or filename extension
                    class_name = audio.__class__.__name__.lower()
                    if "mp3" in class_name:
                        fmt = "mp3"
                    elif "flac" in class_name:
                        fmt = "flac"
                    elif "ogg" in class_name:
                        fmt = "ogg"
                    elif "m4a" in class_name or "mp4" in class_name:
                        fmt = "m4a"
                    else:
                        # fallback to file extension
                        fmt = os.path.splitext(filepath)[1].lstrip(".").lower()
                except Exception:
                    fmt = None
                metadata["format"] = fmt
                # Attempt to extract BPM from common tags/frames
                bpm = None
                try:
                    # Try easy tags first (common for vorbis/flac/mp4 easy tags)
                    if audio and hasattr(audio, 'get'):
                        for k in ('bpm', 'BPM'):
                            v = audio.get(k)
                            if v:
                                try:
                                    bpm = float(v[0])
                                    break
                                except Exception:
                                    try:
                                        bpm = float(v)
                                        break
                                    except Exception:
                                        pass

                    # Fallback to raw mutagen tags for ID3/MP4 specific frames
                    if bpm is None:
                        raw = MutagenFile(filepath)
                        if raw is not None and hasattr(raw, 'tags') and raw.tags is not None:
                            # ID3 TBPM frame for MP3
                            try:
                                if 'TBPM' in raw.tags:
                                    val = raw.tags.get('TBPM')
                                    # mutagen may return a FrameList or text
                                    val_str = str(val)
                                    bpm = float(val_str)
                            except Exception:
                                pass

                            # MP4 tempo tag 'tmpo'
                            if bpm is None:
                                try:
                                    if 'tmpo' in raw.tags:
                                        val = raw.tags.get('tmpo')
                                        bpm = float(val)
                                except Exception:
                                    pass
                except Exception:
                    bpm = None

                metadata['bpm'] = bpm
        except Exception:
            # Fallback to filename if metadata extraction fails
            metadata = {
                "title": os.path.basename(filepath),
                "artist": "Unknown Artist",
                "album": "Unknown Album",
                "duration": "",
                "duration_s": None,
                "bitrate": None,
                "bpm": None,
                "format": None
            }

        # Cache the result
        self._cache[filepath] = metadata
        return metadata

    def get_display_title(self, file_path):
        """
        Get the display title for a file.
        Returns "Title — Artist" if both tags exist, "Title" if only title exists,
        or the filename if no tags are found.

        Args:
            file_path (str): Path to the audio file

        Returns:
            str: Display title string
        """
        try:
            audio = MutagenFile(file_path, easy=True)
            if audio and 'title' in audio:
                title = audio['title'][0]
                if 'artist' in audio:
                    artist = audio['artist'][0]
                    return f"{title} — {artist}"
                return title
        except Exception:
            pass

        return os.path.basename(file_path)

    def get_file_info(self, file_path):
        """
        Extract comprehensive file information including technical details.

        Args:
            file_path (str): Path to the audio file

        Returns:
            dict: Dictionary containing file information (path, size, format, duration, bitrate, etc.)
        """
        info = {
            'path': file_path,
            'filename': os.path.basename(file_path),
            'size': 0,
            'format': '',
            'duration': 0,
            'bitrate': 0,
            'sample_rate': 0,
            'channels': 0,
            'codec': '',
            'metadata': {}
        }

        try:
            # Get file size
            info['size'] = os.path.getsize(file_path)

            # Load with mutagen
            audio = MutagenFile(file_path, easy=True)
            if audio is None:
                return info

            # Get audio info
            if hasattr(audio, 'info'):
                audio_info = audio.info

                # Duration
                if hasattr(audio_info, 'length'):
                    info['duration'] = int(audio_info.length)

                # Bitrate
                if hasattr(audio_info, 'bitrate'):
                    info['bitrate'] = int(audio_info.bitrate)

                # Sample rate
                if hasattr(audio_info, 'sample_rate'):
                    info['sample_rate'] = int(audio_info.sample_rate)

                # Channels
                if hasattr(audio_info, 'channels'):
                    info['channels'] = int(audio_info.channels)

            # Determine format/codec
            class_name = audio.__class__.__name__.lower()
            if 'mp3' in class_name:
                info['format'] = 'MP3'
                info['codec'] = 'MPEG Audio Layer 3'
            elif 'flac' in class_name:
                info['format'] = 'FLAC'
                info['codec'] = 'Free Lossless Audio Codec'
            elif 'ogg' in class_name or 'vorbis' in class_name:
                info['format'] = 'OGG'
                info['codec'] = 'Vorbis'
            elif 'm4a' in class_name or 'mp4' in class_name or 'aac' in class_name:
                info['format'] = 'M4A/AAC'
                info['codec'] = 'Advanced Audio Coding'
            elif 'wave' in class_name or 'wav' in class_name:
                info['format'] = 'WAV'
                info['codec'] = 'PCM'
            else:
                ext = os.path.splitext(file_path)[1].upper().lstrip('.')
                info['format'] = ext
                info['codec'] = 'Unknown'

            # Get metadata tags
            if audio.tags:
                for key in audio.keys():
                    value = audio[key]
                    if isinstance(value, list) and len(value) > 0:
                        info['metadata'][key] = value[0]
                    else:
                        info['metadata'][key] = str(value)

            # Also include parsed metadata such as bpm if available
            try:
                parsed_meta = self.get_metadata(file_path)
                if parsed_meta and 'bpm' in parsed_meta:
                    info['metadata']['bpm'] = parsed_meta.get('bpm')
            except Exception:
                pass
        except Exception:
            pass

        return info

    def save_metadata(self, file_path, metadata_dict):
        """
        Save metadata to an audio file.

        Args:
            file_path (str): Path to the audio file
            metadata_dict (dict): Dictionary of metadata to save

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            audio = MutagenFile(file_path, easy=True)
            if audio is None:
                return False

            # Update tags from dictionary
            for key, value in metadata_dict.items():
                val = str(value).strip()
                if val:
                    audio[key] = [val]
                else:
                    # Remove tag if empty
                    if key in audio:
                        del audio[key]

            audio.save()
            # Clear cache for this file to force refresh
            if file_path in self._cache:
                del self._cache[file_path]
            return True

        except Exception:
            return False

    def update_cache(self, filepath):
        """
        Update metadata cache for a specific file.

        Args:
            filepath (str): Path to the audio file
        """
        if filepath in self._cache:
            del self._cache[filepath]
        self.get_metadata(filepath)

    def register_bpm_listener(self, callback):
        """Register a callback to be notified when BPM is updated for a file.

        Callback will be called as callback(filepath).
        """
        if callback not in self._bpm_listeners:
            self._bpm_listeners.append(callback)

    def unregister_bpm_listener(self, callback):
        """Unregister a BPM listener callback."""
        try:
            self._bpm_listeners.remove(callback)
        except ValueError:
            pass

    def _notify_bpm_listeners(self, filepath):
        for cb in list(self._bpm_listeners):
            try:
                cb(filepath)
            except Exception:
                pass

    def get_booklet_images(self, filepath, include_folder_images=True):
        """
        Extract booklet/liner-note images from audio file metadata.

        Args:
            filepath (str): Path to the audio file
            include_folder_images (bool): If True, also look for images in the same folder

        Returns:
            list: List of tuples containing (image_data, description, image_type)
        """
        booklet_images = []

        try:
            audio = MutagenFile(filepath)
            if audio is None:
                return booklet_images

            # Handle MP3 files (ID3 tags)
            if hasattr(audio, 'tags') and audio.tags is not None:
                # Extract APIC frames (attached pictures)
                try:
                    apic_frames = [audio.tags[key] for key in audio.tags.keys() if key.startswith('APIC')]
                except Exception:
                    apic_frames = []

                for frame in apic_frames:
                    try:
                        pic_type = frame.type
                        description = frame.desc or "Image"

                        # Skip empty images
                        if not frame.data or len(frame.data) == 0:
                            continue

                        # Verify the image is valid
                        try:
                            img = Image.open(io.BytesIO(frame.data))
                            img.verify()
                        except Exception:
                            continue

                        # Convert enum to int if needed
                        pic_type_int = int(pic_type) if hasattr(pic_type, 'value') else pic_type

                        # Include all image types
                        booklet_images.append((frame.data, description, f"APIC Type {pic_type_int}"))
                    except (AttributeError, KeyError, Exception):
                        continue

                # Extract GEOB frames (general encapsulated objects)
                try:
                    geob_frames = [audio.tags[key] for key in audio.tags.keys() if key.startswith('GEOB')]
                except Exception:
                    geob_frames = []

                for frame in geob_frames:
                    try:
                        image_data = frame.data

                        # Skip empty data
                        if not image_data or len(image_data) == 0:
                            continue

                        # Verify it's a valid image
                        img = Image.open(io.BytesIO(image_data))
                        img.verify()
                        description = frame.desc or "Embedded Image"
                        booklet_images.append((image_data, description, "GEOB Image"))
                    except Exception:
                        # Not a valid image, skip
                        continue

            # Handle FLAC files
            if isinstance(audio, FLAC):
                try:
                    pictures = audio.pictures if hasattr(audio, 'pictures') else []
                except Exception:
                    pictures = []

                for picture in pictures:
                    try:
                        # Skip empty images
                        if not picture.data or len(picture.data) == 0:
                            continue

                        # Verify the image is valid
                        try:
                            img = Image.open(io.BytesIO(picture.data))
                            img.verify()
                        except Exception:
                            continue

                        pic_type = picture.type
                        description = picture.desc or "Image"

                        # Convert enum to int if needed
                        pic_type_int = int(pic_type) if hasattr(pic_type, 'value') else pic_type

                        # Include all image types
                        booklet_images.append((picture.data, description, f"FLAC Picture Type {pic_type_int}"))
                    except (AttributeError, Exception):
                        continue

            # Handle MP4/M4A files
            elif isinstance(audio, MP4):
                try:
                    if audio.tags and 'covr' in audio.tags:
                        cover_list = audio.tags['covr']
                        # MP4Cover objects need to be converted to bytes
                        for i, cover in enumerate(cover_list):
                            try:
                                # Convert MP4Cover to bytes if needed
                                if isinstance(cover, MP4Cover):
                                    image_data = bytes(cover)
                                else:
                                    image_data = cover

                                # Skip empty images
                                if not image_data or len(image_data) == 0:
                                    continue

                                # Verify the image is valid
                                try:
                                    img = Image.open(io.BytesIO(image_data))
                                    img.verify()
                                except Exception:
                                    continue

                                # Include all covers
                                booklet_images.append((image_data, f"Cover Art {i+1}", "MP4 Cover"))
                            except Exception:
                                continue
                except Exception:
                    pass

        except Exception:
            pass

        if include_folder_images:
            try:
                folder = os.path.dirname(filepath)

                # Common names VLC looks for
                image_names = ['folder.jpg', 'folder.png', 'cover.jpg', 'cover.png',
                            'front.jpg', 'front.png', 'album.jpg', 'album.png',
                            'albumart.jpg', 'albumart.png']

                for img_name in image_names:
                    img_path = os.path.join(folder, img_name)
                    if os.path.exists(img_path):
                        try:
                            with open(img_path, 'rb') as f:
                                img_data = f.read()
                            if img_data and len(img_data) > 0:
                                # Verify the image is valid
                                try:
                                    img = Image.open(io.BytesIO(img_data))
                                    img.verify()
                                    booklet_images.append((img_data, img_name, "Folder Image"))
                                except Exception:
                                    # Skip corrupted images
                                    pass
                        except Exception:
                            pass

                # Also check for any jpg/png files in the folder
                for ext in ['*.jpg', '*.jpeg', '*.png']:
                    for img_file in glob.glob(os.path.join(folder, ext)):
                        img_name = os.path.basename(img_file)
                        # Skip if already added
                        if not any(b[1] == img_name for b in booklet_images):
                            try:
                                with open(img_file, 'rb') as f:
                                    img_data = f.read()
                                if img_data and len(img_data) > 0:
                                    # Verify the image is valid
                                    try:
                                        img = Image.open(io.BytesIO(img_data))
                                        img.verify()
                                        booklet_images.append((img_data, img_name, "Folder Image"))
                                    except Exception:
                                        # Skip corrupted images
                                        pass
                            except Exception:
                                continue

            except Exception:
                pass

        return booklet_images

def get_best_artwork(filepath):
    """
    Get the best artwork image for a file using fallback hierarchy.

    Args:
        filepath (str): Path to the audio file

    Returns:
        bytes: Image data for the best artwork, or None if no artwork found
    """
    try:
        # Get all available images using the comprehensive extraction function
        images = metadata_extractor.get_booklet_images(filepath, include_folder_images=True)

        if not images:
            return None

        # Priority order for artwork selection
        # 1. Front cover (APIC type 3) from embedded metadata
        # 2. Any embedded artwork (APIC, FLAC Picture, MP4 Cover, GEOB Image)
        # 3. Folder artwork with priority names (cover.jpg, album.jpg, etc.)
        # 4. Any other image (including other folder images)

        # First, look for front cover (type 3) in embedded images
        for img_data, description, img_type in images:
            if "APIC" in img_type and "Type 3" in img_type:
                return img_data

        # Then look for any embedded artwork
        for img_data, description, img_type in images:
            if any(embedded_type in img_type for embedded_type in ["APIC", "FLAC Picture", "MP4 Cover", "GEOB Image"]):
                return img_data

        # Then look for folder artwork with priority names
        priority_names = ['cover.jpg', 'cover.png', 'front.jpg', 'front.png',
                        'album.jpg', 'album.png', 'albumart.jpg', 'albumart.png',
                        'folder.jpg', 'folder.png']

        for img_data, description, img_type in images:
            if "Folder Image" in img_type:
                desc_lower = description.lower()
                if any(name in desc_lower for name in priority_names):
                    return img_data

        # Then look for any folder image
        for img_data, description, img_type in images:
            if "Folder Image" in img_type:
                return img_data

        # Finally, return any available image
        if images:
            return images[0][0]

    except Exception as e:
        pass

    return None

def get_display_bpm(bpm):
    """Get BPM value formatted for display according to current preference.

    Args:
        bpm: Raw BPM value (int or float) or None

    Returns:
        Formatted BPM string for display, or empty string if bpm is None
    """
    if bpm is None:
        return ""

    try:
        bpm_float = float(bpm)
    except (ValueError, TypeError):
        return ""

    if not math.isfinite(bpm_float) or bpm_float <= 0:
        return ""

    # Apply normalization based on preference
    display_bpm = normalize_bpm(bpm_float)
    return str(display_bpm) if display_bpm is not None else ""

def analyze_bpm(filepath, sr=22050, duration=60):
    try:
        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.mp3' and shutil.which('ffmpeg'):
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmpname = tmp.name
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', filepath,
                    '-t', str(duration), '-ar', str(sr), '-ac', '1', tmpname
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                y, sr_used = librosa.load(tmpname, sr=sr, mono=True)
            finally:
                os.unlink(tmpname)
        else:
            y, sr_used = librosa.load(filepath, sr=sr, mono=True, duration=duration)

        return dj_bpm_estimate(y, sr_used)

    except Exception as e:
        print("BPM error:", e)
        return None

def normalize_bpm(bpm):
    try:
        bpm = float(bpm)
    except Exception:
        print("Failed normalization")
        return None

    if not math.isfinite(bpm) or bpm <= 0:
        print("Invalid BPM value")
        return None

    # Behavior depends on BPM_PREFERENCE: 'perceived' folds into 50-100,
    # 'raw' returns the detected tempo without octave-folding.
    if BPM_PREFERENCE == 'raw':
        return int(round(bpm))

    # Default: 'perceived' - fold into 50-100 BPM range
    while bpm > 100:
        bpm /= 2.0
    while bpm < 50:
        bpm *= 2.0

    return int(round(bpm))

def dj_bpm_estimate(y, sr):
    # Guard against empty audio
    if y is None or len(y) == 0:
        print("BPM error: empty audio buffer")
        return None

    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    except Exception as e:
        print("BPM error computing onset envelope:", e)
        onset_env = None

    # Try tempogram-based global tempo estimate first
    try:
        if onset_env is None or len(onset_env) == 0:
            raise RuntimeError("empty onset envelope")

        tg = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
        if tg is None or tg.size == 0:
            raise RuntimeError("empty tempogram")

        # Global tempo profile
        tempo_freqs = librosa.tempo_frequencies(tg.shape[0], sr=sr)
        if tempo_freqs is None or len(tempo_freqs) == 0:
            raise RuntimeError("no tempo frequencies")

        avg_tg = np.mean(tg, axis=1)
        if avg_tg is None or len(avg_tg) == 0 or np.all(np.isnan(avg_tg)):
            raise RuntimeError("invalid tempogram energy")

        idx = int(np.nanargmax(avg_tg))
        if idx < 0 or idx >= len(tempo_freqs):
            raise RuntimeError("tempo index out of range")

        bpm = float(tempo_freqs[idx])
        if not math.isfinite(bpm) or bpm <= 0:
            raise RuntimeError("non-finite tempo from tempogram")

        return bpm

    except Exception as e:
        # Fallback to beat_track which is more robust in many cases
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            if tempo is None or not math.isfinite(tempo) or tempo <= 0:
                print("BPM fallback beat_track failed:", tempo)
                return None
            return float(tempo)
        except Exception as e2:
            print("BPM fallback failed:", e2)
            return None

def write_bpm(filepath, bpm):
    """Write BPM tag back into the audio file using mutagen when possible.

    Returns True on success, False otherwise.
    """
    try:
        if bpm is None:
            return False
        # Use bpm value as-is without normalization
        bpm_val = str(bpm)

        raw = MutagenFile(filepath)
        # MP3 (ID3 TBPM)
        try:
            if filepath.lower().endswith('.mp3'):
                try:
                    id3 = ID3(filepath)
                except ID3NoHeaderError:
                    id3 = ID3()
                # remove existing TBPM frames
                try:
                    id3.delall('TBPM')
                except Exception:
                    pass
                id3.add(TBPM(encoding=3, text=str(bpm_val)))
                id3.save(filepath)
                try:
                    try:
                        metadata_extractor.update_cache(filepath)
                    except Exception:
                        pass
                    metadata_extractor._notify_bpm_listeners(filepath)
                except Exception:
                    pass
                return True
        except Exception:
            pass

        # MP4/M4A tempo tag 'tmpo'
        try:
            if isinstance(raw, MP4) or filepath.lower().endswith(('.m4a', '.mp4')):
                mp4 = MP4(filepath)
                tags = mp4.tags or {}
                tags['tmpo'] = [bpm_val]
                mp4.tags = tags
                mp4.save()
                try:
                    try:
                        metadata_extractor.update_cache(filepath)
                    except Exception:
                        pass
                    metadata_extractor._notify_bpm_listeners(filepath)
                except Exception:
                    pass
                return True
        except Exception:
            pass

        # FLAC Vorbis comment
        try:
            if isinstance(raw, FLAC) or filepath.lower().endswith('.flac'):
                fl = FLAC(filepath)
                fl['bpm'] = str(bpm_val)
                fl.save()
                try:
                    try:
                        metadata_extractor.update_cache(filepath)
                    except Exception:
                        pass
                    metadata_extractor._notify_bpm_listeners(filepath)
                except Exception:
                    pass
                return True
        except Exception:
            pass

        # Generic easy tag fallback
        try:
            easy = MutagenFile(filepath, easy=True)
            if easy is not None:
                easy['bpm'] = [str(bpm_val)]
                easy.save()
                try:
                    try:
                        metadata_extractor.update_cache(filepath)
                    except Exception:
                        pass
                    metadata_extractor._notify_bpm_listeners(filepath)
                except Exception:
                    pass
                return True
        except Exception:
            pass

    except Exception:
        pass
    return False


# Global instance for use across the application
metadata_extractor = MetadataExtractor()

# BPM preference: 'perceived' (50-100) or 'raw' (no octave folding)
BPM_PREFERENCE = 'perceived'

def set_bpm_preference(mode: str):
    global BPM_PREFERENCE
    if mode in ('perceived', 'raw'):
        BPM_PREFERENCE = mode
    else:
        BPM_PREFERENCE = 'perceived'

# Convenience functions for backward compatibility
def get_metadata(filepath):
    """Get metadata for a file using the global extractor."""
    return metadata_extractor.get_metadata(filepath)

def get_display_title(file_path):
    """Get display title for a file using the global extractor."""
    return metadata_extractor.get_display_title(file_path)

def get_file_info(file_path):
    """Get comprehensive file info using the global extractor."""
    return metadata_extractor.get_file_info(file_path)

def save_metadata(file_path, metadata_dict):
    """Save metadata using the global extractor."""
    return metadata_extractor.save_metadata(file_path, metadata_dict)

def get_booklet_images(filepath):
    """Get booklet images using the global extractor."""
    return metadata_extractor.get_booklet_images(filepath)

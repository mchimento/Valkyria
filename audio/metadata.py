"""
Metadata handling module for audio files.
Consolidates all metadata extraction, manipulation, and display logic.
"""

from mutagen import File as MutagenFile
from mutagen.id3 import APIC, GEOB, ID3, TXXX, TBPM, ID3NoHeaderError
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover

import logging
import shutil, tempfile, subprocess, math, os, glob, io
from PIL import Image
import numpy as np
from math import log

logger = logging.getLogger(__name__)

# Ensure EasyID3 recognizes 'key' and 'initial_key' mapped to TKEY
try:
    from mutagen.easyid3 import EasyID3
    EasyID3.RegisterTextKey('key', 'TKEY')
    EasyID3.RegisterTextKey('initial_key', 'TKEY')
except ImportError:
    pass

class MetadataExtractor:
    """Handles extraction and manipulation of audio file metadata."""

    def __init__(self):
        self._cache = {}
        self._bpm_listeners = []
        self._key_listeners = []

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
            # If easy mode returns an empty dict (no tags extracted due to non-standard ID3), try non-easy mode
            # EasyMP3 objects are dict subclasses, so check if it's empty but has audio info
            if audio is None or (hasattr(audio, 'keys') and len(audio.keys()) == 0):
                audio = MutagenFile(filepath)

            if audio:
                # Extract basic metadata
                # Try easy mode tags first (returns lists)
                try:
                    # Check if this looks like easy mode (dict-like with .get() that returns lists)
                    title_test = audio.get("title", [os.path.basename(filepath)])
                    if isinstance(title_test, list):
                        # Easy mode with valid tags
                        metadata["title"] = str(title_test[0])
                        metadata["artist"] = str(audio.get("artist", ["Unknown Artist"])[0])
                        metadata["album"] = str(audio.get("album", ["Unknown Album"])[0])
                    else:
                        # Force exception to try raw tags
                        raise AttributeError("Not easy mode format")
                except (AttributeError, TypeError, KeyError, IndexError):
                    # Not easy mode or tags missing - extract from raw ID3 tags
                    metadata["title"] = os.path.basename(filepath)
                    metadata["artist"] = "Unknown Artist"
                    metadata["album"] = "Unknown Album"

                    if hasattr(audio, 'tags') and audio.tags:
                        if 'TIT2' in audio.tags:
                            metadata["title"] = str(audio.tags['TIT2'])
                        if 'TPE1' in audio.tags:
                            metadata["artist"] = str(audio.tags['TPE1'])
                        if 'TALB' in audio.tags:
                            metadata["album"] = str(audio.tags['TALB'])

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

                # Attempt to extract Key
                key = None
                try:
                    # Try easy tags
                    if audio and hasattr(audio, 'get'):
                        for k in ('key', 'KEY', 'initial_key', 'INITIAL_KEY'):
                            v = audio.get(k)
                            if v:
                                key = str(v[0])
                                break

                    if key is None:
                        # Raw tags
                        raw = MutagenFile(filepath)
                        if raw and hasattr(raw, 'tags') and raw.tags:
                            # ID3
                            if 'TKEY' in raw.tags:
                                key = str(raw.tags['TKEY'])
                            # MP4
                            elif '----:com.apple.iTunes:KEY' in raw.tags:
                                val = raw.tags['----:com.apple.iTunes:KEY']
                                key = val[0].decode('utf-8', errors='ignore') if isinstance(val, list) else str(val)
                            elif '----:com.apple.iTunes:initial_key' in raw.tags:
                                val = raw.tags['----:com.apple.iTunes:initial_key']
                                key = val[0].decode('utf-8', errors='ignore') if isinstance(val, list) else str(val)
                except Exception:
                    pass

                metadata['key'] = key
                # Also compute Camelot notation for convenience (if key present)
                try:
                    camelot = key_to_camelot(key)
                    metadata['camelot'] = camelot
                except Exception:
                    metadata['camelot'] = None
        except Exception as e:
            logger.error(f"Failed to extract metadata from {filepath}: {e}", exc_info=True)
            # Fallback to filename if metadata extraction fails
            metadata = {
                "title": os.path.basename(filepath),
                "artist": "Unknown Artist",
                "album": "Unknown Album",
                "duration": "",
                "duration_s": None,
                "bitrate": None,
                "bpm": None,
                "key": None,
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
                if parsed_meta:
                    if 'bpm' in parsed_meta:
                        info['metadata']['bpm'] = parsed_meta.get('bpm')
                    if 'key' in parsed_meta:
                        info['metadata']['key'] = parsed_meta.get('key')
                    if 'camelot' in parsed_meta:
                        info['metadata']['camelot'] = parsed_meta.get('camelot')
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

            # Special handling for Key cleanup: ensure INITIAL_KEY is also removed for FLAC/Vorbis
            if 'key' in metadata_dict and not str(metadata_dict['key']).strip():
                # Access underlying tags if available
                if hasattr(audio, 'tags') and audio.tags:
                    # For Ogg/FLAC, keys are case-sensitive but usually uppercase
                    for variant in ['INITIAL_KEY', 'initial_key']:
                        if variant in audio.tags:
                            del audio.tags[variant]
            audio.save()
            # Clear cache for this file to force refresh
            if file_path in self._cache:
                del self._cache[file_path]
            # Notify BPM listeners if BPM is part of the saved metadata
            try:
                if 'bpm' in metadata_dict:
                    self._notify_bpm_listeners(file_path)
                if 'key' in metadata_dict:
                    self._notify_key_listeners(file_path)
            except Exception:
                pass
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

    def register_key_listener(self, callback):
        """Register a callback to be notified when Key is updated for a file.

        Callback will be called as callback(filepath).
        """
        if callback not in self._key_listeners:
            self._key_listeners.append(callback)

    def unregister_key_listener(self, callback):
        """Unregister a Key listener callback."""
        try:
            self._key_listeners.remove(callback)
        except ValueError:
            pass

    def _notify_key_listeners(self, filepath):
        for cb in list(self._key_listeners):
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

        if include_folder_images:
            try:
                folder = os.path.dirname(filepath)

                # Common cover-art file names
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


def key_to_camelot(key_str):
    """Convert a musical key string to Camelot wheel notation.

    Examples:
        'A' -> '11B' (A major is 11B)
        'Am' or 'A minor' -> '8A' (A minor is 8A)
        'C' -> '8B' (C major is 8B)

    Returns Camelot code like '8A' or '8B' or None if unrecognized.
    """
    if not key_str:
        return None

    s = str(key_str).strip()
    if s == '':
        return None

    s = s.replace('\u200b', '')  # remove zero-width spaces
    s = s.strip()

    # Detect minor/major
    lower = s.lower()
    is_minor = False
    if lower.endswith('m') and len(lower) <= 3:
        # e.g., 'Am' or 'C#m'
        root = s[:-1]
        is_minor = True
    elif 'minor' in lower:
        parts = lower.split()
        root = parts[0]
        is_minor = True
    elif 'maj' in lower or 'major' in lower:
        parts = lower.split()
        root = parts[0]
        is_minor = False
    else:
        # Assume simple notation: if trailing 'm' already handled, else check uppercase 'm' maybe
        if s[-1] in ('m', 'M') and len(s) <= 3:
            root = s[:-1]
            is_minor = True
        else:
            root = s
            is_minor = False

    root = root.strip()
    # Normalize root (capitalize letter, keep accidental)
    if len(root) == 0:
        return None
    note_letter = root[0].upper()
    accidental = ''
    if len(root) > 1:
        if root[1] in ('#', 'b', '♯', '♭'):
            accidental = root[1]

    # Map to semitone (0=C, 1=C#/Db, ... 11=B)
    note_map = {
        'C': 0, 'B#': 0,
        'C#': 1, 'Db': 1,
        'D': 2,
        'D#': 3, 'Eb': 3,
        'E': 4, 'Fb': 4,
        'F': 5, 'E#': 5,
        'F#': 6, 'Gb': 6,
        'G': 7,
        'G#': 8, 'Ab': 8,
        'A': 9,
        'A#': 10, 'Bb': 10,
        'B': 11, 'Cb': 11
    }

    # Compose key name
    root_name = note_letter + accidental
    # Try direct mapping
    if root_name in note_map:
        pc = note_map[root_name]
    else:
        # Try enharmonic flips (e.g., handle lowercase b accidentals)
        alt = root.upper().replace('♭', 'b').replace('♯', '#')
        if alt in note_map:
            pc = note_map[alt]
        else:
            # Last resort: try single letter only
            if note_letter in note_map:
                pc = note_map[note_letter]
            else:
                return None

    # Map major root pitch class to Camelot number for major mode
    major_pc_to_num = {
        0: 8,   # C
        7: 9,   # G
        2: 10,  # D
        9: 11,  # A
        4: 12,  # E
        11: 1,  # B
        6: 2,   # F#/Gb
        1: 3,   # C#/Db
        8: 4,   # Ab/G#
        3: 5,   # Eb/D#
        10: 6,  # Bb/A#
        5: 7    # F
    }

    if is_minor:
        # For minor, the Camelot number corresponds to the relative major
        # which is +3 semitones from minor root
        major_pc = (pc + 3) % 12
        num = major_pc_to_num.get(major_pc)
        if num is None:
            return None
        return f"{num}A"
    else:
        num = major_pc_to_num.get(pc)
        if num is None:
            return None
        return f"{num}B"

def analyze_bpm(filepath, sr=22050, duration=60):
    try:
        # Prefer soundfile (libsndfile) for reads to avoid pulling in audioread
        # and its deprecated modules. If soundfile fails for the given format
        # (e.g., MP3), try an ffmpeg-decoded temporary WAV, and only as a last
        # resort fall back to librosa.load which may use audioread.
        ext = os.path.splitext(filepath)[1].lower()
        try:
            import soundfile as sf
            try:
                # Read up to `duration` seconds to limit work
                frames = int(sr * duration)
                data, sr_used = sf.read(filepath, dtype='float32', always_2d=False)
                # If duration limit is requested, truncate
                if duration is not None and sr_used and len(data) > frames:
                    data = data[:frames]
                y = data
                if y.ndim > 1:
                    y = y.mean(axis=1)
            except Exception:
                raise
        except Exception:
            # If direct soundfile read fails, try ffmpeg decode for MP3/other
            if shutil.which('ffmpeg'):
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    tmpname = tmp.name
                try:
                    # Prevent console window on Windows (PyInstaller)
                    import sys
                    if sys.platform == 'win32':
                        creationflags = subprocess.CREATE_NO_WINDOW
                    else:
                        creationflags = 0
                    subprocess.run([
                        'ffmpeg', '-y', '-i', filepath,
                        '-t', str(duration), '-ar', str(sr), '-ac', '1', tmpname
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
                    # Read decoded WAV with soundfile if possible
                    try:
                        import soundfile as sf2
                        y, sr_used = sf2.read(tmpname, dtype='float32', always_2d=False)
                        if y.ndim > 1:
                            y = y.mean(axis=1)
                    except Exception:
                        # Last resort, use librosa to load temp WAV
                        import librosa
                        y, sr_used = librosa.load(tmpname, sr=sr, mono=True)
                finally:
                    try:
                        os.unlink(tmpname)
                    except Exception:
                        pass
            else:
                # As a last resort, use librosa.load which may use audioread
                import librosa
                y, sr_used = librosa.load(filepath, sr=sr, mono=True, duration=duration)

        # Ensure audio is at requested sample rate for analysis — resample if needed
        try:
            sr_used_int = int(sr_used)
        except Exception:
            sr_used_int = None

        if sr_used_int and sr_used_int != sr:
            try:
                # Use resample_poly for good quality; reduce up/down by GCD for efficiency
                from math import gcd
                import scipy.signal as sps
                g = gcd(sr, sr_used_int)
                up = sr // g
                down = sr_used_int // g
                # resample_poly expects 1D arrays
                y = sps.resample_poly(y, up, down)
                sr_used = sr
            except Exception as e:
                logger.debug("Resampling failed (%s), proceeding without resample: %s", (sr_used, sr), e)

        return dj_bpm_estimate(y, sr_used)

    except Exception as e:
        logger.debug("BPM error while analyzing %s: %s", filepath, e)
        return None

def normalize_bpm(bpm):
    try:
        bpm = float(bpm)
    except Exception as exc:
        logger.debug("Failed BPM normalization for value %s: %s", bpm, exc)
        return None

    if not math.isfinite(bpm) or bpm <= 0:
        logger.debug("Invalid BPM value encountered: %s", bpm)
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
        logger.debug("BPM error: empty audio buffer")
        return None

    try:
        import librosa
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    except Exception as e:
        logger.debug("BPM error computing onset envelope: %s", e)
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
            # Ensure tempo is a scalar float; handle numpy arrays safely
            try:
                tempo_val = float(np.asarray(tempo).item())
            except Exception:
                logger.debug("BPM fallback beat_track returned invalid tempo: %s", tempo)
                return None
            if not math.isfinite(tempo_val) or tempo_val <= 0:
                logger.debug("BPM fallback beat_track failed: %s", tempo_val)
                return None
            return float(tempo_val)
        except Exception as e2:
            logger.debug("BPM fallback failed: %s", e2)
            return None

def analyze_key(filepath, duration=60):
    """
    Analyze audio file to detect musical key using chroma features.

    Args:
        filepath (str): Path to audio file
        duration (int): Duration to analyze in seconds

    Returns:
        str: Detected key (e.g. "Am", "C", "F#m") or None if failed
    """
    try:
        # Load audio using same robust logic as analyze_bpm
        # We need librosa for chroma features anyway
        import librosa

        # Helper to load audio safely
        def load_audio():
            # Calculate offset to analyze middle of track (better for key signature)
            offset = 0.0

            # Try soundfile first
            try:
                import soundfile as sf
                info = sf.info(filepath)
                sr_native = info.samplerate
                total_frames = info.frames
                frames_to_read = int(duration * sr_native)

                start_frame = 0
                if total_frames > frames_to_read:
                    start_frame = (total_frames - frames_to_read) // 2
                    offset = start_frame / sr_native

                data, sr_used = sf.read(filepath, start=start_frame, frames=frames_to_read, dtype='float32', always_2d=False)
                y = data
                if y.ndim > 1:
                    y = y.mean(axis=1)
                return y, sr_used
            except Exception:
                pass

            # Try ffmpeg decode
            if shutil.which('ffmpeg'):
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    tmpname = tmp.name
                try:
                    # Determine start time for ffmpeg if possible, otherwise just read from start
                    # Getting duration from ffmpeg is an extra call (ffprobe), so we might just skip offset or guess
                    # Ideally we trust sf.read failed, so maybe just read first 60s to be safe and fast.

                    # Prevent console window on Windows (PyInstaller)
                    import sys
                    if sys.platform == 'win32':
                        creationflags = subprocess.CREATE_NO_WINDOW
                    else:
                        creationflags = 0
                    subprocess.run([
                        'ffmpeg', '-y', '-ss', str(offset), '-i', filepath,
                        '-t', str(duration), '-ar', '22050', '-ac', '1', tmpname
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
                    try:
                        import soundfile as sf2
                        y, sr = sf2.read(tmpname, dtype='float32', always_2d=False)
                        if y.ndim > 1:
                            y = y.mean(axis=1)
                        return y, sr
                    except Exception:
                        return librosa.load(tmpname, sr=22050, mono=True)
                finally:
                    try:
                        os.unlink(tmpname)
                    except Exception:
                        pass
            # Last resort
            return librosa.load(filepath, sr=22050, mono=True, offset=offset, duration=duration)

        y, sr = load_audio()
        if y is None or len(y) == 0:
            return None

        # Compute chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        # Sum chroma over time
        chroma_sum = np.sum(chroma, axis=1)

        # Major and Minor profiles (Krumhansl-Schmuckler)
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        # Normalize
        major_profile = major_profile / np.sum(major_profile)
        minor_profile = minor_profile / np.sum(minor_profile)
        chroma_sum = chroma_sum / np.sum(chroma_sum)

        # Correlate
        max_cor = -1
        best_key = None

        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        # Test Major keys
        for i in range(12):
            # Rotate profile
            profile = np.roll(major_profile, i)
            cor = np.corrcoef(chroma_sum, profile)[0, 1]
            if cor > max_cor:
                max_cor = cor
                best_key = notes[i]

        # Test Minor keys
        for i in range(12):
            profile = np.roll(minor_profile, i)
            cor = np.corrcoef(chroma_sum, profile)[0, 1]
            if cor > max_cor:
                max_cor = cor
                best_key = notes[i] + "m"

        return best_key

    except Exception as e:
        logger.debug("Key analysis failed for %s: %s", filepath, e)
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
    return False

def write_key(filepath, key):
    """Write Key tag back into the audio file using mutagen when possible.

    Returns True on success, False otherwise.
    """
    try:
        if not key:
            return False

        # Normalize key string if needed (optional)
        key_val = str(key).strip()

        raw = MutagenFile(filepath)
        # MP3 (ID3 TKEY)
        try:
            if filepath.lower().endswith('.mp3'):
                try:
                    id3 = ID3(filepath)
                except ID3NoHeaderError:
                    id3 = ID3()
                # remove existing TKEY frames
                try:
                    id3.delall('TKEY')
                except Exception:
                    pass
                from mutagen.id3 import TKEY
                id3.add(TKEY(encoding=3, text=str(key_val)))
                id3.save(filepath)
                try:
                    metadata_extractor.update_cache(filepath)
                except Exception:
                    pass
                metadata_extractor._notify_key_listeners(filepath)
                return True
        except Exception:
            pass

        # MP4/M4A key tag
        try:
            if isinstance(raw, MP4) or filepath.lower().endswith(('.m4a', '.mp4')):
                mp4 = MP4(filepath)
                tags = mp4.tags or {}
                # iTunes standard key tag
                tags['----:com.apple.iTunes:KEY'] = [key_val.encode('utf-8')]
                # Also set initial_key for compatibility
                tags['----:com.apple.iTunes:initial_key'] = [key_val.encode('utf-8')]
                mp4.tags = tags
                mp4.save()
                try:
                    metadata_extractor.update_cache(filepath)
                    metadata_extractor._notify_key_listeners(filepath)
                except Exception:
                    pass
                return True
        except Exception:
            pass

        # FLAC Vorbis comment
        try:
            if isinstance(raw, FLAC) or filepath.lower().endswith('.flac'):
                fl = FLAC(filepath)
                fl['KEY'] = str(key_val)
                fl['INITIAL_KEY'] = str(key_val)
                fl.save()
                try:
                    metadata_extractor.update_cache(filepath)
                    metadata_extractor._notify_key_listeners(filepath)
                except Exception:
                    pass
                return True
        except Exception:
            pass

        # Generic easy tag fallback
        try:
            easy = MutagenFile(filepath, easy=True)
            if easy is not None:
                # Some easy implementations map 'key' or 'initial_key'
                try:
                    easy['key'] = [str(key_val)]
                except Exception:
                    try:
                        easy['initial_key'] = [str(key_val)]
                    except Exception:
                        pass
                easy.save()
                try:
                    metadata_extractor.update_cache(filepath)
                    metadata_extractor._notify_key_listeners(filepath)
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

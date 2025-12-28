"""
Metadata handling module for audio files.
Consolidates all metadata extraction, manipulation, and display logic.
"""

import os
import glob
from mutagen import File as MutagenFile
from mutagen.id3 import APIC, GEOB
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
import io
from PIL import Image


class MetadataExtractor:
    """Handles extraction and manipulation of audio file metadata."""

    def __init__(self):
        self._cache = {}

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
        except Exception:
            # Fallback to filename if metadata extraction fails
            metadata = {
                "title": os.path.basename(filepath),
                "artist": "Unknown Artist",
                "album": "Unknown Album",
                "duration": "",
                "duration_s": None,
                "bitrate": None,
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

                                # Include all covers
                                booklet_images.append((image_data, f"Cover Art {i+1}", "MP4 Cover"))
                            except Exception:
                                continue
                except Exception:
                    pass

        except Exception:
            pass

        # Optionally check for folder images (like VLC does)
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
                                booklet_images.append((img_data, img_name, "Folder Image"))
                        except Exception:
                            pass

                # Also check for any jpg/png files in the folder
                for ext in ['*.jpg', '*.jpeg', '*.png']:
                    for img_file in glob.glob(os.path.join(folder, ext)):
                        img_name = os.path.basename(img_file)
                        # Skip if already added
                        if img_name.lower() not in [n.lower() for n in image_names]:
                            try:
                                with open(img_file, 'rb') as f:
                                    img_data = f.read()
                                if img_data and len(img_data) > 0:
                                    booklet_images.append((img_data, img_name, "Folder Image"))
                            except Exception:
                                continue

            except Exception:
                pass

        return booklet_images

# Global instance for use across the application
metadata_extractor = MetadataExtractor()

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

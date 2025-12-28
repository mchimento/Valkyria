"""
Metadata handling module for audio files.
Consolidates all metadata extraction, manipulation, and display logic.
"""

import os
from mutagen import File as MutagenFile


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

    def clear_cache(self):
        """Clear the metadata cache."""
        self._cache.clear()


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

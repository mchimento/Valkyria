import unittest
import os
from unittest.mock import MagicMock, patch, PropertyMock
from audio.metadata import get_display_title, get_metadata

class TestMetadataDisplay(unittest.TestCase):
    @patch('audio.metadata.MutagenFile')
    def test_get_display_title_with_title_and_artist(self, mock_mutagen):
        # Setup mock
        mock_audio = MagicMock()
        mock_audio.__contains__.side_effect = lambda key: key in ['title', 'artist']
        mock_audio.__getitem__.side_effect = lambda key: ['My Title'] if key == 'title' else ['My Artist']
        mock_mutagen.return_value = mock_audio

        # Test
        result = get_display_title("dummy_path.mp3")
        self.assertEqual(result, "My Title — My Artist")

    @patch('audio.metadata.MutagenFile')
    def test_get_display_title_with_title_only(self, mock_mutagen):
        # Setup mock
        mock_audio = MagicMock()
        mock_audio.__contains__.side_effect = lambda key: key == 'title'
        mock_audio.__getitem__.return_value = ['My Title']
        mock_mutagen.return_value = mock_audio

        # Test
        result = get_display_title("dummy_path.mp3")
        self.assertEqual(result, "My Title")

    @patch('audio.metadata.MutagenFile')
    def test_get_display_title_no_metadata(self, mock_mutagen):
        # Setup mock to return None or empty dict-like object
        mock_mutagen.return_value = {}

        # Test
        result = get_display_title("/path/to/filename.mp3")
        self.assertEqual(result, "filename.mp3")

    @patch('audio.metadata.MutagenFile')
    def test_get_display_title_exception(self, mock_mutagen):
        # Setup mock to raise exception
        mock_mutagen.side_effect = Exception("Error reading file")

        # Test
        result = get_display_title("/path/to/filename.mp3")
        self.assertEqual(result, "filename.mp3")

    @patch('audio.metadata.MutagenFile')
    def test_get_metadata_with_nonstandard_id3_tags(self, mock_mutagen):
        """Test that files with non-standard ID3 tags (TXXX frames) are handled correctly.

        When mutagen's easy mode returns an empty dict for files with only TXXX frames,
        the code should fall back to non-easy mode to extract technical metadata.
        """
        # Mock easy mode returning empty dict (simulating TXXX-only file)
        mock_easy = MagicMock()
        mock_easy.keys.return_value = []  # Empty dict

        # Mock non-easy mode returning valid audio with technical info
        mock_noneasy = MagicMock()
        mock_noneasy.tags = {
            'TXXX:major_brand': MagicMock(),
            'TSSE': MagicMock()
        }
        mock_info = MagicMock()
        mock_info.length = 222.119
        mock_info.bitrate = 192000
        type(mock_noneasy).info = PropertyMock(return_value=mock_info)
        mock_noneasy.__class__.__name__ = 'MP3'
        mock_noneasy.get.side_effect = AttributeError("Not easy mode")

        # First call (easy=True) returns empty dict, second call (non-easy) returns valid data
        mock_mutagen.side_effect = [mock_easy, mock_noneasy]

        # Test
        result = get_metadata("Clair Obscur_ Expedition 33 Lumiere.mp3")

        # Verify technical metadata was extracted
        self.assertEqual(result['duration_s'], 222)
        self.assertEqual(result['bitrate'], 192)
        self.assertEqual(result['format'], 'mp3')
        self.assertEqual(result['duration'], '03:42')
        # Title should fall back to filename
        self.assertEqual(result['title'], 'Clair Obscur_ Expedition 33 Lumiere.mp3')
        self.assertEqual(result['artist'], 'Unknown Artist')

    @patch('audio.metadata.MutagenFile')
    def test_get_metadata_with_standard_tags(self, mock_mutagen):
        """Test that files with standard tags are handled correctly in easy mode."""
        # Mock easy mode with standard tags
        mock_audio = MagicMock()
        mock_audio.keys.return_value = ['title', 'artist', 'album']
        mock_audio.get.side_effect = lambda key, default: {
            'title': ['Test Title'],
            'artist': ['Test Artist'],
            'album': ['Test Album']
        }.get(key, default)

        mock_info = MagicMock()
        mock_info.length = 180.5
        mock_info.bitrate = 320000
        type(mock_audio).info = PropertyMock(return_value=mock_info)
        mock_audio.__class__.__name__ = 'EasyMP3'

        mock_mutagen.return_value = mock_audio

        # Test
        result = get_metadata("test.mp3")

        # Verify metadata was extracted correctly
        self.assertEqual(result['title'], 'Test Title')
        self.assertEqual(result['artist'], 'Test Artist')
        self.assertEqual(result['album'], 'Test Album')
        self.assertEqual(result['duration_s'], 180)
        self.assertEqual(result['bitrate'], 320)

if __name__ == '__main__':
    unittest.main()

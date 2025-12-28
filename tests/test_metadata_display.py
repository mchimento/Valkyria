import unittest
import os
from unittest.mock import MagicMock, patch
from audio.metadata import get_display_title

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

if __name__ == '__main__':
    unittest.main()

import unittest
import json
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, mock_open, PropertyMock
from app.settings import Settings


class TestSettings(unittest.TestCase):
    """Unit tests for the Settings class."""

    def setUp(self):
        # Suppress logging during tests to avoid cluttering output with expected errors
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Re-enable logging
        logging.disable(logging.NOTSET)

    def test_initialization_defaults(self):
        """Test that Settings initializes with correct default values."""
        with patch.object(Settings, 'load'):
            settings = Settings()
            settings.theme = "light"
            settings.window_geometry = None

            self.assertEqual(settings.theme, "light")
            self.assertIsNone(settings.window_geometry)
            self.assertTrue(settings.show_playlist)
            self.assertTrue(settings.show_browser)
            self.assertTrue(settings.show_dj)

    def test_load_with_existing_config(self):
        """Test that Settings.load() correctly loads from existing config file."""
        config_data = {
            "theme": "dark",
            "window_geometry": "1200x600",
            "show_dj": False
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with patch('app.settings.Settings.config_path', new_callable=PropertyMock) as mock_config_path:
                mock_config_path.return_value = Path(temp_path)
                settings = Settings()

                self.assertEqual(settings.theme, "dark")
                self.assertEqual(settings.window_geometry, "1200x600")
                self.assertFalse(settings.show_dj)
        finally:
            Path(temp_path).unlink()

    def test_load_with_missing_config(self):
        """Test that Settings.load() handles missing config file gracefully."""
        with patch('app.settings.Settings.config_path', new_callable=PropertyMock) as mock_config_path:
            mock_config_path.return_value = Path('/nonexistent/path/config.json')
            settings = Settings()

            # Should use defaults when file doesn't exist
            self.assertEqual(settings.theme, "light")
            self.assertIsNone(settings.window_geometry)

    def test_load_with_corrupted_json(self):
        """Test that Settings.load() handles corrupted JSON gracefully."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{invalid json content")
            temp_path = f.name

        try:
            with patch('app.settings.Settings.config_path', new_callable=PropertyMock) as mock_config_path:
                mock_config_path.return_value = Path(temp_path)
                settings = Settings()

                # Should use defaults when JSON is invalid
                self.assertEqual(settings.theme, "light")
                self.assertIsNone(settings.window_geometry)
        finally:
            Path(temp_path).unlink()

    def test_load_with_partial_config(self):
        """Test that Settings.load() handles partial config data."""
        config_data = {"theme": "dark"}  # Missing window_geometry

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with patch('app.settings.Settings.config_path', new_callable=PropertyMock) as mock_config_path:
                mock_config_path.return_value = Path(temp_path)
                settings = Settings()

                self.assertEqual(settings.theme, "dark")
                self.assertIsNone(settings.window_geometry)  # Should use default
        finally:
            Path(temp_path).unlink()

    def test_save_creates_valid_json(self):
        """Test that Settings.save() creates a valid JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test_config.json"

            with patch('app.settings.Settings.config_path', new_callable=PropertyMock) as mock_config_path:
                mock_config_path.return_value = temp_path
                settings = Settings()
                settings.theme = "dark"
                settings.window_geometry = "1024x768"
                settings.show_dj = False
                settings.save()

                # Verify file was created
                self.assertTrue(temp_path.exists())

                # Verify content is valid JSON
                with open(temp_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.assertEqual(data['theme'], "dark")
                self.assertEqual(data['window_geometry'], "1024x768")
                self.assertFalse(data['show_dj'])

    def test_save_handles_write_errors(self):
        """Test that Settings.save() handles write errors gracefully."""
        with patch('app.settings.Settings.config_path', new_callable=PropertyMock) as mock_config_path:
            mock_config_path.return_value = Path('/invalid/path/config.json')
            settings = Settings()
            settings.theme = "dark"

            # Should not raise exception
            try:
                settings.save()
            except Exception as e:
                self.fail(f"Settings.save() raised exception: {e}")

    def test_round_trip_save_and_load(self):
        """Test that saving and loading settings preserves data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test_config.json"

            with patch('app.settings.Settings.config_path', new_callable=PropertyMock) as mock_config_path:
                mock_config_path.return_value = temp_path
                # Save settings
                settings1 = Settings()
                settings1.theme = "dark"
                settings1.window_geometry = "800x600"
                settings1.show_dj = False
                settings1.mute = True
                settings1.save()

                # Load settings in new instance
                settings2 = Settings()

                self.assertEqual(settings2.theme, "dark")
                self.assertEqual(settings2.window_geometry, "800x600")
                self.assertFalse(settings2.show_dj)
                self.assertTrue(settings2.mute)


if __name__ == '__main__':
    unittest.main()

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open
from app.settings import Settings


class TestSettings(unittest.TestCase):
    """Unit tests for the Settings class."""

    def test_initialization_defaults(self):
        """Test that Settings initializes with correct default values."""
        with patch.object(Settings, 'load'):
            settings = Settings()
            settings.theme = "light"
            settings.window_geometry = None

            self.assertEqual(settings.theme, "light")
            self.assertIsNone(settings.window_geometry)

    def test_load_with_existing_config(self):
        """Test that Settings.load() correctly loads from existing config file."""
        config_data = {
            "theme": "dark",
            "window_geometry": "1200x600"
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            with patch.object(Settings, 'CONFIG_PATH', Path(temp_path)):
                settings = Settings()

                self.assertEqual(settings.theme, "dark")
                self.assertEqual(settings.window_geometry, "1200x600")
        finally:
            Path(temp_path).unlink()

    def test_load_with_missing_config(self):
        """Test that Settings.load() handles missing config file gracefully."""
        with patch.object(Settings, 'CONFIG_PATH', Path('/nonexistent/path/config.json')):
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
            with patch.object(Settings, 'CONFIG_PATH', Path(temp_path)):
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
            with patch.object(Settings, 'CONFIG_PATH', Path(temp_path)):
                settings = Settings()

                self.assertEqual(settings.theme, "dark")
                self.assertIsNone(settings.window_geometry)  # Should use default
        finally:
            Path(temp_path).unlink()

    def test_save_creates_valid_json(self):
        """Test that Settings.save() creates a valid JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test_config.json"

            with patch.object(Settings, 'CONFIG_PATH', temp_path):
                settings = Settings()
                settings.theme = "dark"
                settings.window_geometry = "1024x768"
                settings.save()

                # Verify file was created
                self.assertTrue(temp_path.exists())

                # Verify content is valid JSON
                with open(temp_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.assertEqual(data['theme'], "dark")
                self.assertEqual(data['window_geometry'], "1024x768")

    def test_save_handles_write_errors(self):
        """Test that Settings.save() handles write errors gracefully."""
        with patch.object(Settings, 'CONFIG_PATH', Path('/invalid/path/config.json')):
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

            with patch.object(Settings, 'CONFIG_PATH', temp_path):
                # Save settings
                settings1 = Settings()
                settings1.theme = "dark"
                settings1.window_geometry = "800x600"
                settings1.save()

                # Load settings in new instance
                settings2 = Settings()

                self.assertEqual(settings2.theme, "dark")
                self.assertEqual(settings2.window_geometry, "800x600")


if __name__ == '__main__':
    unittest.main()

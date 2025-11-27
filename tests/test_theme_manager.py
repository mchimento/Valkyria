import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tkinter as tk
from themes.theme_manager import ThemeManager
from app.settings import Settings


class TestThemeManager(unittest.TestCase):
    """Unit tests for the ThemeManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_settings = Mock(spec=Settings)
        self.mock_settings.theme = "light"

    def test_initialization_loads_theme(self):
        """Test that ThemeManager initializes and loads theme correctly."""
        with patch.object(ThemeManager, 'reload'):
            theme_manager = ThemeManager(self.mock_settings)

            self.assertEqual(theme_manager.settings, self.mock_settings)
            theme_manager.reload.assert_called_once()

    def test_reload_with_valid_theme_file(self):
        """Test that reload() loads a valid theme file."""
        theme_data = {
            "bg": "#ffffff",
            "fg": "#000000",
            "accent": "#0078d4"
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            theme_path = Path(temp_dir) / "light.json"
            with open(theme_path, 'w', encoding='utf-8') as f:
                json.dump(theme_data, f)

            with patch('themes.theme_manager.Path') as mock_path:
                mock_path.return_value.parent = Path(temp_dir)

                theme_manager = ThemeManager(self.mock_settings)

                self.assertEqual(theme_manager.palette['bg'], "#ffffff")
                self.assertEqual(theme_manager.palette['fg'], "#000000")
                self.assertEqual(theme_manager.palette['accent'], "#0078d4")

    def test_reload_with_missing_theme_file_fallback(self):
        """Test that reload() falls back to light theme when theme file is missing."""
        self.mock_settings.theme = "nonexistent"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create light.json as fallback
            light_theme = {"bg": "#f0f0f0", "fg": "#000"}
            light_path = Path(temp_dir) / "light.json"
            with open(light_path, 'w', encoding='utf-8') as f:
                json.dump(light_theme, f)

            with patch('themes.theme_manager.Path') as mock_path:
                mock_path.return_value.parent = Path(temp_dir)

                theme_manager = ThemeManager(self.mock_settings)

                # Should have loaded light.json as fallback
                self.assertIsNotNone(theme_manager.palette)

    def test_reload_with_invalid_json_uses_defaults(self):
        """Test that reload() uses default palette when JSON is invalid."""
        with tempfile.TemporaryDirectory() as temp_dir:
            theme_path = Path(temp_dir) / "light.json"
            with open(theme_path, 'w', encoding='utf-8') as f:
                f.write("{invalid json")

            with patch('themes.theme_manager.Path') as mock_path:
                mock_path.return_value.parent = Path(temp_dir)

                theme_manager = ThemeManager(self.mock_settings)

                # Should have default palette
                self.assertIn('bg', theme_manager.palette)
                self.assertIn('fg', theme_manager.palette)
                self.assertEqual(theme_manager.palette['bg'], "#f0f0f0")

    def test_load_default_palette(self):
        """Test that _load_default_palette() provides valid palette."""
        theme_manager = ThemeManager(self.mock_settings)
        theme_manager._load_default_palette()

        # Check all required keys are present
        required_keys = ['bg', 'fg', 'accent', 'accent_hover', 'tree_bg',
                        'tree_header', 'tooltip_bg', 'highlight', 'ui_font']
        for key in required_keys:
            self.assertIn(key, theme_manager.palette)

        # Check values are strings
        for value in theme_manager.palette.values():
            self.assertIsInstance(value, str)

    def test_apply_to_root_window(self):
        """Test that apply_to() applies styles to root window."""
        theme_manager = ThemeManager(self.mock_settings)
        theme_manager.palette = {
            'bg': '#ffffff',
            'fg': '#000000',
            'accent': '#0078d4'
        }

        mock_root = Mock(spec=tk.Tk)

        with patch('themes.theme_manager.apply_base_styles') as mock_apply:
            theme_manager.apply_to(mock_root)

            # Verify apply_base_styles was called
            mock_apply.assert_called_once_with(mock_root, theme_manager.palette)

            # Verify root.configure was called
            mock_root.configure.assert_called_once_with(bg='#ffffff')

    def test_apply_to_handles_errors_gracefully(self):
        """Test that apply_to() handles errors gracefully."""
        theme_manager = ThemeManager(self.mock_settings)

        mock_root = Mock(spec=tk.Tk)
        mock_root.configure.side_effect = Exception("Test error")

        with patch('themes.theme_manager.apply_base_styles'):
            # Should not raise exception
            try:
                theme_manager.apply_to(mock_root)
            except Exception as e:
                self.fail(f"apply_to() raised exception: {e}")

    def test_reload_updates_palette(self):
        """Test that calling reload() updates the palette."""
        theme_manager = ThemeManager(self.mock_settings)
        original_palette = theme_manager.palette.copy()

        # Change theme setting
        self.mock_settings.theme = "dark"

        # Reload should update palette (even if file doesn't exist, it will use defaults)
        theme_manager.reload()

        # Palette should still be valid
        self.assertIsInstance(theme_manager.palette, dict)
        self.assertIn('bg', theme_manager.palette)

    def test_theme_manager_with_none_settings_theme(self):
        """Test that ThemeManager handles None theme gracefully."""
        self.mock_settings.theme = None

        theme_manager = ThemeManager(self.mock_settings)

        # Should default to "light"
        self.assertIsNotNone(theme_manager.palette)
        self.assertIn('bg', theme_manager.palette)


if __name__ == '__main__':
    unittest.main()

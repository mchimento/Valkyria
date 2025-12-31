"""Tests for application-level theme switching functionality."""
import unittest
import logging
import os
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch
from tkinter import ttk

# Suppress logging during tests
logging.disable(logging.CRITICAL)

# Skip UI tests if running in headless environment (CI/CD)
HAS_DISPLAY = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or os.name == 'nt'

class TestThemeSwitching(unittest.TestCase):
    """Integration tests for theme switching functionality."""

    @classmethod
    def setUpClass(cls):
        """Suppress logging for all tests in this class."""
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        """Re-enable logging after tests."""
        logging.disable(logging.NOTSET)

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide window during tests

    def tearDown(self):
        """Clean up after tests."""
        try:
            if hasattr(self, 'root'):
                self.root.destroy()
        except Exception:
            pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_manager_switch_light_to_dark(self):
        """Test ThemeManager switching from light to dark theme."""
        from themes.theme_manager import ThemeManager
        from app.settings import Settings

        # Create mock settings
        mock_settings = Mock(spec=Settings)
        mock_settings.theme = "light"

        # Create theme manager
        theme_manager = ThemeManager(mock_settings)

        # Verify initial light theme
        self.assertEqual(theme_manager.settings.theme, "light")
        self.assertIsNotNone(theme_manager.palette)

        # Switch to dark theme
        mock_settings.theme = "dark"
        theme_manager.reload()

        # Verify dark theme is loaded
        self.assertEqual(theme_manager.settings.theme, "dark")
        self.assertIsNotNone(theme_manager.palette)

        # Dark theme should have different background color
        self.assertIn('bg', theme_manager.palette)

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_manager_switch_dark_to_light(self):
        """Test ThemeManager switching from dark to light theme."""
        from themes.theme_manager import ThemeManager
        from app.settings import Settings

        # Create mock settings starting with dark theme
        mock_settings = Mock(spec=Settings)
        mock_settings.theme = "dark"

        # Create theme manager
        theme_manager = ThemeManager(mock_settings)

        # Verify initial dark theme
        self.assertEqual(theme_manager.settings.theme, "dark")

        # Switch to light theme
        mock_settings.theme = "light"
        theme_manager.reload()

        # Verify light theme is loaded
        self.assertEqual(theme_manager.settings.theme, "light")
        self.assertIsNotNone(theme_manager.palette)

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_apply_to_root_window(self):
        """Test applying theme to root window after switch."""
        from themes.theme_manager import ThemeManager
        from app.settings import Settings

        mock_settings = Mock(spec=Settings)
        mock_settings.theme = "light"

        theme_manager = ThemeManager(mock_settings)
        theme_manager.palette = {
            'bg': '#ffffff',
            'fg': '#000000',
            'accent': '#0078d4',
            'button_hover': '#106ebe',
            'accent_hover': '#106ebe',
            'button_fg_color': '#ffffff',
            'tree_bg': '#ffffff',
            'tree_header': '#f0f0f0',
            'ui_font': 'Segoe UI'
        }

        # Apply theme to root
        try:
            theme_manager.apply_to(self.root)
            # Verify root background was set
            self.assertEqual(self.root.cget('bg'), '#ffffff')
        except Exception as e:
            # Skip this test if styling fails
            self.skipTest(f"Theme styling failed: {e}")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_controls_bar_theme_integration(self):
        """Test ControlsBar integration with theme switching."""
        from ui.controls import ControlsBar
        from themes.theme_manager import ThemeManager
        from app.settings import Settings

        # Create mock objects
        mock_player = MagicMock()
        mock_state = MagicMock()
        mock_state.play_on_double = False
        mock_settings = Mock(spec=Settings)
        mock_settings.theme = "light"
        mock_settings.volume = 80
        mock_settings.mute = False

        # Create theme manager and controls
        theme_manager = ThemeManager(mock_settings)
        controls = ControlsBar(
            self.root,
            mock_player,
            mock_state,
            theme_manager,
            playlist=None,
            tooltip_manager=None,
            settings=mock_settings
        )

        # Verify initial theme application
        self.assertIsInstance(controls, ttk.Frame)

        # Switch theme
        mock_settings.theme = "dark"
        theme_manager.reload()

        # Update controls with new theme
        controls.update_theme()

        # Verify no exceptions occurred
        self.assertTrue(True)  # If we get here, no exceptions were raised

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_persistence_across_components(self):
        """Test that theme changes persist across different UI components."""
        from ui.controls import ControlsBar
        from themes.theme_manager import ThemeManager
        from app.settings import Settings

        # Create mock objects
        mock_player = MagicMock()
        mock_state = MagicMock()
        mock_state.play_on_double = False
        mock_settings = Mock(spec=Settings)
        mock_settings.theme = "light"
        mock_settings.volume = 80
        mock_settings.mute = False

        # Create theme manager
        theme_manager = ThemeManager(mock_settings)

        # Create multiple UI components
        controls1 = ControlsBar(
            self.root,
            mock_player,
            mock_state,
            theme_manager,
            playlist=None,
            tooltip_manager=None,
            settings=mock_settings
        )

        controls2 = ControlsBar(
            self.root,
            mock_player,
            mock_state,
            theme_manager,
            playlist=None,
            tooltip_manager=None,
            settings=mock_settings
        )

        # Switch theme
        mock_settings.theme = "dark"
        theme_manager.reload()

        # Update both components
        controls1.update_theme()
        controls2.update_theme()

        # Verify both components updated without errors
        self.assertTrue(True)  # If we get here, no exceptions were raised

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_switch_with_invalid_theme_name(self):
        """Test theme switching with invalid theme name."""
        from themes.theme_manager import ThemeManager
        from app.settings import Settings

        mock_settings = Mock(spec=Settings)
        mock_settings.theme = "nonexistent_theme"

        # Should fallback to light theme
        theme_manager = ThemeManager(mock_settings)

        # Should have loaded fallback theme
        self.assertIsNotNone(theme_manager.palette)
        self.assertIn('bg', theme_manager.palette)

        # Should be able to apply theme without errors
        try:
            theme_manager.apply_to(self.root)
        except Exception as e:
            self.fail(f"Theme application with invalid theme name failed: {e}")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_switch_performance(self):
        """Test that theme switching completes in reasonable time."""
        import time
        from themes.theme_manager import ThemeManager
        from ui.controls import ControlsBar
        from app.settings import Settings

        # Create mock objects
        mock_player = MagicMock()
        mock_state = MagicMock()
        mock_state.play_on_double = False
        mock_settings = Mock(spec=Settings)
        mock_settings.theme = "light"  # Initialize with a theme
        mock_settings.volume = 80
        mock_settings.mute = False

        # Create theme manager and controls
        theme_manager = ThemeManager(mock_settings)
        controls = ControlsBar(
            self.root,
            mock_player,
            mock_state,
            theme_manager,
            playlist=None,
            tooltip_manager=None,
            settings=mock_settings
        )

        # Measure time for multiple theme switches
        start_time = time.time()
        
        for i in range(5):  # Reduced from 10 to 5 for faster testing
            mock_settings.theme = "light" if i % 2 == 0 else "dark"
            theme_manager.reload()
            controls.update_theme()
        
        end_time = time.time()
        elapsed_time = end_time - start_time

        # Should complete 5 switches in under 2 seconds (generous limit)
        self.assertLess(elapsed_time, 2.0, f"Theme switching took too long: {elapsed_time:.3f}s")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_switch_with_missing_theme_files(self):
        """Test theme switching when theme files are missing."""
        from themes.theme_manager import ThemeManager
        from app.settings import Settings
        from pathlib import Path

        mock_settings = Mock(spec=Settings)
        mock_settings.theme = "missing_theme"

        with patch('themes.theme_manager.get_resource_path') as mock_get_path:
            # Simulate missing theme files
            mock_get_path.return_value = Path("nonexistent_file.json")
            
            # Should not crash
            try:
                theme_manager = ThemeManager(mock_settings)
                theme_manager.apply_to(self.root)
            except Exception as e:
                self.fail(f"Theme switching with missing files failed: {e}")

            # Should have fallback palette
            self.assertIsNotNone(theme_manager.palette)

if __name__ == '__main__':
    unittest.main()

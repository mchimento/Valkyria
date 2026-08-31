import unittest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from app.paths import get_app_base_path, get_user_data_path, get_resource_path

class TestPaths(unittest.TestCase):
    """Unit tests for path utility functions."""

    def test_get_app_base_path_dev(self):
        """Test base path in development mode (not frozen)."""
        with patch.object(sys, 'frozen', False, create=True):
            base_path = get_app_base_path()
            # In dev mode, it should be the project root (parent of app/)
            # We are in tests/test_paths.py, so we can infer where app/paths.py is
            # app/paths.py is in <root>/app/paths.py
            # get_app_base_path returns <root>
            # This test file is in <root>/tests/test_paths.py
            expected_root = Path(__file__).parent.parent
            self.assertEqual(base_path, expected_root)

    def test_get_app_base_path_frozen(self):
        """Test base path in frozen mode (PyInstaller)."""
        mock_meipass = "/tmp/meipass"
        with patch.object(sys, 'frozen', True, create=True):
            with patch.object(sys, '_MEIPASS', mock_meipass, create=True):
                base_path = get_app_base_path()
                self.assertEqual(base_path, Path(mock_meipass))

    def test_get_user_data_path(self):
        """Mocks Path.home()/LOCALAPPDATA so this never touches the real user directory."""
        import platform
        with tempfile.TemporaryDirectory() as tmp:
            if platform.system() == "Windows":
                with patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                    path = get_user_data_path()
                self.assertEqual(path.name, "Valkyria")
            else:
                with patch.object(Path, "home", return_value=Path(tmp)):
                    path = get_user_data_path()
                self.assertEqual(path.name, ".valkyria")
            # It should be an absolute path
            self.assertTrue(path.is_absolute())

    def test_get_user_data_path_migrates_old_tango_studio_directory(self):
        """An old-named directory's contents should be moved, not left behind."""
        import platform
        with tempfile.TemporaryDirectory() as tmp:
            if platform.system() == "Windows":
                old_dir = Path(tmp) / "TangoStudio"
                old_dir.mkdir()
                (old_dir / "config.json").write_text('{"theme": "dark"}')
                with patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                    path = get_user_data_path()
            else:
                old_dir = Path(tmp) / ".tango-studio"
                old_dir.mkdir()
                (old_dir / "config.json").write_text('{"theme": "dark"}')
                with patch.object(Path, "home", return_value=Path(tmp)):
                    path = get_user_data_path()

            self.assertFalse(old_dir.exists())
            self.assertEqual((path / "config.json").read_text(), '{"theme": "dark"}')

    def test_get_resource_path_dev(self):
        """Test resource path resolution in dev mode."""
        with patch.object(sys, 'frozen', False, create=True):
            path = get_resource_path("themes/dark.json")
            self.assertEqual(path.name, "dark.json")
            self.assertIn("themes", str(path))
            self.assertTrue(path.is_absolute())

    def test_get_resource_path_frozen(self):
        """Test resource path resolution in frozen mode."""
        mock_meipass = "/tmp/meipass"
        with patch.object(sys, 'frozen', True, create=True):
            with patch.object(sys, '_MEIPASS', mock_meipass, create=True):
                path = get_resource_path("themes/dark.json")
                # Use Path to handle separators correctly
                expected = Path(mock_meipass) / "themes" / "dark.json"
                self.assertEqual(path, expected)

if __name__ == '__main__':
    unittest.main()

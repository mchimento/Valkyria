"""
Path utility module for Valkyria.
Handles path resolution for resources and user data, supporting both
development environment and PyInstaller frozen state.
"""
import logging
import shutil
import sys
import os
from pathlib import Path
import platform

logger = logging.getLogger(__name__)

def get_app_base_path() -> Path:
    """
    Get the base path of the application.

    Returns:
        Path: The base path where the application is running.
              In frozen mode (PyInstaller), this is sys._MEIPASS.
              In dev mode, this is the project root (parent of app/).
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temporary directory and stores path in _MEIPASS
        return Path(sys._MEIPASS)
    else:
        # In dev mode, we are in app/paths.py, so project root is parent's parent
        return Path(__file__).parent.parent

def get_user_data_path() -> Path:
    """
    Get the path for storing user data (logs, config).

    Returns:
        Path: A writable directory for user data.
              On Windows: %LOCALAPPDATA%/Valkyria
              On others: ~/.valkyria
    """
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = os.path.expanduser("~\\AppData\\Local")
        path = Path(base) / "Valkyria"
        old_path = Path(base) / "TangoStudio"
    else:
        path = Path.home() / ".valkyria"
        old_path = Path.home() / ".tango-studio"

    if not path.exists() and old_path.exists():
        # One-time migration from the app's old name (Tango Studio) — a
        # plain rename here without this would make every existing
        # user's saved theme, volume, window geometry, etc. (all read
        # from Settings.config_path, which lives under this directory)
        # silently vanish on first launch after the app rename, since
        # Settings() would just find nothing at the new path and fall
        # back to hardcoded defaults. shutil.move handles the same-
        # filesystem rename case and the cross-filesystem copy+remove
        # case transparently.
        try:
            shutil.move(str(old_path), str(path))
            logger.info(f"Migrated user data directory from {old_path} to {path}")
        except OSError:
            logger.warning(
                f"Failed to migrate user data from {old_path} to {path}", exc_info=True
            )

    path.mkdir(parents=True, exist_ok=True)
    return path

def get_resource_path(relative_path: str) -> Path:
    """
    Get the absolute path to a resource file.

    Args:
        relative_path: Path relative to the project root (e.g., "themes/dark.json")

    Returns:
        Path: Absolute path to the resource.
    """
    return get_app_base_path() / relative_path

def get_docs_path() -> Path:
    """
    Get the path to the documentation folder.

    Returns:
        Path: Absolute path to the docs/ directory.
    """
    return get_app_base_path() / "docs"

def get_generator_templates_path() -> Path:
    """
    Get the path to the playlist generator templates JSON file.

    Returns:
        Path: Writable path for generator_templates.json in user data dir.
    """
    return get_user_data_path() / "generator_templates.json"

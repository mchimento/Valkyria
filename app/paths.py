"""
Path utility module for Valkyria.
Handles path resolution for resources and user data, supporting both
development environment and PyInstaller frozen state.
"""
import sys
import os
from pathlib import Path
import platform

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
              On Windows: %LOCALAPPDATA%/TangoStudio
              On others: ~/.tango-studio
    """
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = os.path.expanduser("~\\AppData\\Local")
        path = Path(base) / "TangoStudio"
    else:
        path = Path.home() / ".tango-studio"

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

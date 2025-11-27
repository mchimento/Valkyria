"""
M3U parser and writer
"""
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def parse_m3u(path: str) -> List[str]:
    """
    Parse an M3U playlist file and return a list of file paths.

    Args:
        path: Path to the M3U/M3U8 playlist file.

    Returns:
        List of absolute file paths from the playlist.

    Raises:
        FileNotFoundError: If the playlist file doesn't exist.
        IOError: If the file cannot be read.
    """
    items = []
    base = Path(path).parent

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith(("http://", "https://")):
                    items.append(line)
                else:
                    items.append(str((base / line).resolve()))
        logger.info(f"Parsed M3U playlist: {path} ({len(items)} items)")
    except UnicodeDecodeError:
        logger.warning(f"UTF-8 decode failed for {path}, trying latin-1")
        try:
            with open(path, "r", encoding="latin-1") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith(("http://", "https://")):
                        items.append(line)
                    else:
                        items.append(str((base / line).resolve()))
            logger.info(f"Parsed M3U playlist with latin-1: {path} ({len(items)} items)")
        except Exception as e:
            logger.error(f"Failed to parse M3U file {path}: {e}", exc_info=True)
            raise
    except Exception as e:
        logger.error(f"Failed to parse M3U file {path}: {e}", exc_info=True)
        raise

    return items


def write_m3u(path: str, entries: List[str]) -> None:
    """
    Write a list of file paths to an M3U playlist file.

    Args:
        path: Path where the M3U/M3U8 file should be written.
        entries: List of file paths to include in the playlist.

    Raises:
        IOError: If the file cannot be written.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\\n")
            for e in entries:
                f.write(f"#EXTINF:-1,{Path(e).name}\\n{e}\\n")
        logger.info(f"Wrote M3U playlist: {path} ({len(entries)} items)")
    except Exception as e:
        logger.error(f"Failed to write M3U file {path}: {e}", exc_info=True)
        raise

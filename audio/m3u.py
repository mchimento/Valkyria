"""
M3U parser and writer
"""
from pathlib import Path

def parse_m3u(path):
    items = []
    base = Path(path).parent
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("http://", "https://")):
                items.append(line)
            else:
                items.append(str((base / line).resolve()))
    return items

def write_m3u(path, entries):
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for e in entries:
            f.write(f"#EXTINF:-1,{Path(e).name}\n{e}\n")

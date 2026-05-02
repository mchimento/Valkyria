"""
Playlist generator: data model, generation algorithm, and template persistence.
"""
import json
import os
import random
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}

MUSICAL_KEYS = [
    "Any",
    "C", "Cm", "C#", "C#m",
    "D", "Dm", "Eb", "Ebm",
    "E", "Em", "F", "Fm",
    "F#", "F#m", "G", "Gm",
    "Ab", "Abm", "A", "Am",
    "Bb", "Bbm", "B", "Bm",
]

ORDER_MODES = {
    "strict": "Original order within groups",
    "shuffle_within_group": "Shuffle within groups",
    "fully_random": "Fully random",
}


@dataclass
class FilterSet:
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None
    key: Optional[str] = None  # None or "Any" means no filter

    def to_dict(self):
        return {"bpm_min": self.bpm_min, "bpm_max": self.bpm_max, "key": self.key}

    @classmethod
    def from_dict(cls, d):
        return cls(bpm_min=d.get("bpm_min"), bpm_max=d.get("bpm_max"), key=d.get("key"))


@dataclass
class Source:
    type: str  # "directory" | "playlist" | "file"
    path: str

    def to_dict(self):
        return {"type": self.type, "path": self.path}

    @classmethod
    def from_dict(cls, d):
        return cls(type=d["type"], path=d["path"])


@dataclass
class Subgroup:
    name: str
    sources: List[Source] = field(default_factory=list)

    def to_dict(self):
        return {"name": self.name, "sources": [s.to_dict() for s in self.sources]}

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            sources=[Source.from_dict(s) for s in d.get("sources", [])],
        )


@dataclass
class Group:
    name: str
    subgroups: List[Subgroup] = field(default_factory=list)
    filters: FilterSet = field(default_factory=FilterSet)
    songs_per_round: int = 1

    def to_dict(self):
        return {
            "name": self.name,
            "subgroups": [sg.to_dict() for sg in self.subgroups],
            "filters": self.filters.to_dict(),
            "songs_per_round": self.songs_per_round,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            subgroups=[Subgroup.from_dict(sg) for sg in d.get("subgroups", [])],
            filters=FilterSet.from_dict(d.get("filters", {})),
            songs_per_round=d.get("songs_per_round", 1),
        )


@dataclass
class GeneratorRules:
    total_songs: Optional[int] = None
    total_duration_sec: Optional[int] = None
    allow_repeats: bool = False
    order_mode: str = "shuffle_within_group"

    def to_dict(self):
        return {
            "total_songs": self.total_songs,
            "total_duration_sec": self.total_duration_sec,
            "allow_repeats": self.allow_repeats,
            "order_mode": self.order_mode,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            total_songs=d.get("total_songs"),
            total_duration_sec=d.get("total_duration_sec"),
            allow_repeats=d.get("allow_repeats", False),
            order_mode=d.get("order_mode", "shuffle_within_group"),
        )


@dataclass
class GeneratorTemplate:
    name: str
    groups: List[Group] = field(default_factory=list)
    rules: GeneratorRules = field(default_factory=GeneratorRules)

    def to_dict(self):
        return {
            "name": self.name,
            "groups": [g.to_dict() for g in self.groups],
            "rules": self.rules.to_dict(),
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=d["name"],
            groups=[Group.from_dict(g) for g in d.get("groups", [])],
            rules=GeneratorRules.from_dict(d.get("rules", {})),
        )


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------

def scan_audio_dir(path: str) -> List[str]:
    """Return all audio files found directly inside a directory (non-recursive)."""
    result = []
    try:
        for entry in sorted(os.scandir(path), key=lambda e: e.name.lower()):
            if entry.is_file() and Path(entry.name).suffix.lower() in AUDIO_EXTENSIONS:
                result.append(entry.path)
    except OSError as e:
        logger.warning(f"Could not scan directory {path}: {e}")
    return result


def _load_source_files(source: Source) -> List[str]:
    if source.type == "directory":
        return scan_audio_dir(source.path)
    if source.type == "playlist":
        try:
            from audio.m3u import parse_m3u
            return parse_m3u(source.path)
        except Exception as e:
            logger.warning(f"Could not parse playlist {source.path}: {e}")
    if source.type == "file":
        if os.path.isfile(source.path) and Path(source.path).suffix.lower() in AUDIO_EXTENSIONS:
            return [source.path]
    return []


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def _passes_filter(meta: dict, filters: FilterSet) -> bool:
    bpm = meta.get("bpm")
    if filters.bpm_min is not None:
        if bpm is None or bpm < filters.bpm_min:
            return False
    if filters.bpm_max is not None:
        if bpm is None or bpm > filters.bpm_max:
            return False
    if filters.key and filters.key != "Any":
        track_key = (meta.get("key") or "").strip()
        if track_key != filters.key.strip():
            return False
    return True


def build_group_pool(group: Group, metadata_extractor) -> List[str]:
    """Collect and filter all candidate songs for a group."""
    seen: set = set()
    files: List[str] = []
    for subgroup in group.subgroups:
        for source in subgroup.sources:
            for f in _load_source_files(source):
                if f not in seen:
                    seen.add(f)
                    files.append(f)

    has_filters = (
        group.filters.bpm_min is not None
        or group.filters.bpm_max is not None
        or (group.filters.key and group.filters.key != "Any")
    )
    if not has_filters:
        return files

    filtered = []
    for f in files:
        try:
            meta = metadata_extractor.get_metadata(f)
            if _passes_filter(meta, group.filters):
                filtered.append(f)
        except Exception:
            pass
    return filtered


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate(template: GeneratorTemplate, metadata_extractor) -> List[str]:
    """
    Generate a playlist from the template.

    Groups are processed in list order. Songs are interleaved round-robin:
    each round picks `songs_per_round` tracks from each group in sequence.
    Returns a list of absolute file paths.
    """
    groups = template.groups
    rules = template.rules

    pools = {g.name: build_group_pool(g, metadata_extractor) for g in groups}

    result: List[str] = []
    used: set = set()
    total_dur = 0.0

    def _duration(path: str) -> float:
        try:
            return metadata_extractor.get_metadata(path).get("duration_s") or 0.0
        except Exception:
            return 0.0

    def _can_add() -> bool:
        if rules.total_songs is not None and len(result) >= rules.total_songs:
            return False
        if rules.total_duration_sec is not None and total_dur >= rules.total_duration_sec:
            return False
        return True

    def _add(path: str) -> bool:
        nonlocal total_dur
        if not rules.allow_repeats and path in used:
            return False
        if not _can_add():
            return False
        if rules.total_duration_sec is not None:
            dur = _duration(path)
            if total_dur + dur > rules.total_duration_sec:
                return False
            total_dur += dur
        result.append(path)
        used.add(path)
        return True

    if rules.order_mode == "fully_random":
        all_songs = [s for g in groups for s in pools[g.name]]
        random.shuffle(all_songs)
        for song in all_songs:
            if not _can_add():
                break
            _add(song)
        return result

    # Round-robin across groups
    group_pools: dict = {}
    for g in groups:
        pool = pools[g.name][:]
        if rules.order_mode == "shuffle_within_group":
            random.shuffle(pool)
        group_pools[g.name] = pool

    positions = {g.name: 0 for g in groups}
    exhausted: set = set()

    while len(exhausted) < len(groups) and _can_add():
        made_progress = False
        for g in groups:
            if g.name in exhausted:
                continue
            if not _can_add():
                break
            pool = group_pools[g.name]
            pos = positions[g.name]
            picked = 0
            while picked < g.songs_per_round and pos < len(pool):
                if not _can_add():
                    break
                song = pool[pos]
                pos += 1
                if _add(song):
                    picked += 1
                    made_progress = True
            positions[g.name] = pos
            if pos >= len(pool):
                exhausted.add(g.name)
        if not made_progress:
            break

    return result


# ---------------------------------------------------------------------------
# Template persistence
# ---------------------------------------------------------------------------

def load_templates(path: str) -> List[GeneratorTemplate]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [GeneratorTemplate.from_dict(t) for t in data.get("templates", [])]
    except Exception as e:
        logger.warning(f"Could not load generator templates from {path}: {e}")
        return []


def save_templates(path: str, templates: List[GeneratorTemplate]) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"templates": [t.to_dict() for t in templates]}, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Could not save generator templates to {path}: {e}")

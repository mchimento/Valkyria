# Changelog

All notable changes to Valkyria are documented in this file.

## [0.2.1] - 2026-09-04

### Added
- Packaging for distributable installers: a Windows installer (Inno Setup) and a portable Linux AppImage, alongside the existing raw-binary
  + desktop-entry install flow. See `packaging/README.md`.

## [0.2.0] - 2026-09-02

### Added
- Track titles that don't fit their label (Mini Player, the main window's status panel) now scroll in a looping marquee instead of being clipped.

### Changed
- UI overhaul: migrated the entire interface from tkinter/customtkinter to
  PySide6 (Qt), for better performance (batched waveform rendering, native
  window move/resize) especially on Linux. All features from 0.1.0 carry over unchanged; the tkinter UI has been removed.

- Mini Player: redesigned with a larger accent-colored play/pause button, and a thinner progress bar for a more modern look; layout reordered to controls, then track info.

## [0.1.0] - 2025-11-09

First release, built on tkinter/customtkinter.

### Added
- Playback controls: play/pause/stop/previous/next, volume/mute, repeat
  modes, waveform seekbar.
- Playlist management: add/remove/reorder, search/filter, save/load
  (M3U/M3U8), play-after-current, play-for-time.
- Browser view with drag-and-drop into the playlist and song preview.
- Live Audio Analysis panel: LUFS, peak, limiter activity, BPM, musical
  key, energy.
- Audio Effects: equalizer, compressor, spatializer, vocal remover,
  playback speed, channel mode.
- Playback Features: early track advance, fade in/out, silence detection,
  play on double-click.
- Playlist Generator: rule-based template builder (groups, subgroups,
  sources, BPM/key filters, ordering strategies).
- Track Information and Album Booklet Viewer dialogs.
- Mini Player, Light/Dark themes, and Preferences.

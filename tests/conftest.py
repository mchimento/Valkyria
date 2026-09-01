import pytest


@pytest.fixture(autouse=True)
def _isolate_settings_config_path(tmp_path, monkeypatch):
    """Never let a test's Settings object touch the real user config file.

    app/settings.py imports get_user_data_path directly into its own
    namespace, so Settings.config_path resolves it via
    app.settings.get_user_data_path at call time — patching that reference
    (not app.paths.get_user_data_path) redirects every Settings() instance
    constructed during a test to a throwaway per-test directory, even if a
    test forgets to mock settings.save() itself.
    """
    import app.settings as settings_module

    monkeypatch.setattr(settings_module, "get_user_data_path", lambda: tmp_path)


@pytest.fixture(autouse=True)
def _guard_dj_bpm_estimate_off_main_thread(monkeypatch):
    """Skip heavy audio-analysis work (numba/librosa init, which can crash
    on Windows when run off the main thread) if dj_bpm_estimate is invoked
    from a background worker thread during a test."""
    import importlib
    import threading

    meta = importlib.import_module('audio.metadata')
    orig_dj = getattr(meta, 'dj_bpm_estimate', None)

    def _safe_dj_bpm_estimate(y, sr):
        if threading.current_thread() is not threading.main_thread():
            return None
        if orig_dj is None:
            return None
        return orig_dj(y, sr)

    monkeypatch.setattr(meta, 'dj_bpm_estimate', _safe_dj_bpm_estimate, raising=False)
    yield

import pytest


@pytest.fixture(autouse=True)
def _isolate_settings_config_path(tmp_path, monkeypatch):
    """Never let a test's Settings object touch the real user config file.

    app/settings.py imports get_user_data_path directly into its own
    namespace, so Settings.config_path resolves it via
    app.settings.get_user_data_path at call time — patching that reference
    (not app.paths.get_user_data_path) redirects every Settings() instance
    constructed during a test to a throwaway per-test directory, even if a
    test forgets to mock settings.save() itself. The existing Tk test
    suite (tests/test_settings.py) already does this per-test via
    PropertyMock on Settings.config_path; this is the same protection
    applied blanket so newly added tests can't regress it (confirmed they
    had: several ui_qt tests were writing straight into the real
    ~/.valkyria/config.json before this fixture existed).
    """
    import app.settings as settings_module

    monkeypatch.setattr(settings_module, "get_user_data_path", lambda: tmp_path)


# Provide a test-level safe_after override so worker threads that post back to
# Tk don't require a running Tk mainloop in unit tests. This keeps tests
# deterministic without modifying production code.

@pytest.fixture(autouse=True)
def _patch_audio_bpm_safe_after(monkeypatch):
    def _test_safe_after(root, delay, func, *args, **kwargs):
        try:
            if hasattr(root, 'after'):
                try:
                    return root.after(delay, func, *args)
                except Exception:
                    # Fall back to direct call if Tk can't register callbacks
                    pass
        except Exception:
            pass
        return func(*args, **kwargs)

    # Import the module and set attribute non-raising so the fixture works
    # even if the production module doesn't define _safe_after (keeps tests robust
    # against local or historical reversions).
    import importlib
    bpm_mod = importlib.import_module('audio.bpm')
    monkeypatch.setattr(bpm_mod, '_safe_after', _test_safe_after, raising=False)

    # Also provide a test-time fallback for tkinter's after to avoid RuntimeError
    # when background threads call root.after without a running mainloop. We patch
    # the underlying class (tk.Misc) so instances inherit the behavior. This is
    # intentionally conservative and only applied in tests.
    try:
        import tkinter as tk
        def _test_tk_after(self, delay, func, *args, **kwargs):
            try:
                # Try original behavior first (if mainloop is active)
                return original_after(self, delay, func, *args, **kwargs)
            except Exception:
                # Fallback: call directly
                return func(*args, **kwargs)

        # Replace only if attribute exists; save original if present
        original_after = getattr(tk.Misc, 'after', None)
        monkeypatch.setattr(tk.Misc, 'after', _test_tk_after, raising=False)

        # Patch tkinter.Tk to retry a few times to handle intermittent Tcl init failures.
        # Use a subclass wrapper so it remains a proper type for isinstance checks
        # (some third-party widgets perform isinstance(..., tkinter.Tk)).
        original_Tk = getattr(tk, 'Tk', None)
        if original_Tk is not None:
            class _RetryingTk(original_Tk):
                def __init__(self, *a, **kw):
                    import time
                    last_exc = None
                    for _ in range(3):
                        try:
                            super().__init__(*a, **kw)
                            return
                        except Exception as e:
                            last_exc = e
                            time.sleep(0.05)
                    # Final attempt (let exception propagate)
                    super().__init__(*a, **kw)

            monkeypatch.setattr(tk, 'Tk', _RetryingTk, raising=False)

        # Prevent heavy audio-analysis imports from running inside background worker
        # threads during tests (these can trigger numba/librosa init that crashes
        # on Windows when executed on non-main threads). We wrap the real
        # dj_bpm_estimate to no-op on non-main threads while preserving behavior
        # for direct test calls on the main thread.
        try:
            import importlib as _importlib
            import threading as _threading
            _meta = _importlib.import_module('audio.metadata')
            _orig_dj = getattr(_meta, 'dj_bpm_estimate', None)

            def _safe_dj_bpm_estimate(y, sr):
                # If called from a background worker thread, skip heavy work
                if _threading.current_thread() is not _threading.main_thread():
                    return None
                if _orig_dj is None:
                    return None
                return _orig_dj(y, sr)

            monkeypatch.setattr(_meta, 'dj_bpm_estimate', _safe_dj_bpm_estimate, raising=False)
        except Exception:
            # If anything goes wrong, don't break tests - this is a best-effort
            pass
    except Exception:
        # Tk not available in this environment; nothing to patch
        pass

    yield

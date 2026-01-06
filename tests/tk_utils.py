"""Utilities for checking Tk availability in tests.

Provides a reliable check to determine whether Tcl/Tk is usable in the
current environment (works on Windows and Unix-like systems). Tests can
import HAS_TK to decide whether to skip GUI tests.
"""
import tkinter as tk
import os
import sys


def has_tk():
    """Return True if a tk.Tk() instance can be created and destroyed.

    If TCL_LIBRARY is not set, try to set it from the Python exec prefix
    (common for Windows/MS Store installs) to reduce flaky failures.
    """
    if 'TCL_LIBRARY' not in os.environ:
        candidate = os.path.join(sys.exec_prefix, 'tcl', 'tcl8.6')
        if os.path.exists(os.path.join(candidate, 'init.tcl')):
            os.environ['TCL_LIBRARY'] = candidate
    try:
        root = tk.Tk()
        root.withdraw()
        # Also check ttk/theme subsystem to ensure full usable Tk/Ttk (themes may
        # be missing on some broken installs). If importing ttk or querying
        # theme names fails, consider Tk unusable.
        try:
            import tkinter.ttk as ttk
            try:
                style = ttk.Style(root)
                # Access theme_names to force loading of theme files
                _ = style.theme_names()
            except Exception:
                # Fail if ttk themes cannot be loaded
                root.destroy()
                return False
        except Exception:
            # If ttk import fails, treat as unusable
            root.destroy()
            return False
        root.destroy()
        return True
    except Exception:
        return False


# Module constant for convenience
HAS_TK = has_tk()


def skip_if_no_tk(testcase):
    """Call this in a unittest setUp to skip the test if Tk isn't available.

    Example:
        def setUp(self):
            tests.tk_utils.skip_if_no_tk(self)

    This checks Tk availability at call time (not import time) to avoid
    flakiness when Tcl/Tk initialization intermittently fails during test runs.
    """
    if not has_tk():
        # Raise SkipTest from unittest
        import unittest
        raise unittest.SkipTest("Tkinter not available in this environment")

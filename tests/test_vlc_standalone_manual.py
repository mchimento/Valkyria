import unittest
import sys
import os
from pathlib import Path
import ctypes

# Add project root to sys.path
# tests/ -> project_root
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

plugins_dir = project_root / 'plugins'

# Setup environment variables
os.environ['PYTHON_VLC_LIB_PATH'] = str(plugins_dir / 'libvlc.dll')
os.environ['VLC_PLUGIN_PATH'] = str(plugins_dir)
os.environ['PATH'] = str(plugins_dir) + os.pathsep + os.environ.get('PATH', '')

if hasattr(os, 'add_dll_directory'):
    try:
        os.add_dll_directory(str(plugins_dir))
    except Exception:
        pass

import vlc

@unittest.skipUnless(sys.platform == 'win32', "Standalone bundle test is Windows-only")
class TestVLCStandaloneManual(unittest.TestCase):
    def test_config_plugins_dir(self):
        self._test_config("plugins_dir", plugins_dir)

    def _test_config(self, name, plugin_path):
        print(f"\n--- Testing Configuration: {name} ---")
        if plugin_path:
            os.environ['VLC_PLUGIN_PATH'] = str(plugin_path)
            print(f"Set VLC_PLUGIN_PATH: {plugin_path}")
        else:
            if 'VLC_PLUGIN_PATH' in os.environ:
                del os.environ['VLC_PLUGIN_PATH']
            print("Unset VLC_PLUGIN_PATH")

        # vlc.Instance creates a new instance each time, calling libvlc_new.
        instance = vlc.Instance()
        self.assertIsNotNone(instance, "VLC Instance is None")
        print("SUCCESS: VLC Instance created successfully.")

if __name__ == '__main__':
    unittest.main()

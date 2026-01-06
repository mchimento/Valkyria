"""
BPM-related utilities and logic.
"""

import logging
from audio.metadata import analyze_bpm, write_bpm

logger = logging.getLogger(__name__)

import logging
import multiprocessing
import queue
import threading
import time
from audio.metadata import analyze_bpm, write_bpm

logger = logging.getLogger(__name__)

def on_bpm_updated(filepath, state):
    """Handle BPM update notifications by refreshing status if current track matches."""
    try:
        idx = state.current_index
        if idx is not None and idx < len(state.playlist):
            current_path = state.playlist[idx]
            if current_path == filepath:
                state.update_meta_with_temp_bpm()
    except Exception:
        # Fail silently - BPM updates are not critical
        pass

def _bpm_process_worker(input_queue, output_queue):
    """Function to run in the background process."""
    while True:
        try:
            task = input_queue.get()
            if task is None:
                break

            task_type, filepath, args = task

            try:
                if task_type == 'analyze':
                    result = analyze_bpm(filepath)
                    output_queue.put(('analyze', filepath, result, None))
                elif task_type == 'save':
                    bpm_value = args[0]
                    write_bpm(filepath, bpm_value)
                    output_queue.put(('save', filepath, True, None))
            except Exception as e:
                output_queue.put((task_type, filepath, None, str(e)))

        except Exception:
            break

class BPMAnalysisManager:
    """Manages background BPM analysis and saving using a separate process to avoid blocking the audio thread."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.input_queue = multiprocessing.Queue()
        self.output_queue = multiprocessing.Queue()
        self.process = None
        self.result_thread = None
        self.callbacks = {}  # key: (task_type, filepath), value: callback_function
        self.running = False

    def start(self):
        """Start the background process and result listener."""
        if self.running:
            return

        self.running = True
        self.process = multiprocessing.Process(
            target=_bpm_process_worker,
            args=(self.input_queue, self.output_queue),
            daemon=True
        )
        self.process.start()

        self.result_thread = threading.Thread(target=self._result_listener, daemon=True)
        self.result_thread.start()
        logger.info("BPM Analysis Manager started")

    def _result_listener(self):
        """Listen for results from the background process."""
        while self.running:
            try:
                try:
                    # Timeout to check for running flag periodically
                    result = self.output_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                task_type, filepath, data, error = result

                # Find callback
                key = (task_type, filepath)
                callback_info = self.callbacks.pop(key, None)

                if callback_info:
                    callback, root_widget = callback_info

                    if root_widget:
                        # Schedule callback on main thread
                        if task_type == 'analyze':
                            root_widget.after(0, callback, filepath, data)
                        elif task_type == 'save':
                            root_widget.after(0, callback, filepath, data)

            except Exception as e:
                logger.error(f"Error in BPM result listener: {e}")

    def submit_analysis(self, filepath, callback, root_widget):
        """Submit a BPM analysis task."""
        if not self.running:
            self.start()

        key = ('analyze', filepath)
        # Store callback
        self.callbacks[key] = (callback, root_widget)
        # Send task
        self.input_queue.put(('analyze', filepath, None))

    def submit_save(self, filepath, bpm_value, callback, root_widget):
        """Submit a BPM save task."""
        if not self.running:
            self.start()

        key = ('save', filepath)
        self.callbacks[key] = (callback, root_widget)
        self.input_queue.put(('save', filepath, [bpm_value]))

    def shutdown(self):
        """Shutdown the background process."""
        self.running = False
        if self.process:
            self.input_queue.put(None)
            self.process.join(timeout=1.0)
            if self.process.is_alive():
                self.process.terminate()

# Global accessor
bpm_manager = BPMAnalysisManager.get_instance()

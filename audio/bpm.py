"""
BPM-related utilities and logic.
"""

import logging
from audio.metadata import analyze_bpm, write_bpm

logger = logging.getLogger(__name__)
import multiprocessing
import queue
import threading
import time
from audio.metadata import analyze_bpm, write_bpm, analyze_key, write_key

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

def _analysis_process_worker(input_queue, output_queue):
    """Function to run in the background process."""
    while True:
        try:
            task = input_queue.get()
            if task is None:
                break

            task_type, filepath, args = task

            try:
                if task_type == 'analyze_bpm':
                    result = analyze_bpm(filepath)
                    output_queue.put(('analyze_bpm', filepath, result, None))
                elif task_type == 'save_bpm':
                    bpm_value = args[0]
                    write_bpm(filepath, bpm_value)
                    output_queue.put(('save_bpm', filepath, True, None))
                elif task_type == 'analyze_key':
                    result = analyze_key(filepath)
                    output_queue.put(('analyze_key', filepath, result, None))
                elif task_type == 'save_key':
                    key_value = args[0]
                    write_key(filepath, key_value)
                    output_queue.put(('save_key', filepath, True, None))
            except Exception as e:
                output_queue.put((task_type, filepath, None, str(e)))

        except Exception:
            break

class AnalysisManager:
    """Manages background audio analysis (BPM, Key) and saving using a separate process."""

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
        self.callbacks = {}  # key: (task_type, filepath), value: (callback, root_widget)
        self.running = False

    def start(self):
        """Start the background process and result listener."""
        if self.running:
            return

        self.running = True
        self.process = multiprocessing.Process(
            target=_analysis_process_worker,
            args=(self.input_queue, self.output_queue),
            daemon=True
        )
        self.process.start()

        self.result_thread = threading.Thread(target=self._result_listener, daemon=True)
        self.result_thread.start()
        logger.info("Analysis Manager started")

    def _result_listener(self):
        """Listen for results from the background process."""
        # Import metadata_extractor lazily to avoid import cycles at module init
        try:
            from audio.metadata import metadata_extractor
        except Exception:
            metadata_extractor = None

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
                    callback, scheduler = callback_info

                    if scheduler:
                        # Schedule callback on the caller's own thread (Tk's .after(), a Qt Signal, etc)
                        scheduler(callback, filepath, data)

                    # If this was a save operation and it succeeded, update metadata cache
                    # and notify listeners within the main thread context if possible
                    if task_type in ('save_bpm', 'save_key') and data:
                        try:
                            if scheduler:
                                def _notify():
                                    try:
                                        if metadata_extractor:
                                            metadata_extractor.update_cache(filepath)

                                            if task_type == 'save_bpm':
                                                metadata_extractor._notify_bpm_listeners(filepath)
                                            else:
                                                metadata_extractor._notify_key_listeners(filepath)
                                    except Exception:
                                        pass
                                try:
                                    scheduler(_notify)
                                except Exception:
                                    # If scheduling fails, call directly as fallback
                                    _notify()
                            else:
                                # No scheduler provided - attempt direct update/notify
                                if metadata_extractor:
                                    metadata_extractor.update_cache(filepath)
                                    if task_type == 'save_bpm':
                                        metadata_extractor._notify_bpm_listeners(filepath)
                                    else:
                                        metadata_extractor._notify_key_listeners(filepath)
                        except Exception:
                            pass

            except Exception as e:
                logger.error(f"Error in Analysis result listener: {e}")

    def submit_bpm_analysis(self, filepath, callback, scheduler):
        """Submit a BPM analysis task. scheduler(func, *args) runs func on the caller's thread."""
        if not self.running:
            self.start()

        key = ('analyze_bpm', filepath)
        self.callbacks[key] = (callback, scheduler)
        self.input_queue.put(('analyze_bpm', filepath, None))

    def submit_bpm_save(self, filepath, bpm_value, callback, scheduler):
        """Submit a BPM save task."""
        if not self.running:
            self.start()

        key = ('save_bpm', filepath)
        self.callbacks[key] = (callback, scheduler)
        self.input_queue.put(('save_bpm', filepath, [bpm_value]))

    def submit_key_analysis(self, filepath, callback, scheduler):
        """Submit a Key analysis task."""
        if not self.running:
            self.start()

        key = ('analyze_key', filepath)
        self.callbacks[key] = (callback, scheduler)
        self.input_queue.put(('analyze_key', filepath, None))

    def submit_key_save(self, filepath, key_value, callback, scheduler):
        """Submit a Key save task."""
        if not self.running:
            self.start()

        key = ('save_key', filepath)
        self.callbacks[key] = (callback, scheduler)
        self.input_queue.put(('save_key', filepath, [key_value]))

    def shutdown(self):
        """Shutdown the background process. Guarantees the process is
        actually dead before returning — otherwise Python's own atexit
        multiprocessing cleanup joins remaining daemon children with no
        timeout at all, which can hang the whole interpreter on exit if
        a long-running analysis (analyze_bpm/analyze_key on a real audio
        file) is still in flight when this is called."""
        self.running = False
        if self.process:
            try:
                self.input_queue.put(None)
            except Exception:
                pass
            self.process.join(timeout=1.0)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1.0)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1.0)

# Global accessor - aliased for backward compat if needed, but renamed to analysis_manager
analysis_manager = AnalysisManager.get_instance()
bpm_manager = analysis_manager  # Alias for existing code until updated

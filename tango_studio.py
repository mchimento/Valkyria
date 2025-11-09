#!/usr/bin/env python3
"""
Audio Reproducer Tool
- Tkinter GUI
- python-vlc backend

The tools requires VLC media player to be installed on the system.
"""

import os
import vlc
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

SUPPORTED_EXTS = ('.mp3', '.wav', '.flac', '.ogg', '.m4a')


def parse_m3u(path):
    items = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if not (line.startswith('http://') or line.startswith('https://')):
                base = Path(path).parent
                p = (base / line).resolve()
                items.append(str(p))
            else:
                items.append(line)
    return items


def write_m3u(path, entries):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for e in entries:
            title = os.path.basename(e)
            f.write(f'#EXTINF:-1,{title}\n{e}\n')


class AudioPlayerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audio Reproducer")
        self.geometry("1000x500")

        self.instance = vlc.Instance()
        self.player = None
        self.media = None

        self.playlist = []
        self.browser_files = []
        self.current_index = None
        self.current_playlist_path = None

        self.volume_var = tk.IntVar(value=80)
        self.status = tk.StringVar(value='Ready')
        self.time_var = tk.StringVar(value='00:00 / 00:00')

        self._build_ui()

        self.after(500, self.update_time)

    def _build_ui(self):
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open File...", command=self.open_file)        
        filemenu.add_command(label="Open Folder...", command=self.open_folder)
        filemenu.add_command(label="Open Playlist (M3U/M3U8)...", command=self.open_playlist)
        filemenu.add_separator()
        filemenu.add_command(label="Save Playlist", command=self.save_playlist)
        filemenu.add_command(label="Save Playlist As...", command=self.save_playlist_as)
        filemenu.add_separator()
        filemenu.add_command(label="Quit", command=self.quit_app)
        menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=menubar)

        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # --- Left: Playlist ---
        left_frame = ttk.Frame(main)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(left_frame, text="Playlist (Queue)").pack(anchor=tk.W)
        self.playlist_box = tk.Listbox(left_frame, selectmode=tk.SINGLE)
        self.playlist_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.playlist_box.bind('<Double-1>', self.on_playlist_double)
        self.playlist_box.bind('<Delete>', self.remove_selected_from_playlist)

        # --- Middle: Buttons ---
        mid_frame = ttk.Frame(main)
        mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        ttk.Button(mid_frame, text="Browse Files", command=self.open_folder).pack(pady=5)
        ttk.Button(mid_frame, text="<- Add", command=self.add_selected_to_playlist).pack(pady=10)

        # --- Right: Browser ---
        right_frame = ttk.Frame(main)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(right_frame, text="Browser (Folder Contents)").pack(anchor=tk.W)
        self.browser_box = tk.Listbox(right_frame, selectmode=tk.EXTENDED)
        self.browser_box.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.browser_box.bind('<Delete>', self.remove_selected_from_browser)

        # --- Bottom controls ---
        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=8, pady=6)

        ttk.Button(controls, text='Play', command=self.play_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text='Pause/Resume', command=self.pause_resume).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text='Stop', command=self.stop).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text='Previous', command=self.previous_track).pack(side=tk.LEFT, padx=4)
        ttk.Button(controls, text='Next', command=self.next_track).pack(side=tk.LEFT, padx=4)

        ttk.Label(controls, text='Volume').pack(side=tk.LEFT, padx=(20, 4))
        ttk.Scale(controls, from_=0, to=100, variable=self.volume_var, command=self.on_volume).pack(side=tk.LEFT)

        ttk.Label(controls, textvariable=self.time_var).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(self, textvariable=self.status).pack(side=tk.BOTTOM, anchor=tk.W, padx=8)

    # -------- File Menu Actions --------

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('Audio files', '*.mp3 *.wav *.flac *.ogg *.m4a'), ('All files', '*.*')])
        if path:
            self.playlist = [path]
            self.current_index = 0
            self.current_playlist_path = None
            self._refresh_playlist_box()
            self.play_current()

    def open_playlist(self):
        path = filedialog.askopenfilename(filetypes=[('M3U Playlist', '*.m3u *.m3u8'), ('All files', '*.*')])
        if path:
            try:
                items = parse_m3u(path)
                if not items:
                    messagebox.showinfo('Playlist', 'No entries found in playlist')
                    return
                self.playlist = items
                self.current_index = 0
                self.current_playlist_path = path
                self._refresh_playlist_box()
                self.play_current()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to load playlist: {e}')

    def open_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.playlist.clear()
            self.playlist_box.delete(0, tk.END)
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(SUPPORTED_EXTS):
                        full_path = os.path.join(root, f)
                        self.playlist.append(full_path)
                        self.playlist_box.insert(tk.END, os.path.basename(f))
            self.status.set(f'Loaded {len(self.playlist)} files into playlist')
            self.current_index = 0

    def add_selected_to_playlist(self):
        selections = self.browser_box.curselection()
        count = 0
        for i in selections:
            file_path = self.browser_files[i]
            if file_path not in self.playlist:
                self.playlist.append(file_path)
                count += 1
        self._refresh_playlist_box()
        self.status.set(f'Added {count} files to playlist')

    def remove_selected_from_playlist(self, event=None):
        sel = self.playlist_box.curselection()
        if not sel:
            return
        index = sel[0]
        removed = self.playlist.pop(index)
        self._refresh_playlist_box()
        self.status.set(f'Removed from playlist: {os.path.basename(removed)}')


    def remove_selected_from_browser(self, event=None):
        sels = list(self.browser_box.curselection())[::-1]
        for i in sels:
            removed = self.browser_files.pop(i)
            self.browser_box.delete(i)
        if sels:
            self.status.set(f'Removed {len(sels)} items from browser list')

    def save_playlist(self):
        if not self.current_playlist_path:
            return self.save_playlist_as()
        try:
            write_m3u(self.current_playlist_path, self.playlist)
            self.status.set(f'Saved playlist: {self.current_playlist_path}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save playlist: {e}')

    def save_playlist_as(self):
        path = filedialog.asksaveasfilename(defaultextension='.m3u8', filetypes=[('M3U8 Playlist', '*.m3u8'), ('M3U Playlist', '*.m3u')])
        if path:
            try:
                write_m3u(path, self.playlist)
                self.current_playlist_path = path
                self.status.set(f'Saved playlist: {path}')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to save playlist: {e}')

    def quit_app(self):
        self.stop()
        self.destroy()

    # -------- Playlist --------

    def _refresh_playlist_box(self):
        self.playlist_box.delete(0, tk.END)
        for p in self.playlist:
            self.playlist_box.insert(tk.END, os.path.basename(p))

    # -------- Playback --------

    def play_selected(self):
        sel = self.playlist_box.curselection()
        if sel:
            self.current_index = sel[0]
        elif self.current_index is None and self.playlist:
            self.current_index = 0
        self.play_current()

    def play_current(self):
        if self.current_index is None or not self.playlist:
            self.status.set('No track to play')
            return
        if self.current_index < 0 or self.current_index >= len(self.playlist):
            self.status.set('Index out of range')
            return

        path = self.playlist[self.current_index]
        if not os.path.exists(path):
            messagebox.showerror('Playback error', f'File not found: {path}')
            return

        if self.player:
            try:
                self.player.stop()
            except Exception:
                pass

        self.media = self.instance.media_new(path)
        self.player = self.instance.media_player_new()
        self.player.set_media(self.media)
        self.player.audio_set_volume(self.volume_var.get())

        em = self.player.event_manager()
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_track_end)

        self.player.play()
        self.status.set(f'Playing: {os.path.basename(path)}')
        self._highlight_current()

    def _on_track_end(self, event):
        self.after(100, self._play_next_after_end)

    def _play_next_after_end(self):
        if self.current_index is None:
            return
        if self.current_index + 1 < len(self.playlist):
            self.current_index += 1
            self.play_current()
        else:
            self.status.set('End of playlist')

    def pause_resume(self):
        if not self.player:
            return
        state = self.player.get_state()
        if state == vlc.State.Playing:
            self.player.pause()
            self.status.set('Paused')
        elif state in (vlc.State.Paused, vlc.State.Stopped, vlc.State.NothingSpecial):
            self.player.play()
            self.status.set('Resumed')

    def stop(self):
        if self.player:
            try:
                self.player.stop()
            except Exception:
                pass
        self.status.set('Stopped')

    def previous_track(self):
        if not self.playlist:
            return
        if self.current_index is None:
            self.current_index = 0
        else:
            self.current_index = max(0, self.current_index - 1)
        self.play_current()

    def next_track(self):
        if not self.playlist:
            return
        if self.current_index is None:
            self.current_index = 0
        else:
            self.current_index = min(len(self.playlist) - 1, self.current_index + 1)
        self.play_current()

    def on_volume(self, value):
        if self.player:
            try:
                self.player.audio_set_volume(int(float(value)))
            except Exception:
                pass

    def update_time(self):
        if self.player and self.media:
            length = self.player.get_length() // 1000  # ms to sec
            current = self.player.get_time() // 1000
            if length <= 0: length = 1
            current_min, current_sec = divmod(current, 60)
            length_min, length_sec = divmod(length, 60)
            self.time_var.set(f'{current_min:02d}:{current_sec:02d} / {length_min:02d}:{length_sec:02d}')
        else:
            self.time_var.set('00:00 / 00:00')
        self.after(500, self.update_time)

    def _highlight_current(self):
        self.playlist_box.selection_clear(0, tk.END)
        if self.current_index is not None:
            self.playlist_box.selection_set(self.current_index)
            self.playlist_box.see(self.current_index)

    def on_playlist_double(self, event):
        sel = self.playlist_box.curselection()
        if sel:
            self.current_index = sel[0]
            self.play_current()


if __name__ == '__main__':
    app = AudioPlayerApp()
    app.mainloop()
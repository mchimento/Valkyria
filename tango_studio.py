#!/usr/bin/env python3
"""
Tango Studio
- Tkinter GUI
- python-vlc backend

The tools requires VLC media player to be installed on the system.
"""

import os
import vlc
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import random
import time

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

class DraggableListbox(tk.Listbox):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.bind('<Button-1>', self.set_current)
        self.bind('<B1-Motion>', self.shift_selection)
        self.curIndex = None
        self.on_reorder = None

    def set_current(self, event):
        self.curIndex = self.nearest(event.y)
        # Preserve selection highlight
        self.selection_clear(0, tk.END)
        self.selection_set(self.curIndex)

    def shift_selection(self, event):
        i = self.nearest(event.y)
        if i == self.curIndex:
            return
        self.move_item(self.curIndex, i)
        self.curIndex = i
        # Preserve selection highlight after move
        self.selection_clear(0, tk.END)
        self.selection_set(self.curIndex)

    def move_item(self, from_idx, to_idx):
        if from_idx < 0 or from_idx >= self.size():
            return
        item = self.get(from_idx)
        self.delete(from_idx)
        self.insert(to_idx, item)
        if self.on_reorder:
            self.on_reorder(from_idx, to_idx)

class AudioPlayerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tango Studio")
        self.geometry("1000x500")

        self.configure(bg="#d9d9d9")

        # tool look and feel
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', font=('Segoe UI', 10), padding=6, background="#188BE9", foreground='white')
        style.map('TButton', background=[('active', "#5DADE2")])
        style.configure('Treeview', font=('Segoe UI', 10), rowheight=25)
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))

        # VLC setup
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new() # persistent player
        self.media = None
        em = self.player.event_manager() # Attach end-of-track event once
        em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_track_end)

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

        playlist_menu = tk.Menu(menubar, tearoff=0)
        playlist_menu.add_command(label="Shuffle", command=self.shuffle_playlist)
        playlist_menu.add_command(label="Sort Alphabetically", command=self.sort_playlist)
        playlist_menu.add_separator()
        playlist_menu.add_command(label="Clear Playlist", command=self.clear_playlist)
        menubar.add_cascade(label="Playlist", menu=playlist_menu)
        self.config(menu=menubar)

        main = ttk.Frame(self)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # --- Left: Playlist ---
        left_frame = ttk.Frame(main, padding=(5,5))
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.playlist_tree = ttk.Treeview(left_frame, columns=('Playlist',), show='headings', selectmode='browse')
        self.playlist_tree.tag_configure('current', background='#FFF59D')  # Soft yellow
        self.playlist_tree.heading('Playlist', text='Playlist')
        self.playlist_tree.pack(fill=tk.BOTH, expand=True)
        self.playlist_tree.bind('<Double-1>', self.on_playlist_double)
        self.playlist_tree.bind('<Delete>', self.remove_selected_from_playlist)
        self.playlist_tree.bind('<ButtonPress-1>', self._on_drag_start)
        self.playlist_tree.bind('<B1-Motion>', self._on_drag_motion)
        self.dragged_item = None        

        # --- Right: Browser ---
        right_frame = ttk.Frame(main, padding=(5,5))
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.browser_tree = ttk.Treeview(right_frame, columns=('Song',), show='headings', selectmode='extended')
        self.browser_tree.heading('Song', text='Songs')
        self.browser_tree.pack(fill=tk.BOTH, expand=True)
        self.browser_tree.bind('<Delete>', self.remove_selected_from_browser)

        # --- Middle: Buttons ---
        mid_frame = ttk.Frame(main)
        mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=4, anchor=tk.N)

        ttk.Button(mid_frame, text="Browse Songs", command=self.open_folder_browse).pack(pady=2)
        ttk.Button(mid_frame, text="<- Add", command=self.add_selected_to_playlist).pack(pady=5)

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
            self.update_playlist_tree()
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
                self.update_playlist_tree()
                self.play_current()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to load playlist: {e}')

    def open_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            for item in self.playlist_tree.get_children():
                self.playlist_tree.delete(item)
            self.playlist.clear()
            for f in os.listdir(folder):
                if f.lower().endswith(SUPPORTED_EXTS):
                    full_path = os.path.join(folder, f)
                    self.playlist.append(full_path)
                    self.playlist_tree.insert('', tk.END, values=(f,))
            self.status.set(f'Loaded {len(self.playlist)} files into playlist')
            self.current_index = 0

    def open_folder_browse(self):
        folder = filedialog.askdirectory()
        if folder:
            for item in self.browser_tree.get_children():
                self.browser_tree.delete(item)
            self.browser_files.clear()
            for f in os.listdir(folder):
                if f.lower().endswith(SUPPORTED_EXTS):
                    full_path = os.path.join(folder, f)
                    self.browser_files.append(full_path)
                    self.browser_tree.insert('', tk.END, values=(f,))
            self.status.set(f'Loaded {len(self.browser_files)} files from folder')

    def add_selected_to_playlist(self):
        selections = self.browser_tree.selection()
        for sel in selections:
            idx = self.browser_tree.index(sel)
            fpath = self.browser_files[idx]
            if fpath not in self.playlist:
                self.playlist.append(fpath)        
        self.update_playlist_tree()        

    def remove_selected_from_playlist(self, event=None):
        selections = self.playlist_tree.selection()
        if not selections:
            return

        removed_indices = sorted([self.playlist_tree.index(sel) for sel in selections], reverse=True)

        for idx in removed_indices:
            self.playlist.pop(idx)

        if self.current_index is not None:
            # If the current song itself was removed, reset highlight
            if self.current_index in removed_indices:
                self.current_index = None
            else:
                # Count how many removed indices were before current
                shift = sum(1 for i in removed_indices if i < self.current_index)
                self.current_index -= shift

        self.update_playlist_tree()
        
    def remove_selected_from_browser(self, event=None):
        selections = self.browser_tree.selection()
        for sel in selections[::-1]:
            idx = self.browser_tree.index(sel)
            self.browser_files.pop(idx)
            self.browser_tree.delete(sel)

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
    def reorder_playlist(self, from_idx, to_idx):
        if from_idx < 0 or from_idx >= len(self.playlist) or to_idx < 0 or to_idx >= len(self.playlist):
            return
        item = self.playlist.pop(from_idx)
        self.playlist.insert(to_idx, item)
        if self.current_index == from_idx:
            self.current_index = to_idx
        elif from_idx < self.current_index <= to_idx:
            self.current_index -= 1
        elif to_idx <= self.current_index < from_idx:
            self.current_index += 1

    def update_playlist_tree(self, highlight_current=True):
        for item in self.playlist_tree.get_children():
            self.playlist_tree.delete(item)
        for f in self.playlist:
            self.playlist_tree.insert('', tk.END, values=(os.path.basename(f),))
        if highlight_current:
            self.highlight_current_song(self.current_index)

    def update_browser_tree(self):
        for item in self.browser_tree.get_children():
            self.browser_tree.delete(item)
        for f in self.browser_files:
            self.browser_tree.insert('', tk.END, values=(os.path.basename(f),))

    # ----------------- Drag & Drop -----------------
    def _on_drag_start(self, event):
        item = self.playlist_tree.identify_row(event.y)
        if item:
            self.dragged_item = self.playlist_tree.index(item)

    def _on_drag_motion(self, event):
        if self.dragged_item is None:
            return
        item = self.playlist_tree.identify_row(event.y)
        if not item:
            return
        index = self.playlist_tree.index(item)
        if index != self.dragged_item:
            self.playlist[self.dragged_item], self.playlist[index] = self.playlist[index], self.playlist[self.dragged_item]
            self.update_playlist_tree()
            self.dragged_item = index

    # -------- Playback --------
    def fade_out_and_play(self, index):
        if self.player is not None and self.player.is_playing():
            vol = self.player.audio_get_volume()
            for v in range(vol, -1, -5):
                self.player.audio_set_volume(v)
                self.update()
                time.sleep(0.01)

        if index < 0 or index >= len(self.playlist):
            return
        self.current_index = index
        self.highlight_current_song(index)
        
        path = self.playlist[index]
        self.media = self.instance.media_new(path)
        if self.player is None:
            self.player = self.instance.media_player_new()
        self.player.set_media(self.media)
        self.player.audio_set_volume(self.volume_var.get())

        self.player.play()
        self.status.set(f'Playing: {os.path.basename(path)}')

    def play_selected(self):
        sel = self.playlist_tree.selection()
        if sel:
            self.current_index = self.playlist_tree.index(sel[0])
        elif self.current_index is None and self.playlist:
            self.current_index = 0
        self.highlight_current_song(self.current_index)
        self.play_current()

    def play_current(self):
        if self.current_index is None or not self.playlist:
            self.status.set('No track to play')
            return
        path = self.playlist[self.current_index]
        if not os.path.exists(path):
            messagebox.showerror('Playback error', f'File not found: {path}')
            return
        if self.player.is_playing():
            self.player.stop()

        self.media = self.instance.media_new(path)
        self.player.set_media(self.media)
        self.player.audio_set_volume(self.volume_var.get())
        self.highlight_current_song(self.current_index)
        self.status.set(f'Playing: {os.path.basename(path)}')
        self.player.play()

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
        if self.current_index is not None and self.current_index - 1 >= 0:
            self.fade_out_and_play(self.current_index - 1)

    def next_track(self):        
        if not self.playlist:
            return
        if self.current_index is not None and self.current_index + 1 < len(self.playlist):
            self.fade_out_and_play(self.current_index + 1)        

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

    def highlight_current_song(self, index):
        for item in self.playlist_tree.get_children():
            self.playlist_tree.item(item, tags=())
        if index is not None and 0 <= index < len(self.playlist):
            item = self.playlist_tree.get_children()[index]
            self.playlist_tree.item(item, tags=('current',))            

    def on_playlist_double(self, event):
        sel = self.playlist_tree.selection()
        if sel:
            self.current_index = self.playlist_tree.index(sel[0])
            self.highlight_current_song(self.current_index)
            self.fade_out_and_play(self.current_index)

    # -------- Playlist operations --------

    def shuffle_playlist(self):
        current_song = None
        if self.current_index is not None and 0 <= self.current_index < len(self.playlist):
            current_song = self.playlist[self.current_index]

        random.shuffle(self.playlist)
        self.update_playlist_tree(False)

        if current_song in self.playlist:
            self.current_index = self.playlist.index(current_song)
            self.highlight_current_song(self.current_index)
        else:
            self.current_index = None

    def sort_playlist(self):
        current_song = None
        if self.current_index is not None and 0 <= self.current_index < len(self.playlist):
            current_song = self.playlist[self.current_index]

        self.playlist.sort(key=lambda f: os.path.basename(f).lower())
        self.update_playlist_tree(False)

        if current_song in self.playlist:
            self.current_index = self.playlist.index(current_song)
            self.highlight_current_song(self.current_index)
        else:
            self.current_index = None

    def clear_playlist(self):
        self.playlist.clear()
        self.update_playlist_tree()
        self.current_index = None


if __name__ == '__main__':
    app = AudioPlayerApp()
    app.mainloop()
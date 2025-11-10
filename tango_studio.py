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

        # Tooltip state
        self.tooltip = None
        self.tooltip_visible = False
        self.current_tooltip_item = None
        self.tooltip_after_id = None
        # Status restore timer id (used to restore status after temporary messages)
        self._status_restore_after_id = None
        
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
        self.dragged_index = None

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

        tree_container = ttk.Frame(left_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.playlist_tree = ttk.Treeview(tree_container, columns=('Playlist',), show='headings', selectmode='browse')        
        self.playlist_tree.heading('Playlist', text='Playlist')
        self.playlist_tree.column('Playlist', width=200, minwidth=100, stretch=True)
        self.playlist_tree.tag_configure('current', background='#FFF59D')  # Soft yellow        
        self.playlist_tree.grid(row=0, column=0, sticky='nsew')

        self.playlist_tree.bind('<Double-1>', self.on_playlist_double)
        self.playlist_tree.bind('<Delete>', self.remove_selected_from_playlist)
        self.playlist_tree.bind('<ButtonPress-1>', self._on_drag_start)
        self.playlist_tree.bind('<B1-Motion>', self._on_drag_motion)
        self.playlist_tree.bind('<ButtonRelease-1>', self._on_drag_end)
        self.playlist_tree.bind('<Enter>', lambda e: self._on_tree_enter(e, self.playlist_tree))
        self.playlist_tree.bind('<Leave>', self._on_tree_leave)
        self.playlist_tree.bind('<Motion>', lambda e: self._on_tree_motion(e, self.playlist_tree))
        self.dragged_item = None

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.playlist_tree.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        self.playlist_tree.configure(yscrollcommand=vsb.set)

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)  

        # --- Right: Browser ---
        right_frame = ttk.Frame(main, padding=(5,5))
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.browser_tree = ttk.Treeview(right_frame, columns=('Song',), show='headings', selectmode='extended')
        self.browser_tree.heading('Song', text='Songs')
        self.browser_tree.pack(fill=tk.BOTH, expand=True)
        self.browser_tree.bind('<Delete>', self.remove_selected_from_browser)
        self.browser_tree.bind('<Enter>', lambda e: self._on_tree_enter(e, self.browser_tree))
        self.browser_tree.bind('<Leave>', self._on_tree_leave)
        self.browser_tree.bind('<Motion>', lambda e: self._on_tree_motion(e, self.browser_tree))

        # --- Middle: Buttons ---
        mid_frame = ttk.Frame(main)
        mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=4, anchor=tk.N)

        ttk.Button(mid_frame, text="Browse Songs", command=self.open_folder_browse).pack(pady=2)
        ttk.Button(mid_frame, text="<- Add", command=self.add_selected_to_playlist).pack(pady=5)
        ttk.Button(mid_frame, text="<- Add below", command=self.add_selected_below_playlist).pack(pady=5)

        # --- Bottom controls ---
        bottom_frame = ttk.Frame(self, padding=(5,5))
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(side=tk.TOP, fill=tk.X)

        for text, cmd in [('Play', self.play_selected), ('Pause', self.pause_resume), ('Stop', self.stop), ('Previous', self.previous_track), ('Next', self.next_track)]:
            ttk.Button(button_frame, text=text, command=cmd).pack(side=tk.LEFT, padx=5, pady=10)

        ttk.Label(button_frame, textvariable=self.time_var).pack(side=tk.LEFT, padx=10)
        ttk.Label(button_frame, text="Volume:").pack(side=tk.LEFT)
        ttk.Scale(button_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.volume_var, command=self.set_volume).pack(side=tk.LEFT)

        ttk.Label(bottom_frame, textvariable=self.status, foreground='blue', font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=5)

    # -------- File Menu Actions --------
    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('Audio files', '*.mp3 *.wav *.flac *.ogg *.m4a'), ('All files', '*.*')])
        if path:
            self.playlist = [path]
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
            # Walk through folder and subfolders recursively
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(SUPPORTED_EXTS):
                        full_path = os.path.join(root, f)
                        self.playlist.append(full_path)
                        self.playlist_tree.insert('', tk.END, values=(f,))
            # Show a temporary status message and restore previous status after 3s
            self._set_temporary_status(f'Loaded {len(self.playlist)} files into playlist', 3000)

    def open_folder_browse(self):
        folder = filedialog.askdirectory()
        if folder:
            for item in self.browser_tree.get_children():
                self.browser_tree.delete(item)
            self.browser_files.clear()
            # Walk through folder and subfolders recursively
            for root, dirs, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(SUPPORTED_EXTS):
                        full_path = os.path.join(root, f)
                        self.browser_files.append(full_path)
                        self.browser_tree.insert('', tk.END, values=(f,))                                                
            # Use centralized temporary-status helper
            self._set_temporary_status(f'Loaded {len(self.browser_files)} files into browser', 3000)

    def add_selected_to_playlist(self):
        selections = self.browser_tree.selection()
        added = 0
        for sel in selections:
            idx = self.browser_tree.index(sel)
            fpath = self.browser_files[idx]
            if fpath not in self.playlist:
                self.playlist.append(fpath)
                added += 1
        self._set_temporary_status(f'Added {added} file(s) to the bottom of the playlist', 3000)
                
        self.update_playlist_tree()        

    def add_selected_below_playlist(self):
        """
        Insert selected browser files into the playlist immediately below the currently playing track.
        If no track is currently playing, append to the end of the playlist.
        Duplicate entries are skipped to match existing add behavior.
        """
        selections = self.browser_tree.selection()
        if not selections:
            return

        # Determine selected files in browser order
        sel_indices = sorted([self.browser_tree.index(s) for s in selections])
        files_to_add = [self.browser_files[i] for i in sel_indices]

        # Insert position: after current_index if present, otherwise at end
        if self.current_index is not None and 0 <= self.current_index < len(self.playlist):
            insert_pos = self.current_index + 1
        else:
            insert_pos = len(self.playlist)

        added = 0
        for fpath in files_to_add:
            if fpath in self.playlist:
                continue
            self.playlist.insert(insert_pos + added, fpath)
            added += 1

        if added:
            self.update_playlist_tree()
            self._set_temporary_status(f'Added {added} file(s) below current track', 3000)
        else:
            self._set_temporary_status('No new files added (duplicates skipped)', 3000)

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
            # Show temporary saved message
            self._set_temporary_status(f'Saved playlist: {self.current_playlist_path}', 3000)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save playlist: {e}')

    def save_playlist_as(self):
        path = filedialog.asksaveasfilename(defaultextension='.m3u8', filetypes=[('M3U8 Playlist', '*.m3u8'), ('M3U Playlist', '*.m3u')])
        if path:
            try:
                write_m3u(path, self.playlist)
                self.current_playlist_path = path
                # Show temporary saved message
                self._set_temporary_status(f'Saved playlist: {path}', 3000)
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

    def update_playlist_tree(self, highlight_current=True, preserve_selection=False):
        # Optionally store current selection
        selected_indices = []
        if preserve_selection:
            selected_items = self.playlist_tree.selection()
            selected_indices = [self.playlist_tree.index(i) for i in selected_items]

        self.playlist_tree.delete(*self.playlist_tree.get_children())
        for f in self.playlist:
            self.playlist_tree.insert('', tk.END, values=(os.path.basename(f), f))

        # Restore selection
        if preserve_selection:
            children = self.playlist_tree.get_children()
            for i in selected_indices:
                if i < len(children):
                    self.playlist_tree.selection_add(children[i])

    def update_browser_tree(self):
        for item in self.browser_tree.get_children():
            self.browser_tree.delete(item)
        for f in self.browser_files:
            self.browser_tree.insert('', tk.END, values=(os.path.basename(f),))

    # ----------------- Drag & Drop -----------------
    def _on_drag_start(self, event):
        row_id = self.playlist_tree.identify_row(event.y)
        if row_id:
            # Cancel any pending tooltip and hide it while dragging to avoid
            # scheduled tooltip callbacks referencing now-missing items.
            if self.tooltip_after_id:
                try:
                    self.after_cancel(self.tooltip_after_id)
                except Exception:
                    pass
                self.tooltip_after_id = None
            if self.tooltip:
                try:
                    self.tooltip.withdraw()
                except Exception:
                    pass
                self.tooltip_visible = False
                self.current_tooltip_item = None

            self.dragged_index = self.playlist_tree.index(row_id)

    def _on_drag_motion(self, event):
        if self.dragged_index is None:
            return

        target_row = self.playlist_tree.identify_row(event.y)
        if not target_row:
            return

        target_index = self.playlist_tree.index(target_row)
        if target_index == self.dragged_index:
            return

        # Swap playlist entries
        self.playlist.insert(target_index, self.playlist.pop(self.dragged_index))

        # Adjust current index if a song is playing and dragged song is current
        if self.current_index is not None:
            if self.dragged_index == self.current_index:
                self.current_index = target_index
            elif self.dragged_index < self.current_index <= target_index:
                self.current_index -= 1
            elif target_index <= self.current_index < self.dragged_index:
                self.current_index += 1

        # Update tree and preserve selection
        self.update_playlist_tree(preserve_selection=True)

        # Move selection highlight to follow dragged item
        children = self.playlist_tree.get_children()
        if target_index < len(children):
            self.playlist_tree.selection_set(children[target_index])
            self.playlist_tree.see(children[target_index])

        # Highlight current song if there is one playing
        if self.current_index is not None:
            self.highlight_current_song(self.current_index)

        self.dragged_index = target_index

    def _on_drag_end(self, event):
        """
        Called when mouse button is released after a drag.
        """
        # Clear dragging flag
        self.dragged_index = None

        # Cancel any leftover scheduled tooltip (we will re-evaluate immediately)
        if self.tooltip_after_id:
            try:
                self.after_cancel(self.tooltip_after_id)
            except Exception:
                pass
            self.tooltip_after_id = None

        # If the pointer is over the playlist_tree, synthesize a Motion
        # event so hover logic runs and may schedule/show a tooltip.
        try:
            tree = self.playlist_tree
            px = tree.winfo_pointerx()
            py = tree.winfo_pointery()
            rel_x = px - tree.winfo_rootx()
            rel_y = py - tree.winfo_rooty()
            if 0 <= rel_x <= tree.winfo_width() and 0 <= rel_y <= tree.winfo_height():
                tree.event_generate('<Motion>', x=rel_x, y=rel_y)
        except Exception:
            pass

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
            self.status.set('Ready')
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

    def set_volume(self, _=None):
        if self.player is not None:
            self.player.audio_set_volume(self.volume_var.get())

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

    # -------- Tooltip handling --------
    def _create_tooltip(self):
        if self.tooltip:
            return
        self.tooltip = tk.Toplevel(self)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry("+0+0")
        self.tooltip.configure(bg='lightyellow')
        self.tooltip_label = tk.Label(self.tooltip, justify=tk.LEFT,
                                    relief=tk.SOLID, borderwidth=1,
                                    font=("Segoe UI", 9), bg='lightyellow')
        self.tooltip_label.pack()
        self.tooltip.withdraw()

    def _on_tree_enter(self, event, tree):
        self._create_tooltip()
        
    def _on_tree_leave(self, event):
        # Cancel any pending show operations
        if self.tooltip_after_id:
            self.after_cancel(self.tooltip_after_id)
            self.tooltip_after_id = None
        
        # Hide tooltip immediately
        if self.tooltip:
            self.tooltip.withdraw()
            self.tooltip_visible = False
            self.current_tooltip_item = None

    def _schedule_tooltip_show(self, tree, item, filepath):
        # Cancel any existing scheduled show/hide
        if self.tooltip_after_id:
            self.after_cancel(self.tooltip_after_id)
        
        # If we're already showing this item, don't restart the timer
        if self.current_tooltip_item == item and self.tooltip_visible:
            return
            
        self.tooltip_after_id = self.after(600, lambda: self._show_tooltip(tree, item, filepath))
        
    def _show_tooltip(self, tree, item, filepath):
        self.tooltip_after_id = None
        self.current_tooltip_item = item

        # If a drag operation is in progress, don't show tooltips
        if getattr(self, 'dragged_index', None) is not None:
            return

        # Ensure the item still exists in the tree (it may have been
        # removed or the tree reordered while the tooltip was scheduled).
        try:
            if not tree.exists(item):
                return
        except Exception:
            # Tree may have been destroyed or unsupported widget; bail out
            return

        # Update tooltip text
        self.tooltip_label.config(text=filepath)

        # Position tooltip near the item but not directly under mouse
        try:
            bbox = tree.bbox(item)
            if not bbox:
                return
            x, y, _, h = bbox
        except tk.TclError:
            # Item may no longer be present; nothing to show
            return
        x += tree.winfo_rootx() + 25
        y += tree.winfo_rooty() + h  # Position below the item
        
        # Ensure tooltip is fully visible
        screen_width = self.winfo_screenwidth()
        tooltip_width = self.tooltip_label.winfo_reqwidth()
        if x + tooltip_width > screen_width:
            x = screen_width - tooltip_width - 10
            
        self.tooltip.wm_geometry(f"+{x}+{y}")
        self.tooltip.deiconify()
        self.tooltip_visible = True

    def _on_tree_motion(self, event, tree):
        if not self.tooltip:
            return
            
        # Get the item under cursor
        item = tree.identify_row(event.y)
        if not item:
            # Hide tooltip immediately when not over an item
            if self.tooltip_visible:
                self.tooltip.withdraw()
                self.tooltip_visible = False
                self.current_tooltip_item = None
            return
            
        # Get the full path for the item
        idx = tree.index(item)
        if tree == self.playlist_tree and idx < len(self.playlist):
            filepath = self.playlist[idx]
        elif tree == self.browser_tree and idx < len(self.browser_files):
            filepath = self.browser_files[idx]
        else:
            return
            
        self._schedule_tooltip_show(tree, item, filepath)

    # -------- Status helpers --------
    def _restore_status(self, prev_status):
        """Restore the previous status string and clear the scheduled id."""
        try:
            self.status.set(prev_status)
        finally:
            self._status_restore_after_id = None

    def _set_temporary_status(self, msg, duration=3000):
        """
        Set a temporary status message for `duration` milliseconds, then restore the previous value.
        Cancels any previously scheduled restore so repeated calls behave sensibly.
        """
        prev = self.status.get()
        # Cancel existing restore if any
        if getattr(self, '_status_restore_after_id', None):
            try:
                self.after_cancel(self._status_restore_after_id)
            except Exception:
                pass
            self._status_restore_after_id = None

        self.status.set(msg)
        # Schedule restore
        self._status_restore_after_id = self.after(duration, lambda: self._restore_status(prev))


if __name__ == '__main__':
    app = AudioPlayerApp()
    app.mainloop()
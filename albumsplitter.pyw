#Needed an edit so I could push for some reason

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk  # For displaying images
from pydub import AudioSegment
import os
from mutagen.id3 import ID3, APIC, TIT2, TALB, TPE1, TRCK
from mutagen.mp3 import MP3
import time
import re


class AlbumSplitterApp:
    def update_lengths_and_start_times(self, changed_track_index=None, is_length_change=False):
        total_tracks = len(self.tracks)

        # Find the manually marked last track (if any)
        last_track_index = next(
            (i for i, track in enumerate(self.tracks) if track.get("last_track_checkbox") and track["last_track_checkbox"].var.get() == 1),
            -1
        )

        # Forward propagation: Update start times of subsequent tracks
        for i in range(total_tracks - 1):
            current_start = self.parse_time(self.tracks[i]["start_time"].get())
            current_length = self.parse_time(self.tracks[i]["song_length"].get())

            if current_start is not None and current_length is not None:
                next_start = current_start + current_length
                self.tracks[i + 1]["start_time"].delete(0, tk.END)
                self.tracks[i + 1]["start_time"].insert(0, f"{next_start // 60}:{next_start % 60:02}")

        # Backward propagation: Update lengths of preceding tracks based on start times
        for i in range(1, total_tracks):
            current_start = self.parse_time(self.tracks[i]["start_time"].get())
            prev_start = self.parse_time(self.tracks[i - 1]["start_time"].get())

            if current_start is not None and prev_start is not None:
                new_length = current_start - prev_start
                if new_length >= 0:  # Avoid negative lengths
                    self.tracks[i - 1]["song_length"].delete(0, tk.END)
                    self.tracks[i - 1]["song_length"].insert(0, f"{new_length // 60}:{new_length % 60:02}")

        # Update the length of the last track only if the checkbox is checked
        if last_track_index != -1 and self.album_audio:
            last_track_start = self.parse_time(self.tracks[last_track_index]["start_time"].get())
            if last_track_start is not None:
                # Calculate the length of the last track from the album's total duration
                last_length = len(self.album_audio) // 1000 - last_track_start
                self.tracks[last_track_index]["song_length"].delete(0, tk.END)
                self.tracks[last_track_index]["song_length"].insert(0, f"{last_length // 60}:{last_length % 60:02}")









    def on_track_time_change(self, track_index):
        #Bind changes in start time or song length to update related fields.
        track = self.tracks[track_index]

        # Bind start time change
        track["start_time"].bind(
            "<FocusOut>", lambda e: self.update_lengths_and_start_times(changed_track_index=track_index)
        )
        # Bind song length change
        track["song_length"].bind(
            "<FocusOut>", lambda e: self.update_lengths_and_start_times(changed_track_index=track_index, is_length_change=True)
        )



    

    def __init__(self, root):
        self.root = root
        self.root.title("Album Splitter")
        self.tracks = []
        self.album_file = None
        self.album_audio = None
        self.album_cover = None

        # Display MP3 file name
        self.album_label = tk.Label(root, text="No album loaded", font=("Arial", 14))
        self.album_label.pack(pady=5)

        tk.Button(root, text="Load Album File", command=self.load_album).pack(pady=5)
        tk.Button(root, text="Select Album Cover", command=self.select_album_cover).pack(pady=5)

        # Canvas for displaying album cover
        self.cover_canvas = tk.Canvas(root, width=200, height=200, bg="gray")
        self.cover_canvas.pack(pady=5)

        # Create canvas with scrollbar for scrollable track list
        self.canvas = tk.Canvas(root)
        self.scrollbar = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Enable scrolling with mouse wheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.add_track(0)  # Start with the first track by default

        # Buttons for adding tracks and applying settings to all tracks
        tk.Button(root, text="Add Track", command=self.add_track).pack(pady=5)
        tk.Button(root, text="Apply Album to All Tracks", command=self.apply_album_to_all).pack(pady=5)
        tk.Button(root, text="Apply Artist to All Tracks", command=self.apply_artist_to_all).pack(pady=5)

        # Split button
        tk.Button(root, text="Split Album", command=self.split_album).pack(pady=10)

    def _on_mousewheel(self, event):
        # Adjust the canvas yview by a small step with the mouse wheel scroll
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def load_album(self):
        file_path = filedialog.askopenfilename(title="Select Album File", filetypes=[("Audio Files", "*.mp3 *.wav *.flac")])
        if file_path:
            self.album_file = file_path
            self.album_audio = AudioSegment.from_file(file_path)
            self.album_label.config(text=f"Loaded album: {os.path.basename(file_path)}")
            messagebox.showinfo("Album Loaded", f"Loaded album: {os.path.basename(file_path)}")

    def select_album_cover(self):
        cover_path = filedialog.askopenfilename(title="Select Album Cover", filetypes=[("Image Files", "*.jpg *.jpeg *.png")])
        if cover_path:
            self.album_cover = cover_path
            self.display_album_cover(cover_path)
            messagebox.showinfo("Album Cover Selected", f"Selected album cover: {os.path.basename(cover_path)}")

    def display_album_cover(self, cover_path):
        try:
            image = Image.open(cover_path)
            image = image.resize((200, 200), Image.Resampling.LANCZOS)  # Use LANCZOS for resizing
            self.cover_image = ImageTk.PhotoImage(image)  # Store reference to avoid garbage collection
            self.cover_canvas.create_image(100, 100, image=self.cover_image)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load album cover: {e}")

    def add_track(self, start_time=0):
        track_num = len(self.tracks) + 1
        track_frame = tk.Frame(self.scrollable_frame, borderwidth=1, relief="solid", pady=5)
        track_index = len(self.tracks)  # Capture the index at creation time

        # Create track details and UI elements
        track = {
            "frame": track_frame,
            "track_num": tk.Label(track_frame, text=f"Track {track_num}:", font=("Arial", 10)),
            "minimize_button": tk.Button(track_frame, text="-", width=1, height=1, command=lambda: self.toggle_track(track)),
            "remove_button": tk.Button(
                track_frame,
                text="Remove",
                command=lambda idx=track_index: self.remove_track(idx)  # Pass track index explicitly
            ),
            "details_frame": tk.Frame(track_frame),
            "last_track_checkbox": tk.Checkbutton(track_frame, text="Last Track", command=lambda: self.set_last_track(track_index)),
        }

        # Initialize the checkbox variable
        track["last_track_checkbox"].var = tk.IntVar()
        track["last_track_checkbox"].config(variable=track["last_track_checkbox"].var)

        # Track details
        track["start_time"] = tk.Entry(track["details_frame"], width=10)
        track["song_length"] = tk.Entry(track["details_frame"], width=10)
        track["title"] = tk.Entry(track["details_frame"], width=20)
        track["album"] = tk.Entry(track["details_frame"], width=20)
        track["artist"] = tk.Entry(track["details_frame"], width=20)
        track["track_number"] = tk.Entry(track["details_frame"], width=5)

        # Default values
        track["start_time"].insert(0, start_time if isinstance(start_time, str) else f"{start_time//60}:{start_time%60:02}")
        track["song_length"].insert(0, "0:00")
        track["title"].insert(0, f"Track {track_num}")
        track["album"].insert(0, "")
        track["artist"].insert(0, "")
        track["track_number"].insert(0, str(track_num))

        # Pack widgets
        track["track_num"].pack(side=tk.LEFT)
        track["minimize_button"].pack(side=tk.LEFT)
        track["last_track_checkbox"].pack(side=tk.RIGHT)
        track["remove_button"].pack(side=tk.RIGHT)
        track["details_frame"].pack()

        # Pack track details
        tk.Label(track["details_frame"], text="Start Time (mm:ss):").pack()
        track["start_time"].pack()
        tk.Label(track["details_frame"], text="Length (mm:ss):").pack()
        track["song_length"].pack()
        tk.Label(track["details_frame"], text="Title:").pack()
        track["title"].pack()
        tk.Label(track["details_frame"], text="Album:").pack()
        track["album"].pack()
        tk.Label(track["details_frame"], text="Artist:").pack()
        track["artist"].pack()
        tk.Label(track["details_frame"], text="Track #:").pack()
        track["track_number"].pack()

        track_frame.pack(fill="x", padx=5, pady=5)
        self.tracks.append(track)

        # Bind change events
        self.on_track_time_change(len(self.tracks) - 1)

        # Update times for the new track
        self.update_lengths_and_start_times()





    def set_last_track(self, track_index):
        for i, track in enumerate(self.tracks):
            if i == track_index:
                # Toggle the state of the checkbox
                is_last = track["last_track_checkbox"].var.get() == 1

                if is_last:
                    # Mark this as the last track and disable all other checkboxes
                    for j, other_track in enumerate(self.tracks):
                        if j != i:
                            other_track["last_track_checkbox"].config(state=tk.DISABLED)
                    track["song_length"].config(state=tk.NORMAL)  # Allow manual editing of the last track length
                else:
                    # Unmark this track and re-enable all other checkboxes
                    for other_track in self.tracks:
                        other_track["last_track_checkbox"].config(state=tk.NORMAL)
            else:
                # Disable or enable other checkboxes based on the state of the selected one
                state = tk.DISABLED if self.tracks[track_index]["last_track_checkbox"].var.get() == 1 else tk.NORMAL
                track["last_track_checkbox"].config(state=state)




    def remove_track(self, track_index):
        #Remove the specified track and update remaining tracks.
        
        # Remove the track's frame from the UI
        self.tracks[track_index]["frame"].destroy()
        # Remove the track from the list
        del self.tracks[track_index]

        # Reorder remaining tracks
        for i, track in enumerate(self.tracks):
            track["track_num"].config(text=f"Track {i + 1}:")
            track["track_number"].delete(0, tk.END)
            track["track_number"].insert(0, str(i + 1))
        
        # Rebind Remove Buttons with updated indices
        for i, track in enumerate(self.tracks):
            track["remove_button"].config(command=lambda idx=i: self.remove_track(idx))

        # Update subsequent tracks to ensure consistency
        self.update_lengths_and_start_times()




    def toggle_track(self, track):
        #Toggle visibility of the details frame and resize the track frame when minimized.
        if track["details_frame"].winfo_ismapped():
            # Minimize the track
            track["details_frame"].pack_forget()
            track["minimize_button"].config(text="+")
            track["frame"].config(height=20)  # Make the track smaller
        else:
            # Maximize the track
            track["details_frame"].pack()
            track["minimize_button"].config(text="-")
        track["frame"].config(height="")  # Reset to default height


    def apply_album_to_all(self):
        album_name = self.tracks[0]["album"].get()
        for track in self.tracks:
            track["album"].delete(0, tk.END)
            track["album"].insert(0, album_name)

    def apply_artist_to_all(self):
        artist_name = self.tracks[0]["artist"].get()
        for track in self.tracks:
            track["artist"].delete(0, tk.END)
            track["artist"].insert(0, artist_name)

    def parse_time(self, time_str):
        try:
            minutes, seconds = map(int, time_str.split(":"))
            return minutes * 60 + seconds
        except ValueError:
            return None

    def embed_cover(self, audio, cover_path):
        try:
            # Determine mime type, save as jpg
            image = Image.open(cover_path)
            image.save(cover_path, format="JPEG")  # Save as JPEG
            mime_type = "image/jpeg"

            # Add album cover
            with open(cover_path, "rb") as img:
                audio.tags.add(
                    APIC(
                        encoding=3,
                        mime=mime_type,
                        type=3,  # Front cover
                        data=img.read(),
                    )
                )
            print("Cover embedded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to embed album cover: {e}")

    def sanitize_filename(self, filename):
        #Remove characters that are invalid for file names.
        
        import re
        return re.sub(r'[<>:"/\\|?*\n]', ' ', filename)


    def split_album(self):
        if not self.album_audio:
            messagebox.showerror("No Album Loaded", "Please load an album file first.")
            return

        output_folder = filedialog.askdirectory(title="Select Output Folder")
        if not output_folder:
            return

        # Get track times and metadata
        track_times = []
        track_titles = []
        track_albums = []
        track_artists = []
        track_numbers = []

        for track in self.tracks:
            start_time_str = track["start_time"].get()
            title = self.sanitize_filename(track["title"].get())  # Use self.sanitize_filename
            album = self.sanitize_filename(track["album"].get())
            artist = self.sanitize_filename(track["artist"].get())
            track_number = track["track_number"].get()

            start_time_sec = self.parse_time(start_time_str)
            if start_time_sec is None:
                messagebox.showerror("Invalid Time Format", f"Invalid time format: {start_time_str}")
                return

            track_times.append(start_time_sec)
            track_titles.append(title)
            track_albums.append(album)
            track_artists.append(artist)
            track_numbers.append(track_number)

        # Add the end time as the end of the album
        track_times.append(len(self.album_audio) / 1000)

        # Split and export each track
        for i in range(len(track_titles)):
            start_ms = track_times[i] * 1000
            end_ms = track_times[i + 1] * 1000

            track_audio = self.album_audio[start_ms:end_ms]
            final_output_path = os.path.join(output_folder, f"{track_titles[i]}.mp3")
            final_output_path = os.path.normpath(final_output_path)

            os.makedirs(os.path.dirname(final_output_path), exist_ok=True)
            track_audio.export(final_output_path, format="mp3")

            # Embed metadata and album cover
            audio = MP3(final_output_path, ID3=ID3)

            try:
                audio.add_tags()
            except Exception:
                pass  # Tags already exist

            audio["TIT2"] = TIT2(encoding=3, text=track_titles[i])
            audio["TALB"] = TALB(encoding=3, text=track_albums[i])
            audio["TPE1"] = TPE1(encoding=3, text=track_artists[i])
            audio["TRCK"] = TRCK(encoding=3, text=track_numbers[i])

            if self.album_cover:
                self.embed_cover(audio, self.album_cover)

            audio.save(v2_version=3)  # Save as ID3v2.3

        messagebox.showinfo("Done", "Album has been split successfully!")



# Run the application
root = tk.Tk()
app = AlbumSplitterApp(root)
root.mainloop()

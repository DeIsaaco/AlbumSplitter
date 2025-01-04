import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk  # For displaying images
from pydub import AudioSegment
import os
from mutagen.id3 import ID3, APIC, TIT2, TALB, TPE1, TRCK
from mutagen.mp3 import MP3
import time

class AlbumSplitterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Album Splitter")
        self.tracks = []
        self.album_file = None
        self.album_audio = None
        self.album_cover = None  # Store album cover path

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
        track = {
            "frame": track_frame,
            "track_num": tk.Label(track_frame, text=f"Track {track_num}:", font=("Arial", 10)),
            "minimize_button": tk.Button(track_frame, text="-", width=2, command=lambda: self.toggle_track(track)),
            "details_frame": tk.Frame(track_frame)
        }

        # Track details
        track["start_time"] = tk.Entry(track["details_frame"], width=10)
        track["title"] = tk.Entry(track["details_frame"], width=20)
        track["album"] = tk.Entry(track["details_frame"], width=20)
        track["artist"] = tk.Entry(track["details_frame"], width=20)  # New artist field
        track["track_number"] = tk.Entry(track["details_frame"], width=5)

        # Default values for the new track
        track["start_time"].insert(0, start_time if isinstance(start_time, str) else f"{start_time//60}:{start_time%60:02}")
        track["title"].insert(0, f"Track {track_num}")
        track["album"].insert(0, "")
        track["artist"].insert(0, "")
        track["track_number"].insert(0, str(track_num))

        # Pack track widgets in a structured order
        track["track_num"].pack(side=tk.LEFT)
        track["minimize_button"].pack(side=tk.LEFT)
        track["details_frame"].pack()

        tk.Label(track["details_frame"], text="Start Time (mm:ss):").pack()
        track["start_time"].pack()
        tk.Label(track["details_frame"], text="Title:").pack()
        track["title"].pack()
        tk.Label(track["details_frame"], text="Album:").pack()
        track["album"].pack()
        tk.Label(track["details_frame"], text="Artist:").pack()  # Artist label and field
        track["artist"].pack()
        tk.Label(track["details_frame"], text="Track #:").pack()
        track["track_number"].pack()

        track_frame.pack(fill="x", padx=5, pady=5)  # Pack each track frame sequentially
        self.tracks.append(track)

    def toggle_track(self, track):
        # Toggle visibility of the details frame
        if track["details_frame"].winfo_ismapped():
            track["details_frame"].pack_forget()
            track["minimize_button"].config(text="+")
        else:
            track["details_frame"].pack()
            track["minimize_button"].config(text="-")

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
        track_artists = []  # List to store artist for each track
        track_numbers = []

        for track in self.tracks:
            start_time_str = track["start_time"].get()
            title = track["title"].get()
            album = track["album"].get()
            artist = track["artist"].get()  # Retrieve artist name
            track_number = track["track_number"].get()

            start_time_sec = self.parse_time(start_time_str)
            if start_time_sec is None:
                messagebox.showerror("Invalid Time Format", f"Invalid time format: {start_time_str}")
                return

            track_times.append(start_time_sec)
            track_titles.append(title)
            track_albums.append(album)
            track_artists.append(artist)  # Append artist name to list
            track_numbers.append(track_number)

        # Add the end time as the end of the album
        track_times.append(len(self.album_audio) / 1000)

        # Split and export each track
        for i in range(len(track_titles)):
            start_ms = track_times[i] * 1000
            end_ms = track_times[i + 1] * 1000

            track_audio = self.album_audio[start_ms:end_ms]
            final_output_path = os.path.join(output_folder, f"{track_titles[i]}.mp3")

            # Ensure the output directory exists
            os.makedirs(os.path.dirname(final_output_path), exist_ok=True)

            # Normalize paths
            final_output_path = os.path.normpath(final_output_path)

            # Export the track without metadata or cover
            track_audio.export(final_output_path, format="mp3")

            # Ensure the file exists before proceeding
            for _ in range(10):  # Try for up to 10 iterations (approx. 1 second)
                if os.path.exists(final_output_path):
                    break
                time.sleep(0.1)  # Wait 100ms before checking again

            if not os.path.exists(final_output_path):
                messagebox.showerror("Error", f"Failed to create output file: {final_output_path}")
                return

            # Embed metadata and album cover using mutagen
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
                with open(self.album_cover, "rb") as img:
                    audio.tags.add(
                        APIC(
                            encoding=3,  # UTF-8
                            mime="image/jpeg",  # Or "image/png"
                            type=3,  # Front cover
                            desc="Cover",
                            data=img.read(),
                        )
                    )

            # Save the file with metadata
            audio.save()

            print(f"Exported {track_titles[i]} with cover")

        messagebox.showinfo("Done", "Album has been split successfully!")


# Run the application
root = tk.Tk()
app = AlbumSplitterApp(root)
root.mainloop()

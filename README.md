# AlbumSplitter
Splits an album's mp3 file into its individual songs.

# Install (Windows instructions, if you're on linux, you should know how to do this anyways)
1. Download latest release from right
2. Extract to folder outside of downloads (desktop, program files, etc)
3. Install python (https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe)
4. Open command prompt (Windows key, type cmd, press enter)
5. Navigate to extracted folder
	-You can open cmd in this directory by typing "cmd" in the File Explorer address bar
6. In the window that pops up, type "pip install -r requirements.txt" without the quotation marks. (to copy/paste, use ctrl c here, and shift+insert in command prompt)
7. Install FFmpeg (https://www.youtube.com/watch?v=JR36oH35Fgg)
8. Run the albumsplitter.py file

# Use
1. Select your album .mp3 file by dragging and dropping, or by double clicking the empty dark-grey box at the top of the window.
2. Set the metadata at the top of the window. You can leave these blank.
3. Set your album cover by dragging and dropping, or by clicking the album cover button.
4. Use the 'S' key to 'split' the album. This creates a new song start time, and a new track. Very intuitive. You can also use the manual buttons at the bottom of the window.
5. Set the titles, ensure all metadata is correct.
6. Click the "Split Album" button, and wait (You can also export songs individually if you want to do so, just use each track's respective export button).

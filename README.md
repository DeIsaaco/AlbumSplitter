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
1. Select your album .mp3 file by clicking the "Load Album File" button
2. Set your first song title, the album, and the artist (Track # is 1 by default, start time is 0:00 by default)
3. Set your album cover with the "Select Album Cover" Button
4. Add your second, third, etc. tracks. Make sure to add in the start times for each of them
5. Click the two apply to all buttons at the bottom. These apply the album title and artist that you set for the first song to all of the songs.
6. Click the "Split Album" button, and wait.

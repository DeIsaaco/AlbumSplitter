#!/usr/bin/env python3
import sys, os, re, numpy as np, subprocess, tempfile, shutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog, QScrollArea, QProgressBar,
    QMessageBox, QShortcut
)
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap, QDragEnterEvent, QDropEvent, QKeySequence, QIcon
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer, QRect
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from pydub import AudioSegment, effects

# Global constants
CHUNK_DURATION = 30  # seconds of effective playback per chunk
OVERLAP_SECONDS = 1.0  # extra seconds to overlap for seamless transition

#############################################
# Helper functions for time formatting
#############################################
def format_time(seconds):
    total_ms = int(seconds * 1000)
    minutes = total_ms // 60000
    seconds_part = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{minutes:02d}:{seconds_part:02d}:{ms:03d}"

def parse_time(time_str):
    parts = time_str.strip().split(":")
    if len(parts) == 2:
        minutes, sec = parts
        return int(minutes) * 60 + int(sec)
    elif len(parts) == 3:
        minutes, sec, ms = parts
        return int(minutes) * 60 + int(sec) + int(ms) / 1000.0
    else:
        raise ValueError("Time format should be MM:SS or MM:SS:sss")

#############################################
# Helper function to extract a chunk using ffmpeg
#############################################
def extract_segment(input_file, start, duration, ffmpeg_path="ffmpeg"):
    temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    temp_file.close()  # ffmpeg will write to this file
    cmd = [
        ffmpeg_path,
        "-y",  # automatically overwrite output
        "-hide_banner",
        "-loglevel", "error",
        "-ss", str(start),
        "-t", str(duration),
        "-i", input_file,
        "-acodec", "copy",
        temp_file.name
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    return temp_file.name

#############################################
# Helper function to embed album cover using ffmpeg
#############################################
def embed_cover(audio_file, cover_file, output_file, ffmpeg_path="ffmpeg"):
    cmd = [
        ffmpeg_path,
        "-y",
        "-i", audio_file,
        "-i", cover_file,
        "-map", "0:a",
        "-map", "1:v",
        "-c", "copy",
        "-id3v2_version", "3",
        "-metadata:s:v", "title=Album cover",
        "-metadata:s:v", "comment=Cover (front)",
        output_file
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)

#############################################
# Worker thread for loading the audio file
#############################################
class AudioLoaderThread(QThread):
    finished = pyqtSignal(AudioSegment, np.ndarray, int)  # audio, waveform, sample_rate
    error = pyqtSignal(str)
    
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
    
    def run(self):
        try:
            audio = AudioSegment.from_file(self.file_path)
            sample_rate = audio.frame_rate
            audio_mono = audio.set_channels(1)
            samples = np.array(audio_mono.get_array_of_samples(), dtype=np.float32)
            waveform = samples / np.max(np.abs(samples)) if np.max(np.abs(samples)) > 0 else samples
            self.finished.emit(audio, waveform, sample_rate)
        except Exception as e:
            self.error.emit(str(e))

#############################################
# Waveform widget with draggable playhead
#############################################
class WaveformWidget(QWidget):
    playheadChanged = pyqtSignal(float)
    waveformDoubleClicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.waveform = None
        self.audio_duration = 0.0
        self.sample_rate = 44100
        self.zoom = 1.0
        self.offset = 0.0
        self.playhead_time = 0.0
        self.draggingPlayhead = False
        self.markers = []
        self.setMinimumHeight(80)
    
    def setWaveform(self, waveform, duration, sample_rate):
        self.waveform = waveform
        self.audio_duration = duration
        self.sample_rate = sample_rate
        self.zoom = 1.0
        self.offset = 0.0
        self.playhead_time = 0.0
        self.update()
    
    def setMarkers(self, markers):
        self.markers = markers
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        # Fill entire widget background
        painter.fillRect(rect, QColor(30,30,30))
        
        # Define active waveform area (top 60% of the widget)
        active_height = int(rect.height() * 0.6)
        active_rect = QRect(rect.x(), rect.y(), rect.width(), active_height)
        mid_y = active_rect.y() + active_rect.height() / 2
        
        # Draw waveform only in the active area
        if self.waveform is not None:
            width = rect.width()
            visible_duration = self.audio_duration / self.zoom
            pen = QPen(QColor(0,200,0))
            painter.setPen(pen)
            for x in range(width):
                t1 = self.offset + (x/width)*visible_duration
                t2 = self.offset + ((x+1)/width)*visible_duration
                idx1 = int(t1 * self.sample_rate)
                idx2 = int(t2 * self.sample_rate)
                idx1 = max(0, idx1)
                idx2 = min(len(self.waveform), idx2)
                if idx2 <= idx1:
                    continue
                segment = self.waveform[idx1:idx2]
                min_val = np.min(segment)
                max_val = np.max(segment)
                # Scale amplitude to half of active_rect height
                y1 = mid_y - (max_val * active_rect.height() / 2)
                y2 = mid_y - (min_val * active_rect.height() / 2)
                painter.drawLine(x, int(y1), x, int(y2))
        
        # Draw markers and playhead lines extending full height
        visible_duration = self.audio_duration / self.zoom
        if self.markers:
            for i, marker in enumerate(self.markers):
                if marker < self.offset or marker > self.offset + visible_duration:
                    continue
                x_marker = int((marker - self.offset) / visible_duration * rect.width())
                marker_pen = QPen(QColor(200,50,50), 2)
                painter.setPen(marker_pen)
                painter.drawLine(x_marker, 0, x_marker, rect.height())
        
        if self.audio_duration > 0:
            visible_duration = self.audio_duration / self.zoom
            if self.playhead_time < self.offset:
                 x = 0
            elif self.playhead_time > self.offset + visible_duration:
                 x = rect.width()
            else:
                 x = int((self.playhead_time - self.offset) / visible_duration * rect.width())
            playhead_pen = QPen(QColor(50,150,250), 2)
            painter.setPen(playhead_pen)
            painter.drawLine(x, 0, x, rect.height())
        else:
            x = 0
 
        # Draw marker labels and playhead timestamp in the bottom area
        if self.markers:
            for i, marker in enumerate(self.markers):
                if marker < self.offset or marker > self.offset + visible_duration:
                    continue
                x_marker = int((marker - self.offset) / visible_duration * rect.width())
                painter.drawText(x_marker+5, rect.height()-5, f"Track {i+1}")
        painter.drawText(x+5, rect.height()-15, format_time(self.playhead_time))
    
    def mousePressEvent(self, event):
        if self.audio_duration <= 0:
            return
        rect = self.rect()
        visible_duration = self.audio_duration / self.zoom
        if self.playhead_time < self.offset:
            current_x = 0
        elif self.playhead_time > self.offset + visible_duration:
            current_x = rect.width()
        else:
            current_x = int((self.playhead_time - self.offset) / visible_duration * rect.width())
        if abs(event.x() - current_x) < 5:
            self.draggingPlayhead = True
        else:
            new_time = self.offset + (event.x()/rect.width()) * visible_duration
            new_time = max(0, min(new_time, self.audio_duration))
            self.playhead_time = new_time
            self.update()
            self.playheadChanged.emit(self.playhead_time)
    
    def mouseMoveEvent(self, event):
        if self.draggingPlayhead:
            rect = self.rect()
            visible_duration = self.audio_duration / self.zoom
            new_time = self.offset + (event.x()/rect.width()) * visible_duration
            new_time = max(0, min(new_time, self.audio_duration))
            self.playhead_time = new_time
            self.update()
    
    def mouseReleaseEvent(self, event):
        if self.draggingPlayhead:
            self.draggingPlayhead = False
            self.playheadChanged.emit(self.playhead_time)
    
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ShiftModifier:
            rect = self.rect()
            visible_duration = self.audio_duration / self.zoom
            delta_seconds = -event.angleDelta().y() / 120 * (visible_duration * 0.1)
            self.offset += delta_seconds
            self.offset = max(0, min(self.offset, self.audio_duration - visible_duration))
            self.update()
        else:
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 0.9
            old_visible = self.audio_duration / self.zoom
            self.zoom *= factor
            if self.zoom < 1.0:
                self.zoom = 1.0
            new_visible = self.audio_duration / self.zoom
            center = self.offset + old_visible / 2
            self.offset = center - new_visible / 2
            self.offset = max(0, min(self.offset, self.audio_duration - new_visible))
            self.update()
    
    def mouseDoubleClickEvent(self, event):
        self.waveformDoubleClicked.emit()

#############################################
# Track item widget
#############################################
class TrackItemWidget(QWidget):
    trackChanged = pyqtSignal(int, float, float, str)
    playPauseRequested = pyqtSignal(int)
    trackRemoveRequested = pyqtSignal(int)
    exportRequested = pyqtSignal(int)
    
    def __init__(self, index, start_time=0.0, length=0.0, title="", parent=None):
        super().__init__(parent)
        self.index = index
        self.start_time = start_time
        self.length = length
        self.title = title
        self.setFixedHeight(40)
        layout = QHBoxLayout()
        layout.setContentsMargins(2,2,2,2)
        self.setLayout(layout)
        self.trackNumLabel = QLabel(f"Track {index+1}")
        self.trackNumLabel.setFixedWidth(70)
        layout.addWidget(self.trackNumLabel)
        self.startEdit = QLineEdit(format_time(self.start_time))
        self.lengthEdit = QLineEdit(format_time(self.length))
        self.titleEdit = QLineEdit(self.title)
        self.playButton = QPushButton("Play")
        self.playButton.setFixedWidth(50)
        self.exportButton = QPushButton("Export")
        self.exportButton.setFixedWidth(70)
        self.removeButton = QPushButton("Remove")
        self.removeButton.setFixedWidth(70)
        layout.addWidget(QLabel("Start:"))
        layout.addWidget(self.startEdit)
        layout.addWidget(QLabel("Length:"))
        layout.addWidget(self.lengthEdit)
        layout.addWidget(QLabel("Title:"))
        layout.addWidget(self.titleEdit)
        layout.addWidget(self.playButton)
        layout.addWidget(self.exportButton)
        layout.addWidget(self.removeButton)
        self.startEdit.editingFinished.connect(self.updateTrack)
        self.lengthEdit.editingFinished.connect(self.updateTrack)
        self.titleEdit.editingFinished.connect(self.updateTrack)
        self.playButton.clicked.connect(self.requestPlayPause)
        self.removeButton.clicked.connect(self.requestRemove)
        self.exportButton.clicked.connect(self.requestExport)
    
    def updateTrack(self):
        try:
            new_start = parse_time(self.startEdit.text())
            new_length = parse_time(self.lengthEdit.text())
            new_title = self.titleEdit.text()
            self.start_time = new_start
            self.length = new_length
            self.title = new_title
            self.startEdit.setText(format_time(new_start))
            self.lengthEdit.setText(format_time(new_length))
            self.trackChanged.emit(self.index, new_start, new_length, new_title)
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Invalid time format. Use MM:SS or MM:SS:sss")
    
    def requestPlayPause(self):
        self.playPauseRequested.emit(self.index)
    
    def requestRemove(self):
        self.trackRemoveRequested.emit(self.index)
    
    def requestExport(self):
        self.exportRequested.emit(self.index)

#############################################
# Main window tying everything together
#############################################
class AlbumSplitterMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Album MP3 Splitter")
        self.resize(1200,800)
        self.audio = None
        self.waveform_data = None
        self.audio_file_path = ""
        self.tracks = []
        self.trackWidgets = []
        self.album_art = None
        self.album_art_path = None
        self.current_playing_track = None
        self.current_preview_end = None   # end time (seconds) of effective playback
        self.current_chunk_base = None    # base time (seconds) of current chunk
        self.current_mode = None          # "track" or "full"
        self.loading_next_chunk = False
        self.player = QMediaPlayer()
        self.player.setVolume(100)
        self.player.error.connect(lambda: print("Player error:", self.player.errorString()))
        self.player.positionChanged.connect(self.onPlayerPositionChanged)
        
        centralWidget = QWidget()
        self.setCentralWidget(centralWidget)
        mainLayout = QVBoxLayout()
        centralWidget.setLayout(mainLayout)
        self.setStyleSheet("""
        QMainWindow { background-color: #2b2b2b; color: white; }
        QLabel, QLineEdit, QPushButton, QScrollArea, QProgressBar { background-color: #3c3f41; color: white; }
        QLineEdit { border: 1px solid #5a5a5a; }
        QPushButton { border: 1px solid #5a5a5a; padding: 4px; }
        """)
        
        # Metadata
        metaLayout = QHBoxLayout()
        mainLayout.addLayout(metaLayout)
        self.albumTitleEdit = QLineEdit("Album Title")
        self.artistEdit = QLineEdit("Artist")
        self.genreEdit = QLineEdit("Genre")
        self.yearEdit = QLineEdit("Year")
        self.composerEdit = QLineEdit("Composer")
        metaLayout.addWidget(QLabel("Album Title:"))
        metaLayout.addWidget(self.albumTitleEdit)
        metaLayout.addWidget(QLabel("Artist:"))
        metaLayout.addWidget(self.artistEdit)
        metaLayout.addWidget(QLabel("Genre:"))
        metaLayout.addWidget(self.genreEdit)
        metaLayout.addWidget(QLabel("Year:"))
        metaLayout.addWidget(self.yearEdit)
        metaLayout.addWidget(QLabel("Composer:"))
        metaLayout.addWidget(self.composerEdit)
        
        # Album cover and waveform
        coverWaveLayout = QHBoxLayout()
        mainLayout.addLayout(coverWaveLayout)
        self.coverButton = QPushButton("Select Cover")
        self.coverButton.setFixedSize(200,200)
        self.coverButton.clicked.connect(self.loadAlbumArt)
        coverWaveLayout.addWidget(self.coverButton)
        self.waveformWidget = WaveformWidget()
        coverWaveLayout.addWidget(self.waveformWidget, 1)
        self.waveformWidget.playheadChanged.connect(self.onPlayheadChanged)
        self.waveformWidget.waveformDoubleClicked.connect(self.openAudioFile)
        
        # Playback controls
        playbackLayout = QHBoxLayout()
        mainLayout.addLayout(playbackLayout)
        playFromHeadButton = QPushButton("Play from Playhead")
        playFromHeadButton.clicked.connect(self.playFromPlayhead)
        pauseButton = QPushButton("Global Pause")
        pauseButton.clicked.connect(self.globalPause)
        playbackLayout.addWidget(playFromHeadButton)
        playbackLayout.addWidget(pauseButton)
        
        # Track management
        splitterLayout = QHBoxLayout()
        mainLayout.addLayout(splitterLayout)
        trackManagementLayout = QVBoxLayout()
        splitterLayout.addLayout(trackManagementLayout, 2)
        self.trackListWidget = QWidget()
        self.trackListLayout = QVBoxLayout()
        self.trackListLayout.setAlignment(Qt.AlignTop)
        self.trackListWidget.setLayout(self.trackListLayout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.trackListWidget)
        trackManagementLayout.addWidget(scroll)
        addTrackButton = QPushButton("Add Track")
        addTrackButton.clicked.connect(self.addTrack)
        trackManagementLayout.addWidget(addTrackButton)
        
        # Split album and progress
        splitButton = QPushButton("Split Album")
        splitButton.clicked.connect(self.splitAlbum)
        mainLayout.addWidget(splitButton)
        self.progressBar = QProgressBar()
        mainLayout.addWidget(self.progressBar)
        
        self.setAcceptDrops(True)
        QShortcut(QKeySequence("Ctrl+O"), self, self.openAudioFile)
        QShortcut(QKeySequence("Ctrl+S"), self, self.splitAlbum)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_S:
            if self.audio:
                marker_time = self.waveformWidget.playhead_time
                marker_time = max(0, min(marker_time, self.audio.duration_seconds))
                new_track = {"start": marker_time, "length": 0.0, "title": f"Track {len(self.tracks)+1}"}
                self.tracks.append(new_track)
                self.tracks.sort(key=lambda t: t["start"])
                for i in range(len(self.tracks)-1):
                    self.tracks[i]["length"] = self.tracks[i+1]["start"] - self.tracks[i]["start"]
                self.tracks[-1]["length"] = self.audio.duration_seconds - self.tracks[-1]["start"]
                self.refreshTrackList()
                self.waveformWidget.setMarkers([t["start"] for t in self.tracks])
        else:
            super().keyPressEvent(event)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.mp3','.wav','.flac')):
                self.loadAudioFile(file_path)
            elif file_path.lower().endswith(('.jpg','.jpeg','.png')):
                self.loadAlbumArtFromFile(file_path)
    
    def loadAudioFile(self, file_path=None):
        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "", "Audio Files (*.mp3 *.wav *.flac)")
        if file_path:
            self.audio_file_path = file_path
            self.progressBar.setValue(0)
            self.progressBar.setFormat("Loading audio...")
            self.loaderThread = AudioLoaderThread(file_path)
            self.loaderThread.finished.connect(self.onAudioLoaded)
            self.loaderThread.error.connect(self.onAudioLoadError)
            self.loaderThread.start()
    
    def onAudioLoaded(self, audio, waveform, sample_rate):
        self.audio = audio
        self.waveform_data = waveform
        duration = audio.duration_seconds
        self.waveformWidget.setWaveform(waveform, duration, sample_rate)
        self.tracks = [{"start": 0.0, "length": 0.0, "title": "Track 1"}]
        self.refreshTrackList()
        self.waveformWidget.setMarkers([t["start"] for t in self.tracks])
        self.progressBar.setValue(100)
        self.progressBar.setFormat("Audio loaded.")
    
    def onAudioLoadError(self, error_msg):
        QMessageBox.critical(self, "Audio Load Error", error_msg)
        self.progressBar.setValue(0)
    
    def openAudioFile(self):
        self.loadAudioFile()
    
    def loadAlbumArt(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Album Cover", "", "Image Files (*.jpg *.jpeg *.png)")
        if file_path:
            self.loadAlbumArtFromFile(file_path)
    
    def loadAlbumArtFromFile(self, file_path):
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            self.album_art = pixmap.scaled(200,200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.coverButton.setIcon(QIcon(self.album_art))
            self.coverButton.setIconSize(self.coverButton.size())
            self.coverButton.setText("")
            self.album_art_path = file_path
    
    def addTrack(self):
        if self.audio is None: return
        if self.tracks:
            last_track = self.tracks[-1]
            new_start = last_track["start"] + last_track["length"]
        else:
            new_start = 0.0
        new_track = {"start": new_start, "length": 0.0, "title": f"Track {len(self.tracks)+1}"}
        self.tracks.append(new_track)
        self.refreshTrackList()
        self.waveformWidget.setMarkers([t["start"] for t in self.tracks])
    
    def removeTrack(self, index):
        if 0 <= index < len(self.tracks):
            self.tracks.pop(index)
            if self.tracks:
                for i in range(len(self.tracks)-1):
                    self.tracks[i]["length"] = self.tracks[i+1]["start"] - self.tracks[i]["start"]
                self.tracks[-1]["length"] = self.audio.duration_seconds - self.tracks[-1]["start"]
            self.refreshTrackList()
            self.waveformWidget.setMarkers([t["start"] for t in self.tracks])
    
    def refreshTrackList(self):
        for i in reversed(range(self.trackListLayout.count())):
            widget = self.trackListLayout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.trackWidgets = []
        for idx, track in enumerate(self.tracks):
            item = TrackItemWidget(idx, track["start"], track["length"], track["title"])
            item.playPauseRequested.connect(self.onTrackPlayPause)
            item.trackChanged.connect(self.onTrackChanged)
            item.trackRemoveRequested.connect(self.onTrackRemove)
            item.exportRequested.connect(self.onTrackExportRequested)
            self.trackListLayout.addWidget(item)
            self.trackWidgets.append(item)
    
    def onTrackChanged(self, index, new_start, new_length, new_title):
        if 0 <= index < len(self.tracks):
            self.tracks[index]["start"] = new_start
            self.tracks[index]["length"] = new_length
            self.tracks[index]["title"] = new_title
            if index > 0:
                self.tracks[index-1]["length"] = new_start - self.tracks[index-1]["start"]
            if index < len(self.tracks)-1:
                self.tracks[index+1]["start"] = new_start + new_length
                for i in range(index+1, len(self.tracks)-1):
                    self.tracks[i+1]["start"] = self.tracks[i]["start"] + self.tracks[i]["length"]
            if self.audio:
                album_duration = self.audio.duration_seconds
                self.tracks[-1]["length"] = album_duration - self.tracks[-1]["start"]
            for i, widget in enumerate(self.trackWidgets):
                widget.startEdit.setText(format_time(self.tracks[i]["start"]))
                widget.lengthEdit.setText(format_time(self.tracks[i]["length"]))
            self.waveformWidget.setMarkers([t["start"] for t in self.tracks])
    
    def onTrackRemove(self, index):
        self.removeTrack(index)
    
    def onTrackExportRequested(self, index):
        if self.audio is None or index < 0 or index >= len(self.tracks):
            QMessageBox.warning(self, "Export Error", "No audio loaded or invalid track index.")
            return
        track = self.tracks[index]
        start_ms = int(track["start"] * 1000)
        end_ms = int((track["start"] + track["length"]) * 1000)
        if end_ms <= start_ms:
            QMessageBox.warning(self, "Export Error", "Track length is 0. Adjust track length before exporting.")
            return
        # Prompt for file save location with a suggested filename
        safe_title = re.sub(r'[\\/:"*?<>|]+', '_', track["title"])
        suggested_filename = f"{safe_title}.mp3"
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Track", suggested_filename, "MP3 Files (*.mp3)")
        if not file_path:
            return
        normalized_audio = effects.normalize(self.audio)
        # First, export the segment to a temporary file
        temp_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_audio.close()
        segment = normalized_audio[start_ms:end_ms]
        metadata = {
            "title": track["title"],
            "artist": self.artistEdit.text(),
            "album": self.albumTitleEdit.text(),
            "track": str(index+1),
            "genre": self.genreEdit.text(),
            "year": self.yearEdit.text(),
            "composer": self.composerEdit.text()
        }
        segment.export(temp_audio.name, format="mp3", tags=metadata)
        # If an album cover is available, embed it
        if self.album_art_path:
            temp_output = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_output.close()
            try:
                embed_cover(temp_audio.name, self.album_art_path, temp_output.name)
                shutil.move(temp_output.name, file_path)
                QMessageBox.information(self, "Success", f"Track '{track['title']}' exported with album cover!")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", f"Error embedding cover for {track['title']}: {str(e)}")
        else:
            shutil.move(temp_audio.name, file_path)
            QMessageBox.information(self, "Success", f"Track '{track['title']}' exported successfully!")
    
    def onTrackPlayPause(self, index):
        track = self.tracks[index]
        if track["length"] <= 0:
            QMessageBox.warning(self, "Playback Error", "Track length is 0. Adjust track length before previewing.")
            return
        if self.audio_file_path:
            self.current_mode = "track"
            self.current_track_end = track["start"] + track["length"]
            self.current_chunk_base = track["start"]
            available = self.current_track_end - self.current_chunk_base
            extract_duration = min(CHUNK_DURATION + OVERLAP_SECONDS, available)
            try:
                segment_file = extract_segment(self.audio_file_path, self.current_chunk_base, extract_duration)
            except Exception as e:
                QMessageBox.warning(self, "Playback Error", f"Error extracting segment: {e}")
                return
            if self.current_playing_track is not None and self.player.state() == QMediaPlayer.PlayingState:
                self.player.stop()
                self.trackWidgets[self.current_playing_track].playButton.setText("Play")
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(segment_file)))
            self.player.setPosition(0)
            self.current_preview_end = self.current_chunk_base + CHUNK_DURATION
            self.player.play()
            self.trackWidgets[index].playButton.setText("Pause")
            self.current_playing_track = index
    
    def onPlayerPositionChanged(self, pos):
        if not self.waveformWidget.draggingPlayhead and self.audio:
            if self.current_chunk_base is not None:
                self.waveformWidget.playhead_time = self.current_chunk_base + pos/1000.0
            else:
                self.waveformWidget.playhead_time = pos/1000.0
            self.waveformWidget.update()
            if self.current_mode == "track":
                if self.current_chunk_base is not None and self.current_preview_end is not None:
                    current_effective = self.current_preview_end - self.current_chunk_base
                    if pos >= int((current_effective - 2)*1000):
                        next_chunk_start = self.current_preview_end - OVERLAP_SECONDS
                        if next_chunk_start < self.current_track_end:
                            self.load_next_chunk(track_mode=True, start_override=next_chunk_start)
                        else:
                            self.player.stop()
                            if self.current_playing_track is not None:
                                self.trackWidgets[self.current_playing_track].playButton.setText("Play")
                            self.current_preview_end = None
                            self.current_chunk_base = None
            elif self.current_mode == "full":
                if self.current_chunk_base is not None and self.current_preview_end is not None and not self.loading_next_chunk:
                    current_effective = self.current_preview_end - self.current_chunk_base
                    if pos >= int((current_effective - 2)*1000):
                        self.loading_next_chunk = True
                        next_chunk_start = self.current_preview_end - OVERLAP_SECONDS
                        QTimer.singleShot(100, lambda: self.load_next_chunk(track_mode=False, start_override=next_chunk_start))
    
    def onPlayheadChanged(self, time_sec):
        self.waveformWidget.playhead_time = time_sec
        self.current_chunk_base = time_sec
        self.current_preview_end = None
        self.waveformWidget.update()
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.player.setPosition(0)
            if self.current_playing_track is not None:
                self.trackWidgets[self.current_playing_track].playButton.setText("Play")
                self.current_playing_track = None
    
    def load_next_chunk(self, track_mode=False, start_override=None):
        if start_override is not None:
            next_chunk_start = start_override
        else:
            next_chunk_start = self.current_preview_end - OVERLAP_SECONDS
        if track_mode:
            if next_chunk_start >= self.current_track_end:
                self.player.stop()
                self.current_preview_end = None
                self.current_chunk_base = None
                return
            available = self.current_track_end - next_chunk_start
            extract_duration = min(CHUNK_DURATION + OVERLAP_SECONDS, available)
        else:
            remaining = self.audio.duration_seconds - next_chunk_start
            if remaining <= 0:
                self.player.stop()
                self.current_preview_end = None
                self.current_chunk_base = None
                self.loading_next_chunk = False
                return
            extract_duration = min(CHUNK_DURATION + OVERLAP_SECONDS, remaining)
        try:
            segment_file = extract_segment(self.audio_file_path, next_chunk_start, extract_duration)
        except Exception as e:
            QMessageBox.warning(self, "Playback Error", f"Error extracting next segment: {e}")
            self.loading_next_chunk = False
            return
        self.player.stop()
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(segment_file)))
        self.player.setPosition(0)
        self.current_chunk_base = next_chunk_start
        self.current_preview_end = next_chunk_start + CHUNK_DURATION
        self.player.play()
        self.loading_next_chunk = False
    
    def playFromPlayhead(self):
        if self.audio and self.audio_file_path:
            self.current_mode = "full"
            self.current_chunk_base = self.waveformWidget.playhead_time
            remaining = self.audio.duration_seconds - self.current_chunk_base
            extract_duration = min(CHUNK_DURATION + OVERLAP_SECONDS, remaining)
            try:
                segment_file = extract_segment(self.audio_file_path, self.current_chunk_base, extract_duration)
            except Exception as e:
                QMessageBox.warning(self, "Playback Error", f"Error extracting segment: {e}")
                return
            if self.player.state() == QMediaPlayer.PlayingState:
                self.player.stop()
                if self.current_playing_track is not None:
                    self.trackWidgets[self.current_playing_track].playButton.setText("Play")
                    self.current_playing_track = None
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(segment_file)))
            self.player.setPosition(0)
            self.current_preview_end = self.current_chunk_base + CHUNK_DURATION
            self.player.play()
    
    def globalPause(self):
        try:
            if self.player.state() in [QMediaPlayer.PlayingState, QMediaPlayer.PausedState]:
                self.player.pause()
                if self.current_playing_track is not None:
                    self.trackWidgets[self.current_playing_track].playButton.setText("Play")
            else:
                print("Player is not in a state that can be paused.")
        except Exception as e:
            print("Error pausing:", e)
    
    def splitAlbum(self):
        if self.audio is None or not self.tracks:
            QMessageBox.warning(self, "Error", "No audio loaded or tracks defined.")
            return
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return
        normalized_audio = effects.normalize(self.audio)
        for idx, track in enumerate(self.tracks):
            start_ms = int(track["start"] * 1000)
            end_ms = int((track["start"] + track["length"]) * 1000)
            if end_ms <= start_ms:
                continue
            segment = normalized_audio[start_ms:end_ms]
            metadata = {
                "title": track["title"],
                "artist": self.artistEdit.text(),
                "album": self.albumTitleEdit.text(),
                "track": str(idx+1),
                "genre": self.genreEdit.text(),
                "year": self.yearEdit.text(),
                "composer": self.composerEdit.text()
            }
            safe_title = re.sub(r'[\\/:"*?<>|]+', '_', track["title"])
            output_path = os.path.join(output_dir, f"{safe_title}.mp3")
            # Export segment to a temporary file
            temp_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            temp_audio.close()
            segment.export(temp_audio.name, format="mp3", tags=metadata)
            # Embed album cover if available
            if self.album_art_path:
                temp_output = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                temp_output.close()
                try:
                    embed_cover(temp_audio.name, self.album_art_path, temp_output.name)
                    shutil.move(temp_output.name, output_path)
                except Exception as e:
                    QMessageBox.warning(self, "Export Error", f"Error embedding cover for {track['title']}: {str(e)}")
            else:
                shutil.move(temp_audio.name, output_path)
        QMessageBox.information(self, "Success", "Album split successfully!")

def main():
    app = QApplication(sys.argv)
    window = AlbumSplitterMainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

# core/clipboard_monitor.py

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QClipboard, QImage
from PyQt6.QtWidgets import QApplication

class ClipboardMonitor(QObject):
    text_copied = pyqtSignal(str)
    image_copied = pyqtSignal(QImage)

    def __init__(self):
        super().__init__()
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.previous_text = self.clipboard.text()
        self.previous_image = self.clipboard.image()

    def on_clipboard_change(self):
        # Check for text
        current_text = self.clipboard.text()
        if current_text and current_text != self.previous_text:
            self.previous_text = current_text
            self.text_copied.emit(current_text)

        # Check for image
        current_image = self.clipboard.image()
        if not current_image.isNull() and current_image != self.previous_image:
            self.previous_image = current_image
            self.image_copied.emit(current_image)

    def start_monitoring(self):
        self.clipboard.dataChanged.connect(self.on_clipboard_change)

    def stop_monitoring(self):
        self.clipboard.dataChanged.disconnect(self.on_clipboard_change)
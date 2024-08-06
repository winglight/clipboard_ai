# ui/main_window.py

import base64
from PIL import Image
import io
import os
import asyncio
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QLabel, QPushButton, QComboBox, 
                             QListWidgetItem, QTextEdit, QMessageBox, QMenuBar, QMenu,
                             QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, QBuffer, QByteArray, QRunnable, QThreadPool, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QAction, QKeySequence, QGuiApplication, QKeyEvent
from core.clipboard_monitor import ClipboardMonitor
from core.ai_interface import AIInterface, PROMPT_IMAGE, PROMPT_TEXT
from core.database_manager import DatabaseManager
from ui.config_dialog import ConfigDialog

class AIWorker(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(str)
        error = pyqtSignal(str)

    def __init__(self, ai_interface, content, prompt):
        super().__init__()
        self.ai_interface = ai_interface
        self.content = content
        self.prompt = prompt
        self.signals = AIWorker.Signals()

    @pyqtSlot()
    def run(self):
        print("AIWorker started")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.ai_interface.send_to_ai(self.content, self.prompt))
            self.signals.finished.emit(response)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            loop.close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clipboard AI")
        self.setGeometry(100, 100, 800, 600)

        self.clipboard_monitor = ClipboardMonitor()
        self.ai_interface = AIInterface()
        self.db_manager = DatabaseManager()

        self.clips_dir = "clips"
        os.makedirs(self.clips_dir, exist_ok=True)

        self.init_ui()
        self.setup_menu()
        self.load_history()
        self.load_configs()

        self.threadpool = QThreadPool()

        # Connect clipboard monitor signals
        self.clipboard_monitor.text_copied.connect(self.on_text_copied)
        self.clipboard_monitor.image_copied.connect(self.on_image_copied)

        # Check if any AI models are configured
        self.check_ai_config()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.image_viewer = None  # Add this line

        layout = QHBoxLayout()
        central_widget.setLayout(layout)

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.display_clip)

        left_layout.addWidget(QLabel("History:"))
        left_layout.addWidget(self.history_list)

        # Add Clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_history)
        left_layout.addWidget(clear_button)  # 修改这一行

        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        self.clip_display = QLabel()
        self.clip_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clip_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.clip_display.setStyleSheet("QLabel { background-color: white; }")
        self.clip_display.mousePressEvent = self.on_clip_display_click


        self.model_selector = QComboBox()
        self.model_selector.currentIndexChanged.connect(self.change_ai_model)

        self.send_button = QPushButton("Send to AI")
        self.send_button.clicked.connect(self.send_to_ai)

        self.ai_response = QTextEdit()
        self.ai_response.setReadOnly(True)

        right_layout.addWidget(QLabel("Clip Content:"))
        right_layout.addWidget(self.clip_display)
        right_layout.addWidget(QLabel("AI Model:"))
        right_layout.addWidget(self.model_selector)
        right_layout.addWidget(self.send_button)
        right_layout.addWidget(QLabel("AI Response:"))
        right_layout.addWidget(self.ai_response)

        # Add panels to main layout
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)

        # Add keyboard shortcut for delete
        delete_action = QAction("Delete", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self.delete_selected_item)
        self.addAction(delete_action)

    def on_clip_display_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.type() == event.Type.MouseButtonDblClick:
            selected_items = self.history_list.selectedItems()
            if selected_items:
                clip_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
                clip = self.db_manager.get_clip(clip_id)
                _, clip_type, _, file_path, _ = clip
                if clip_type == "image":
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        self.open_image_viewer(pixmap)

    def open_image_viewer(self, pixmap):
        self.image_viewer = ImageViewer(pixmap)
        self.image_viewer.show()
        
    def setup_menu(self):
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")
        
        config_action = QAction("AI Configuration", self)
        config_action.triggered.connect(self.open_config_dialog)
        settings_menu.addAction(config_action)

    def load_history(self):
        clips = self.db_manager.get_all_clips()
        for clip in clips:
            clip_id, clip_type, content, file_path, timestamp = clip
            item = QListWidgetItem(f"{clip_type.capitalize()} - {timestamp}")
            item.setData(Qt.ItemDataRole.UserRole, clip_id)
            self.history_list.addItem(item)

    def load_configs(self):
        self.model_selector.clear()  # Clear existing items before reloading
        configs = self.db_manager.get_configs()
        for config in configs:
            config_id, name, config_type, api_key, model, other_settings = config
            
            try:
                parsed_other_settings = json.loads(other_settings)
            except json.JSONDecodeError:
                parsed_other_settings = {}

            self.model_selector.addItem(f"{name} ({model})", {
                'id': config_id,
                'name': name,
                'type': config_type,
                'api_key': api_key,
                'model': model,
                'other_settings': parsed_other_settings
            })

    def change_ai_model(self, index):
        if index >= 0:
            config = self.model_selector.itemData(index)
            if config:
                self.ai_interface.set_config(config=config)

    def send_to_ai(self):
        selected_items = self.history_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a clip from the history.")
            return

        if not self.ai_interface.current_config:
            QMessageBox.warning(self, "Configuration Error", "Please select an AI model first.")
            return

        clip_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        clip = self.db_manager.get_clip(clip_id)
        _, clip_type, content, file_path, _ = clip

        if clip_type == "image":
            prompt = PROMPT_IMAGE
            # 使用PIL库加载图片对象
            img = Image.open(file_path)
            # img = img.resize((int(img.width/2), int(img.height/2)), resample=Image.LANCZOS)
            img = img.convert("P", palette=Image.ADAPTIVE, colors=256)

            # 将图片对象转换为bytes格式
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            # 获取保存的二进制数据
            img_bytes = img_bytes.getvalue()

            # 将图片bytes转换为base64编码
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            content = img_base64  # For simplicity, we're just sending the file path. In a real application, you might want to send the image data.
        else:
            prompt = PROMPT_TEXT

        worker = AIWorker(self.ai_interface, content, prompt)
        worker.signals.finished.connect(self.display_ai_response)
        worker.signals.error.connect(self.display_error)

        self.threadpool.start(worker)
        self.ai_response.setText("Waiting for AI response...")

    def display_ai_response(self, response):
        self.ai_response.setText(response)

    def display_error(self, error):
        self.ai_response.setText(f"Error: {error}")
        QMessageBox.critical(self, "AI Error", f"An error occurred: {error}")

    def display_clip(self, item):
        clip_id = item.data(Qt.ItemDataRole.UserRole)
        clip = self.db_manager.get_clip(clip_id)
        _, clip_type, content, file_path, _ = clip

        if clip_type == "text":
            self.clip_display.setText(content)
        elif clip_type == "image":
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(self.clip_display.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.clip_display.setPixmap(scaled_pixmap)
            else:
                self.clip_display.setText("Error loading image.")

    def on_text_copied(self, text):
        clip_id = self.db_manager.add_clip("text", text)
        item = QListWidgetItem(f"Text - {clip_id}")
        item.setData(Qt.ItemDataRole.UserRole, clip_id)
        self.history_list.insertItem(0, item)

    def on_image_copied(self, image):
        file_name = f"image_{len(os.listdir(self.clips_dir))}.png"
        file_path = os.path.join(self.clips_dir, file_name)
        image.save(file_path, "PNG")
        
        clip_id = self.db_manager.add_clip("image", "", file_path)
        item = QListWidgetItem(f"Image - {clip_id}")
        item.setData(Qt.ItemDataRole.UserRole, clip_id)
        self.history_list.insertItem(0, item)

    def check_ai_config(self):
        configs = self.db_manager.get_configs()
        if not configs:
            self.open_config_dialog()

    def open_config_dialog(self):
        config_dialog = ConfigDialog(self.db_manager)
        if config_dialog.exec():
            # 如果对话框被接受（用户点击了"确定"），重新加载配置
            self.load_configs()

    def clear_history(self):
        reply = QMessageBox.question(self, "Clear History", 
                                     "Are you sure you want to clear all history?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.history_list.clear()
            self.content_display.clear()
            self.db_manager.clear_history()

    def delete_selected_item(self):
        current_item = self.history_list.currentItem()
        if current_item:
            row = self.history_list.row(current_item)
            self.history_list.takeItem(row)
            if self.history_list.count() == 0:
                self.content_display.clear()
            clip_id = current_item.data(Qt.ItemDataRole.UserRole)
            self.db_manager.delete_chat(clip_id)

class ImageViewer(QMainWindow):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        self.original_pixmap = pixmap
        self.init_ui()
        self.adjust_window_size()

    def init_ui(self):
        self.scroll_area = QScrollArea(self)
        self.setCentralWidget(self.scroll_area)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(True)

    def adjust_window_size(self):
        screen = QGuiApplication.primaryScreen().geometry()
        image_ratio = self.original_pixmap.width() / self.original_pixmap.height()
        screen_ratio = screen.width() / screen.height()

        if image_ratio > screen_ratio:  # 横版图片
            new_width = screen.width()
            new_height = int(new_width / image_ratio)
        else:  # 竖版图片
            new_height = screen.height()
            new_width = int(new_height * image_ratio)

        self.resize(new_width, new_height)
        self.center_on_screen()
        self.update_image()

    def update_image(self):
        scaled_pixmap = self.original_pixmap.scaled(
            self.scroll_area.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()

    def center_on_screen(self):
        screen = QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2,
                  (screen.height() - size.height()) // 2)
        
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
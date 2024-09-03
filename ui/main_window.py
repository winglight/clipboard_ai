# ui/main_window.py

import base64
from PIL import Image
import io
import os
import time
import shutil
import asyncio
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QLabel, QPushButton, QComboBox, 
                             QListWidgetItem, QTextEdit, QMessageBox, QMenuBar, QMenu,
                             QScrollArea, QSizePolicy, QSplitter)
from PyQt6.QtCore import Qt, QBuffer, QByteArray, QRunnable, QThreadPool, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap, QAction, QKeySequence, QGuiApplication, QKeyEvent
from core.clipboard_monitor import ClipboardMonitor
from core.ai_interface import AIInterface, PROMPT_IMAGE, PROMPT_TEXT
from core.database_manager import DatabaseManager
from ui.config_dialog import ConfigDialog

class AIWorker(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal(str, float)  # 添加处理时间
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
            start_time = time.time()  # 记录开始时间
            response = loop.run_until_complete(self.ai_interface.send_to_ai(self.content, self.prompt))
            end_time = time.time()  # 记录结束时间
            processing_time = end_time - start_time  # 计算处理时间
            self.signals.finished.emit(response, processing_time)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            loop.close()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clipboard AI")
        self.setGeometry(100, 100, 1000, 700)  # 调整初始窗口大小

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

        self.image_viewer = None

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # 创建主分割器
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # 左面板
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.display_clip)

        left_layout.addWidget(QLabel("History:"))
        left_layout.addWidget(self.history_list)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_history)
        left_layout.addWidget(clear_button)

        # 右面板
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)

        # 创建右面板的分割器
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(self.right_splitter)

        # 上部分：剪贴内容显示
        upper_widget = QWidget()
        upper_layout = QVBoxLayout()
        upper_widget.setLayout(upper_layout)

        self.clip_display = QTextEdit()  # 改用 QTextEdit
        self.clip_display.setReadOnly(True)
        self.clip_display.setAlignment(Qt.AlignmentFlag.AlignLeft)  # 文本左对齐
        self.clip_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.clip_display.setStyleSheet("QTextEdit { background-color: white; }")

        upper_layout.addWidget(QLabel("Clip Content:"))
        upper_layout.addWidget(self.clip_display)

        # 下部分：AI 相关控件
        lower_widget = QWidget()
        lower_layout = QVBoxLayout()
        lower_widget.setLayout(lower_layout)

        self.model_selector = QComboBox()
        self.model_selector.currentIndexChanged.connect(self.change_ai_model)

        self.send_button = QPushButton("Send to AI")
        self.send_button.clicked.connect(self.send_to_ai)

        self.ai_response = QTextEdit()
        self.ai_response.setReadOnly(True)

        self.ai_response_time_label = QLabel() 

        lower_layout.addWidget(QLabel("AI Model:"))
        lower_layout.addWidget(self.model_selector)
        lower_layout.addWidget(self.send_button)
        lower_layout.addWidget(QLabel("AI Response:"))
        lower_layout.addWidget(self.ai_response)
        lower_layout.addWidget(self.ai_response_time_label) 

        # 添加部件到右面板分割器
        self.right_splitter.addWidget(upper_widget)
        self.right_splitter.addWidget(lower_widget)

        # 设置初始大小
        self.right_splitter.setSizes([350, 350])

        # 添加面板到主分割器
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(right_panel)

        # 设置左面板的固定宽度
        left_panel.setMinimumWidth(200)
        left_panel.setMaximumWidth(300)

        # 添加键盘快捷键
        delete_action = QAction("Delete", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self.delete_selected_item)
        self.addAction(delete_action)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 调整右面板分割器的大小
        total_height = self.right_splitter.height()
        self.right_splitter.setSizes([total_height // 2, total_height // 2])

    def display_clip(self, item):
        clip_id = item.data(Qt.ItemDataRole.UserRole)
        clip = self.db_manager.get_clip(clip_id)
        _, clip_type, content, file_path, _, ai_response, processing_time = clip

        if clip_type == "text":
            self.clip_display.setPlainText(content)
        elif clip_type == "image":
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.clip_display.clear()
                self.clip_display.insertHtml(f'<img src="{file_path}" width="100%">')
            else:
                self.clip_display.setPlainText("Error loading image.")
        if ai_response:
            self.ai_response.setPlainText(ai_response)
            if processing_time:
                self.ai_response_time_label.setText(f"Processing time: {processing_time}")
            else:
                self.ai_response_time_label.setText("")
        else:
            self.ai_response.setPlainText("")
            self.ai_response_time_label.setText("")

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
            clip_id, clip_type, content, file_path, timestamp, ai_response, processing_time = clip
            item = QListWidgetItem(f"{clip_type.capitalize()} - {timestamp}")
            item.setData(Qt.ItemDataRole.UserRole, clip_id)
            self.history_list.addItem(item)

    def load_configs(self):
        self.model_selector.clear()
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
        _, clip_type, content, file_path, _, _, _ = clip

        if clip_type == "image":
            prompt = PROMPT_IMAGE
            img = Image.open(file_path)
            img = img.convert("P", palette=Image.ADAPTIVE, colors=256)

            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes = img_bytes.getvalue()

            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            content = img_base64
        else:
            prompt = PROMPT_TEXT

        worker = AIWorker(self.ai_interface, content, prompt)
        worker.signals.finished.connect(lambda response, time: self.display_ai_response(response, time, clip_id))
        worker.signals.error.connect(self.display_error)

        self.threadpool.start(worker)
        self.ai_response.setText("Waiting for AI response...")
        self.ai_response_time_label.setText("Processing...")

    def display_ai_response(self, response, processing_time, clip_id):
        self.ai_response.setText(response)
        
        # 格式化处理时间
        formatted_time = f"{processing_time:.2f} seconds"
        
        # 更新AI响应时间标签
        self.ai_response_time_label.setText(f"Processing time: {formatted_time}")
        
        # 保存 AI 响应和处理时间到数据库
        self.db_manager.update_clip_response(clip_id, response, formatted_time)
        
        # 更新历史列表项
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == clip_id:
                item.setText(f"{item.text()} (AI processed)")
                break

    def display_error(self, error):
        self.ai_response.setText(f"Error: {error}")
        QMessageBox.critical(self, "AI Error", f"An error occurred: {error}")

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
        config_dialog = ConfigDialog(self.db_manager, self)
        if config_dialog.exec():
            self.load_configs()

    def clear_history(self):
        reply = QMessageBox.question(self, "Clear History", 
                                     "Are you sure you want to clear all history?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.history_list.clear()
            self.db_manager.clear_history()
            shutil.rmtree(self.clips_dir)
            os.makedirs(self.clips_dir, exist_ok=True)

    def delete_selected_item(self):
        current_item = self.history_list.currentItem()
        if current_item:
            row = self.history_list.row(current_item)
            self.history_list.takeItem(row)
            clip_id = current_item.data(Qt.ItemDataRole.UserRole)
            clip = self.db_manager.get_clip(clip_id)
            self.db_manager.delete_chat(clip_id)
            
            _, clip_type, content, file_path, _ = clip
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

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
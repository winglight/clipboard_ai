# ui/config_dialog.py

import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QComboBox, QPushButton, QListWidget, QListWidgetItem, 
                             QMessageBox, QTextEdit, QFormLayout, QWidget, QStackedWidget)
from PyQt6.QtCore import Qt

class ConfigDialog(QDialog):
    def __init__(self, db_manager, parent):
        super().__init__()
        self.db_manager = db_manager
        self.parent = parent
        self.setWindowTitle("AI Configuration")
        self.setGeometry(200, 200, 700, 500)
        self.current_config_id = None
        self.init_ui()
        self.load_configs()

    def init_ui(self):
        layout = QHBoxLayout()

        # Left panel: list of configurations
        left_panel = QVBoxLayout()
        self.config_list = QListWidget()
        self.config_list.itemClicked.connect(self.load_config)
        left_panel.addWidget(QLabel("Configurations:"))
        left_panel.addWidget(self.config_list)

        add_button = QPushButton("Add New")
        add_button.clicked.connect(self.add_new_config)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.delete_config)
        button_layout = QHBoxLayout()
        button_layout.addWidget(add_button)
        button_layout.addWidget(delete_button)
        left_panel.addLayout(button_layout)

        # Right panel: configuration details
        right_panel = QVBoxLayout()
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.type_input = QComboBox()
        self.type_input.addItems(["openai", "ollama"])
        self.type_input.currentIndexChanged.connect(self.on_type_changed)

        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Type:", self.type_input)

        self.stacked_widget = QStackedWidget()

        # OpenAI specific fields
        openai_widget = QWidget()
        openai_layout = QFormLayout()
        self.openai_api_key_input = QLineEdit()
        self.openai_model_input = QLineEdit()
        openai_layout.addRow("API Key:", self.openai_api_key_input)
        openai_layout.addRow("Model:", self.openai_model_input)
        openai_widget.setLayout(openai_layout)

        # Ollama specific fields
        ollama_widget = QWidget()
        ollama_layout = QFormLayout()
        self.ollama_api_url_input = QLineEdit()
        self.ollama_model_input = QLineEdit()
        ollama_layout.addRow("API URL:", self.ollama_api_url_input)
        ollama_layout.addRow("Model:", self.ollama_model_input)
        ollama_widget.setLayout(ollama_layout)

        self.stacked_widget.addWidget(openai_widget)
        self.stacked_widget.addWidget(ollama_widget)

        form_layout.addRow(self.stacked_widget)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_config)

        right_panel.addLayout(form_layout)
        right_panel.addWidget(save_button)

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 2)

        self.setLayout(layout)

    def load_configs(self):
        self.config_list.clear()
        configs = self.db_manager.get_configs()
        for config in configs:
            config_id, name, _, _, _, _ = config
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, config_id)
            self.config_list.addItem(item)

    def load_config(self, item):
        self.current_config_id = item.data(Qt.ItemDataRole.UserRole)
        config = self.db_manager.get_config(self.current_config_id)
        if config:
            _, name, config_type, api_key, model, other_settings = config
            self.name_input.setText(name)
            index = self.type_input.findText(config_type)
            if index >= 0:
                self.type_input.setCurrentIndex(index)
            if config_type == "openai":
                self.openai_api_key_input.setText(api_key)
                self.openai_model_input.setText(model)
            elif config_type == "ollama":
                self.ollama_model_input.setText(model)
            try:
                if other_settings and isinstance(other_settings, str):
                    other_settings_dict = json.loads(other_settings)
                    if isinstance(other_settings_dict, dict):
                        self.ollama_api_url_input.setText(other_settings_dict.get('api_url', ''))
                    else:
                        self.ollama_api_url_input.setText('')
                else:
                    self.ollama_api_url_input.setText('')
            except json.JSONDecodeError:
                self.ollama_api_url_input.setText('')

    def on_type_changed(self, index):
        self.stacked_widget.setCurrentIndex(index)

    def add_new_config(self):
        self.current_config_id = None
        self.name_input.clear()
        self.openai_api_key_input.clear()
        self.openai_model_input.clear()
        self.ollama_api_url_input.clear()
        self.ollama_model_input.clear()
        self.type_input.setCurrentIndex(0)

    def delete_config(self):
        current_item = self.config_list.currentItem()
        if current_item:
            config_id = current_item.data(Qt.ItemDataRole.UserRole)
            reply = QMessageBox.question(self, "Delete Configuration", 
                                         "Are you sure you want to delete this configuration?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.db_manager.delete_config(config_id)
                self.load_configs()
                self.add_new_config()  # Clear the form after deletion
                self.parent.load_configs()

    def save_config(self):
        name = self.name_input.text()
        if not name:
            QMessageBox.warning(self, "Invalid Input", "Name cannot be empty.")
            return

        config_type = self.type_input.currentText()
        if config_type == "openai":
            api_key = self.openai_api_key_input.text()
            model = self.openai_model_input.text()
            other_settings = '{}'
        elif config_type == "ollama":
            api_key = ''
            model = self.ollama_model_input.text()
            api_url = self.ollama_api_url_input.text()
            other_settings = {'api_url': api_url}
        
        if self.current_config_id is not None:
            # Update existing config
            self.db_manager.update_config(self.current_config_id, name, config_type, api_key, model, other_settings)
        else:
            # Check if a config with this name already exists
            existing_configs = self.db_manager.get_configs()
            if any(config[1] == name for config in existing_configs):
                QMessageBox.warning(self, "Duplicate Name", "A configuration with this name already exists.")
                return
            # Add new config
            self.db_manager.add_config(name, config_type, api_key, model, other_settings)
        
        self.load_configs()
        # Select the newly added or updated item
        items = self.config_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.config_list.setCurrentItem(items[0])
            self.load_config(items[0])
        self.parent.load_configs()

    def closeEvent(self, event):
        self.load_configs()
        super().closeEvent(event)
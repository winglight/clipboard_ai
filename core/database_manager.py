# core/database_manager.py

import sqlite3
import json
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name="clipboard_ai.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        # Create clips table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            content TEXT,
            file_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create configs table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            api_key TEXT,
            model TEXT NOT NULL,
            other_settings TEXT
        )
        ''')
        self.conn.commit()

    def add_clip(self, clip_type, content, file_path=""):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute('''
        INSERT INTO clips (type, content, file_path, timestamp)
        VALUES (?, ?, ?, ?)
        ''', (clip_type, content, file_path, timestamp))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_clip(self, clip_id):
        self.cursor.execute('SELECT * FROM clips WHERE id = ?', (clip_id,))
        return self.cursor.fetchone()

    def get_all_clips(self):
        self.cursor.execute('SELECT * FROM clips ORDER BY timestamp DESC')
        return self.cursor.fetchall()

    def add_config(self, name, config_type, api_key, model, other_settings=None):
        other_settings_json = json.dumps(other_settings) if other_settings else None
        self.cursor.execute('''
        INSERT INTO configs (name, type, api_key, model, other_settings)
        VALUES (?, ?, ?, ?, ?)
        ''', (name, config_type, api_key, model, other_settings_json))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_configs(self):
        self.cursor.execute('SELECT * FROM configs')
        return self.cursor.fetchall()
    
    def get_config(self, config_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM configs WHERE id = ?", (config_id,))
        config = cursor.fetchone()
        cursor.close()
        return config

    def update_config(self, config_id, name, config_type, api_key, model, other_settings=None):
        other_settings_json = json.dumps(other_settings) if other_settings else None
        self.cursor.execute('''
        UPDATE configs
        SET name = ?, type = ?, api_key = ?, model = ?, other_settings = ?
        WHERE id = ?
        ''', (name, config_type, api_key, model, other_settings_json, config_id))
        self.conn.commit()

    def delete_config(self, config_id):
        self.cursor.execute('DELETE FROM configs WHERE id = ?', (config_id,))
        self.conn.commit()
    
    def delete_chat(self, clip_id):
        self.cursor.execute('DELETE FROM clips WHERE id = ?', (clip_id,))
        self.conn.commit()

    def clear_history(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM clips")
        self.conn.commit()
        
    def close(self):
        self.conn.close()
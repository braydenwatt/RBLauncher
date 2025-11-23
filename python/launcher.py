import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFrame, QToolButton, QMenu, QAction, QScrollArea,
                             QLayout, QSizePolicy, QSplitter)
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter, QPainterPath, QPen
from PyQt5.QtCore import Qt, QSize, QRect, QPoint, QItemSelection, QRectF
import os
import json
import subprocess
import webbrowser
from add_instance_window import add_instance_window
from manage_mods import manage_modsWindow
from account_window import AccountWindow
from edit_instance import EditInstanceWindow
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from settings_window import SetWindow
import zipfile
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QProgressDialog, QPlainTextEdit
import shutil
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette
import threading
import sip
import requests
import time
import re
import re
from PyQt5.QtWidgets import QTextEdit, QPlainTextEdit
from PyQt5.QtGui import QTextCharFormat, QColor, QTextCursor
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
from progress_dialog import ProgressDialog

# Custom FlowLayout for wrapping widgets to new rows
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=-1):
        super(FlowLayout, self).__init__(parent)
        
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        
        self.setSpacing(spacing)
        self.horizontal_spacing = spacing
        self.vertical_spacing = spacing
        self.itemList = []
    
    def setVerticalSpacing(self, spacing):
        """Set vertical spacing between rows"""
        self.vertical_spacing = spacing
    
    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)
    
    def addItem(self, item):
        self.itemList.append(item)
    
    def count(self):
        return len(self.itemList)
    
    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None
    
    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None
    
    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, width):
        height = self.doLayout(QRect(0, 0, width, 0), True)
        return height
    
    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self.doLayout(rect, False)
    
    def sizeHint(self):
        return self.minimumSize()
    
    def minimumSize(self):
        size = QSize()
        
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
            
        margin = self.contentsMargins().left()
        size += QSize(2 * margin, 2 * margin)
        return size
    
    def doLayout(self, rect, testOnly):
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        
        for item in self.itemList:
            wid = item.widget()
            # Use our custom spacing values
            spaceX = self.horizontal_spacing
            spaceY = self.vertical_spacing
                
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
                
            if not testOnly:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
                
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
            
        return y + lineHeight - rect.y()

CONFIG_PATH = os.path.expanduser("~/.minecraft_launcher_config.json")
GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
if not os.path.exists(GAME_DIR):
    os.mkdir(GAME_DIR)

class LogSignalEmitter(QObject):
    log_signal = pyqtSignal(str)

class InstallationWorker(QObject):
    """Worker for handling installations in a separate thread."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # Success status, message

    def __init__(self, instance_data, java_path):
        super().__init__()
        self.instance_data = instance_data
        self.java_path = java_path
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        try:
            self.progress.emit(f"DEBUG: Starting installation worker")
            self.progress.emit(f"DEBUG: Instance data keys: {list(self.instance_data.keys())}")
            instance_type = self.instance_data.get('type')
            self.progress.emit(f"DEBUG: Instance type: {instance_type}")
            
            if instance_type == "Modrinth":
                self.progress.emit("DEBUG: Installing Modrinth pack...")
                self.install_modrinth_pack()
            else:
                self.progress.emit("DEBUG: Installing vanilla or fabric...")
                self.install_vanilla_or_fabric()
            
            if not self._should_stop:
                self.progress.emit("DEBUG: Installation completed successfully")
                self.finished.emit(True, "Installation completed successfully!")

        except Exception as e:
            self.progress.emit(f"DEBUG: Exception in worker run: {type(e).__name__}: {e}")
            import traceback
            self.progress.emit(f"DEBUG: Traceback: {traceback.format_exc()}")
            self.finished.emit(False, f"An error occurred: {e}")

    def execute_process(self, args):
        """Executes a subprocess and emits its output."""
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        for line in process.stdout:
            if self._should_stop:
                process.terminate()
                self.progress.emit("Installation cancelled.")
                self.finished.emit(False, "Installation cancelled by user.")
                return False # Indicate failure
            self.progress.emit(line.strip())
        process.wait()
        
        if process.returncode != 0:
            self.progress.emit(f"Script finished with error code: {process.returncode}")
            return False # Indicate failure
            
        return True # Indicate success

    def install_modrinth_pack(self):
        """Handles the installation of a Modrinth modpack."""
        self.progress.emit("Setting up instance directories...")
        name = self.instance_data['name']
        self.progress.emit(f"DEBUG: Instance name: {name}")
        
        INSTANCE_DIR = f"{GAME_DIR}/instances/{name}"
        MOD_DIR = f"{INSTANCE_DIR}/mods"
        RESOURCE_DIR = f"{INSTANCE_DIR}/resourcepacks"
        
        self.progress.emit(f"DEBUG: Creating directories at {INSTANCE_DIR}")
        os.makedirs(MOD_DIR, exist_ok=True)
        os.makedirs(RESOURCE_DIR, exist_ok=True)

        self.progress.emit("Downloading modpack files...")
        
        # Get the actual files to download (not mod metadata)
        file_data = self.instance_data.get('mods', [])
        self.progress.emit(f"DEBUG: file_data type: {type(file_data)}")
        self.progress.emit(f"DEBUG: file_data length: {len(file_data) if isinstance(file_data, list) else 'not a list'}")
        
        # Also log mod_data for reference
        mod_data = self.instance_data.get('mod_data', [])
        self.progress.emit(f"DEBUG: mod_data (metadata) length: {len(mod_data) if isinstance(mod_data, list) else 'not a list'}")
        
        total_files = len(file_data)
        self.progress.emit(f"DEBUG: Total files to process: {total_files}")
        
        if total_files == 0:
            self.progress.emit("WARNING: No files found to download. Checking instance_data structure...")
            self.progress.emit(f"DEBUG: Available keys in instance_data: {list(self.instance_data.keys())}")
            return
        
        for i, file_entry in enumerate(file_data):
            if self._should_stop: return
            self.progress.emit(f"DEBUG: Processing file {i+1}/{total_files}")
            self.progress.emit(f"DEBUG: File entry keys: {list(file_entry.keys()) if isinstance(file_entry, dict) else 'not a dict'}")
            
            try:
                path = file_entry["path"]
                self.progress.emit(f"DEBUG: File path: {path}")
            except KeyError as e:
                self.progress.emit(f"ERROR: Missing 'path' key in file entry: {file_entry}")
                self.progress.emit(f"ERROR: Available keys: {list(file_entry.keys()) if isinstance(file_entry, dict) else 'not a dict'}")
                continue
                
            try:
                url = file_entry["downloads"][0]
                self.progress.emit(f"DEBUG: Download URL: {url}")
            except (KeyError, IndexError) as e:
                self.progress.emit(f"ERROR: Missing or invalid 'downloads' in file entry: {file_entry}")
                continue
                
            output_path = os.path.join(INSTANCE_DIR, path)
            self.progress.emit(f"DEBUG: Output path: {output_path}")
            
            self.progress.emit(f"Downloading {os.path.basename(path)} ({i+1}/{total_files})...")
            
            # Create subdirectories if they don't exist
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                self.progress.emit(f"DEBUG: Created directory: {os.path.dirname(output_path)}")
            except Exception as e:
                self.progress.emit(f"ERROR: Failed to create directory {os.path.dirname(output_path)}: {e}")
                continue

            try:
                self.progress.emit(f"DEBUG: Starting download from {url}")
                response = requests.get(url, stream=True, timeout=15)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                self.progress.emit(f"DEBUG: File size: {total_size} bytes")
                
                with open(output_path, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._should_stop:
                            self.progress.emit("Cancelling download...")
                            return
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and downloaded % (total_size // 10 + 1) == 0:
                                self.progress.emit(f"DEBUG: Downloaded {downloaded}/{total_size} bytes")
                
                self.progress.emit(f"DEBUG: Successfully downloaded {os.path.basename(path)}")
                
            except Exception as e:
                self.progress.emit(f"ERROR: Failed to download {os.path.basename(path)}: {e}")
                self.progress.emit(f"DEBUG: Exception type: {type(e).__name__}")
                # Continue with other files
        
        self.progress.emit("All modpack files downloaded.")

        modloader = self.instance_data['section']
        if modloader == "Fabric":
            self.progress.emit("Installing Fabric...")
            version = self.instance_data['selected_version']
            fabric_version = self.instance_data['selected_fabric_version'].replace("Fabric", "").strip()
            install_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "install_fabric.sh")
            args = [install_script, version, fabric_version, self.java_path]
            self.execute_process(args)

    def install_vanilla_or_fabric(self):
        """Handles Vanilla or Fabric installation."""
        self.progress.emit("Setting up instance directory...")
        name = self.instance_data['name']
        INSTANCE_DIR = f"{GAME_DIR}/instances/{name}"
        os.makedirs(INSTANCE_DIR, exist_ok=True)

        modloader = self.instance_data['section']
        version = self.instance_data['selected_version']
        
        if modloader == "Fabric":
            self.progress.emit("Installing Fabric...")
            fabric_version = self.instance_data['selected_fabric_version'].replace("Fabric", "").strip()
            install_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "install_fabric.sh")
            args = [install_script, version, fabric_version, self.java_path]
            self.execute_process(args)
        elif modloader == "Vanilla":
            self.progress.emit("Downloading Vanilla client...")
            install_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "download_vanilla.sh")
            args = [install_script, version, self.java_path]
            self.execute_process(args)

class MinecraftLauncherUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.themes = {
            "creeper": {
                "background": "#2D2D2D",
                "text": "#FFFFFF",
                "button_bg": "#5CA64C",
                "button_hover": "#4D4D4D",
                "frame_bg": "#222222",
                "instance_bg": "#333333",
                "instance_border": "#5CA64C",
                "icon_bg": "#3D3D3D",
                "selected_bg": "#5CA64C",
                "selected_border": "#5CA64C",
            },
            "dark": {
                "background": "#2D2D2D",
                "text": "#FFFFFF",
                "button_bg": "#3D3D3D",
                "button_hover": "#4D4D4D",
                "frame_bg": "#222222",
                "instance_bg": "#333333",
                "instance_border": "#4D4D4D",
                "icon_bg": "#3D3D3D",
                "selected_bg": "#007AFF",
                "selected_border": "#007AFF",
            },
            "oled": {
                "background": "#0A0A0A",      
                "text": "#FFFFFF",            
                "button_bg": "#1A1A1A",         
                "button_hover": "#2A2A2A",    
                "frame_bg": "#101010",          
                "instance_bg": "#1C1C1C",     
                "instance_border": "#2E2E2E",   
                "icon_bg": "#1A1A1A",        
                "selected_bg": "#0A84FF",      
                "selected_border": "#2997FF"   
            },
            "light": {
                "background": "#F5F5F5",
                "text": "#3B3B3B",
                "button_bg": "#E0E0E0",
                "button_hover": "#D5D5D5",
                "frame_bg": "#FFFFFF",
                "instance_bg": "#F0F0F0",
                "instance_border": "#CCCCCC",
                "icon_bg": "#E0E0E0",
                "selected_bg": "#007AFF",
                "selected_border": "#007AFF"
            },
            "guardian": {
                "background": "#2D2D2D",
                "text": "#FFFFFF",
                "button_bg": "#2C3E50",           # deep navy
                "button_hover": "#34495E",        # soft slate
                "frame_bg": "#222222",            # dark blue-gray
                "instance_bg": "#263238",         # dark slate
                "instance_border": "#00BCD4",     # cyan
                "icon_bg": "#1A2A30",             # deep blue
                "selected_bg": "#FF9800",         # orange accent
                "selected_border": "#00ACC1"      # cyan accent
            },
            "enderman": {
                "background": "#0A0A0A",
                "text": "#E0D7FF",                # pale purple-white
                "button_bg": "#1A001A",           # deep purple-black
                "button_hover": "#2A0033",        # muted purple
                "frame_bg": "#100010",            # subtle purple tint
                "instance_bg": "#1C001C",
                "instance_border": "#7D3C98",     # amethyst purple
                "icon_bg": "#1A001A",
                "selected_bg": "#BB86FC",         # vibrant purple
                "selected_border": "#9C27B0"      # richer purple
            },
            "blaze": {
                "background": "#FFF5E1",           # warm cream
                "text": "#3B1F00",                 # dark brown
                "button_bg": "#FFCC80",            # soft orange
                "button_hover": "#FFB74D",         # deeper orange
                "frame_bg": "#FFFFFF",
                "instance_bg": "#FFE0B2",
                "instance_border": "#FF9800",      # vivid orange
                "icon_bg": "#FFD180",
                "selected_bg": "#FF5722",          # blaze orange
                "selected_border": "#FFC107"       # golden yellow
            },
        }
        self.ansi_colors = {
            '30': '#000000',  # Black
            '31': '#FF0000',  # Red
            '32': '#00FF00',  # Green
            '33': '#FFFF00',  # Yellow
            '34': '#0000FF',  # Blue
            '35': '#FF00FF',  # Magenta
            '36': '#00FFFF',  # Cyan
            '37': '#FFFFFF',  # White
            '90': '#808080',  # Bright Black (Gray)
            '91': '#FF6B6B',  # Bright Red
            '92': '#4ECDC4',  # Bright Green
            '93': '#FFE66D',  # Bright Yellow
            '94': '#6B73FF',  # Bright Blue
            '95': '#FF6BFF',  # Bright Magenta
            '96': '#6BFFFF',  # Bright Cyan
            '97': '#FFFFFF',  # Bright White
        }
        self.setWindowTitle("RBL: Dawn")
        self.current_theme = "dark"
        self.instances = {}
        self.instances_data = {}
        self.selected_instance_name = None
        self.selected_instance_widget = None
        self.selected_instance_label = None
        self.instance_icon = None
        self.instance_name = None
        self.instance_window = None
        self.mod_window = None
        self.username = ""
        self.uuid = ""
        self.access_token = ""
        self.settings_window = None
        self.account_window = None
        self.account_data = None
        self.log_emitter = LogSignalEmitter()
        self.log_emitter.log_signal.connect(self.append_log_to_viewer)
        self.log_viewer = None
        self.show_log = False
        self.side = 1
        self.java_path = ''
        self.active_instances = {}

        # UI Components - stored as instance variables for easy access
        self.central_widget = None
        self.main_layout = None
        self.left_scroll_area = None
        self.left_content_widget = None
        self.left_layout = None
        self.right_widget = None
        self.right_layout = None
        self.flow_layout = None
        self.section_frame = None

        # Load config and setup UI
        config = self.load_config()
        self.current_theme = config.get("theme", "dark")
        instances_list = config.get("instances", [""])
        self.instances_data = config.get("instances", [""])
        self.username = config.get("username", "")
        self.uuid = config.get("UUID", "")
        self.access_token = config.get("access_token", "")
        print(self.instances_data)

        self.setup_ui()
        self.apply_theme(self.current_theme)
        self.refresh_instances()
        
    def load_config(self):
        default_config = {
            "theme": "dark",
            "instances": {}
        }

        if os.path.exists(CONFIG_PATH):
            print("loading config")
            config = {}
            try:
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)
                    self.instances_data = config.get('instances')
                    print("INSTANCE DATA ", self.instances_data)
                    self.java_path = config.get('java_path')
                    return config
            except Exception as e:
                print("Error loading config:", e)

        # If file doesn't exist or fails to load, return and save default config
        print("Creating default config...")
        with open(CONFIG_PATH, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config

    def save_config(self):
        if self.java_path == '':
            java_path = shutil.which("java")
            if java_path:
                print(f"Java found at: {java_path}")
                self.java_path = java_path
            else:
                print("Java not found in PATH.")

        config = {
            "theme": self.current_theme,
            "java_path": self.java_path,
            "instances": self.instances_data,  # Save the full dict, not just keys
            "username": self.username,
            "UUID": self.uuid,
            "access_token": self.access_token
        }
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print("Error saving config:", e)

        print("JAVA PATH ", self.java_path)
        

    def build_stylesheet(self, colors):
        return f"""
        QMainWindow {{
            background-color: {colors['background']};
            color: {colors['text']};
        }}
        QPushButton, QToolButton {{
            background-color: {colors['button_bg']};
            color: {colors['text']};
            border-radius: 4px;
            border: none;
            padding: 5px;
        }}
        QPushButton:hover, QToolButton:hover {{
            background-color: {colors['button_hover']};
        }}
        QFrame {{
            background-color: {colors['frame_bg']};
            border: none;
        }}
        QLabel {{
            color: {colors['text']};
        }}
        QLabel[class="instance-name"] {{
            padding: 2px;
            border: 2px solid transparent;
            border-radius: 1px
        }}
        QLabel[class="instance-name"][selected="true"] {{
            border: 2px solid {colors['selected_border']};
            border-radius: 1px;
            background-color: {colors['selected_bg']};
            color: white;
        }}
        QScrollArea {{
            background-color: {colors['frame_bg']};
            border: none;
        }}
        """

    def setup_ui(self):
        """Initial UI setup - called once"""
        # Main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # Setup top menu
        self.setup_top_menu()
        
        # Setup main content area
        self.setup_main_content()

    def load_colored_svg_icon(self, file_path):
        color = self.themes[self.current_theme]['text']

        with open(file_path, 'r') as f:
            svg_content = f.read()

        # Replace fill="#xxxxxx"
        svg_content = re.sub(r'fill="#[0-9a-fA-F]{6}"', f'fill="{color}"', svg_content)

        # Replace fill: rgb(r, g, b) with fill="{color}"
        svg_content = re.sub(r'style="fill:\s*rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)\s*;"', f'fill="{color}"', svg_content)

        # Proceed with rendering to QIcon as you have
        from PyQt5.QtSvg import QSvgRenderer
        from PyQt5.QtGui import QPixmap, QPainter, QIcon
        from PyQt5.QtCore import Qt, QSize

        svg_renderer = QSvgRenderer(bytearray(svg_content, encoding='utf-8'))
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        svg_renderer.render(painter)
        painter.end()

        return QIcon(pixmap)


    def refresh_top_menu(self):
        """Refresh top menu appearance based on the current theme."""
        # Update icons to match new theme colors
        self.update_button_icon(self.add_instance_btn, ".icons/new.svg")
        self.update_button_icon(self.folders_btn, ".icons/folder.svg")
        self.update_button_icon(self.settings_btn, ".icons/settings.svg")
        self.update_button_icon(self.help_btn, ".icons/help.svg")
        self.update_button_icon(self.accounts_btn, f".icons/{self.username}.png", is_svg=False)

    def update_button_icon(self, button, icon_path, is_svg=True):
        """Helper to update a button's icon using the current theme."""
        if is_svg:
            icon = self.load_colored_svg_icon(icon_path)
        else:
            icon = QIcon(icon_path)
        button.setIcon(icon)

    def setup_top_menu(self):
        """Setup the top menu bar"""
        top_menu = QHBoxLayout()
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

        # Create buttons
        self.add_instance_btn = QPushButton("Add Instance")
        icon = self.load_colored_svg_icon(".icons/new.svg") 
        self.add_instance_btn.setIcon(icon)
        self.add_instance_btn.clicked.connect(self.add_instance)

        self.folders_btn = QPushButton("Open Folder")
        icon2 = self.load_colored_svg_icon(".icons/folder.svg")
        self.folders_btn.setIcon(icon2)
        self.folders_btn.clicked.connect(self.open_folders)

        self.settings_btn = QPushButton("Settings")
        icon3 = self.load_colored_svg_icon(".icons/settings.svg")
        self.settings_btn.setIcon(icon3)
        self.settings_btn.clicked.connect(self.open_settings)

        self.help_btn = QPushButton("Help")
        icon4 = self.load_colored_svg_icon(".icons/help.svg")
        self.help_btn.setIcon(icon4)
        self.help_btn.clicked.connect(self.show_help)

        self.accounts_btn = QPushButton("Account")
        self.accounts_btn.setIcon(QIcon(f".icons/{self.username}.png"))
        self.accounts_btn.clicked.connect(self.manage_accounts)

        theme_btn = QToolButton()
        theme_btn.setText("Theme")
        theme_menu = QMenu()

        # Apply button styles
        button_style = """
            QPushButton, QToolButton {
                border-radius: 6px;
                qproperty-iconSize: 16px 16px;
            }
        """

        for btn in [self.add_instance_btn, self.folders_btn, self.settings_btn, self.help_btn, self.accounts_btn, theme_btn]:
            btn.setStyleSheet(button_style)

        # Setup theme menu
        dark_action = QAction("Dark", self)
        creeper_action = QAction("Creeper", self)
        light_action = QAction("Light", self)
        oled_action = QAction("Oled", self)

        theme_menu.addAction(dark_action)
        theme_menu.addAction(creeper_action)
        theme_menu.addAction(light_action)
        theme_menu.addAction(oled_action)

        theme_btn.setMenu(theme_menu)
        theme_btn.setPopupMode(QToolButton.InstantPopup)

        # Add to layout
        top_menu.addWidget(self.add_instance_btn)
        top_menu.addWidget(self.folders_btn)
        top_menu.addWidget(self.settings_btn)
        top_menu.addWidget(self.help_btn)
        top_menu.addStretch()
        top_menu.addWidget(theme_btn)
        top_menu.addWidget(self.accounts_btn)

        self.main_layout.addLayout(top_menu)

        # Connect theme actions
        dark_action.triggered.connect(lambda: self.set_theme("dark"))
        creeper_action.triggered.connect(lambda: self.set_theme("creeper"))
        light_action.triggered.connect(lambda: self.set_theme("light"))
        oled_action.triggered.connect(lambda: self.set_theme("oled"))

    def setup_main_content(self):
        """Setup the main content area"""
        main_h_layout = QHBoxLayout()
        main_h_layout.setSpacing(10)

        # Setup left panel (instances or log viewer)
        self.setup_left_panel()
        
        # Setup right panel
        self.setup_right_panel()

        # Add panels to main layout based on side preference
        if self.side == 0:
            main_h_layout.addWidget(self.right_widget, 3)
            main_h_layout.addWidget(self.left_scroll_area, 7)
        elif self.side == 1:
            main_h_layout.addWidget(self.left_scroll_area, 7)
            main_h_layout.addWidget(self.right_widget, 3)

        self.main_layout.addLayout(main_h_layout, 1)

    def setup_left_panel(self):
        """Setup the left panel (instances grid or log viewer)"""
        self.left_scroll_area = QScrollArea()
        self.left_scroll_area.setWidgetResizable(True)
        self.left_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.left_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.left_scroll_area.setStyleSheet("border-radius: 6px")
        
        self.left_content_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_content_widget)
        self.left_layout.setAlignment(Qt.AlignTop)
        
        self.left_scroll_area.setWidget(self.left_content_widget)

    def setup_right_panel(self):
        """Setup the right panel (instance details and actions)"""
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)
        self.right_layout.setAlignment(Qt.AlignTop | Qt.AlignRight)

        # Instance icon and name
        self.instance_icon = QLabel()
        self.instance_icon.setFixedSize(100, 100)
        self.instance_icon.setStyleSheet("border-radius: 12px")

        self.instance_name = QLabel("Select an instance")
        self.instance_name.setFixedHeight(30)
        self.instance_name.setAlignment(Qt.AlignCenter)
        self.instance_name.setStyleSheet("border-radius: 8px")

        self.right_layout.addWidget(self.instance_icon, alignment=Qt.AlignCenter)
        self.right_layout.addWidget(self.instance_name)
        self.instance_name.setWordWrap(True)

        # Action buttons
        self.setup_action_buttons()
        
        # Add stretch to push buttons to the top
        self.right_layout.addStretch(1)

    def setup_action_buttons(self):
        """Setup the action buttons in the right panel"""
        buttons_data = [
            ("Launch", self.launch_instance, ".icons/launch.svg"),
            ("Kill", self.kill_instance, ".icons/status-bad.svg"),
            ("Show/Hide Logs", self.toggle_log_viewer, ".icons/log.svg"),
            ("Manage Mods", self.install_mods, ".icons/loadermods.svg"),
            ("Edit", self.edit_instance, ".icons/instance-settings.svg"),
            ("Folder", self.open_instance_folder, ".icons/folder.svg"),
            ("Export", self.export_instance, ".icons/export.svg"),
            ("Copy", self.copy_instance, ".icons/copy.svg"),
            ("Delete", self.delete_instance, ".icons/delete.svg")
        ]

        button_style_with_spacing = """
        QPushButton {
            text-align: left;
            padding-left: 8px;
            icon-size: 16px 16px;
        }
        QPushButton::icon {
            padding-right: 24px;
        }
        """

        for text, callback, icon in buttons_data:
            btn = QPushButton(text)
            if icon != '':
                icon = self.load_colored_svg_icon(icon) 
                btn.setIcon(icon)
            btn.setObjectName("action_button")  # Tag for easy removal
            btn.clicked.connect(callback)
            btn.setFixedWidth(200)
            btn.setStyleSheet(button_style_with_spacing)
            self.right_layout.addWidget(btn)

    def refresh_action_buttons(self):
        """Updates the icons (and optionally text) of existing action buttons"""
        updated_buttons = {
            "Launch": ".icons/launch.svg",
            "Kill": ".icons/status-bad.svg",
            "Show/Hide Logs": ".icons/log.svg",
            "Manage Mods": ".icons/loadermods.svg",
            "Edit": ".icons/instance-settings.svg",
            "Folder": ".icons/folder.svg",
            "Export": ".icons/export.svg",
            "Copy": ".icons/copy.svg",
            "Delete": ".icons/delete.svg"
        }

        for i in range(self.right_layout.count()):
            item = self.right_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QPushButton) and widget.objectName() == "action_button":
                label = widget.text()
                if label in updated_buttons:
                    icon_path = updated_buttons[label]
                    icon = self.load_colored_svg_icon(icon_path)
                    widget.setIcon(icon)
        

    def refresh_ui(self):
        """Refresh the entire UI - use when major changes occur"""
        self.apply_theme(self.current_theme)
        print("refreshing ui")
        self.refresh_top_menu()
        self.refresh_instances()
        self.refresh_action_buttons()
        self.refresh_right_panel()

    def refresh_instances(self):
        """Refresh only the instances display"""
        # Clear existing instances from layout
        self.clear_instances_display()
        
        if self.show_log:
            self.setup_log_viewer()
        else:
            self.setup_instances_display()
            if self.selected_instance_name:
                self.update_selected_instance(self.selected_instance_name)

    def clear_instances_display(self):
        """Clear the current instances display"""
        # Clear the left layout
        while self.left_layout.count():
            child = self.left_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def ansi_to_html(self, text):
        """Clean ANSI to HTML converter that handles your script's format"""
        # Escape HTML characters first
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Your script's specific color mappings
        color_map = {
            '0;31': '#f38ba8',  # RED for [ERROR]
            '0;32': '#a6e3a1',  # GREEN for [INFO] 
            '1;33': '#f9e2af',  # YELLOW for [WARN]
            '0;34': '#89b4fa',  # BLUE for [DEBUG]
        }
        
        # Simple but effective pattern matching
        def replace_ansi(match):
            full_code = match.group(1)
            if full_code in color_map:
                return f'<span style="color: {color_map[full_code]}; font-weight: bold;">'
            elif full_code == '0':  # Reset code
                return '</span>'
            return ''  # Ignore unknown codes
        
        # Replace ANSI codes with HTML
        html_text = re.sub(r'\x1b\[([0-9;]*)m', replace_ansi, text)
        
        return html_text
    
    def setup_log_viewer(self):
        """Setup log viewer that can handle HTML formatting"""
        if self.log_viewer is None:
            # Use QTextEdit instead of QPlainTextEdit for HTML support
            self.log_viewer = QTextEdit()
            self.log_viewer.setReadOnly(True)
            self.log_viewer.setPlaceholderText("Launch an instance to see logs here...")
            
            style = f"""
                QTextEdit {{
                    background: {self.themes[self.current_theme]['frame_bg']};
                    color: {self.themes[self.current_theme]['text']};
                    border: none;
                    margin-right: 10px;
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                }}
                QScrollBar:vertical {{
                    background: #e0e0e0;
                    width: 12px;
                    margin: 0px 0px 0px 0px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #a0a0a0;
                    min-height: 20px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                    background: none;
                }}
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """
            self.log_viewer.setStyleSheet(style)
            self.log_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        if self.show_log:
            self.left_layout.addWidget(self.log_viewer, stretch=1)

    def setup_instances_display(self):
        """Setup the instances display"""
        if self.instances_data:
            self.create_instance_section("", self.instances_data, self.left_layout)
        self.left_layout.addStretch(1)

    def refresh_right_panel(self):
        """Refresh the right panel with current instance info"""
        self.update_instance_icon()
        self.update_accounts_button()

    def update_instance_icon(self):
        """Update the instance icon in the right panel"""
        if not self.selected_instance_name:
            self.instance_icon.setStyleSheet(
                f"border-radius: 8px; background-color: {self.themes[self.current_theme]['icon_bg']}; border-color: {self.themes[self.current_theme]['instance_border']}"
            )
            return

        # Get image path for selected instance
        image = self.instances_data.get(self.selected_instance_name, {}).get('image', 'default')
        
        if isinstance(image, dict):
            image_name = image.get('saved_path', '.icons/default.png')
        elif isinstance(image, str):
            image_name = image if image else '.icons/default.png'
        else:
            image_name = '.icons/default.png'

        if os.path.exists(image_name):
            pixmap = QPixmap(image_name)
            rounded = self.rounded_pixmap(pixmap, radius=16)
            self.instance_icon.setPixmap(rounded)
            self.instance_icon.setFixedSize(100, 100)
            self.instance_icon.setScaledContents(True)
            
        else:
            self.instance_icon.clear()
            self.instance_icon.setStyleSheet(f"border-radius: 4px; background-color: {self.themes[self.current_theme]['icon_bg']};")

    def update_accounts_button(self):
        """Update the accounts button icon"""
        self.accounts_btn.setIcon(QIcon(f".icons/{self.username}.png"))

    def refresh_theme(self):
        """Refresh only the theme/styling"""
        self.apply_theme(self.current_theme)

    def toggle_log_viewer(self):
        """Toggle between log viewer and instances display"""
        self.show_log = not self.show_log
        if self.log_viewer is not None:
            self.log_viewer.setParent(None)
        self.refresh_instances()

    def force_instance_view(self):
        if self.show_log:
            self.show_log = False  # Make sure state reflects the switch
            if self.log_viewer is not None:
                self.log_viewer.setParent(None)
            self.refresh_instances()

    def show_log_viewer(self):
        """Show the log viewer"""
        if not self.show_log:
            self.show_log = True
            self.refresh_instances()

    def hide_log_viewer(self):
        """Hide the log viewer and return to normal view"""
        if self.show_log:
            self.show_log = False
            self.refresh_instances()

    def rounded_pixmap(self, pixmap, radius):
        size = pixmap.size()
        rounded = QPixmap(size)
        rounded.fill(Qt.transparent)  # start with transparent pixmap

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size.width(), size.height()), radius, radius)
        painter.setClipPath(path)

        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return rounded

    # Top menu button actions
    def add_instance(self):
        # Only allow one instance of the window at a time
        if self.instance_window is None or not self.instance_window.isVisible():
            self.instance_window = add_instance_window(theme_colors=self.current_theme)
            
            # Connect the signal to a handler function that receives the data
            self.instance_window.instanceCreated.connect(self.handle_new_instance)
            
            self.instance_window.show()
        else:
            self.instance_window.raise_()
            self.instance_window.activateWindow()

    def handle_new_instance(self, instance_data):
        print("Got instance data from add_instance_window:", instance_data)
        self.force_instance_view()
        base_name = instance_data['name']
        name = base_name
        counter = 1
        while name in self.instances:
            name = f"{base_name} ({counter})"
            counter += 1

        # Update name in the data
        instance_data['name'] = name

        # --- Start Installation Process ---
        self.start_installation(instance_data)
        
    def start_installation(self, instance_data, is_update=False):
        """Starts the installation in a worker thread and shows a progress dialog."""
        
        # First, save the configuration
        if not is_update:
            name = instance_data['name']
            if instance_data['type'] == "Modrinth":
                clean_data = {
                    'name': instance_data.get('name', ''),
                    'modloader': instance_data.get('section', ''),
                    'version': instance_data.get('selected_version', ''),
                    'fabric_version': instance_data.get('selected_fabric_version', ''),
                    'image': instance_data.get('image', ''),
                    'mod_data': instance_data.get('mod_data', ''),
                    'version_number': instance_data.get('version_number', ''),
                    'files': instance_data.get('filenames', '')
                }
            else:
                clean_data = {
                    'name': instance_data.get('name', ''),
                    'modloader': instance_data.get('section', ''),
                    'version': instance_data.get('selected_version', ''),
                    'fabric_version': instance_data.get('selected_fabric_version', ''),
                    'image': instance_data.get('image', ''),
                    'modpack_data': instance_data.get('mod_data', ''),
                    'version_number': instance_data.get('version_number', '')
                }
            self.instances_data[name] = clean_data
        
        self.save_config()
        self.load_config()
        self.refresh_instances()

        # Now, show progress dialog and start worker
        progress_title = "Updating Instance" if is_update else "Creating New Instance"
        self.progress_dialog = ProgressDialog(self, title=progress_title, theme_colors=self.current_theme)
        
        self._install_thread = QThread()
        self._install_worker = InstallationWorker(instance_data, self.java_path)
        self._install_worker.moveToThread(self._install_thread)

        # Connect signals
        self._install_thread.started.connect(self._install_worker.run)
        self._install_worker.progress.connect(self.progress_dialog.append_log)
        self._install_worker.finished.connect(self.on_installation_finished)
        self.progress_dialog.cancelled.connect(self._install_worker.stop)
        
        self._install_thread.finished.connect(self._install_thread.deleteLater)

        self.progress_dialog.show()
        self._install_thread.start()

    def on_installation_finished(self, success, message):
        """Handles the finished signal from the installation worker."""
        self.progress_dialog.append_log(message)
        self.progress_dialog.close_dialog(success)
        self.refresh_instances()
        self._install_thread.quit()
        self._install_worker.deleteLater()
        
    def edit_instance(self):
        instance_name = self.selected_instance_name

        if instance_name == None:
            return

        if self.instance_window is None or not self.instance_window.isVisible():
            self.force_instance_view()
            instance_data = self.instances_data.get(instance_name, {})
            print("here")
            print(instance_data)
            print(self.current_theme)
            self.instance_window = EditInstanceWindow(theme_colors=self.current_theme, instance_data=instance_data)
            
            # Connect signal for updating
            self.instance_window.instanceUpdated.connect(self.handle_updated_instance)

            self.instance_window.show()
        else:
            self.instance_window.raise_()
            self.instance_window.activateWindow()

    def handle_updated_instance(self, updated_data):
        original_name = updated_data['original']
        
        print("Got updated instance data:", updated_data)
        new_name = updated_data['name']
        new_version = updated_data['version']
        new_modloader = updated_data['modloader']

        old_dir = os.path.join(GAME_DIR, "instances", original_name)
        new_dir = os.path.join(GAME_DIR, "instances", new_name)

        # Rename instance folder if name changed
        if original_name != new_name:
            if os.path.exists(old_dir):
                os.rename(old_dir, new_dir)
            # Rename key in instances_data
            self.instances_data[new_name] = self.instances_data.pop(original_name)
        else:
            new_dir = old_dir  # Folder didn't change
            self.instances_data[new_name] = self.instances_data.get(new_name, {})

        # Update instance data
        self.instances_data[new_name].update({
            'name': new_name,
            'modloader': new_modloader,
            'version': new_version,
            'fabric_version': updated_data.get('fabric_version', ''),
            'image': updated_data.get('image', {}).get('saved_path', '')
        })

        # Re-save config and start installation
        self.start_installation(self.instances_data[new_name], is_update=True)

    def open_folders(self):
        print("Opening folders panel...")
        GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
        subprocess.run(["open", GAME_DIR])

    def open_settings(self):
        print("Opening settings panel...")
        if self.settings_window is None or not self.settings_window.isVisible():
            self.settings_window = SetWindow(theme_colors=self.current_theme, java_path=self.java_path)
            
            # Connect the signal to a handler function that receives the data
            self.settings_window.settings_updated.connect(self.on_settings_updated)
            
            self.settings_window.show()
        else:
            self.settings_window.raise_()
            self.settings_window.activateWindow()

    def on_settings_updated(self, settings_data):
        self.java_path = settings_data.get('java_path')
        print("UPDATED JAVA TO ", settings_data.get('java_path'))

    def show_help(self):
        print("Showing help information...")
        url = 'https://github.com/braydenwatt/A-Really-Bad-Minecraft-Launcher'
        webbrowser.open(url)
        
    def manage_accounts(self):
        print("Opening accounts manager...")
        if self.account_window is None or not self.account_window.isVisible():
            self.account_window = AccountWindow(theme_colors=self.current_theme, username=self.username, uuid=self.uuid)
            
            # Connect the signal to a handler function that receives the data
            self.account_window.account_updated.connect(self.on_account_updated)
            
            self.account_window.show()
        else:
            self.account_window.raise_()
            self.account_window.activateWindow()

    def on_account_updated(self, data):
        print("Account updated:", data)
        self.account_data = data
        self.username = data['username']
        self.uuid = data['uuid']
        self.access_token = data['access_token']
        self.save_config()

    def append_log_to_viewer(self, text):
        """Append text with ANSI colors converted to HTML"""
        if self.log_viewer and not sip.isdeleted(self.log_viewer):
            html_text = self.ansi_to_html(text.strip())
            print("HTML: ", html_text)
            # Move cursor to end and insert HTML
            cursor = self.log_viewer.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertHtml(html_text + '<br>')
            
            # Auto-scroll to bottom
            scrollbar = self.log_viewer.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def launch_instance(self):
        """Launch the selected instance and show logs"""
        if not self.selected_instance_name:
            print("No instance selected")
            return
        
        if self.selected_instance_name in self.active_instances:
            print("Not launching again")
            return

        print(f"Launching instance: {self.selected_instance_name}")
        
        instance_data = self.instances_data.get(self.selected_instance_name, {})
        modloader = instance_data.get('modloader', '')
        version = instance_data.get('version', '')

        self.setup_log_viewer()

        if modloader == "Fabric":
            self.launch_fabric_instance(version, instance_data)
            self.active_instances[self.selected_instance_name] = self.selected_instance_name
        else:
            self.launch_vanilla_instance(version)
            self.active_instances[self.selected_instance_name] = self.selected_instance_name

    def launch_fabric_instance(self, version, instance_data):
        """Launch a Fabric instance with process monitoring"""
        fabric_version = instance_data.get('fabric_version', '').replace("Fabric", "").strip()
        print(instance_data)
        launch_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "fabric.command")
        args = [launch_script, self.username, self.uuid, version, fabric_version, 
                self.access_token, self.selected_instance_name, self.java_path]

        def run_subprocess():
            try:
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # Line buffered
                    universal_newlines=True
                )
                
                # Store the process object instead of just the name
                self.active_instances[self.selected_instance_name] = process
                
                for line in process.stdout:
                    # Emit signal for thread-safe GUI update
                    self.log_emitter.log_signal.emit(line.strip())
                    print(line, end='')  # Still print to console
                    
                process.wait()
                self.log_emitter.log_signal.emit(f"\nProcess finished with exit code: {process.returncode}")
                
                # Remove from active instances when process completes
                self.active_instances.pop(self.selected_instance_name, None)
                
            except Exception as e:
                self.log_emitter.log_signal.emit(f"Error launching instance: {str(e)}")
                # Remove from active instances on error
                self.active_instances.pop(self.selected_instance_name, None)

        # Start subprocess in separate thread
        threading.Thread(target=run_subprocess, daemon=True).start()

    def launch_vanilla_instance(self, version):
        """Launch a Vanilla instance with process monitoring"""
        launch_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts","launch_vanilla.command")
        args = [launch_script, self.username, self.uuid, version, self.access_token, self.selected_instance_name, self.java_path]

        def run_subprocess():
            try:
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Store the process object instead of just the name
                self.active_instances[self.selected_instance_name] = process
                
                for line in process.stdout:
                    self.log_emitter.log_signal.emit(line.strip())
                    print(line, end='')
                    
                process.wait()
                self.log_emitter.log_signal.emit(f"\nProcess finished with exit code: {process.returncode}")
                
                # Remove from active instances when process completes  
                self.active_instances.pop(self.selected_instance_name, None)
                
            except Exception as e:
                self.log_emitter.log_signal.emit(f"Error launching instance: {str(e)}")
                # Remove from active instances on error
                self.active_instances.pop(self.selected_instance_name, None)

        threading.Thread(target=run_subprocess, daemon=True).start()

    # Add a method to hide the log viewer
    def hide_log_viewer(self):
        """Hide the log viewer and return to normal view"""
        if self.show_log:
            self.show_log = False
            self.refresh_ui
            
    def kill_instance(self):
        if self.selected_instance_name:
            print(f"Killing instance: {self.selected_instance_name}")
            kill_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "kill.command")
            args = [kill_script, self.selected_instance_name]
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            for line in process.stdout:
                print(line, end='')

            self.active_instances.pop(self.selected_instance_name, None)
        else:
            print("No instance selected")
            
    def open_instance_folder(self):
        if self.selected_instance_name:
            print(f"Opening folder for instance: {self.selected_instance_name}")
            INSTANCE_DIR = f"{GAME_DIR}/instances/{self.selected_instance_name}"
            subprocess.run(["open", INSTANCE_DIR])
        else:
            print("No instance selected")
            
    def export_instance(self):
        if self.selected_instance_name:
            INSTANCE_DIR = f"{GAME_DIR}/instances/{self.selected_instance_name}"
            export_path, _ = QFileDialog.getSaveFileName(None, "Export Instance As", f"{self.selected_instance_name}.zip")
            if export_path:
                self.zip_instance(INSTANCE_DIR, export_path)
        else:
            print("No instance selected")
            
    def zip_instance(self, instance_path, export_path):
        # Collect all files first so we know the total count
        files_to_zip = []
        for root, dirs, files in os.walk(instance_path):
            for file in files:
                files_to_zip.append(os.path.join(root, file))

        total_files = len(files_to_zip)
        if total_files == 0:
            print("No files to zip")
            return

        progress = QProgressDialog("Exporting instance...", "Cancel", 0, total_files)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, full_path in enumerate(files_to_zip):
                arcname = os.path.relpath(full_path, start=instance_path)
                zipf.write(full_path, arcname)

                # Update progress bar
                progress.setValue(i + 1)

                # Check if user clicked cancel
                if progress.wasCanceled():
                    print("Export canceled by user")
                    break

        progress.close()
                    
    def install_mods(self):
        
        self.load_config()

        if self.selected_instance_name is None:
            return

        if self.instances_data[self.selected_instance_name].get('modloader') != "Fabric":
            return

        if self.mod_window is not None and self.mod_window.isVisible():
            self.mod_window.raise_()
            self.mod_window.activateWindow()
            return

        try:
            mod_data = self.instances_data[self.selected_instance_name].get('mod_data', [])
        except Exception as e:
            print(f"Error accessing mod_data: {e}")
            mod_data = []

        INSTANCE_DIR = os.path.join(GAME_DIR, "instances", self.selected_instance_name)
        MOD_DIR = os.path.join(INSTANCE_DIR, "mods")

        try:
            file_names = set(f for f in os.listdir(MOD_DIR) if os.path.isfile(os.path.join(MOD_DIR, f)))
        except FileNotFoundError:
            print(f"Mods folder not found at {MOD_DIR}")
            file_names = set()

        # Filter out mods whose first filename is missing
        valid_mod_data = []
        for mod in mod_data:
            filenames = mod.get('filenames', [])
            if filenames and filenames[0] in file_names:
                valid_mod_data.append(mod)
            else:
                print(f"Removing missing mod: {mod.get('title', 'Unknown')} (missing {filenames[0] if filenames else 'no filename'})")

        # Track already-known filenames (just filename[0] per mod)
        tracked_filenames = {mod['filenames'][0] for mod in valid_mod_data if mod.get('filenames')}
        unexpected_files = []

        for f in file_names:
            print(f"[DEBUG] Checking file: {f}")
            
            if f.endswith('.jar') or f.endswith('.jar.disabled'):
                if f not in tracked_filenames:
                    print(f"        => Unexpected (not tracked)")
                    unexpected_files.append(f)
                else:
                    print(f"        => Already tracked")
            else:
                print(f"        => Skipped (not a .jar or .jar.disabled file)")


        for filename in unexpected_files:
            print(filename)
            
            valid_mod_data.append({
                'id': 'Unknown',
                'project_id': 'Unknown',
                'title': filename,
                'description': 'This mod was manually installed',
                'author': 'Unknown',
                'downloads': 'Unknown',
                'version': 'Unknown',
                'enabled': filename.endswith('.jar'),
                'icon_url': 'Default',
                'filenames': [filename],
            })

        print("DEBUG: Original mod_data length:", len(mod_data))
        print("DEBUG: Valid mod_data length:", len(valid_mod_data))
        print("DEBUG: Tracked filenames:", tracked_filenames)
        print("DEBUG: Unexpected files found:", unexpected_files)
        
        if valid_mod_data:
            print("DEBUG: First valid mod entry:", valid_mod_data[0])
        else:
            print("DEBUG: No valid mod data found!")

        self.instances_data[self.selected_instance_name]['mod_data'] = valid_mod_data

        print(f"DEBUG: Creating manage_modsWindow with {len(valid_mod_data)} mods")
        self.mod_window = manage_modsWindow(
            mod_data=valid_mod_data,
            theme_colors=self.current_theme,
            selected_name=self.selected_instance_name,
            version=self.instances_data[self.selected_instance_name]['version'],
            loader=self.instances_data[self.selected_instance_name]['modloader'],
        )
        self.mod_window.modsUpdated.connect(self.handle_mod_data_update)
        self.mod_window.nameUpdated.connect(self.handle_mod_name_change)
        self.mod_window.modsInstalled.connect(self.reopen)
        self.mod_window.show()

    def reopen(self):
        print("accept")
        self.mod_window.accept()
        self.install_mods()

    def handle_mod_data_update(self, instance_name, new_mod_data):
        if instance_name in self.instances_data:
            self.instances_data[instance_name]['mod_data'] = new_mod_data
            self.save_config()

    def handle_mod_name_change(self, instance_name: str, new_mod_data: dict):
        mod_id = new_mod_data.get('id')
        if not mod_id:
            print("Error: new_mod_data missing 'id'")
            return

        if instance_name in self.instances_data:
            mod_data_list = self.instances_data[instance_name].setdefault('mod_data', [])
            
            # Convert list to dict by id for easy update
            mod_data_dict = {mod['id']: mod for mod in mod_data_list}

            mod_data_dict[mod_id] = new_mod_data  # update or add

            # Convert back to list
            self.instances_data[instance_name]['mod_data'] = list(mod_data_dict.values())
            self.save_config()
        else:
            print(f"Instance {instance_name} not found.")


    def copy_instance(self):
        
        original_name = self.selected_instance_name

        if original_name not in self.instances:
            print(f"Instance '{original_name}' does not exist.")
            return

        self.force_instance_view()

        # Extract base name by removing any " copy" or " copy N"
        base_name = re.sub(r'( copy( \d+)?)$', '', original_name)
        new_name = f"{base_name} copy"

        counter = 1
        while new_name in self.instances:
            new_name = f"{base_name} copy {counter}"
            counter += 1

        # Paths for old and new instances
        original_dir = os.path.join(GAME_DIR, "instances", original_name)
        new_dir = os.path.join(GAME_DIR, "instances", new_name)

        try:
            # Copy entire folder recursively
            shutil.copytree(original_dir, new_dir)
        except Exception as e:
            print(f"Error copying instance folder: {e}")
            return

        # Copy the metadata from instances_data and update the name
        original_data = self.instances_data.get(original_name, {}).copy()
        original_data['name'] = new_name
        self.instances_data[new_name] = original_data

        # Update instances dictionary if you keep instance widgets or labels here
        # You may need to create new UI widgets for the copied instance
        # For example:
        # self.instances[new_name] = create_widgets_for_instance(new_name, new_dir)

        # Save and reload configs and update UI
        self.save_config()
        self.load_config()
        self.refresh_instances()
        print(f"Copied instance '{original_name}' to '{new_name}'")

            
    def delete_instance(self):
        name = self.selected_instance_name

        if name not in self.instances_data:
            print(f"Instance '{name}' not found.")
            return

        # Create a customizable message box
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Delete Instance")
        msg_box.setText(f"Are you sure you want to delete the instance '{name}'?")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        msg_box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {self.themes[self.current_theme]['background']};
                border-radius: 12px;
                color: {self.themes[self.current_theme]['text']}
            }}
            QLabel {{
                background-color: {self.themes[self.current_theme]['background']};
                color: {self.themes[self.current_theme]['text']};
                font-size: 14px;
            }}
        """)


        reply = msg_box.exec_()
        if reply != QMessageBox.Yes:
            return  # Cancelled

        # Delete instance folder
        instance_path = os.path.join(GAME_DIR, "instances", name)
        try:
            if os.path.exists(instance_path):
                shutil.rmtree(instance_path)
                print(f"Deleted instance folder: {instance_path}")
        except Exception as e:
            print(f"Failed to delete instance folder: {e}")
            return

        # Clean up data
        del self.instances_data[name]

        if self.selected_instance_name == name:
            self.selected_instance_name = None
            self.selected_instance_label = None
            self.selected_instance_widget = None
            self.instance_name.setText("")
            self.instance_icon.clear()

        self.save_config()
        self.load_config()
        self.refresh_instances()

        print(f"Instance '{name}' deleted.")

    def set_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.apply_theme(theme_name)
            self.save_config()
            self.load_config()
            self.refresh_ui()
           

    def apply_theme(self, theme_name):
        if theme_name in self.themes:
            stylesheet = self.build_stylesheet(self.themes[theme_name])
            self.setStyleSheet(stylesheet)
            style = f"""
                QPlainTextEdit {{
                    background: {self.themes[self.current_theme]['frame_bg']};
                    color: {self.themes[self.current_theme]['text']};
                    border: none;
                    margin-right: 10px;
                }}
                QScrollBar:vertical {{
                    background: #e0e0e0;
                    width: 12px;
                    margin: 0px 0px 0px 0px;
                    border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background: #a0a0a0;
                    min-height: 20px;
                    border-radius: 5px;
                }}
                QScrollBar::add-line:vertical,
                QScrollBar::sub-line:vertical {{
                    height: 0px;
                    background: none;
                }}
                QScrollBar::add-page:vertical,
                QScrollBar::sub-page:vertical {{
                    background: none;
                }}
            """
            if self.log_viewer is not None:
                self.log_viewer.setStyleSheet(style)
    
    def create_instance_section(self, section_name, instance_names, parent_layout):
        """Create a section of instances with a header"""
        # Skip if there are no instance names
        if not instance_names:
            return

        section_frame = QFrame()
        section_frame.setFrameShape(QFrame.StyledPanel)
        section_layout = QVBoxLayout(section_frame)
        
        # Create a widget to contain our flow layout
        flow_container = QWidget()
        # Use the FlowLayout class with custom spacing
        # Adjust these values to control spacing between instances
        horizontal_spacing = -40  # Spacing between instances horizontally
        vertical_spacing = 0    # Spacing between rows
        
        self.flow_layout = FlowLayout(flow_container, margin=10, spacing=horizontal_spacing)
        self.flow_layout.setVerticalSpacing(vertical_spacing)
        
        for name in instance_names:
            instance = self.create_instance_widget(name)
            if instance:
                self.flow_layout.addWidget(instance)
        
        section_layout.addWidget(flow_container)
        
        # Make the section frame expand to fill available space
        parent_layout.addWidget(section_frame) 

    def create_instance_widget(self, name):
        if not name:
            return None

        print(name)

        self.load_config()

        # Get modloader from instance data, fallback to 'default' if missing
        image = self.instances_data.get(name, {}).get('image', 'default')
        print(image)

        print(self.instances_data)

        instance_widget = QWidget()
        instance_layout = QVBoxLayout(instance_widget)
        instance_layout.setAlignment(Qt.AlignCenter)

        icon = QLabel()
        icon.setFixedSize(64, 64)
        print("instance data")
        print(self.instances_data)

        # Get modloader info for icon
        image = self.instances_data.get(name, {}).get('image', 'default')

        if isinstance(image, dict):
            image_name = image.get('saved_path', '.icons/default.png')
        elif isinstance(image, str):
            image_name = image if image else '.icons/default.png'
        else:
            image_name = '.icons/default.png'

        if os.path.exists(image_name) and image_name != ".icons/default.png":
            pixmap = QPixmap(image_name)  # Load original image (not scaled)
            rounded = self.rounded_pixmap(pixmap, radius=16)

            icon.setPixmap(rounded)
            icon.setFixedSize(64, 64)
            icon.setScaledContents(True)
        else:
            pixmap = QPixmap(image_name)  # Load original image (not scaled)
            rounded = self.rounded_pixmap(pixmap, radius=16)
            icon.setPixmap(rounded)
            icon.setFixedSize(64, 64)
            icon.setScaledContents(True)
            icon.setStyleSheet(f"border-radius: 4px; background-color: {self.themes[self.current_theme]['icon_bg']};")

        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setProperty("class", "instance-name")
        name_label.setProperty("selected", False)
        name_label.style().unpolish(name_label)
        name_label.style().polish(name_label)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(400)

        instance_layout.addWidget(icon, alignment=Qt.AlignCenter)
        instance_layout.addSpacing(10)
        instance_layout.addWidget(name_label, alignment=Qt.AlignCenter)

        instance_widget.setFixedWidth(150)

        self.instances[name] = {'widget': instance_widget, 'label': name_label}
        instance_widget.mousePressEvent = lambda event: self.update_selected_instance(name)

        return instance_widget

    def update_selected_instance(self, name):
        if name is None:
            return
        self.selected_instance_name = name
        self.instance_name.setText(name)

        # Reset previous selection if it exists
        if self.selected_instance_label is not None and not sip.isdeleted(self.selected_instance_label):
            self.selected_instance_label.setProperty("selected", False)
            self.selected_instance_label.style().unpolish(self.selected_instance_label)
            self.selected_instance_label.style().polish(self.selected_instance_label)

         # Now update new selection label safely
        selected_label = self.instances.get(name, {}).get('label', None)

        if selected_label is not None and not sip.isdeleted(selected_label):
            selected_label.setProperty("selected", True)
            selected_label.style().unpolish(selected_label)
            selected_label.style().polish(selected_label)
            self.selected_instance_label = selected_label
        else:
            # Label missing or deleted - maybe log or handle gracefully
            print(f"Label for instance '{name}' is missing or deleted.")
            self.selected_instance_label = None

        # Get modloader info for icon
        # Get modloader info for icon
        image = self.instances_data.get(name, {}).get('image', 'default')

        if isinstance(image, dict):
            image_name = image.get('saved_path', '.icons/default.png')
        elif isinstance(image, str):
            image_name = image if image else '.icons/default.png'
        else:
            image_name = '.icons/default.png'

        image_path = image_name

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            rounded = self.rounded_pixmap(pixmap, radius=16)
            self.instance_icon.setPixmap(rounded)
            self.instance_icon.setFixedSize(100, 100)
            self.instance_icon.setScaledContents(True)
        else:
            self.instance_icon.clear()
            self.instance_icon.setStyleSheet(f"border-radius: 4px; background-color: {self.themes[self.current_theme]['icon_bg']};")

        self.selected_instance_label = selected_label
        self.selected_instance_widget = self.instances[name]['widget']


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MinecraftLauncherUI()
    window.show()
    sys.exit(app.exec_())

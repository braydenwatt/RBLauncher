import sys
import os
import shutil
import threading
import requests
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                           QPushButton, QListWidget, QListWidgetItem, QFrame, 
                           QScrollArea, QWidget, QSizePolicy, QComboBox, 
                           QGridLayout, QCheckBox, QSpacerItem, QFileDialog,
                           QTextEdit, QSplitter, QApplication)
from PyQt5.QtGui import QIcon, QPixmap, QColor, QImage, QPainter
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer, QUrl
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
import json
from PyQt5.QtWidgets import QSplitter, QSplitterHandle
from progress_dialog import ProgressDialog

class NoResizeSplitterHandle(QSplitterHandle):
    def mousePressEvent(self, event): pass
    def mouseMoveEvent(self, event): pass
    def mouseReleaseEvent(self, event): pass

class NoResizeSplitter(QSplitter):
    def createHandle(self):
        return NoResizeSplitterHandle(self.orientation(), self)

class ModFetchWorker(QThread):
    """Worker thread for fetching mod information from Modrinth API with progress updates."""
    progress_updated = pyqtSignal(int, int, str)  # current, total, mod_name
    log_updated = pyqtSignal(str)
    finished_with_data = pyqtSignal(list)  # mods_info list
    error_occurred = pyqtSignal(str)
    
    def __init__(self, mod_list):
        super().__init__()
        self.mod_list = mod_list
        self.should_stop = False
    
    def stop(self):
        self.should_stop = True
    
    def run(self):
        """Fetch mod information with progress updates."""
        mods_info = []
        session = requests.Session()
        project_cache = {}
        total_mods = len(self.mod_list)
        
        self.log_updated.emit(f"Starting to fetch information for {total_mods} mods...")
        
        for i, mod in enumerate(self.mod_list):
            if self.should_stop:
                self.log_updated.emit("Operation cancelled by user.")
                return
            
            version_id = mod.get('version_id')
            if not version_id:
                self.log_updated.emit(f"Skipping mod {i+1}/{total_mods} - no version ID")
                continue
            
            try:
                self.log_updated.emit(f"Fetching mod {i+1}/{total_mods} (version: {version_id})...")
                
                # Get version information
                version_info = session.get(f"https://api.modrinth.com/v2/version/{version_id}").json()
                project_id = version_info['project_id']
                
                # Use cached project info if possible
                if project_id in project_cache:
                    project_info = project_cache[project_id]
                    self.log_updated.emit(f"Using cached project info for {project_info.get('title', 'Unknown')}")
                else:
                    project_info = session.get(f"https://api.modrinth.com/v2/project/{project_id}").json()
                    project_cache[project_id] = project_info
                    self.log_updated.emit(f"Fetched project info for {project_info.get('title', 'Unknown')}")
                
                mod_info = {
                    'id': version_info['id'],
                    'project_id': project_id,
                    'title': project_info['title'],
                    'description': project_info['description'],
                    'author': version_info.get('author', "Unknown"),
                    'downloads': project_info['downloads'],
                    'version': version_info['version_number'],
                    'enabled': True,
                    'icon_url': project_info['icon_url'],
                    'filenames': [f['filename'] for f in version_info.get('files', [])]
                }
                
                mods_info.append(mod_info)
                self.progress_updated.emit(i + 1, total_mods, project_info.get('title', 'Unknown'))
                
            except Exception as e:
                error_msg = f"Error with version {version_id}: {str(e)}"
                self.log_updated.emit(error_msg)
                print(error_msg)  # Keep console output for debugging
                continue
        
        self.log_updated.emit(f"Successfully fetched information for {len(mods_info)} out of {total_mods} mods.")
        self.finished_with_data.emit(mods_info)
    
class ModrinthPackWidget(QWidget):
    """Custom widget for displaying a Modrinth modpack in the list"""
    
    def __init__(self, pack_data, theme_colors):
        super().__init__()
        self.pack_data = pack_data
        self.theme_colors = theme_colors
        self.selected = False
        self.init_ui()
        
    def init_ui(self):
        # Set fixed height to prevent stretching
        self.setMinimumHeight(72)  # Adjust this value as needed
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setScaledContents(True)
        self.icon_label.setStyleSheet(f"background-color: {self.theme_colors['icon_bg']}; border-radius: 4px;")
        self.icon_label.setAlignment(Qt.AlignCenter)  # Ensure icon is centered
        
        # Load icon if available
        if self.pack_data.get('icon_url'):
            self.load_icon()
        else:
            # Default icon
            pixmap = QPixmap(48, 48)
            pixmap.fill(QColor(self.theme_colors['icon_bg']))
            self.icon_label.setPixmap(pixmap)
        
        layout.addWidget(self.icon_label, 0, Qt.AlignTop)  # Align to top instead of stretch
        
        # Content (title and description)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.title_label = QLabel(self.pack_data.get('title', 'Unknown Pack'))
        self.title_label.setStyleSheet(f"color: {self.theme_colors['text']}; font-weight: bold; font-size: 14px;")
        self.title_label.setWordWrap(True)
        
        # Description
        description = self.pack_data.get('description', '')
        if len(description) > 100:
            description = description[:100] + "..."
        self.desc_label = QLabel(description)
        self.desc_label.setStyleSheet(f"color: {self.theme_colors['text']}; opacity: 0.8;")
        self.desc_label.setWordWrap(True)
        
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.desc_label)
        content_layout.addStretch()
        
        layout.addLayout(content_layout, 1)
        
        self.update_selection_style()
        
    def load_icon(self):
        """Load icon from URL"""
        def fetch_icon():
            try:
                response = requests.get(self.pack_data['icon_url'], timeout=10)
                response.raise_for_status()
                
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                # Scale to fit
                
                
                # Use QTimer to update UI from main thread
                self.icon_label.setPixmap(pixmap)
                self.icon_label.setFixedSize(48, 48)
                self.icon_label.setScaledContents(True)
            except Exception as e:
                print(f"Failed to load icon: {e}")
                
        threading.Thread(target=fetch_icon, daemon=True).start()
    
    def set_selected(self, selected):
        self.selected = selected
        self.update_selection_style()
        
    def update_selection_style(self):
        if self.selected:
            self.setStyleSheet(f"""
                ModrinthPackWidget {{
                    background-color: {self.theme_colors['selected_bg']};
                    border: 1px solid {self.theme_colors['selected_border']};
                    border-radius: 4px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ModrinthPackWidget {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                }}
                ModrinthPackWidget:hover {{
                    background-color: {self.theme_colors['button_hover']};
                    border: 1px solid {self.theme_colors['instance_border']};
                }}
            """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Find the parent add_instance_window
            parent = self.parent()
            while parent and not isinstance(parent, add_instance_window):
                parent = parent.parent()
            if parent:
                parent.select_modpack(self)
        super().mousePressEvent(event)

class add_instance_window(QDialog):
    """Dialog window for adding a new Minecraft instance"""
    instanceCreated = pyqtSignal(object)
    
    def __init__(self, parent=None, theme_colors=None):
        super().__init__(parent)
        self.setWindowTitle("New Instance")
        self.setMinimumSize(900, 650)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint)
        
        # Store the selected image path and modpack data
        self.selected_image_path = None
        self.selected_modpack = None
        self.modpack_widgets = []
        self.modpack_data = []
        self.current_section = None
        
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
        }
        
        # Set default theme if none provided
        self.current_theme = theme_colors if theme_colors in self.themes else "dark"
        self.init_ui()
        self.apply_theme(self.current_theme)
        
    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Name input area with image upload
        name_layout = QHBoxLayout()
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(10)
        
        # Image upload area
        image_layout = QVBoxLayout()
        image_layout.setAlignment(Qt.AlignCenter)
        image_layout.setSpacing(10)
        self.image_label = QLabel()
        self.image_label.setFixedSize(80, 80)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet(f"background-color: {self.themes[self.current_theme]['instance_bg']}; border: 1px dashed #777777;")
        
        # Set default placeholder image
        placeholder_pixmap = QPixmap(80, 80)
        placeholder_pixmap.fill(Qt.transparent)
        self.image_label.setPixmap(placeholder_pixmap)
        
        self.upload_btn = QPushButton("Upload")
        self.upload_btn.clicked.connect(self.upload_image)
        self.upload_btn.setFixedWidth(80)
        
        image_layout.addWidget(self.image_label, 0, Qt.AlignCenter)
        image_layout.addWidget(self.upload_btn, 0, Qt.AlignCenter)
        self.has_searched = False
        # Name input
        name_input_layout = QHBoxLayout()
        name_label = QLabel("Name:")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Instance name")
        name_label.setStyleSheet(f"background: transparent; color: {self.themes[self.current_theme]['text']}")
        name_input_layout.addWidget(name_label)
        name_input_layout.addWidget(self.name_input, 1)
        
        name_layout.addLayout(image_layout)
        name_layout.addSpacing(10)
        name_layout.addLayout(name_input_layout, 1)
        
        # Combine the top inputs
        top_layout = QVBoxLayout()
        top_layout.setSpacing(5)
        top_layout.addLayout(name_layout)
        
        # Main content area with sidebar and content
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left sidebar
        sidebar_frame = QFrame()
        sidebar_frame.setFrameShape(QFrame.StyledPanel)
        sidebar_frame.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        sidebar_frame.setStyleSheet(f"background: {self.themes[self.current_theme]['frame_bg']}; border: none;")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # Create buttons
        self.vanilla_btn = self.create_sidebar_button("Vanilla", ".icons/vanilla.png")
        self.fabric_btn = self.create_sidebar_button("Fabric", ".icons/fabric.png")
        self.modrinth_btn = self.create_sidebar_button("Modrinth", ".icons/modrinth.png")

        for btn in [self.vanilla_btn, self.fabric_btn, self.modrinth_btn]:
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        sidebar_layout.addWidget(self.vanilla_btn)
        sidebar_layout.addWidget(self.fabric_btn)
        sidebar_layout.addWidget(self.modrinth_btn)
        sidebar_layout.addStretch(1)

        # Right content area - using splitter for Modrinth
        horizontal_content_layout = QHBoxLayout()
        horizontal_content_layout.setContentsMargins(0, 0, 0, 0)
        horizontal_content_layout.setSpacing(0)
        
        # Left side of splitter (modpack list or version lists)
        left_content_frame = QFrame()
        left_content_frame.setFrameShape(QFrame.StyledPanel)
        left_content_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_content_frame.setStyleSheet("background: transparent;")
        
        self.content_layout = QVBoxLayout(left_content_frame)
        self.content_layout.setContentsMargins(5, 0, 0, 0)
        self.content_layout.setSpacing(5)
        self.mod_data_map = {}

        # Search bars
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(15)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search and filter...")
        self.search_button = QPushButton("Search")
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_button)
        self.search_button.clicked.connect(self.filter_versions)
        self.search_input.textChanged.connect(self.filter_versions)

        second_search_layout = QHBoxLayout()
        second_search_layout.setContentsMargins(0, 0, 0, 0)
        second_search_layout.setSpacing(15)
        self.second_search_input = QLineEdit()
        self.second_search_input.setPlaceholderText("Search and filter...")
        self.second_search_button = QPushButton("Search")
        second_search_layout.addWidget(self.second_search_input, 1)
        second_search_layout.addWidget(self.second_search_button)
        self.second_search_button.clicked.connect(self.filter_fabric_versions)
        self.second_search_input.textChanged.connect(self.filter_fabric_versions)
        self.flag = True

        # Version lists
        self.versions_list = QListWidget()
        self.versions_list.setUniformItemSizes(True)
        self.versions_list.setStyleSheet(self.get_list_style())
        
        self.second_versions_list = QListWidget()
        self.second_versions_list.setUniformItemSizes(True)
        self.second_versions_list.setStyleSheet(self.get_list_style())
    
        # Modrinth modpack list (scroll area)
        self.modpack_scroll = QScrollArea()
        self.modpack_scroll.setWidgetResizable(True)
        self.modpack_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {self.themes[self.current_theme]['frame_bg']};
                border: none;
            }}
        """)
        
        self.modpack_container = QWidget()
        self.modpack_layout = QVBoxLayout(self.modpack_container)
        self.modpack_layout.setSpacing(2)
        self.modpack_layout.setContentsMargins(5, 5, 5, 5)
        self.modpack_scroll.setWidget(self.modpack_container)

        self.bottom_spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        
        # Sort dropdown for Modrinth
        self.sort_layout = QHBoxLayout()
        self.sort_layout.setContentsMargins(0, 0, 0, 0)
        self.sort_label = QLabel("Sort by:")
        self.sort_label.setStyleSheet(f"color: {self.themes[self.current_theme]['text']};")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Relevance", "Downloads", "Updated", "Created"])
        self.sort_combo.currentTextChanged.connect(self.sort_modpacks)
        self.sort_combo.setMinimumWidth(107)
        self.sort_layout.addWidget(self.sort_label)
        self.sort_layout.addWidget(self.sort_combo)
        self.sort_layout.addStretch()
        
        # Add components to content layout
        self.content_layout.addLayout(search_layout)
        self.content_layout.addWidget(self.versions_list, 1)
        self.content_layout.addLayout(second_search_layout)
        self.content_layout.addWidget(self.second_versions_list, 1)
        self.content_layout.addLayout(self.sort_layout)
        self.content_layout.addWidget(self.modpack_scroll, 1)
        
        # Right side of splitter (modpack details)
        self.details_frame = QFrame()
        self.details_frame.setFrameShape(QFrame.StyledPanel)
        self.details_frame.setStyleSheet(f"background: {self.themes[self.current_theme]['frame_bg']}; border: none;")
        self.details_frame.setMinimumWidth(300)
        
        details_layout = QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(10, 10, 10, 10)
        
        # Modpack details widgets
        self.details_title = QLabel("Select a modpack")
        self.details_title.setStyleSheet(f"color: {self.themes[self.current_theme]['text']}; font-weight: bold; font-size: 16px;")
        self.details_title.setWordWrap(True)
        
        self.details_author = QLabel("")
        self.details_author.setStyleSheet(f"color: {self.themes[self.current_theme]['text']}; font-size: 12px;")
        
        self.details_description = QTextEdit()
        self.details_description.setReadOnly(True)
        self.details_description.setStyleSheet(f"""
            QTextEdit {{
                background: {self.themes[self.current_theme]['instance_bg']};
                color: {self.themes[self.current_theme]['text']};
                border: 1px solid {self.themes[self.current_theme]['instance_border']};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        
        self.details_info = QLabel("")
        self.details_info.setStyleSheet(f"color: {self.themes[self.current_theme]['text']}; font-size: 11px;")
        self.details_info.setWordWrap(True)
        
        # Version selection for Modrinth
        version_label = QLabel("Version:")
        version_label.setStyleSheet(f"color: {self.themes[self.current_theme]['text']};")
        self.version_combo = QComboBox()
        self.version_combo.currentTextChanged.connect(self.validate_ok_button)
        
        details_layout.addWidget(self.details_title)
        details_layout.addWidget(self.details_author)
        details_layout.addWidget(self.details_description, 1)
        details_layout.addWidget(self.details_info)
        details_layout.addWidget(version_label)
        details_layout.addWidget(self.version_combo)
        details_layout.addStretch()
        
        spacer = QWidget()
        spacer.setFixedWidth(10)

        left_content_frame.setMinimumWidth(400)


        # Add frames to splitter
        horizontal_content_layout.addWidget(left_content_frame, 1)  # main content grows
        horizontal_content_layout.addWidget(spacer)
        horizontal_content_layout.addWidget(self.details_frame, 1)     # details has fixed width

        # Add sidebar and content to main content layout
        content_layout.addWidget(sidebar_frame)
        content_layout.addLayout(horizontal_content_layout, 1)
        
        # Bottom buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)

        self.cancel_btn = QPushButton("Cancel")
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.setEnabled(False)

        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.ok_btn)

        # Add all components to main layout
        main_layout.addLayout(top_layout, 0)
        main_layout.addLayout(content_layout, 1)
        main_layout.addLayout(buttons_layout, 0)
        
        # Connect signals
        self.versions_list.itemSelectionChanged.connect(self.validate_ok_button)
        self.second_versions_list.itemSelectionChanged.connect(self.validate_ok_button)
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.clicked.connect(self.create_instance)
        self.vanilla_btn.clicked.connect(lambda: self.change_section("Vanilla"))
        self.fabric_btn.clicked.connect(lambda: self.change_section("Fabric"))
        self.modrinth_btn.clicked.connect(lambda: self.change_section("Modrinth"))

        # Set vanilla as default selected
        QTimer.singleShot(0, lambda: self.change_section("Vanilla"))

    def get_list_style(self):
        """Get consistent list widget styling"""
        return f"""
            QListWidget {{
                background: {self.themes[self.current_theme]['frame_bg']};
                color: {self.themes[self.current_theme]['text']};
                border: none;
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

    def create_sidebar_button(self, text, icon_path=None):
        """Create a styled button for the sidebar"""
        button = QPushButton(text)
        button.setCheckable(True)
        button.setFlat(True)
        button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px;
                border: none;
            }
        """)
        
        if icon_path and os.path.exists(icon_path):
            try:
                button.setIcon(QIcon(icon_path))
            except:
                pass
                
        return button

    def apply_sidebar_button_style(self):
        theme = self.themes.get(self.current_theme)
        if not theme:
            return
        text_color = theme["text"]
        hover_bg = theme["button_hover"]
        selected_bg = theme["selected_bg"]

        style = f"""
            QPushButton {{
                border: none;
                background: transparent;
                color: {text_color};
                padding: 8px 12px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton:checked {{
                background-color: {selected_bg};
                color: white;
                text-align: left;
            }}
        """
        for btn in [self.vanilla_btn, self.fabric_btn, self.modrinth_btn]:
            btn.setStyleSheet(style)
            btn.setCheckable(True)

    def validate_ok_button(self):
        """Enable/disable OK button based on current selection"""
        if self.current_section == "Modrinth":
            has_modpack = self.selected_modpack is not None
            has_version = self.version_combo.currentText() != ""
            self.ok_btn.setEnabled(has_modpack and has_version)
            return
            
        version_selected = self.versions_list.currentItem() is not None

        if self.current_section == "Fabric":
            fabric_selected = self.second_versions_list.currentItem() is not None
            self.ok_btn.setEnabled(version_selected and fabric_selected)
        else:
            self.ok_btn.setEnabled(version_selected)

    def upload_image(self):
        """Open file dialog to select an image"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, 'Select Instance Image', '', 
            'Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)'
        )
        
        if file_path:
            self.selected_image_path = file_path
            pixmap = QPixmap(file_path)
            scaled_pixmap = pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setStyleSheet("background-color: transparent; border: none;")
            self.upload_btn.setText("Change")

    def populate_versions(self, version_list):
        """Populate the main version list"""
        self.versions_list.clear()
        for version in version_list:
            self.versions_list.addItem(version)

    def populate_fabric_versions(self, version_list):
        """Populate the Fabric version list"""
        self.second_versions_list.clear()
        for version in version_list:
            self.second_versions_list.addItem(version)

    def filter_versions(self):
        """Filter versions based on search input"""
        if self.current_section == "Modrinth":
            self.has_searched = True
            self.search_modpacks(self.search_input.text().lower())
        else:
            query = self.search_input.text().lower()
            for i in range(self.versions_list.count()):
                item = self.versions_list.item(i)
                item.setHidden(query not in item.text().lower())

    def filter_modpacks(self):
        """Filter currently displayed modpacks based on search input"""
        query = self.search_input.text().lower().strip()
        
        for widget in self.modpack_widgets:
            title_match = query in widget.pack_data.get('title', '').lower()
            desc_match = query in widget.pack_data.get('description', '').lower()
            author_match = query in widget.pack_data.get('author', '').lower()

            should_show = not query or title_match or desc_match or author_match
            widget.setVisible(should_show)

    def filter_fabric_versions(self):
        """Filter Fabric versions based on search input"""
        query = self.second_search_input.text().lower()
        for i in range(self.second_versions_list.count()):
            item = self.second_versions_list.item(i)
            item.setHidden(query not in item.text().lower())
    
    def load_modpacks(self, sort_index=None):
        """Load modpacks from Modrinth API"""

        def fetch():
            try:
                url = "https://api.modrinth.com/v2/search"
                params = {
                    'facets': '[["project_type:modpack"]]',
                    'limit': 100,
                }

                if sort_index is not None and sort_index != "downloads":
                    params['index'] = sort_index 

                # Build the full URL with query parameters for debugging
                prepared_request = requests.Request('GET', url, params=params).prepare()
                print("Full request URL:", prepared_request.url)

                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                modpacks = []
                for hit in data.get('hits', []):
                    modpack = {
                        'id': hit.get('project_id'),
                        'title': hit.get('title'),
                        'description': hit.get('description'),
                        'author': hit.get('author'),
                        'icon_url': hit.get('icon_url'),
                        'downloads': hit.get('downloads', 0),
                        'updated': hit.get('date_modified'),
                        'created': hit.get('date_created'),
                        'categories': hit.get('categories', [])
                    }
                    modpacks.append(modpack)
                
                # Use QTimer to update UI from main thread
                self.populate_modpacks(modpacks)
            except Exception as e:
                print(f"Failed to load modpacks: {e}")
                
        fetch()

    def search_modpacks(self, query=""):
        """Load modpacks from Modrinth API with optional search query"""
        sort_by = self.sort_combo.currentText().lower()
        print("sorting this way")
        # Map UI text to API index values
        sort_mapping = {
            "relevance": "relevance",
            "downloads": "downloads", 
            "updated": "updated",
            "created": "newest"
        }
        
        sort_index = sort_mapping.get(sort_by, "downloads")

        def fetch():
            try:
                url = "https://api.modrinth.com/v2/search"
                params = {
                    'facets': '[["project_type:modpack"]]',
                    'limit': 20 if self.search_input.text() else 100,
                    'index': sort_index,
                    'query': query  
                }
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                modpacks = []
                for hit in data.get('hits', []):
                    modpack = {
                        'id': hit.get('project_id'),
                        'title': hit.get('title'),
                        'description': hit.get('description'),
                        'author': hit.get('author'),
                        'icon_url': hit.get('icon_url'),
                        'downloads': hit.get('downloads', 0),
                        'updated': hit.get('date_modified'),
                        'created': hit.get('date_created'),
                        'categories': hit.get('categories', [])
                    }
                    modpacks.append(modpack)
                
                self.populate_modpacks(modpacks)
            except Exception as e:
                print(f"Failed to load modpacks: {e}")
        
        fetch()

    def populate_modpacks(self, modpacks):
        """Populate the modpack list with widgets based on provided data."""
        
        if not self.flag:
            index = self.modpack_layout.indexOf(self.bottom_spacer)
            if index != -1:
                item = self.modpack_layout.takeAt(index)
                del item  # Optional: ensure it's cleaned up

        # Clear existing widgets
        for widget in self.modpack_widgets:
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.modpack_widgets.clear()

        # Store the new modpack data
        self.modpack_data = modpacks

        # Disable layout updates for performance
        self.modpack_container.setUpdatesEnabled(False)

        # Add new modpack widgets
        for i, modpack in enumerate(modpacks):
            widget = ModrinthPackWidget(modpack, self.themes[self.current_theme])
            self.modpack_widgets.append(widget)
            self.modpack_layout.addWidget(widget)

            # Periodically process events to keep UI responsive
            if i % 5 == 4:
                QApplication.processEvents()

        if self.flag:
            self.modpack_layout.addItem(self.bottom_spacer)
            self.flag = False
        else:
            self.modpack_layout.addItem(self.bottom_spacer)

        # Re-enable updates and refresh the container
        self.modpack_container.setUpdatesEnabled(True)
        self.modpack_container.update()

        print(f"Populated {len(modpacks)} modpacks")

    def sort_modpacks(self):
        """Sort modpacks by selected criteria and reload or re-sort local data"""
        sort_by = self.sort_combo.currentText().lower()

        # Map UI text to API index values and local data keys
        sort_mapping = {
            "relevance": None,
            "downloads": "downloads", 
            "updated": "updated",
            "created": "newest"
        }

        if self.search_input.text():
            self.search_modpacks(self.search_input.text())
        else:
            api_index = sort_mapping.get(sort_by, "downloads")
            print(api_index)
            self.load_modpacks(api_index)


    def select_modpack(self, selected_widget):
        """Select a modpack and update details panel"""
        # Deselect all other widgets
        for widget in self.modpack_widgets:
            widget.set_selected(widget == selected_widget)
        
        self.version_combo.clear()
        self.selected_modpack = selected_widget.pack_data
        self.update_modpack_details()
        self.load_modpack_versions()

    def update_modpack_details(self):
        """Update the details panel with selected modpack info"""
        if not self.selected_modpack:
            return
            
        self.details_title.setText(self.selected_modpack.get('title', 'Unknown Pack'))
        self.details_author.setText(f"by {self.selected_modpack.get('author', 'Unknown')}")
        self.details_description.setPlainText(self.selected_modpack.get('description', 'No description available'))
        
        # Format additional info
        downloads = self.selected_modpack.get('downloads', 0)
        categories = ', '.join(self.selected_modpack.get('categories', []))
        info_text = f"Downloads: {downloads:,}\nCategories: {categories}"
        self.details_info.setText(info_text)

    def load_modpack_versions(self):
        """Load versions for the selected modpack"""
        if not self.selected_modpack:
            return
            
        def fetch():
            try:
                project_id = self.selected_modpack['id']
                url = f"https://api.modrinth.com/v2/project/{project_id}/version"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                versions = response.json()
                
                version_list = []
                self.version_map = {}  # Create or clear the version map
                self.mod_data_map = {}

                for version in versions:
                    version_name = version.get('name', version.get('version_number', 'Unknown'))
                    game_versions = ', '.join(version.get('game_versions', []))
                    display_text = f"{version_name} (MC {game_versions})"

                    version_list.append(display_text)
                    self.version_map[display_text] = version  # Map display text to full version data

                    mod_list = []
                    for file_info in version.get('files', []):
                        # Check if this is the main modpack file (usually .mrpack)
                        if file_info.get('filename', '').endswith('.mrpack'):
                            continue
                        
                        mod_entry = {
                            'filename': file_info.get('filename'),
                            'url': file_info.get('url'),
                            'hashes': file_info.get('hashes', {}),
                            'size': file_info.get('size'),
                            'primary': file_info.get('primary', False)
                        }
                        mod_list.append(mod_entry)
                    
                    # Also get dependencies if available
                    dependencies = []
                    for dep in version.get('dependencies', []):
                        dep_entry = {
                            'project_id': dep.get('project_id'),
                            'version_id': dep.get('version_id'),
                            'dependency_type': dep.get('dependency_type')
                        }
                        dependencies.append(dep_entry)
                    
                    self.mod_data_map[display_text] = {
                        'files': mod_list,
                        'dependencies': dependencies,
                        'game_versions': version.get('game_versions', []),
                        'loaders': version.get('loaders', []),
                        'version_number': version.get('version_number'),
                        'changelog': version.get('changelog')
                    }

                self.populate_version_combo(version_list)


            except Exception as e:
                print(f"Failed to load modpack versions: {e}")
                
        fetch()

    def populate_version_combo(self, versions):
        """Populate the version combo box"""
        self.version_combo.clear()
        self.version_combo.addItems(versions)
        if versions:
            self.version_combo.setCurrentIndex(0)

    # Add this to the change_section method for the Modrinth case:
    def change_section(self, section):
        """Change the active section and update content"""
        from PyQt5.QtCore import QTimer
        import threading
        import requests

        # Helper functions to fetch data
        def fetch_vanilla_versions():
            def fetch():
                url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    data = response.json()
                    releases = [v["id"] for v in data["versions"]]
                    self.populate_versions(releases)
                    QTimer.singleShot(0, lambda: self.populate_versions(releases))
                except Exception as e:
                    print(f"Failed to fetch vanilla versions: {e}")
            threading.Thread(target=fetch, daemon=True).start()

        def fetch_fabric_versions():
            def fetch():
                url = "https://meta.fabricmc.net/v2/versions/loader"
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    data = response.json()
                    print("Fetched fabric versions")
                    versions = [f"Fabric {entry['version']}" for entry in data]
                    self.populate_fabric_versions(versions)
                    QTimer.singleShot(0, lambda: self.populate_versions(versions))
                except Exception as e:
                    print(f"Failed to fetch Fabric versions: {e}")
            threading.Thread(target=fetch, daemon=True).start()

        # Uncheck all buttons
        for btn in [self.vanilla_btn, self.fabric_btn, self.modrinth_btn]:
            btn.setChecked(False)

        self.versions_list.clear()
        self.current_section = section

        if section == "Vanilla":
            self.search_input.textChanged.connect(self.filter_versions)
            self.search_input.show()
            self.search_button.show()
            self.versions_list.show()
            self.second_search_input.hide()
            self.second_search_button.hide()
            self.second_versions_list.hide()
            self.modpack_scroll.hide()
            self.details_frame.hide()
            self.sort_layout.setParent(None)
            self.sort_label.hide()
            self.sort_combo.hide()
            self.vanilla_btn.setChecked(True)
            self.search_input.setPlaceholderText("Search Minecraft versions...")
            fetch_vanilla_versions()

        if section == "Fabric":
            self.search_input.textChanged.connect(self.filter_versions)
            self.second_search_input.show()
            self.second_search_button.show()
            self.second_versions_list.show()
            self.versions_list.show()
            self.sort_label.hide()
            self.sort_combo.hide()
            self.fabric_btn.setChecked(True)
            self.search_input.setPlaceholderText("Search Minecraft versions...")
            self.second_search_input.setPlaceholderText("Search Fabric version...")
            self.modpack_scroll.hide()
            self.details_frame.hide()
            self.sort_layout.setParent(None)
            fetch_vanilla_versions()
            fetch_fabric_versions()
        
        if section == "Modrinth":
            self.search_input.textChanged.disconnect()
            self.modrinth_btn.setChecked(True)
            self.versions_list.hide()
            self.sort_label.show()
            self.sort_combo.show()
            self.second_versions_list.hide()
            self.second_search_button.hide()
            self.second_search_input.hide()
            self.search_button.show()  # Show search button for Modrinth
            self.search_input.show()   # Show search input for Modrinth
            self.search_input.setPlaceholderText("Search Modpacks...")
            self.sort_layout.setParent(None)  # Remove from current layout
            self.content_layout.insertLayout(1, self.sort_layout)  # Add after search
            self.modpack_scroll.show()
            self.details_frame.show()
            self.load_modpacks()  
        
        self.validate_ok_button()

    def create_instance(self):
        data = self.get_instance_data()
        print(data)
        
        # If an image was selected, save it to the icons folder
        if self.selected_image_path:
            # Generate a destination filename based on instance name
            instance_name = self.name_input.text() if self.name_input.text() else self.current_section + " " + self.versions_list.currentItem().text()
            filename = instance_name.lower().replace(" ", "_") + os.path.splitext(self.selected_image_path)[1]
            
            # Ensure the icons directory exists
            os.makedirs(".icons", exist_ok=True)
            
            # Create the destination path
            destination_path = os.path.join(".icons", filename)
            
            # Copy the image file
            try:
                shutil.copy2(self.selected_image_path, destination_path)
                print(f"Image saved to {destination_path}")
            except Exception as e:
                print(f"Failed to save image: {e}")

        self.instanceCreated.emit(data)
        self.close()
    
    def apply_input_styles(self):
        if not self.current_theme:
            return
        theme = self.themes[self.current_theme]

        # For line edits (name_input and search_input)
        line_edit_style = f"""
            QLineEdit {{
                background-color: {theme['frame_bg']};
                color: {theme['text']};
                border: 1px solid {theme['button_bg']};
                padding: 4px 8px;
                border-radius: 3px;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme['selected_border']};
                background-color: {theme['instance_bg']};
            }}
        """
        self.name_input.setStyleSheet(line_edit_style)
        self.search_input.setStyleSheet(line_edit_style)
        self.second_search_input.setStyleSheet(line_edit_style)

        # For search_button
        button_style = f"""
            QPushButton {{
                background-color: {theme['button_bg']};
                color: {theme['text']};
                border: 1px solid {theme['button_bg']};
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme['button_hover']};
                border: 1px solid {theme['selected_border']};
            }}
            QPushButton:pressed {{
                background-color: {theme['selected_bg']};
                border: 1px solid {theme['selected_border']};
                color: white;
            }}
        """
        upload_style = f"""
            QPushButton {{
                background-color: {theme['button_bg']};
                color: {theme['text']};
                border: 1px solid {theme['button_bg']};
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {theme['button_hover']};
                border: 1px solid {theme['selected_border']};
            }}
            QPushButton:pressed {{
                background-color: {theme['selected_bg']};
                border: 1px solid {theme['selected_border']};
                color: white;
            }}
        """
        self.search_button.setStyleSheet(button_style)
        self.second_search_button.setStyleSheet(button_style)
        self.upload_btn.setStyleSheet(upload_style)
        
    def apply_button_style(self):
        if not self.current_theme:
            return
        theme = self.themes[self.current_theme]

        style = f"""
        QPushButton {{
            background-color: {theme['button_bg']};
            color: {theme['text']};
            border: 1px solid {theme['button_bg']};
            padding: 6px 12px;
            border-radius: 4px;
        }}
        QPushButton:hover {{
            background-color: {theme['button_hover']};
            border: 1px solid {theme['selected_border']};
        }}
        QPushButton:pressed {{
            background-color: {theme['selected_bg']};
            border: 1px solid {theme['selected_border']};
            color: white;
        }}
        QPushButton:disabled {{
            background-color: #222222;
            border: 1px solid transparent;
            color: #888888;
        }}
        """
        self.cancel_btn.setStyleSheet(style)
        self.ok_btn.setStyleSheet(style)

    def apply_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            theme = self.themes[theme_name]
            stylesheet = self.build_stylesheet(theme)
            self.setStyleSheet(stylesheet)
            self.apply_sidebar_button_style()
            self.apply_input_styles()
            self.apply_button_style()
            print(f"Applied theme: {theme_name}")

    def build_stylesheet(self, colors):
        return f"""
        background-color: {colors['background']};
        QPushButton, QToolButton {{
            background-color: {colors['button_bg']};
            color: {colors['text']};
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
        }}
        QLabel[class="instance-name"][selected="true"] {{
            border: 2px solid {colors['selected_border']};
            border-radius: 3px;
            background-color: {colors['selected_bg']};
        }}
        QScrollArea {{
            background-color: {colors['frame_bg']};
            border: none;
        }}
        """
    
    def get_instance_data(self):
        """Return the data for the new instance"""
        if self.current_section == "Modrinth":
            instance_name = self.name_input.text() or self.selected_modpack.get('title', 'Modrinth Pack')
            selected_version_display = self.version_combo.currentText()

            # Create image data
            image_data = None
            if self.selected_image_path:
                ext = os.path.splitext(self.selected_image_path)[1]
                filename = instance_name.lower().replace(" ", "_") + ext
                saved_path = os.path.join(".icons", filename)
                image_data = {
                    "original_path": self.selected_image_path,
                    "saved_path": saved_path
                }
            else:
                modpack_icon_url = self.selected_modpack.get('icon_url')
                if modpack_icon_url:
                    ext = os.path.splitext(modpack_icon_url.split("?")[0])[1] or ".png"
                    filename = instance_name.lower().replace(" ", "_") + ext
                    saved_path = os.path.join(".icons", filename)

                    # Ensure directory exists
                    os.makedirs(".icons", exist_ok=True)

                    try:
                        response = requests.get(modpack_icon_url, timeout=10)
                        response.raise_for_status()
                        with open(saved_path, "wb") as f:
                            f.write(response.content)

                        image_data = {
                            "original_path": modpack_icon_url,
                            "saved_path": saved_path
                        }
                    except Exception as e:
                        print(f"Failed to download modpack icon: {e}")

            def fetch():
                try:
                    selected_display = self.version_combo.currentText()
                    version_data = self.version_map.get(selected_display)

                    if version_data:
                        if version_data['files']:
                            file_url = version_data['files'][0]['url']
                            return file_url
                        else:
                            print("No files found in the selected version.")
                    else:
                        print(f"No version found matching: {selected_display}")

                except Exception as e:
                    print(f"Failed to load modpack version: {e}")

            import zipfile

            def download_file(url, output_path):
                try:
                    response = requests.get(url, stream=True, timeout=15)
                    response.raise_for_status()  # Raise error for bad responses

                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:  # filter out keep-alive chunks
                                f.write(chunk)

                    print(f"Download complete: {output_path}")

                    # Check if file is a zip file by extension, then unzip
                    if output_path.lower().endswith('.zip'):
                        unzip_dir = os.path.splitext(output_path)[0]  # remove .zip extension
                        os.makedirs(unzip_dir, exist_ok=True)

                        with zipfile.ZipFile(output_path, 'r') as zip_ref:
                            zip_ref.extractall(unzip_dir)

                        print(f"Unzipped to: {unzip_dir}")
                        return unzip_dir

                    return True

                except Exception as e:
                    print(f"Download failed: {e}")
                    return False
            
            GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
            file_url = fetch()
            print("File URL: " + file_url)
            unzip_dir = download_file(file_url, f"{GAME_DIR}/{instance_name}.zip")

            with open(f"{unzip_dir}/modrinth.index.json") as file:
                data = json.load(file)

            if 'fabric-loader' in data['dependencies']:
                section = "Fabric"
                fabric_version = f"Fabric {data['dependencies']['fabric-loader']}"
                print(fabric_version)
            else:
                section = "Forge"
                print('Error: Modpack is not Fabric')

            minecraft_version = data['dependencies']['minecraft']
            print(minecraft_version)

            mod_data = self.mod_data_map.get(selected_version_display, {})
            version_data = self.version_map.get(selected_version_display, {})

            mod_list = mod_data['dependencies']
            print("Modrinth mod data:", mod_list)

            # Fetch mod information using worker thread with progress dialog
            mods_info = self.fetch_mods_with_progress(mod_list)

                    
            return {
                "type": "Modrinth",
                "name": instance_name,
                "section": section,
                "selected_version": minecraft_version,
                "selected_fabric_version": fabric_version,
                "image": image_data,
                "mods": data['files'],
                "mod_data": mods_info,  # This contains the full mod list and metadata
                "version_number": mod_data['version_number'],
                # "modpack_metadata": {
                #    "project_id": self.selected_modpack.get('id'),
                #    "version_id": version_data.get('id'),
                #    "version_number": mod_data.get('version_number'),
                #    "title": self.selected_modpack.get('title'),
                #    "author": self.selected_modpack.get('author'),
                #    "description": self.selected_modpack.get('description')
                #}
            }
        
        else:
            # Existing logic for Vanilla/Fabric
            instance_name = self.name_input.text() if self.name_input.text() else self.current_section + " " + self.versions_list.currentItem().text()
            
            # Create image data
            image_data = None
            if self.selected_image_path:
                filename = instance_name.lower().replace(" ", "_") + os.path.splitext(self.selected_image_path)[1]
                image_data = {
                    "original_path": self.selected_image_path,
                    "saved_path": os.path.join(".icons", filename)
                }
            
            fabric_version = ""
            if self.current_section == "Fabric" and self.second_versions_list.currentItem():
                fabric_version = self.second_versions_list.currentItem().text()

            return {
                "type": "Custom",
                "name": instance_name,
                "section": self.current_section,
                "selected_version": self.versions_list.currentItem().text() if self.versions_list.currentItem() else "",
                "selected_fabric_version": fabric_version,
                "image": image_data,
                "mod_data": None,
            }
    
    def fetch_mods_with_progress(self, mod_list):
        """Fetch mod information using worker thread with progress dialog."""
        if not mod_list:
            return []
        
        # Create and show progress dialog
        progress_dialog = ProgressDialog(
            parent=self,
            title="Fetching Mod Information",
            theme_colors=self.current_theme
        )
        progress_dialog.set_status(f"Preparing to fetch information for {len(mod_list)} mods...")
        progress_dialog.progress_bar.setRange(0, len(mod_list))
        progress_dialog.progress_bar.setValue(0)
        
        # Create and configure worker
        self.mod_fetch_worker = ModFetchWorker(mod_list)
        mods_info_result = []
        
        def on_progress(current, total, mod_name):
            progress_dialog.progress_bar.setValue(current)
            progress_dialog.set_status(f"Processing mod {current}/{total}: {mod_name}")
        
        def on_log_update(message):
            progress_dialog.append_log(message)
        
        def on_finished(mods_info):
            nonlocal mods_info_result
            mods_info_result = mods_info
            progress_dialog.close_dialog(success=True)
            # Auto-close the dialog after a brief delay
            QTimer.singleShot(1000, progress_dialog.accept)  # Close after 1 second
        
        def on_error(error_msg):
            progress_dialog.append_log(f"ERROR: {error_msg}")
            progress_dialog.set_status("Error occurred during mod fetching")
        
        def on_cancel():
            progress_dialog.set_status("Cancelling...")
            self.mod_fetch_worker.stop()
        
        # Connect signals
        self.mod_fetch_worker.progress_updated.connect(on_progress)
        self.mod_fetch_worker.log_updated.connect(on_log_update)
        self.mod_fetch_worker.finished_with_data.connect(on_finished)
        self.mod_fetch_worker.error_occurred.connect(on_error)
        progress_dialog.cancelled.connect(on_cancel)
        
        # Start worker and show dialog
        self.mod_fetch_worker.start()
        progress_dialog.exec_()  # Block until dialog is closed
        
        # Clean up
        if hasattr(self, 'mod_fetch_worker'):
            self.mod_fetch_worker.wait()  # Wait for thread to finish
            self.mod_fetch_worker.deleteLater()
        
        return mods_info_result
    
# For standalone testing
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    window = add_instance_window()
    window.show()
    
    sys.exit(app.exec_())
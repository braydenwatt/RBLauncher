import sys
import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                           QPushButton, QListWidget, QListWidgetItem, QFrame, 
                           QScrollArea, QWidget, QSizePolicy, QComboBox, 
                           QGridLayout, QCheckBox, QSpacerItem, QFileDialog,
                           QTextEdit, QSplitter, QApplication, QTabWidget,
                           QProgressBar)
from PyQt5.QtGui import QIcon, QPixmap, QColor, QImage, QPainter
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer, QUrl, QObject
import json
import requests
import threading

class ModWidget(QWidget):
    """Custom widget for displaying a mod in the list"""
    
    def __init__(self, mod_data, theme_colors):
        super().__init__()
        self.mod_data = mod_data
        self.theme_colors = theme_colors
        self.selected = False
        self.init_ui()
        
    def init_ui(self):
        # Set fixed height to prevent stretching
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        self.user_interaction = True  # Track if change is from user or program
        
        self.checkbox = QCheckBox()
        self.checkbox.setFixedSize(20, 20)
        self.checkbox.stateChanged.connect(self.on_checkbox_state_changed)
        layout.addWidget(self.checkbox, 0, Qt.AlignVCenter)
        
        self.checkbox.setCheckState(Qt.Unchecked)

        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setScaledContents(True)
        self.icon_label.setStyleSheet(f"background-color: {self.theme_colors['icon_bg']}; border-radius: 4px;")
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        if self.mod_data.get('icon_url'):
            self.load_icon()
        else:
            # Default icon
            pixmap = QPixmap(48, 48)
            pixmap.fill(QColor(self.theme_colors['icon_bg']))
            self.icon_label.setPixmap(pixmap)
        
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        
        # Content (title and description)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        self.title_label = QLabel(self.mod_data.get('title', 'Unknown Mod'))
        self.title_label.setStyleSheet(f"color: {self.theme_colors['text']}; font-weight: bold; font-size: 14px;")
        self.title_label.setWordWrap(True)
        
        # Description
        description = self.mod_data.get('description', '')
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
                response = requests.get(self.mod_data['icon_url'], timeout=10)
                response.raise_for_status()
                
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                self.icon_label.setPixmap(pixmap)
                self.icon_label.setFixedSize(48, 48)
                self.icon_label.setScaledContents(True)
            except Exception as e:
                print(f"Failed to load icon: {e}")
        
        if self.mod_data['icon_url'] == "Default":
            pixmap = QPixmap('.icons/default.png')
            self.icon_label.setPixmap(pixmap)
            self.icon_label.setFixedSize(48, 48)
            self.icon_label.setScaledContents(True)
        else:
            threading.Thread(target=fetch_icon, daemon=True).start()

    def on_checkbox_state_changed(self, state):
        if not self.user_interaction:
            return

        if state == Qt.Checked:
            # User tried to check -> revert to unchecked
            self.user_interaction = False
            self.checkbox.setCheckState(Qt.Unchecked)
            self.user_interaction = True
        elif state == Qt.Unchecked:
            parent = self.parent()
            while parent and not isinstance(parent, install_mods_window):
                parent = parent.parent()
            if parent:
                parent.remove_mod_from_selection(self.mod_data)
            self.user_interaction = False
            self.checkbox.setCheckState(Qt.Unchecked)
            self.user_interaction = True
    
    def set_checked(self, checked):
        """Set checkbox state programmatically"""
        self.user_interaction = False
        self.checkbox.setCheckState(Qt.Checked)
        self.user_interaction = True
        
    def is_checked(self):
        """Get checkbox state"""
        return self.checkbox.isChecked()
    
    def set_selected(self, selected):
        self.selected = selected
        self.update_selection_style()
        
    def update_selection_style(self):
        if self.selected:
            self.setStyleSheet(f"""
                ModWidget {{
                    background-color: {self.theme_colors['selected_bg']};
                    border: 1px solid {self.theme_colors['selected_border']};
                    border-radius: 4px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ModWidget {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                }}
                ModWidget:hover {{
                    background-color: {self.theme_colors['button_hover']};
                    border: 1px solid {self.theme_colors['instance_border']};
                }}
            """)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Find the parent install_mods_window
            parent = self.parent()
            while parent and not isinstance(parent, install_mods_window):
                parent = parent.parent()
            if parent:
                parent.select_mod(self)
        super().mousePressEvent(event)

class SelectedModWidget(QWidget):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    """Widget for displaying selected mods in the confirmation tab"""
    
    def __init__(self, mod_data, theme_colors, parent_window):
        super().__init__()
        self.mod_data = mod_data
        self.theme_colors = theme_colors
        self.parent_window = parent_window
        self.init_ui()
        
    def init_ui(self):
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setScaledContents(True)
        self.icon_label.setStyleSheet(f"background-color: {self.theme_colors['icon_bg']}; border-radius: 4px;")
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # Placeholder icon
        if self.mod_data.get('icon_url'):
            self.load_icon()
        else:
            # Default icon
            pixmap = QPixmap(40, 40)
            pixmap.fill(QColor(self.theme_colors['icon_bg']))
            self.icon_label.setPixmap(pixmap)
        
        layout.addWidget(self.icon_label, 0, Qt.AlignTop)
        
        # Content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        print(self.mod_data)

        # Title
        self.title_label = QLabel(self.mod_data.get('title', 'Unknown Mod'))
        self.title_label.setStyleSheet(f"color: {self.theme_colors['text']}; font-weight: bold; font-size: 13px;")
        
        # Author and downloads
        author = self.mod_data.get('author', 'Unknown')
        downloads = self.mod_data.get('downloads', 0)
        version = self.mod_data.get('version', 'Unknown')
        print(version)
        self.info_label = QLabel(f"by {author} • {downloads:,} downloads • {version}")
        self.info_label.setStyleSheet(f"color: {self.theme_colors['text']}; opacity: 0.7; font-size: 11px;")
        
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.info_label)
        content_layout.addStretch()
        
        layout.addLayout(content_layout, 1)
        
        # Remove button
        self.remove_btn = QPushButton("")
        icon = self.load_colored_svg_icon(".icons/close.svg")
        self.remove_btn.setIcon(icon)
        self.remove_btn.setFixedSize(25, 25)
        self.remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.theme_colors['button_bg']};
                color: {self.theme_colors['text']};
                border: none;
                border-radius: 12px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #ff4444;
                color: white;
            }}
        """)
        self.remove_btn.clicked.connect(self.remove_mod)
        
        layout.addWidget(self.remove_btn, 0, Qt.AlignTop)
        
        # Style the widget
        self.setStyleSheet(f"""
            SelectedModWidget {{
                background-color: {self.theme_colors['instance_bg']};
                border: 1px solid {self.theme_colors['instance_border']};
                border-radius: 4px;
            }}
        """)
    
    def load_icon(self):
        """Load icon from URL"""
        def fetch_icon():
            try:
                response = requests.get(self.mod_data['icon_url'], timeout=10)
                response.raise_for_status()
                
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                
                self.icon_label.setPixmap(pixmap)
                self.icon_label.setFixedSize(48, 48)
                self.icon_label.setScaledContents(True)
            except Exception as e:
                print(f"Failed to load icon: {e}")
        
        if self.mod_data['icon_url'] == "Default":
            pixmap = QPixmap('.icons/default.png')
            self.icon_label.setPixmap(pixmap)
            self.icon_label.setFixedSize(48, 48)
            self.icon_label.setScaledContents(True)
        else:
            threading.Thread(target=fetch_icon, daemon=True).start()

    def remove_mod(self):
        """Remove this mod from selection"""
        self.parent_window.remove_mod_from_selection(self.mod_data)

    def load_colored_svg_icon(self, file_path):
        import re

        color = self.theme_colors['text']

        with open(file_path, 'r') as f:
            svg_content = f.read()

        # Replace fill="#xxxxxx"
        svg_content = re.sub(r'fill="#[0-9a-fA-F]{6}"', f'fill="{color}"', svg_content)
        svg_content = re.sub(r'stroke="#[0-9a-fA-F]{6}"', f'stroke="{color}"', svg_content)
        svg_content = re.sub(r'stroke-width="#[0-9a-fA-F]{6}"', f'stroke-width="1"', svg_content)
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

class install_mods_window(QDialog):
    """Dialog window for installing mods"""
    modsInstalled = pyqtSignal()
    
    def __init__(self, parent=None, theme_colors=None, instance_name=""):
        super().__init__(parent)
        self.setWindowTitle("Install Mods")
        self.setMinimumSize(1000, 700)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint)
        
        # Store selected mods and mod widgets
        self.selected_mods = []
        self.mod_widgets = []
        self.selected_mod_widgets = []
        self.mod_data = []
        self.selected_mod = None
        self.instance_name = instance_name
        
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
        self.load_mods()  # Load placeholder mods
        
    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Tab widget for Browse and Selected tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {self.themes[self.current_theme]['instance_border']};
                background: {self.themes[self.current_theme]['frame_bg']};
            }}
            QTabBar::tab {{
                background: {self.themes[self.current_theme]['button_bg']};
                color: {self.themes[self.current_theme]['text']};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {self.themes[self.current_theme]['selected_bg']};
                color: white;
            }}
            QTabBar::tab:hover {{
                background: {self.themes[self.current_theme]['button_hover']};
            }}
        """)
        
        # Browse tab
        self.browse_tab = QWidget()
        self.setup_browse_tab()
        self.tab_widget.addTab(self.browse_tab, "Browse Mods")
        
        # Selected tab
        self.selected_tab = QWidget()
        self.setup_selected_tab()
        self.tab_widget.addTab(self.selected_tab, "Selected (0)")
        
        main_layout.addWidget(self.tab_widget, 1)
        
        # Bottom buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)

        self.cancel_btn = QPushButton("Cancel")
        self.install_btn = QPushButton("Install Selected")
        self.install_btn.setFixedWidth(125)
        self.install_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.themes[self.current_theme]['button_bg']};
                color: {self.themes[self.current_theme]['text']};
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {self.themes[self.current_theme]['button_hover']};
                border: 1px solid {self.themes[self.current_theme]['selected_bg']};
            }}
            QPushButton:disabled {{
                background-color: #222222;
                border: 1px solid transparent;
                color: #888888;
            }}
        """)
        self.install_btn.setDefault(True)
        self.install_btn.setEnabled(False)

        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addWidget(self.install_btn)

        main_layout.addLayout(buttons_layout, 0)
        
        # Connect signals
        self.cancel_btn.clicked.connect(self.reject)
        self.install_btn.clicked.connect(self.install_mods)
        self.mod_data_map = {}
        self.version_map = {}
        
    def setup_browse_tab(self):
        """Setup the browse mods tab"""
        layout = QVBoxLayout(self.browse_tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Search and filter controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(15)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search mods...")
        self.search_button = QPushButton("Search")
        self.search_button.pressed.connect(lambda: self.sort_mods(self.search_input.text()))
        
        # Sort dropdown
        self.sort_label = QLabel("Sort by:")
        self.sort_combo = QComboBox()
        self.sort_combo.setFixedWidth(105)
        self.sort_combo.setStyleSheet(f"""
            QComboBox {{
                background: transparent;
                border: none;
                color: {self.themes[self.current_theme]['text']};
                padding-right: 20px; 
            }}

            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}

            QComboBox QAbstractItemView {{
                min-width: 110px;  /* Set your desired width */
            }}
        """)
        self.sort_combo.addItems(["Relevance", "Downloads", "Updated", "Created"])
        self.sort_combo.currentTextChanged.connect(lambda: self.sort_mods(self.search_input.text()))
        
        controls_layout.addWidget(self.search_input, 1)
        controls_layout.addWidget(self.search_button)
        controls_layout.addWidget(self.sort_label)
        controls_layout.addWidget(self.sort_combo)
        
        layout.addLayout(controls_layout)
        
        # Main content area with splitter
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - mod list
        left_frame = QFrame()
        left_frame.setFrameShape(QFrame.StyledPanel)
        left_frame.setMinimumWidth(400)
        
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        self.mod_scroll = QScrollArea()
        self.mod_scroll.setWidgetResizable(True)
        self.mod_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mod_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.mod_container = QWidget()
        self.mod_layout = QVBoxLayout(self.mod_container)
        self.mod_layout.setSpacing(2)
        self.mod_layout.setContentsMargins(5, 5, 5, 5)

        # Set the container background to match frame_bg
        self.mod_container.setStyleSheet(f"""
            QWidget {{
                background-color: {self.themes[self.current_theme]['frame_bg']};
            }}
        """)

        self.mod_scroll.setWidget(self.mod_container)
        
        # Add spacer at the bottom
        self.bottom_spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.mod_layout.addItem(self.bottom_spacer)
        
        left_layout.addWidget(self.mod_scroll, 1)
        
        # Right side - mod details
        self.details_frame = QFrame()
        self.details_frame.setFrameShape(QFrame.StyledPanel)
        self.details_frame.setStyleSheet(f"background: {self.themes[self.current_theme]['frame_bg']}; border: none;")
        self.details_frame.setMinimumWidth(300)
        
        details_layout = QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(10)
        
        # Mod details widgets
        self.details_title = QLabel("Select a mod")
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
        
        # Version selection
        version_layout = QHBoxLayout()
        version_label = QLabel("Version:")
        version_label.setStyleSheet(f"color: {self.themes[self.current_theme]['text']};")
        self.version_combo = QComboBox()
        version_layout.addWidget(version_label)
        self.version_combo.setStyleSheet(f"""
            QComboBox {{
                background: transparent;
                border: none;
                color: {self.themes[self.current_theme]['text']};
                padding: 6px 0px; 
                border-radius: 4px;
            }}

            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
        """)
        version_layout.addWidget(self.version_combo, 1)
        
        # Add to selection button
        self.add_btn = QPushButton("Select for Installation")
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.themes[self.current_theme]['button_bg']};
                color: {self.themes[self.current_theme]['text']};
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {self.themes[self.current_theme]['button_hover']};
                border: 1px solid {self.themes[self.current_theme]['selected_bg']};
            }}
            QPushButton:disabled {{
                background-color: #222222;
                border: 1px solid transparent;
                color: #888888;
            }}
        """)
        
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(lambda: self.add_mod_to_selection(self.selected_mod))
        
        details_layout.addWidget(self.details_title)
        details_layout.addWidget(self.details_author)
        details_layout.addWidget(self.details_description, 1)
        details_layout.addWidget(self.details_info)
        details_layout.addLayout(version_layout)
        details_layout.addWidget(self.add_btn)
        details_layout.addStretch()
        
        # Add frames to splitter
        content_splitter.addWidget(left_frame)
        content_splitter.addWidget(self.details_frame)
        content_splitter.setSizes([500, 300])
        
        layout.addWidget(content_splitter, 1)
        
    def load_modpack_versions(self):
        """Load versions for the selected modpack"""
        if not self.selected_mod:
            return
            
        def fetch():
            try:
                project_id = self.selected_mod['project_id']
                url = f"https://api.modrinth.com/v2/project/{project_id}/version"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                versions = response.json()
                
                version_list = []


                for version in versions:
                    print(version)
                    version_name = version.get('name')
                    game_versions = ', '.join(version.get('game_versions', []))
                    loader = ', '.join([l.capitalize() for l in version.get('loaders', [])])
                    display_text = f"{version_name} ({loader} {game_versions})"

                    version_list.append(display_text)
                    self.version_map[display_text] = version  # Map display text to full version data

                    mod_list = []
                    for file_info in version.get('files', []):
                        # Check if this is the main modpack file (usually .mrpack)
                        if file_info.get('filename', '').endswith('.mrpack'):
                            continue
                        
                        mod_entry = {
                            'version_id': version.get('id'),
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

    def setup_selected_tab(self):
        """Setup the selected mods tab"""
        layout = QVBoxLayout(self.selected_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Header with count and clear button
        header_layout = QHBoxLayout()
        self.selected_count_label = QLabel("0 mods selected")
        self.selected_count_label.setStyleSheet(f"color: {self.themes[self.current_theme]['text']}; font-size: 14px; font-weight: bold;")
        
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_selections)
        
        header_layout.addWidget(self.selected_count_label)
        header_layout.addStretch()
        header_layout.addWidget(self.clear_all_btn)
        
        layout.addLayout(header_layout)
        
        # Selected mods scroll area
        self.selected_scroll = QScrollArea()
        self.selected_scroll.setWidgetResizable(True)
        self.selected_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {self.themes[self.current_theme]['frame_bg']};
                border-radius: 4px;
            }}
        """)
        
        self.selected_container = QWidget()
        self.selected_layout = QVBoxLayout(self.selected_container)
        self.selected_layout.setSpacing(5)
        self.selected_layout.setContentsMargins(10, 10, 10, 10)
        self.selected_scroll.setWidget(self.selected_container)
        
        # Add spacer at the bottom
        self.selected_spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.selected_layout.addItem(self.selected_spacer)
        
        layout.addWidget(self.selected_scroll, 1)
        
        # Empty state label
        self.empty_label = QLabel("No mods selected yet.\nBrowse the 'Browse Mods' tab to add mods.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet(f"""
            color: {self.themes[self.current_theme]['text']};
            font-size: 14px;
            opacity: 0.6;
            padding: 40px;
        """)
        layout.addWidget(self.empty_label)
     
    def populate_mods(self, mods):
        """Populate the mod list with widgets"""
        # Clear existing widgets
        for widget in self.mod_widgets:
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.mod_widgets.clear()
        
        # Remove spacer temporarily
        index = self.mod_layout.indexOf(self.bottom_spacer)
        if index != -1:
            self.mod_layout.takeAt(index)
        
        self.mod_data = mods
        
        # Add new mod widgets
        for mod in mods:
            widget = ModWidget(mod, self.themes[self.current_theme])
            self.mod_widgets.append(widget)
            self.mod_layout.addWidget(widget)
        
        # Re-add spacer
        self.mod_layout.addItem(self.bottom_spacer)
        
        print(f"Populated {len(mods)} mods")
        
    def select_mod(self, selected_widget):
        """Select a mod and update details panel"""
        # Deselect all other widgets
        for widget in self.mod_widgets:
            widget.set_selected(widget == selected_widget)
        
        self.selected_mod = selected_widget.mod_data
        self.update_mod_details()
        self.load_modpack_versions()
        
    def update_mod_details(self):
        """Update the details panel with selected mod info"""
        if not self.selected_mod:
            return
            
        self.details_title.setText(self.selected_mod.get('title', 'Unknown Mod'))
        self.details_author.setText(f"by {self.selected_mod.get('author', 'Unknown')}")
        self.details_description.setPlainText(self.selected_mod.get('description', 'No description available'))
        
        # Format additional info
        downloads = self.selected_mod.get('downloads', 0)
        categories = ', '.join(self.selected_mod.get('categories', []))
        info_text = f"Downloads: {downloads:,}\nCategories: {categories}"
        self.details_info.setText(info_text)
        
        # Populate version combo
        versions = self.selected_mod.get('versions', [])
        self.version_combo.clear()
        self.version_combo.addItems(versions)
        
        # Enable add button
        self.add_btn.setEnabled(True)
    
    def update_selection_ui(self):
        """Update the selection-related UI elements"""
        count = len(self.selected_mods)
        
        # Update tab title
        self.tab_widget.setTabText(1, f"Selected ({count})")
        
        # Update count label
        self.selected_count_label.setText(f"{count} mod{'s' if count != 1 else ''} selected")
        
        # Update install button
        self.install_btn.setEnabled(count > 0)
        self.install_btn.setText(f"Install {count} Mod{'s' if count != 1 else ''}" if count > 0 else "Install Selected")
        
        # Show/hide empty state
        self.empty_label.setVisible(count == 0)
        self.selected_scroll.setVisible(count > 0)

    def add_mod_to_selection(self, mod_data):
        """Add a mod to the selection"""
        #print(self.mod_data_map)

        if mod_data not in self.selected_mods:
            self.selected_mods.append(mod_data)
            version = self.version_combo.currentText()
            mod_data['version'] = version

            # Create widget for selected tab
            selected_widget = SelectedModWidget(mod_data, self.themes[self.current_theme], self)
            self.selected_mod_widgets.append(selected_widget)
            
            # Remove spacer temporarily
            index = self.selected_layout.indexOf(self.selected_spacer)
            if index != -1:
                self.selected_layout.takeAt(index)
            
            # Add the widget
            self.selected_layout.addWidget(selected_widget)
            
            # Re-add spacer
            self.selected_layout.addItem(self.selected_spacer)
            
            # Update UI
            self.update_selection_ui()
            
            # Find and check the corresponding mod widget in browse tab
            for widget in self.mod_widgets:
                if widget.mod_data.get('project_id') == mod_data.get('project_id'):
                    widget.set_checked(True)
                    break

    def remove_mod_from_selection(self, mod_data):
        """Remove a mod from the selection"""
        if mod_data in self.selected_mods:
            self.selected_mods.remove(mod_data)
            
            # Remove widget from selected tab
            for widget in self.selected_mod_widgets[:]:  # Use slice to avoid modification during iteration
                if widget.mod_data.get('project_id') == mod_data.get('project_id'):
                    self.selected_mod_widgets.remove(widget)
                    widget.setParent(None)
                    widget.deleteLater()
                    break
            
            # Update UI
            self.update_selection_ui()
            
            # Find and uncheck the corresponding mod widget in browse tab
            for widget in self.mod_widgets:
                if widget.mod_data.get('project_id') == mod_data.get('project_id'):
                    self.user_interaction = False
                    widget.checkbox.setCheckState(Qt.Unchecked)
                    self.user_interaction = True
                    break

    def update_selection_ui(self):
        """Update the selection-related UI elements"""
        count = len(self.selected_mods)
        
        # Update tab title
        self.tab_widget.setTabText(1, f"Selected ({count})")
        
        # Update count label
        self.selected_count_label.setText(f"{count} mod{'s' if count != 1 else ''} selected")
        
        # Update install button
        self.install_btn.setEnabled(count > 0)
        self.install_btn.setText(f"Install {count} Mod{'s' if count != 1 else ''}" if count > 0 else "Install Selected")
        
        # Show/hide empty state
        self.empty_label.setVisible(count == 0)
        self.selected_scroll.setVisible(count > 0)

    def search_mods(self, query=""):
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
                    'facets': '[["project_type:mod"]]',
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
                        'project_id': hit.get('project_id'),
                        'title': hit.get('title'),
                        'description': hit.get('description'),
                        'author': hit.get('author'),
                        'icon_url': hit.get('icon_url'),
                        'downloads': hit.get('downloads', 0),
                        'updated': hit.get('date_modified'),
                        'created': hit.get('date_created'),
                        'categories': hit.get('categories', []),
                        'gallery': hit.get('gallery', [])
                    }
                    modpacks.append(modpack)
                
                self.populate_mods(modpacks)

            except Exception as e:
                print(f"Failed to load modpacks: {e}")
        
        fetch()

    def load_mods(self, sort_index=None):
        """Load modpacks from Modrinth API"""

        def fetch():
            try:
                url = "https://api.modrinth.com/v2/search"
                params = {
                    'facets': '[["project_type:mod"]]',
                    'limit': 100,
                }

                if sort_index is not None:
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
                        'project_id': hit.get('project_id'),
                        'title': hit.get('title'),
                        'description': hit.get('description'),
                        'author': hit.get('author'),
                        'icon_url': hit.get('icon_url'),
                        'downloads': hit.get('downloads', 0),
                        'updated': hit.get('date_modified'),
                        'created': hit.get('date_created'),
                        'categories': hit.get('categories', []),
                        'gallery': hit.get('gallery', [])
                    }
                    modpacks.append(modpack)
                
                # Use QTimer to update UI from main thread
                self.populate_mods(modpacks)

            except Exception as e:
                print(f"Failed to load modpacks: {e}")
        
        fetch()
                
    def sort_mods(self, query):
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
            self.search_mods(self.search_input.text())
        else:
            api_index = sort_mapping.get(sort_by, "downloads")
            print(api_index)
            self.load_mods(api_index)
        
        # Restore checkbox states for selected mods
        for widget in self.mod_widgets:
            for selected_mod in self.selected_mods:
                if widget.mod_data.get('project_id') == selected_mod.get('project_id'):
                    widget.set_checked(True)
                    break

    def clear_all_selections(self):
        """Clear all selected mods"""
        # Clear the selected mods list
        self.selected_mods.clear()
        
        # Remove all selected mod widgets
        for widget in self.selected_mod_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self.selected_mod_widgets.clear()
        
        # Uncheck all mod widgets in browse tab
        for widget in self.mod_widgets:
            self.user_interaction = False
            widget.checkbox.setCheckState(Qt.Unchecked)
            self.user_interaction = True
        
        # Update UI
        self.update_selection_ui()

    def install_dependency(self, dep_project_id, mod_data_list, processed_projects, parent_version_data=None):
        """Install a dependency by project ID, matching parent mod's version and loader"""
        try:
            # Fetch project info
            project_url = f"https://api.modrinth.com/v2/project/{dep_project_id}"
            project_response = requests.get(project_url, timeout=10)
            project_response.raise_for_status()
            project_data = project_response.json()
            
            # Fetch all versions for the dependency
            versions_url = f"https://api.modrinth.com/v2/project/{dep_project_id}/version"
            versions_response = requests.get(versions_url, timeout=10)
            versions_response.raise_for_status()
            versions_data = versions_response.json()
            
            if not versions_data:
                print(f"No versions found for dependency: {dep_project_id}")
                return False
            
            # Get target game versions and loaders from parent mod
            target_game_versions = set()
            target_loaders = set()
            
            if parent_version_data:
                target_game_versions = set(parent_version_data.get("game_versions", []))
                target_loaders = set(parent_version_data.get("loaders", []))
            
            # If no parent version data, try to get from instance config or use defaults
            if not target_game_versions or not target_loaders:
                # You might want to get this from your instance configuration
                # For now, falling back to common defaults
                print(f"Warning: No version constraints from parent mod, using fallback logic")
            
            # Find the best matching version
            best_version = None
            best_score = -1
            
            for version in versions_data:
                version_game_versions = set(version.get("game_versions", []))
                version_loaders = set(version.get("loaders", []))
                
                # Calculate compatibility score
                score = 0
                
                # Check game version compatibility
                if target_game_versions:
                    game_version_match = len(target_game_versions.intersection(version_game_versions))
                    if game_version_match == 0:
                        continue  # Skip if no game version overlap
                    score += game_version_match * 10  # Higher weight for game version matches
                
                # Check loader compatibility
                if target_loaders:
                    loader_match = len(target_loaders.intersection(version_loaders))
                    if loader_match == 0:
                        continue  # Skip if no loader overlap
                    score += loader_match * 5  # Weight for loader matches
                
                # Prefer newer versions (higher index in sorted list means older)
                score += (len(versions_data) - versions_data.index(version)) * 0.1
                
                if score > best_score:
                    best_score = score
                    best_version = version
            
            # Fallback to latest version if no compatible version found
            if not best_version:
                print(f"Warning: No compatible version found for dependency {dep_project_id}, using latest")
                best_version = versions_data[0]
            else:
                print(f"Selected version {best_version.get('version_number', 'Unknown')} for dependency {dep_project_id}")
                if target_game_versions:
                    matching_game_versions = set(best_version.get("game_versions", [])).intersection(target_game_versions)
                    print(f"  Game versions: {', '.join(matching_game_versions)}")
                if target_loaders:
                    matching_loaders = set(best_version.get("loaders", [])).intersection(target_loaders)
                    print(f"  Loaders: {', '.join(matching_loaders)}")
            
            # Create mod object for dependency
            dep_mod = {
                "project_id": dep_project_id,
                "title": project_data.get("title", "Unknown Dependency"),
                "description": project_data.get("description", ""),
                "author": project_data.get("team", "Unknown"),
                "downloads": project_data.get("downloads", 0),
                "icon_url": project_data.get("icon_url", "Default")
            }
            
            # Install the dependency with the selected version
            return self.install_single_mod(dep_mod, best_version, mod_data_list, processed_projects)
            
        except Exception as e:
            print(f"Error installing dependency {dep_project_id}: {e}")
            return False

    def install_mods(self):
        """Start installation in a worker thread and show a progress dialog."""
        if not self.selected_mods:
            return

        # Create progress dialog
        self.install_progress_dialog = QDialog(self)
        self.install_progress_dialog.setWindowTitle("Installing Mods")
        self.install_progress_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
        self.install_progress_dialog.setFixedSize(500, 300)
        self.install_progress_dialog.setModal(True)

        layout = QVBoxLayout(self.install_progress_dialog)

        self.install_progress_label = QLabel("Preparing to install mods...")
        layout.addWidget(self.install_progress_label)

        self.install_progress_bar = QProgressBar()
        self.install_progress_bar.setRange(0, 100)
        layout.addWidget(self.install_progress_bar)

        self.install_progress_text = QTextEdit()
        self.install_progress_text.setMaximumHeight(140)
        self.install_progress_text.setReadOnly(True)
        layout.addWidget(self.install_progress_text)

        button_layout = QHBoxLayout()
        self.cancel_install_btn = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_install_btn)
        layout.addLayout(button_layout)

        # Apply theme to progress dialog
        self.install_progress_dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {self.themes[self.current_theme]['background']};
                color: {self.themes[self.current_theme]['text']};
            }}
            QLabel {{ color: {self.themes[self.current_theme]['text']}; }}
            QTextEdit {{ background-color: {self.themes[self.current_theme]['frame_bg']}; color: {self.themes[self.current_theme]['text']}; border: 1px solid {self.themes[self.current_theme]['button_bg']}; }}
            QPushButton {{ background-color: {self.themes[self.current_theme]['button_bg']}; color: {self.themes[self.current_theme]['text']}; padding: 6px 12px; border-radius: 4px; }}
            QPushButton:hover {{ background-color: {self.themes[self.current_theme]['button_hover']}; }}
        """)

        # Worker and thread
        class InstallerWorker(QObject):
            progress = pyqtSignal(str, int, str)  # mod_name, percent, message
            log = pyqtSignal(str)
            finished = pyqtSignal(bool)

            def __init__(self, window):
                super().__init__()
                self.window = window
                self._should_stop = False

            def stop(self):
                self._should_stop = True

            def run(self):
                try:
                    CONFIG_PATH = os.path.expanduser("~/.minecraft_launcher_config.json")

                    # Load existing config
                    try:
                        with open(CONFIG_PATH, 'r') as f:
                            config = json.load(f)
                    except Exception as e:
                        self.log.emit(f"Failed to load config: {e}")
                        self.finished.emit(False)
                        return

                    instance_data = config.get('instances', {}).get(self.window.instance_name, {})
                    if not instance_data:
                        self.log.emit(f"Instance '{self.window.instance_name}' not found in config.")
                        self.finished.emit(False)
                        return

                    mod_data_list = instance_data.setdefault('mod_data', [])

                    processed_projects = set()
                    for existing_mod in mod_data_list:
                        if 'project_id' in existing_mod:
                            processed_projects.add(existing_mod['project_id'])

                    total = len(self.window.selected_mods)
                    idx = 0

                    for mod in list(self.window.selected_mods):
                        if self._should_stop:
                            self.log.emit("Installation cancelled by user.")
                            break

                        idx += 1
                        mod_name = mod.get('title', 'Unknown')
                        percent = int(((idx - 1) / total) * 100) if total > 0 else 0
                        self.progress.emit(mod_name, percent, f"Starting ({idx}/{total})")
                        self.log.emit(f"Installing: {mod_name}")

                        version_key = mod.get('version', '') if isinstance(mod, dict) else ''
                        version_data = self.window.version_map.get(version_key)

                        if not version_data or not isinstance(version_data, dict):
                            self.log.emit(f"No version data found for: {mod_name}")
                            continue

                        # Call the existing installation helper (safe to run off the main thread since it doesn't touch Qt)
                        success = self.window.install_single_mod(mod, version_data, mod_data_list, processed_projects)

                        if success:
                            self.log.emit(f"✓ Installed: {mod_name}")
                        else:
                            self.log.emit(f"✗ Failed to install: {mod_name}")

                        percent = int((idx / total) * 100) if total > 0 else 100
                        self.progress.emit(mod_name, percent, "Finished")

                        # Process required dependencies
                        dependencies = version_data.get("dependencies", [])
                        for dep in dependencies:
                            if self._should_stop:
                                break
                            if dep.get("dependency_type") == "required":
                                dep_project_id = dep.get("project_id")
                                if not dep_project_id or dep_project_id in processed_projects:
                                    continue
                                self.log.emit(f"Installing required dependency: {dep_project_id}")
                                if self.window.install_dependency(dep_project_id, mod_data_list, processed_projects, version_data):
                                    self.log.emit(f"✓ Installed dependency: {dep_project_id}")
                                else:
                                    self.log.emit(f"✗ Failed to install dependency: {dep_project_id}")

                    # Save updated config
                    try:
                        with open(CONFIG_PATH, 'w') as f:
                            json.dump(config, f, indent=4)
                        self.log.emit("Config successfully updated with downloaded mods.")
                    except Exception as e:
                        self.log.emit(f"Failed to save updated config: {e}")
                        self.finished.emit(False)
                        return

                    self.finished.emit(True)
                except Exception as e:
                    self.log.emit(f"Installer error: {e}")
                    self.finished.emit(False)

        # Create worker and thread
        self._installer_thread = QThread()
        self._installer_worker = InstallerWorker(self)
        self._installer_worker.moveToThread(self._installer_thread)

        # Wire signals
        self._installer_thread.started.connect(self._installer_worker.run)
        self._installer_worker.progress.connect(lambda name, pct, msg: self._on_install_progress(name, pct, msg))
        self._installer_worker.log.connect(lambda message: self._append_install_log(message))
        self._installer_worker.finished.connect(lambda success: self._on_install_finished(success))
        self._installer_worker.finished.connect(self._installer_thread.quit)
        self._installer_thread.finished.connect(self._installer_thread.deleteLater)

        self.cancel_install_btn.clicked.connect(lambda: self._installer_worker.stop())

        # Show dialog and start
        self.install_progress_dialog.show()
        self._installer_thread.start()

    def _on_install_progress(self, mod_name, percent, message):
        self.install_progress_label.setText(f"{mod_name}: {message}")
        self.install_progress_bar.setValue(percent)
        # Append a short line to the text area
        self.install_progress_text.append(f"{mod_name}: {message}")

    def _append_install_log(self, message):
        self.install_progress_text.append(message)
        # Auto-scroll to bottom
        cursor = self.install_progress_text.textCursor()
        cursor.movePosition(cursor.End)
        self.install_progress_text.setTextCursor(cursor)

    def _on_install_finished(self, success):
        if success:
            self.install_progress_label.setText("Installation completed!")
            self.install_progress_bar.setValue(100)
            self.modsInstalled.emit()
            # Close the install progress dialog after short pause
            QTimer.singleShot(800, self.install_progress_dialog.accept)
            # Close the install window as well
            QTimer.singleShot(1000, self.accept)
        else:
            self.install_progress_label.setText("Installation finished with errors. See log for details.")
            self.cancel_install_btn.setText("Close")
            self.cancel_install_btn.clicked.disconnect()
            self.cancel_install_btn.clicked.connect(self.install_progress_dialog.accept)

    def install_single_mod(self, mod, version_data, mod_data_list, processed_projects):
        """Install a single mod and return success status"""
        project_id = mod.get("project_id")
        if project_id in processed_projects:
            print(f"Skipping {mod.get('title', 'Unknown')} - already installed")
            return True
        
        files = version_data.get('files', [])
        if not isinstance(files, list) or not files:
            print("No files found in version data.")
            return False
        
        primary_files = [file for file in files if file.get('primary') is True]
        if not primary_files:
            print("No primary files found for version.")
            return False
        
        success_count = 0
        filenames = []
        
        for file in primary_files:
            filename = file.get('filename')
            url = file.get('url')
            if filename and url:
                print(f"Downloading: {filename} from {url}")
                success, downloaded_path = self.download_mod_file(url, filename)
                if success:
                    filenames.append(filename)
                    success_count += 1
                else:
                    print(f"Failed to download {filename}")
        
        if success_count > 0:
            mod_entry = {
                "id": version_data.get("id", 'Unknown'),
                "project_id": project_id,
                "title": mod.get("title", 'Unknown'),
                "description": mod.get("description", ''),
                "author": mod.get("author", "Unknown"),
                "downloads": mod.get("downloads", "Unknown"),
                "version": version_data.get('version_number'),
                "enabled": True,
                "icon_url": mod.get("icon_url", "Default"),
                "filenames": filenames
            }
            mod_data_list.append(mod_entry)
            processed_projects.add(project_id)
            return True
        
        return False

    def download_mod_file(self, download_url, filename):
        """Download the mod file"""
        try:
            GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
            INSTANCE_DIR = os.path.join(GAME_DIR, "instances", self.instance_name)
            MOD_DIR = os.path.join(INSTANCE_DIR, "mods")

            # Ensure mods directory exists
            os.makedirs(MOD_DIR, exist_ok=True)

            # Download to temporary location first
            temp_file_path = os.path.join(MOD_DIR, f".temp_{filename}")
            final_file_path = os.path.join(MOD_DIR, filename)

            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()

            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            os.replace(temp_file_path, final_file_path)
            return True, final_file_path

        except Exception as e:
            print(f"Error downloading mod file: {e}")
            return False, None

    def apply_theme(self, theme_name):
        """Apply the specified theme to all UI elements"""
        if theme_name not in self.themes:
            return
        
        self.current_theme = theme_name
        theme = self.themes[theme_name]
        
        # Apply main window styling
        main_style = f"""
            QDialog {{
                background-color: {theme['background']};
                color: {theme['text']};
            }}
            
            QLabel {{
                color: {theme['text']};
            }}
            
            QPushButton {{
                background-color: {theme['button_bg']};
                color: {theme['text']};
                padding: 8px 16px;
                border-radius: 4px;
            }}
            
            QPushButton:hover {{
                background-color: {theme['button_hover']};
                border: 1px solid {theme['selected_bg']};
            }}
            
            QPushButton:disabled {{
                background-color: {theme['button_bg']};
                color: {theme['text']};
                opacity: 0.5;
            }}
            
            QLineEdit {{
                background-color: {theme['frame_bg']};
                color: {theme['text']};
                border: 1px solid {theme['instance_border']};
                padding: 6px;
                border-radius: 4px;
            }}

            QLineEdit::hover {{
                background-color: {theme['frame_bg']};
                color: {theme['text']};
                border: 1px solid {theme['selected_bg']};
                padding: 6px;
                border-radius: 4px;
            }}

            QFrame {{
                border: none;
            }}
        """
        
        self.setStyleSheet(main_style)
        
        # Update tab widget styling
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar::tab {{
                background: {theme['button_bg']};
                color: {theme['text']};
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {theme['selected_bg']};
                color: white;
            }}
            QTabBar::tab:hover {{
                background: {theme['button_hover']};
            }}
        """)
        
        # Update scroll areas
        scroll_style = f"""
            QScrollArea {{
                background-color: {theme['frame_bg']};
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {theme['frame_bg']};
            }}
            QScrollBar:vertical {{
                background-color: {theme['button_bg']};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme['button_hover']};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {theme['selected_bg']};
            }}
        """
        self.mod_scroll.setStyleSheet(scroll_style)
        self.selected_scroll.setStyleSheet(scroll_style)
        
        # Update the mod container background
        self.mod_container.setStyleSheet(f"""
            QWidget {{
                background-color: {theme['frame_bg']};
            }}
        """)
        
        # Update the selected container background  
        self.selected_container.setStyleSheet(f"""
            QWidget {{
                background-color: {theme['frame_bg']};
                border-radius: 4px
            }}
        """)
        
        # Update details frame
        self.details_frame.setStyleSheet("border: none;")
        
        # Update details description text edit
        self.details_description.setStyleSheet(f"""
            QTextEdit {{
                color: {theme['text']};
                border: none;
                padding: 8px;
            }}
        """)
        
        # Update all mod widgets with new theme
        for widget in self.mod_widgets:
            widget.theme_colors = theme
            widget.update_selection_style()
            # Update icon background
            widget.icon_label.setStyleSheet("border-radius: 4px;")
            # Update text colors
            widget.title_label.setStyleSheet(f"color: {theme['text']}; font-weight: bold; font-size: 14px;")
            widget.desc_label.setStyleSheet(f"color: {theme['text']}; opacity: 0.8;")
        
        # Update all selected mod widgets with new theme
        for widget in self.selected_mod_widgets:
            widget.theme_colors = theme
            widget.setStyleSheet(f"""
                SelectedModWidget {{
                    border: none;
                }}
            """)
            # Update individual elements
            widget.icon_label.setStyleSheet("border-radius: 4px;")
            widget.title_label.setStyleSheet(f"color: {theme['text']}; font-weight: bold; font-size: 13px;")
            widget.info_label.setStyleSheet(f"color: {theme['text']}; opacity: 0.7; font-size: 11px;")
            widget.remove_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme['button_bg']};
                    color: {theme['text']};
                    border: none;
                    border-radius: 12px;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: #ff4444;
                    color: white;
                }}
            """)
        
        # Update other theme-dependent elements
        self.details_title.setStyleSheet(f"color: {theme['text']}; font-weight: bold; font-size: 16px;")
        self.details_author.setStyleSheet(f"color: {theme['text']}; font-size: 12px;")
        self.details_info.setStyleSheet(f"color: {theme['text']}; font-size: 11px;")
        self.selected_count_label.setStyleSheet(f"color: {theme['text']}; font-size: 14px; font-weight: bold;")
        self.empty_label.setStyleSheet(f"""
            color: {theme['text']};
            font-size: 14px;
            opacity: 0.6;
            padding: 40px;
            background-color: {theme['instance_bg']};
        """)

def main():
    """Main function to run the install_mods_window dialog"""
    app = QApplication(sys.argv)
    
    # Create and show the install_mods_window
    window = install_mods_window(theme_colors="dark")  # You can change theme: "creeper", "oled", "dark", "light"
    
    # Show the window
    window.show()
    
    # Run the application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
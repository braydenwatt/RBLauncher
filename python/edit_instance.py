import sys
import os
import shutil
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                           QPushButton, QListWidget, QListWidgetItem, QFrame, 
                           QScrollArea, QWidget, QSizePolicy, QComboBox, 
                           QGridLayout, QCheckBox, QSpacerItem, QFileDialog)
from PyQt5.QtGui import QIcon, QPixmap, QColor, QImage
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer
from PyQt5.QtCore import pyqtSignal

class EditInstanceWindow(QDialog):
    """Dialog window for editing an existing Minecraft instance"""
    instanceUpdated = pyqtSignal(object)
    
    def __init__(self, parent=None, theme_colors=None, instance_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Instance")
        self.setMinimumSize(700, 550)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint)
        
        # Store the instance data
        self.instance_data = instance_data or {}
        print(self.instance_data)
        # Initialize the selected image path
        self.selected_image_path = None
        if instance_data and 'image' in instance_data and instance_data['image']:
            if 'saved_path' in instance_data['image']:
                self.selected_image_path = instance_data['image']['saved_path']
            elif 'original_path' in instance_data['image']:
                self.selected_image_path = instance_data['image']['original_path']
            elif isinstance(instance_data['image'], str):
                self.selected_image_path = instance_data['image']
        
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
            }
        }
        self.current_theme = theme_colors if theme_colors in self.themes else "dark"
        # Create widgets
        self.init_ui()
        
        self.apply_theme(theme_colors)
        self.original_name = ""
        self.populate_instance_data()
        
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
        for btn in [self.vanilla_btn, self.fabric_btn]:
            btn.setStyleSheet(style)
            btn.setCheckable(True)

    def validate_ok_button(self):
        version_selected = self.versions_list.currentItem() is not None
        fallback = self.instance_data['version'] is not None
        print(version_selected or fallback)

        if self.current_section == "Fabric":
            fabric_selected = self.second_versions_list.currentItem() is not None
            fallback_fabric = self.instance_data['fabric_version'] is not None
            self.ok_btn.setEnabled((version_selected or fallback) and (fabric_selected or fallback_fabric))
        else:
            self.ok_btn.setEnabled(version_selected or fallback)

    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)  # Reduced spacing between layout elements
        
        # Name input area with image upload
        name_layout = QHBoxLayout()
        name_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        name_layout.setSpacing(10)  # Keep some spacing between image and name
        
        # Image upload area
        image_layout = QVBoxLayout()
        image_layout.setAlignment(Qt.AlignCenter)
        image_layout.setSpacing(10)  # Reduced spacing between image and button
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
        self.upload_btn.setFixedWidth(80)  # Set a fixed width for the button
        
        # Add to layout with alignment
        image_layout.addWidget(self.image_label, 0, Qt.AlignCenter)
        image_layout.addWidget(self.upload_btn, 0, Qt.AlignCenter)
        
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
        top_layout.setSpacing(5)  # Reduced spacing
        top_layout.addLayout(name_layout)
        
        # Main content area with sidebar and content
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins around content
        
        # Left sidebar
        sidebar_frame = QFrame()
        sidebar_frame.setFrameShape(QFrame.StyledPanel)
        sidebar_frame.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)  # shrink-wrap width and height
        sidebar_frame.setStyleSheet(f"background: {self.themes[self.current_theme]['frame_bg']}; border: none;")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)  # remove outer margins
        sidebar_layout.setSpacing(0)  # no space between buttons
        
        # Create buttons with minimal padding
        self.vanilla_btn = self.create_sidebar_button("Vanilla", ".icons/vanilla.png")
        self.fabric_btn = self.create_sidebar_button("Fabric", ".icons/fabric.png")

        # Make buttons have minimum size policy so they don't expand
        for btn in [self.vanilla_btn, self.fabric_btn]:
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        sidebar_layout.addWidget(self.vanilla_btn)
        sidebar_layout.addWidget(self.fabric_btn)
        sidebar_layout.addStretch(1)

        # Right content area
        content_frame = QFrame()
        content_frame.setFrameShape(QFrame.StyledPanel)
        content_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_frame.setStyleSheet("background: transparent;")
        
        self.content_layout = QVBoxLayout(content_frame)
        self.content_layout.setContentsMargins(5, 0, 0, 0)  # Reduced left margin only
        self.content_layout.setSpacing(5)  # Reduced spacing
        
        # Search bar
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        search_layout.setSpacing(15)  # Reduced spacing
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search and filter...")
        self.search_button = QPushButton("Search")
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_button)
        self.search_button.clicked.connect(self.filter_versions)
        self.search_input.textChanged.connect(self.filter_versions)

        second_search_layout = QHBoxLayout()
        second_search_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        second_search_layout.setSpacing(15)  # Reduced spacing
        self.second_search_input = QLineEdit()
        self.second_search_input.setPlaceholderText("Search and filter...")
        self.second_search_button = QPushButton("Search")
        second_search_layout.addWidget(self.second_search_input, 1)
        second_search_layout.addWidget(self.second_search_button)
        self.second_search_button.clicked.connect(self.filter_fabric_versions)
        self.second_search_input.textChanged.connect(self.filter_fabric_versions)

        # Version list
        style = f"""
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
        
        self.versions_list = QListWidget()
        self.versions_list.setUniformItemSizes(True)
        self.versions_list.setStyleSheet(style)
        
        self.second_versions_list = QListWidget()
        self.second_versions_list.setUniformItemSizes(True)
        self.second_versions_list.setStyleSheet(style)
        
        # Add search bar and version list to content layout
        self.content_layout.addLayout(search_layout)
        self.content_layout.addWidget(self.versions_list, 1)

        self.content_layout.addLayout(second_search_layout)
        self.content_layout.addWidget(self.second_versions_list, 1)
        
        # Add sidebar and content to main content layout
        content_layout.addWidget(sidebar_frame)
        content_layout.addWidget(content_frame, 1)
        
        # Bottom buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)  # Push buttons to the right

        self.cancel_btn = QPushButton("Cancel")
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setDefault(True)
        self.ok_btn.setEnabled(False)

        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addSpacing(10)  # <-- This adds space between Cancel and OK
        buttons_layout.addWidget(self.ok_btn)
        
        # Add all components to main layout
        main_layout.addLayout(top_layout, 0)  # Minimal space for top layout
        main_layout.addLayout(content_layout, 1)  # Give majority of space to content
        main_layout.addLayout(buttons_layout, 0)  # Minimal space for buttons
        
        self.versions_list.itemSelectionChanged.connect(self.validate_ok_button)
        self.second_versions_list.itemSelectionChanged.connect(self.validate_ok_button)

        # Connect signals
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.clicked.connect(self.update_instance)
        self.vanilla_btn.clicked.connect(lambda: self.change_section("Vanilla"))
        self.fabric_btn.clicked.connect(lambda: self.change_section("Fabric"))
        
        # Set default section
        self.current_section = None
        self.validate_ok_button()
        self.initialize_data()

    def initialize_data(self):
        """Initialize data based on instance_data"""
        if not self.instance_data:
            # Default to Vanilla if no data
            self.change_section("Vanilla")
            return
            
        # Figure out which section to select based on instance data
        section = self.instance_data.get('section', self.instance_data.get('modloader', 'Vanilla'))
        self.change_section(section)

    def populate_instance_data(self):
        """Populate fields with existing instance data"""
        if not self.instance_data:
            return
            
        # Set instance name
        if 'name' in self.instance_data:
            self.name_input.setText(self.instance_data['name'])
            self.original_name = self.instance_data['name']
            self.setWindowTitle(f"Edit Instance ({self.original_name})")
            
        # Set image if available
        if self.selected_image_path and os.path.exists(self.selected_image_path):
            pixmap = QPixmap(self.selected_image_path)
            if not pixmap.isNull():
                self.image_label.setPixmap(pixmap)
                self.image_label.setStyleSheet("background-color: transparent; border: none;")
                self.image_label.setFixedSize(80, 80) 
                self.image_label.setScaledContents(True) 
                self.upload_btn.setText("Change")

    def filter_versions(self):
        query = self.search_input.text().lower()
        for i in range(self.versions_list.count()):
            item = self.versions_list.item(i)
            item.setHidden(query not in item.text().lower())

    def filter_fabric_versions(self):
        query = self.second_search_input.text().lower()
        for i in range(self.second_versions_list.count()):
            item = self.second_versions_list.item(i)
            item.setHidden(query not in item.text().lower())
    
    def upload_image(self):
        """Open file dialog to select an image"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, 'Select Instance Image', '', 
            'Image Files (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)'
        )
        
        if file_path:
            # Store the selected image path
            self.selected_image_path = file_path
            
            # Load and display the image
            pixmap = QPixmap(file_path)
            pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
            self.image_label.setStyleSheet("background-color: transparent; border: none;")
            
            # Change button text
            self.upload_btn.setText("Change")
        
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
        
        if icon_path:
            try:
                button.setIcon(QIcon(icon_path))
            except:
                # If icon loading fails, just use text
                pass
                
        return button
        
    def populate_versions(self, version_list):
        self.versions_list.clear()
        for version in version_list:
            self.versions_list.addItem(version)
            
        # Select the current version if it exists
        current_version = self.instance_data.get('version', '')
        if current_version:
            items = self.versions_list.findItems(current_version, Qt.MatchExactly)
            if items:
                items[0].setSelected(True)
                self.versions_list.setCurrentItem(items[0])
                self.validate_ok_button()

    def populate_fabric_versions(self, version_list):
        self.second_versions_list.clear()
        for version in version_list:
            self.second_versions_list.addItem(version)
            
        # Select the current fabric version if it exists
        current_fabric = self.instance_data.get('fabric_version', '')
        print(current_fabric)
        if current_fabric:
            items = self.second_versions_list.findItems(current_fabric, Qt.MatchExactly | Qt.MatchContains)
            if items:
                items[0].setSelected(True)
                self.second_versions_list.setCurrentItem(items[0])
                self.validate_ok_button()

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
                    self.validate_ok_button()
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
                    versions = [f"Fabric {entry['version']}" for entry in data]
                    self.populate_fabric_versions(versions)
                    self.validate_ok_button()
                    QTimer.singleShot(0, lambda: self.populate_fabric_versions(versions))
                except Exception as e:
                    print(f"Failed to fetch Fabric versions: {e}")
            threading.Thread(target=fetch, daemon=True).start()

        # Uncheck all buttons
        for btn in [self.vanilla_btn, self.fabric_btn]:
            btn.setChecked(False)

        self.versions_list.clear()
        self.current_section = section

        if section == "Vanilla":
            self.second_search_input.hide()
            self.second_search_button.hide()
            self.second_versions_list.hide()
            self.vanilla_btn.setChecked(True)
            self.search_input.setPlaceholderText("Search Minecraft versions...")
            fetch_vanilla_versions()
            fetch_fabric_versions()

        elif section == "Fabric":
            self.second_search_input.show()
            self.second_search_button.show()
            self.second_versions_list.show()
            self.fabric_btn.setChecked(True)
            self.search_input.setPlaceholderText("Search Minecraft versions...")
            self.second_search_input.setPlaceholderText("Search Fabric version...")
            fetch_vanilla_versions()
            fetch_fabric_versions()

        self.validate_ok_button()

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
        QPushButton:checked {{
            background-color: {colors['selected_bg']};
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
    
    def update_instance(self):
        data = self.get_instance_data()
        print("Updated instance data:", data)
        
        # If an image was selected, save it to the .icons folder
        if self.selected_image_path:
            # Generate a destination filename based on instance name
            instance_name = self.name_input.text() if self.name_input.text() else self.current_section + " " + self.versions_list.currentItem().text()
            filename = instance_name.lower().replace(" ", "_") + os.path.splitext(self.selected_image_path)[1]
            
            # Ensure the .icons directory exists
            os.makedirs(".icons", exist_ok=True)
            
            # Create the destination path
            destination_path = os.path.join(".icons", filename)
            
            # Copy the image file if it's not already in the .icons directory
            if not self.selected_image_path.startswith(os.path.join(os.getcwd(), ".icons")):
                try:
                    shutil.copy2(self.selected_image_path, destination_path)
                    print(f"Image saved to {destination_path}")
                    # Update the image path in the data
                    data["image"]["saved_path"] = destination_path
                except Exception as e:
                    print(f"Failed to save image: {e}")

        self.instanceUpdated.emit(data)
        self.close()

    def get_instance_data(self):
        """Return the updated data for the instance"""
        original_name = self.original_name

        instance_name = self.name_input.text() if self.name_input.text() else self.current_section + " " + self.versions_list.currentItem().text()
        
        # Create image data
        image_data = {}
        if self.selected_image_path:
            filename = instance_name.lower().replace(" ", "_") + os.path.splitext(self.selected_image_path)[1]
            image_data = {
                "original_path": self.selected_image_path,
                "saved_path": os.path.join(".icons", filename)
            }
        
        # Get selected version data
        minecraft_version = ""
        if self.versions_list.currentItem():
            minecraft_version = self.versions_list.currentItem().text()
        elif self.instance_data['version']:
            minecraft_version = self.instance_data['version']
        
            
        modloader_version = ""
        if self.current_section == "Fabric" and self.second_versions_list.currentItem():
            modloader_version = self.second_versions_list.currentItem().text()
        elif self.instance_data['fabric_version']:
            modloader_version = self.instance_data['fabric_version']
        
        return {
            "original": original_name,
            "name": instance_name,
            "modloader": self.current_section,  # Use modloader field for consistency
            "version": minecraft_version,
            "fabric_version": modloader_version,
            "image": image_data
        }

# For standalone testing
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    
    # Test with some example instance data
    test_data = {
        "name": "My Fabric Instance",
        "modloader": "Fabric",
        "minecraft_version": "1.19.2",
        "modloader_version": "Fabric 0.16.14",
        "image": {
            "original_path": "path/to/image.png",
            "saved_path": ".icons/my_fabric_instance.png"
        }
    }
    
    window = EditInstanceWindow(instance_data=test_data)
    if window.exec_() == QDialog.Accepted:
        print("Instance updated successfully!")
    else:
        print("Edit cancelled")
    
    sys.exit(app.exec_())
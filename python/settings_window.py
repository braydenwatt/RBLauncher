import sys
import os
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QLineEdit, QPushButton, QFrame, QMessageBox, QFileDialog,
                           QGridLayout, QSpacerItem, QSizePolicy)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal
import shutil

class SetWindow(QDialog):
    """Dialog window for application settings"""
    
    settings_updated = pyqtSignal(dict)
    
    def __init__(self, parent=None, theme_colors=None, java_path=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 200)
        
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

        # Store incoming values
        self.initial_java_path = java_path

        # Initialize UI components
        self.init_ui()

        # Set defaults if provided
        if self.initial_java_path:
            self.java_path_edit.setText(self.initial_java_path)

        # Apply theme
        self.current_theme = None
        self.apply_theme(theme_colors if theme_colors else "dark")

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Settings section
        settings_frame = QFrame()
        settings_frame.setFrameShape(QFrame.StyledPanel)
        settings_layout = QGridLayout(settings_frame)

        fixed_height = 30  # Set fixed height for all QLineEdits

        # Java Path field
        settings_layout.addWidget(QLabel("Java Path:"), 0, 0)
        
        java_path_layout = QHBoxLayout()
        self.java_path_edit = QLineEdit()
        self.java_path_edit.setFixedHeight(fixed_height)
        self.java_path_edit.setPlaceholderText("Path to Java executable (java.exe or java)")
        java_path_layout.addWidget(self.java_path_edit)
        
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setFixedHeight(fixed_height)
        self.browse_btn.setMaximumWidth(80)
        self.browse_btn.clicked.connect(self.browse_java_path)
        java_path_layout.addWidget(self.browse_btn)
        
        # Create a widget to contain the layout and add it to the grid
        java_path_widget = QFrame()
        java_path_widget.setLayout(java_path_layout)
        settings_layout.addWidget(java_path_widget, 0, 1)

        # Auto-detect Java button
        self.auto_detect_btn = QPushButton("Auto-detect Java")
        self.auto_detect_btn.setMinimumHeight(35)
        self.auto_detect_btn.clicked.connect(self.auto_detect_java)
        settings_layout.addWidget(self.auto_detect_btn, 1, 0, 1, 2)

        main_layout.addWidget(settings_frame)

        # Add some spacing
        spacer = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addItem(spacer)

        # Button row
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setMinimumHeight(35)
        self.save_btn.clicked.connect(self.save_settings)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(35)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def apply_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            theme = self.themes[theme_name]
            stylesheet = self.build_stylesheet(theme)
            self.setStyleSheet(stylesheet)
            print(f"Applied theme: {theme_name}")
    
    def build_stylesheet(self, colors):
        return f"""
        QDialog {{
            background-color: {colors['background']};
        }}
        QFrame {{
            background-color: {colors['frame_bg']};
            border-radius: 5px;
            padding: 10px;
        }}
        QLabel {{
            color: {colors['text']};
        }}
        QLineEdit {{
            background-color: {colors['instance_bg']};
            color: {colors['text']};
            border: 1px solid {colors['instance_border']};
            border-radius: 3px;
            padding: 5px;
        }}
        QPushButton {{
            background-color: {colors['button_bg']};
            color: {colors['text']};
            border: none;
            border-radius: 3px;
            padding: 8px;
        }}
        QPushButton:hover {{
            background-color: {colors['button_hover']};
        }}
        QPushButton#save_btn {{
            background-color: {colors['selected_bg']};
        }}
        QPushButton#save_btn:hover {{
            background-color: {colors['selected_border']};
        }}
        """

    def browse_java_path(self):
        """Open file dialog to browse for Java executable"""
        current_path = self.java_path_edit.text().strip()
        
        # Determine starting directory
        if current_path and os.path.exists(current_path):
            start_dir = os.path.dirname(current_path)
        else:
            start_dir = os.path.expanduser("~")
        
        # Set filter based on OS
        if sys.platform == "win32":
            file_filter = "Java Executable (java.exe);;All Files (*)"
        else:
            file_filter = "Java Executable (java);;All Files (*)"
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Java Executable",
            start_dir,
            file_filter
        )
        
        if file_path:
            self.java_path_edit.setText(file_path)

    def auto_detect_java(self):
        """Auto-detect Java installation"""
        java_path = shutil.which("java")
        if java_path:
            print(f"Java found at: {java_path}")
            self.java_path_edit.setText(java_path)
            self.java_path = java_path
            QMessageBox.information(
                self, 
                "Java Detected", 
                f"Found Java at: {java_path}"
            )
        else:
            print("Java not found in PATH.")
            QMessageBox.warning(
                self, 
                "Java Not Found", 
                "Could not automatically detect Java installation.\nPlease browse and select java.exe manually."
            )
    
    def validate_java_path(self, path):
        """Validate that the provided path is a valid Java executable"""
        if not path:
            return False, "Java path cannot be empty"
        
        if not os.path.exists(path):
            return False, "Java executable not found at specified path"
        
        if not os.path.isfile(path):
            return False, "Specified path is not a file"
        
        # Check if it's executable (Unix-like systems)
        if not sys.platform == "win32" and not os.access(path, os.X_OK):
            return False, "Java executable does not have execute permissions"
        
        # Basic name validation
        filename = os.path.basename(path).lower()
        if sys.platform == "win32":
            if not filename == "java.exe":
                return False, "On Windows, Java executable should be named 'java.exe'"
        else:
            if not filename == "java":
                return False, "Java executable should be named 'java'"
        
        return True, "Valid Java path"

    def save_settings(self):
        """Save the settings and emit signal"""
        java_path = self.java_path_edit.text().strip()
        
        # Validate Java path if provided
        if java_path:
            is_valid, message = self.validate_java_path(java_path)
            if not is_valid:
                QMessageBox.warning(self, "Invalid Java Path", message)
                return
        
        # Create settings dictionary
        settings_data = {
            'java_path': java_path
        }
        
        # Emit signal for parent window
        self.settings_updated.emit(settings_data)
        
        # Close the dialog
        self.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Test with different themes
    window = SetWindow(theme_colors="dark", java_path="/usr/bin/java")
    window.show()
    
    sys.exit(app.exec_())
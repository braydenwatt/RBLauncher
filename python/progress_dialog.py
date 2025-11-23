import sys
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QTextEdit, QPushButton, QApplication
from PyQt5.QtCore import Qt, pyqtSignal

class ProgressDialog(QDialog):
    """A generic, reusable progress dialog for long-running tasks."""
    cancelled = pyqtSignal()

    def __init__(self, parent=None, title="Processing...", theme_colors=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
        self.setFixedSize(500, 350)
        self.setModal(True)

        self.themes = {
            "dark": {
                "background": "#2D2D2D",
                "text": "#FFFFFF",
                "button_bg": "#3D3D3D",
                "button_hover": "#4D4D4D",
                "frame_bg": "#222222",
            },
            "light": {
                "background": "#F5F5F5",
                "text": "#3B3B3B",
                "button_bg": "#E0E0E0",
                "button_hover": "#D5D5D5",
                "frame_bg": "#FFFFFF",
            },
        }
        self.current_theme = theme_colors if theme_colors in self.themes else "dark"
        
        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Starting...")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate
        layout.addWidget(self.progress_bar)

        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        layout.addWidget(self.log_viewer)

        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.cancel_button.clicked.connect(self.on_cancel)

    def apply_theme(self):
        theme = self.themes[self.current_theme]
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme['background']};
                color: {theme['text']};
            }}
            QLabel {{ color: {theme['text']}; }}
            QTextEdit {{ 
                background-color: {theme['frame_bg']}; 
                color: {theme['text']}; 
                border: 1px solid {theme['button_bg']}; 
                font-family: "Menlo", "Consolas", monospace;
            }}
            QPushButton {{ 
                background-color: {theme['button_bg']}; 
                color: {theme['text']}; 
                padding: 6px 12px; 
                border-radius: 4px; 
            }}
            QPushButton:hover {{ background-color: {theme['button_hover']}; }}
        """)

    def on_cancel(self):
        self.status_label.setText("Cancelling...")
        self.cancel_button.setEnabled(False)
        self.cancelled.emit()

    def append_log(self, text):
        self.log_viewer.append(text)
        # Auto-scroll to bottom
        cursor = self.log_viewer.textCursor()
        cursor.movePosition(cursor.End)
        self.log_viewer.setTextCursor(cursor)

    def set_status(self, text):
        self.status_label.setText(text)

    def close_dialog(self, success=True):
        if success:
            self.set_status("Finished!")
            self.progress_bar.setRange(0,100)
            self.progress_bar.setValue(100)
        else:
            self.set_status("Finished with errors.")
        
        self.cancel_button.setText("Close")
        self.cancel_button.setEnabled(True)
        self.cancel_button.clicked.disconnect()
        self.cancel_button.clicked.connect(self.accept)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    dialog = ProgressDialog(title="Testing Progress", theme_colors="dark")
    dialog.show()
    dialog.append_log("Doing something...")
    dialog.append_log("Doing something else...")
    sys.exit(app.exec_())

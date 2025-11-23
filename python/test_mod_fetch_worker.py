#!/usr/bin/env python3
"""Test script for ModFetchWorker to demonstrate progress dialog functionality."""

import sys
from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt5.QtCore import Qt
from add_instance_window import ModFetchWorker
from progress_dialog import ProgressDialog

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ModFetchWorker Test")
        self.setGeometry(200, 200, 300, 200)
        
        layout = QVBoxLayout(self)
        
        self.info_label = QLabel("Click the button to test ModFetchWorker with progress dialog")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        self.test_btn = QPushButton("Test Mod Fetching")
        self.test_btn.clicked.connect(self.test_mod_fetching)
        layout.addWidget(self.test_btn)
        
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        
    def test_mod_fetching(self):
        """Test the mod fetching process with a small sample of mods."""
        # Sample mod list (smaller version for testing)
        test_mod_list = [
            {'project_id': 'P7dR8mSH', 'version_id': 'dQ3p80zK', 'dependency_type': 'embedded'},  # Fabric API
            {'project_id': 'NNAgCjsB', 'version_id': 'YkqoVa13', 'dependency_type': 'embedded'},  # Entity Culling  
            {'project_id': '3IuO68q1', 'version_id': '9EpmlvYD', 'dependency_type': 'embedded'},  # Puzzle
        ]
        
        self.result_label.setText("Starting mod fetch test...")
        
        # Create and show progress dialog
        progress_dialog = ProgressDialog(
            parent=self,
            title="Testing Mod Information Fetch",
            theme_colors="dark"
        )
        progress_dialog.set_status(f"Preparing to fetch information for {len(test_mod_list)} mods...")
        progress_dialog.progress_bar.setRange(0, len(test_mod_list))
        progress_dialog.progress_bar.setValue(0)
        
        # Create and configure worker
        self.mod_fetch_worker = ModFetchWorker(test_mod_list)
        
        def on_progress(current, total, mod_name):
            progress_dialog.progress_bar.setValue(current)
            progress_dialog.set_status(f"Processing mod {current}/{total}: {mod_name}")
        
        def on_log_update(message):
            progress_dialog.append_log(message)
        
        def on_finished(mods_info):
            progress_dialog.close_dialog(success=True)
            self.result_label.setText(f"Successfully fetched {len(mods_info)} mods!")
        
        def on_error(error_msg):
            progress_dialog.append_log(f"ERROR: {error_msg}")
            progress_dialog.set_status("Error occurred during mod fetching")
        
        def on_cancel():
            progress_dialog.set_status("Cancelling...")
            self.mod_fetch_worker.stop()
            self.result_label.setText("Mod fetching was cancelled")
        
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Set a dark theme similar to the launcher
    app.setStyleSheet("""
        QWidget {
            background-color: #2D2D2D;
            color: #FFFFFF;
        }
        QPushButton {
            background-color: #3D3D3D;
            border: 1px solid #4D4D4D;
            padding: 8px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #4D4D4D;
        }
    """)
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec_())
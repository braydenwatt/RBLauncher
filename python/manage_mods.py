import sys
import os
import threading
import requests
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                           QPushButton, QListWidget, QListWidgetItem, QFrame, 
                           QScrollArea, QWidget, QSizePolicy, QComboBox, 
                           QGridLayout, QCheckBox, QSpacerItem, QFileDialog,
                           QTextEdit, QSplitter, QApplication, QMenu, QAction,
                           QMessageBox)
from PyQt5.QtGui import QIcon, QPixmap, QColor, QImage, QPainter
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer, QUrl
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
import json

from PyQt5.QtWidgets import QPushButton
from PyQt5.QtCore import QSize
from install_mods_window import install_mods_window
import threading
import requests
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractButton
from PyQt5.QtCore import Qt, QPropertyAnimation, QRectF, pyqtProperty
from PyQt5.QtGui import QColor, QPainter, QBrush

class ModUpdater(QObject):
    """Worker class for downloading and updating mods"""
    
    progressUpdate = pyqtSignal(str, str, int)  # mod_name, status, progress
    updateComplete = pyqtSignal(str, bool, str)  # mod_name, success, message
    finished = pyqtSignal()
    modNameUpdated = pyqtSignal(str, dict, str)
    
    def __init__(self, mod_widgets, instance_name, mc_version, loader):
        super().__init__()
        self.mod_widgets = mod_widgets
        self.instance_name = instance_name
        self.mc_version = mc_version
        self.loader = loader.lower() if loader else ""
        self._should_stop = False
        
    def stop(self):
        """Request the worker to stop"""
        self._should_stop = True
        
    def update_mods(self):
        """Update all provided mods"""
        try:
            for widget in self.mod_widgets:
                if self._should_stop:
                    break
                    
                mod_data = widget.mod_data
                mod_name = mod_data.get('title', 'Unknown Mod')
                
                # Skip mods without project ID or updates
                project_id = mod_data.get('project_id', '')
                if not project_id or str(project_id).lower() in ['unknown', '', 'none', 'null']:
                    self.updateComplete.emit(mod_name, False, "Unknown project ID")
                    continue
                    
                if not widget.has_update:
                    self.updateComplete.emit(mod_name, False, "No updates available")
                    continue
                
                self.progressUpdate.emit(mod_name, "Fetching latest version info...", 10)
                
                # Get the latest version info
                success, download_url, filename, new_version = self.get_latest_version_info(project_id)
                if not success:
                    self.updateComplete.emit(mod_name, False, "Failed to get version info")
                    continue
                
                if self._should_stop:
                    break
                
                self.progressUpdate.emit(mod_name, f"Downloading v{new_version}...", 30)
                
                # Download the new version
                success, file_path = self.download_mod_file(download_url, filename)
                if not success:
                    self.updateComplete.emit(mod_name, False, "Failed to download")
                    continue
                
                if self._should_stop:
                    break
                
                self.progressUpdate.emit(mod_name, "Installing update...", 80)
                
                # Replace the old file(s) with the new one
                success, message = self.replace_mod_files(mod_data, file_path, filename, new_version)
                
                self.progressUpdate.emit(mod_name, "Complete", 100)
                self.updateComplete.emit(mod_name, success, message)
                
        except Exception as e:
            print(f"Error in mod updater: {e}")
        finally:
            self.finished.emit()
    
    def get_latest_version_info(self, project_id):
        """Get download info for the latest version"""
        try:
            url = f"https://api.modrinth.com/v2/project/{project_id}/version"
            params = {}
            if self.mc_version:
                params['game_versions[]'] = self.mc_version
            if self.loader:
                params['loaders[]'] = self.loader
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return False, None, None, None
            
            versions = response.json()
            if not versions:
                return False, None, None, None
            
            # Filter versions strictly
            filtered_versions = [
                v for v in versions
                if self.mc_version in v["game_versions"] and self.loader in v["loaders"]
            ]
            
            if not filtered_versions:
                return False, None, None, None
            
            latest_version = filtered_versions[0]
            
            # Get the primary download file
            files = latest_version.get('files', [])
            if not files:
                return False, None, None, None
            
            # Find the primary file or the first one
            primary_file = None
            for file_info in files:
                if file_info.get('primary', False):
                    primary_file = file_info
                    break
            
            if not primary_file:
                primary_file = files[0]  # Use first file if no primary found
            
            download_url = primary_file.get('url')
            filename = primary_file.get('filename')
            version_number = latest_version.get('version_number')
            
            if not download_url or not filename:
                return False, None, None, None
            
            return True, download_url, filename, version_number
            
        except Exception as e:
            print(f"Error getting version info: {e}")
            return False, None, None, None
    
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
            
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(temp_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._should_stop:
                        try:
                            os.remove(temp_file_path)
                        except:
                            pass
                        return False, None
                    
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Update progress
                    if total_size > 0:
                        progress = 30 + int((downloaded / total_size) * 50)  # 30-80% range
                        # We can't emit signals here easily, so we'll keep it simple
            
            return True, temp_file_path
            
        except Exception as e:
            print(f"Error downloading mod file: {e}")
            return False, None
    
    def replace_mod_files(self, mod_data, new_file_path, new_filename, new_version):
        """Replace old mod files with the new one"""
        try:
            GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
            INSTANCE_DIR = os.path.join(GAME_DIR, "instances", self.instance_name)
            MOD_DIR = os.path.join(INSTANCE_DIR, "mods")
            
            old_filenames = mod_data.get('filenames', [])
            
            # Remove old files
            for old_filename in old_filenames:
                old_file_path = os.path.join(MOD_DIR, old_filename)
                if os.path.exists(old_file_path):
                    try:
                        os.remove(old_file_path)
                        print(f"Removed old file: {old_filename}")
                    except Exception as e:
                        print(f"Warning: Could not remove old file {old_filename}: {e}")
            
            # Move new file to final location
            final_file_path = os.path.join(MOD_DIR, new_filename)
            os.rename(new_file_path, final_file_path)
            
            # Update mod data
            mod_data['filenames'] = [new_filename]
            mod_data['version'] = new_version

            print(mod_data)

            self.modNameUpdated.emit(self.instance_name, mod_data, mod_data['id'])
            
            return True, f"Updated to v{new_version}"
            
        except Exception as e:
            print(f"Error replacing mod files: {e}")
            # Clean up temp file if it exists
            try:
                if os.path.exists(new_file_path):
                    os.remove(new_file_path)
            except:
                pass
            return False, f"Installation failed: {str(e)}"
        
class AnimatedToggle(QAbstractButton):
    def __init__(self, parent=None, theme_colors=None):
        super().__init__(parent)
        self.setCheckable(True)
        self._offset = 0.0
        self._thumb_radius = 10
        self.theme_colors = theme_colors or {
            "toggle_on": "#2ecc71",
            "toggle_off": "#555",
            "thumb": "#000000"
        }

        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(200)
        self.toggled.connect(self._start_animation)
        self.setFixedSize(50, 28)

    def _start_animation(self, checked):
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background
        bg_color = QColor(self.theme_colors['selected_bg'] if self.isChecked() else self.theme_colors['icon_bg'])
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), self.height() / 2, self.height() / 2)

        # Thumb (circle)
        thumb_color = QColor(self.theme_colors['text'])
        thumb_x = self._offset * (self.width() - 2 * self._thumb_radius - 8) + 4
        thumb_y = (self.height() - 2 * self._thumb_radius) / 2
        painter.setBrush(QBrush(thumb_color))
        painter.drawEllipse(QRectF(thumb_x, thumb_y, 2 * self._thumb_radius, 2 * self._thumb_radius))

    def sizeHint(self):
        return self.size()

    def get_offset(self):
        return self._offset

    def set_offset(self, value):
        self._offset = value
        self.update()

    offset = pyqtProperty(float, fget=get_offset, fset=set_offset)

class UpdateChecker(QObject):
    """Worker class for checking mod updates in a separate thread"""
    
    updateCheckComplete = pyqtSignal(bool, str)  # has_update, latest_version
    finished = pyqtSignal()
    
    def __init__(self, project_id, current_version, mc_version, loader):
        super().__init__()
        self.project_id = project_id
        self.current_version = current_version
        self.mc_version = mc_version
        self.loader = loader.lower() if loader else ""
        self._should_stop = False
        
    def stop(self):
        """Request the worker to stop"""
        self._should_stop = True
        
    def check_for_updates(self):
        """Check if mod has updates available"""
        try:
            if self._should_stop:
                return
                
            if not self.project_id or str(self.project_id).lower() in ['unknown', '', 'none', 'null']:
                self.updateCheckComplete.emit(False, "")
                self.finished.emit()
                return
                
            # Get all versions for the project
            url = f"https://api.modrinth.com/v2/project/{self.project_id}/version"
            
            # Add query parameters to filter by game version and loader
            params = {}
            print(self.mc_version)
            if self.mc_version:
                params['game_versions[]'] = self.mc_version
            if self.loader:
                params['loaders[]'] = self.loader
            
            if self._should_stop:
                return
                
            response = requests.get(url, params=params, timeout=10)
            print("Full request URL:", response.request.url)

            if self._should_stop:
                return
                
            if response.status_code != 200:
                print(f"Failed to fetch versions: {response.status_code}")
                self.updateCheckComplete.emit(False, "")
                self.finished.emit()
                return
                
            versions = response.json()
            all_versions = response.json()

            # Strictly filter only versions matching both game version and loader
            filtered_versions = [
                v for v in all_versions
                if self.mc_version in v["game_versions"] and self.loader in v["loaders"]
            ]

            if filtered_versions:
                latest = filtered_versions[0]
                print("Strict latest version:", latest["version_number"])
            else:
                print("No strictly matching versions found.")

            if not versions:
                print("No compatible versions found")
                self.updateCheckComplete.emit(False, "")
                self.finished.emit()
                return
                
            if self._should_stop:
                return
                
            # Get the latest version (first in the list, as they're sorted by date)
            latest_version = latest
            latest_version_number = latest_version['version_number']
            
            print(f"Current version: {self.current_version}, Latest version: {latest_version_number}")
            
            # Check if update is available
            has_update = self.current_version != latest_version_number
            
            if not self._should_stop:
                self.updateCheckComplete.emit(has_update, latest_version_number)
            
        except requests.RequestException as e:
            if not self._should_stop:
                print(f"Network error while checking for updates: {e}")
                self.updateCheckComplete.emit(False, "")
        except Exception as e:
            if not self._should_stop:
                print(f"Error checking for updates: {e}")
                self.updateCheckComplete.emit(False, "")
        finally:
            self.finished.emit()

class ModWidget(QWidget):
    """Custom widget for displaying a mod in the list with inline options"""
    
    modToggled = pyqtSignal(object)  # Signal when mod is toggled
    modSelected = pyqtSignal(object, bool)  # Signal when mod selection changes
    modUpdateRequested = pyqtSignal(object)  # Signal when update is requested
    modRemoveRequested = pyqtSignal(object)  # Signal when remove is requested
    nameUpdated = pyqtSignal(str, dict, str)
    
    def __init__(self, mod_data, theme_colors, is_manage_mode=True, selected_instance="", version="", loader=""):
        super().__init__()
        self.mod_data = mod_data
        self.theme_colors = theme_colors
        self.is_manage_mode = is_manage_mode
        self.selected_instance_name = selected_instance
        self.mc_version = version
        self.loader = loader
        self.selected = False
        self.enabled = mod_data.get('enabled', True)
        
        # Update checking variables
        self.has_update = False
        self.latest_version = ""
        self.update_checker = None
        self.update_thread = None
        self._is_destroyed = False
        
        self.init_ui()
        
        # Start update check after UI is initialized
        QTimer.singleShot(100, self.start_update_check)
        
    def init_ui(self):
        # Set fixed height to prevent stretching
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        self.select_checkbox = QCheckBox()
        self.select_checkbox.toggled.connect(self.on_selection_changed)
        layout.addWidget(self.select_checkbox, 0, Qt.AlignVCenter)
        self.select_checkbox.setToolTip("Select Mod")
        
        # Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setStyleSheet(f"background-color: {self.theme_colors['icon_bg']}; border-radius: 4px;")
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # Load icon if available
        if self.mod_data.get('icon_url'):
            self.load_icon()
        else:
            # Default icon
            pixmap = QPixmap(48, 48)
            pixmap.fill(QColor(self.theme_colors['icon_bg']))
            self.icon_label.setPixmap(pixmap)
        
        layout.addWidget(self.icon_label, alignment=Qt.AlignVCenter)
        
        # Content (title and description)
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title with version
        title_text = self.mod_data.get('title', 'Unknown Mod')
        version = self.mod_data.get('version', '')
        if version and version != "Unknown":
            title_text += f" ({version})"
        
        self.title_label = QLabel(title_text)
        self.title_label.setStyleSheet(f"color: {self.theme_colors['text']}; font-weight: bold; font-size: 14px;")
        self.title_label.setWordWrap(True)
        
        # Author and description on second line
        description = self.mod_data.get('description', '')
        if len(description) > 160:
            description = description[:160] + "..."
        
        info_text = description
        self.info_label = QLabel(info_text)
        self.info_label.setStyleSheet(f"color: {self.theme_colors['text']}; opacity: 0.8; font-size: 12px;")
        self.info_label.setWordWrap(True)
        
        content_layout.addWidget(self.title_label)
        content_layout.addWidget(self.info_label)
        content_layout.addStretch()
        
        layout.addLayout(content_layout, 1)
        
        # Action buttons (rightmost)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        # Toggle button (Enable/Disable)
        self.toggle_btn = AnimatedToggle(theme_colors=self.theme_colors)
        self.toggle_btn.setChecked(self.enabled)
        self.toggle_btn.toggled.connect(self.toggle_enabled)
        self.toggle_btn.setToolTip("Disable Mod" if self.enabled else "Enable Mod")
        layout.addWidget(self.toggle_btn, 0, Qt.AlignVCenter)

        # Update button - initially disabled while checking
        self.update_btn = QPushButton()
        self.update_btn.setIconSize(QSize(20, 20))
        self.update_btn.setFixedSize(20, 20)
        self.update_btn.setFlat(True)
        self.update_btn.setEnabled(False)  # Disabled until update check completes
        self.update_btn.setToolTip("Checking for updates...")
        self.update_btn.clicked.connect(self.request_update)
        self.update_btn.setStyleSheet("border: none;")
        
        # Remove button
        self.remove_btn = QPushButton()
        self.remove_btn.setIcon(self.load_colored_svg_icon(".icons/delete.svg"))
        self.remove_btn.setIconSize(QSize(20, 20))
        self.remove_btn.setFixedSize(20, 20)
        self.remove_btn.setFlat(True)
        self.remove_btn.setToolTip("Remove")  
        self.remove_btn.clicked.connect(self.request_remove)
        self.remove_btn.setStyleSheet("border: none;")
        
        actions_layout.addWidget(self.toggle_btn)
        actions_layout.addSpacing(6)
        actions_layout.addWidget(self.update_btn)
        actions_layout.addSpacing(6)
        actions_layout.addWidget(self.remove_btn)
        actions_layout.addSpacing(6)
        
        layout.addLayout(actions_layout)
        
        # Apply initial visual state based on enabled status
        self.update_disabled_visual_state()
        self.update_selection_style()

    def update_disabled_visual_state(self):
        """Update the visual appearance based on enabled/disabled state"""
        if not self.enabled:
            # Disabled state - add strikethrough
            
            # Update title with strikethrough
            title_text = self.mod_data.get('title', 'Unknown Mod')
            version = self.mod_data.get('version', '')
            if version and version != "Unknown":
                title_text += f" (v{version})"
            
            # Apply strikethrough style
            strikethrough_style = f"""
                color: {self.theme_colors['text']}; 
                font-weight: bold; 
                font-size: 14px;
                text-decoration: line-through;
                opacity: 0.6;
            """
            self.title_label.setStyleSheet(strikethrough_style)
            
            # Update description with reduced opacity
            self.info_label.setStyleSheet(f"color: {self.theme_colors['text']}; opacity: 0.4; font-size: 12px;")
            
        else:
            # Enabled state - normal appearance
            
            # Update title without strikethrough
            title_text = self.mod_data.get('title', 'Unknown Mod')
            version = self.mod_data.get('version', '')
            if version and version != "Unknown":
                title_text += f" (v{version})"
            
            normal_style = f"""
                color: {self.theme_colors['text']}; 
                font-weight: bold; 
                font-size: 14px;
            """
            self.title_label.setStyleSheet(normal_style)
            
            # Restore normal description opacity
            self.info_label.setStyleSheet(f"color: {self.theme_colors['text']}; opacity: 0.8; font-size: 12px;")

    def load_colored_svg_icon(self, file_path, base_size=1024, use_gray=False):
        import re
        from PyQt5.QtSvg import QSvgRenderer
        from PyQt5.QtGui import QPixmap, QPainter, QIcon
        from PyQt5.QtCore import Qt

        # Use gray color if specified, otherwise use theme text color
        color = "#808080" if use_gray else self.theme_colors['text']

        try:
            with open(file_path, 'r') as f:
                svg_content = f.read()

            # Replace fill="#xxxxxx"
            svg_content = re.sub(r'fill="#[0-9a-fA-F]{6}"', f'fill="{color}"', svg_content)

            # Replace fill: rgb(...) with fill="{color}"
            svg_content = re.sub(
                r'style="fill:\s*rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)\s*;"',
                f'fill="{color}"',
                svg_content
            )

            # Render at high resolution
            svg_renderer = QSvgRenderer(bytearray(svg_content, encoding='utf-8'))
            pixmap = QPixmap(base_size, base_size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()

            return QIcon(pixmap)
        except Exception as e:
            print(f"Error loading SVG icon {file_path}: {e}")
            return QIcon()

    def start_update_check(self):
        """Start the update checking process in a separate thread"""
        if self._is_destroyed:
            return
            
        project_id = self.mod_data.get('project_id', '')
        current_version = self.mod_data.get('version', '')
        
        # Only check for updates if we have necessary information
        if not project_id or str(project_id).lower() in ['unknown', '', 'none', 'null']:
            self.on_update_check_complete(False, "")
            return
            
        if not current_version or current_version.lower() in ['unknown', '', 'none', 'null']:
            self.on_update_check_complete(False, "")
            return
        
        # Clean up any existing thread
        self.cleanup_update_thread()
        
        # Create thread and worker
        self.update_thread = QThread()
        self.update_checker = UpdateChecker(
            project_id=project_id,
            current_version=current_version,
            mc_version=self.mc_version,
            loader=self.loader
        )
        
        # Move worker to thread
        self.update_checker.moveToThread(self.update_thread)
        
        # Connect signals - use lambda to ensure we don't have lingering connections
        self.update_thread.started.connect(self.update_checker.check_for_updates)
        self.update_checker.updateCheckComplete.connect(self.on_update_check_complete)
        self.update_checker.finished.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self.cleanup_update_thread)
        
        # Start the thread
        self.update_thread.start()

    def cleanup_update_thread(self):
        """Safely clean up the update checking thread"""
        if self.update_checker:
            self.update_checker.stop()
            
        if self.update_thread and self.update_thread.isRunning():
            self.update_thread.quit()
            # Wait for thread to finish, but not indefinitely
            if not self.update_thread.wait(3000):  # 3 second timeout
                print("Warning: Update thread did not finish cleanly")
                self.update_thread.terminate()
                self.update_thread.wait(1000)  # Wait 1 more second after terminate
        
        # Clean up references
        if self.update_thread:
            self.update_thread.deleteLater()
            self.update_thread = None
        if self.update_checker:
            self.update_checker.deleteLater()
            self.update_checker = None

    def on_update_check_complete(self, has_update, latest_version):
        """Handle the completion of update checking"""
        if self._is_destroyed:
            return
            
        self.has_update = has_update
        self.latest_version = latest_version
        
        # Update the button based on results
        project_id = self.mod_data.get('project_id', '')
        has_project_id = bool(project_id and str(project_id).lower() not in ['unknown', '', 'none', 'null'])
        
        if not has_project_id:
            # No project ID available
            self.update_btn.setIcon(self.load_colored_svg_icon(".icons/refresh.svg", use_gray=True))
            self.update_btn.setEnabled(False)
            self.update_btn.setToolTip("Update unavailable (Unknown project ID)")
        elif has_update:
            # Update available
            self.update_btn.setIcon(self.load_colored_svg_icon(".icons/refresh.svg", use_gray=False))
            self.update_btn.setEnabled(True)
            tooltip = f"Update available (v{latest_version})" if latest_version else "Update available"
            self.update_btn.setToolTip(tooltip)
        else:
            # No update available
            self.update_btn.setIcon(self.load_colored_svg_icon(".icons/refresh.svg", use_gray=True))
            self.update_btn.setEnabled(False)
            self.update_btn.setToolTip("No updates available (Latest version)")

    
    def refresh_widget(self):
        """Refresh the toggle display and animate if needed."""
        new_enabled = self.mod_data.get('enabled', True)
        
        # Block signals to prevent triggering toggle_enabled during refresh
        self.toggle_btn.blockSignals(True)
        
        if new_enabled != self.toggle_btn.isChecked():
            self.toggle_btn.setChecked(new_enabled)
            # Manually trigger animation since signals are blocked
            self.toggle_btn._start_animation(new_enabled)
        else:
            # Even if the state is the same, trigger animation explicitly
            self.toggle_btn._start_animation(new_enabled)
        
        # Re-enable signals
        self.toggle_btn.blockSignals(False)

        self.toggle_btn.setToolTip("Disable Mod" if new_enabled else "Enable Mod")
        
        # Update visual state when refreshing
        self.enabled = new_enabled
        self.update_disabled_visual_state()

    def get_action_button_style(self):
        """Get the style for action buttons"""
        return f"""
            QPushButton {{
                background-color: {self.theme_colors['button_bg']};
                color: {self.theme_colors['text']};
                border: 1px solid {self.theme_colors['button_bg']};
                border-radius: 3px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {self.theme_colors['button_hover']};
                border: 1px solid {self.theme_colors['selected_border']};
            }}
            QPushButton:pressed {{
                background-color: {self.theme_colors['selected_bg']};
            }}
        """

    def get_remove_button_style(self):
        """Get the style for remove button (red)"""
        return f"""
            QPushButton {{
                background-color: #D32F2F;
                color: white;
                border: 1px solid #D32F2F;
                border-radius: 3px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #B71C1C;
                border: 1px solid #B71C1C;
            }}
            QPushButton:pressed {{
                background-color: #8D1313;
            }}
        """
        
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

    def on_selection_changed(self, checked):
        """Handle selection checkbox change"""
        self.selected = checked
        self.update_selection_style()
        self.modSelected.emit(self, checked)

    def set_selected(self, selected):
        """Set selection state programmatically"""
        self.select_checkbox.setChecked(selected)
        self.selected = selected
        self.update_selection_style()

    def toggle_enabled(self):
        """Toggle mod enabled state based on first filename only"""
        filenames = self.mod_data['filenames']
        if not filenames:
            print("No filenames to toggle.")
            return

        print("Toggling filenames:", filenames)

        GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
        INSTANCE_DIR = os.path.join(GAME_DIR, "instances", self.selected_instance_name)
        MOD_DIR = os.path.join(INSTANCE_DIR, "mods")

        target_enabled = not self.enabled  # Desired new state

        first_filename = filenames[0]
        original_path = os.path.join(MOD_DIR, first_filename)

        # Determine new filename based on desired state
        if target_enabled:
            # Enable: remove '.disabled' if present
            if first_filename.endswith(".disabled"):
                new_name = first_filename[:-9]  # Remove ".disabled"
            else:
                new_name = first_filename
        else:
            # Disable: add '.disabled' if not already present
            if not first_filename.endswith(".disabled"):
                new_name = first_filename + ".disabled"
            else:
                new_name = first_filename

        new_path = os.path.join(MOD_DIR, new_name)

        if original_path == new_path:
            # No rename needed, just update state and filenames accordingly
            print("No rename needed for first filename.")
        else:
            # Try renaming the first file
            try:
                os.rename(original_path, new_path)
                print(f"Renamed {first_filename} -> {new_name}")
            except Exception as e:
                print(f"Failed to rename {first_filename}: {e}")
                print("Toggle aborted due to rename failure.")
                return

        # Build new filenames list updating only the first filename
        new_filenames = filenames.copy()
        new_filenames[0] = new_name

        self.enabled = target_enabled
        self.mod_data['enabled'] = self.enabled
        self.mod_data['filenames'] = new_filenames

        if self.mod_data['id'] != "Unknown":
            self.nameUpdated.emit(self.selected_instance_name, self.mod_data, self.mod_data['id'])

        # Update label if id is 'Unknown'
        if self.mod_data['id'] == 'Unknown':
            self.title_label.setText(new_name)

        # Update toggle button tooltip
        self.toggle_btn.setToolTip("Disable Mod" if self.enabled else "Enable Mod")
        
        # Update visual appearance based on new enabled state
        self.update_disabled_visual_state()
        self.update_selection_style()
        self.modToggled.emit(self)

    def request_update(self):
        """Request update for this mod"""
        self.modUpdateRequested.emit(self)
    
    def update_title_after_update(self):
        """Update the title label after a successful mod update"""
        title_text = self.mod_data.get('title', 'Unknown Mod')
        version = self.mod_data.get('version', '')
        if version and version != "Unknown":
            title_text += f" (v{version})"
        
        self.title_label.setText(title_text)
        
        # Reset update status since we just updated
        self.has_update = False
        self.on_update_check_complete(False, "")

    def request_remove(self):
        """Request removal of this mod"""
        self.modRemoveRequested.emit(self)
        
    def update_selection_style(self):
        """Update widget styling based on selection and enabled state"""
        if self.selected:
            self.setStyleSheet(f"""
                ModWidget {{
                    background-color: {self.theme_colors['selected_bg']};
                    border: 1px solid {self.theme_colors['selected_border']};
                    border-radius: 4px;
                }}
            """)
        elif not self.enabled:
            # Disabled mod styling
            self.setStyleSheet(f"""
                ModWidget {{
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    opacity: 0.5;
                }}
                ModWidget:hover {{
                    background-color: {self.theme_colors['button_hover']};
                    border: 1px solid {self.theme_colors['instance_border']};
                    opacity: 0.7;
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

    def closeEvent(self, event):
        """Handle widget close event"""
        self._is_destroyed = True
        self.cleanup_update_thread()
        if hasattr(self, 'update_worker') and self.update_worker:
            self.update_worker.stop()
    
        # Clean up mod widgets
        for widget in self.mod_widgets:
            if widget is not None:
                widget.cleanup_update_thread()
        
        super().closeEvent(event)
        
    def __del__(self):
        """Clean up threads when widget is destroyed"""
        self._is_destroyed = True
        self.cleanup_update_thread()

class manage_modsWindow(QDialog):
    """Dialog window for managing existing mods in a Minecraft instance"""
    modsUpdated = pyqtSignal(str, list)
    nameUpdated = pyqtSignal(str, dict, str)
    modsInstalled = pyqtSignal()

    def __init__(self, parent=None, theme_colors=None, mod_data=None, instance_data=None, selected_name="", version="", loader=""):
        super().__init__(parent)
        self.setWindowTitle(f"Manage Mods For {selected_name}")
        self.setMinimumSize(800, 600)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinMaxButtonsHint)
        
        # Store instance and mod data
        self.instance_data = instance_data or {}
        self.mod_data = mod_data or []
        self.mod_widgets = []
        self.selected_mods = set()  # Track selected mods
        self.changes_made = False
        self.selected_instance_name = selected_name
        self.mc_version = version
        self.loader = loader
        
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
                "toggle_on": "#007AFF",      
                "toggle_off": "#555555", 
                "thumb": "#000000"
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
        self.populate_mods()
        
    def init_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Top bar with search
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(15)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search installed mods...")
        self.search_input.textChanged.connect(self.filter_mods)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.filter_mods)
        
        # Install mods button
        self.install_btn = QPushButton("Install Mods")
        self.install_btn.clicked.connect(self.open_install_window)
        
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_btn)
        search_layout.addWidget(self.install_btn)
        
        # Bulk action buttons
        bulk_layout = QHBoxLayout()
        bulk_layout.setContentsMargins(0, 0, 0, 0)
        bulk_layout.setSpacing(10)
        
        # Selection buttons
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_mods)
        
        self.select_none_btn = QPushButton("Deselect All")
        self.select_none_btn.clicked.connect(self.select_no_mods)
        
        self.update_selected_btn = QPushButton("Update Selected")
        self.update_selected_btn.clicked.connect(self.update_selected_mods)
        
        self.toggle_selected_btn = QPushButton("Toggle Selected")
        self.toggle_selected_btn.clicked.connect(self.toggle_selected_mods)
        
        self.remove_selected_btn = QPushButton("Remove Selected")
        self.remove_selected_btn.clicked.connect(self.remove_selected_mods)

        self.folder_btn = QPushButton("Open Mod Folder")
        self.folder_btn.clicked.connect(self.open_mod_folder)
        
        bulk_layout.addWidget(self.select_all_btn)
        bulk_layout.addWidget(QFrame())
        bulk_layout.addWidget(self.select_none_btn)
        bulk_layout.addWidget(QFrame())  # Separator
        bulk_layout.addWidget(self.update_selected_btn)
        bulk_layout.addWidget(QFrame())  # Separator
        bulk_layout.addWidget(self.toggle_selected_btn)
        bulk_layout.addWidget(QFrame())  # Separator
        bulk_layout.addWidget(self.remove_selected_btn)
        bulk_layout.addStretch()
        bulk_layout.addWidget(self.folder_btn)
        
        # Main content area - single column layout
        content_frame = QFrame()
        content_frame.setFrameShape(QFrame.StyledPanel)
        content_frame.setStyleSheet(f"background: {self.themes[self.current_theme]['frame_bg']}; border: none;")
        
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(5)
        
        # Mod list scroll area
        self.mod_scroll = QScrollArea()
        self.mod_scroll.setWidgetResizable(True)
        self.mod_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {self.themes[self.current_theme]['frame_bg']};
                border: none;
            }}
        """)
        
        self.mod_container = QWidget()
        self.mod_layout = QVBoxLayout(self.mod_container)
        self.mod_layout.setSpacing(2)
        self.mod_layout.setContentsMargins(5, 5, 5, 5)
        self.mod_scroll.setWidget(self.mod_container)
        
        content_layout.addWidget(self.mod_scroll, 1)
        self.install_window = None
        # Bottom buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch(1)
        
        self.cancel_btn = QPushButton("Cancel")
        self.apply_btn = QPushButton("OK")
        self.apply_btn.setDefault(True)
        self.apply_btn.setEnabled(False)
        
        buttons_layout.addWidget(self.cancel_btn)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.apply_btn)
        
        # Add all components to main layout
        main_layout.addLayout(search_layout, 0)
        main_layout.addLayout(bulk_layout, 0)
        main_layout.addWidget(content_frame, 1)
        main_layout.addLayout(buttons_layout, 0)
        
        # Connect signals
        self.cancel_btn.clicked.connect(self.reject)
        self.apply_btn.clicked.connect(self.apply_changes)
        
        # Update bulk button states
        self.update_bulk_button_states()
    
    def open_mod_folder(self):
        import subprocess

        GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
        INSTANCE_DIR = os.path.join(GAME_DIR, "instances", self.selected_instance_name)
        MOD_DIR = os.path.join(INSTANCE_DIR, "mods")

        subprocess.run(["open", MOD_DIR])

    def on_mod_update_requested(self, widget):
        """Handle update request for single mod"""
        if not widget.has_update:
            QMessageBox.information(self, "No Update", "This mod is already up to date.")
            return
        
        # Start update process for single mod
        self.start_mod_updates([widget])

    def update_selected_mods(self):
        """Update selected mods"""
        if not self.selected_mods:
            QMessageBox.information(self, "No Selection", "Please select mods to update.")
            return
        
        # Filter only mods that have updates available
        mods_with_updates = [widget for widget in self.selected_mods if widget.has_update]
        
        if not mods_with_updates:
            QMessageBox.information(self, "No Updates", "None of the selected mods have updates available.")
            return
        
        # Start update process for selected mods
        self.start_mod_updates(mods_with_updates)

    def start_mod_updates(self, mod_widgets):
        """Start the mod update process"""
        # Create progress dialog
        self.update_progress_dialog = QDialog(self)
        self.update_progress_dialog.setWindowTitle("Updating Mods")
        self.update_progress_dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)
        self.update_progress_dialog.setFixedSize(400, 200)
        self.update_progress_dialog.setModal(True)
        
        layout = QVBoxLayout(self.update_progress_dialog)
        
        self.progress_label = QLabel("Preparing to update mods...")
        layout.addWidget(self.progress_label)
        
        self.progress_text = QTextEdit()
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setReadOnly(True)
        layout.addWidget(self.progress_text)
        
        button_layout = QHBoxLayout()
        self.cancel_update_btn = QPushButton("Cancel")
        self.cancel_update_btn.clicked.connect(self.cancel_mod_updates)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_update_btn)
        layout.addLayout(button_layout)
        
        # Apply theme to progress dialog
        self.update_progress_dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {self.themes[self.current_theme]['background']};
                color: {self.themes[self.current_theme]['text']};
            }}
            QLabel {{
                color: {self.themes[self.current_theme]['text']};
            }}
            QTextEdit {{
                background-color: {self.themes[self.current_theme]['frame_bg']};
                color: {self.themes[self.current_theme]['text']};
                border: 1px solid {self.themes[self.current_theme]['button_bg']};
            }}
            QPushButton {{
                background-color: {self.themes[self.current_theme]['button_bg']};
                color: {self.themes[self.current_theme]['text']};
                border: 1px solid {self.themes[self.current_theme]['button_bg']};
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {self.themes[self.current_theme]['button_hover']};
            }}
        """)
        
        # Create and start update worker
        self.update_thread = QThread()
        self.update_worker = ModUpdater(
            mod_widgets=mod_widgets,
            instance_name=self.selected_instance_name,
            mc_version=self.mc_version,
            loader=self.loader
        )

        self.update_worker.modNameUpdated.connect(self.emit_name_change)
        
        # Move worker to thread
        self.update_worker.moveToThread(self.update_thread)
        
        # Connect signals
        self.update_thread.started.connect(self.update_worker.update_mods)
        self.update_worker.progressUpdate.connect(self.on_update_progress)
        self.update_worker.updateComplete.connect(self.on_mod_update_complete)
        self.update_worker.finished.connect(self.on_all_updates_finished)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self.cleanup_update_worker)
        
        # Show progress dialog and start updates
        self.update_progress_dialog.show()
        self.update_thread.start()

    def on_update_progress(self, mod_name, status, progress):
        """Handle update progress updates"""
        self.progress_label.setText(f"Updating: {mod_name}")
        self.progress_text.append(f"{mod_name}: {status}")
        
        # Auto-scroll to bottom
        cursor = self.progress_text.textCursor()
        cursor.movePosition(cursor.End)
        self.progress_text.setTextCursor(cursor)

    def on_mod_update_complete(self, mod_name, success, message):
        """Handle completion of individual mod update"""
        if success:
            self.progress_text.append(f"✓ {mod_name}: {message}")
            # Find and update the corresponding widget
            for widget in self.mod_widgets:
                if widget.mod_data.get('title', 'Unknown Mod') == mod_name:
                    widget.update_title_after_update()
                    break
            self.mark_changes_made()
        else:
            self.progress_text.append(f"✗ {mod_name}: {message}")
        
        # Auto-scroll to bottom
        cursor = self.progress_text.textCursor()
        cursor.movePosition(cursor.End)
        self.progress_text.setTextCursor(cursor)

    def on_all_updates_finished(self):
        """Handle completion of all mod updates"""
        self.progress_label.setText("Updates completed!")
        self.cancel_update_btn.setText("Close")
        self.cancel_update_btn.clicked.disconnect()
        self.cancel_update_btn.clicked.connect(self.update_progress_dialog.close)

    def cancel_mod_updates(self):
        """Cancel the mod update process"""
        if hasattr(self, 'update_worker') and self.update_worker:
            self.update_worker.stop()
        
        if hasattr(self, 'update_progress_dialog'):
            self.update_progress_dialog.close()

    def cleanup_update_worker(self):
        """Clean up the update worker and thread"""
        if hasattr(self, 'update_worker') and self.update_worker:
            self.update_worker.deleteLater()
            self.update_worker = None
        
        if hasattr(self, 'update_thread') and self.update_thread:
            self.update_thread.deleteLater()
            self.update_thread = None
            
    def populate_mods(self):
        """Populate the mod list with widgets"""
        # Clear existing widgets
        for widget in self.mod_widgets:
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.mod_widgets.clear()
        self.selected_mods.clear()
        
        # Add mod widgets
        for mod in self.mod_data:
            widget = ModWidget(mod, self.themes[self.current_theme], is_manage_mode=True, selected_instance=self.selected_instance_name, version=self.mc_version, loader=self.loader)
            widget.nameUpdated.connect(self.emit_name_change)

            # Connect signals
            widget.modToggled.connect(self.on_mod_toggled)
            widget.modSelected.connect(self.on_mod_selected)
            widget.modUpdateRequested.connect(self.on_mod_update_requested)
            widget.modRemoveRequested.connect(self.on_mod_remove_requested)
            
            self.mod_widgets.append(widget)
            self.mod_layout.addWidget(widget)
        
        # Add spacer at the bottom
        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.mod_layout.addItem(spacer)
        
        self.update_bulk_button_states()
        print(f"Populated {len(self.mod_data)} mods")
    
    def emit_name_change(self, instance_name, new_mod_data, mod_name):
        print(mod_name)
        self.nameUpdated.emit(instance_name, new_mod_data, mod_name)

    def on_mod_toggled(self, widget):
        """Handle mod toggle"""
        self.mark_changes_made()
    
    def on_mod_selected(self, widget, selected):
        """Handle mod selection change"""
        if selected:
            self.selected_mods.add(widget)
        else:
            self.selected_mods.discard(widget)
        
        self.update_bulk_button_states()
    
    def on_mod_remove_requested(self, widget):
        """Handle remove request for single mod"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Remove Mod")
        msg_box.setText(f"Are you sure you want to remove '{widget.mod_data.get('title', 'Unknown Mod')}'?")
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)

        # Apply custom stylesheet
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

        if reply == QMessageBox.Yes:
            self.remove_mod(widget)

    
    def remove_mod(self, widget):
        """Remove a specific mod"""
        mod_id = widget.mod_data.get('id')
        filenames = widget.mod_data.get('filenames', [])
        print("Removing filenames:", filenames)

        GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
        INSTANCE_DIR = os.path.join(GAME_DIR, "instances", self.selected_instance_name)
        MOD_DIR = os.path.join(INSTANCE_DIR, "mods")

        for filename in filenames:
            file_path = os.path.join(MOD_DIR, filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
            else:
                print(f"File not found: {file_path}")

        # Update in-memory mod_data
        self.mod_data = [mod for mod in self.mod_data if mod.get('id') != mod_id]

        # Emit signal if not a manual mod
        if mod_id != "Unknown":
            self.modsUpdated.emit(self.selected_instance_name, self.mod_data)

        # GUI cleanup
        self.selected_mods.discard(widget)
        widget.setParent(None)
        widget.deleteLater()
        self.mod_widgets.remove(widget)

        self.mark_changes_made()
        self.update_bulk_button_states()


    
    def select_all_mods(self):
        """Select all mods"""
        for widget in self.mod_widgets:
            if widget.isVisible():
                widget.set_selected(True)
    
    def select_no_mods(self):
        """Deselect all mods"""
        for widget in self.mod_widgets:
            widget.set_selected(False)
  
    def toggle_selected_mods(self):
        """Toggle selected mods"""
        if not self.selected_mods:
            QMessageBox.information(self, "No Selection", "Please select mods to toggle.")
            return
        
        print("Refreshing")

        for widget in self.selected_mods:
            widget.toggle_enabled()
            widget.refresh_widget()
    
    def remove_selected_mods(self):
        """Remove selected mods"""
        if not self.selected_mods:
            QMessageBox.information(self, "No Selection", "Please select mods to remove.")
            return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Delete Instance")
        msg_box.setText(f"Are you sure you want to remove {len(self.selected_mods)} selected mods?")
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
        if reply == QMessageBox.Yes:
            # Create a copy of the set to avoid modification during iteration
            mods_to_remove = list(self.selected_mods)
            for widget in mods_to_remove:
                self.remove_mod(widget)
    
    def update_bulk_button_states(self):
        """Update the enabled state of bulk action buttons"""
        has_selection = len(self.selected_mods) > 0
        has_mods = len(self.mod_widgets) > 0
        
        self.update_selected_btn.setEnabled(has_selection)
        self.toggle_selected_btn.setEnabled(has_selection)
        self.remove_selected_btn.setEnabled(has_selection)

        self.select_all_btn.setEnabled(has_mods)
        self.select_none_btn.setEnabled(has_selection)
    
    def mark_changes_made(self):
        """Mark that changes have been made"""
        self.changes_made = True
        self.apply_btn.setEnabled(True)
    
    def filter_mods(self):
        """Filter mods based on search input"""
        query = self.search_input.text().lower().strip()
        
        for widget in self.mod_widgets:
            title_match = query in widget.mod_data.get('title', '').lower()
            desc_match = query in widget.mod_data.get('description', '').lower()
            author_match = query in widget.mod_data.get('author', '').lower()
            
            should_show = not query or title_match or desc_match or author_match
            widget.setVisible(should_show)
        
        self.update_bulk_button_states()
    
    def refresh_mods(self):
        """Refresh the mod list by re-reading mod data and repopulating widgets"""
        self.modsInstalled.emit()
        
        print("Mod list refreshed successfully")

    def open_install_window(self):
        """Open the install mods window"""
        if self.install_window is None or not self.install_window.isVisible():
            self.install_window = install_mods_window(theme_colors=self.current_theme, instance_name=self.selected_instance_name)
            
            self.install_window.modsInstalled.connect(self.refresh_mods)

            self.install_window.show()
        else:
            self.install_window.raise_()
            self.install_window.activateWindow()
    
    def apply_changes(self):
        """Apply the mod changes and close dialog"""
        self.accept()
    
    def apply_theme(self, theme_name):
        """Apply the specified theme"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            theme = self.themes[theme_name]
            stylesheet = self.build_stylesheet(theme)
            self.setStyleSheet(stylesheet)
            self.apply_input_styles()
            self.apply_button_styles()
    
    def build_stylesheet(self, colors):
        """Build the main stylesheet"""
        return f"""
        manage_modsWindow {{
            background-color: {colors['background']};
        }}
        QLabel {{
            color: {colors['text']};
        }}
        """
    
    def apply_input_styles(self):
        """Apply styles to input widgets"""
        if not self.current_theme:
            return
        theme = self.themes[self.current_theme]
        
        line_edit_style = f"""
            QLineEdit {{
                background-color: {theme['frame_bg']};
                color: {theme['text']};
                border: 1px solid {theme['button_bg']};
                padding: 6px 8px;
                border-radius: 3px;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme['selected_border']};
                background-color: {theme['instance_bg']};
            }}
        """
        
        self.search_input.setStyleSheet(line_edit_style)
    
    def apply_button_styles(self):
        """Apply styles to buttons"""
        if not self.current_theme:
            return
        theme = self.themes[self.current_theme]
        
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
                color: white;
            }}
            QPushButton:disabled {{
                background-color: #222222;
                border: 1px solid transparent;
                color: #888888;
            }}
        """
        
        # Apply to all buttons except the remove selected button (which has custom styling)
        buttons = [
            self.search_btn, self.install_btn, self.select_all_btn, self.select_none_btn,
            self.update_selected_btn, self.remove_selected_btn, self.folder_btn,
            self.toggle_selected_btn, self.cancel_btn, self.apply_btn
        ]
        
        for button in buttons:
            button.setStyleSheet(button_style)

# For standalone testing
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Mock mod data for testing
    mock_mods = [
        {
            'id': 'mod1',
            'title': 'JEI (Just Enough Items)',
            'description': 'JEI is an item and recipe viewing mod for Minecraft, built from the ground up for stability and performance.',
            'downloads': 150000000,
            'version': '11.4.0.297',
            'enabled': True,
            'icon_url': None,
            'filenames': ['justenoughitems.jar']
        },
        {
            'id': 'mod2', 
            'title': 'Optifine',
            'description': 'OptiFine is a Minecraft optimization mod. It allows Minecraft to run faster and look better with full support for HD textures.',
            'downloads': 200000000,
            'version': '1.19.2_HD_U_H9',
            'enabled': True,
            'icon_url': None,
            'filenames': ['optifine.jar']
        },
        {
            'id': 'mod3',
            'title': 'Iron Chests',
            'description': 'A mod that adds a variety of new chests with different properties to Minecraft.',
            'downloads': 50000000,
            'version': '14.4.4',
            'enabled': False,
            'icon_url': None,
            'filenames': ['ironchests.jar']
        }
    ]
    
    window = manage_modsWindow(mod_data=mock_mods, theme_colors="dark")
    window.show()
    
    sys.exit(app.exec_())
import sys
import threading
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
from PyQt5.QtWidgets import (QToolButton, QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QLineEdit, QPushButton, QFrame, QMessageBox, QTextEdit,
                           QGridLayout, QSpacerItem, QSizePolicy)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QSize


class AuthWorker(QThread):
    """Worker thread to handle authentication without freezing the UI"""
    update_status = pyqtSignal(str)
    auth_success = pyqtSignal(dict)
    auth_failure = pyqtSignal(str)
    
    def __init__(self, auth_code):
        super().__init__()
        self.auth_code = auth_code
        
    def run(self):
        self.update_status.emit("2/5 Exchanging code for Microsoft access token…")
        token = self.get_token(self.auth_code)
        if not token:
            self.auth_failure.emit("Failed to get Microsoft Access Token!")
            return
            
        self.update_status.emit("3/5 Authenticating with Xbox Live…")
        xbl = self.auth_xbl(token)
        if not xbl['Token']:
            self.auth_failure.emit("Failed to authenticate with Xbox Live!")
            return
            
        self.update_status.emit("4/5 Authenticating with XSTS…")
        xsts = self.auth_xsts(xbl['Token'], xbl['uhs'])
        if not xsts['Token']:
            self.auth_failure.emit("Failed to authenticate with XSTS!")
            return
            
        self.update_status.emit("5/5 Getting Minecraft access token…")
        mc_access_token = self.get_minecraft_access_token(xsts['Token'], xsts['uhs'])
        if not mc_access_token:
            self.auth_failure.emit("Failed to get Minecraft Access Token!")
            return
            
        self.update_status.emit("✅ Minecraft Access Token obtained successfully!")
        
        # Check game ownership and get profile
        has_game = self.check_game_ownership(mc_access_token)
        if not has_game:
            self.auth_failure.emit("You do not own Minecraft: Java Edition.")
            return
            
        profile = self.get_profile_info(mc_access_token)
        if not profile['UUID'] or not profile['name']:
            self.auth_failure.emit("Failed to get profile information.")
            return
        
        # Return all data
        auth_data = {
            'username': profile['name'],
            'uuid': profile['UUID'],
            'access_token': mc_access_token
        }
        self.auth_success.emit(auth_data)
        
    def get_token(self, code):
        try:
            response = requests.post('https://login.live.com/oauth20_token.srf', data={
                "client_id": "00000000402b5328",
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": "https://login.live.com/oauth20_desktop.srf",
                "scope": "service::user.auth.xboxlive.com::MBI_SSL"
            })
            json_data = response.json()
            if response.status_code == 200 and 'access_token' in json_data:
                return json_data['access_token']
        except Exception as e:
            self.update_status.emit(f"Error getting token: {e}")
        return None

    def auth_xbl(self, access_token):
        try:
            response = requests.post('https://user.auth.xboxlive.com/user/authenticate', json={
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": access_token
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT"
            })
            json_data = response.json()
            if response.status_code == 200 and 'Token' in json_data:
                return {
                    'Token': json_data['Token'],
                    'uhs': json_data['DisplayClaims']['xui'][0]['uhs']
                }
        except Exception as e:
            self.update_status.emit(f"Error authenticating with XBL: {e}")
        return {'Token': None, 'uhs': None}

    def auth_xsts(self, xbl_token, uhs):
        try:
            response = requests.post('https://xsts.auth.xboxlive.com/xsts/authorize', json={
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [xbl_token]
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT"
            })
            json_data = response.json()
            if response.status_code == 200 and 'Token' in json_data:
                new_uhs = json_data['DisplayClaims']['xui'][0]['uhs']
                if uhs == new_uhs:
                    return {
                        'Token': json_data['Token'],
                        'uhs': new_uhs
                    }
        except Exception as e:
            self.update_status.emit(f"Error authenticating with XSTS: {e}")
        return {'Token': None, 'uhs': None}

    def get_minecraft_access_token(self, token, uhs):
        try:
            response = requests.post('https://api.minecraftservices.com/authentication/login_with_xbox', json={
                "identityToken": f"XBL3.0 x={uhs};{token}"
            })
            json_data = response.json()
            if response.status_code == 200 and 'access_token' in json_data:
                return json_data['access_token']
        except Exception as e:
            self.update_status.emit(f"Error getting Minecraft access token: {e}")
        return None

    def get_profile_info(self, access_token):
        try:
            response = requests.get('https://api.minecraftservices.com/minecraft/profile', headers={
                'Authorization': f'Bearer {access_token}'
            })
            json_data = response.json()
            if response.status_code == 200 and 'id' in json_data and 'name' in json_data:
                return {'UUID': json_data['id'], 'name': json_data['name']}
        except Exception as e:
            self.update_status.emit(f"Error getting profile info: {e}")
        return {'UUID': None, 'name': None}

    def check_game_ownership(self, access_token):
        try:
            response = requests.get('https://api.minecraftservices.com/entitlements/mcstore', headers={
                'Authorization': f'Bearer {access_token}'
            })
            json_data = response.json()
            if response.status_code == 200 and 'items' in json_data:
                return len(json_data['items']) > 0
        except Exception as e:
            self.update_status.emit(f"Error checking game ownership: {e}")
        return False


class UrlInputDialog(QDialog):
    """Dialog to get the redirected URL from the user after Microsoft login"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Microsoft Authentication")
        self.setMinimumSize(600, 150)
        self.result_code = None
        
        layout = QVBoxLayout()
        
        # Instruction label
        label = QLabel("After logging in, you will be redirected to a URL.\nPaste the full redirected URL here:")
        layout.addWidget(label)
        label.setStyleSheet("background: transparent")

        # URL input field
        self.url_input = QLineEdit()
        self.url_input.setMinimumWidth(550)
        layout.addWidget(self.url_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.submit_btn = QPushButton("Submit")
        self.cancel_btn = QPushButton("Cancel")
        
        self.submit_btn.clicked.connect(self.submit_url)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.submit_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def submit_url(self):
        redirect_url = self.url_input.text().strip()
        parsed = urlparse(redirect_url)
        
        if parsed.hostname == 'login.live.com' and parsed.path == '/oauth20_desktop.srf':
            query = parse_qs(parsed.query)
            if 'code' in query and 'error' not in query:
                self.result_code = query['code'][0]
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Invalid URL: No authorization code found")
        else:
            QMessageBox.critical(self, "Error", "Invalid URL: Not a valid Microsoft redirect")


class AccountWindow(QDialog):
    """Dialog window for Minecraft account authentication"""
    
    account_updated = pyqtSignal(dict)
    
    def __init__(self, parent=None, theme_colors=None, username=None, uuid=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Account")
        self.setMinimumSize(600, 325)
        
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
        self.initial_username = username
        self.initial_uuid = uuid

        print(uuid)
        # Initialize UI components
        self.init_ui()

        # Set defaults if provided
        if self.initial_username:
            self.username_edit.setText(self.initial_username)
        if self.initial_uuid:
            self.uuid_edit.setText(self.initial_uuid)

        # Apply theme
        self.current_theme = None
        self.apply_theme(theme_colors if theme_colors else "dark")


    def init_ui(self):
        main_layout = QVBoxLayout()
        print(self.size())
        # Account details section
        details_frame = QFrame()
        details_frame.setFrameShape(QFrame.StyledPanel)
        details_layout = QGridLayout(details_frame)

        fixed_height = 30  # Set fixed height for all QLineEdits

        # Username field
        details_layout.addWidget(QLabel("Username:"), 0, 0)
        self.username_edit = QLineEdit()
        self.username_edit.setReadOnly(True)
        self.username_edit.setFixedHeight(fixed_height)
        details_layout.addWidget(self.username_edit, 0, 1)

        # UUID field
        details_layout.addWidget(QLabel("UUID:"), 1, 0)
        self.uuid_edit = QLineEdit()
        self.uuid_edit.setReadOnly(True)
        self.uuid_edit.setFixedHeight(fixed_height)
        details_layout.addWidget(self.uuid_edit, 1, 1)

        # Access Token field
        details_layout.addWidget(QLabel("Access Token:"), 2, 0)
        self.token_edit = QLineEdit()
        self.token_edit.setReadOnly(True)
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setFixedHeight(fixed_height)
        details_layout.addWidget(self.token_edit, 2, 1)

        main_layout.addWidget(details_frame)

        # Login button
        self.login_btn = QPushButton("Login with Microsoft")
        self.login_btn.setMinimumHeight(40)
        self.login_btn.clicked.connect(self.start_microsoft_auth)
        main_layout.addWidget(self.login_btn)

        # Toggle Output button
        self.toggle_output_btn = QToolButton()
        self.toggle_output_btn.setText("Show Output")
        self.toggle_output_btn.setCheckable(True)
        self.toggle_output_btn.setChecked(False)
        self.toggle_output_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.toggle_output_btn.clicked.connect(self.toggle_status_output)
        main_layout.addWidget(self.toggle_output_btn)

        # Status output
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(150)
        self.output_text.setVisible(False)  # Hide by default
        main_layout.addWidget(self.output_text)

        # Button row
        button_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def toggle_status_output(self):
        show = self.toggle_output_btn.isChecked()
        self.output_text.setVisible(show)
        self.toggle_output_btn.setText("Hide Output" if show else "Show Output")
        self.adjustSize()  # Resize the window based on new content


    def apply_theme(self, theme_name):
        if theme_name in self.themes:
            self.current_theme = theme_name
            theme = self.themes[theme_name]
            stylesheet = self.build_stylesheet(theme)
            self.setStyleSheet(stylesheet)
            self.toggle_output_btn.setStyleSheet(f"""
                QToolButton {{
                    border: 1px solid {theme['selected_bg']};
                    border-radius: 4px;
                    padding: 6px 12px;
                    background-color: none;
                    color: {theme['text']}
                }}
                QToolButton:checked {{
                    background-color: {theme['selected_bg']};
                    color: white;
                }}
                """)
            print(f"Applied theme: {theme_name}")
    
    def build_stylesheet(self, colors):
        return f"""
        QDialog {{
            background-color: {colors['background']};
        }}
        QFrame {{
            background-color: {colors['frame_bg']};
            border-radius: 5px;
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
        QTextEdit {{
            background-color: {colors['instance_bg']};
            color: {colors['text']};
            border: 1px solid {colors['instance_border']};
            border-radius: 3px;
        }}
        """
    
    def append_output(self, text):
        """Add text to the output console"""
        self.output_text.append(text)
        # Scroll to the bottom
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def start_microsoft_auth(self):
        """Start the Microsoft authentication process"""
        self.append_output("Starting Microsoft authentication process...")
        self.append_output("1/5 Opening the login page in your browser...")
        
        # Open the Microsoft login page
        auth_url = (
            'https://login.live.com/oauth20_authorize.srf?client_id=00000000402b5328'
            '&response_type=code&scope=service%3A%3Auser.auth.xboxlive.com%3A%3AMBI_SSL'
            '&redirect_uri=https%3A%2F%2Flogin.live.com%2Foauth20_desktop.srf'
        )
        webbrowser.open(auth_url)
        
        # Show URL input dialog
        url_dialog = UrlInputDialog(self)
        if url_dialog.exec_() == QDialog.Accepted and url_dialog.result_code:
            self.start_auth_process(url_dialog.result_code)
        else:
            self.append_output("❌ Authentication cancelled or failed.")
    
    def start_auth_process(self, auth_code):
        """Continue authentication with the obtained code"""
        # Create worker thread
        self.auth_worker = AuthWorker(auth_code)
        self.auth_worker.update_status.connect(self.append_output)
        self.auth_worker.auth_success.connect(self.on_auth_success)
        self.auth_worker.auth_failure.connect(self.on_auth_failure)
        self.auth_worker.start()
    
    def on_auth_success(self, auth_data):
        """Handle successful authentication"""
        # Update UI fields
        self.username_edit.setText(auth_data['username'])
        self.uuid_edit.setText(auth_data['uuid'])
        self.token_edit.setText(auth_data['access_token'])
        
        # Output success message
        self.append_output(f"\n✅ Authentication complete!")
        self.append_output(f"Username: {auth_data['username']}")
        self.append_output(f"UUID: {auth_data['uuid']}")
        
        # Emit signal for parent window
        self.account_updated.emit(auth_data)
    
    def on_auth_failure(self, error_message):
        """Handle authentication failure"""
        self.append_output(f"❌ {error_message}")
        QMessageBox.warning(self, "Authentication Failed", error_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = AccountWindow()
    window.show()
    
    sys.exit(app.exec_())
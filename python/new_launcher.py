import sys
import os
import json
import shutil
import subprocess
import threading
import re
import time
import webbrowser
import requests
import zipfile
import urllib.request
from urllib.parse import urlparse, parse_qs, urljoin

# PyQt5 Imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QListWidget, QListWidgetItem, QFrame,
    QStackedWidget, QLineEdit, QMessageBox, QSizePolicy, QDialog,
    QStackedLayout, QProgressBar, QScrollArea, QGridLayout, QFileDialog, 
    QCheckBox, QProgressDialog
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QFont, QColor, QPainter, QPainterPath
)
from PyQt5.QtCore import (
    Qt, QSize, QTimer, pyqtSignal, QThread, QPoint, QEvent, 
    QUrl, QByteArray, QObject, QEventLoop
)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtNetwork import (
    QNetworkAccessManager, QNetworkRequest, QNetworkReply
)
# ================= GLOBAL CONSTANTS =================
CONFIG_PATH = os.path.expanduser(
    "~/Library/Application Support/ReallyBadLauncher/config.json"
)
GAME_DIR = os.path.expanduser("~/Library/Application Support/ReallyBadLauncher")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
ICONS_DIR = os.path.join(PROJECT_DIR, ".icons")
APP_ICON_PATH = os.path.join(ICONS_DIR, "rbldawn.png") 
APP_ICON_PATH2 = os.path.join(ICONS_DIR, "icon.png") 
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)


class WizardCard(QPushButton):
    """A large selectable card (custom vs modpack) with SVG support."""
    def __init__(self, icon_path, title, subtitle, value, parent=None):
        super().__init__(parent)
        self.value = value
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(140)
        self.setObjectName("WizardCard")
        
        # Layout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)
        
        # Icon (Pixmap)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(40, 40)
        self.icon_lbl.setStyleSheet("background: transparent; border: none;")
        self.icon_lbl.setScaledContents(True)
        
        # Load Icon
        # Load Icon
        if icon_path and os.path.exists(icon_path) and icon_path.lower().endswith(".svg"):
            icon = self.load_svg_icon(icon_path, size=40, color="#ffffff")
            self.icon_lbl.setPixmap(icon.pixmap(40, 40))
        elif os.path.exists(icon_path):
            pm = QPixmap(icon_path)
            if not pm.isNull():
                self.icon_lbl.setPixmap(pm)
        else:
            self.icon_lbl.setText("?")

        
        # Title
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; background: transparent; border: none; color: white;")
        
        # Subtitle
        self.sub_lbl = QLabel(subtitle)
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setStyleSheet("font-size: 13px; color: #a1a1aa; background: transparent; border: none;")
        
        lay.addWidget(self.icon_lbl)
        lay.addWidget(self.title_lbl)
        lay.addWidget(self.sub_lbl)
        lay.addStretch()

    def load_svg_icon(self, path: str, size: int = 18, color: str = "#ffffff") -> QIcon:
        if not path or not os.path.exists(path):
            return QIcon()

        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()

        svg = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', f'fill="{color}"', svg)
        svg = re.sub(r'fill="[^"]+"', f'fill="{color}"', svg)
        svg = re.sub(r'stroke="#[0-9a-fA-F]{3,6}"', f'stroke="{color}"', svg)
        svg = re.sub(r'stroke="[^"]+"', f'stroke="{color}"', svg)

        renderer = QSvgRenderer(bytearray(svg, encoding="utf-8"))

        dpr = QApplication.instance().devicePixelRatio()
        px = int(size * dpr)

        pixmap = QPixmap(px, px)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        pixmap.setDevicePixelRatio(dpr)  # 🔥 critical line

        return QIcon(pixmap)
# ================= WORKERS (Ported from old code) =================

class ApiWorker(QThread):
    """Generic worker for fetching JSON from APIs"""
    data_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, mode, query=None):
        super().__init__()
        self.mode = mode
        self.query = query

    def run(self):
        try:
            if self.mode == "vanilla":
                url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
                data = requests.get(url).json()
                # Return ALL versions (release + snapshot)
                # We will filter them in the UI
                self.data_ready.emit(data["versions"])
            
            elif self.mode == "fabric":
                url = "https://meta.fabricmc.net/v2/versions/loader"
                data = requests.get(url).json()
                # Just get loader versions
                versions = [v["version"] for v in data]
                self.data_ready.emit(versions)

            elif self.mode == "modpack_search":
                url = "https://api.modrinth.com/v2/search"
                params = {
                    'facets': '[["project_type:modpack"]]',
                    'limit': 20,
                    'query': self.query or ""
                }
                data = requests.get(url, params=params).json()
                hits = data.get("hits", [])
                results = []
                for h in hits:
                    results.append({
                        "id": h.get("project_id"),
                        "title": h.get("title"),
                        "desc": h.get("description"),
                        "author": h.get("author"),
                        "icon_url": h.get("icon_url"),
                        "downloads": h.get("downloads"),
                        "versions": h.get("versions", []) # Note: search doesn't return full version list usually
                    })
                self.data_ready.emit(results)
                
            elif self.mode == "modpack_versions":
                # query is project_id
                url = f"https://api.modrinth.com/v2/project/{self.query}/version"
                data = requests.get(url).json()
                self.data_ready.emit(data)

        except Exception as e:
            self.error.emit(str(e))

# ================= NEW INSTANCE WIZARD PAGE =================

class NewInstancePage(QWidget):
    created = pyqtSignal(dict) # Emits the final instance data
    cancelled = pyqtSignal()   # Emits when user wants to go back to home

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NewInstancePage")
        
        # State
        self.step = 1
        self.instance_type = "custom" 
        self.selected_image_path = None  # <--- NEW: Store file path
        
        self.data = {
            "name": "",
            "version": None,
            "loader": "vanilla",
            "loader_version": None,
            "modpack_info": None,
            "modpack_version_id": None
        }
        self.modpack_results = []
        
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 1. Header (Gradient Bar) ---
        self.header = QFrame()
        self.header.setObjectName("WizardHeader")
        hl = QVBoxLayout(self.header)
        hl.setContentsMargins(28, 20, 28, 20)
        self.title_lbl = QLabel("Create New Instance")
        self.title_lbl.setObjectName("WizardTitle")
        self.subtitle_lbl = QLabel("Step 1 of 3")
        self.subtitle_lbl.setObjectName("WizardSubtitle")
        hl.addWidget(self.title_lbl)
        hl.addWidget(self.subtitle_lbl)
        main_layout.addWidget(self.header)

        # --- 2. Progress Bar (Thin) ---
        self.progress_container = QFrame()
        self.progress_container.setObjectName("ProgressContainer")
        pl = QHBoxLayout(self.progress_container)
        pl.setContentsMargins(28, 0, 28, 0)
        pl.setSpacing(4)
        self.progress_bars = []
        for i in range(3):
            bar = QFrame()
            bar.setFixedHeight(4)
            bar.setObjectName("ProgressBarInactive")
            self.progress_bars.append(bar)
            pl.addWidget(bar)
        main_layout.addWidget(self.progress_container)

        # --- 3. Content Area (Stacked) ---
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        # Step 1: Type & Name
        self.page_step1 = self.build_step_1()
        self.stack.addWidget(self.page_step1)

        # Step 2: Custom (Game Version)
        self.page_step2_custom = self.build_step_2_custom()
        self.stack.addWidget(self.page_step2_custom)
        
        # Step 2: Modpack (Search)
        self.page_step2_modpack = self.build_step_2_modpack()
        self.stack.addWidget(self.page_step2_modpack)

        # Step 3: Custom (Loader)
        self.page_step3_custom = self.build_step_3_custom()
        self.stack.addWidget(self.page_step3_custom)
        
        # Step 3: Modpack (Version Select)
        self.page_step3_modpack = self.build_step_3_modpack()
        self.stack.addWidget(self.page_step3_modpack)

        # --- 4. Footer (Buttons) ---
        self.footer = QFrame()
        self.footer.setObjectName("WizardFooter")
        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(28, 20, 28, 20)
        
        self.btn_back = QPushButton("Cancel")
        self.btn_back.setObjectName("SecondaryButton")
        self.btn_back.clicked.connect(self.go_back)
        
        self.btn_next = QPushButton("Next")
        self.btn_next.setObjectName("PrimaryButton")
        self.btn_next.clicked.connect(self.go_next)
        
        fl.addWidget(self.btn_back)
        fl.addStretch()
        fl.addWidget(self.btn_next)
        main_layout.addWidget(self.footer)

        self.update_ui_state()

    # ================= UI BUILDERS =================

    def build_step_1(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 30, 40, 30)
        lay.setSpacing(20)

        # Type Selection
        lbl = QLabel("Instance Type")
        lbl.setObjectName("SectionLabel")
        lay.addWidget(lbl)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(15)
        
        # UPDATED: Use .icons/new.svg and .icons/quickmods.svg
        # Ensure ICONS_DIR is available or use relative path string
        icon_new = os.path.join(ICONS_DIR, "new.svg")
        icon_mods = os.path.join(ICONS_DIR, "quickmods.svg")

        self.card_custom = WizardCard(icon_new, "Custom Instance", "Build your own setup from scratch", "custom")
        self.card_custom.setChecked(True)
        self.card_custom.clicked.connect(lambda: self.set_type("custom"))
        
        self.card_modpack = WizardCard(icon_mods, "Import Modpack", "Install from Modrinth", "modpack")
        self.card_modpack.clicked.connect(lambda: self.set_type("modpack"))

        cards_layout.addWidget(self.card_custom)
        cards_layout.addWidget(self.card_modpack)
        lay.addLayout(cards_layout)

        # Name Input
        lbl_name = QLabel("Instance Name")
        lbl_name.setObjectName("SectionLabel")
        lay.addWidget(lbl_name)
        
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("My New Instance")
        self.inp_name.setObjectName("WizardInput")
        lay.addWidget(self.inp_name)

        # Image Upload Area
        # We wrap this in a QWidget so we can hide/show the whole block easily
        self.upload_container = QWidget()
        upload_lay = QVBoxLayout(self.upload_container)
        upload_lay.setContentsMargins(0,0,0,0)
        upload_lay.setSpacing(10)

        lbl_icon = QLabel("Instance Icon")
        lbl_icon.setObjectName("SectionLabel")
        upload_lay.addWidget(lbl_icon)

        img_row = QHBoxLayout()
        img_row.setSpacing(15)
        
        self.img_preview = QLabel()
        self.img_preview.setFixedSize(70, 70)
        self.img_preview.setObjectName("ImagePreview")
        self.img_preview.setStyleSheet("background: #27272a; border-radius: 12px; border: 1px dashed #52525b;")
        self.img_preview.setAlignment(Qt.AlignCenter)
        
        btn_upload = QPushButton("Upload Image...")
        btn_upload.setObjectName("SecondaryButton")
        btn_upload.setCursor(Qt.PointingHandCursor)
        btn_upload.clicked.connect(self.upload_image)
        
        img_row.addWidget(self.img_preview)
        img_row.addWidget(btn_upload)
        img_row.addStretch()
        upload_lay.addLayout(img_row)
        
        lay.addWidget(self.upload_container) # Add container to main layout

        lay.addStretch()
        return w

    def set_type(self, t):
        self.instance_type = t
        
        # Toggle Card Selection Visuals
        self.card_custom.setChecked(t == "custom")
        self.card_modpack.setChecked(t == "modpack")
        
        # Toggle Upload Visibility
        # If custom -> Show Upload. If modpack -> Hide Upload.
        if hasattr(self, 'upload_container'):
            self.upload_container.setVisible(t == "custom")
            
        self.update_ui_state()

    def upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Icon", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if path:
            self.selected_image_path = path
            # Update Preview
            pm = QPixmap(path).scaled(
                70, 70, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            self.img_preview.setPixmap(pm)
            # Remove dashed border when image is set
            self.img_preview.setStyleSheet("background: transparent; border: none; border-radius: 12px;")

    def build_step_2_custom(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 30, 40, 30)
        
        lbl = QLabel("Game Version")
        lbl.setObjectName("SectionLabel")
        lay.addWidget(lbl)

        # --- UPDATED: Search & Filter Row ---
        filter_row = QHBoxLayout()
        
        self.inp_version_search = QLineEdit()
        self.inp_version_search.setPlaceholderText("Search versions...")
        self.inp_version_search.setObjectName("WizardInput")
        self.inp_version_search.textChanged.connect(self.filter_vanilla_list) # Connect search
        
        self.chk_snapshots = QCheckBox("Show Snapshots")
        self.chk_snapshots.setStyleSheet("color: #a1a1aa; spacing: 8px;")
        self.chk_snapshots.stateChanged.connect(self.filter_vanilla_list) # Connect toggle
        
        filter_row.addWidget(self.inp_version_search, 1)
        filter_row.addWidget(self.chk_snapshots)
        lay.addLayout(filter_row)
        lay.addSpacing(10)
        # ------------------------------------

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("WizardScroll")
        content = QWidget()
        self.versions_layout = QVBoxLayout(content)
        scroll.setWidget(content)
        lay.addWidget(scroll)
        
        self.version_btns = [] 
        self.all_vanilla_versions = [] # Store raw data for filtering
        return w

    # Logic to handle the API result and filtering
    # ================= REPLACEMENT METHODS =================
    def populate_vanilla_list(self, versions_data):
        """
        Receives list of dicts from ApiWorker: 
        [{'id': '1.20.4', 'type': 'release'}, {'id': '24w04a', 'type': 'snapshot'}...]
        """
        # 1. Store the raw data
        self.all_vanilla_versions = versions_data
        
        # 2. Trigger the filter to draw the UI
        self.filter_vanilla_list()

    def filter_vanilla_list(self):
        """
        Filters the stored data based on search text and snapshot toggle,
        then draws the buttons.
        """
        # 1. Clear current list UI
        while self.versions_layout.count():
            item = self.versions_layout.takeAt(0)
            if item.widget(): 
                item.widget().deleteLater()
            
        self.version_btns = []
        
        # Safely get search text and toggle state
        if hasattr(self, 'inp_version_search'):
            search_txt = self.inp_version_search.text().lower()
        else:
            search_txt = ""
            
        if hasattr(self, 'chk_snapshots'):
            show_snap = self.chk_snapshots.isChecked()
        else:
            show_snap = False
        
        # 2. Filter and Draw
        count = 0
        limit = 50 # Optimization: only show top 50 matches to prevent lag
        
        # Initialize if missing
        if not hasattr(self, 'all_vanilla_versions'):
            self.all_vanilla_versions = []

        for v in self.all_vanilla_versions:
            # EXTRACT DATA FROM DICT (Fixes the TypeError)
            v_id = v.get("id", "Unknown")
            v_type = v.get("type", "release")
            
            # Logic: Must match search AND (be release OR (be snapshot AND show_snap is true))
            if search_txt in v_id.lower():
                if v_type == "release" or (show_snap and v_type == "snapshot"):
                    
                    # Prepare text
                    display_text = v_id
                    if v_type == "snapshot":
                        display_text = f"{v_id} (Snapshot)"

                    # Create Button with STRING, not Dict
                    btn = QPushButton(display_text)
                    btn.setCheckable(True)
                    btn.setObjectName("ListItem")
                        
                    # Restore selection if it was already selected
                    if self.data.get("version") == v_id:
                        btn.setChecked(True)
                        
                    # Connect click event
                    btn.clicked.connect(lambda _, ver=v_id, b=btn: self.select_vanilla_version(ver, b))
                    
                    self.versions_layout.addWidget(btn)
                    self.version_btns.append(btn)
                    
                    count += 1
                    if count >= limit: 
                        break

    def build_step_2_modpack(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 30, 40, 30)
        
        # Search Bar
        search_lay = QHBoxLayout()
        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("Search Modpacks on Modrinth...")
        self.inp_search.setObjectName("WizardInput")
        self.inp_search.returnPressed.connect(self.search_modpacks)
        
        btn_search = QPushButton("Search")
        btn_search.setObjectName("SecondaryButton")
        btn_search.clicked.connect(self.search_modpacks)
        
        search_lay.addWidget(self.inp_search)
        search_lay.addWidget(btn_search)
        lay.addLayout(search_lay)
        
        lay.addSpacing(10)

        # Results Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("WizardScroll")
        content = QWidget()
        self.modpack_grid = QGridLayout(content)
        self.modpack_grid.setAlignment(Qt.AlignTop)
        scroll.setWidget(content)
        lay.addWidget(scroll)
        
        return w

    def build_step_3_custom(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 30, 40, 30)

        lbl = QLabel("Mod Loader")
        lbl.setObjectName("SectionLabel")
        lay.addWidget(lbl)
        
        self.loader_group = []
        loaders = [
            ("vanilla", "Vanilla", "Official Minecraft release"),
            ("fabric", "Fabric", "Lightweight mod loader"),
            # ("forge", "Forge", "Coming soon...") 
        ]
        
        for lid, title, desc in loaders:
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setObjectName("LoaderItem")
            btn.setFixedHeight(70)
            btn.setCursor(Qt.PointingHandCursor)
            
            l = QVBoxLayout(btn)
            t = QLabel(title)
            t.setStyleSheet("font-weight: bold; font-size: 15px; color: white; background: transparent;")
            d = QLabel(desc)
            d.setStyleSheet("color: #a1a1aa; font-size: 12px; background: transparent;")
            l.addWidget(t)
            l.addWidget(d)
            
            btn.clicked.connect(lambda _, x=lid: self.set_loader(x))
            lay.addWidget(btn)
            self.loader_group.append((lid, btn))
            
        self.loader_group[0][1].setChecked(True)
        lay.addStretch()
        return w

    def build_step_3_modpack(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 30, 40, 30)
        
        # Modpack Info Preview
        self.mp_preview = QFrame()
        self.mp_preview.setObjectName("ModpackPreview")
        pl = QHBoxLayout(self.mp_preview)
        
        self.mp_icon = QLabel()
        self.mp_icon.setFixedSize(64, 64)
        self.mp_icon.setScaledContents(True)
        self.mp_icon.setStyleSheet("background: #27272a; border-radius: 8px;")
        
        info_l = QVBoxLayout()
        self.mp_title = QLabel("Title")
        self.mp_title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        self.mp_author = QLabel("Author")
        self.mp_author.setStyleSheet("color: #a1a1aa;")
        info_l.addWidget(self.mp_title)
        info_l.addWidget(self.mp_author)
        
        pl.addWidget(self.mp_icon)
        pl.addLayout(info_l)
        pl.addStretch()
        
        lay.addWidget(self.mp_preview)
        lay.addSpacing(20)
        
        lbl = QLabel("Select Version")
        lbl.setObjectName("SectionLabel")
        lay.addWidget(lbl)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("WizardScroll")
        content = QWidget()
        self.mp_versions_layout = QVBoxLayout(content)
        scroll.setWidget(content)
        lay.addWidget(scroll)
        
        return w

    # ================= LOGIC & FLOW =================

    def set_icon(self, char):
        self.data["icon"] = char
        for btn in self.icon_buttons:
            btn.setChecked(btn.text() == char)

    def set_loader(self, loader):
        self.data["loader"] = loader
        for lid, btn in self.loader_group:
            btn.setChecked(lid == loader)

    def go_next(self):
        # Validation
        if self.step == 1:
            if not self.inp_name.text().strip():
                # Provide default if empty
                self.inp_name.setText("New Instance")
            self.data["name"] = self.inp_name.text()
            
            # Branching
            if self.instance_type == "custom":
                self.step = 2
                self.stack.setCurrentWidget(self.page_step2_custom)
                if not self.data["version"]:
                    self.fetch_vanilla()
            else:
                self.step = 2
                self.stack.setCurrentWidget(self.page_step2_modpack)
                # Load default modpacks if empty
                if not self.modpack_results:
                    self.search_modpacks()

        elif self.step == 2:
            if self.instance_type == "custom":
                if not self.data["version"]:
                    QMessageBox.warning(self, "Selection Required", "Please select a game version.")
                    return
                self.step = 3
                self.stack.setCurrentWidget(self.page_step3_custom)
            else:
                if not self.data["modpack_info"]:
                    QMessageBox.warning(self, "Selection Required", "Please select a modpack.")
                    return
                self.step = 3
                self.stack.setCurrentWidget(self.page_step3_modpack)
                self.fetch_modpack_versions()

        elif self.step == 3:
            # Finish
            self.finish()
            return

        self.update_ui_state()

    def go_back(self):
        if self.step == 1:
            self.cancelled.emit()
        else:
            self.step -= 1
            if self.step == 1:
                self.stack.setCurrentWidget(self.page_step1)
            elif self.step == 2:
                if self.instance_type == "custom":
                    self.stack.setCurrentWidget(self.page_step2_custom)
                else:
                    self.stack.setCurrentWidget(self.page_step2_modpack)
        self.update_ui_state()

    def update_ui_state(self):
        # Progress Bars
        for i, bar in enumerate(self.progress_bars):
            if i < self.step:
                bar.setObjectName("ProgressBarActive")
            else:
                bar.setObjectName("ProgressBarInactive")
            # Force style refresh
            bar.style().unpolish(bar)
            bar.style().polish(bar)
            
        self.subtitle_lbl.setText(f"Step {self.step} of 3")
        
        # Button text
        if self.step == 1:
            self.btn_back.setText("Cancel")
            self.btn_next.setText("Next")
        elif self.step == 3:
            self.btn_next.setText("Create Instance" if self.instance_type=="custom" else "Install")
        else:
            self.btn_back.setText("Back")
            self.btn_next.setText("Next")

    # ================= DATA FETCHING =================

    def fetch_vanilla(self):
        # Clear existing
        while self.versions_layout.count():
            item = self.versions_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        lbl = QLabel("Loading versions...")
        lbl.setStyleSheet("color: #a1a1aa; padding: 20px;")
        self.versions_layout.addWidget(lbl)
        
        self.worker = ApiWorker("vanilla")
        self.worker.data_ready.connect(self.populate_vanilla_list)
        self.worker.start()

    def select_vanilla_version(self, version, btn):
        self.data["version"] = version
        for b in self.version_btns:
            b.setChecked(b == btn)

    def search_modpacks(self):
        query = self.inp_search.text()
        
        # clear grid
        while self.modpack_grid.count():
            item = self.modpack_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        loading = QLabel("Searching Modrinth...")
        loading.setStyleSheet("color: #a1a1aa;")
        self.modpack_grid.addWidget(loading, 0, 0)
        
        self.worker = ApiWorker("modpack_search", query)
        self.worker.data_ready.connect(self.populate_modpack_grid)
        self.worker.start()

    def populate_modpack_grid(self, results):
        # Clear loading
        while self.modpack_grid.count():
            item = self.modpack_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        self.modpack_results = results
        self.modpack_btns = []
        
        row, col = 0, 0
        for info in results:
            # Card-like button
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(190, 220)
            btn.setObjectName("ModpackCard")
            
            l = QVBoxLayout(btn)
            l.setContentsMargins(10, 10, 10, 10)
            
            # Icon Label
            ico = QLabel()
            ico.setFixedSize(60, 60)
            ico.setStyleSheet("background: #3f3f46; border-radius: 8px;")
            ico.setAlignment(Qt.AlignCenter)
            
            # --- IMAGE LOADING LOGIC ---
            url = info.get('icon_url')
            if url:
                # 1. Create a Network Manager attached to the label (cleans up automatically)
                nam = QNetworkAccessManager(ico)
                ico._nam = nam # Keep python reference alive
                
                # 2. Define the callback (using default arg to capture specific label)
                def on_loaded(reply, label=ico):
                    if reply.error() == QNetworkReply.NoError:
                        data = reply.readAll()
                        pix = QPixmap()
                        pix.loadFromData(data)
                        if not pix.isNull():
                            # Scale to size
                            pix = pix.scaled(60, 60, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                            
                            # Apply Rounded Corners (to match border-radius: 8px)
                            rounded = QPixmap(60, 60)
                            rounded.fill(Qt.transparent)
                            painter = QPainter(rounded)
                            painter.setRenderHint(QPainter.Antialiasing)
                            path = QPainterPath()
                            path.addRoundedRect(0, 0, 60, 60, 8, 8)
                            painter.setClipPath(path)
                            painter.drawPixmap(0, 0, pix)
                            painter.end()
                            
                            label.setPixmap(rounded)
                            # Remove gray background now that we have an image
                            label.setStyleSheet("background: transparent;")
                    reply.deleteLater()

                # 3. Connect and Fetch
                nam.finished.connect(on_loaded)
                nam.get(QNetworkRequest(QUrl(url)))
            else:
                # Fallback if no URL
                ico.setText("?")
                ico.setStyleSheet("background: #3f3f46; border-radius: 8px; color: #71717a; font-size: 24px; font-weight: bold;")
            # ---------------------------

            title = QLabel(info['title'])
            title.setWordWrap(True)
            title.setStyleSheet("font-weight: bold; color: white; background: transparent;")
            title.setAlignment(Qt.AlignHCenter)
            
            auth = QLabel(f"by {info['author']}")
            auth.setStyleSheet("color: #a1a1aa; font-size: 11px; background: transparent;")
            auth.setAlignment(Qt.AlignHCenter)

            desc = QLabel(info['desc'][:60] + "..." if info['desc'] else "")
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #71717a; font-size: 10px; background: transparent;")
            desc.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            
            l.addWidget(ico, 0, Qt.AlignHCenter)
            l.addWidget(title)
            l.addWidget(auth)
            l.addWidget(desc)
            l.addStretch()
            
            btn.clicked.connect(lambda _, i=info, b=btn: self.select_modpack(i, b))
            
            self.modpack_grid.addWidget(btn, row, col)
            self.modpack_btns.append(btn)
            
            col += 1
            if col > 3: # 4 columns
                col = 0
                row += 1

    def select_modpack(self, info, btn):
        # 1. Get the currently displayed text
        current_name = self.inp_name.text().strip()
        
        # 2. Check if we should auto-update the name.
        # We update if:
        #   a) The name is still the generic "New Instance"
        #   b) OR the name matches the PREVIOUS modpack's title (meaning the user hasn't manually typed a custom name)
        should_update = False
        
        if current_name == "New Instance" or not current_name:
            should_update = True
        elif self.data.get("modpack_info") and current_name == self.data["modpack_info"].get("title"):
            should_update = True

        # 3. Update data
        if should_update:
            self.inp_name.setText(info['title'])
            self.data["name"] = info['title']

        self.data["modpack_info"] = info
            
        # 4. Visual selection update
        for b in self.modpack_btns:
            b.setChecked(b == btn)

    def clear_layout(self, layout):
        if hasattr(layout, 'count'):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

    def fetch_modpack_versions(self):
        info = self.data["modpack_info"]
        
        # 1. Update Text Info
        self.mp_title.setText(info['title'])
        self.mp_author.setText(f"by {info['author']}")
        
        # 2. Async Load Icon
        url = info.get("icon_url")
        if url:
            # Create a Network Manager attached to the label so it persists
            nam = QNetworkAccessManager(self.mp_icon)
            self.mp_icon._nam = nam # Keep python reference alive to prevent GC
            
            def on_loaded(reply):
                if reply.error() == QNetworkReply.NoError:
                    data = reply.readAll()
                    pix = QPixmap()
                    pix.loadFromData(data)
                    if not pix.isNull():
                        # Scale to match the FixedSize(64, 64)
                        pix = pix.scaled(64, 64, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                        
                        # Apply Rounded Corners (8px)
                        rounded = QPixmap(64, 64)
                        rounded.fill(Qt.transparent)
                        painter = QPainter(rounded)
                        painter.setRenderHint(QPainter.Antialiasing)
                        path = QPainterPath()
                        path.addRoundedRect(0, 0, 64, 64, 8, 8)
                        painter.setClipPath(path)
                        painter.drawPixmap(0, 0, pix)
                        painter.end()
                        
                        self.mp_icon.setPixmap(rounded)
                        self.mp_icon.setStyleSheet("background: transparent;")
                reply.deleteLater()

            nam.finished.connect(on_loaded)
            nam.get(QNetworkRequest(QUrl(url)))
        else:
            # Fallback
            self.mp_icon.clear()
            self.mp_icon.setText("?")
            self.mp_icon.setStyleSheet("background: #27272a; border-radius: 8px; color: #71717a; font-size: 24px; font-weight: bold;")
            self.mp_icon.setAlignment(Qt.AlignCenter)

        # 3. Start fetching versions
        self.clear_layout(self.mp_versions_layout)
        self.mp_versions_layout.addWidget(QLabel("Loading versions...", styleSheet="color:#a1a1aa;"))
        self.worker = ApiWorker("modpack_versions", info['id'])
        self.worker.data_ready.connect(self.populate_modpack_versions)
        self.worker.start()

    def populate_modpack_versions(self, versions):
        while self.mp_versions_layout.count():
            item = self.mp_versions_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        self.mp_ver_btns = []
        for v in versions:
            v_num = v['version_number']
            v_name = v.get('name', v_num)
            mc_ver = v['game_versions'][0] if v['game_versions'] else "Unknown"
            loader = v['loaders'][0] if v['loaders'] else "Unknown"
            
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setObjectName("ListItem")
            btn.setFixedHeight(50)
            
            l = QHBoxLayout(btn)
            l.addWidget(QLabel(v_name, styleSheet="color: white; font-weight: bold; background: transparent;"))
            l.addStretch()
            l.addWidget(QLabel(f"{mc_ver} • {loader}", styleSheet="color: #a1a1aa; background: transparent;"))
            
            # Store full version object to get file url later
            btn.clicked.connect(lambda _, ver_obj=v, b=btn: self.select_modpack_version(ver_obj, b))
            
            self.mp_versions_layout.addWidget(btn)
            self.mp_ver_btns.append(btn)

    def select_modpack_version(self, ver_obj, btn):
        self.data["modpack_version_id"] = ver_obj # Store full object
        for b in self.mp_ver_btns:
            b.setChecked(b == btn)

    def finish(self):
        # 1. Prepare Image Data (Default fallback)
        image_data = "🟩" 
        
        # Check 1: User uploaded custom image (Local File)
        if self.selected_image_path and os.path.exists(self.selected_image_path):
            try:
                icons_dir = os.path.join(PROJECT_DIR, ".icons")
                os.makedirs(icons_dir, exist_ok=True)
                
                ext = os.path.splitext(self.selected_image_path)[1]
                safe_name = self.data["name"].lower().replace(" ", "_")
                filename = f"{safe_name}{ext}"
                
                saved_path = os.path.join(".icons", filename)
                abs_dest = os.path.join(PROJECT_DIR, saved_path)
                
                shutil.copy2(self.selected_image_path, abs_dest)
                
                image_data = {
                    "original_path": self.selected_image_path,
                    "saved_path": saved_path
                }
            except Exception as e:
                print(f"Failed to save custom image: {e}")

        # Check 2: Modpack icon (Download asynchronously)
        elif self.instance_type == "modpack" and self.data["modpack_info"]:
            mp_info = self.data["modpack_info"]
            icon_url = mp_info.get("icon_url")
            
            if icon_url:
                try:
                    icons_dir = os.path.join(PROJECT_DIR, ".icons")
                    os.makedirs(icons_dir, exist_ok=True)
                    
                    ext = os.path.splitext(icon_url)[1]
                    if not ext or len(ext) > 5: ext = ".png"
                    
                    safe_name = self.data["name"].lower().replace(" ", "_")
                    filename = f"{safe_name}{ext}"
                    
                    saved_path = os.path.join(".icons", filename)
                    abs_dest = os.path.join(PROJECT_DIR, saved_path)
                    
                    # --- ASYNC DOWNLOAD LOGIC (FIXED) ---
                    # Uses QEventLoop directly (requires 'from PyQt5.QtCore import QEventLoop')
                    loop = QEventLoop()
                    nam = QNetworkAccessManager()
                    nam.finished.connect(loop.quit)
                    
                    print(f"Downloading icon from {icon_url}...")
                    reply = nam.get(QNetworkRequest(QUrl(icon_url)))
                    loop.exec_() # Wait here until finished
                    
                    if reply.error() == QNetworkReply.NoError:
                        data = reply.readAll()
                        with open(abs_dest, 'wb') as f:
                            f.write(data)
                            
                        image_data = {
                            "original_path": icon_url,
                            "saved_path": saved_path
                        }
                    else:
                        print(f"Download Error: {reply.errorString()}")
                    
                    reply.deleteLater()
                    # ----------------------------

                except Exception as e:
                    print(f"Failed to save modpack image: {e}")

        # 2. Build Final Data
        final_data = {}
        
        if self.instance_type == "custom":
            final_data = {
                "type": "Custom",
                "name": self.data["name"],
                "version": self.data["version"],
                "modloader": "Fabric" if self.data["loader"] == "fabric" else "Vanilla",
                "loader_version": None, 
                "image": image_data,
                "last_played": None
            }
        else:
            # Modpack logic
            mp_info = self.data["modpack_info"]
            mp_ver = self.data["modpack_version_id"]
            
            if not mp_ver:
                 QMessageBox.warning(self, "Error", "No version selected")
                 return
                 
            files = mp_ver.get("files", [])
            primary_file = next((f for f in files if f.get("primary")), files[0] if files else None)
            
            if not primary_file:
                QMessageBox.critical(self, "Error", "Modpack has no files to download.")
                return

            final_data = {
                "type": "Modrinth",
                "name": self.data["name"],
                "version": mp_ver['game_versions'][0],
                "modloader": mp_ver['loaders'][0].capitalize(),
                "image": image_data, # Use the downloaded image data
                "modpack_url": primary_file['url'],
                "modpack_hash": primary_file['hashes']['sha1'],
                "last_played": None
            }

        self.created.emit(final_data)
        
        # Reset wizard
        self.step = 1
        self.inp_name.clear()
        self.selected_image_path = None
        self.img_preview.clear()
        self.img_preview.setStyleSheet("background: #27272a; border-radius: 12px; border: 1px dashed #52525b;")
        self.stack.setCurrentWidget(self.page_step1)
        self.update_ui_state()

    # ================= STYLES =================
    
    def apply_styles(self):
        self.setStyleSheet("""

            QWidget#NewInstancePage { background: #09090b; }
            QFrame#WizardHeader { 
                background: #09090b; 
                border-bottom: 1px solid #27272a; 
            }
            QLabel#WizardTitle { font-size: 24px; font-weight: bold; color: white; background: transparent; }
            QLabel#WizardSubtitle { font-size: 14px; color: #ffffff; background: transparent; }
            
            QFrame#ProgressContainer { background: #18181b; }
            QFrame#ProgressBarActive { background: #10b981; border-radius: 2px; }
            QFrame#ProgressBarInactive { background: #3f3f46; border-radius: 2px; }
            
            QFrame#WizardFooter { background: #18181b; border-top: 1px solid #27272a; }
            
            QLabel#SectionLabel { font-size: 16px; font-weight: bold; color: white; margin-bottom: 8px; }
            
            QPushButton#WizardCard {
                background: #27272a; border: 2px solid transparent; border-radius: 16px; text-align: left;
            }
            QPushButton#WizardCard:checked {
                background: #059669; border: 2px solid #34d399;
            }
            QPushButton#WizardCard:hover:!checked {
                background: #3f3f46;
            }
            
            QLineEdit#WizardInput {
                background: #27272a; border: 1px solid #3f3f46; border-radius: 12px;
                color: white; padding: 12px; font-size: 14px;
            }
            QLineEdit#WizardInput:focus { border: 1px solid #10b981; }
            
            QPushButton#IconBtn { background: #27272a; border-radius: 8px; font-size: 20px; border: none; }
            QPushButton#IconBtn:checked { background: #059669; }
            QPushButton#IconBtn:hover:!checked { background: #3f3f46; }
            
            QPushButton#PrimaryButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #0d9488);
                color: white; border-radius: 12px; padding: 10px 24px; font-weight: bold; font-size: 14px; border: none;
            }
            QPushButton#PrimaryButton:hover { background: #10b981; }
            
            QPushButton#SecondaryButton {
                background: #3f3f46; color: white; border-radius: 12px; padding: 10px 24px; font-weight: bold; border: none;
            }
            QPushButton#SecondaryButton:hover { background: #52525b; }
            
            QScrollArea#WizardScroll { border: none; background: transparent; }
            QScrollArea#WizardScroll QWidget { background: transparent; }
            
            QPushButton#ListItem {
                background: #27272a; border: 1px solid transparent; border-radius: 10px; color: white; text-align: left; padding: 10px;
            }
            QPushButton#ListItem:checked {
                background: #059669; border: 1px solid #34d399;
            }
            QPushButton#ListItem:hover:!checked { background: #3f3f46; }
            
            QPushButton#LoaderItem {
                background: #27272a; border: 2px solid transparent; border-radius: 12px; text-align: left; padding: 0 15px;
            }
            QPushButton#LoaderItem:checked {
                background: #059669; border: 2px solid #34d399;
            }
            
            QPushButton#ModpackCard {
                background: #27272a; border: 2px solid transparent; border-radius: 16px;
            }
            QPushButton#ModpackCard:checked {
                background: #059669; border: 2px solid #34d399;
            }
            QPushButton#ModpackCard:hover:!checked { background: #3f3f46; }
        """)

# ================= AUTH WORKER =================
class AuthWorker(QThread):
    status = pyqtSignal(str)
    success = pyqtSignal(dict)
    failure = pyqtSignal(str)

    def __init__(self, auth_code):
        super().__init__()
        self.code = auth_code

    def run(self):
        try:
            self.status.emit("Exchanging code for Microsoft token…")
            token = self.get_token()
            if not token:
                raise Exception("Microsoft authentication failed")

            self.status.emit("Authenticating with Xbox Live…")
            xbl = self.auth_xbl(token)
            if not xbl:
                raise Exception("Xbox Live authentication failed")

            self.status.emit("Authenticating with XSTS…")
            xsts = self.auth_xsts(xbl)
            if not xsts:
                raise Exception("XSTS authentication failed")

            self.status.emit("Getting Minecraft access token…")
            mc = self.get_mc_token(xsts)
            if not mc:
                raise Exception("Minecraft token failed")

            profile = self.get_profile(mc)
            if not profile:
                raise Exception("Failed to fetch Minecraft profile")

            self.success.emit({
                "username": profile["name"],
                "uuid": profile["id"],
                "access_token": mc
            })

        except Exception as e:
            self.failure.emit(str(e))

    # ---- API helpers ----
    def get_token(self):
        r = requests.post(
            "https://login.live.com/oauth20_token.srf",
            data={
                "client_id": "00000000402b5328",
                "code": self.code,
                "grant_type": "authorization_code",
                "redirect_uri": "https://login.live.com/oauth20_desktop.srf",
                "scope": "service::user.auth.xboxlive.com::MBI_SSL",
            },
        )
        return r.json().get("access_token") if r.ok else None

    def auth_xbl(self, token):
        r = requests.post(
            "https://user.auth.xboxlive.com/user/authenticate",
            json={
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": token,
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT",
            },
        )
        j = r.json()
        if r.ok:
            return {
                "token": j["Token"],
                "uhs": j["DisplayClaims"]["xui"][0]["uhs"],
            }

    def auth_xsts(self, xbl):
        r = requests.post(
            "https://xsts.auth.xboxlive.com/xsts/authorize",
            json={
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [xbl["token"]],
                },
                "RelyingParty": "rp://api.minecraftservices.com/",
                "TokenType": "JWT",
            },
        )
        j = r.json()
        if r.ok:
            return {
                "token": j["Token"],
                "uhs": j["DisplayClaims"]["xui"][0]["uhs"],
            }

    def get_mc_token(self, xsts):
        r = requests.post(
            "https://api.minecraftservices.com/authentication/login_with_xbox",
            json={"identityToken": f"XBL3.0 x={xsts['uhs']};{xsts['token']}"},
        )
        return r.json().get("access_token") if r.ok else None

    def get_profile(self, token):
        r = requests.get(
            "https://api.minecraftservices.com/minecraft/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        return r.json() if r.ok else None


# ================= ACCOUNT WINDOW =================
# ================= ACCOUNT WINDOW (FIXED) =================
class AccountWindow(QDialog):
    account_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sign in")
        self.setFixedSize(500, 480)
        self.setObjectName("AccountWindow")

        # Main layout for the dialog background
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)

        # The central card frame
        self.card = QFrame()
        self.card.setObjectName("AuthCard")
        # 🔥 CRITICAL FIX: Forces the frame to paint its background-color
        self.card.setAttribute(Qt.WA_StyledBackground, True) 
        main_layout.addWidget(self.card)

        # Stack layout lives inside the card
        self.stack = QStackedLayout(self.card)
        self.page_intro = self._build_intro()
        self.page_url = self._build_url()

        self.stack.addWidget(self.page_intro)
        self.stack.addWidget(self.page_url)
        self.stack.setCurrentWidget(self.page_intro)

        self.apply_styles()

    # ---------- PAGE 1 ----------
    def _build_intro(self):
        page_container = QFrame()
        lay = QVBoxLayout(page_container)
        lay.setContentsMargins(40, 50, 40, 50)
        lay.setSpacing(0)

        # 1. Wrapper for the white square (Alignment wrapper)
        logo_wrapper = QVBoxLayout()
        logo_wrapper.setAlignment(Qt.AlignCenter)

        # 2. The white tile itself
        self.logo_tile = QFrame()
        self.logo_tile.setObjectName("LogoTile")
        self.logo_tile.setFixedSize(84, 84) 
        # 🔥 CRITICAL FIX: Forces the white tile to paint
        self.logo_tile.setAttribute(Qt.WA_StyledBackground, True)

        # 3. Layout inside the tile to center the actual icon
        tile_layout = QVBoxLayout(self.logo_tile)
        tile_layout.setContentsMargins(0, 0, 0, 0)
        tile_layout.setAlignment(Qt.AlignCenter)

        # 4. The Icon
        logo_img = QLabel()
        logo_img.setPixmap(self._load_ms_logo(42))
        logo_img.setAlignment(Qt.AlignCenter)
        
        tile_layout.addWidget(logo_img)
        logo_wrapper.addWidget(self.logo_tile)

        # --- Text ---
        title = QLabel("Sign in with Microsoft")
        title.setObjectName("AuthTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Use your Microsoft account to access Minecraft")
        subtitle.setObjectName("AuthSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        # --- Button ---
        self.btn_ms = QPushButton("Continue with Microsoft")
        self.btn_ms.setObjectName("LaunchButton")
        self.btn_ms.setMinimumHeight(64)
        self.btn_ms.setCursor(Qt.PointingHandCursor)
        self.btn_ms.clicked.connect(self._start_ms_flow)

        # --- Assembly ---
        lay.addStretch(1)
        lay.addLayout(logo_wrapper)
        lay.addSpacing(28) 
        lay.addWidget(title)
        lay.addSpacing(10)
        lay.addWidget(subtitle)
        lay.addSpacing(45)
        lay.addWidget(self.btn_ms)
        lay.addStretch(1)

        return page_container

    # ---------- PAGE 2 ----------
    def _build_url(self):
        page_container = QFrame()
        lay = QVBoxLayout(page_container)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(16)

        warning = QLabel(
            "You will be redirected to a Microsoft page.\n\n"
            "AFTER SIGNING IN COPY THE ENTIRE URL\n"
            "from your browser and paste it below.\n\n"
            "DO THIS QUICKLY before the code disappears for \"safety\"."
        )
        warning.setObjectName("AuthWarning")
        warning.setAlignment(Qt.AlignCenter)
        warning.setWordWrap(True)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("AuthInput")
        self.url_input.setPlaceholderText("Paste redirected URL here…")
        self.url_input.setMinimumHeight(44)

        self.status = QLabel("")
        self.status.setObjectName("AuthStatus")
        self.status.setAlignment(Qt.AlignCenter)

        submit = QPushButton("Submit URL")
        submit.setObjectName("PrimaryButton")
        submit.setMinimumHeight(50)
        submit.setCursor(Qt.PointingHandCursor)
        submit.clicked.connect(self._submit_url)

        lay.addStretch()
        lay.addWidget(warning)
        lay.addSpacing(10)
        lay.addWidget(self.url_input)
        lay.addWidget(self.status)
        lay.addSpacing(10)
        lay.addWidget(submit)
        lay.addStretch()

        return page_container

    # ---------- FLOW ----------
    def _start_ms_flow(self):
        self.stack.setCurrentWidget(self.page_url)

        def open_browser():
            url = (
                "https://login.live.com/oauth20_authorize.srf"
                "?client_id=00000000402b5328"
                "&response_type=code"
                "&scope=service::user.auth.xboxlive.com::MBI_SSL"
                "&redirect_uri=https://login.live.com/oauth20_desktop.srf"
            )
            webbrowser.open(url)

        QTimer.singleShot(5000, open_browser)

    def _submit_url(self):
        raw = self.url_input.text().strip()
        parsed = urlparse(raw)

        if parsed.hostname != "login.live.com":
            QMessageBox.critical(self, "Invalid URL", "That is not a Microsoft redirect URL.")
            return

        code = parse_qs(parsed.query).get("code", [None])[0]
        if not code:
            QMessageBox.critical(self, "Invalid URL", "Authorization code not found.")
            return

        self.status.setText("Authenticating…")
        self.url_input.setEnabled(False)
        self.worker = AuthWorker(code)
        self.worker.status.connect(self.status.setText)
        self.worker.success.connect(self._on_success)
        self.worker.failure.connect(self._on_failure)
        self.worker.start()

    def _on_success(self, data):
        self.account_updated.emit(data)
        self.accept()

    def _on_failure(self, msg):
        QMessageBox.critical(self, "Login Failed", msg)
        self.status.setText("")
        self.url_input.setEnabled(True)
        self.url_input.clear()

    # ---------- ICON ----------
    def _load_ms_logo(self, size: int) -> QPixmap:
        svg = """<svg viewBox="0 0 24 24" fill="none"
        xmlns="http://www.w3.org/2000/svg">
        <path d="M0 0h11.4v11.4H0z" fill="#F25022"/>
        <path d="M12.6 0H24v11.4H12.6z" fill="#7FBA00"/>
        <path d="M0 12.6h11.4V24H0z" fill="#00A4EF"/>
        <path d="M12.6 12.6H24V24H12.6z" fill="#FFB900"/>
        </svg>"""
        renderer = QSvgRenderer(bytearray(svg, "utf-8"))
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        renderer.render(p)
        p.end()
        return pm

    # ---------- STYLES ----------
    def apply_styles(self):
        # We use explicit ID selectors to ensure they apply even if parent styles conflict
        self.setStyleSheet("""
        /* Window Background */
        QDialog#AccountWindow {
            background: #18181b; 
        }

        /* The Card - Dark Grey */
        QFrame#AuthCard {
            background-color: #27272a;
            border: 1px solid #3f3f46;
            border-radius: 24px;
        }

        /* The White Square - GUARANTEED WHITE BACKGROUND */
        QFrame#LogoTile {
            background-color: #ffffff;
            border-radius: 20px;
        }

        /* Title - Large and Bold */
        QLabel#AuthTitle {
            color: #ffffff;
            font-family: "Segoe UI", sans-serif;
            font-size: 26px;
            font-weight: 800;
        }

        /* Subtitle - Small and Gray */
        QLabel#AuthSubtitle {
            color: #a1a1aa;
            font-family: "Segoe UI", sans-serif;
            font-size: 14px;
            font-weight: 300;
            padding: 0 10px;
        }

        /* Button: Green */
        QPushButton#LaunchButton {
            background-color: #10b981;
            color: white;
            border: none;
            border-radius: 14px;
            font-size: 17px;
            font-weight: 700;
        }
        QPushButton#LaunchButton:hover {
            background-color: #059669;
        }

        /* Inputs */
        QLineEdit#AuthInput {
            background: #18181b;
            border: 1px solid #3f3f46;
            color: white;
            padding: 0 12px;
            border-radius: 8px;
        }
        
        /* Secondary Buttons inside Auth Window */
        QPushButton#PrimaryButton {
            background-color: #27272a;
            border: 1px solid #52525b;
            color: white;
            border-radius: 12px;
            font-size: 15px;
            font-weight: 700;
        }
        QPushButton#PrimaryButton:hover {
            background-color: #3f3f46;
        }
        
        QLabel#AuthWarning { color: #facc15; font-weight: 700; }
        QLabel#AuthStatus { color: #34d399; font-weight: 600; }
        """)

class ModrinthSearchWorker(QObject):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query, mc_version, sort_index="relevance"):
        super().__init__()
        self.query = query
        self.mc_version = mc_version
        self.sort_index = sort_index

    def run(self):
        try:
            url = "https://api.modrinth.com/v2/search"
            
            # Facets: AND logic is outer list, OR logic is inner list.
            # We want: (Fabric) AND (Game Version) AND (Mod)
            facets = [
                ["categories:fabric"],
                ["project_type:mod"],
            ]
            
            if self.mc_version:
                facets.append([f"versions:{self.mc_version}"])

            params = {
                "query": self.query,
                "facets": json.dumps(facets),
                "index": self.sort_index, # relevance, downloads, newest, updated
                "limit": 20
            }

            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                self.results_ready.emit(data.get("hits", []))
            else:
                self.error.emit(f"Search failed: {r.status_code}")
        except Exception as e:
            self.error.emit(str(e))

class ModGridCard(QFrame):
    clicked = pyqtSignal(dict) # emits full mod data

    def __init__(self, mod_data, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.setCursor(Qt.PointingHandCursor)
        
        # 🔥 CHANGED: Full width, shorter fixed height (like ModRow)
        self.setFixedHeight(110) 
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setObjectName("ModGridCard")
        
        # Style (Card look)
        self.setStyleSheet("""
            QFrame#ModGridCard {
                background: #27272a; border: 1px solid #3f3f46; border-radius: 12px;
            }
            QFrame#ModGridCard:hover {
                background: #3f3f46; border: 1px solid #52525b;
            }
            QLabel { background: transparent; border: none; }
        """)

        # 🔥 CHANGED: Horizontal Layout for the row look
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # 1. Icon (Left)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(64, 64)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet("background: #18181b; border-radius: 8px;")
        
        icon_url = mod_data.get("icon_url")
        if icon_url:
            self._load_icon(icon_url)
        else:
            self.icon_lbl.setText("?")
            self.icon_lbl.setStyleSheet("background: #18181b; border-radius: 8px; color: #71717a; font-weight: bold; font-size: 24px;")

        main_layout.addWidget(self.icon_lbl)

        # 2. Details Column (Middle)
        details_col = QVBoxLayout()
        details_col.setSpacing(4)
        details_col.setContentsMargins(0, 4, 0, 4)

        # Title
        title = mod_data.get("title", "Unknown")
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: white; font-weight: bold; font-size: 15px;")
        details_col.addWidget(lbl_title)

        # Author
        author = mod_data.get("author", "Unknown")
        lbl_auth = QLabel(f"by {author}")
        lbl_auth.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        details_col.addWidget(lbl_auth)

        # Description (Truncated)
        desc_text = mod_data.get("description", "")
        # Strip newlines for cleaner row view
        desc_text = desc_text.replace("\n", " ")
        if len(desc_text) > 90: 
            desc_text = desc_text[:90] + "..."
            
        lbl_desc = QLabel(desc_text)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #71717a; font-size: 12px;")
        lbl_desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        details_col.addWidget(lbl_desc)
        details_col.addStretch()
        
        main_layout.addLayout(details_col, 1) # 1 = stretch factor

        # 3. Stats Column (Right)
        stats_col = QVBoxLayout()
        stats_col.setContentsMargins(0, 4, 0, 4)
        stats_col.setSpacing(4)
        stats_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Downloads
        dls = self._format_number(mod_data.get("downloads", 0))
        lbl_dls = QLabel(f"⬇ {dls}")
        lbl_dls.setStyleSheet("color: #34d399; font-size: 12px; font-weight: bold;")
        lbl_dls.setAlignment(Qt.AlignRight)
        
        # Updated Date
        date_str = mod_data.get("date_modified", "")[:10]
        lbl_date = QLabel(date_str)
        lbl_date.setStyleSheet("color: #52525b; font-size: 11px;")
        lbl_date.setAlignment(Qt.AlignRight)
        
        stats_col.addWidget(lbl_dls)
        stats_col.addWidget(lbl_date)
        
        main_layout.addLayout(stats_col)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.mod_data)
        super().mousePressEvent(event)

    def _format_number(self, num):
        if num >= 1_000_000: return f"{num/1_000_000:.1f}M"
        if num >= 1_000: return f"{num/1_000:.1f}K"
        return str(num)

    def _load_icon(self, url):
        from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
        self.nam = QNetworkAccessManager(self)
        self.nam.finished.connect(self._icon_loaded)
        self.nam.get(QNetworkRequest(QUrl(url)))

    def _icon_loaded(self, reply):
        if reply.error() == QNetworkReply.NoError:
            data = reply.readAll()
            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                pix = pix.scaled(64, 64, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                rounded = QPixmap(64, 64)
                rounded.fill(Qt.transparent)
                p = QPainter(rounded)
                p.setRenderHint(QPainter.Antialiasing)
                path = QPainterPath()
                path.addRoundedRect(0, 0, 64, 64, 8, 8)
                p.setClipPath(path)
                p.drawPixmap(0, 0, pix)
                p.end()
                self.icon_lbl.setPixmap(rounded)
                self.icon_lbl.setStyleSheet("background: transparent;")
        reply.deleteLater()

class VersionSelectDialog(QDialog):
    """
    Dialog to let the user choose a specific version to install.
    """
    def __init__(self, current_version, versions_list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Version")
        self.setFixedSize(700, 600) # Increased width to fit extra text
        self.selected_file = None
        self.selected_version_number = None
        
        # Styles
        self.setStyleSheet("""
            QDialog { background: #18181b; }
            QLabel { color: white; }
            QListWidget { 
                background: #27272a; border: 1px solid #3f3f46; border-radius: 8px; 
                outline: none;
            }
            QListWidget::item { 
                padding: 12px; border-bottom: 1px solid #3f3f46; color: #d4d4d8;
            }
            QListWidget::item:selected { 
                background: #059669; color: white; border: 1px solid #10b981; border-radius: 4px;
            }
            QPushButton#PrimaryButton {
                background: #059669; color: white; border: none; border-radius: 8px; padding: 10px; font-weight: bold;
            }
            QPushButton#PrimaryButton:hover { background: #10b981; }
            QPushButton#SecondaryButton {
                background: #3f3f46; color: white; border: none; border-radius: 8px; padding: 10px;
            }
            QPushButton#SecondaryButton:hover { background: #52525b; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        lbl = QLabel(f"Current Version: {current_version}")
        lbl.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        layout.addWidget(lbl)

        # List
        self.list_widget = QListWidget()
        self.populate_list(versions_list, current_version)
        layout.addWidget(self.list_widget)

        # Buttons
        btn_box = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("SecondaryButton")
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_install = QPushButton("Install Selected")
        self.btn_install.setObjectName("PrimaryButton")
        self.btn_install.clicked.connect(self.confirm_selection)
        self.btn_install.setEnabled(False) # Disabled until selection

        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_install)
        layout.addLayout(btn_box)
        
        self.list_widget.itemClicked.connect(lambda: self.btn_install.setEnabled(True))

    def populate_list(self, versions, current_ver):
        
        for v in versions:
            v_num = v.get("version_number", "Unknown")
            v_type = v.get("version_type", "release").capitalize()
            date_str = v.get("date_published", "")[:10] # YYYY-MM-DD
            
            # --- GAME VERSIONS ---
            game_versions = v.get("game_versions", [])
            gv_str = ", ".join(game_versions[:2]) 
            if len(game_versions) > 2:
                gv_str += "..."
            if not gv_str: gv_str = "Any"

            # --- LOADERS ---
            loaders = v.get("loaders", [])
            # Capitalize each loader (fabric -> Fabric)
            loaders = [l.capitalize() for l in loaders]
            loaders_str = ", ".join(loaders)
            if not loaders_str: loaders_str = "All"

            # Find primary file
            files = v.get("files", [])
            primary_file = next((f for f in files if f.get("primary")), files[0] if files else None)
            
            if not primary_file: continue

            # Format: Version • Type • Loaders • Game Version • Date
            item_text = f"{v_num}  •  {v_type}  •  {loaders_str}  •  {gv_str}  •  {date_str}"
            
            if v_num == current_ver:
                item_text += "  (Current)"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, primary_file) 
            item.setData(Qt.UserRole + 1, v_num)
            
            self.list_widget.addItem(item)

    def confirm_selection(self):
        item = self.list_widget.currentItem()
        if item:
            self.selected_file = item.data(Qt.UserRole)
            self.selected_version_number = item.data(Qt.UserRole + 1)
            self.accept()

class ModrinthVersionFetcher(QObject):
    """Fetches list of versions compatible with the instance."""
    versions_ready = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, project_id, mc_version, loader):
        super().__init__()
        self.project_id = project_id
        self.mc_version = mc_version
        self.loader = loader

    def run(self):
        try:
            url = f"https://api.modrinth.com/v2/project/{self.project_id}/version"
            params = {}
            if self.mc_version: params["game_versions[]"] = self.mc_version
            if self.loader: params["loaders[]"] = self.loader.lower()

            r = requests.get(url, params=params, timeout=10)
            if r.status_code == 200:
                self.versions_ready.emit(r.json())
            else:
                self.error.emit(f"API Error: {r.status_code}")
        except Exception as e:
            self.error.emit(str(e))

class ModrinthInstaller(QObject):
    """Downloads a specific file URL and replaces old files."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, dict) # success, msg, updated_data_partial

    def __init__(self, file_info, new_version_number, mod_data, mods_dir):
        super().__init__()
        self.file_info = file_info
        self.new_version = new_version_number
        self.mod_data = mod_data
        self.mods_dir = mods_dir
        self._should_stop = False

    def run(self):
        try:
            url = self.file_info.get("url")
            version_id = url.split("/versions/")[1].split("/", 1)[0]

            filename = self.file_info.get("filename")
            
            if not url or not filename:
                self.finished.emit(False, "Invalid file info", {})
                return

            os.makedirs(self.mods_dir, exist_ok=True)
            
            # 1. Download
            self.progress.emit(f"Downloading {filename}...")
            temp_path = os.path.join(self.mods_dir, f".temp_{filename}")
            
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if self._should_stop: return
                    f.write(chunk)
            
            # 2. Delete Old Files
            self.progress.emit("Removing old version...")
            old_files = self.mod_data.get("filenames", [])
            for fn in old_files:
                p = os.path.join(self.mods_dir, fn)
                if os.path.exists(p):
                    try: os.remove(p)
                    except: pass
            
            # 3. Move New File
            final_path = os.path.join(self.mods_dir, filename)
            os.replace(temp_path, final_path)
            
            # 4. Success Data
            updated_data = {
                "filenames": [filename],
                "version": self.new_version,
                "enabled": True
            }
            self.finished.emit(True, f"Installed {self.new_version}", updated_data)

        except Exception as e:
            self.finished.emit(False, str(e), {})

    def stop(self):
        self._should_stop = True

# ---------- Helper widgets ----------
class Card(QFrame):
    def __init__(self, title: str, value: str):
        super().__init__()
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(6)
        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")
        self.value = QLabel(value)
        self.value.setObjectName("CardValue")
        lay.addWidget(self.title)
        lay.addWidget(self.value)


class SectionRow(QFrame):
    """A row like: [title/subtitle] .... [action button]"""
    def __init__(self, title: str, subtitle: str, action_text: str, action_cb=None):
        super().__init__()
        self.setObjectName("SectionRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)

        left = QVBoxLayout()
        left.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("RowTitle")
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("RowSubtitle")
        left.addWidget(self.title)
        left.addWidget(self.subtitle)

        lay.addLayout(left, 1)

        self.btn = QPushButton(action_text)
        self.btn.setObjectName("LinkButton")
        if action_cb:
            self.btn.clicked.connect(action_cb)
        lay.addWidget(self.btn, 0, Qt.AlignRight)

# ================= INSTALLATION WORKER (FIXED) =================
class InstallationWorker(QObject):
    """Worker for handling installations in a separate thread."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, instance_data, java_path):
        super().__init__()
        self.instance_data = instance_data
        self.java_path = java_path or "java"
        self._should_stop = False
        # Setup cache dir for extracted mod icons
        self.mod_icon_cache = os.path.join(GAME_DIR, "cache", "mod_icons")
        os.makedirs(self.mod_icon_cache, exist_ok=True)

    def stop(self):
        self._should_stop = True

    def run(self):
        try:
            instance_type = self.instance_data.get('type')
            
            if instance_type == "Modrinth":
                self.install_modrinth_pack()
            else:
                self.install_vanilla_or_fabric()
            
            if not self._should_stop:
                self.finished.emit(True, "Installation completed successfully!")

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            self.finished.emit(False, f"Error: {str(e)}")

    def execute_process(self, args):
        """Executes a subprocess and emits output."""
        if args[0].endswith(".sh") or args[0].endswith(".command"):
            subprocess.run(["chmod", "+x", args[0]])

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
                return False
            self.progress.emit(line.strip())
        process.wait()
        return process.returncode == 0

    def download_url(self, url, dest):
        """Helper to download a file with progress logging."""
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            r = requests.get(url, stream=True, timeout=15)
            r.raise_for_status()
            with open(dest, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if self._should_stop: return False
                    f.write(chunk)
            return True
        except Exception as e:
            self.progress.emit(f"Download Failed: {e}")
            return False

    def extract_jar_metadata(self, jar_path):
        """
        Reads fabric.mod.json to find name, version, icon, and potentially project_id.
        """
        meta = {
            "filename": os.path.basename(jar_path),
            "name": os.path.basename(jar_path), 
            "version": "",
            "author": "Unknown",
            "icon_path": None,
            "project_id": None 
        }
        
        try:
            with zipfile.ZipFile(jar_path, 'r') as z:
                if "fabric.mod.json" in z.namelist():
                    data = json.load(z.open("fabric.mod.json"))
                    meta["name"] = data.get("name", meta["filename"])
                    meta["version"] = data.get("version", "")
                    
                    # Authors
                    authors = data.get("authors", [])
                    if isinstance(authors, list) and authors:
                        meta["author"] = authors[0] if isinstance(authors[0], str) else authors[0].get("name", "Unknown")
                    elif isinstance(authors, str):
                        meta["author"] = authors

                    # Attempt to find Modrinth Project ID from metadata
                    # Some mods put it in "custom" -> "modrinth" or "contact"
                    contact = data.get("contact", {})
                    if "modrinth" in contact:
                        # Sometimes this is a URL, sometimes an ID
                        val = contact["modrinth"]
                        if "modrinth.com/mod/" in val:
                            meta["project_id"] = val.split("/")[-1]
                        else:
                            meta["project_id"] = val
                    
                    if not meta["project_id"]:
                        custom = data.get("custom", {})
                        if "modrinth" in custom:
                            meta["project_id"] = custom["modrinth"]

                    # Extract Icon
                    icon_file = data.get("icon")
                    if icon_file:
                        if isinstance(icon_file, dict):
                            icon_file = icon_file.get("128x") or icon_file.get("64x") or list(icon_file.values())[0]
                        
                        if icon_file and icon_file in z.namelist():
                            ext = os.path.splitext(icon_file)[1]
                            if not ext: ext = ".png"
                            safe_id = data.get("id", meta["name"]).replace(" ", "_").lower()
                            cached_icon_name = f"{safe_id}{ext}"
                            cached_path = os.path.join(self.mod_icon_cache, cached_icon_name)
                            
                            with z.open(icon_file) as source, open(cached_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                            
                            meta["icon_path"] = cached_path

        except Exception as e:
            print(f"Failed to read metadata for {jar_path}: {e}")
        
        return meta

    def install_modrinth_pack(self):
        name = self.instance_data['name']
        instance_dir = os.path.join(GAME_DIR, "instances", name)
        
        mp_url = self.instance_data.get('modpack_url')
        if not mp_url:
            self.progress.emit("Error: No Modpack URL found.")
            return

        self.progress.emit("Downloading Modrinth Pack...")
        pack_zip_path = os.path.join(instance_dir, "modpack.mrpack")
        if not self.download_url(mp_url, pack_zip_path):
            raise Exception("Failed to download modpack file.")

        self.progress.emit("Reading modpack manifest...")
        downloaded_mods_metadata = []

        try:
            with zipfile.ZipFile(pack_zip_path, 'r') as z:
                with z.open("modrinth.index.json") as f:
                    manifest = json.load(f)
                
                # --- NEW: Extract Dependencies (Loader & Game Version) ---
                deps = manifest.get("dependencies", {})
                print(deps)
                # 1. Sync Minecraft Version
                if "minecraft" in deps:
                    self.instance_data["version"] = deps["minecraft"]
                
                # 2. Sync Loader Version
                if "fabric-loader" in deps:
                    self.instance_data["modloader"] = "Fabric"
                    self.instance_data["fabric_version"] = deps["fabric-loader"]
                    print(self.instance_data)
                    # Also set generic field for compatibility
                    self.instance_data["loader_version"] = deps["fabric-loader"]
                    self.progress.emit(f"Set Fabric Loader to {deps['fabric-loader']}")
                    
                elif "forge" in deps:
                    self.instance_data["modloader"] = "Forge"
                    self.instance_data["loader_version"] = deps["forge"]
                # ---------------------------------------------------------

                files = manifest.get("files", [])
                total = len(files)
                self.progress.emit(f"Found {total} mods to download.")
                
                for i, file_info in enumerate(files):
                    if self._should_stop: return
                    
                    path = file_info["path"] 
                    downloads = file_info["downloads"]
                    
                    if not downloads: continue
                    
                    dl_url = downloads[0]
                    dest_path = os.path.join(instance_dir, path)
                    
                    self.progress.emit(f"[{i+1}/{total}] Downloading {os.path.basename(path)}...")
                    if self.download_url(dl_url, dest_path):
                        # 1. Extract metadata from the Jar
                        mod_meta = self.extract_jar_metadata(dest_path)
                        mod_meta["filenames"] = [os.path.basename(dest_path)]
                        
                        # 2. Extract Project ID from URL if missing
                        if not mod_meta.get("project_id") and "cdn.modrinth.com/data/" in dl_url:
                            try:
                                parts = dl_url.split("/")
                                if "data" in parts:
                                    data_index = parts.index("data")
                                    if len(parts) > data_index + 1:
                                        mod_meta["project_id"] = parts[data_index + 1]
                            except Exception as e:
                                print(f"Could not parse project ID from URL {dl_url}: {e}")
                        
                        downloaded_mods_metadata.append(mod_meta)

                # Overrides (Config files, etc.)
                for zip_info in z.infolist():
                    if zip_info.filename.startswith("overrides/"):
                        target_name = zip_info.filename[len("overrides/"):]
                        if not target_name: continue
                        target_path = os.path.join(instance_dir, target_name)
                        if zip_info.is_dir():
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with z.open(zip_info) as source, open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                                
            self.progress.emit("Modpack files installed.")
            
            # SAVE METADATA TO INSTANCE
            self.instance_data["mod_data"] = downloaded_mods_metadata
            self.instance_data["mod_count"] = len(downloaded_mods_metadata)
            
        except Exception as e:
            raise Exception(f"Failed to process modpack: {e}")
        finally:
            if os.path.exists(pack_zip_path):
                os.remove(pack_zip_path)

        self.install_vanilla_or_fabric()

    def install_vanilla_or_fabric(self):
        self.progress.emit("Setting up core game files...")
        name = self.instance_data['name']
        version = self.instance_data['version']
        modloader = self.instance_data.get('modloader', 'Vanilla')
        
        # Ensure directory exists
        instance_dir = os.path.join(GAME_DIR, "instances", name)
        os.makedirs(instance_dir, exist_ok=True)
        
        scripts_dir = os.path.join(BASE_DIR, "scripts")
        
        if modloader == "Fabric":
            self.progress.emit(f"Installing Fabric for {version}...")
            # Default fabric version if not specified
            fabric_ver = self.instance_data.get('fabric_version', 'latest')
            script = os.path.join(scripts_dir, "install_fabric.sh")
            
            if os.path.exists(script):
                self.execute_process([script, version, fabric_ver, self.java_path])
            else:
                self.progress.emit(f"Error: Script not found at {script}")

        elif modloader == "Vanilla":
            self.progress.emit(f"Downloading Vanilla {version}...")
            script = os.path.join(scripts_dir, "download_vanilla.sh")
            
            if os.path.exists(script):
                self.execute_process([script, version, self.java_path])
            else:
                self.progress.emit(f"Error: Script not found at {script}")

# ============================
# FULL MANAGE MODS PAGE (DROP-IN)
# Includes:
# - ToggleSwitch (iOS style)
# - ModRow with real logic:
#   - toggle renames .disabled
#   - delete removes files + entry
#   - settings menu: update check + update + open folder + open modrinth
# - ManageModsPage with persistence into LauncherV2.instances_data + save_config()
# ============================

import os, sys, re, subprocess, threading, json
from urllib.parse import urljoin

# If you don't already have requests installed, install it or replace with urllib
import requests

from PyQt5.QtCore import (
    Qt, QSize, QTimer, pyqtSignal, QObject, QThread, QPoint
)
from PyQt5.QtGui import (
    QIcon, QPixmap, QPainter, QPainterPath, QCursor
)
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,
    QLineEdit, QStackedWidget, QScrollArea, QMessageBox, QCheckBox,
    QMenu, QAction, QDialog, QTextEdit
)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication

# ---------------------------
# EXPECTED GLOBALS in your project:
# - GAME_DIR
# - PROJECT_DIR
# - ICONS_DIR
# If you have different names, adjust below.
# ---------------------------


class ToggleSwitch(QCheckBox):
    """Custom iOS-style toggle switch using QSS."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(50, 28)
        self.setStyleSheet("""
            QCheckBox { spacing: 0px; }
            QCheckBox::indicator {
                width: 46px; height: 24px;
                border-radius: 12px;
                background-color: #3f3f46; /* Zinc-700 */
                border: 2px solid #3f3f46;
            }
            QCheckBox::indicator:checked {
                background-color: #059669; /* Emerald-600 */
                border: 2px solid #059669;
            }
            QCheckBox::indicator:unchecked:hover { background-color: #52525b; }
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.white)

        if self.isChecked():
            painter.drawEllipse(26, 4, 20, 20)
        else:
            painter.drawEllipse(4, 4, 20, 20)

        painter.end()


# ---------------------------
# Modrinth Workers
# ---------------------------

class ModrinthUpdateChecker(QObject):
    updateCheckComplete = pyqtSignal(bool, str)  # has_update, latest_version
    finished = pyqtSignal()

    def __init__(self, project_id, current_version, mc_version, loader):
        super().__init__()
        self.project_id = project_id
        self.current_version = current_version or ""
        self.mc_version = mc_version or ""
        self.loader = (loader or "").lower().strip()
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def check(self):
        try:
            if self._should_stop:
                return

            if not self.project_id or str(self.project_id).lower() in ["unknown", "", "none", "null"]:
                self.updateCheckComplete.emit(False, "")
                return

            if not self.current_version or str(self.current_version).lower() in ["unknown", "", "none", "null"]:
                self.updateCheckComplete.emit(False, "")
                return

            url = f"https://api.modrinth.com/v2/project/{self.project_id}/version"
            params = {}
            if self.mc_version:
                params["game_versions[]"] = self.mc_version
            if self.loader:
                params["loaders[]"] = self.loader

            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                self.updateCheckComplete.emit(False, "")
                return

            versions = resp.json() or []
            if not versions:
                self.updateCheckComplete.emit(False, "")
                return

            strict = [
                v for v in versions
                if (not self.mc_version or self.mc_version in v.get("game_versions", [])) and
                   (not self.loader or self.loader in v.get("loaders", []))
            ]
            if not strict:
                self.updateCheckComplete.emit(False, "")
                return

            latest = strict[0]
            latest_num = latest.get("version_number", "")
            has_update = bool(latest_num and latest_num != self.current_version)

            self.updateCheckComplete.emit(has_update, latest_num)

        except Exception:
            self.updateCheckComplete.emit(False, "")
        finally:
            self.finished.emit()


class ModrinthModUpdater(QObject):
    progress = pyqtSignal(str)
    complete = pyqtSignal(bool, str, dict)  # success, msg, updated_mod_data
    finished = pyqtSignal()

    def __init__(self, mod_data, mods_dir, mc_version, loader):
        super().__init__()
        self.mod_data = mod_data
        self.mods_dir = mods_dir
        self.mc_version = mc_version or ""
        self.loader = (loader or "").lower().strip()
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        try:
            project_id = self.mod_data.get("project_id", "")
            if not project_id or str(project_id).lower() in ["unknown", "", "none", "null"]:
                self.complete.emit(False, "Unknown project_id", self.mod_data)
                return

            self.progress.emit("Fetching latest version info…")

            url = f"https://api.modrinth.com/v2/project/{project_id}/version"
            params = {}
            if self.mc_version:
                params["game_versions[]"] = self.mc_version
            if self.loader:
                params["loaders[]"] = self.loader

            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                self.complete.emit(False, "Failed to fetch versions", self.mod_data)
                return

            versions = resp.json() or []
            strict = [
                v for v in versions
                if (not self.mc_version or self.mc_version in v.get("game_versions", [])) and
                   (not self.loader or self.loader in v.get("loaders", []))
            ]
            if not strict:
                self.complete.emit(False, "No strictly matching versions found", self.mod_data)
                return

            latest = strict[0]
            new_version = latest.get("version_number", "")

            files = latest.get("files", []) or []
            if not files:
                self.complete.emit(False, "No downloadable files on latest version", self.mod_data)
                return

            primary = next((f for f in files if f.get("primary")), files[0])
            download_url = primary.get("url")
            filename = primary.get("filename")
            if not download_url or not filename:
                self.complete.emit(False, "Bad download file metadata", self.mod_data)
                return

            if self._should_stop:
                self.complete.emit(False, "Cancelled", self.mod_data)
                return

            os.makedirs(self.mods_dir, exist_ok=True)

            self.progress.emit(f"Downloading v{new_version}…")
            temp_path = os.path.join(self.mods_dir, f".temp_{filename}")
            r = requests.get(download_url, stream=True, timeout=30)
            r.raise_for_status()

            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if self._should_stop:
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
                        self.complete.emit(False, "Cancelled", self.mod_data)
                        return
                    if chunk:
                        f.write(chunk)

            self.progress.emit("Installing update…")

            # remove old files
            old_files = self.mod_data.get("filenames", []) or []
            for old in old_files:
                p = os.path.join(self.mods_dir, old)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

            # move new file
            final_path = os.path.join(self.mods_dir, filename)
            os.replace(temp_path, final_path)

            # update mod_data
            self.mod_data["filenames"] = [filename]
            self.mod_data["version"] = new_version
            self.mod_data["enabled"] = True

            self.complete.emit(True, f"Updated to v{new_version}", self.mod_data)

        except Exception as e:
            self.complete.emit(False, f"Update failed: {e}", self.mod_data)
        finally:
            self.finished.emit()


# ---------------------------
# ModRow
# ---------------------------

class ModRow(QFrame):
    """A single row representing an installed mod."""
    def __init__(self, mod_data, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data or {}
        self.setObjectName("ModRow")
        
        # 🔥 CHANGED: Use setMinimumHeight instead of fixed, allows growth
        self.setFixedHeight(80) 
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._check_thread = None
        self._check_worker = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 1. Toggle
        self.toggle = ToggleSwitch()
        self.toggle.setChecked(self.mod_data.get("enabled", True))
        self.toggle.toggled.connect(self.on_toggle_clicked)
        layout.addWidget(self.toggle)
        
        # 2. SPACER
        layout.addSpacing(16)

        # 3. Icon (Loaded from cache if available)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(48, 48)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        
        icon_path = self.mod_data.get("icon_path")
        if icon_path and os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(48, 48, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            rounded = QPixmap(48, 48)
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0, 0, 48, 48, 8, 8)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pix)
            painter.end()
            self.icon_lbl.setPixmap(rounded)
            self.icon_lbl.setStyleSheet("background: transparent;")
        else:
            nameish = (self.mod_data.get("title") or self.mod_data.get("name") or "?")
            colors = ["#7c3aed", "#db2777", "#ea580c", "#059669", "#2563eb"]
            color = colors[len(nameish) % len(colors)]
            self.icon_lbl.setText(nameish[:1].upper())
            self.icon_lbl.setStyleSheet(f"""
                background-color: {color};
                color: white;
                font-weight: bold;
                font-size: 20px;
                border-radius: 8px;
            """)
            
        layout.addWidget(self.icon_lbl)

        # 4. Text Info
        text_lay = QVBoxLayout()
        text_lay.setSpacing(4)

        title_text = self.mod_data.get("title") or self.mod_data.get("name", "Unknown Mod")
        self.title_lbl = QLabel(title_text)
        self.title_lbl.setWordWrap(True) # 🔥 CHANGED: Allow text to wrap
        self.title_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background: transparent;")

        sub_lay = QHBoxLayout()
        sub_lay.setSpacing(8)

        author = QLabel(f"by {self.mod_data.get('author', 'Unknown')}")
        self.ver_lbl = QLabel(f"v{self.mod_data.get('version', 'Unknown')}")
        
        muted = "color: #a1a1aa; font-size: 12px; background: transparent;"
        author.setStyleSheet(muted)
        self.ver_lbl.setStyleSheet(muted)
        dot1 = QLabel("•"); dot1.setStyleSheet(muted)

        sub_lay.addWidget(author)
        sub_lay.addWidget(dot1)
        sub_lay.addWidget(self.ver_lbl)
        sub_lay.addStretch()

        text_lay.addWidget(self.title_lbl)
        text_lay.addLayout(sub_lay)

        layout.addLayout(text_lay, 1)

        # 5. Actions (Always Visible)
        self.actions_frame = QFrame()
        act_lay = QHBoxLayout(self.actions_frame)
        act_lay.setContentsMargins(0, 0, 0, 0)
        act_lay.setSpacing(8)

        # UPDATE BUTTON
        self.btn_update = QPushButton()
        self.btn_update.setFixedSize(36, 36)
        self.btn_update.setObjectName("ActionBtn")
        self.btn_update.setToolTip("Download New Version") # 🔥 CHANGED: Tooltip
        update_icon_path = os.path.join(ICONS_DIR, "checkupdate.svg")
        self.set_svg_icon(self.btn_update, update_icon_path, size=20)
        self.btn_update.clicked.connect(self._run_update)

        # DELETE BUTTON
        self.btn_delete = QPushButton()
        self.btn_delete.setFixedSize(36, 36)
        self.btn_delete.setObjectName("DeleteBtn")
        self.btn_delete.setToolTip("Delete Mod") # 🔥 CHANGED: Tooltip
        delete_icon_path = os.path.join(ICONS_DIR, "delete.svg")
        self.set_svg_icon(self.btn_delete, delete_icon_path, size=20, color="#ef4444")
        self.btn_delete.clicked.connect(self.delete_mod)

        act_lay.addWidget(self.btn_update)
        act_lay.addWidget(self.btn_delete)

        layout.addWidget(self.actions_frame)
        # 🔥 CHANGED: Removed self.actions_frame.hide() so they are always visible

        self.setStyleSheet("#ModRow { background-color: #27272a; border: 1px solid #3f3f46; border-radius: 12px; }")
        
        # initial disabled style
        self.apply_enabled_style(self.toggle.isChecked())

        # auto update check
        QTimer.singleShot(150, self.start_update_check)

    def set_svg_icon(self, btn, path, size=18, color="#ffffff"):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f: svg = f.read()
            svg = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', f'fill="{color}"', svg)
            renderer = QSvgRenderer(bytearray(svg, encoding="utf-8"))
            pixmap = QPixmap(size*2, size*2)
            pixmap.fill(Qt.transparent)
            p = QPainter(pixmap)
            renderer.render(p)
            p.end()
            pixmap.setDevicePixelRatio(2.0)
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(size, size))
        else:
            btn.setText("?")

    # 🔥 CHANGED: Only background color changes on hover, buttons stay visible
    def enterEvent(self, event):
        self.setStyleSheet("#ModRow { background-color: #27272a; border: 1px solid #3f3f46; border-radius: 12px; }")
        super().enterEvent(event)

        
    def _run_update(self):
        page = self._page()
        if page:
            page.update_single_mod(self)

    # ---- helpers ----

    def _page(self):
        p = self.parent()
        while p and not isinstance(p, ManageModsPage):
            p = p.parent()
        return p

    def _mods_dir(self):
        page = self._page()
        if not page:
            return ""
        inst_name = page.current_instance_name
        if not inst_name:
            return ""
        return os.path.join(GAME_DIR, "instances", inst_name, "mods")

    def _instance_version_loader(self):
        page = self._page()
        inst = page.current_instance if page else {}
        mc_version = (inst.get("version") or "").strip()
        loader = (inst.get("modloader") or inst.get("loader") or "").strip()
        return mc_version, loader

    # ---- style ----

    def apply_enabled_style(self, enabled: bool):
        if enabled:
            self.title_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background: transparent;")
        else:
            self.title_lbl.setStyleSheet(
                "color: #d4d4d8; font-weight: bold; font-size: 14px; background: transparent; text-decoration: line-through;"
            )

    # ---- toggle logic (.disabled rename) ----

    def on_toggle_clicked(self, checked: bool):
        mods_dir = self._mods_dir()
        if not mods_dir:
            self._revert_toggle(checked, "No instance mods directory.")
            return
        os.makedirs(mods_dir, exist_ok=True)

        filenames = self.mod_data.get("filenames", []) or []
        if not filenames:
            self.mod_data["enabled"] = checked
            self.apply_enabled_style(checked)
            self._persist()
            return

        # find an actual existing file
        existing = None
        for fn in filenames:
            if os.path.exists(os.path.join(mods_dir, fn)):
                existing = fn
                break
        if existing is None:
            existing = filenames[0]

        old_path = os.path.join(mods_dir, existing)

        if checked:
            new_name = existing[:-9] if existing.endswith(".disabled") else existing
        else:
            new_name = existing if existing.endswith(".disabled") else (existing + ".disabled")

        new_path = os.path.join(mods_dir, new_name)

        if old_path != new_path and os.path.exists(old_path):
            try:
                os.rename(old_path, new_path)
            except Exception as e:
                self._revert_toggle(checked, f"Could not rename:\n{e}")
                return

        # update mod_data
        new_files = filenames[:]
        if existing in new_files:
            new_files[new_files.index(existing)] = new_name
        elif new_files:
            new_files[0] = new_name

        self.mod_data["filenames"] = new_files
        self.mod_data["enabled"] = checked
        self.apply_enabled_style(checked)
        self._persist()

    def _revert_toggle(self, checked: bool, msg: str):
        self.toggle.blockSignals(True)
        self.toggle.setChecked(not checked)
        self.toggle.blockSignals(False)
        QMessageBox.warning(self, "Toggle failed", msg)

    # ---- delete logic ----

    def delete_mod(self):
        title = self.mod_data.get("title") or self.mod_data.get("name", "this mod")
        if QMessageBox.question(self, "Remove Mod", f"Remove '{title}'?") != QMessageBox.Yes:
            return

        mods_dir = self._mods_dir()
        if mods_dir:
            filenames = self.mod_data.get("filenames", []) or []
            for fn in filenames:
                p = os.path.join(mods_dir, fn)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

        page = self._page()
        if page:
            page.remove_mod_from_instance(self.mod_data)

    # ---- update check ----

    def start_update_check(self):
        project_id = self.mod_data.get("project_id", "")
        current_version = self.mod_data.get("version", "")
        if not project_id or str(project_id).lower() in ["unknown", "", "none", "null"]:
            return
        if not current_version or str(current_version).lower() in ["unknown", "", "none", "null"]:
            return

        mc_version, loader = self._instance_version_loader()

        self._cleanup_check_thread()

        self._check_thread = QThread()
        self._check_worker = ModrinthUpdateChecker(project_id, current_version, mc_version, loader)
        self._check_worker.moveToThread(self._check_thread)

        self._check_thread.started.connect(self._check_worker.check)
        self._check_worker.updateCheckComplete.connect(self.on_update_check_complete)
        self._check_worker.finished.connect(self._check_thread.quit)
        self._check_thread.finished.connect(self._cleanup_check_thread)
        self._check_thread.start()

    def _cleanup_check_thread(self):
        if self._check_worker:
            try:
                self._check_worker.stop()
            except Exception:
                pass
        if self._check_thread and self._check_thread.isRunning():
            self._check_thread.quit()
            self._check_thread.wait(1500)

        if self._check_thread:
            self._check_thread.deleteLater()
        if self._check_worker:
            self._check_worker.deleteLater()

        self._check_thread = None
        self._check_worker = None

    def on_update_check_complete(self, has_update: bool, latest_version: str):
        self.mod_data["_has_update"] = bool(has_update)
        self.mod_data["_latest_version"] = latest_version or ""

    # ---- settings menu ----

    def open_actions_menu(self):
        menu = QMenu(self)

        has_update = bool(self.mod_data.get("_has_update"))
        latest = self.mod_data.get("_latest_version", "")

        act_update = QAction(f"Update to v{latest}" if latest else "Update", self)
        act_update.setEnabled(has_update)
        act_update.triggered.connect(self._run_update)
        menu.addAction(act_update)

        menu.addSeparator()

        act_open_folder = QAction("Open mods folder", self)
        act_open_folder.triggered.connect(self._open_mods_folder)
        menu.addAction(act_open_folder)

        project_id = self.mod_data.get("project_id", "")
        if project_id and str(project_id).lower() not in ["unknown", "", "none", "null"]:
            act_modrinth = QAction("Open on Modrinth", self)
            act_modrinth.triggered.connect(lambda: __import__("webbrowser").open(f"https://modrinth.com/mod/{project_id}"))
            menu.addAction(act_modrinth)

        menu.exec_(QCursor.pos())

    def _open_mods_folder(self):
        page = self._page()
        if page:
            page.open_mods_folder()


    # ---- persist ----

    def _persist(self):
        page = self._page()
        if page:
            page.persist_mod_change(self.mod_data)


# ---------------------------
# ManageModsPage
# ---------------------------

class ManageModsPage(QWidget):
    back_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ManageModsPage")
        self.current_instance = {}
        self.current_instance_name = ""
        self._active_update_refs = []  # keep threads/workers/dialogs alive
        self.init_ui()
        self.apply_styles()

    def _launcher(self):
        # The top-level window is LauncherV2
        return self.window()

    def init_ui(self):
        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # --- LEFT SIDEBAR ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(280)
        side_lay = QVBoxLayout(self.sidebar)
        side_lay.setContentsMargins(24, 24, 24, 24)
        side_lay.setSpacing(20)

        btn_back = QPushButton("← Back to Launcher")
        btn_back.setObjectName("LinkButton")
        btn_back.setCursor(Qt.PointingHandCursor)
        btn_back.clicked.connect(self.go_back)
        side_lay.addWidget(btn_back)

        header_row = QHBoxLayout()
        self.inst_icon = QLabel()
        self.inst_icon.setFixedSize(48, 48)
        self.inst_icon.setAlignment(Qt.AlignCenter)
        self.inst_icon.setStyleSheet("background: #3f3f46; border-radius: 8px;")

        info_col = QVBoxLayout()
        self.inst_name = QLabel("Instance Name")
        self.inst_name.setStyleSheet("color: white; font-weight: bold; font-size: 16px;")
        self.inst_count = QLabel("0 mods installed")
        self.inst_count.setStyleSheet("color: #71717a; font-size: 12px;")
        info_col.addWidget(self.inst_name)
        info_col.addWidget(self.inst_count)

        header_row.addWidget(self.inst_icon)
        header_row.addLayout(info_col)
        side_lay.addLayout(header_row)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet("background: #27272a;")
        side_lay.addWidget(div)

        side_lay.addStretch()

        # Open folder bottom row
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.btn_folder = QPushButton()
        self.btn_folder.setObjectName("IconButton")
        self.btn_folder.setFixedSize(44, 44)
        self.btn_folder.setCursor(Qt.PointingHandCursor)
        self.btn_folder.setToolTip("Open Mods Folder")
        self.btn_folder.clicked.connect(self.open_mods_folder)

        lbl_folder = QLabel("Open Mods Folder")
        lbl_folder.setStyleSheet("color: #a1a1aa; font-size: 13px; font-weight: 600;")

        bottom_row.addWidget(self.btn_folder)
        bottom_row.addWidget(lbl_folder)
        bottom_row.addStretch()

        side_lay.addLayout(bottom_row)

        main_lay.addWidget(self.sidebar)

        # --- RIGHT CONTENT ---
        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(0)

        tabs_frame = QFrame()
        tabs_frame.setObjectName("TabsHeader")
        tabs_lay = QHBoxLayout(tabs_frame)
        tabs_lay.setContentsMargins(32, 0, 32, 0)
        tabs_lay.setSpacing(24)

        self.btn_tab_installed = QPushButton("Installed")
        self.btn_tab_installed.setObjectName("TabButtonActive")
        self.btn_tab_installed.clicked.connect(lambda: self.switch_tab("installed"))

        self.btn_tab_browse = QPushButton("Browse")
        self.btn_tab_browse.setObjectName("TabButtonInactive")
        self.btn_tab_browse.clicked.connect(lambda: self.switch_tab("browse"))

        tabs_lay.addWidget(self.btn_tab_installed)
        tabs_lay.addWidget(self.btn_tab_browse)
        tabs_lay.addStretch()
        content_lay.addWidget(tabs_frame)
        
        # Tool Bar (Search + Sort)
        tool_frame = QFrame()
        tool_lay = QHBoxLayout(tool_frame)
        tool_lay.setContentsMargins(32, 24, 32, 10)
        tool_lay.setSpacing(16)

        self.inp_search = QLineEdit()
        self.inp_search.setPlaceholderText("Search...")
        self.inp_search.setObjectName("SearchInput")
        self.inp_search.returnPressed.connect(self.trigger_search) # Connect Enter key
        tool_lay.addWidget(self.inp_search, 1)

        # Sort Dropdown
        from PyQt5.QtWidgets import QComboBox
        self.combo_sort = QComboBox()
        self.combo_sort.addItems(["Relevance", "Downloads", "Newest", "Updated"])
        self.combo_sort.setFixedSize(120, 42)
        # Quick styling for combo
        self.combo_sort.setStyleSheet("""
            QComboBox { 
                background: #27272a; color: white; border: 1px solid #3f3f46; 
                border-radius: 8px; padding-left: 10px; 
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #27272a; color: white; selection-background-color: #059669; }
        """)
        self.combo_sort.currentIndexChanged.connect(self.trigger_search)
        tool_lay.addWidget(self.combo_sort)

        content_lay.addWidget(tool_frame)

        self.stack = QStackedWidget()

        # Page 1: Installed (Existing code)
        page_installed = QWidget()
        pi_lay = QVBoxLayout(page_installed)
        pi_lay.setContentsMargins(32, 10, 32, 32)
        scroll_inst = QScrollArea()
        scroll_inst.setWidgetResizable(True)
        scroll_inst.setFrameShape(QFrame.NoFrame)
        scroll_inst.setStyleSheet("background: transparent;")
        self.mods_list_widget = QWidget()
        self.mods_layout = QVBoxLayout(self.mods_list_widget)
        self.mods_layout.setAlignment(Qt.AlignTop)
        self.mods_layout.setSpacing(12)
        scroll_inst.setWidget(self.mods_list_widget)
        pi_lay.addWidget(scroll_inst)
        self.stack.addWidget(page_installed)

        # Page 2: Browse (Replaces placeholder)
        page_browse = QWidget()
        pb_lay = QVBoxLayout(page_browse)
        pb_lay.setContentsMargins(32, 10, 32, 32)
        
        scroll_browse = QScrollArea()
        scroll_browse.setWidgetResizable(True)
        scroll_browse.setFrameShape(QFrame.NoFrame)
        scroll_browse.setStyleSheet("background: transparent;")
        
        self.browse_container = QWidget()
        self.browse_grid = QGridLayout(self.browse_container)
        self.browse_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.browse_grid.setSpacing(20)
        
        scroll_browse.setWidget(self.browse_container)
        pb_lay.addWidget(scroll_browse)
        self.stack.addWidget(page_browse)

        content_lay.addWidget(self.stack, 1)
        main_lay.addWidget(content, 1)
        self.switch_tab("installed")

    # --------------------------
    # Public load
    # --------------------------

    def load_instance_data(self, instance_data):
        self.current_instance = instance_data or {}
        self.current_instance_name = self.current_instance.get("name", "")

        name = self.current_instance.get("name", "Unknown")
        self.inst_name.setText(name)

        # Icon handling: match your launcher logic
        image = self.current_instance.get("image")
        image_path = None

        if isinstance(image, dict):
            image_path = image.get("saved_path")
        elif isinstance(image, str):
            image_path = image

        if image_path and not os.path.isabs(image_path):
            image_path = os.path.join(PROJECT_DIR, image_path)

        if image_path and os.path.exists(image_path) and image_path != "🟩":
            pixmap = QPixmap(image_path).scaled(
                48, 48, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            rounded = self.rounded_pixmap(pixmap, radius=8)
            self.inst_icon.setPixmap(rounded)
            self.inst_icon.setStyleSheet("background: transparent;")
            self.inst_icon.setText("")
        else:
            colors = ["#7c3aed", "#db2777", "#ea580c", "#059669", "#2563eb"]
            color = colors[len(name) % len(colors)]
            self.inst_icon.setText(name[0].upper())
            self.inst_icon.setStyleSheet(
                f"background: {color}; border-radius: 8px; font-size: 24px; font-weight: bold; color: white;"
            )
            self.inst_icon.setPixmap(QPixmap())

        mod_data = self.current_instance.get("mod_data", []) or []
        self.render_mod_rows(mod_data)

        # set folder icon if launcher has helper
        launcher = self._launcher()
        if launcher and hasattr(launcher, "load_svg_icon"):
            folder_icon_path = os.path.join(ICONS_DIR, "folder.svg")
            self.btn_folder.setIcon(launcher.load_svg_icon(folder_icon_path, size=20, color="#ffffff"))
            self.btn_folder.setIconSize(QSize(20, 20))

        # update category counts (simple)
        self.refresh_category_counts()

    # --------------------------
    # Rendering / filtering
    # --------------------------

    def render_mod_rows(self, mod_data):
        # clear layout
        while self.mods_layout.count():
            item = self.mods_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.inst_count.setText(f"{len(mod_data)} mods installed")

        if not mod_data:
            lbl = QLabel("No mods found.")
            lbl.setStyleSheet("color: #52525b; margin-top: 20px;")
            lbl.setAlignment(Qt.AlignCenter)
            self.mods_layout.addWidget(lbl)
            return

        for mod in mod_data:
            row = ModRow(mod, parent=self)
            self.mods_layout.addWidget(row)

        self.apply_search_filter(self.inp_search.text().strip())

    def apply_search_filter(self, text: str):
        text = (text or "").strip().lower()
        for i in range(self.mods_layout.count()):
            w = self.mods_layout.itemAt(i).widget()
            if not w or not isinstance(w, ModRow):
                continue
            if not text:
                w.show()
                continue
            title = (w.mod_data.get("title") or w.mod_data.get("name") or "").lower()
            author = (w.mod_data.get("author") or "").lower()
            cat = (w.mod_data.get("category") or "").lower()
            w.setVisible(text in title or text in author or text in cat)

    def refresh_category_counts(self):
        # Optional: you can recompute categories dynamically later.
        pass

    # --------------------------
    # Persistence back to LauncherV2
    # --------------------------

    def persist_mod_change(self, updated_mod_data: dict):
        launcher = self._launcher()
        if not launcher or not hasattr(launcher, "instances_data"):
            return

        inst_name = self.current_instance_name
        if not inst_name:
            return

        inst = launcher.instances_data.get(inst_name, {})
        mods = inst.get("mod_data", []) or []

        uid = updated_mod_data.get("id")
        title = updated_mod_data.get("title") or updated_mod_data.get("name")

        replaced = False
        for i, m in enumerate(mods):
            if uid and m.get("id") == uid:
                mods[i] = updated_mod_data
                replaced = True
                break

        if not replaced:
            for i, m in enumerate(mods):
                if (m.get("title") or m.get("name")) == title:
                    mods[i] = updated_mod_data
                    replaced = True
                    break

        inst["mod_data"] = mods
        inst["mods"] = len(mods)
        inst["mod_count"] = len(mods)

        launcher.instances_data[inst_name] = inst
        launcher.save_config()

        self.current_instance = inst
        self.inst_count.setText(f"{len(mods)} mods installed")

    def remove_mod_from_instance(self, mod_data: dict):
        launcher = self._launcher()
        if not launcher or not hasattr(launcher, "instances_data"):
            return

        inst_name = self.current_instance_name
        if not inst_name:
            return

        inst = launcher.instances_data.get(inst_name, {})
        mods = inst.get("mod_data", []) or []

        uid = mod_data.get("id")
        title = mod_data.get("title") or mod_data.get("name")

        new_mods = []
        for m in mods:
            if uid and m.get("id") == uid:
                continue
            if (not uid) and ((m.get("title") or m.get("name")) == title):
                continue
            new_mods.append(m)

        inst["mod_data"] = new_mods
        inst["mods"] = len(new_mods)
        inst["mod_count"] = len(new_mods)

        launcher.instances_data[inst_name] = inst
        launcher.save_config()

        self.current_instance = inst
        self.render_mod_rows(new_mods)

    # --------------------------
    # Update flow (single mod)
    # --------------------------

    # --------------------------
    # Update flow (Dialog based)
    # --------------------------

    def update_single_mod(self, row_widget: ModRow):
        """Step 1: Fetch versions"""
        inst = self.current_instance or {}
        mc_version = (inst.get("version") or "").strip()
        loader = (inst.get("modloader") or inst.get("loader") or "").strip()
        project_id = row_widget.mod_data.get("project_id")
        
        if not project_id:
            QMessageBox.warning(self, "Error", "Cannot update: Missing Project ID.")
            return

        # Show a quick loading indicator (could be a dialog or status bar)
        self.loading_dlg = QProgressDialog("Fetching versions...", "Cancel", 0, 0, self)
        self.loading_dlg.setWindowModality(Qt.WindowModal)
        self.loading_dlg.show()
        
        # Start Fetch Worker
        self._fetch_thread = QThread()
        self._fetch_worker = ModrinthVersionFetcher(project_id, mc_version, loader)
        self._fetch_worker.moveToThread(self._fetch_thread)
        
        # Connect signals
        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_worker.versions_ready.connect(
            lambda v: self.on_versions_fetched(v, row_widget)
        )
        self._fetch_worker.error.connect(
            lambda e: QMessageBox.warning(self, "Error", f"Failed to fetch versions:\n{e}")
        )
        
        # Cleanup
        self._fetch_worker.versions_ready.connect(self.loading_dlg.close)
        self._fetch_worker.error.connect(self.loading_dlg.close)
        self._fetch_worker.versions_ready.connect(self._fetch_thread.quit)
        self._fetch_worker.error.connect(self._fetch_thread.quit)
        
        self._fetch_thread.start()

    def on_versions_fetched(self, versions, row_widget):
        """Step 2: Show Dialog"""
        if not versions:
            QMessageBox.information(self, "No Updates", "No compatible versions found for this instance.")
            return
            
        current_ver = row_widget.mod_data.get("version", "Unknown")
        
        dlg = VersionSelectDialog(current_ver, versions, self)
        if dlg.exec_() == QDialog.Accepted:
            # User chose a file!
            file_info = dlg.selected_file
            new_ver_num = dlg.selected_version_number
            # Update this line in on_versions_fetched/confirm_selection flow:
            self.install_specific_version(file_info, new_ver_num, row_widget.mod_data, is_new_install=False)

    def go_back(self):
        self.back_clicked.emit()

    def install_specific_version(self, file_info, new_ver_num, mod_data_target, is_new_install=False):
        """
        Reused for both Updates and New Installs.
        """
        inst_name = self.current_instance_name
        mods_dir = os.path.join(GAME_DIR, "instances", inst_name, "mods")
        
        prog = QDialog(self)
        prog.setWindowTitle("Installing")
        prog.setFixedSize(300, 100)
        lay = QVBoxLayout(prog)
        lbl = QLabel(f"Installing {new_ver_num}...")
        lbl.setStyleSheet("color: white;")
        lay.addWidget(lbl)
        prog.show()
        
        self._inst_thread = QThread()
        self._inst_worker = ModrinthInstaller(file_info, new_ver_num, mod_data_target, mods_dir)
        self._inst_worker.moveToThread(self._inst_thread)
        
        def on_finish(success, msg, updated_data):
            prog.close()
            if success:
                # Merge the new file info into our target data
                mod_data_target.update(updated_data)
                
                if is_new_install:
                    # --- FIX START: Download the icon if it's a new install ---
                    icon_url = mod_data_target.get("icon_url")
                    if icon_url:
                        try:
                            # 1. Define cache location
                            icon_cache_dir = os.path.join(GAME_DIR, "cache", "mod_icons")
                            os.makedirs(icon_cache_dir, exist_ok=True)
                            
                            # 2. Determine filename from URL or Project ID
                            ext = os.path.splitext(icon_url)[1]
                            if not ext or len(ext) > 5: ext = ".png"
                            
                            # Use project ID for filename to avoid collisions/weird characters
                            safe_name = mod_data_target.get("project_id", "unknown_mod")
                            save_path = os.path.join(icon_cache_dir, f"{safe_name}{ext}")
                            
                            # 3. Download the image (using requests synchronously here is okay 
                            #    since it's small and we are already in a "finished" callback)
                            print(f"[Icon] Downloading icon from {icon_url}...")
                            r = requests.get(icon_url, timeout=5)
                            if r.status_code == 200:
                                with open(save_path, "wb") as f:
                                    f.write(r.content)
                                # 4. Update the data with the LOCAL path
                                mod_data_target["icon_path"] = save_path
                        except Exception as e:
                            print(f"[Icon] Failed to download icon: {e}")
                    # --- FIX END ---

                    self.add_mod_to_instance(mod_data_target)
                else:
                    self.persist_mod_change(mod_data_target)
                
                QMessageBox.information(self, "Success", f"Installed {mod_data_target.get('title')}")
            else:
                QMessageBox.warning(self, "Failed", msg)
        
        self._inst_thread.started.connect(self._inst_worker.run)
        self._inst_worker.finished.connect(on_finish)
        self._inst_worker.finished.connect(self._inst_thread.quit)
        self._inst_thread.start()

    # --------------------------
    # Folder open
    # --------------------------

    def open_mods_folder(self):
        name = self.current_instance_name or self.current_instance.get("name")
        if not name:
            return

        path = os.path.join(GAME_DIR, "instances", name, "mods")
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create folder:\n{e}")
                return

        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")

    # --------------------------
    # Navigation
    # --------------------------
    def switch_tab(self, tab):
        # 1. Disconnect signals to prevent overlap
        try: self.inp_search.returnPressed.disconnect()
        except: pass
        try: self.inp_search.textChanged.disconnect()
        except: pass

        if tab == "installed":
            self.stack.setCurrentIndex(0)
            self.btn_tab_installed.setObjectName("TabButtonActive")
            self.btn_tab_browse.setObjectName("TabButtonInactive")
            
            self.inp_search.setPlaceholderText("Filter installed mods...")
            self.inp_search.clear() 
            
            # Connect local filter
            self.inp_search.textChanged.connect(self.apply_search_filter)
            self.combo_sort.hide()

        else:
            self.stack.setCurrentIndex(1)
            self.btn_tab_installed.setObjectName("TabButtonInactive")
            self.btn_tab_browse.setObjectName("TabButtonActive")
            
            self.inp_search.setPlaceholderText("Search Modrinth...")
            self.inp_search.clear() # Reset text to empty
            
            # Connect API search
            self.inp_search.returnPressed.connect(self.trigger_search)
            self.combo_sort.show()
            
            # 🔥 FIX: Force a search refresh immediately. 
            # This makes the grid load the default "Popular/Relevant" list 
            # so it matches the empty search bar, effectively "resetting" the view.
            self.trigger_search()

        # Refresh styles
        self.btn_tab_installed.style().unpolish(self.btn_tab_installed)
        self.btn_tab_installed.style().polish(self.btn_tab_installed)
        self.btn_tab_browse.style().unpolish(self.btn_tab_browse)
        self.btn_tab_browse.style().polish(self.btn_tab_browse)

    # --- BROWSE LOGIC ---

    def trigger_search(self):
        query = self.inp_search.text()
        sort_mode = self.combo_sort.currentText().lower()
        
        # Get current instance MC version
        inst = self.current_instance or {}
        mc_ver = inst.get("version", "")
        
        # 1. Clean up old thread if it exists
        if hasattr(self, '_search_thread') and self._search_thread:
            try:
                # Check if valid C++ object exists before calling methods
                if self._search_thread.isRunning():
                    self._search_thread.quit()
                    self._search_thread.wait(100) # Wait briefly, don't freeze
            except RuntimeError:
                # The C++ object was already deleted, ignore
                pass
            
            # Disconnect old signals to prevent overlap
            try: self._search_worker.results_ready.disconnect()
            except: pass
            
            self._search_thread = None

        # Clear Grid
        while self.browse_grid.count():
            item = self.browse_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        # Show loading
        lbl = QLabel("Searching Modrinth...")
        lbl.setStyleSheet("color: #a1a1aa; font-size: 16px;")
        lbl.setAlignment(Qt.AlignCenter)
        self.browse_grid.addWidget(lbl, 0, 0)
        
        # 2. Start New Worker
        self._search_thread = QThread()
        self._search_worker = ModrinthSearchWorker(query, mc_ver, sort_mode)
        self._search_worker.moveToThread(self._search_thread)
        
        # Connect signals
        self._search_thread.started.connect(self._search_worker.run)
        self._search_worker.results_ready.connect(self.display_browse_results)
        self._search_worker.error.connect(lambda e: print("Search error:", e))
        
        # Cleanup logic
        self._search_worker.results_ready.connect(self._search_thread.quit)
        self._search_worker.error.connect(self._search_thread.quit)
        
        # Proper deletion
        self._search_thread.finished.connect(self._search_thread.deleteLater)
        self._search_thread.finished.connect(self._search_worker.deleteLater)
        
        self._search_thread.start()
    def display_browse_results(self, hits):
        # Clear loading label
        while self.browse_grid.count():
            item = self.browse_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        if not hits:
            lbl = QLabel("No results found.")
            lbl.setStyleSheet("color: #a1a1aa;")
            self.browse_grid.addWidget(lbl, 0, 0)
            return

        row, col = 0, 0
        max_cols = 1 # Adjust based on window size if you want
        
        for hit in hits:
            card = ModGridCard(hit)
            card.clicked.connect(self.on_browse_card_clicked)
            self.browse_grid.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def on_browse_card_clicked(self, mod_data):
        """
        1. Fetch versions for this mod (filtered by current instance version).
        2. Show VersionSelectDialog.
        3. Install.
        """
        project_id = mod_data.get("project_id")
        inst = self.current_instance or {}
        mc_version = inst.get("version", "")
        loader = inst.get("modloader", "fabric").lower() 

        # Loading Dialog
        self.loading_dlg = QProgressDialog("Fetching versions...", "Cancel", 0, 0, self)
        self.loading_dlg.setWindowModality(Qt.WindowModal)
        self.loading_dlg.show()

        self._fetch_thread = QThread()
        self._fetch_worker = ModrinthVersionFetcher(project_id, mc_version, loader)
        self._fetch_worker.moveToThread(self._fetch_thread)
        
        # --- CONNECT SIGNALS ---
        self._fetch_thread.started.connect(self._fetch_worker.run) # <--- THIS WAS MISSING
        
        self._fetch_worker.versions_ready.connect(
            lambda v: self.show_install_dialog(v, mod_data)
        )
        # Handle errors too so the dialog doesn't get stuck open
        self._fetch_worker.error.connect(lambda e: print(f"Fetch error: {e}"))
        self._fetch_worker.error.connect(self.loading_dlg.close)

        self._fetch_worker.versions_ready.connect(self.loading_dlg.close)
        self._fetch_worker.versions_ready.connect(self._fetch_thread.quit)
        self._fetch_worker.error.connect(self._fetch_thread.quit)
        
        self._fetch_thread.start()

    def show_install_dialog(self, versions, mod_data):
        if not versions:
            QMessageBox.warning(self, "Incompatible", "No versions found for your Minecraft version.")
            return

        dlg = VersionSelectDialog(current_version=None, versions_list=versions, parent=self)
        
        if dlg.exec_() == QDialog.Accepted:
            file_info = dlg.selected_file
            new_ver_num = dlg.selected_version_number
            
            # --- MAKE SURE THIS DICT HAS 'icon_url' ---
            target_data = {
                "filenames": [], 
                "project_id": mod_data.get("project_id"),
                "title": mod_data.get("title"),
                "author": mod_data.get("author"),
                "icon_url": mod_data.get("icon_url") # <--- CRITICAL LINE
            }
            
            self.install_specific_version(file_info, new_ver_num, target_data, is_new_install=True)

    def install_specific_version(self, file_info, new_ver_num, mod_data_target, is_new_install=False):
        inst_name = self.current_instance_name
        mods_dir = os.path.join(GAME_DIR, "instances", inst_name, "mods")
        
        print(f"\n[DEBUG] Starting install for: {mod_data_target.get('title')}")
        print(f"[DEBUG] Target Data before install: {mod_data_target}")

        prog = QDialog(self)
        prog.setWindowTitle("Installing")
        prog.setFixedSize(300, 100)
        lay = QVBoxLayout(prog)
        lbl = QLabel(f"Installing {new_ver_num}...")
        lbl.setStyleSheet("color: white;")
        lay.addWidget(lbl)
        prog.show()
        
        self._inst_thread = QThread()
        self._inst_worker = ModrinthInstaller(file_info, new_ver_num, mod_data_target, mods_dir)
        self._inst_worker.moveToThread(self._inst_thread)
        
        def on_finish(success, msg, updated_data):
            prog.close()
            if success:
                print(f"[DEBUG] Installer finished successfully.")
                # Merge the new file info into our target data
                mod_data_target.update(updated_data)
                
                if is_new_install:
                    print("[DEBUG] This is a new install. Attempting icon download...")
                    icon_url = mod_data_target.get("icon_url")
                    print(f"[DEBUG] Icon URL from data: {icon_url}")

                    if icon_url:
                        try:
                            # 1. Define cache location
                            icon_cache_dir = os.path.join(GAME_DIR, "cache", "mod_icons")
                            os.makedirs(icon_cache_dir, exist_ok=True)
                            
                            # 2. Determine filename
                            ext = os.path.splitext(icon_url)[1]
                            if not ext or len(ext) > 5: ext = ".png"
                            
                            safe_name = str(mod_data_target.get("project_id", "unknown")).replace("/", "_")
                            save_path = os.path.join(icon_cache_dir, f"{safe_name}{ext}")
                            
                            print(f"[DEBUG] Downloading to: {save_path}")

                            # 3. Download
                            r = requests.get(icon_url, timeout=5)
                            print(f"[DEBUG] Download status code: {r.status_code}")
                            
                            if r.status_code == 200:
                                with open(save_path, "wb") as f:
                                    f.write(r.content)
                                
                                if os.path.exists(save_path):
                                    print(f"[DEBUG] File successfully saved. Size: {os.path.getsize(save_path)} bytes")
                                    # 4. Update the data with the LOCAL path
                                    mod_data_target["icon_path"] = save_path
                                else:
                                    print("[DEBUG] CRITICAL: File write finished but file not found on disk.")
                            else:
                                print(f"[DEBUG] Failed to download icon. HTTP {r.status_code}")
                        except Exception as e:
                            print(f"[DEBUG] Exception during icon download: {e}")
                    else:
                        print("[DEBUG] No icon_url found in mod_data_target.")

                    print(f"[DEBUG] Final data sending to instance: {mod_data_target}")
                    self.add_mod_to_instance(mod_data_target)
                else:
                    self.persist_mod_change(mod_data_target)
                
                QMessageBox.information(self, "Success", f"Installed {mod_data_target.get('title')}")
            else:
                print(f"[DEBUG] Installer failed: {msg}")
                QMessageBox.warning(self, "Failed", msg)
        
        self._inst_thread.started.connect(self._inst_worker.run)
        self._inst_worker.finished.connect(on_finish)
        self._inst_worker.finished.connect(self._inst_thread.quit)
        self._inst_thread.start()

    def add_mod_to_instance(self, new_mod_data):
        launcher = self._launcher()
        inst = launcher.instances_data.get(self.current_instance_name, {})
        mods = inst.get("mod_data", [])
        mods.append(new_mod_data)
        
        inst["mod_data"] = mods
        inst["mod_count"] = len(mods)
        launcher.save_config()
        self.current_instance = inst
        
        # If we are on installed tab, refresh
        self.render_mod_rows(mods)

    # --------------------------
    # SVG helper + rounding
    # --------------------------

    def load_svg_icon(self, path: str, size: int = 18, color: str = "#ffffff") -> QIcon:
        if not path or not os.path.exists(path):
            return QIcon()

        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()

        svg = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', f'fill="{color}"', svg)
        svg = re.sub(r'fill="[^"]+"', f'fill="{color}"', svg)
        svg = re.sub(r'stroke="#[0-9a-fA-F]{3,6}"', f'stroke="{color}"', svg)
        svg = re.sub(r'stroke="[^"]+"', f'stroke="{color}"', svg)

        renderer = QSvgRenderer(bytearray(svg, encoding="utf-8"))

        dpr = QApplication.instance().devicePixelRatio()
        px = int(size * dpr)

        pixmap = QPixmap(px, px)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        pixmap.setDevicePixelRatio(dpr)
        return QIcon(pixmap)

    def rounded_pixmap(self, pixmap: QPixmap, radius: int) -> QPixmap:
        if pixmap.isNull():
            return pixmap

        w, h = pixmap.width(), pixmap.height()
        out = QPixmap(w, h)
        out.fill(Qt.transparent)

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, radius, radius)

        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return out

    # --------------------------
    # Styles
    # --------------------------

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget#ManageModsPage { background: #09090b; }
            QFrame#Sidebar { background: #09090b; border-right: 1px solid #27272a; }
            QFrame#TabsHeader { background: #09090b; border-bottom: 1px solid #27272a; }

            QPushButton#LinkButton { background: transparent; color: #a1a1aa; text-align: left; font-size: 13px; border: none; }
            QPushButton#LinkButton:hover { color: white; }

            QPushButton#CategoryBtn { background: transparent; color: #a1a1aa; border: none; border-radius: 8px; text-align: left; }
            QPushButton#CategoryBtn:hover { background: #27272a; color: white; }
            QPushButton#CategoryBtn:checked { background: #059669; color: white; }

            QPushButton#IconButton {
                background: rgba(63,63,70,0.7);
                color: white;
                border: 1px solid rgba(39,39,42,0.9);
                border-radius: 12px;
                font-weight: 800;
            }
            QPushButton#IconButton:hover { background: rgba(82,82,91,0.9); }

            QPushButton#TabButtonActive { background: transparent; color: white; font-weight: bold; font-size: 14px; border: none; border-bottom: 2px solid #059669; padding-bottom: 14px; padding-top: 14px; margin-bottom: -1px; }
            QPushButton#TabButtonInactive { background: transparent; color: #a1a1aa; font-weight: bold; font-size: 14px; border: none; border-bottom: 2px solid transparent; padding-bottom: 14px; padding-top: 14px; }
            QPushButton#TabButtonInactive:hover { color: white; }

            QLineEdit#SearchInput { background: #27272a; border: 1px solid #3f3f46; border-radius: 12px; color: white; padding: 12px 16px; font-size: 14px; }
            QLineEdit#SearchInput:focus { border: 1px solid #059669; }

            QPushButton#ActionBtn { background: #3f3f46; border-radius: 8px; border: none; color: white; }
            QPushButton#ActionBtn:hover { background: #52525b; }

            QPushButton#DeleteBtn { background: rgba(220, 38, 38, 0.2); border-radius: 8px; border: none; color: #f87171; }
            QPushButton#DeleteBtn:hover { background: rgba(220, 38, 38, 0.3); }

            #ModRow { background-color: rgba(39, 39, 42, 0.5); border: 1px solid rgba(63, 63, 70, 0.5); border-radius: 12px; }
        """)


class LogEmitter(QObject):
    """Signals for thread-safe logging"""
    log_signal = pyqtSignal(str)

class LogWindow(QDialog):
    """Simple window to view game logs"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Output")
        self.resize(800, 600)
        self.setStyleSheet("background: #18181b;")
        
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #09090b;
                color: #d4d4d8;
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.text_edit)

    def append_log(self, text):
        self.text_edit.append(text)
        # Auto-scroll
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QCursor.End)
        self.text_edit.setTextCursor(cursor)

class SettingsWindow(QDialog):
    settings_saved = pyqtSignal(str) # Emits the new java path

    def __init__(self, current_java_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Launcher Settings")
        self.setFixedSize(600, 250)
        self.setObjectName("SettingsWindow")
        
        # Default fallback if empty
        self.default_macos_path = "/Library/Java/JavaVirtualMachines/jdk-21.jdk/Contents/Home/bin/java"
        
        self.current_path = current_java_path if current_java_path else self.default_macos_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Title
        title = QLabel("Java Runtime Environment")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Description
        desc = QLabel("Select the Java executable (java) to use for launching Minecraft.")
        desc.setStyleSheet("color: #a1a1aa; font-size: 13px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Input Row
        row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setText(self.current_path)
        self.path_input.setPlaceholderText("Path to java executable...")
        self.path_input.setStyleSheet("""
            QLineEdit {
                background: #27272a; border: 1px solid #3f3f46; 
                border-radius: 8px; color: white; padding: 10px;
            }
            QLineEdit:focus { border: 1px solid #10b981; }
        """)
        
        btn_browse = QPushButton("Browse")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setFixedSize(80, 40)
        btn_browse.clicked.connect(self.browse_file)
        btn_browse.setStyleSheet("""
            QPushButton {
                background: #3f3f46; color: white; border-radius: 8px; font-weight: bold;
            }
            QPushButton:hover { background: #52525b; }
        """)

        row.addWidget(self.path_input)
        row.addWidget(btn_browse)
        layout.addLayout(row)

        layout.addStretch()

        # Save Button
        btn_save = QPushButton("Save Settings")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setFixedHeight(45)
        btn_save.clicked.connect(self.save_and_close)
        btn_save.setStyleSheet("""
            QPushButton {
                background: #059669; color: white; border-radius: 8px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background: #10b981; }
        """)
        layout.addWidget(btn_save)

        self.apply_styles()

    def browse_file(self):
        # On Mac, we usually look for the 'java' binary inside Home/bin
        start_dir = "/Library/Java/JavaVirtualMachines" if os.path.exists("/Library/Java/JavaVirtualMachines") else ""
        path, _ = QFileDialog.getOpenFileName(self, "Select Java Executable", start_dir)
        if path:
            self.path_input.setText(path)

    def save_and_close(self):
        new_path = self.path_input.text().strip()
        self.settings_saved.emit(new_path)
        self.accept()

    def apply_styles(self):
        self.setStyleSheet("QDialog#SettingsWindow { background: #18181b; }")

class AppUpdateChecker(QObject):
    """
    Checks a URL for a JSON file containing {"version": "2.0.1", "url": "..."}
    """
    finished = pyqtSignal(bool, str, str)  # has_update, new_version, download_url

    def __init__(self, current_version, update_url):
        super().__init__()
        self.current_version = current_version
        self.update_url = update_url

    def run(self):
        try:
            print(f"[UPDATE] Checking for updates from {self.update_url}...")
            # 1. Fetch the JSON
            r = requests.get(self.update_url, timeout=5)
            if r.status_code != 200:
                print(f"[UPDATE] Failed with status {r.status_code}")
                self.finished.emit(False, "", "")
                return

            data = r.json()
            remote_ver = data.get("version", "0.0.0")
            download_url = data.get("url", "")

            # 2. Compare Versions (Simple Semantic Versioning)
            if self._is_newer(remote_ver):
                self.finished.emit(True, remote_ver, download_url)
            else:
                self.finished.emit(False, remote_ver, "")

        except Exception as e:
            print(f"[UPDATE] Error checking for updates: {e}")
            self.finished.emit(False, "", "")

    def _is_newer(self, remote_ver):
        """Returns True if remote_ver > self.current_version"""
        try:
            # Remove 'v' prefix and suffixes like '-beta' for comparison
            # This turns "v2.0.1-beta" into [2, 0, 1]
            def parse(v):
                clean = v.lower().lstrip("v").split("-")[0] 
                return [int(x) for x in clean.split(".")]

            local_parts = parse(self.current_version)
            remote_parts = parse(remote_ver)
            
            return remote_parts > local_parts
        except Exception:
            return False

# ---------- Main Window ----------
class LauncherV2(QMainWindow):
    mc_feed_loaded = pyqtSignal(list)
    mc_feed_done = pyqtSignal()
    avatar_ready = pyqtSignal(QPixmap)
    log_output = pyqtSignal(str) # ✅ NEW: Signal for logs

    instance_started = pyqtSignal(str)
    instance_stopped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # --------- VERSION CONFIG ----------
        self.APP_VERSION = "2.0.2"
        self.UPDATE_API_URL = "https://raw.githubusercontent.com/braydenwatt/RBLauncher/main/version_manifest.json"

        self.setWindowTitle(f"RBLauncher: Dusk (v{self.APP_VERSION})")
        self.resize(1200, 760)
        self.log_output.connect(self._handle_log_output)
        self.icon_paths = {
            "Launch": os.path.join(ICONS_DIR, "launch.svg"),
            "Kill": os.path.join(ICONS_DIR, "status-bad.svg"),
            "Show/Hide Logs": os.path.join(ICONS_DIR, "log.svg"),
            "Manage Mods": os.path.join(ICONS_DIR, "loadermods.svg"),
            "Edit": os.path.join(ICONS_DIR, "instance-settings.svg"),
            "Folder": os.path.join(ICONS_DIR, "folder.svg"),
            "Export": os.path.join(ICONS_DIR, "export.svg"),
            "Copy": os.path.join(ICONS_DIR, "copy.svg"),
            "Delete": os.path.join(ICONS_DIR, "delete.svg"),
            "Home": os.path.join(ICONS_DIR, "home.svg"),
            "Account": os.path.join(ICONS_DIR, "accounts.svg"),
        }

        self.net = QNetworkAccessManager(self)
        self._img_cache = {}  # url -> QPixmap

        # state
        self.instances_data = {}      # name -> dict
        self.selected_instance_name = None
        self.username = ""
        self.uuid = ""
        self.access_token = ""
        self.java_path = ""
        self.active_instances = {}    # name -> subprocess.Popen
        self.current_theme = "dark"

        os.makedirs(os.path.join(GAME_DIR, "instances"), exist_ok=True)

        # load config
        self.load_config()
        self.update_launch_auth_state()

        # UI
        self.root = QWidget()
        self.setCentralWidget(self.root)
        self.root_lay = QHBoxLayout(self.root)
        self.root_lay.setContentsMargins(0, 0, 0, 0)
        self.root_lay.setSpacing(0)

        self.build_sidebar()
        self.avatar_ready.connect(self._update_profile_avatar_ui)
        self.build_pages()
        self.refresh_profile_avatar()

        self.apply_styles()

        self.enforce_login_expiry()
        self._last_played_timer = QTimer(self)
        self._last_played_timer.timeout.connect(self._refresh_last_played_card)
        self._last_played_timer.start(30_000)  # every 30s
        self._auth_expiry_timer = QTimer(self)
        self._auth_expiry_timer.timeout.connect(self.enforce_login_expiry)
        self._auth_expiry_timer.start(5*60_000)  # check every 60s (or 5*60_000)
        # --- in __init__ after UI build, install event filter (so ESC works) ---
        QApplication.instance().installEventFilter(self)

        # initial populate
        self.refresh_instances_list()
        self.update_home_launch_label()
        self.selected_instance_name = None
        self.pages.setCurrentWidget(self.page_home)   # stay on home
        self.mc_feed_loaded.connect(self._set_mc_updates_items)
        self.mc_feed_done.connect(self._mc_feed_done_ui)
        self.instance_started.connect(self._on_instance_state_changed)
        self.instance_stopped.connect(self._on_instance_state_changed)

        QTimer.singleShot(2000, self.check_for_app_updates)

    # ---------------- APP UPDATE LOGIC ----------------

    def check_for_app_updates(self):
        """Starts the update check thread."""
        self._app_update_thread = QThread()
        self._app_update_worker = AppUpdateChecker(self.APP_VERSION, self.UPDATE_API_URL)
        self._app_update_worker.moveToThread(self._app_update_thread)

        # Connect signals
        self._app_update_thread.started.connect(self._app_update_worker.run)
        self._app_update_worker.finished.connect(self._on_app_update_result)
        
        # Cleanup
        self._app_update_worker.finished.connect(self._app_update_thread.quit)
        self._app_update_thread.finished.connect(self._app_update_worker.deleteLater)
        self._app_update_thread.finished.connect(self._app_update_thread.deleteLater)

        self._app_update_thread.start()

    def _on_app_update_result(self, has_update, new_version, url):
        if has_update:
            msg = QMessageBox(self)
            msg.setWindowTitle("Update Available")
            msg.setText(f"A new version of RBLauncher is available!\n\nCurrent: {self.APP_VERSION}\nNew: {new_version}")
            msg.setInformativeText("Would you like to download it now?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            
            # Style the message box to match your theme
            msg.setStyleSheet("""
                QMessageBox { background-color: #18181b; color: white; }
                QLabel { color: white; }
                QPushButton { 
                    background-color: #059669; 
                    color: white; 
                    border-radius: 6px; 
                    padding: 6px 12px;
                }
                QPushButton:hover { background-color: #10b981; }
            """)

            if msg.exec_() == QMessageBox.Yes:
                import webbrowser
                webbrowser.open(url)

    def is_authenticated(self) -> bool:
        return bool(self.access_token)
    def update_launch_auth_state(self):
        logged_in = self.is_authenticated()

        # Home page launch button
        if hasattr(self, "btn_launch_home"):
            self.btn_launch_home.setEnabled(logged_in)

        # Instance page launch button
        if hasattr(self, "btn_launch_big"):
            self.btn_launch_big.setEnabled(logged_in)

    def _refresh_last_played_card(self):
        if not self.selected_instance_name or not hasattr(self, "card_last"):
            return
        data = self.instances_data.get(self.selected_instance_name, {})
        self.card_last.value.setText(self._time_ago(data.get("last_played", "")))

    def _mc_feed_done_ui(self):
        print("[UI] DONE (main thread)")
        if hasattr(self, "mc_progress"):
            self.mc_progress.setVisible(False)
        if hasattr(self, "mc_progress_label"):
            self.mc_progress_label.setVisible(False)

    def load_svg_icon(self, path: str, size: int = 18, color: str = "#ffffff") -> QIcon:
        if not path or not os.path.exists(path):
            return QIcon()

        with open(path, "r", encoding="utf-8") as f:
            svg = f.read()

        svg = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', f'fill="{color}"', svg)
        svg = re.sub(r'fill="[^"]+"', f'fill="{color}"', svg)
        svg = re.sub(r'stroke="#[0-9a-fA-F]{3,6}"', f'stroke="{color}"', svg)
        svg = re.sub(r'stroke="[^"]+"', f'stroke="{color}"', svg)

        renderer = QSvgRenderer(bytearray(svg, encoding="utf-8"))

        dpr = QApplication.instance().devicePixelRatio()
        px = int(size * dpr)

        pixmap = QPixmap(px, px)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        pixmap.setDevicePixelRatio(dpr)  # 🔥 critical line

        return QIcon(pixmap)

    def set_button_svg_icon(self, btn: QPushButton, key: str, size: int = 18, color: str = "#ffffff"):
        path = self.icon_paths.get(key, "")
        btn.setIcon(self.load_svg_icon(path, size=size, color=color))
        btn.setIconSize(QSize(size, size))

    def get_instance_icon_path(self, name: str) -> str:
        data = self.instances_data.get(name, {})
        image = data.get("image")

        if isinstance(image, dict):
            path = image.get("saved_path")
        elif isinstance(image, str):
            path = image
        else:
            path = None

        if path:
            # make relative paths absolute relative to PROJECT_DIR
            if not os.path.isabs(path):
                path = os.path.join(PROJECT_DIR, path)
            if os.path.exists(path):
                return path

        return os.path.join(ICONS_DIR, "default.png")


    def _default_profile_avatar(self):
        # fallback: keep your gradient box but put a letter
        self.profile_avatar.setText((self.username[:1] if self.username else "U").upper())
        self.profile_avatar.setAlignment(Qt.AlignCenter)

    # ---------------- AVATAR LOGIC ----------------

    def refresh_profile_avatar(self):
        """Starts the background worker to fetch the avatar."""
        # 1. Set a temporary fallback (Letter or default image)
        self.profile_avatar.clear() # Clear previous image/text
        self.profile_avatar.setText((self.username[:1] if self.username else "U").upper())
        
        # 2. Start thread
        threading.Thread(target=self._worker_fetch_avatar, daemon=True).start()

    def _worker_fetch_avatar(self):
        """Background thread: Resolves UUID -> Checks Cache -> Downloads."""
        import urllib.request
        
        # 1. Get UUID
        uuid = self.uuid
        if not uuid and self.username:
            uuid = self._resolve_uuid_from_username(self.username)
        
        # If we still have no UUID, we can't get a skin. Stop here.
        if not uuid:
            return

        # Clean UUID (remove dashes)
        uuid = uuid.replace("-", "").strip()
        
        # 2. Check Cache
        cache_dir = os.path.join(GAME_DIR, "cache", "avatars")
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{uuid}_40.png")

        img_bytes = None

        if os.path.exists(cache_path):
            # Load from disk
            try:
                with open(cache_path, "rb") as f:
                    img_bytes = f.read()
            except Exception as e:
                print(f"[AVATAR] Read cache failed: {e}")

        # 3. Download if not in cache (or cache read failed)
        if not img_bytes:
            url = f"https://mc-heads.net/avatar/{uuid}/40"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "RBLauncher"})
                # Use your existing SSL context helper
                ctx = self._make_ssl_context()
                with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                    img_bytes = resp.read()
                
                # Write to cache
                with open(cache_path, "wb") as f:
                    f.write(img_bytes)
            except Exception as e:
                print(f"[AVATAR] Download failed: {e}")
                return

        # 4. Create Pixmap (Must be done carefully, but loading bytes into QPixmap 
        # is safest done on Main Thread via Signal, or by passing bytes)
        
        # However, passing raw bytes to a signal is fine. 
        # But to be safe, let's create the pixmap object here? 
        # NO. QPixmap cannot be created effectively outside the main thread on some platforms.
        # We will create the QImage here (safe) or pass bytes.
        
        # Let's pass the QImage, which is thread-safe, then convert to Pixmap in UI.
        from PyQt5.QtGui import QImage
        image = QImage()
        if image.loadFromData(img_bytes):
            # Convert to pixmap on main thread via signal
            pm = QPixmap.fromImage(image)
            self.avatar_ready.emit(pm)

    def _update_profile_avatar_ui(self, pixmap: QPixmap):
        """Slot called by the signal on the Main UI Thread."""
        if pixmap.isNull():
            return

        # Hardcode the size to 40x40 to match your UI layout
        target_size = 40 
        
        # Scale High Quality
        scaled = pixmap.scaled(
            target_size, target_size, 
            Qt.KeepAspectRatioByExpanding, 
            Qt.SmoothTransformation
        )
        
        # Round corners
        rounded = self.rounded_pixmap(scaled, radius=10)

        # Apply
        self.profile_avatar.setPixmap(rounded)
        self.profile_avatar.setStyleSheet("background: transparent; border-radius: 10px;")
        self.profile_avatar.setPixmap(rounded)
        self.profile_avatar.setText("")
        # CRITICAL: Do NOT call setText here, or the image will vanish.


    def _resolve_uuid_from_username(self, username: str) -> str:
        """
        Blocking network call is NOT ideal on UI thread.
        We'll call this only inside a worker thread.
        Mojang API: https://api.mojang.com/users/profiles/minecraft/<name>
        """
        if not username:
            return ""
        try:
            url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
            req = urllib.request.Request(url, headers={"User-Agent": "RBLauncher"})
            ctx = self._make_ssl_context()
            with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            raw = data.get("id", "")
            if len(raw) == 32:
                return raw
        except Exception:
            pass
        return ""


    def rounded_pixmap(self, pixmap: QPixmap, radius: int) -> QPixmap:
        if pixmap.isNull():
            return pixmap

        w, h = pixmap.width(), pixmap.height()
        out = QPixmap(w, h)
        out.fill(Qt.transparent)

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, radius, radius)

        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return out


    # ---------------- CONFIG ----------------
    def load_config(self):
        # The specific default requested
        default_java = "/Library/Java/JavaVirtualMachines/jdk-21.jdk/Contents/Home/bin/java"
        
        default_cfg = {
            "theme": "dark",
            "instances": {},
            "username": "",
            "UUID": "",
            "access_token": "",
            "java_path": default_java, # ✅ Set default here
            "last_played_instance": "",
            "last_login_utc": ""
        }

        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    cfg = json.load(f)
                self.current_theme = cfg.get("theme", "dark")
                self.instances_data = cfg.get("instances", {}) or {}
                self.username = cfg.get("username", "")
                self.uuid = cfg.get("UUID", "")
                self.access_token = cfg.get("access_token", "")
                # ✅ Load path, fall back to default if empty string
                self.java_path = cfg.get("java_path") or default_java 
                self.last_played_instance = cfg.get("last_played_instance", "")
                self.last_login_utc = cfg.get("last_login_utc", "")
                return
            except Exception:
                pass

        # If no config exists, write default
        with open(CONFIG_PATH, "w") as f:
            json.dump(default_cfg, f, indent=4)

        self.current_theme = "dark"
        self.instances_data = {}
        self.username = ""
        self.uuid = ""
        self.access_token = ""
        self.java_path = default_java # ✅
        self.last_login_utc = ""

    def open_settings(self):
        """Opens the SettingsWindow to configure Java path."""
        dlg = SettingsWindow(self.java_path, self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec_()

    def _on_settings_saved(self, new_path):
        """Callback when settings are saved."""
        self.java_path = new_path
        self.save_config()
        print(f"[SETTINGS] Java path updated to: {self.java_path}")
        QMessageBox.information(self, "Settings Saved", "Java path updated successfully.")

    def _set_auth_ui_state(self):
        """Refresh sidebar/profile UI based on whether access_token exists."""
        self.profile_name.setText(self.username or "Username")
        self.profile_status.setText("Authenticated" if self.access_token else "Not logged in")

        # refresh profile menu contents next open
        if hasattr(self, "profile_menu"):
            self._hide_profile_menu()
            del self.profile_menu

        # refresh avatar (will show letter if logged out)
        self.refresh_profile_avatar()


    def _is_login_expired(self) -> bool:
        """True if last_login_utc is missing/invalid or older than 24h."""
        if not getattr(self, "last_login_utc", ""):
            return True

        from datetime import datetime, timezone, timedelta
        try:
            dt = datetime.fromisoformat(self.last_login_utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            return True

        return (datetime.now(timezone.utc) - dt) >= timedelta(hours=24)


    def enforce_login_expiry(self):
        """
        If token exists but is older than 24h, clear it and update UI/config.
        Call on startup and optionally on a timer.
        """
        if self.access_token and self._is_login_expired():
            print("[AUTH] Token expired (>24h). Clearing access token.")
            self.access_token = ""
            self.last_login_utc = ""
            # optional: keep username/uuid or clear them too (your call)
            # self.username = ""
            # self.uuid = ""
            self.update_launch_auth_state()
            self.save_config()
            self._set_auth_ui_state()


    def save_config(self):
        cfg = {
            "theme": self.current_theme,
            "java_path": self.java_path,
            "instances": self.instances_data,
            "username": self.username,
            "UUID": self.uuid,
            "access_token": self.access_token,
            "last_played_instance": getattr(self, "last_played_instance", ""),
            "last_login_utc": getattr(self, "last_login_utc", "")  # ✅ NEW
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=4)


    # --- inside class LauncherV2(QMainWindow): add these helpers ---

    def _build_profile_menu(self):
        self.profile_menu = QFrame(self.sidebar)
        self.profile_menu.setObjectName("ProfileMenu")
        self.profile_menu.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.profile_menu.setAttribute(Qt.WA_TranslucentBackground, False)
        self.profile_menu.setAutoFillBackground(True)

        # ✅ ONLY ONE layout on ProfileMenu
        lay = QVBoxLayout(self.profile_menu)
        lay.setContentsMargins(0, 0, 0, 0)   # no padding = no weird gap
        lay.setSpacing(0)

        # --- Header ---
        header = QFrame()
        header.setObjectName("ProfileMenuHeader")
        h = QVBoxLayout(header)
        h.setContentsMargins(12, 12, 12, 12)  # keep nice header padding
        h.setSpacing(4)

        name = QLabel(self.username or "Username")
        name.setObjectName("ProfileMenuName")
        email = QLabel("Microsoft account" if self.access_token else "Not logged in")
        email.setObjectName("ProfileMenuEmail")
        h.addWidget(name)
        h.addWidget(email)

        lay.addWidget(header)

        def add_item(text, icon_key=None, cb=None):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setObjectName("ProfileMenuItem")
            b.setFlat(True)
            b.setMinimumHeight(36)
            if icon_key:
                self.set_button_svg_icon(b, icon_key, size=16, color="#ffffff")
            if cb:
                b.clicked.connect(lambda: (self._hide_profile_menu(), cb()))
            else:
                b.clicked.connect(self._hide_profile_menu)
            lay.addWidget(b)

        add_item("Launcher Settings", "Edit", self.open_settings)
        add_item("Open Launcher Folder", "Folder", lambda: subprocess.run(["open", GAME_DIR]))

        div = QFrame()
        div.setObjectName("ProfileMenuDivider")
        div.setFixedHeight(1)
        lay.addWidget(div)

        add_item("Log In", None, self.open_account_manager)
        add_item("Help", None, lambda: __import__("webbrowser").open("https://github.com/braydenwatt/RBLauncher"))

        self.profile_menu.setFixedWidth(280)




    def _toggle_profile_menu(self):
        if not hasattr(self, "profile_menu"):
            self._build_profile_menu()

        if self.profile_menu.isVisible():
            self._hide_profile_menu()
            return

        # Position it ABOVE the profile button, aligned to left edge
        btn = self.profile_btn
        menu = self.profile_menu

        # Map the button's bottom-left to global coordinates
        bottom_left_global = btn.mapToGlobal(QPoint(0, 0))
        # Place menu above the button with a small gap
        x = bottom_left_global.x()
        y = bottom_left_global.y() - menu.sizeHint().height() - 8

        menu.move(x, y)
        menu.show()

    def _hide_profile_menu(self):
        if hasattr(self, "profile_menu") and self.profile_menu.isVisible():
            self.profile_menu.hide()

    def eventFilter(self, obj, event):
        # Click outside closes menu
        if hasattr(self, "profile_menu") and self.profile_menu.isVisible():
            if event.type() in (QEvent.MouseButtonPress, QEvent.KeyPress):
                # ESC closes
                if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
                    self._hide_profile_menu()
                    return True
        return super().eventFilter(obj, event)


    def go_home(self):
        self.selected_instance_name = None
        self.refresh_instances_list()
        self.instances_list.clearSelection()
        self.pages.setCurrentWidget(self.page_home)

        self.update_launch_buttons_ui()

    # ---------------- UI: Sidebar ----------------
    def build_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(320)

        lay = QVBoxLayout(self.sidebar)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Header
        header = QFrame()
        header.setObjectName("SidebarHeader")
        h = QVBoxLayout(header)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.setContentsMargins(0, 0, 0, 0)

        # left logo
        logo = QLabel()
        logo.setObjectName("AppLogo")
        logo.setFixedSize(34, 34)

        pm = QPixmap(APP_ICON_PATH)
        if not pm.isNull():
            pm = pm.scaled(34, 34, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            pm = self.rounded_pixmap(pm, radius=8)
            logo.setPixmap(pm)

        # right title/subtitle stack
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.setContentsMargins(0, 0, 0, 0)

        app_title = QLabel("RBLauncher")
        app_title.setObjectName("AppTitle")
        app_sub = QLabel("v2.0.0-beta • Dusk")
        app_sub.setObjectName("AppSubtitle")

        title_col.addWidget(app_title)
        title_col.addWidget(app_sub)

        title_row.addWidget(logo, 0, Qt.AlignTop)
        title_row.addLayout(title_col, 1)

        # Home icon button (next to the text)
        self.btn_home = QPushButton()
        self.btn_home.setObjectName("IconButton")
        self.btn_home.setFixedSize(36, 36)
        print("HOME SVG PATH:", self.icon_paths["Home"], os.path.exists(self.icon_paths["Home"]))
        self.set_button_svg_icon(self.btn_home, "Home", size=20, color="#ffffff")
        self.btn_home.clicked.connect(self.go_home)

        title_row.addWidget(self.btn_home, 0, Qt.AlignTop)


        h.addLayout(title_row)
        h.addSpacing(12)

        self.btn_new_instance = QPushButton(" +  New Instance")
        self.btn_new_instance.setObjectName("PrimaryButton")
        self.btn_new_instance.clicked.connect(self.open_new_instance_page)
        h.addWidget(self.btn_new_instance)

        # Divider line under Add Instance button
        divider = QFrame()
        divider.setObjectName("SidebarDivider")
        divider.setFrameShape(QFrame.NoFrame)     # <-- important
        divider.setFixedHeight(1)                # <-- important
        h.addWidget(divider)

        lay.addWidget(header)

        # Instances label
        self.instances_label = QLabel("Instances")
        self.instances_label.setObjectName("SidebarSectionLabel")
        lay.addWidget(self.instances_label)

        # List
        self.instances_list = QListWidget()
        self.instances_list.setObjectName("InstancesList")
        self.instances_list.itemClicked.connect(self.on_instance_clicked)
        self.instances_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.instances_list.setMinimumHeight(0)

        lay.addWidget(self.instances_list, 1)


        # Profile (whole thing is clickable)
        self.profile_btn = QPushButton()
        self.profile_btn.setObjectName("ProfileButton")
        self.profile_btn.setCursor(Qt.PointingHandCursor)
        self.profile_btn.clicked.connect(self._toggle_profile_menu)
        self.profile_btn.setFixedHeight(72)

        p = QHBoxLayout(self.profile_btn)
        p.setContentsMargins(12, 12, 12, 12)
        p.setSpacing(10)

        # Placeholder avatar square
        self.profile_avatar = QLabel()
        self.profile_avatar.setObjectName("ProfileAvatar")
        self.profile_avatar.setFixedSize(40, 40)
        self.profile_avatar.setAlignment(Qt.AlignCenter)
        self.profile_avatar.setText(" ")  # placeholder, you can set pixmap later

        # Name + status
        self.profile_name = QLabel(self.username or "Username")
        self.profile_name.setObjectName("ProfileName")
        self.profile_status = QLabel("Authenticated" if self.access_token else "Not logged in")
        self.profile_status.setObjectName("ProfileStatus")
        self.profile_name.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.profile_status.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        name_box = QVBoxLayout()
        name_box.setSpacing(0)
        name_box.addWidget(self.profile_name)
        name_box.addWidget(self.profile_status)

        # Bigger settings icon (no separate outline button)
        self.profile_gear = QLabel()
        self.profile_gear.setObjectName("ProfileGear")
        self.profile_gear.setFixedSize(28, 28)
        self.profile_gear.setAlignment(Qt.AlignCenter)
        self.profile_gear.setPixmap(self.load_svg_icon(self.icon_paths["Edit"], size=22).pixmap(22, 22))

        p.addWidget(self.profile_avatar, 0)
        p.addLayout(name_box, 0)
        p.addWidget(self.profile_gear, 0, Qt.AlignRight)

        lay.addWidget(self.profile_btn)

        self.root_lay.addWidget(self.sidebar)

    # ---------------- UI: Pages ----------------
    def build_pages(self):
        self.pages = QStackedWidget()
        self.pages.setObjectName("Pages")
        self.root_lay.addWidget(self.pages, 1)

        # 0) Home page (new)
        self.page_home = QWidget()
        self.pages.addWidget(self.page_home)
        self.build_home_page(self.page_home)
        
        # 1) Launcher page
        self.page_launcher = QWidget()
        self.pages.addWidget(self.page_launcher)
        self.build_launcher_page(self.page_launcher)

        # 2) New instance page (placeholder)
        self.page_new_instance = QWidget()
        self.pages.addWidget(self.page_new_instance)
        self.build_new_instance_page(self.page_new_instance)

        # 3) Mod manager page (placeholder)
        self.page_mods = ManageModsPage()
        self.page_mods.back_clicked.connect(self.go_back_to_launcher) # Create this method
        self.pages.addWidget(self.page_mods)

        self.pages.setCurrentIndex(0)

    def go_back_to_launcher(self):
        # Return to the instance details page (page 1)
        self.pages.setCurrentWidget(self.page_launcher)
        
    def populate_mc_updates_from_mojang(self, limit: int = 12):
        import ssl

        FEED_URL = "https://launchercontent.mojang.com/v2/javaPatchNotes.json"
        BASE_URL = "https://launchercontent.mojang.com"

        print("\n=== MC NEWS DEBUG START ===")
        print("Limit:", limit)
        print("Feed URL:", FEED_URL)

        cache_dir = os.path.join(GAME_DIR, "cache", "mojang_patchnotes")
        os.makedirs(cache_dir, exist_ok=True)
        print("Cache dir:", cache_dir)

        def ui(msg):
            print("[UI]", msg)
            if hasattr(self, "mc_progress_label"):
                self.mc_progress_label.setText(msg)
                self.mc_progress_label.setVisible(True)
            if hasattr(self, "mc_progress"):
                self.mc_progress.setVisible(True)
                self.mc_progress.setRange(0, 0)

        def ui_done():
            print("[UI] DONE")
            if hasattr(self, "mc_progress"):
                self.mc_progress.setVisible(False)
            if hasattr(self, "mc_progress_label"):
                self.mc_progress_label.setVisible(False)

        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: ui("Starting Mojang feed load…"))

        def worker():
            print("[THREAD] Worker started")
            items = []

            try:
                # ---------------- FETCH FEED ----------------
                print("[THREAD] Fetching JSON...")
                req = urllib.request.Request(
                    FEED_URL,
                    headers={"User-Agent": "RBLauncher/DEBUG"}
                )

                ctx = self._make_ssl_context()
                with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                    raw = resp.read()
                    print("[THREAD] HTTP status OK, bytes:", len(raw))
                    data = json.loads(raw.decode("utf-8"))

                print("[THREAD] JSON parsed")
                print("[THREAD] Keys:", list(data.keys()))

                from datetime import datetime, timezone

                def parse_iso_z(s: str):
                    if not s:
                        return datetime.min.replace(tzinfo=timezone.utc)
                    try:
                        # "2025-12-16T13:32:25.283Z" -> "+00:00"
                        s2 = s.replace("Z", "+00:00")
                        return datetime.fromisoformat(s2)
                    except Exception:
                        return datetime.min.replace(tzinfo=timezone.utc)

                entries = data.get("entries", [])
                print("[THREAD] Total entries:", len(entries))

                # sort newest -> oldest by date field
                entries.sort(key=lambda e: parse_iso_z(e.get("date", "")), reverse=True)

                # take top N
                entries = entries[:limit]
                print("[THREAD] Using most recent entries:", len(entries))
                print("[THREAD] Newest date:", entries[0].get("date") if entries else "none")


                # ---------------- PROCESS ENTRIES ----------------
                for i, e in enumerate(entries):
                    print(f"[THREAD] Entry {i+1}/{len(entries)}")

                    title = e.get("title", "Untitled")
                    print("  title:", title)

                    image_url = None
                    img = e.get("image")
                    print("  image field:", img)

                    if isinstance(img, dict):
                        rel = img.get("url")
                        if rel:
                            image_url = urljoin(BASE_URL + "/", rel.lstrip("/"))

                    print("  image_url:", image_url)

                    icon_path = None
                    if image_url:
                        safe_id = e.get("id", f"item_{i}")
                        icon_path = os.path.join(cache_dir, f"{safe_id}.jpg")
                        print("  icon_path:", icon_path)

                        if not os.path.exists(icon_path):
                            print("  downloading image...")
                            try:
                                img_req = urllib.request.Request(image_url, headers={"User-Agent": "RBLauncher/DEBUG"})
                                with urllib.request.urlopen(img_req, timeout=10, context=ctx) as r:
                                    img_bytes = r.read()
                                with open(icon_path, "wb") as f:
                                    f.write(img_bytes)
                                print("  image downloaded OK, bytes:", len(img_bytes))
                            except Exception as img_ex:
                                print("  IMAGE DOWNLOAD FAILED:", img_ex)
                                icon_path = None
                        else:
                            print("  image already cached")

                    items.append({
                        "title": title,
                        "date": e.get("date", ""),
                        "short": e.get("shortText", ""),
                        "content_path": e.get("contentPath", ""),
                        "icon_path": icon_path,
                    })

                print("[THREAD] Finished building items:", len(items))

            except Exception as ex:
                print("!!! EXCEPTION IN WORKER !!!")
                print(type(ex), ex)
                items = [{
                    "title": "FAILED TO LOAD FEED",
                    "short": repr(ex),
                    "icon_path": None
                }]

            print("[THREAD] Scheduling UI update")
            self.mc_feed_loaded.emit(items)

            print("[THREAD] Emitting mc_feed_done")
            self.mc_feed_done.emit()
            print("[THREAD] Worker finished")

        print("[MAIN] Starting thread")
        threading.Thread(target=worker, daemon=True).start()

    def _make_ssl_context(self):
        import ssl
        try:
            import certifi
            cafile = certifi.where()
            print("[NET] SSL: using certifi CA bundle:", cafile)
            return ssl.create_default_context(cafile=cafile)
        except Exception as e:
            print("[NET] SSL: using system default context (certifi unavailable):", repr(e))
            return ssl.create_default_context()

    def _pretty_mojang_date(self, iso_str: str) -> str:
        """
        Converts "2025-12-16T13:32:25.283Z" -> "Dec 16, 2025 • 1:32 PM"
        Falls back to raw string if parsing fails.
        """
        if not iso_str:
            return ""
        try:
            from datetime import datetime, timezone
            # Mojang uses Z for UTC
            s = iso_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)

            # Convert to local time
            local_dt = dt.astimezone()

            # Format: Dec 16, 2025 • 1:32 PM
            date_part = local_dt.strftime("%b %d, %Y")
            time_part = local_dt.strftime("%I:%M %p").lstrip("0")  # remove leading zero
            return f"{date_part} • {time_part}"
        except Exception:
            return iso_str

    def _set_mc_updates_items(self, items):
        # Check for the layout, not the list
        if not hasattr(self, "mc_updates_layout"):
            return

        # 1. Clear existing items from the layout
        # We loop backwards to safely delete widgets
        while self.mc_updates_layout.count():
            item = self.mc_updates_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        thumb_size = 88 

        from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSizePolicy, QFrame
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPixmap

        if not items:
            # Optional: Show a "No updates" label if list is empty
            return

        for it in items:
            title = it.get("title", "Untitled")
            short = (it.get("short", "") or "").strip()
            pretty_date = self._pretty_mojang_date(it.get("date", ""))

            # Create the row container
            row = QFrame()
            row.setObjectName("NewsItemRow") # Useful for CSS styling if needed
            # Remove Fixed height constraints, let layout decide height
            row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(10, 8, 10, 8)
            row_l.setSpacing(10)

            # --- Thumbnail ---
            thumb = QLabel()
            thumb.setFixedSize(thumb_size, thumb_size)
            thumb.setScaledContents(True)
            # Make sure thumb stays at the top-left, doesn't float to center vertically
            thumb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            icon_path = it.get("icon_path")
            if icon_path and os.path.exists(icon_path):
                pm = QPixmap(icon_path)
                if not pm.isNull():
                    pm = pm.scaled(thumb_size, thumb_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    # Assuming you have this helper method:
                    pm = self.rounded_pixmap(pm, radius=14)
                    thumb.setPixmap(pm)

            # --- Text Column ---
            text_box = QWidget()
            text_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            text_l = QVBoxLayout(text_box)
            text_l.setContentsMargins(0, 0, 0, 0)
            text_l.setSpacing(2)

            title_lbl = QLabel(title)
            title_lbl.setObjectName("MCTitle")
            title_lbl.setWordWrap(True)
            title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

            date_lbl = QLabel(pretty_date)
            date_lbl.setObjectName("MCDate")
            date_lbl.setWordWrap(True)
            date_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

            short_lbl = QLabel(short)
            short_lbl.setObjectName("MCShort")
            short_lbl.setWordWrap(True)
            short_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

            text_l.addWidget(title_lbl)
            if pretty_date:
                text_l.addWidget(date_lbl)
            if short:
                text_l.addWidget(short_lbl)
            
            # Add a spacer at bottom of text to push it up if row is tall
            text_l.addStretch() 

            # Add to Row Layout
            row_l.addWidget(thumb, 0, Qt.AlignCenter)
            row_l.addWidget(text_box, 1, Qt.AlignVCenter)

            # Add Row to Main Feed Layout
            self.mc_updates_layout.addWidget(row)
    


    def build_home_page(self, parent):
        from PyQt5.QtWidgets import QScrollArea

        # OUTER layout: no padding so BottomBar can be full-width
        outer = QVBoxLayout(parent)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # CONTENT wrapper
        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(28, 28, 28, 28)
        content_lay.setSpacing(16)

        # --- Top row: title + help link (top-right) ---
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(4)

        title = QLabel("Welcome back")
        title.setObjectName("HomeTitle")

        subtitle = QLabel("Pick an instance on the left, or launch your last played.")
        subtitle.setObjectName("HomeSubtitle")

        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        top_row.addLayout(title_col, 1)

        self.btn_help_home = QPushButton("Help")
        self.btn_help_home.setObjectName("HelpPill")
        self.btn_help_home.setCursor(Qt.PointingHandCursor)

        # (Assuming ICONS_DIR is defined elsewhere)
        help_svg = os.path.join(ICONS_DIR, "help.svg")
        self.btn_help_home.setIcon(self.load_svg_icon(help_svg, size=16, color="#34d399"))
        self.btn_help_home.setIconSize(QSize(16, 16))

        import webbrowser
        self.btn_help_home.clicked.connect(lambda: webbrowser.open("https://github.com/braydenwatt/RBLauncher"))
        top_row.addWidget(self.btn_help_home, 0, Qt.AlignTop | Qt.AlignRight)

        content_lay.addLayout(top_row)

        # --- What's new in Minecraft (Scroll Area Approach) ---
        whats_new = QFrame()
        whats_new.setObjectName("WhatsNewBlock")
        whats_new.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        wl = QVBoxLayout(whats_new)
        wl.setContentsMargins(1, 1, 1, 1) # Small margin if you have a border
        wl.setSpacing(10)

        # Title inside the block
        wn_header_lay = QVBoxLayout()
        wn_header_lay.setContentsMargins(15, 15, 15, 5) # Padding for the title text
        wn_title = QLabel("What’s new in Minecraft")
        wn_title.setObjectName("NewsTitle")
        wn_header_lay.addWidget(wn_title)
        wl.addLayout(wn_header_lay)
        
        # progress UI
        self.mc_progress_label = QLabel("Loading…")
        self.mc_progress_label.setObjectName("HomeSubtitle") 
        self.mc_progress_label.setContentsMargins(15, 0, 0, 0)
        self.mc_progress_label.setVisible(False)
        wl.addWidget(self.mc_progress_label)

        self.mc_progress = QProgressBar()
        self.mc_progress.setObjectName("MCProgress")
        self.mc_progress.setTextVisible(False)
        self.mc_progress.setVisible(False)
        wl.addWidget(self.mc_progress)

        # --- THE SCROLL AREA REPLACEMENT ---
        self.mc_scroll_area = QScrollArea()
        self.mc_scroll_area.setObjectName("NewsScrollArea") # Style this transparent in CSS
        self.mc_scroll_area.setWidgetResizable(True) # CRITICAL: Forces content to fit width
        self.mc_scroll_area.setFrameShape(QFrame.NoFrame)
        self.mc_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container Widget inside Scroll Area
        self.mc_scroll_content = QWidget()
        self.mc_scroll_content.setObjectName("NewsScrollContent")
        self.mc_scroll_content.setStyleSheet("background: transparent;") # Ensure transparency
        
        # The Layout we will add rows to
        self.mc_updates_layout = QVBoxLayout(self.mc_scroll_content)
        self.mc_updates_layout.setContentsMargins(0, 0, 0, 0)
        self.mc_updates_layout.setSpacing(0) # Spacing handled by row margins
        self.mc_updates_layout.setAlignment(Qt.AlignTop)

        self.mc_scroll_area.setWidget(self.mc_scroll_content)
        wl.addWidget(self.mc_scroll_area, 1)

        content_lay.addWidget(whats_new, 1)

        # Add padded content to outer
        outer.addWidget(content, 1)

        # --- Bottom launch bar ---
        home_bottom = QFrame()
        home_bottom.setObjectName("BottomBar")
        bl = QVBoxLayout(home_bottom)
        bl.setContentsMargins(28, 18, 28, 18)
        bl.setSpacing(0)

        self.btn_launch_home = QPushButton("Launch last played")
        self.btn_launch_home.setObjectName("LaunchButton")
        self.btn_launch_home.setMinimumHeight(60)
        self.set_button_svg_icon(self.btn_launch_home, "Launch", size=22)
        self.btn_launch_home.setIconSize(QSize(22, 22))
        self.btn_launch_home.clicked.connect(self.launch_last_played_from_home)

        bl.addWidget(self.btn_launch_home)
        outer.addWidget(home_bottom, 0)

        # Kick off real feed load
        self.populate_mc_updates_from_mojang(limit=6)

    def _pick_most_recent_instance(self) -> str:
        from datetime import datetime

        best_name = ""
        best_dt = None

        for name, data in self.instances_data.items():
            iso = data.get("last_played", "")
            if not iso:
                continue
            try:
                dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            except Exception:
                continue

            if best_dt is None or dt > best_dt:
                best_dt = dt
                best_name = name

        return best_name


    def launch_last_played_from_home(self):
        if not self.is_authenticated():
            QMessageBox.warning(self, "Not signed in", "Sign in required.")
            return

        # Identify target instance
        name = getattr(self, "last_played_instance", "")
        if not name or name not in self.instances_data:
            name = self._pick_most_recent_instance() or next(iter(self.instances_data.keys()))
        
        if not name: return

        # Check if running
        if name in self.active_instances:
            self.kill_instance(name)
        else:
            # Set selection and launch
            self.set_selected_instance(name)
            self.pages.setCurrentWidget(self.page_launcher)
            self.refresh_instances_list()
            self.launch_instance()

    def kill_instance(self, name):
        """Terminates the subprocess for the given instance."""
        proc = self.active_instances.get(name)
        if proc:
            self.log_output.emit(f"\n[Manager] Stopping instance: {name}...")
            try:
                pid = proc.pid
                os.kill(pid, signal.SIGKILL)
            except Exception as e:
                print(f"Error killing process: {e}")

    def build_launcher_page(self, parent):
        outer = QVBoxLayout(parent)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        self.header = QFrame()
        self.header.setObjectName("MainHeader")
        hl = QVBoxLayout(self.header)
        hl.setContentsMargins(28, 24, 28, 24)
        hl.setSpacing(16)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        # big icon
        self.instance_big_icon = QLabel("🟩")
        self.instance_big_icon.setObjectName("BigIcon")
        self.instance_big_icon.setFixedSize(84, 84)
        self.instance_big_icon.setAlignment(Qt.AlignCenter)

        # name + tags
        name_col = QVBoxLayout()
        name_col.setSpacing(6)
        self.instance_title = QLabel("Select an instance")
        self.instance_title.setObjectName("InstanceTitle")
        self.instance_tags = QLabel("") 
        self.instance_tags.setObjectName("InstanceTags")
        name_col.addWidget(self.instance_title)
        name_col.addWidget(self.instance_tags)

        # right actions
        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.btn_open_folder = QPushButton()
        self.btn_open_folder.setObjectName("IconButton")
        self.btn_open_folder.setFixedSize(44, 44)
        self.set_button_svg_icon(self.btn_open_folder, "Folder", size=18)
        self.btn_open_folder.clicked.connect(self.open_instance_folder)

        self.btn_delete = QPushButton()
        self.btn_delete.setObjectName("DangerIconButton")
        self.btn_delete.setFixedSize(44, 44)
        self.set_button_svg_icon(self.btn_delete, "Delete", size=18)
        self.btn_delete.clicked.connect(self.delete_instance)

        actions.addWidget(self.btn_open_folder)
        actions.addWidget(self.btn_delete)

        top_row.addWidget(self.instance_big_icon)
        top_row.addLayout(name_col, 1)
        top_row.addLayout(actions)

        hl.addLayout(top_row)
        outer.addWidget(self.header)

        # Body scroll-ish container
        body = QWidget()
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(28, 24, 28, 24)
        body_l.setSpacing(16)

        # 1. Cards Row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self.card_last = Card("Last Played", "—")
        self.card_version = Card("Game Version", "—")
        self.card_loader = Card("Loader Type", "—")
        cards_row.addWidget(self.card_last)
        cards_row.addWidget(self.card_version)
        cards_row.addWidget(self.card_loader)
        body_l.addLayout(cards_row)

        # 2. Settings Section
        settings = QFrame()
        settings.setObjectName("SettingsBlock")
        s = QVBoxLayout(settings)
        s.setContentsMargins(16, 16, 16, 16)
        s.setSpacing(8)
        title = QLabel("Instance Settings")
        title.setObjectName("SectionTitle")
        s.addWidget(title)
        
        self.row_manage_mods = SectionRow(
            "Manage Mods",
            "0 mods installed",
            "Open",
            action_cb=self.open_mod_manager_page
        )
        s.addWidget(self.row_manage_mods)
        body_l.addWidget(settings, 0)

        # 3. Game Logs Section (✅ NEW)
        logs_card = QFrame()
        logs_card.setObjectName("LogsBlock") # Uses same rounded style
        l_layout = QVBoxLayout(logs_card)
        l_layout.setContentsMargins(16, 16, 16, 16)
        l_layout.setSpacing(8)

        l_title = QLabel("Game Output")
        l_title.setObjectName("SectionTitle")
        l_layout.addWidget(l_title)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogConsole")
        self.log_view.setPlaceholderText("Waiting for instance start...")
        l_layout.addWidget(self.log_view)

        body_l.addWidget(logs_card, 1) # Stretch 1 to fill remaining space

        outer.addWidget(body, 1)

        # Bottom launch bar
        bottom = QFrame()
        bottom.setObjectName("BottomBar")
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(28, 18, 28, 18)
        self.btn_launch_big = QPushButton("Launch")
        self.btn_launch_big.setObjectName("LaunchButton")
        self.btn_launch_big.setMinimumHeight(60)
        self.set_button_svg_icon(self.btn_launch_big, "Launch", size=22)
        self.btn_launch_big.setIconSize(QSize(22, 22))
        self.btn_launch_big.clicked.connect(self.launch_instance)
        bl.addWidget(self.btn_launch_big)
        outer.addWidget(bottom)

    def build_new_instance_page(self, parent):
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(0, 0, 0, 0)
        
        self.wizard = NewInstancePage()
        
        # Connect Signals
        self.wizard.cancelled.connect(lambda: self.pages.setCurrentIndex(0)) # Go to Home
        self.wizard.created.connect(self.finalize_instance_creation)
        
        lay.addWidget(self.wizard)

    # --- Inside LauncherV2 Class ---

    def finalize_instance_creation(self, instance_data):
        """Called when Wizard emits 'created' signal."""
        base_name = instance_data['name']
        name = base_name
        counter = 1
        
        # 1. Handle Name Collisions
        while name in self.instances_data:
            name = f"{base_name} ({counter})"
            counter += 1
        instance_data['name'] = name

        # 2. Set this as the selected instance immediately
        self.selected_instance_name = name

        # 3. Start the Installation Process
        self.start_installation(instance_data)

    def start_installation(self, instance_data):
        """Saves config and spins up the worker thread."""
        name = instance_data['name']
        
        # 1. Save to Config (Optimistic Update)
        self.instances_data[name] = instance_data
        self.save_config()
        self.refresh_instances_list()
        
        # 2. Setup Progress Dialog
        # using QProgressDialog since we don't have your custom 'ProgressDialog' file source
        from PyQt5.QtWidgets import QProgressDialog
        self.prog_dlg = QProgressDialog("Installing...", "Cancel", 0, 0, self)
        self.prog_dlg.setWindowTitle("Creating Instance")
        self.prog_dlg.setWindowModality(Qt.WindowModal)
        self.prog_dlg.setMinimumDuration(0)
        self.prog_dlg.show()

        # 3. Setup Thread & Worker
        self._thread = QThread()
        self._worker = InstallationWorker(instance_data, self.java_path)
        self._worker.moveToThread(self._thread)

        # 4. Connect Signals
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.update_install_progress)
        self._worker.finished.connect(self.on_installation_finished)
        self.prog_dlg.canceled.connect(self._worker.stop)
        
        # Cleanup signals
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        # 5. Start
        self._thread.start()

    def update_install_progress(self, msg):
        """Update the dialog label with log messages."""
        if hasattr(self, 'prog_dlg'):
            self.prog_dlg.setLabelText(msg)
            print(f"[INSTALL] {msg}")

    def on_installation_finished(self, success, msg):
        """Clean up after installation and switch view."""
        # Close progress dialog if open
        if hasattr(self, 'prog_dlg'):
            self.prog_dlg.close()
        
        if success:
            QMessageBox.information(self, "Success", f"Instance installed successfully!\n{msg}")
            
            # 1. Refresh the sidebar list (reloads from config)
            self.refresh_instances_list()
            self.save_config()

            # 2. Find and Select the new item in the Sidebar
            if self.selected_instance_name:
                # Find the QListWidgetItem by string text
                items = self.instances_list.findItems(self.selected_instance_name, Qt.MatchExactly)
                if items:
                    item = items[0]
                    self.instances_list.setCurrentItem(item) # Visually highlight
                    # 3. Update the details page (Header, Icons, Buttons)
                    self.set_selected_instance(self.selected_instance_name)
            
            # 4. Force the main view to the Launcher Page
            self.pages.setCurrentWidget(self.page_launcher)
            
        else:
            QMessageBox.critical(self, "Installation Failed", msg)

    def mark_instance_last_played(self, name: str):
        if not name or name not in self.instances_data:
            return

        from datetime import datetime, timezone
        iso = datetime.now(timezone.utc).isoformat()

        self.instances_data[name]["last_played"] = iso
        self.instances_data[name]["last_played_instance"] = name  # optional per-instance

        # ✅ global "last played" pointer
        self.last_played_instance = name

        self.save_config()

        if self.selected_instance_name == name and hasattr(self, "card_last"):
            self.card_last.value.setText(self._time_ago(iso))

        self.update_home_launch_label()


    def _time_ago(self, iso_str: str) -> str:
        if not iso_str:
            return "—"

        from datetime import datetime, timezone

        try:
            # Handles "2025-12-19T21:03:10.123+00:00"
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            return "—"

        now = datetime.now(timezone.utc)
        seconds = int((now - dt).total_seconds())
        if seconds < 0:
            seconds = 0

        minute = 60
        hour = 60 * minute
        day = 24 * hour
        month = 30 * day
        year = 365 * day

        if seconds < minute:
            return "Just now" if seconds < 10 else f"{seconds} seconds ago"
        if seconds < hour:
            m = seconds // minute
            return f"{m} minute{'s' if m != 1 else ''} ago"
        if seconds < day:
            h = seconds // hour
            return f"{h} hour{'s' if h != 1 else ''} ago"
        if seconds < month:
            d = seconds // day
            return f"{d} day{'s' if d != 1 else ''} ago"
        if seconds < year:
            mo = seconds // month
            return f"{mo} month{'s' if mo != 1 else ''} ago"

        y = seconds // year
        return f"{y} year{'s' if y != 1 else ''} ago"


    def build_mod_manager_page(self, parent):
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        top = QHBoxLayout()
        self.btn_back_from_mods = QPushButton("← Back to Launcher")
        self.btn_back_from_mods.setObjectName("SecondaryButton")
        self.btn_back_from_mods.clicked.connect(lambda: self.pages.setCurrentIndex(0))

        self.mods_title = QLabel("Mod Manager (placeholder)")
        self.mods_title.setObjectName("InstanceTitle")

        top.addWidget(self.btn_back_from_mods, 0)
        top.addWidget(self.mods_title, 1, Qt.AlignLeft)
        lay.addLayout(top)

        self.mods_search = QLineEdit()
        self.mods_search.setPlaceholderText("Search installed mods...")
        self.mods_search.setObjectName("SearchBox")
        lay.addWidget(self.mods_search)

        hint = QLabel("You can keep using your existing manage_modsWindow for now, or rebuild it into this page.")
        hint.setObjectName("MutedText")
        lay.addWidget(hint)

        btn_open_old_mods = QPushButton("Open existing Manage Mods Window")
        btn_open_old_mods.setObjectName("PrimaryButton")
        btn_open_old_mods.clicked.connect(self.install_mods)  # reuse your existing install_mods()
        lay.addWidget(btn_open_old_mods)

        lay.addStretch(1)

    # ---------------- Navigation ----------------
    def open_new_instance_page(self):
        self.pages.setCurrentIndex(2)
        self.selected_instance_name = None
        self.refresh_instances_list()

    def open_mod_manager_page(self):
        if not self.selected_instance_name: return

        # Get data
        data = self.instances_data.get(self.selected_instance_name, {})

        # Load into page
        self.page_mods.load_instance_data(data)

        # Switch View
        self.pages.setCurrentWidget(self.page_mods)

    # ---------------- Sidebar behavior ----------------
    def refresh_instances_list(self):
        self.instances_list.clear()
        names = list(self.instances_data.keys())
        self.instances_label.setText(f"Instances ({len(names)})")

        for name in names:
            data = self.instances_data.get(name, {})
            version = data.get("version", "")
            loader = data.get("modloader", data.get("loader", ""))

            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, name)

            # 🔹 ICON HANDLING
            icon_path = self.get_instance_icon_path(name)
            pixmap = QPixmap(icon_path).scaled(
                32, 32,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            pixmap = self.rounded_pixmap(pixmap, radius=8)
            item.setIcon(QIcon(pixmap))

            item.setSizeHint(QSize(260, 56))
            self.instances_list.addItem(item)

        # keep selection highlight
        if self.selected_instance_name:
            for i in range(self.instances_list.count()):
                it = self.instances_list.item(i)
                if it.data(Qt.UserRole) == self.selected_instance_name:
                    self.instances_list.setCurrentItem(it)
                    break
        
        self.update_home_launch_label()

    def on_instance_clicked(self, item: QListWidgetItem):
        name = item.data(Qt.UserRole)
        self.set_selected_instance(name)

    def set_selected_instance(self, name: str):
        if not name or name not in self.instances_data:
            return
        self.selected_instance_name = name
        data = self.instances_data.get(name, {})

        # Update main header
        self.instance_title.setText(name)

        version = data.get("version", "—")
        loader = data.get("modloader", "—")
        mods = data.get("mods", data.get("mod_count", 0))
        tags = f"{version} • {loader}"
        if isinstance(mods, int) and mods > 0:
            tags += f" • {mods} mods"
        self.instance_tags.setText(tags)

        # Icon: you can map your saved image paths; for now, show emoji fallback
        # If you have image saved_path, you can set a pixmap here.
        icon_path = self.get_instance_icon_path(name)

        pixmap = QPixmap(icon_path).scaled(
            84, 84,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

        self.pages.setCurrentWidget(self.page_launcher)

        pixmap = self.rounded_pixmap(pixmap, radius=18)
        self.instance_big_icon.setPixmap(pixmap)
        self.instance_big_icon.setText("")  # clear emoji fallback


        # Cards
        self.card_last.value.setText(self._time_ago(data.get("last_played", "")))
        self.card_version.value.setText(version)
        self.card_loader.value.setText(loader)

        # Manage mods row subtitle
        if isinstance(mods, int):
            self.row_manage_mods.subtitle.setText(f"{mods} mods installed")
        else:
            self.row_manage_mods.subtitle.setText("Manage installed mods")

        # Launch button label
        self.btn_launch_big.setText(f"Launch {name}")

        self.update_launch_buttons_ui()

    # ---------------- Styles ----------------
    def apply_styles(self):
        # Dark zinc + emerald accent, close to your mockup
        self.setStyleSheet("""
        /* Reuse SettingsBlock style for LogsBlock */
        QFrame#LogsBlock {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            border-radius: 18px;
        }

        /* The actual text area */
        QTextEdit#LogConsole {
            background-color: #09090b; 
            color: #a1a1aa; 
            border: 1px solid #3f3f46; 
            border-radius: 12px;
            font-family: "Menlo", "Consolas", "Courier New", monospace;
            font-size: 11px;
            padding: 8px;
        }
       /* ===============================
        PROFILE MENU (NO FLICKER)
        =============================== */
        QFrame#ProfileMenu {
            background: #111114;
            border: 1px solid rgba(39,39,42,0.95);
            border-radius: 16px;
        }

        /* header stays the same */
        QFrame#ProfileMenuHeader {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #2a2a30, stop:1 #141418);
            border: 1px solid rgba(39,39,42,0.95);
            border-bottom: none;
            border-top-left-radius: 16px;
            border-top-right-radius: 16px;
        }

        /* Header */
        QFrame#ProfileMenuHeader {
            background: qlineargradient(
                x1:0,y1:0,x2:1,y2:1,
                stop:0 #2a2a30,
                stop:1 #141418
            );
            border: 1px solid rgba(39,39,42,0.95);
            border-bottom: none;
            border-top-left-radius: 16px;
            border-top-right-radius: 16px;
        }

        /* Header text */
        QLabel#ProfileMenuName {
            color: white;
            font-size: 14px;
            font-weight: 800;
        }
        QLabel#ProfileMenuEmail {
            color: #a1a1aa;
            font-size: 11px;
            font-weight: 700;
        }

        /* Divider */
        QFrame#ProfileMenuDivider {
            background: rgba(39,39,42,0.95);
            border: none;
            margin: 6px 0px;
        }

        /* Items */
        QPushButton#ProfileMenuItem {
            background: transparent;
            border: none;
            padding: 10px 14px;
            color: white;
            text-align: left;
            font-weight: 400;
            border-radius: 10px;
        }
        QPushButton#ProfileMenuItem:hover {
            background: rgba(63,63,70,0.55);
        }
        QPushButton#ProfileMenuItem:pressed {
            background: rgba(82,82,91,0.75);
        }

        /* ----- Scroll area inside the WhatsNew card ----- */
        QScrollArea#NewsScrollArea {
            background: transparent;
            border: none;
        }
        QWidget#NewsScrollContent {
            background: transparent;
        }

        /* Text styles inside each row */
        QLabel#MCTitle {
            color: white;
            font-size: 14px;
            font-weight: 900;
        }
        QLabel#MCDate {
            color: #a1a1aa;
            font-size: 11px;
            font-weight: 700;
        }
        QLabel#MCShort {
            color: #d4d4d8;
            font-size: 12px;
        }

        /* Optional: prettier progress bar */
        QProgressBar#MCProgress {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            border-radius: 10px;
            height: 10px;
        }
        QProgressBar#MCProgress::chunk {
            background: #10b981;
            border-radius: 10px;
        }

        /* Scrollbar styling (mac still shows overlay sometimes, but this helps) */
        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: rgba(113,113,122,0.55);
            border-radius: 5px;
            min-height: 24px;
        }
        QScrollBar::handle:vertical:hover {
            background: rgba(161,161,170,0.75);
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: transparent;
        }

        QFrame#WhatsNewBlock {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            border-radius: 18px;
        }
        QPushButton#LinkButton::icon { margin-right: 6px; }
        QPushButton#HelpPill {
            background: transparent;
            border: 1px solid rgba(39,39,42,0.85);
            border-radius: 12px;
            padding: 6px 10px;
            color: #34d399;
            font-weight: 800;
        }
        QPushButton#HelpPill:hover {
            border: 1px solid rgba(16,185,129,0.75);
            background: rgba(16,185,129,0.10);
        }
        QPushButton#HelpPill::icon { margin-right: 6px; }
        QListWidget::item {
            icon-size: 32px;
        }
        QListWidget::item:selected {
            icon-size: 32px;
        }
        QLabel#AppLogo {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            border-radius: 10px;
        }

        QMainWindow { background: #0f172a; } /* fallback */
        QWidget#Pages { background: #18181b; }

        QFrame#Sidebar { background: #09090b; border-right: 1px solid #27272a; }
        QFrame#SidebarHeader { }
        QLabel#AppTitle { color: white; font-size: 22px; font-weight: 800; }
        QLabel#AppSubtitle { color: #71717a; font-size: 11px; }

        QLabel#SidebarSectionLabel { color: #71717a; font-size: 11px; font-weight: 800; letter-spacing: 1px; }
        QListWidget#InstancesList {
            background: transparent;
            border: none;
            color: #d4d4d8;
            outline: none;
        }
        QListWidget#InstancesList::item {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            margin: 6px 0px;
            padding: 12px;
            border-radius: 14px;
        }
        QListWidget#InstancesList::item:selected {
            background: #059669;
            border: 1px solid #10b981;
            color: white;
        }

        QFrame#ProfileCard { background: rgba(39,39,42,0.35); border: 1px solid rgba(39,39,42,0.65); border-radius: 14px; }
        QLabel#ProfileName { color: white; font-weight: 700; }
        QLabel#ProfileStatus { color: #71717a; font-size: 11px; }

        QPushButton#PrimaryButton {
            background: #059669;
            color: white;
            border: none;
            border-radius: 14px;
            padding: 12px;
            font-weight: 800;
        }
        QPushButton#PrimaryButton:hover { background: #10b981; }

        QPushButton#SecondaryButton {
            background: #3f3f46;
            color: white;
            border: none;
            border-radius: 12px;
            padding: 10px 12px;
            font-weight: 700;
        }
        QPushButton#SecondaryButton:hover { background: #52525b; }

        QPushButton#IconButton {
            background: rgba(63,63,70,0.7);
            color: white;
            border: 1px solid rgba(39,39,42,0.9);
            border-radius: 12px;
            font-weight: 800;
        }
        QPushButton#IconButton:hover { background: rgba(82,82,91,0.9); }

        QPushButton#DangerIconButton {
            background: rgba(220,38,38,0.18);
            color: #fca5a5;
            border: 1px solid rgba(220,38,38,0.25);
            border-radius: 12px;
            font-weight: 800;
        }
        QPushButton#DangerIconButton:hover { background: rgba(220,38,38,0.28); }

        QFrame#MainHeader { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #27272a, stop:1 #18181b); border-bottom: 1px solid #27272a; }
       QLabel#BigIcon {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            border-radius: 18px;
            color: white;
            font-size: 34px;
            font-weight: 900;
        }
        QLabel#InstanceTitle { color: white; font-size: 28px; font-weight: 900; }
        QLabel#InstanceTags { color: #a1a1aa; font-size: 12px; }

        QFrame#Card { background: rgba(39,39,42,0.35); border: 1px solid rgba(39,39,42,0.65); border-radius: 18px; }
        QLabel#CardTitle { color: #a1a1aa; font-size: 12px; }
        QLabel#CardValue { color: white; font-size: 18px; font-weight: 800; }

        QFrame#SettingsBlock { background: rgba(39,39,42,0.35); border: 1px solid rgba(39,39,42,0.65); border-radius: 18px; }
        QLabel#SectionTitle { color: white; font-size: 16px; font-weight: 800; }

        QFrame#SectionRow { border-bottom: 1px solid rgba(39,39,42,0.65); }
        QLabel#RowTitle { color: white; font-weight: 700; }
        QLabel#RowSubtitle { color: #a1a1aa; font-size: 12px; }
        QPushButton#LinkButton { background: transparent; border: none; color: #34d399; font-weight: 800; }
        QPushButton#LinkButton:hover { color: #6ee7b7; }

        QFrame#BottomBar { background: #09090b; border-top: 1px solid #27272a; }
        QPushButton#LaunchButton {
            background-color: #10b981;
            color: white;
            border: none;
            border-radius: 14px;
            font-size: 17px;
            font-weight: 700;
        }
        QPushButton#LaunchButton:hover {
            background-color: #059669;
        }

        QLineEdit#SearchBox {
            background: rgba(39,39,42,0.6);
            border: 1px solid rgba(39,39,42,0.9);
            color: white;
            padding: 12px 14px;
            border-radius: 14px;
        }
        QLabel#MutedText { color: #a1a1aa; }
        QFrame#SidebarDivider {
            background: #27272a;
            border: none;
            margin-top: 10px;
            margin-bottom: 10px;
        }

        QPushButton#ProfileButton {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            border-radius: 14px;
            text-align: left;
        }
        QPushButton#ProfileButton:hover {
            background: rgba(63,63,70,0.55);
        }

        QLabel#ProfileAvatar {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #3b82f6, stop:1 #a855f7);
            border-radius: 10px;
        }

        QLabel#ProfileGear {
            color: #a1a1aa;
        }
        QPushButton#LaunchButton {
            padding-left: 18px;
            text-align: center;
        }
        QPushButton#LaunchButton::icon {
            margin-right: 10px;
        }

        QLabel#HomeTitle { color: white; font-size: 34px; font-weight: 900; }
        QLabel#HomeSubtitle { color: #a1a1aa; font-size: 13px; }

        QWidget#HomeOverlay {
            background: rgba(9, 9, 11, 0.55);
        }

        QFrame#NewsBlock {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            border-radius: 18px;
        }

        QLabel#NewsTitle { color: white; font-size: 16px; font-weight: 800; }
        QListWidget#NewsList {
            background: transparent;
            border: none;
            color: #d4d4d8;
        }
        QListWidget#NewsList::item {
            background: rgba(39,39,42,0.35);
            border: 1px solid rgba(39,39,42,0.65);
            margin: 6px 0px;
            padding: 10px;
            border-radius: 14px;
        }

        """)

    # ---------------- Hook your existing methods ----------------
    # You already have these methods in your current class.
    # Move them over or keep your old class and transplant this UI structure.
    def add_instance(self):
        """REUSE: your add_instance() that opens add_instance_window and connects instanceCreated"""
        print("TODO: reuse your add_instance_window flow here")

    # ---------------- LAUNCHING LOGIC ----------------

    def launch_instance(self):
        """Toggle: Launch if idle, Kill if running."""
        # 1. Auth Check
        if not self.is_authenticated():
            QMessageBox.warning(self, "Auth Required", "Please sign in first.")
            return

        # 2. Selection Check
        if not self.selected_instance_name:
            return

        # 3. TOGGLE LOGIC
        if self.selected_instance_name in self.active_instances:
            # IT IS RUNNING -> KILL IT
            self.kill_instance(self.selected_instance_name)
            return

        # 4. Record Stats (Only on launch)
        self.mark_instance_last_played(self.selected_instance_name)

        print(f"[Launch] Starting: {self.selected_instance_name}")
        
        instance_data = self.instances_data.get(self.selected_instance_name, {})
        modloader = instance_data.get('modloader', 'Vanilla')
        version = instance_data.get('version', '')

        if modloader == "Fabric":
            self.launch_fabric_instance(version, instance_data)
        else:
            self.launch_vanilla_instance(version)

    def launch_fabric_instance(self, version, instance_data):
        """Prepare arguments for Fabric launch"""
        script_name = "fabric.command"
        launch_script = os.path.join(BASE_DIR, "scripts", script_name)
        
        fabric_version = instance_data.get('fabric_version', None)

        # ✅ Ensure we use self.java_path
        java_exec = self.java_path if self.java_path else "java"

        args = [
            launch_script, 
            self.username, 
            self.uuid, 
            version, 
            fabric_version, 
            self.access_token, 
            self.selected_instance_name, 
            java_exec # ✅ Passed here
        ]
        
        self._run_launch_thread(args)

    def launch_vanilla_instance(self, version):
        """Prepare arguments for Vanilla launch"""
        script_name = "launch_vanilla.command"
        launch_script = os.path.join(BASE_DIR, "scripts", script_name)
        
        # ✅ Ensure we use self.java_path
        java_exec = self.java_path if self.java_path else "java"

        args = [
            launch_script, 
            self.username, 
            self.uuid, 
            version, 
            self.access_token, 
            self.selected_instance_name, 
            java_exec # ✅ Passed here
        ]

        self._run_launch_thread(args)

    def _handle_log_output(self, text):
        """Slot to append log text to the UI safely."""
        if hasattr(self, 'log_view'):
            self.log_view.append(text)
            # Auto scroll to bottom
            sb = self.log_view.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _run_launch_thread(self, args):
        """Executes the subprocess in a separate thread to prevent GUI freezing"""
        
        # Clear previous logs on new launch
        if hasattr(self, 'log_view'):
            self.log_view.clear()
            self.log_view.append(f"Executing command:\n{' '.join(args)}\n")

        # Ensure script is executable (Mac/Linux)
        if args[0].endswith(".command") or args[0].endswith(".sh"):
            subprocess.run(["chmod", "+x", args[0]])

        def runner():
            instance_name = self.selected_instance_name
            active_name = instance_name
            try:
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Register active process
                self.active_instances[instance_name] = process
                
                # Emit signal that instance has started
                self.instance_started.emit(active_name)
                
                # Stream output
                for line in process.stdout:
                    # Emit signal instead of printing
                    self.log_output.emit(line.strip())
                    
                process.wait()
                self.log_output.emit(f"\nProcess finished with exit code: {process.returncode}")
                
            except Exception as e:
                self.log_output.emit(f"Error launching instance: {str(e)}")
            finally:
                # Cleanup
                if instance_name in self.active_instances:
                    del self.active_instances[instance_name]

                # Emit signal that instance stopped
                self.instance_stopped.emit(active_name)
        # Start the background thread
        threading.Thread(target=runner, daemon=True).start()

    def _on_instance_state_changed(self, instance_name):
        """Slot called when any instance starts or stops."""
        # Refresh buttons based on current selection
        self.update_launch_buttons_ui()

    def update_launch_buttons_ui(self):
        """Updates the Big Launch button and Home button based on running PIDs."""
        
        # --- 1. Update Instance Page Button (Big Button) ---
        if self.selected_instance_name:
            is_running = self.selected_instance_name in self.active_instances
            self._apply_button_state(self.btn_launch_big, is_running, self.selected_instance_name)
        
        # --- 2. Update Home Page Button ---
        # Determine which instance the home button represents
        home_inst_name = getattr(self, "last_played_instance", "")
        if not home_inst_name or home_inst_name not in self.instances_data:
            home_inst_name = self._pick_most_recent_instance()
        
        if home_inst_name:
            is_running = home_inst_name in self.active_instances
            self._apply_button_state(self.btn_launch_home, is_running, home_inst_name, is_home=True)

    def _apply_button_state(self, btn, is_running, instance_name, is_home=False):
        """Helper to style a button as Launch (Green) or Stop (Red)."""
        if is_running:
            btn.setText(f"Stop {instance_name}")
            btn.setObjectName("StopButton") # Requires CSS update below
            # Force red style directly to ensure override
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ef4444; 
                    color: white; 
                    border: none; 
                    border-radius: 14px; 
                    font-size: 17px; 
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #dc2626; }
            """)
            self.set_button_svg_icon(btn, "Kill", size=22)
        else:
            prefix = "Launch last played" if is_home else "Launch"
            display_name = f" ({instance_name})" if is_home else f" {instance_name}"
            btn.setText(f"{prefix}{display_name}")
            btn.setObjectName("LaunchButton")
            # Force green style (restore)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #10b981; 
                    color: white; 
                    border: none; 
                    border-radius: 14px; 
                    font-size: 17px; 
                    font-weight: 700;
                }
                QPushButton:hover { background-color: #059669; }
            """)
            self.set_button_svg_icon(btn, "Launch", size=22)

    def open_instance_folder(self):
        if not self.selected_instance_name:
            return
        
        # 1. Construct the path
        path = os.path.join(GAME_DIR, "instances", self.selected_instance_name)
        
        # 2. Create it if it doesn't exist (Fixes the error)
        if not os.path.exists(path):
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create instance folder:\n{e}")
                return

        # 3. Open the folder (Cross-platform safe)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")

    def edit_instance(self):
        """REUSE: your edit_instance() logic"""
        if not self.selected_instance_name:
            return
        print("TODO: open EditInstanceWindow for", self.selected_instance_name)

    def delete_instance(self):
        """REUSE: your delete_instance() logic (with your styled QMessageBox if you want)"""
        if not self.selected_instance_name:
            return
        name = self.selected_instance_name
        if name not in self.instances_data:
            return

        box = QMessageBox(self)
        box.setWindowTitle("Delete Instance")
        box.setText(f"Delete '{name}'?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        if box.exec_() != QMessageBox.Yes:
            return

        instance_path = os.path.join(GAME_DIR, "instances", name)
        try:
            if os.path.exists(instance_path):
                shutil.rmtree(instance_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        del self.instances_data[name]
        self.save_config()
        self.refresh_instances_list()
        self.instance_title.setText("Select an instance")
        self.instance_tags.setText("")
        self.btn_launch_big.setText("Launch")
        self.instances_list.clearSelection()
        self.selected_instance_name = None
        self.pages.setCurrentWidget(self.page_home)
        self.update_home_launch_label()


    def update_home_launch_label(self):
        if not hasattr(self, "btn_launch_home"):
            return

        if not self.instances_data:
            self.btn_launch_home.setText("Launch last played")
            return

        name = getattr(self, "last_played_instance", "")
        if not name or name not in self.instances_data:
            name = self._pick_most_recent_instance() or next(iter(self.instances_data.keys()))

        self.btn_launch_home.setText(f"Launch last played ({name})")



    def install_mods(self):
        """REUSE: your install_mods() (opens manage_modsWindow)"""
        print("TODO: call your existing install_mods()")

   # ---------------- LauncherV2 Methods ----------------

    def open_account_manager(self):
        """Opens the new AccountWindow"""
        dlg = AccountWindow(parent=None)
        # Connect the signal from AccountWindow to our success handler
        dlg.account_updated.connect(self._on_login_success)
        dlg.exec_()

    def _on_login_success(self, data):
        self.username = data.get("username")
        self.uuid = data.get("uuid")
        self.access_token = data.get("access_token")

        # ✅ NEW: save login time (UTC ISO)
        from datetime import datetime, timezone
        self.last_login_utc = datetime.now(timezone.utc).isoformat()

        self.save_config()

        self._set_auth_ui_state()
        self.update_launch_auth_state()

        print(f"[AUTH] Logged in as {self.username}")

    def configure_java_args(self):
        print("TODO: java args UI")

    def configure_memory(self):
        print("TODO: memory UI")

    def configure_resolution(self):
        print("TODO: resolution UI")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON_PATH2))
    app.setApplicationName("RBLauncher: Dusk")
    w = LauncherV2()
    w.show()
    sys.exit(app.exec_())

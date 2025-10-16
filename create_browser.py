import sys
import requests
import json
import subprocess
import platform
import os
import base64
import re
import shutil
from io import BytesIO
from PyQt6.QtCore import QUrl, Qt, QThread, pyqtSignal, QBuffer, QPropertyAnimation, QEasingCurve, QSize, QTimer, QStandardPaths
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLineEdit, QPushButton, QTextEdit, 
                             QSplitter, QLabel, QComboBox, QMessageBox, QProgressDialog,
                             QTabWidget, QToolButton, QMenu, QFileDialog, QProgressBar,
                             QDialog, QListWidget, QListWidgetItem)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineDownloadRequest
from PyQt6.QtGui import QImage, QPainter, QAction, QIcon, QDesktopServices

class DownloadManager(QDialog):
    """Dialog to show active and completed downloads"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloads")
        self.setGeometry(200, 200, 700, 400)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Download Manager")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Downloads list
        self.downloads_list = QListWidget()
        layout.addWidget(self.downloads_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.open_folder_btn = QPushButton("Open Downloads Folder")
        self.open_folder_btn.clicked.connect(self.open_downloads_folder)
        btn_layout.addWidget(self.open_folder_btn)
        
        self.clear_btn = QPushButton("Clear Completed")
        self.clear_btn.clicked.connect(self.clear_completed)
        btn_layout.addWidget(self.clear_btn)
        
        btn_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        
        layout.addLayout(btn_layout)
        
        self.downloads = []  # Store download info
    
    def add_download(self, download_item):
        """Add a new download to the list"""
        filename = download_item.downloadFileName()
        
        # Create widget for this download
        item = QListWidgetItem()
        widget = QWidget()
        widget_layout = QVBoxLayout(widget)
        widget_layout.setContentsMargins(5, 5, 5, 5)
        
        # Filename label
        name_label = QLabel(f"📥 {filename}")
        name_label.setStyleSheet("font-weight: bold;")
        widget_layout.addWidget(name_label)
        
        # Progress bar
        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setValue(0)
        widget_layout.addWidget(progress)
        
        # Status label
        status_label = QLabel("Starting download...")
        widget_layout.addWidget(status_label)
        
        item.setSizeHint(widget.sizeHint())
        self.downloads_list.addItem(item)
        self.downloads_list.setItemWidget(item, widget)
        
        # Store references
        download_info = {
            'item': item,
            'widget': widget,
            'progress': progress,
            'status': status_label,
            'download': download_item,
            'filename': filename,
            'completed': False
        }
        self.downloads.append(download_info)
        
        # Connect signals
        download_item.receivedBytesChanged.connect(
            lambda: self.update_progress(download_info)
        )
        download_item.stateChanged.connect(
            lambda state: self.update_state(download_info, state)
        )
        
        return download_info
    
    def update_progress(self, download_info):
        """Update download progress"""
        download = download_info['download']
        received = download.receivedBytes()
        total = download.totalBytes()
        
        if total > 0:
            percent = int((received / total) * 100)
            download_info['progress'].setValue(percent)
            
            # Format sizes
            received_mb = received / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            download_info['status'].setText(
                f"Downloading... {received_mb:.1f} MB / {total_mb:.1f} MB ({percent}%)"
            )
    
    def update_state(self, download_info, state):
        """Update download state"""
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            download_info['completed'] = True
            download_info['progress'].setValue(100)
            download_info['status'].setText(f"✅ Completed - {download_info['download'].downloadDirectory()}")
            download_info['status'].setStyleSheet("color: green; font-weight: bold;")
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            download_info['status'].setText("❌ Cancelled")
            download_info['status'].setStyleSheet("color: red;")
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            download_info['status'].setText("⚠️ Failed - Connection interrupted")
            download_info['status'].setStyleSheet("color: orange;")
    
    def clear_completed(self):
        """Remove completed downloads from the list"""
        for download_info in self.downloads[:]:
            if download_info['completed']:
                row = self.downloads_list.row(download_info['item'])
                self.downloads_list.takeItem(row)
                self.downloads.remove(download_info)
    
    def open_downloads_folder(self):
        """Open the downloads folder in file explorer"""
        downloads_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(downloads_path))


class OllamaInstaller(QThread):
    """Worker thread to install Ollama"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self):
        super().__init__()
        self.system = platform.system()
    
    def run(self):
        try:
            self.progress.emit("Detecting your operating system...")
            
            if self.system == "Windows":
                self.install_windows()
            elif self.system == "Darwin":  # macOS
                self.install_macos()
            elif self.system == "Linux":
                self.install_linux()
            else:
                self.finished.emit(False, f"Unsupported OS: {self.system}")
        except Exception as e:
            self.finished.emit(False, f"Installation failed: {str(e)}")
    
    def install_windows(self):
        self.progress.emit("Downloading Ollama for Windows...")
        
        url = "https://ollama.com/download/OllamaSetup.exe"
        installer_path = os.path.join(os.environ.get("TEMP", "."), "OllamaSetup.exe")
        
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        with open(installer_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        self.progress.emit(f"Downloading... {percent}%")
        
        self.progress.emit("Running installer...")
        subprocess.run([installer_path, "/S"], check=True)
        
        self.progress.emit("Installation complete! Starting Ollama...")
        subprocess.Popen(["ollama", "serve"], 
                        creationflags=subprocess.CREATE_NO_WINDOW if self.system == "Windows" else 0)
        
        self.finished.emit(True, "Ollama installed successfully!")
    
    def install_macos(self):
        self.progress.emit("Downloading Ollama for macOS...")
        
        url = "https://ollama.com/download/Ollama-darwin.zip"
        installer_path = "/tmp/Ollama.zip"
        
        response = requests.get(url, stream=True)
        with open(installer_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        self.progress.emit("Installing...")
        subprocess.run(["unzip", "-o", installer_path, "-d", "/Applications/"], check=True)
        
        self.progress.emit("Starting Ollama...")
        subprocess.Popen(["/Applications/Ollama.app/Contents/MacOS/ollama", "serve"])
        
        self.finished.emit(True, "Ollama installed successfully!")
    
    def install_linux(self):
        self.progress.emit("Installing Ollama for Linux...")
        
        install_script = subprocess.check_output(
            ["curl", "-fsSL", "https://ollama.com/install.sh"]
        )
        
        subprocess.run(["sh", "-c", install_script.decode()], check=True)
        
        self.progress.emit("Starting Ollama...")
        subprocess.Popen(["ollama", "serve"])
        
        self.finished.emit(True, "Ollama installed successfully!")


class OllamaWorker(QThread):
    """Worker thread to handle Ollama API calls without blocking UI"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    streaming = pyqtSignal(str)
    
    def __init__(self, messages, model, image_base64=None):
        super().__init__()
        self.messages = messages
        self.model = model
        self.image_base64 = image_base64
    
    def run(self):
        try:
            vision_models = ["llava", "bakllava", "llava-phi3", "llama3.2-vision"]
            supports_vision = any(vm in self.model.lower() for vm in vision_models)
            
            if self.image_base64 and supports_vision:
                prompt = ""
                for msg in self.messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "user":
                        prompt += f"User: {content}\n\n"
                    elif role == "assistant":
                        prompt += f"Assistant: {content}\n\n"
                
                prompt += "Assistant: "
                
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [self.image_base64],
                        "stream": False
                    },
                    timeout=120
                )
            else:
                prompt = ""
                for msg in self.messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "user":
                        prompt += f"User: {content}\n\n"
                    elif role == "assistant":
                        prompt += f"Assistant: {content}\n\n"
                
                prompt += "Assistant: "
                
                response = requests.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=120
                )
            
            if response.status_code == 200:
                data = response.json()
                assistant_message = data["response"]
                self.finished.emit(assistant_message)
            else:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("error", {}).get("message", response.text)
                except:
                    pass
                self.error.emit(f"Ollama Error ({response.status_code}): {error_detail}")
        except requests.exceptions.ConnectionError:
            self.error.emit("Cannot connect to Ollama. Make sure Ollama is running!\n\nStart it with: ollama serve")
        except requests.exceptions.Timeout:
            self.error.emit("Request timed out. The model might be too large or your computer is slow.")
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")


class BrowserTab(QWidget):
    """Individual browser tab with its own web view"""
    def __init__(self, url="https://www.google.com", profile=None, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.browser = QWebEngineView()
        
        # Use the persistent profile if provided
        if profile:
            from PyQt6.QtWebEngineCore import QWebEnginePage
            page = QWebEnginePage(profile, self.browser)
            self.browser.setPage(page)
        
        self.browser.setUrl(QUrl(url))
        layout.addWidget(self.browser)
        
        # Track fullscreen state
        self.is_fullscreen = False
        self.original_parent = None
        self.original_layout = layout
        
        # Connect fullscreen request handler
        self.browser.page().fullScreenRequested.connect(self.handle_fullscreen_request)
    
    def handle_fullscreen_request(self, request):
        """Handle fullscreen requests from web pages (like YouTube)"""
        request.accept()
        
        if request.toggleOn():
            self.enter_fullscreen()
        else:
            self.exit_fullscreen()
    
    def enter_fullscreen(self):
        """Enter fullscreen mode"""
        if self.is_fullscreen:
            return
        
        self.is_fullscreen = True
        
        # Store original parent
        self.original_parent = self.parent()
        
        # Remove from current layout
        if self.original_parent:
            self.original_parent.layout().removeWidget(self)
        
        # Make this widget a top-level window
        self.setParent(None)
        self.setWindowFlags(Qt.WindowType.Window)
        self.showFullScreen()
        
        # Notify parent window
        if self.parent_window:
            self.parent_window.on_tab_fullscreen(True)
    
    def exit_fullscreen(self):
        """Exit fullscreen mode"""
        if not self.is_fullscreen:
            return
        
        self.is_fullscreen = False
        
        # Restore to original parent
        self.setWindowFlags(Qt.WindowType.Widget)
        if self.original_parent:
            self.setParent(self.original_parent)
            self.original_parent.layout().addWidget(self)
        
        self.showNormal()
        
        # Notify parent window
        if self.parent_window:
            self.parent_window.on_tab_fullscreen(False)
    
    def keyPressEvent(self, event):
        """Handle key presses in fullscreen mode"""
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.browser.page().triggerAction(self.browser.page().WebAction.ExitFullScreen)
        super().keyPressEvent(event)


class GlitchBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Glitch Create - AI-Powered Browser")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create persistent profile for saving login sessions
        try:
            self.setup_persistent_profile()
        except Exception as e:
            print(f"Warning: Could not setup persistent profile: {e}")
            self.web_profile = None
        
        # Create download manager
        self.download_manager = DownloadManager(self)
        
        # Setup download handling
        if self.web_profile:
            self.web_profile.downloadRequested.connect(self.on_download_requested)
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Browser controls
        nav_layout = QHBoxLayout()
        
        self.back_btn = QPushButton("←")
        self.back_btn.setFixedWidth(40)
        self.back_btn.clicked.connect(self.navigate_back)
        nav_layout.addWidget(self.back_btn)
        
        self.forward_btn = QPushButton("→")
        self.forward_btn.setFixedWidth(40)
        self.forward_btn.clicked.connect(self.navigate_forward)
        nav_layout.addWidget(self.forward_btn)
        
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedWidth(40)
        self.refresh_btn.clicked.connect(self.refresh_page)
        nav_layout.addWidget(self.refresh_btn)
        
        self.home_btn = QPushButton("🏠")
        self.home_btn.setFixedWidth(40)
        self.home_btn.setToolTip("Go to homepage")
        self.home_btn.clicked.connect(self.go_home)
        nav_layout.addWidget(self.home_btn)
        
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL...")
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_layout.addWidget(self.url_bar)
        
        self.go_btn = QPushButton("Go")
        self.go_btn.setFixedWidth(60)
        self.go_btn.clicked.connect(self.navigate_to_url)
        nav_layout.addWidget(self.go_btn)
        
        # Downloads button
        self.downloads_btn = QPushButton("📥 Downloads")
        self.downloads_btn.setFixedWidth(100)
        self.downloads_btn.setToolTip("View downloads")
        self.downloads_btn.clicked.connect(self.show_downloads)
        nav_layout.addWidget(self.downloads_btn)
        
        # Fullscreen button
        self.fullscreen_btn = QPushButton("⛶ Fullscreen")
        self.fullscreen_btn.setFixedWidth(100)
        self.fullscreen_btn.setToolTip("Toggle fullscreen (F11)")
        self.fullscreen_btn.clicked.connect(self.toggle_browser_fullscreen)
        nav_layout.addWidget(self.fullscreen_btn)
        
        # New tab button
        self.new_tab_btn = QPushButton("+ Tab")
        self.new_tab_btn.setFixedWidth(70)
        self.new_tab_btn.setToolTip("Open new tab (Ctrl+T)")
        self.new_tab_btn.clicked.connect(self.add_new_tab)
        nav_layout.addWidget(self.new_tab_btn)
        
        # Toggle chat button
        self.toggle_chat_btn = QPushButton("◀ Hide Chat")
        self.toggle_chat_btn.setFixedWidth(100)
        self.toggle_chat_btn.clicked.connect(self.toggle_chat_panel)
        nav_layout.addWidget(self.toggle_chat_btn)
        
        layout.addLayout(nav_layout)
        
        # Tab widget for multiple browser tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Splitter for browser and AI chat
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tab_widget)
        
        # AI Chat panel
        self.chat_container = QWidget()
        chat_container_layout = QVBoxLayout(self.chat_container)
        chat_container_layout.setContentsMargins(0, 0, 0, 0)
        
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_container_layout.addWidget(chat_widget)
        
        # Model selector
        model_layout = QHBoxLayout()
        model_label = QLabel("AI Model:")
        model_label.setStyleSheet("font-weight: bold;")
        model_layout.addWidget(model_label)
        
        self.model_selector = QComboBox()
        self.model_selector.addItems([
            "llama3.2-vision:11b",
            "llama3.2-vision:90b", 
            "llava",
            "llava-phi3",
            "bakllava",
            "llama3.2",
            "llama3.2:1b",
            "llama3.1",
            "mistral",
            "phi3",
            "gemma2",
            "qwen2.5"
        ])
        self.model_selector.setToolTip("Select which Ollama model to use (Vision models can see screenshots!)")
        self.model_selector.currentTextChanged.connect(self.on_model_changed)
        model_layout.addWidget(self.model_selector)
        
        self.current_model = self.model_selector.currentText()
        self.installed_models = []
        self.pending_screenshot = False
        
        self.check_models_btn = QPushButton("Check Models")
        self.check_models_btn.clicked.connect(self.check_available_models)
        model_layout.addWidget(self.check_models_btn)
        
        self.clear_chat_btn = QPushButton("Clear Chat")
        self.clear_chat_btn.setToolTip("Clear conversation history")
        self.clear_chat_btn.clicked.connect(self.clear_chat)
        model_layout.addWidget(self.clear_chat_btn)
        
        # Add clear cookies button
        self.clear_cookies_btn = QPushButton("Clear Logins")
        self.clear_cookies_btn.setToolTip("Clear saved login sessions and cookies")
        self.clear_cookies_btn.clicked.connect(self.clear_saved_logins)
        model_layout.addWidget(self.clear_cookies_btn)
        
        model_layout.addStretch()
        chat_layout.addLayout(model_layout)
        
        chat_label = QLabel("💬 Chat with Local AI")
        chat_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        chat_layout.addWidget(chat_label)
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("background-color: #ffffff; padding: 10px; color: #000000;")
        chat_layout.addWidget(self.chat_display)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask AI about this page or anything else...")
        self.chat_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.chat_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)
        
        self.page_context_btn = QPushButton("📄 Analyze Page")
        self.page_context_btn.setFixedWidth(130)
        self.page_context_btn.clicked.connect(self.analyze_page)
        input_layout.addWidget(self.page_context_btn)
        
        self.screenshot_btn = QPushButton("📸 See Page")
        self.screenshot_btn.setFixedWidth(110)
        self.screenshot_btn.setToolTip("Take screenshot and let AI see the page (requires vision model)")
        self.screenshot_btn.clicked.connect(self.analyze_page_with_vision)
        input_layout.addWidget(self.screenshot_btn)
        
        chat_layout.addLayout(input_layout)
        splitter.addWidget(self.chat_container)
        
        splitter.setSizes([900, 500])
        self.splitter = splitter
        layout.addWidget(splitter)
        
        # State variables
        self.chat_visible = True
        self.chat_width = 500
        self.conversation_history = []
        self.worker = None
        self.installer = None
        self.home_page = "https://www.google.com"
        self.browser_fullscreen = False
        
        # Add first tab
        self.add_new_tab(self.home_page)
        
        # Add keyboard shortcuts
        self.setup_shortcuts()
        
        # Welcome message
        self.add_to_chat("System", "🚀 Welcome to Glitch Create - Your AI-Powered Browser!")
        
        if self.web_profile:
            self.add_to_chat("AI", f"Hi! I'm a local AI running on your computer with Ollama. I'm completely free and private!\n\nCurrent model: {self.model_selector.currentText()}\n\n🔒 Login sessions will be saved and persist between restarts.\n📥 File downloads are fully supported - click any download link!\n⛶ Press F11 or click Fullscreen for immersive browsing!\n\nI can help you browse the web and answer questions. Try asking me about the current page or anything else!\n\n✨ New: I can now open websites for you! Just ask me to visit any website and I'll navigate there automatically.")
        else:
            self.add_to_chat("AI", f"Hi! I'm a local AI running on your computer with Ollama. I'm completely free and private!\n\nCurrent model: {self.model_selector.currentText()}\n\n📥 File downloads are fully supported!\n⛶ Press F11 for fullscreen mode!\n\nI can help you browse the web and answer questions. Try asking me about the current page or anything else!\n\n✨ New: I can now open websites for you! Just ask me to visit any website and I'll navigate there automatically.")
        
        # Auto-start Ollama
        self.auto_start_ollama()
    
    def on_download_requested(self, download):
        """Handle download requests"""
        # Get default downloads folder
        downloads_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        
        # Set download path
        suggested_filename = download.downloadFileName()
        download_path = os.path.join(downloads_path, suggested_filename)
        
        # Ask user if they want to save the file
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            download_path,
            "All Files (*.*)"
        )
        
        if file_path:
            download.setDownloadFileName(os.path.basename(file_path))
            download.setDownloadDirectory(os.path.dirname(file_path))
            download.accept()
            
            # Add to download manager
            self.download_manager.add_download(download)
            
            # Show notification
            self.add_to_chat("System", f"📥 Downloading: {os.path.basename(file_path)}")
            
            # Auto-show download manager
            if not self.download_manager.isVisible():
                self.download_manager.show()
        else:
            download.cancel()
    
    def show_downloads(self):
        """Show the download manager dialog"""
        self.download_manager.show()
        self.download_manager.raise_()
        self.download_manager.activateWindow()
    
    def toggle_browser_fullscreen(self):
        """Toggle fullscreen mode for the entire browser window"""
        if self.browser_fullscreen:
            self.showNormal()
            self.fullscreen_btn.setText("⛶ Fullscreen")
            self.browser_fullscreen = False
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText("⛶ Exit Fullscreen")
            self.browser_fullscreen = True
    
    def on_tab_fullscreen(self, is_fullscreen):
        """Called when a tab enters or exits fullscreen"""
        # Hide/show main window controls when tab is in fullscreen
        if is_fullscreen:
            self.menuBar().hide()
        else:
            self.menuBar().show()
    
    def setup_persistent_profile(self):
        """Setup a persistent web profile to save cookies and session data"""
        try:
            # Get application data directory
            data_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
            
            # Create base directory if needed
            if not os.path.exists(data_path):
                os.makedirs(data_path, exist_ok=True)
            
            profile_path = os.path.join(data_path, "GlitchProfile")
            
            # Create directory if it doesn't exist
            os.makedirs(profile_path, exist_ok=True)
            
            # Store profile path for later use
            self.profile_path = profile_path
            
            # Create persistent profile with a unique name
            self.web_profile = QWebEngineProfile("GlitchBrowserProfile")
            
            # Set persistent storage path
            self.web_profile.setPersistentStoragePath(profile_path)
            
            # Force persistent cookies
            self.web_profile.setPersistentCookiesPolicy(
                QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
            )
            
            # Set cache path
            cache_path = os.path.join(profile_path, "cache")
            os.makedirs(cache_path, exist_ok=True)
            self.web_profile.setCachePath(cache_path)
            
            print(f"Profile setup successful at: {profile_path}")
            
        except Exception as e:
            print(f"Error setting up profile: {e}")
            raise
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # New tab: Ctrl+T
        new_tab_action = QAction(self)
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(self.add_new_tab)
        self.addAction(new_tab_action)
        
        # Close tab: Ctrl+W
        close_tab_action = QAction(self)
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))
        self.addAction(close_tab_action)
        
        # Focus URL bar: Ctrl+L
        focus_url_action = QAction(self)
        focus_url_action.setShortcut("Ctrl+L")
        focus_url_action.triggered.connect(self.focus_url_bar)
        self.addAction(focus_url_action)
        
        # Refresh: F5
        refresh_action = QAction(self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_page)
        self.addAction(refresh_action)
        
        # Fullscreen: F11
        fullscreen_action = QAction(self)
        fullscreen_action.setShortcut("F11")
        fullscreen_action.triggered.connect(self.toggle_browser_fullscreen)
        self.addAction(fullscreen_action)
        
        # Downloads: Ctrl+J
        downloads_action = QAction(self)
        downloads_action.setShortcut("Ctrl+J")
        downloads_action.triggered.connect(self.show_downloads)
        self.addAction(downloads_action)
    
    def focus_url_bar(self):
        """Focus and select all text in URL bar"""
        self.url_bar.setFocus()
        self.url_bar.selectAll()
    
    def add_new_tab(self, url=None, *args, **kwargs):
        """Add a new browser tab"""
        # Handle both direct calls and signal calls
        if isinstance(url, bool) or url is None:
            url = self.home_page
        
        # Create tab with persistent profile if available
        profile_to_use = self.web_profile if hasattr(self, 'web_profile') and self.web_profile else None
        tab = BrowserTab(url, profile=profile_to_use, parent=self)
        
        # Add tab with page title first
        index = self.tab_widget.addTab(tab, "New Tab")
        self.tab_widget.setCurrentIndex(index)
        
        # Connect signals after tab is added
        tab.browser.urlChanged.connect(self.update_url_bar)
        tab.browser.loadFinished.connect(lambda checked, t=tab: self.on_page_loaded(t))
        tab.browser.titleChanged.connect(lambda title, t=tab: self.update_tab_title(t, title))
        
        return tab
    
    def on_page_loaded(self, tab):
        """Called when a page finishes loading"""
        title = tab.browser.page().title()
        self.update_tab_title(tab, title)
    
    def update_tab_title(self, tab, title):
        """Update tab title"""
        index = self.tab_widget.indexOf(tab)
        if index != -1:
            # Truncate long titles
            max_length = 20
            if len(title) > max_length:
                title = title[:max_length] + "..."
            self.tab_widget.setTabText(index, title if title else "New Tab")
    
    def close_tab(self, index):
        """Close a tab"""
        if self.tab_widget.count() > 1:
            self.tab_widget.removeTab(index)
        else:
            # Don't close last tab, just navigate to home
            self.go_home()
    
    def on_tab_changed(self, index):
        """Called when active tab changes"""
        if index >= 0:
            current_tab = self.tab_widget.widget(index)
            if current_tab:
                url = current_tab.browser.url().toString()
                self.url_bar.setText(url)
    
    def get_current_browser(self):
        """Get the browser widget from the current tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            return current_tab.browser
        return None
    
    def go_home(self):
        """Navigate to home page"""
        browser = self.get_current_browser()
        if browser:
            browser.setUrl(QUrl(self.home_page))
    
    def navigate_back(self):
        browser = self.get_current_browser()
        if browser:
            browser.back()
    
    def navigate_forward(self):
        browser = self.get_current_browser()
        if browser:
            browser.forward()
    
    def refresh_page(self):
        browser = self.get_current_browser()
        if browser:
            browser.reload()
    
    def navigate_to_url(self):
        url = self.url_bar.text().strip()
        if not url:
            return
        
        # Check if it's a search query or URL
        if not url.startswith("http") and "." not in url.split()[0]:
            # Treat as search query
            url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
        elif not url.startswith("http"):
            url = "https://" + url
        
        browser = self.get_current_browser()
        if browser:
            browser.setUrl(QUrl(url))
    
    def update_url_bar(self, url):
        """Update URL bar when current tab's URL changes"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_browser = current_tab.browser
            sender = self.sender()
            if sender == current_browser:
                self.url_bar.setText(url.toString())
    
    def clear_chat(self):
        """Clear the chat history"""
        reply = QMessageBox.question(
            self,
            "Clear Chat",
            "Are you sure you want to clear the conversation history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.conversation_history = []
            self.chat_display.clear()
            self.add_to_chat("System", "Chat history cleared!")
    
    def clear_saved_logins(self):
        """Clear all saved cookies and login sessions"""
        if not hasattr(self, 'web_profile') or not self.web_profile:
            QMessageBox.information(self, "Info", "Login persistence is not enabled.")
            return
        
        reply = QMessageBox.question(
            self,
            "Clear Saved Logins",
            "This will clear all saved login sessions and cookies.\n"
            "You will need to log in again to all websites.\n\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Clear cookies from the profile
                self.web_profile.cookieStore().deleteAllCookies()
                
                # Clear HTTP cache
                self.web_profile.clearHttpCache()
                
                # Also delete the persistent storage directory
                if hasattr(self, 'profile_path') and os.path.exists(self.profile_path):
                    try:
                        shutil.rmtree(self.profile_path)
                        os.makedirs(self.profile_path, exist_ok=True)
                    except Exception as e:
                        print(f"Could not delete profile directory: {e}")
                
                self.add_to_chat("System", "✓ All saved logins and cookies cleared!")
                QMessageBox.information(
                    self,
                    "Success",
                    "All saved login sessions and cookies have been cleared.\n"
                    "Please restart the browser to apply changes."
                )
                
            except Exception as e:
                self.add_to_chat("System", f"Error clearing logins: {str(e)}")
                QMessageBox.warning(self, "Error", f"Failed to clear logins: {str(e)}")
    
    def toggle_chat_panel(self):
        """Toggle chat panel visibility with animation"""
        if self.chat_visible:
            self.chat_visible = False
            self.toggle_chat_btn.setText("▶ Show Chat")
            
            self.chat_width = self.chat_container.width()
            
            self.animation = QPropertyAnimation(self.chat_container, b"maximumWidth")
            self.animation.setDuration(300)
            self.animation.setStartValue(self.chat_width)
            self.animation.setEndValue(0)
            self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.animation.finished.connect(lambda: self.chat_container.setMaximumWidth(0))
            self.animation.start()
            
            self.animation2 = QPropertyAnimation(self.chat_container, b"minimumWidth")
            self.animation2.setDuration(300)
            self.animation2.setStartValue(self.chat_width)
            self.animation2.setEndValue(0)
            self.animation2.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.animation2.start()
        else:
            self.chat_visible = True
            self.toggle_chat_btn.setText("◀ Hide Chat")
            
            self.chat_container.setMaximumWidth(16777215)
            
            self.animation = QPropertyAnimation(self.chat_container, b"minimumWidth")
            self.animation.setDuration(300)
            self.animation.setStartValue(0)
            self.animation.setEndValue(self.chat_width)
            self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.animation.finished.connect(lambda: self.chat_container.setMinimumWidth(self.chat_width))
            self.animation.start()
    
    def auto_start_ollama(self):
        """Automatically start Ollama if not running"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                self.add_to_chat("System", "✓ Connected to Ollama successfully!")
                self.check_and_download_model()
                return
        except:
            pass
        
        # Try to start Ollama automatically
        self.add_to_chat("System", "🔄 Ollama not detected. Attempting to start...")
        
        try:
            system = platform.system()
            if system == "Windows":
                # Try to start Ollama service on Windows
                subprocess.Popen(["ollama", "serve"], 
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            elif system == "Darwin":  # macOS
                subprocess.Popen(["/Applications/Ollama.app/Contents/MacOS/ollama", "serve"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:  # Linux
                subprocess.Popen(["ollama", "serve"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            
            # Wait a bit and check again
            QTimer.singleShot(3000, self.check_ollama_after_start)
            
        except FileNotFoundError:
            # Ollama not installed
            self.add_to_chat("System", "⚠ Ollama is not installed.")
            self.offer_ollama_installation()
        except Exception as e:
            self.add_to_chat("System", f"⚠ Could not start Ollama: {str(e)}")
            self.offer_ollama_installation()
    
    def check_ollama_after_start(self):
        """Check if Ollama started successfully"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                self.add_to_chat("System", "✓ Ollama started successfully!")
                self.check_and_download_model()
                return
        except:
            pass
        
        self.add_to_chat("System", "⚠ Could not start Ollama automatically.")
        self.offer_ollama_installation()
    
    def offer_ollama_installation(self):
        """Offer to install Ollama"""
        reply = QMessageBox.question(
            self,
            "Ollama Not Found",
            "Ollama is not installed or not running.\n\n"
            "Would you like to automatically install Ollama now?\n"
            "(This is free and runs AI models locally on your computer)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.install_ollama()
        else:
            self.add_to_chat("System", "⚠ You can manually install Ollama from https://ollama.ai")
    
    def install_ollama(self):
        """Install Ollama automatically"""
        self.progress_dialog = QProgressDialog("Installing Ollama...", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Installing Ollama")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.show()
        
        self.installer = OllamaInstaller()
        self.installer.progress.connect(self.on_install_progress)
        self.installer.finished.connect(self.on_install_finished)
        self.installer.start()
    
    def on_install_progress(self, message):
        """Update installation progress"""
        self.progress_dialog.setLabelText(message)
        self.add_to_chat("System", message)
    
    def on_install_finished(self, success, message):
        """Handle installation completion"""
        self.progress_dialog.close()
        
        if success:
            self.add_to_chat("System", "✓ " + message)
            QMessageBox.information(self, "Success", message + "\n\nOllama is now running!")
            
            import time
            time.sleep(3)
            self.check_and_download_model()
        else:
            self.add_to_chat("System", "✗ " + message)
            QMessageBox.warning(self, "Installation Failed", message)
    
    def check_and_download_model(self):
        """Check if any models are installed, if not download one"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                self.installed_models = [model["name"] for model in models]
                
                if not models:
                    reply = QMessageBox.question(
                        self,
                        "No Models Found",
                        "No AI models are installed yet.\n\n"
                        "Would you like to download llama3.2:1b? (Small, fast model ~1.3GB)\n\n"
                        "This will take a few minutes depending on your internet speed.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        self.download_model("llama3.2:1b")
                else:
                    self.add_to_chat("System", f"Found {len(models)} installed model(s): {', '.join(self.installed_models)}")
        except:
            pass
    
    def on_model_changed(self, model_name):
        """Handle model selection change"""
        if not model_name:
            return
        
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code != 200:
                self.add_to_chat("System", "⚠ Cannot connect to Ollama. Make sure it's running.")
                self.model_selector.setCurrentText(self.current_model)
                return
            
            data = response.json()
            installed = [model["name"] for model in data.get("models", [])]
            self.installed_models = installed
            
            model_installed = any(model_name in model or model in model_name for model in installed)
            
            if model_installed:
                self.current_model = model_name
                self.add_to_chat("System", f"✓ Switched to model: {model_name}")
                
                if self.pending_screenshot:
                    self.pending_screenshot = False
                    self.take_and_analyze_screenshot()
            else:
                reply = QMessageBox.question(
                    self,
                    "Model Not Installed",
                    f"The model '{model_name}' is not installed.\n\n"
                    f"Would you like to download it now?\n\n"
                    f"Note: This may take several minutes depending on the model size and your internet speed.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.download_model(model_name)
                    self.current_model = model_name
                else:
                    self.add_to_chat("System", f"Keeping current model: {self.current_model}")
                    self.model_selector.setCurrentText(self.current_model)
        
        except Exception as e:
            self.add_to_chat("System", f"Error checking model: {str(e)}")
            self.model_selector.setCurrentText(self.current_model)
    
    def download_model(self, model_name):
        """Download an Ollama model"""
        self.add_to_chat("System", f"📥 Downloading model '{model_name}'... This may take a few minutes.")
        
        self.download_progress = QProgressDialog(
            f"Downloading {model_name}...\n\nThis may take several minutes.", 
            None, 0, 0, self
        )
        self.download_progress.setWindowTitle("Downloading Model")
        self.download_progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.download_progress.setCancelButton(None)
        self.download_progress.show()
        
        try:
            if platform.system() == "Windows":
                process = subprocess.Popen(
                    ["ollama", "pull", model_name],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            else:
                process = subprocess.Popen(
                    ["ollama", "pull", model_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            stdout, stderr = process.communicate()
            
            self.download_progress.close()
            
            if process.returncode == 0:
                self.add_to_chat("System", f"✓ Model '{model_name}' downloaded successfully! You can start chatting now.")
                self.check_available_models()
                
                if self.pending_screenshot:
                    self.pending_screenshot = False
                    self.add_to_chat("System", "Now taking screenshot with the new vision model...")
                    self.take_and_analyze_screenshot()
            else:
                self.add_to_chat("System", f"✗ Failed to download model: {stderr}")
                
        except Exception as e:
            self.download_progress.close()
            self.add_to_chat("System", f"✗ Failed to download model: {str(e)}")
    
    def check_available_models(self):
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [model["name"] for model in data.get("models", [])]
                if models:
                    self.add_to_chat("System", f"Available models: {', '.join(models)}")
                    self.model_selector.clear()
                    self.model_selector.addItems(models)
                else:
                    self.add_to_chat("System", "No models installed. Install one with: ollama pull llama3.2")
            else:
                self.add_to_chat("System", "Failed to fetch models from Ollama")
        except Exception as e:
            self.add_to_chat("System", f"Error checking models: {str(e)}")
    
    def add_to_chat(self, sender, message):
        if sender == "You":
            color = "#0066cc"
        elif sender == "AI":
            color = "#2d5016"
        else:
            color = "#cc0000"
        
        formatted_message = message.replace("\n", "<br>")
        self.chat_display.append(f'<span style="color: {color}; font-weight: bold;">{sender}:</span> {formatted_message}<br>')
        
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def send_message(self):
        user_message = self.chat_input.text().strip()
        if not user_message:
            return
        
        self.chat_input.clear()
        self.add_to_chat("You", user_message)
        
        # Add system context about browser control capabilities
        enhanced_message = user_message
        
        # Only add the system prompt on the first message or if conversation is short
        if len(self.conversation_history) == 0:
            system_context = """[SYSTEM CAPABILITY: You can control the browser! When you want to open a website, use this format: [OPEN_URL: https://example.com]. 
You can also naturally suggest websites by saying things like "I'll open https://example.com for you" or "Let me navigate to https://wikipedia.org" and the browser will automatically open them.
Be helpful and proactively open relevant websites when users ask for them.]

"""
            enhanced_message = system_context + user_message
        
        self.conversation_history.append({
            "role": "user",
            "content": enhanced_message
        })
        
        self.get_ai_response()
    
    def analyze_page_with_vision(self):
        """Take a screenshot and have AI analyze the visual content"""
        vision_models = ["llava", "bakllava", "llava-phi3", "llama3.2-vision"]
        supports_vision = any(vm in self.current_model.lower() for vm in vision_models)
        
        if not supports_vision:
            reply = QMessageBox.question(
                self,
                "Vision Model Required",
                f"The current model '{self.current_model}' doesn't support vision.\n\n"
                "Would you like to switch to llama3.2-vision:11b?\n"
                "(This model can see and analyze screenshots)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.pending_screenshot = True
                self.model_selector.setCurrentText("llama3.2-vision:11b")
                return
            else:
                return
        
        self.take_and_analyze_screenshot()
    
    def take_and_analyze_screenshot(self):
        """Actually take the screenshot and send to AI"""
        browser = self.get_current_browser()
        if not browser:
            return
        
        self.add_to_chat("You", "📸 Taking screenshot of page...")
        
        size = browser.size()
        image = QImage(size, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        browser.render(painter)
        painter.end()
        
        buffer = QBuffer()
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        image_data = buffer.data()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        current_url = browser.url().toString()
        current_title = browser.page().title()
        
        message = f"I'm viewing this webpage:\n\nURL: {current_url}\nTitle: {current_title}\n\nPlease analyze what you see in this screenshot. Describe the page layout, content, images, and any important information visible."
        
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        self.get_ai_response(image_base64=image_base64)
    
    def analyze_page(self):
        browser = self.get_current_browser()
        if browser:
            browser.page().toPlainText(self.on_page_content_received)
    
    def on_page_content_received(self, content):
        browser = self.get_current_browser()
        if not browser:
            return
        
        current_url = browser.url().toString()
        current_title = browser.page().title()
        
        max_content_length = 6000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n...(content truncated for length)"
        
        message = f"I'm currently viewing this webpage:\n\nURL: {current_url}\nTitle: {current_title}\n\nPage content:\n{content}\n\nPlease analyze this page and tell me what it's about, including key information and main topics."
        
        self.add_to_chat("You", "📄 Analyzing current page...")
        
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        self.get_ai_response()
    
    def get_ai_response(self, image_base64=None):
        self.chat_input.setEnabled(False)
        self.send_btn.setEnabled(False)
        self.page_context_btn.setEnabled(False)
        self.screenshot_btn.setEnabled(False)
        
        if image_base64:
            self.add_to_chat("System", "AI is analyzing the screenshot...")
        else:
            self.add_to_chat("System", "AI is thinking...")
        
        selected_model = self.current_model
        
        self.worker = OllamaWorker(self.conversation_history, selected_model, image_base64)
        self.worker.finished.connect(self.on_ai_response)
        self.worker.error.connect(self.on_ai_error)
        self.worker.start()
    
    def on_ai_response(self, assistant_message):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.select(cursor.SelectionType.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()
        
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        # Check if AI wants to open a URL
        self.check_and_handle_url_commands(assistant_message)
        
        self.add_to_chat("AI", assistant_message)
        
        self.chat_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.page_context_btn.setEnabled(True)
        self.screenshot_btn.setEnabled(True)
        self.chat_input.setFocus()
    
    def on_ai_error(self, error_message):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.select(cursor.SelectionType.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()
        
        self.add_to_chat("System", error_message)
        
        self.chat_input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.page_context_btn.setEnabled(True)
        self.screenshot_btn.setEnabled(True)
    
    def check_and_handle_url_commands(self, message):
        """Check if AI message contains URL commands and handle them"""
        # Look for special command format: [OPEN_URL: url]
        url_pattern = r'\[OPEN_URL:\s*([^\]]+)\]'
        matches = re.findall(url_pattern, message)
        
        for url in matches:
            url = url.strip()
            self.add_to_chat("System", f"🌐 Opening: {url}")
            self.open_url_in_browser(url)
        
        # Also detect natural language URLs that AI might suggest
        # Look for common URL patterns in the text
        url_regex = r'https?://[^\s<>"{}|\\^`\[\]]+'
        natural_urls = re.findall(url_regex, message)
        
        # If AI mentions opening/visiting/navigating in the same sentence as a URL
        action_words = ['open', 'visit', 'navigate', 'go to', 'check out', 'opening', 'visiting']
        
        for url in natural_urls:
            # Check if the URL appears near action words
            message_lower = message.lower()
            url_index = message_lower.find(url.lower())
            
            # Look in a window around the URL
            start = max(0, url_index - 100)
            end = min(len(message_lower), url_index + len(url) + 50)
            context = message_lower[start:end]
            
            if any(word in context for word in action_words):
                self.add_to_chat("System", f"🌐 AI suggested opening: {url}")
                self.open_url_in_browser(url)
                break  # Only open the first suggested URL to avoid overwhelming the user
    
    def open_url_in_browser(self, url):
        """Open a URL in the current browser tab"""
        if not url.startswith("http"):
            url = "https://" + url
        
        browser = self.get_current_browser()
        if browser:
            browser.setUrl(QUrl(url))
            self.url_bar.setText(url)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application name
    app.setApplicationName("Glitch Create")
    app.setOrganizationName("Glitch")
    
    try:
        browser = GlitchBrowser()
        browser.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting browser: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)
import sys
import time
import psutil
import logging
import os
import platform
from PyQt5.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QAction, 
                            QWidget, QLabel, QVBoxLayout, QHBoxLayout, QDesktopWidget,
                            QCheckBox, QMessageBox)
from PyQt5.QtGui import QIcon, QFont, QColor
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, Qt


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutoStartManager:
    def __init__(self, app_name="InternetSpeedMonitor"):
        self.app_name = app_name
        self.app_path = os.path.abspath(sys.argv[0])
        self.system = platform.system()
        logger.info(f"Initializing AutoStartManager for {self.system} with app path: {self.app_path}")
        
    def is_enabled(self):
        """Check if auto start is enabled for the app."""
        try:
            if self.system == "Windows":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_READ
                )
                try:
                    value, _ = winreg.QueryValueEx(key, self.app_name)
                    winreg.CloseKey(key)
                    return value == self.app_path
                except WindowsError:
                    winreg.CloseKey(key)
                    return False
            
            elif self.system == "Linux":
                autostart_dir = os.path.expanduser("~/.config/autostart")
                desktop_file = os.path.join(autostart_dir, f"{self.app_name}.desktop")
                return os.path.exists(desktop_file)
                
            elif self.system == "Darwin":  # macOS
                plist_path = os.path.expanduser(f"~/Library/LaunchAgents/com.{self.app_name}.plist")
                return os.path.exists(plist_path)
                
            else:
                logger.warning(f"Unsupported platform: {self.system}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking auto start status: {e}")
            return False
            
    def enable(self):
        """Enable auto start for the app."""
        try:
            if self.system == "Windows":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_WRITE
                )
                winreg.SetValueEx(key, self.app_name, 0, winreg.REG_SZ, self.app_path)
                winreg.CloseKey(key)
                logger.info("Enabled auto start on Windows")
                return True
                
            elif self.system == "Linux":
                autostart_dir = os.path.expanduser("~/.config/autostart")
                if not os.path.exists(autostart_dir):
                    os.makedirs(autostart_dir)
                
                desktop_file = os.path.join(autostart_dir, f"{self.app_name}.desktop")
                with open(desktop_file, "w") as f:
                    f.write(f"""[Desktop Entry]
Type=Application
Name={self.app_name}
Exec={self.app_path}
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
""")
                os.chmod(desktop_file, 0o755)  # Make it executable
                logger.info("Enabled auto start on Linux")
                return True
                
            elif self.system == "Darwin":  # macOS
                plist_dir = os.path.expanduser("~/Library/LaunchAgents")
                if not os.path.exists(plist_dir):
                    os.makedirs(plist_dir)
                
                plist_path = os.path.join(plist_dir, f"com.{self.app_name}.plist")
                with open(plist_path, "w") as f:
                    f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.{self.app_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{self.app_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
""")
                os.system(f"launchctl load {plist_path}")
                logger.info("Enabled auto start on macOS")
                return True
                
            else:
                logger.warning(f"Unsupported platform for auto start: {self.system}")
                return False
                
        except Exception as e:
            logger.error(f"Error enabling auto start: {e}")
            return False
            
    def disable(self):
        """Disable auto start for the app."""
        try:
            if self.system == "Windows":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0, winreg.KEY_WRITE
                )
                try:
                    winreg.DeleteValue(key, self.app_name)
                except WindowsError:
                    pass  # Key doesn't exist
                winreg.CloseKey(key)
                logger.info("Disabled auto start on Windows")
                return True
                
            elif self.system == "Linux":
                desktop_file = os.path.expanduser(f"~/.config/autostart/{self.app_name}.desktop")
                if os.path.exists(desktop_file):
                    os.remove(desktop_file)
                logger.info("Disabled auto start on Linux")
                return True
                
            elif self.system == "Darwin":  # macOS
                plist_path = os.path.expanduser(f"~/Library/LaunchAgents/com.{self.app_name}.plist")
                if os.path.exists(plist_path):
                    os.system(f"launchctl unload {plist_path}")
                    os.remove(plist_path)
                logger.info("Disabled auto start on macOS")
                return True
                
            else:
                logger.warning(f"Unsupported platform for auto start: {self.system}")
                return False
                
        except Exception as e:
            logger.error(f"Error disabling auto start: {e}")
            return False

class SpeedMonitor(QObject):
    speed_updated = pyqtSignal(float, float)
    
    def __init__(self):
        super().__init__()
        self.upload_speed = 0
        self.download_speed = 0
        self.last_upload = 0
        self.last_download = 0
        self.last_time = time.time()
        
        try:
            # Get initial values
            net_io = psutil.net_io_counters()
            self.last_upload = net_io.bytes_sent
            self.last_download = net_io.bytes_recv
            logger.info(f"Initial network stats - Upload: {self.last_upload}, Download: {self.last_download}")
        except Exception as e:
            logger.error(f"Error initializing network monitor: {e}")
            raise
        
    def update_speed(self):
        try:
            # Get current network stats
            net_io = psutil.net_io_counters()
            current_time = time.time()
            
            # Calculate time difference
            time_diff = current_time - self.last_time
            if time_diff < 0.1:  # Avoid division by very small numbers
                return
            
            # Calculate upload and download speeds in KB/s
            upload_diff = net_io.bytes_sent - self.last_upload
            download_diff = net_io.bytes_recv - self.last_download
            
            self.upload_speed = upload_diff / time_diff / 1024
            self.download_speed = download_diff / time_diff / 1024
            
            # Update last values
            self.last_upload = net_io.bytes_sent
            self.last_download = net_io.bytes_recv
            self.last_time = current_time
            
            # Emit signal with new speeds
            self.speed_updated.emit(self.upload_speed, self.download_speed)
        except Exception as e:
            logger.error(f"Error updating speed: {e}")

class SpeedDisplayWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Set window flags
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Create layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create download speed label
        self.download_label = QLabel("↓ 0.0 KB/s")
        self.download_label.setFont(QFont("Arial", 10))
        self.download_label.setStyleSheet("color: white;")
        
        # Create upload speed label
        self.upload_label = QLabel("↑ 0.0 KB/s")
        self.upload_label.setFont(QFont("Arial", 10))
        self.upload_label.setStyleSheet("color: white;")
        
        # Add labels to layout
        main_layout.addWidget(self.download_label)
        main_layout.addWidget(self.upload_label)
        
        # Set layout
        self.setLayout(main_layout)
        
        # Set background color
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 5px;")
        
        # Set initial position (bottom right)
        self.position_window()
        
        # For dragging the window
        self.dragging = False
        self.offset = None
    
    def position_window(self):
        # Position in bottom right corner
        desktop = QDesktopWidget().availableGeometry()
        self.resize(120, 70)
        self.move(desktop.width() - 130, desktop.height() - 80)
        
    def update_speeds(self, download, upload):
        # Update labels
        self.download_label.setText(f"↓ {self.format_speed(download)}")
        self.upload_label.setText(f"↑ {self.format_speed(upload)}")
    
    def format_speed(self, speed):
        # Format speed value to appropriate units
        if speed >= 1024:
            return f"{speed/1024:.1f} MB/s"
        else:
            return f"{speed:.1f} KB/s"
    
    # Events for dragging the window
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.pos()
    
    def mouseMoveEvent(self, event):
        if self.dragging and self.offset:
            self.move(self.pos() + event.pos() - self.offset)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False

class InternetSpeedApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # Initialize auto start manager
        self.auto_start_manager = AutoStartManager()
        
        # Create the tray icon
        self.tray_icon = QSystemTrayIcon()
        
        # Try to load the icon, or use a fallback
        try:
            self.tray_icon.setIcon(QIcon("network.ico"))
        except:
            # If the icon file is missing, try system icon or create a default
            logger.warning("Network icon not found, using system icon")
            self.tray_icon.setIcon(QIcon.fromTheme("network-wired"))
        
        self.tray_icon.setVisible(True)
        self.tray_icon.setToolTip('Internet Speed Monitor')
        
        # Create the menu
        self.menu = QMenu()
        
        # Add toggle display action
        self.display_visible = True
        self.toggle_display_action = QAction("Hide Speed Display", self.app)
        self.toggle_display_action.triggered.connect(self.toggle_display)
        self.menu.addAction(self.toggle_display_action)
        
        # Add reset position action
        reset_position_action = QAction("Reset Window Position", self.app)
        reset_position_action.triggered.connect(self.reset_position)
        self.menu.addAction(reset_position_action)
        
        # Add auto start option
        self.autostart_action = QAction("Start with System", self.app)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(self.auto_start_manager.is_enabled())
        self.autostart_action.triggered.connect(self.toggle_autostart)
        self.menu.addAction(self.autostart_action)
        
        # Add separator
        self.menu.addSeparator()
        
        # Add quit action
        quit_action = QAction("Exit", self.app)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)
        
        # Set the menu
        self.tray_icon.setContextMenu(self.menu)
        
        # Create speed display window
        self.display_window = SpeedDisplayWindow()
        self.display_window.show()
        
        # Create speed monitor
        try:
            self.speed_monitor = SpeedMonitor()
            self.speed_monitor.speed_updated.connect(self.update_speeds)
            
            # Create timer to update speeds
            self.timer = QTimer()
            self.timer.timeout.connect(self.speed_monitor.update_speed)
            self.timer.start(1000)  # Update every second
            
            logger.info("Application initialized successfully")
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            sys.exit(1)
    
    def toggle_display(self):
        self.display_visible = not self.display_visible
        if self.display_visible:
            self.display_window.show()
            self.toggle_display_action.setText("Hide Speed Display")
        else:
            self.display_window.hide()
            self.toggle_display_action.setText("Show Speed Display")
    
    def reset_position(self):
        self.display_window.position_window()
    
    def toggle_autostart(self):
        is_checked = self.autostart_action.isChecked()
        success = False
        
        if is_checked:
            success = self.auto_start_manager.enable()
            message = "Auto start enabled successfully."
        else:
            success = self.auto_start_manager.disable()
            message = "Auto start disabled successfully."
        
        # If operation failed, show error and revert checkbox
        if not success:
            QMessageBox.warning(None, "Auto Start", 
                               "Failed to change auto start settings. This might require administrative privileges.")
            self.autostart_action.setChecked(not is_checked)
        else:
            logger.info(message)
    
    def update_speeds(self, upload, download):
        try:
            # Update display window
            self.display_window.update_speeds(download, upload)
            
            # Update tooltip
            download_text = self.display_window.format_speed(download)
            upload_text = self.display_window.format_speed(upload)
            tooltip_text = f"Internet Speed\n↓ {download_text}\n↑ {upload_text}"
            self.tray_icon.setToolTip(tooltip_text)
        except Exception as e:
            logger.error(f"Error updating speeds: {e}")
    
    def run(self):
        self.tray_icon.show()
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    try:
        app = InternetSpeedApp()
        app.run()
    except Exception as e:
        logger.critical(f"Critical error: {e}")
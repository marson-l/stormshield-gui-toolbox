#!/usr/bin/env python3
"""
Stormshield SNS CLI GUI Application
A modern PyQt-based interface for executing commands on Stormshield appliances
"""

import re
import sys
import os
import getpass
import ssl
import certifi
from pathlib import Path
from typing import List, Optional
import time
import subprocess
import gzip
import shutil

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox,
    QFileDialog, QMessageBox, QProgressBar, QTabWidget, QGroupBox, QStatusBar, QComboBox,
    QListWidget, QListWidgetItem, QDialog, QInputDialog
)
from PyQt6.QtCore import (
    QThread, pyqtSignal,Qt, QSettings, QUrl
)
from PyQt6.QtGui import (
    QFont, QIcon, QColor, QTextCharFormat, QSyntaxHighlighter
)

from stormshield.sns.sslclient import SSLClient


class CommandHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Stormshield commands"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # Command keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#0078d4"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        
        keywords = ["config", "system", "network", "interface", "create", "modify", "delete"]
        for keyword in keywords:
            self.highlighting_rules.append((f"\\b{keyword}\\b", keyword_format))
        
        # Parameters
        param_format = QTextCharFormat()
        param_format.setForeground(QColor("#795548"))
        self.highlighting_rules.append((r"\b\w+=[^\s]+", param_format))
        
        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((r"#[^\n]*", comment_format))
    
    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            import re
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), format)


class ConnectionThread(QThread):
    """Thread for handling SSL connection to avoid blocking UI"""
    
    connected = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(int)
    
    def __init__(self, host, port, user, password):
        super().__init__()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.client = None
    
    def run(self):
        try:
            self.progress.emit(25)
            
            # Handle SSL certificate verification for compiled executables
            ssl_context = None
            try:
                # Try to create a proper SSL context
                ssl_context = ssl.create_default_context()
                # For Stormshield appliances, we typically need to disable verification
                # since they often use self-signed certificates
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            except Exception:
                # Fallback if SSL context creation fails
                ssl_context = None
            
            # Create SSL client with proper certificate handling
            try:
                self.client = SSLClient(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    sslverifyhost=False,
                    sslverifypeer=False  # Disable peer verification for self-signed certs
                )
            except TypeError:
                # Fallback for older versions of the SSL client
                self.client = SSLClient(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    sslverifyhost=False
                )
            
            self.progress.emit(100)
            self.connected.emit(True, f"Successfully connected to {self.host}")
        except Exception as e:
            self.progress.emit(100)
            error_msg = str(e)
            
            # Provide more helpful error messages for common SSL issues
            if "certificate" in error_msg.lower() or "ssl" in error_msg.lower():
                error_msg = f"SSL/Certificate Error: {error_msg}\n" + \
                           "This is often caused by self-signed certificates. " + \
                           "Connection security is disabled for Stormshield appliances."
            elif "connection" in error_msg.lower():
                error_msg = f"Connection Error: {error_msg}\n" + \
                           "Please check the host/IP address and port number."
            elif "authentication" in error_msg.lower() or "login" in error_msg.lower():
                error_msg = f"Authentication Error: {error_msg}\n" + \
                           "Please check your username and password."
            
            self.connected.emit(False, f"Connection failed: {error_msg}")


class CommandExecutorThread(QThread):
    """Thread for executing commands without blocking UI"""
    
    command_executed = pyqtSignal(str, str, bool)  # command, output, success
    progress = pyqtSignal(int)
    
    def __init__(self, client, commands):
        super().__init__()
        self.client = client
        self.commands = commands
    
    def run(self):
        total_commands = len(self.commands)
        for i, command in enumerate(self.commands):
            if command.strip():
                try:
                    result = self.client.send_command(command)
                    output = "\n".join(result.output.split("\n")[1:-1]) if result.output else "No output"
                    result = str(result)  # Convert to string for display
                    if "100 code=" in result:
                        result = f"{result} | Command executed successfully."
                    else:
                        result = f"{result} | Command execution failed."
                    self.command_executed.emit(command, result, True)
                except Exception as e:
                    self.command_executed.emit(command, f"Error: {str(e)}", False)
                
                progress = int(((i + 1) / total_commands) * 100)
                self.progress.emit(progress)
                
                # Small delay to show progress
                self.msleep(100)


class MonitoringThread(QThread):
    """Thread for monitoring system status without blocking UI"""
    
    monitoring_data = pyqtSignal(str)  # monitoring output
    monitoring_started = pyqtSignal(str)  # monitoring type
    
    def __init__(self, client, monitor_type="system"):
        super().__init__()
        self.client = client
        self.monitor_type = monitor_type
        self.is_running = False
    
    def run(self):
        self.is_running = True
        self.monitoring_started.emit(f"Monitoring {self.monitor_type.upper()}...")
        
        while self.is_running:
            if self.client:
                try:
                    if self.monitor_type == "system":
                        result = self.client.send_command("monitor system")
                    elif self.monitor_type == "ipsec":
                        result = str(self.client.send_command("monitor getikesa"))
                        result += "\n" + str(self.client.send_command("monitor getsa"))
                    elif self.monitor_type == "interface":
                        result = self.client.send_command("monitor interface")
                    else:
                        result = self.client.send_command(f"monitor {self.monitor_type}")
                    
                    self.monitoring_data.emit(str(result))
                except Exception as e:
                    self.monitoring_data.emit(f"Error: {str(e)}")
            
            # Sleep for 2 seconds between monitoring updates
            self.msleep(2000)
    
    def stop_monitoring(self):
        self.is_running = False
        self.quit()
        self.wait()


class ModernButton(QPushButton):
    """Custom styled button with hover effects"""
    
    def __init__(self, text, primary=False):
        super().__init__(text)
        self.primary = primary
        self.setFixedHeight(40)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style()
    
    def update_style(self):
        if self.primary:
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #0078d4, stop: 1 #106ebe);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #106ebe, stop: 1 #005a9e);
                }
                QPushButton:pressed {
                    background: #005a9e;
                }
                QPushButton:disabled {
                    background: #cccccc;
                    color: #666666;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: #f3f2f1;
                    color: #323130;
                    border: 1px solid #d2d0ce;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #edebe9;
                    border-color: #c7c6c4;
                }
                QPushButton:pressed {
                    background: #e1dfdd;
                }
                QPushButton:disabled {
                    background: #f3f2f1;
                    color: #a19f9d;
                    border-color: #e1dfdd;
                }
            """)


class ModernLineEdit(QLineEdit):
    """Custom styled line edit with modern appearance"""
    
    def __init__(self, placeholder=""):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(36)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                padding: 8px 12px;
                background: white;
                color: #323130;
                selection-background-color: #0078d4;
            }
            QLineEdit:focus {
                border-color: #0078d4;
                outline: none;
            }
            QLineEdit:disabled {
                background: #f3f2f1;
                color: #a19f9d;
                border-color: #e1dfdd;
            }
        """)


class StormshieldGUI(QMainWindow):
    """Main GUI application for Stormshield SNS CLI"""
    
    def __init__(self):
        super().__init__()
        self.client = None
        self.connection_thread = None
        self.executor_thread = None
        self.monitoring_thread = None
        self.terminal_executor = None
        self.is_connected = False
        self.cmd_history_list = []
        
        self.setWindowTitle("Stormshield SNS CLI GUI")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 600)
        
        # Set application icon (you can add an icon file)
        self.setWindowIcon(QIcon())
        
        self.setup_ui()
        self.setup_styling()
        self.setup_status_bar()
        
        # Load previous settings if available (only window geometry, not connection data)
        self.load_window_settings()
    
    def setup_ui(self):
        """Setup the main user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("🛡️ Stormshield SNS CLI Manager")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #323130; margin-bottom: 10px;")
        main_layout.addWidget(title_label)
        
        # Main content in tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d2d0ce;
                border-radius: 6px;
                background: white;
            }
            QTabBar::tab {
                background: #f3f2f1;
                color: #323130;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: white;
                border: 1px solid #d2d0ce;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background: #edebe9;
            }
        """)
        
        # Connection tab
        self.connection_tab = self.create_connection_tab()
        self.tab_widget.addTab(self.connection_tab, "🔗 Connection")
        
        # Commands tab
        self.commands_tab = self.create_commands_tab()
        self.tab_widget.addTab(self.commands_tab, "⚡ Commands")
        
        # Results tab
        self.results_tab = self.create_results_tab()
        self.tab_widget.addTab(self.results_tab, "📊 Results")
        
        # Terminal tab
        self.terminal_tab = self.create_terminal_tab()
        self.tab_widget.addTab(self.terminal_tab, "💻 Terminal")

        # Monitor tab
        self.monitor_tab = self.create_monitor_tab()
        self.tab_widget.addTab(self.monitor_tab, "🚦 Monitor")

        # Backup Extractor tab
        self.backup_extractor_tab = self.create_backup_extractor_tab()
        self.tab_widget.addTab(self.backup_extractor_tab, "💾 Backup Extractor")

        main_layout.addWidget(self.tab_widget)
    
    def create_connection_tab(self):
        """Create the connection configuration tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Connection group
        conn_group = QGroupBox("🔐 Appliance Connection")
        conn_group.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        conn_layout = QGridLayout(conn_group)
        conn_layout.setSpacing(15)
        
        # Host
        conn_layout.addWidget(QLabel("Host/IP Address:"), 0, 0)
        self.host_edit = ModernLineEdit("Enter host/IP address")
        self.host_edit.clear()  # Ensure field starts empty
        conn_layout.addWidget(self.host_edit, 0, 1)
        
        # Port
        conn_layout.addWidget(QLabel("SSL Port:"), 0, 2)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(443)  # Keep 443 as default since it's the standard SSL port
        self.port_spin.setFixedHeight(36)
        self.port_spin.setStyleSheet("""
            QSpinBox {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                padding: 8px;
                background: white;
                color: #323130;
            }
            QSpinBox:focus {
                border-color: #0078d4;
            }
        """)
        conn_layout.addWidget(self.port_spin, 0, 3)
        
        # Username
        conn_layout.addWidget(QLabel("Username:"), 1, 0)
        self.user_edit = ModernLineEdit("Enter username")
        self.user_edit.clear()  # Ensure field starts empty
        conn_layout.addWidget(self.user_edit, 1, 1)
        
        # Password
        conn_layout.addWidget(QLabel("Password:"), 1, 2)
        self.password_edit = ModernLineEdit("Enter password")
        self.password_edit.clear()  # Ensure field starts empty
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        conn_layout.addWidget(self.password_edit, 1, 3)
        
        # Buttons layout - Create a horizontal layout for buttons
        buttons_layout = QHBoxLayout()
        
        # Connection button
        self.connect_btn = ModernButton("🔗 Connect to Appliance", primary=True)
        self.connect_btn.clicked.connect(self.connect_to_appliance)
        buttons_layout.addWidget(self.connect_btn)

        # Backup button
        self.backup_btn = ModernButton("💾 Backup")
        self.backup_btn.clicked.connect(self.backup_appliance)
        self.backup_btn.setEnabled(False)
        buttons_layout.addWidget(self.backup_btn)

        # System info button
        self.system_info_btn = ModernButton("ℹ️ System Info")
        self.system_info_btn.clicked.connect(self.show_system_info)
        self.system_info_btn.setEnabled(False)
        buttons_layout.addWidget(self.system_info_btn)

        # Disconnect button
        self.disconnect_btn = ModernButton("🔌 Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_from_appliance)
        self.disconnect_btn.setEnabled(False)
        buttons_layout.addWidget(self.disconnect_btn)
        
        # Add buttons layout to grid
        conn_layout.addLayout(buttons_layout, 2, 0, 1, 4)
        
        # Progress bar
        self.connection_progress = QProgressBar()
        self.connection_progress.setVisible(False)
        self.connection_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                text-align: center;
                background: #f3f2f1;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0078d4, stop: 1 #40e0d0);
                border-radius: 4px;
            }
        """)
        conn_layout.addWidget(self.connection_progress, 3, 0, 1, 4)
        
        # Profile management buttons
        profile_layout = QHBoxLayout()
        
        self.save_profile_btn = ModernButton("💾 Save Profile")
        self.save_profile_btn.clicked.connect(self.save_connection_profile)
        profile_layout.addWidget(self.save_profile_btn)
        
        self.load_profile_btn = ModernButton("📂 Load Profile")
        self.load_profile_btn.clicked.connect(self.load_connection_profile_dialog)
        profile_layout.addWidget(self.load_profile_btn)
        
        self.manage_profiles_btn = ModernButton("⚙️ Manage Profiles")
        self.manage_profiles_btn.clicked.connect(self.manage_connection_profiles)
        profile_layout.addWidget(self.manage_profiles_btn)
        
        profile_layout.addStretch()
        conn_layout.addLayout(profile_layout, 4, 0, 1, 4)
        
        layout.addWidget(conn_group)
        
        # Status group
        status_group = QGroupBox("📊 Connection Status")
        status_group.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("❌ Not connected")
        self.status_label.setFont(QFont("Segoe UI", 10))
        self.status_label.setStyleSheet("color: #d13438; padding: 10px;")
        status_layout.addWidget(self.status_label)
        
        self.warning_label = QLabel(
            "⚠️ <b>Important:</b> Make sure you're not connected to the appliance "
            "with the same user session, as this will cause command execution failure."
        )
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("""
            QLabel {
                background: #fff4e6;
                color: #8a6d3b;
                padding: 12px;
                border-radius: 6px;
                border-left: 4px solid #f0ad4e;
            }
        """)
        status_layout.addWidget(self.warning_label)
        
        layout.addWidget(status_group)
        layout.addStretch()
        
        return tab
    
    def create_commands_tab(self):
        """Create the commands configuration tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Command source group
        source_group = QGroupBox("📝 Command Source")
        source_group.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        source_layout = QVBoxLayout(source_group)
        
        # File selection
        file_layout = QHBoxLayout()
        self.cmdfile_edit = ModernLineEdit("No file selected")
        self.cmdfile_edit.setReadOnly(True)
        file_layout.addWidget(QLabel("Command File:"))
        file_layout.addWidget(self.cmdfile_edit)
        
        self.browse_btn = ModernButton("📁 Browse")
        self.browse_btn.clicked.connect(self.browse_command_file)
        file_layout.addWidget(self.browse_btn)
        
        source_layout.addLayout(file_layout)
        
        # Manual command input
        source_layout.addWidget(QLabel("Or enter commands manually:"))
        self.command_text = QTextEdit()
        self.command_text.setMaximumHeight(200)
        self.command_text.setPlaceholderText(
            "Enter Stormshield commands, one per line...\n"
            "Example:\n"
            "config network interface show"
        )
        self.command_text.setFont(QFont("Consolas", 10))
        
        # Add syntax highlighting
        self.highlighter = CommandHighlighter(self.command_text.document())
        
        self.command_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                padding: 8px;
                background: white;
                color: #323130;
            }
            QTextEdit:focus {
                border-color: #0078d4;
            }
        """)
        source_layout.addWidget(self.command_text)
        
        layout.addWidget(source_group)
        
        # Execution group
        exec_group = QGroupBox("⚡ Command Execution")
        exec_group.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        exec_layout = QVBoxLayout(exec_group)
        
        # Execution controls
        controls_layout = QHBoxLayout()
        
        self.execute_btn = ModernButton("▶️ Execute Commands", primary=True)
        self.execute_btn.clicked.connect(self.execute_commands)
        self.execute_btn.setEnabled(False)
        controls_layout.addWidget(self.execute_btn)
        
        self.stop_btn = ModernButton("⏹️ Stop Execution")
        self.stop_btn.clicked.connect(self.stop_execution)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #d13438, stop: 1 #b71c1c);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #b71c1c, stop: 1 #8d1414);
            }
            QPushButton:pressed {
                background: #8d1414;
            }
            QPushButton:disabled {
                background: #cccccc;
                color: #666666;
            }
        """)
        controls_layout.addWidget(self.stop_btn)
        
        self.clear_results_btn = ModernButton("🗑️ Clear Results")
        self.clear_results_btn.clicked.connect(self.clear_results)
        controls_layout.addWidget(self.clear_results_btn)
        
        controls_layout.addStretch()
        exec_layout.addLayout(controls_layout)
        
        # Execution progress
        self.execution_progress = QProgressBar()
        self.execution_progress.setVisible(False)
        self.execution_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                text-align: center;
                background: #f3f2f1;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #107c10, stop: 1 #16c60c);
                border-radius: 4px;
            }
        """)
        exec_layout.addWidget(self.execution_progress)
        
        layout.addWidget(exec_group)
        layout.addStretch()
        
        return tab
    
    def create_results_tab(self):
        """Create the results display tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Results header
        header_layout = QHBoxLayout()
        results_label = QLabel("📊 Command Execution Results")
        results_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_layout.addWidget(results_label)
        
        header_layout.addStretch()
        
        self.export_btn = ModernButton("💾 Export Results")
        self.export_btn.clicked.connect(self.export_results)
        header_layout.addWidget(self.export_btn)
        
        layout.addLayout(header_layout)
        
        # Results display
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setFont(QFont("Consolas", 10))
        self.results_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.results_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                padding: 12px;
                background: #fafafa;
                color: #323130;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.results_text)
        
        return tab
    
    def create_terminal_tab(self):
        """Create the interactive terminal tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Terminal header
        header_layout = QHBoxLayout()
        terminal_label = QLabel("💻 Interactive Terminal")
        terminal_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_layout.addWidget(terminal_label)
        
        header_layout.addStretch()
        
        self.clear_terminal_btn = ModernButton("🗑️ Clear Terminal")
        self.clear_terminal_btn.clicked.connect(self.clear_terminal)
        header_layout.addWidget(self.clear_terminal_btn)

        self.get_full_rights_btn = ModernButton("✅ Get Private data access right")
        self.get_full_rights_btn.clicked.connect(self.get_full_rights)
        header_layout.addWidget(self.get_full_rights_btn)

        self.release_rights_btn = ModernButton("⛔ Release Private data access right")
        self.release_rights_btn.clicked.connect(self.release_rights)
        header_layout.addWidget(self.release_rights_btn)

        layout.addLayout(header_layout)
        
        # Terminal output display
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("Consolas", 10))
        self.terminal_output.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                padding: 12px;
                background: #1e1e1e;
                color: #ffffff;
                line-height: 1.4;
            }
        """)
        # Set initial welcome message
        welcome_message = """🛡️ Stormshield SNS Interactive Terminal
═══════════════════════════════════════════════════════════════
Welcome! Enter commands below to interact directly with the appliance.
Connection status will be shown here.

"""
        self.terminal_output.setPlainText(welcome_message)
        layout.addWidget(self.terminal_output)
        
        # Command input section
        input_group = QGroupBox("📝 Command Input")
        input_group.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        input_layout = QVBoxLayout(input_group)
        
        # Command input with history
        cmd_input_layout = QHBoxLayout()
        cmd_input_layout.addWidget(QLabel("Command:"))
        
        self.terminal_input = ModernLineEdit("Enter command...")
        self.terminal_input.setFont(QFont("Consolas", 10))
        self.terminal_input.returnPressed.connect(self.execute_terminal_command)
        cmd_input_layout.addWidget(self.terminal_input)
        
        self.send_cmd_btn = ModernButton("📤 Send", primary=True)
        self.send_cmd_btn.clicked.connect(self.execute_terminal_command)
        self.send_cmd_btn.setEnabled(False)
        cmd_input_layout.addWidget(self.send_cmd_btn)
        
        input_layout.addLayout(cmd_input_layout)
        
        # Command history dropdown
        history_layout = QHBoxLayout()
        history_layout.addWidget(QLabel("History:"))
        
        self.command_history = QComboBox()
        self.command_history.setEditable(False)
        self.command_history.addItem("No command history")
        self.command_history.currentTextChanged.connect(self.load_command_from_history)
        self.command_history.setStyleSheet("""
            QComboBox {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                padding: 8px 12px;
                background: white;
                color: #323130;
                min-height: 20px;
            }
            QComboBox:focus {
                border-color: #0078d4;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """)
        history_layout.addWidget(self.command_history)
        
        clear_history_btn = ModernButton("🗑️ Clear History")
        clear_history_btn.clicked.connect(self.clear_command_history)
        history_layout.addWidget(clear_history_btn)
        
        history_layout.addStretch()
        input_layout.addLayout(history_layout)
        
        # Terminal progress indicator
        self.terminal_progress = QProgressBar()
        self.terminal_progress.setVisible(False)
        self.terminal_progress.setRange(0, 0)  # Indeterminate progress
        self.terminal_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                text-align: center;
                background: #f3f2f1;
                height: 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0078d4, stop: 1 #40e0d0);
                border-radius: 4px;
            }
        """)
        input_layout.addWidget(self.terminal_progress)
        
        layout.addWidget(input_group)
        
        # Initialize command history list
        self.cmd_history_list = []
        
        return tab
    
    def setup_styling(self):
        """Apply modern styling to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background: #faf9f8;
            }
            QGroupBox {
                font-weight: 600;
                border: 2px solid #e1dfdd;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #323130;
            }
            QLabel {
                color: #323130;
                font-size: 10pt;
            }
            QMessageBox {
                background: white;
                color: #323130;
            }
            QMessageBox QLabel {
                background: white;
                color: #323130;
                font-size: 10pt;
                padding: 10px;
            }
            QMessageBox QPushButton {
                background: #f3f2f1;
                color: #323130;
                border: 1px solid #d2d0ce;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background: #edebe9;
                border-color: #c7c6c4;
            }
            QMessageBox QPushButton:pressed {
                background: #e1dfdd;
            }
            QMessageBox QPushButton:default {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #0078d4, stop: 1 #106ebe);
                color: white;
                border: none;
                font-weight: 600;
            }
            QMessageBox QPushButton:default:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #106ebe, stop: 1 #005a9e);
            }
            QDialog {
                background: white;
                color: #323130;
            }
            QDialog QLabel {
                background: transparent;
                color: #323130;
                font-size: 10pt;
            }
            QInputDialog {
                background: white;
                color: #323130;
            }
            QInputDialog QLabel {
                background: transparent;
                color: #323130;
                font-size: 10pt;
                padding: 5px;
            }
            QInputDialog QLineEdit {
                background: white;
                color: #323130;
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                padding: 8px;
            }
            QInputDialog QPushButton {
                background: #f3f2f1;
                color: #323130;
                border: 1px solid #d2d0ce;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                min-width: 80px;
            }
        """)
    
    def create_monitor_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Results header
        header_layout = QHBoxLayout()
        results_label = QLabel("Click on items to monitor")
        results_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_layout.addWidget(results_label)
        
        header_layout.addStretch()
        
        self.ipsec_btn = ModernButton("IPSEC")
        self.ipsec_btn.clicked.connect(self.monitor_ipsec)
        header_layout.addWidget(self.ipsec_btn)

        self.system_btn = ModernButton("SYSTEM")
        self.system_btn.clicked.connect(self.monitor_system)
        header_layout.addWidget(self.system_btn)

        self.interface_btn = ModernButton("INTERFACE")
        self.interface_btn.clicked.connect(self.monitor_interface)
        header_layout.addWidget(self.interface_btn)

        layout.addLayout(header_layout)

        # Results display
        self.monitor_text = QTextEdit()
        self.monitor_text.setReadOnly(True)
        self.monitor_text.setFont(QFont("Consolas", 10))
        self.monitor_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.monitor_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                padding: 12px;
                background: #fafafa;
                color: #323130;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.monitor_text)
        self.monitor_text.setPlainText("Monitoring results will be displayed here...")

        self.stop_btn = ModernButton("STOP")
        self.stop_btn.clicked.connect(self.stop_monitoring)
        layout.addWidget(self.stop_btn)

        return tab

    def monitor_ipsec(self):
        """Start IPSec monitoring using proper QThread"""
        if not self.client:
            QMessageBox.warning(self, "Connection Required", "Please connect to the appliance first.")
            return
        
        # Stop any existing monitoring
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()
        
        # Create and start new monitoring thread
        self.monitoring_thread = MonitoringThread(self.client, "ipsec")
        self.monitoring_thread.monitoring_started.connect(self.on_monitoring_started)
        self.monitoring_thread.monitoring_data.connect(self.on_monitoring_data)
        self.monitoring_thread.start()

    def monitor_system(self):
        """Start system monitoring using proper QThread"""
        if not self.client:
            QMessageBox.warning(self, "Connection Required", "Please connect to the appliance first.")
            return
        
        # Stop any existing monitoring
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()
        
        # Create and start new monitoring thread
        self.monitoring_thread = MonitoringThread(self.client, "system")
        self.monitoring_thread.monitoring_started.connect(self.on_monitoring_started)
        self.monitoring_thread.monitoring_data.connect(self.on_monitoring_data)
        self.monitoring_thread.start()

    def monitor_interface(self):
        """Start interface monitoring using proper QThread"""
        if not self.client:
            QMessageBox.warning(self, "Connection Required", "Please connect to the appliance first.")
            return
        
        # Stop any existing monitoring
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()
        
        # Create and start new monitoring thread
        self.monitoring_thread = MonitoringThread(self.client, "interface")
        self.monitoring_thread.monitoring_started.connect(self.on_monitoring_started)
        self.monitoring_thread.monitoring_data.connect(self.on_monitoring_data)
        self.monitoring_thread.start()

    def on_monitoring_started(self, message):
        """Handle monitoring start signal (thread-safe)"""
        self.monitor_text.setPlainText(message)

    def on_monitoring_data(self, data):
        """Handle monitoring data signal (thread-safe)"""
        self.monitor_text.setPlainText(data)

    def stop_monitoring(self):
        """Stop the monitoring thread"""
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()

    def create_backup_extractor_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(20)
        
        # Command source group
        source_group = QGroupBox("💾 Backup Extractor")
        source_group.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        source_layout = QVBoxLayout(source_group)
        
        # File selection
        file_layout = QHBoxLayout()
        self.backupfile_edit = ModernLineEdit("No file selected")
        self.backupfile_edit.setReadOnly(True)
        file_layout.addWidget(QLabel("Backup File:"))
        file_layout.addWidget(self.backupfile_edit)
        
        self.browse_btn = ModernButton("📁 Browse")
        self.browse_btn.clicked.connect(self.browse_backup_file)
        #bfilepath = self.backupfile_edit.text()

        file_layout.addWidget(self.browse_btn)
        
        source_layout.addLayout(file_layout)
        
        layout.addWidget(source_group)
        
        # Execution group
        exec_group = QGroupBox("⚡ Backup Extraction")
        exec_group.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        exec_layout = QVBoxLayout(exec_group)
        
        # Execution controls
        controls_layout = QHBoxLayout()
        
        self.bexecute_btn = ModernButton("▶️ Extract backup file", primary=True)
        self.bexecute_btn.clicked.connect(self.execute_backup_extraction)
        self.bexecute_btn.setEnabled(False)
        controls_layout.addWidget(self.bexecute_btn)

        controls_layout.addStretch()
        exec_layout.addLayout(controls_layout)
        
        # Execution progress
        self.execution_progress = QProgressBar()
        self.execution_progress.setVisible(False)
        self.execution_progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #e1dfdd;
                border-radius: 6px;
                text-align: center;
                background: #f3f2f1;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #107c10, stop: 1 #16c60c);
                border-radius: 4px;
            }
        """)
        exec_layout.addWidget(self.execution_progress)
        
        layout.addWidget(exec_group)
        layout.addStretch()
        
        return tab

    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Please connect to an appliance")
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #f3f2f1;
                color: #323130;
                border-top: 1px solid #e1dfdd;
            }
        """)
    
    def browse_command_file(self):
        """Browse for command file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Command File",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            self.cmdfile_edit.setText(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.command_text.setPlainText(content)
                self.status_bar.showMessage(f"Loaded command file: {Path(file_path).name}")
                
                # Command file path is not saved automatically
                # Users must explicitly save profiles if they want to store this information
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load file: {str(e)}")

    def browse_backup_file(self):
        """Browse for backup file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Backup File",
            "",
            "Text Files (*.na)"
        )
        if file_path:
            self.backupfile_edit.setText(file_path)
            self.bexecute_btn.setEnabled(True)
            # return file_path

    def connect_to_appliance(self):
        """Connect to the Stormshield appliance"""
        host = self.host_edit.text().strip()
        port = self.port_spin.value()
        user = self.user_edit.text().strip()
        password = self.password_edit.text()
        
        if not all([host, user, password]):
            QMessageBox.warning(self, "Missing Information", 
                              "Please fill in all connection fields.")
            return
        
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("🔄 Connecting...")
        self.connection_progress.setVisible(True)
        self.connection_progress.setValue(0)
        
        # Create connection thread
        self.connection_thread = ConnectionThread(host, port, user, password)
        self.connection_thread.connected.connect(self.on_connection_result)
        self.connection_thread.progress.connect(self.connection_progress.setValue)
        self.connection_thread.start()
    
    def on_connection_result(self, success, message):
        """Handle connection result"""
        self.connection_progress.setVisible(False)
        self.connect_btn.setEnabled(True)
        
        if success:
            self.client = self.connection_thread.client
            self.is_connected = True
            self.connect_btn.setText("✅ Connected")
            self.connect_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #107c10, stop: 1 #0e6e0e);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 600;
                }
            """)
            self.connect_btn.setEnabled(False)  # Disable connect when connected
            self.disconnect_btn.setEnabled(True)  # Enable disconnect when connected
            self.disconnect_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #d13438, stop: 1 #c62828);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: 600;
                }
            """)
            self.backup_btn.setEnabled(True)  # Enable backup button
            self.system_info_btn.setEnabled(True)
            
            user_display = self.user_edit.text()
            if user_display.lower() == "admin":
                user_display = f"⚠️ {user_display} ⚠️"
            
            self.status_label.setText(f"✅ Connected to {self.host_edit.text()} as {user_display}")
            self.status_label.setStyleSheet("color: #107c10; padding: 10px;")
            self.execute_btn.setEnabled(True)
            if hasattr(self, 'send_cmd_btn'):
                self.send_cmd_btn.setEnabled(True)  # Enable terminal
            self.status_bar.showMessage(f"Connected to {self.host_edit.text()}")
            
            # Update terminal status
            if hasattr(self, 'terminal_output'):
                self.update_terminal_status()
            
            # Connection settings are not saved automatically
            # Users must explicitly save profiles if they want to store connection data
            
            # Switch to commands tab
            self.tab_widget.setCurrentIndex(1)
            
        else:
            self.is_connected = False
            self.connect_btn.setText("🔗 Connect to Appliance")
            self.connect_btn.setStyleSheet("")  # Reset to default
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.status_label.setText(f"❌ Connection failed: {message}")
            self.status_label.setStyleSheet("color: #d13438; padding: 10px;")
            self.execute_btn.setEnabled(False)
            if hasattr(self, 'send_cmd_btn'):
                self.send_cmd_btn.setEnabled(False)  # Disable terminal
            self.status_bar.showMessage("Connection failed")
            
            # Update terminal status
            if hasattr(self, 'terminal_output'):
                self.update_terminal_status()
    
    def disconnect_from_appliance(self):
        """Disconnect from the Stormshield appliance"""
        if self.client:
            try:
                # Close the SSL connection if possible
                if hasattr(self.client, 'close'):
                    self.client.close()
            except:
                pass  # Ignore any errors during disconnect
            
            self.client = None
        
        self.is_connected = False
        self.connect_btn.setText("🔗 Connect to Appliance")
        self.connect_btn.setStyleSheet("")  # Reset to default styling
        self.connect_btn.setEnabled(True)
        self.backup_btn.setEnabled(False)
        self.system_info_btn.setEnabled(False)
        self.disconnect_btn.setStyleSheet("")
        self.disconnect_btn.setEnabled(False)
        
        self.status_label.setText("❌ Disconnected from appliance")
        self.status_label.setStyleSheet("color: #d13438; padding: 10px;")
        self.execute_btn.setEnabled(False)
        if hasattr(self, 'send_cmd_btn'):
            self.send_cmd_btn.setEnabled(False)  # Disable terminal
        self.status_bar.showMessage("Disconnected from appliance")
        
        # Update terminal status
        if hasattr(self, 'terminal_output'):
            self.update_terminal_status()
        
        # Switch back to connection tab
        self.tab_widget.setCurrentIndex(0)

    def backup_appliance(self):
        """Backup the Stormshield appliance"""
        if self.client:
            self.status_bar.showMessage(f"Launching backup...")
            backup_file = self.client.send_command("config backup list=all> last_backup.na")
        if "100 code=" in str(backup_file):
            self.status_bar.showMessage(f"Backup created")
            QMessageBox.information(self, "Backup Created", 
                              "The backup has been created successfully.")
        else:
            QMessageBox.warning(self, "Backup Failed", 
                                "Failed to create backup.")
            self.status_bar.showMessage("Backup failed")

    def show_system_info(self):
        """Show system information"""
        if self.client:
            self.status_bar.showMessage(f"Retrieving system information... Please wait")
            system_info = str(self.client.send_command("system ident"))
            match = re.search(r"SystemName=\s*(.+)", system_info)
            if match:
                system_name = match.group(1)

            self.status_bar.showMessage("Please wait... Retrieving system information.")
            system_info = self.client.send_command("system right ticket acquire")
            system_info = self.client.send_command(f"system information> system_info_{system_name}")
            system_info = self.client.send_command("system right ticket release")

            self.status_bar.showMessage("System information retrieved")
            QMessageBox.information(self, "System Information", 
                                        f"Filename \"system_info_{system_name}\" created successfully.\n")
        else:
            QMessageBox.warning(self, "System Information Failed", 
                                "Failed to retrieve system information.")
            self.status_bar.showMessage("System information retrieval failed")

    def save_connection_profile(self):
        """Handle saving connection profile with user input for profile name"""
        profile_name, ok = QInputDialog.getText(
            self, "Save Connection Profile", 
            "Enter profile name:", 
            text="Profile 1"
        )
        
        if ok and profile_name.strip():
            self.save_connection_info(profile_name.strip())
    
    def load_connection_profile_dialog(self):
        """Handle loading connection profile with profile selection dialog"""
        saved_profiles = self.get_saved_profiles()
        if not saved_profiles:
            QMessageBox.information(self, "No Profiles", "No saved connection profiles found.")
            return
        
        profile_name, ok = QInputDialog.getItem(
            self, "Load Connection Profile",
            "Select profile to load:",
            saved_profiles, 0, False
        )
        
        if ok and profile_name:
            self.load_connection_profile(profile_name)
    
    def manage_connection_profiles(self):
        """Show profile management dialog"""
        self.show_profile_manager()
    
    def show_profile_manager(self):
        """Show a dialog to manage saved connection profiles"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage Connection Profiles")
        dialog.setModal(True)
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Profile list
        self.profile_list = QListWidget()
        self.refresh_profile_list()
        layout.addWidget(QLabel("Saved Connection Profiles:"))
        layout.addWidget(self.profile_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        load_btn = QPushButton("📂 Load Selected")
        load_btn.clicked.connect(lambda: self.load_selected_profile(dialog))
        button_layout.addWidget(load_btn)
        
        delete_btn = QPushButton("🗑️ Delete Selected")
        delete_btn.clicked.connect(self.delete_selected_profile)
        button_layout.addWidget(delete_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("✖️ Close")
        close_btn.clicked.connect(dialog.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    def refresh_profile_list(self):
        """Refresh the profile list widget"""
        if hasattr(self, 'profile_list'):
            self.profile_list.clear()
            profiles = self.get_saved_profiles()
            for profile in profiles:
                # Get profile details for display
                try:
                    settings = QSettings("snstool", "StormshieldGUI")
                    host = settings.value(f"profiles/{profile}/host", "")
                    user = settings.value(f"profiles/{profile}/user", "")
                    saved_date = settings.value(f"profiles/{profile}/saved_date", "")
                    
                    display_text = f"{profile}"
                    if host and user:
                        display_text += f" ({user}@{host})"
                    if saved_date:
                        display_text += f" - {saved_date}"
                    
                    item = QListWidgetItem(display_text)
                    item.setData(256, profile)  # Store profile name as user data
                    self.profile_list.addItem(item)
                except:
                    # If there's an error reading profile details, just show the name
                    item = QListWidgetItem(profile)
                    item.setData(256, profile)
                    self.profile_list.addItem(item)
    
    def load_selected_profile(self, dialog):
        """Load the selected profile from the list"""
        current_item = self.profile_list.currentItem()
        if current_item:
            profile_name = current_item.data(256)
            if self.load_connection_profile(profile_name):
                dialog.close()
    
    def delete_selected_profile(self):
        """Delete the selected profile from the list"""
        current_item = self.profile_list.currentItem()
        if current_item:
            profile_name = current_item.data(256)
            reply = QMessageBox.question(
                self, "Confirm Deletion",
                f"Are you sure you want to delete profile '{profile_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.delete_connection_profile(profile_name):
                    self.refresh_profile_list()
    
    def execute_backup_extraction(self):
        """Execute the commands"""
        if not self.backupfile_edit.text():
            QMessageBox.warning(self, "No Backup File",
                              "Please specify a backup file to extract.")
        else:
            # TODO: Implement backup extraction logic
            basedir = os.path.dirname(self.backupfile_edit.text())
            archivepath = f"{basedir}/extracted_backup.tar.gz"
            command = f'".\\bin\\decbackup.exe" -i "{self.backupfile_edit.text()}" -o "{archivepath}"'
            subprocess.run(command, shell=True)
            self.status_bar.showMessage("Opération de déchiffrement terminée.")

            with gzip.open(f"{archivepath}", 'rb') as f_in, open(os.path.splitext(archivepath)[0], 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            # Supprimer le fichier .tar.gz
            os.remove(f"{archivepath}")
            self.status_bar.showMessage("Opération de décompression terminée.")
            output_tar = os.path.splitext(archivepath)[0]

            # Exécuter la commande shell pour extraire le .tar
            extract_command = f'tar -xf "{output_tar}" -C "{basedir}"'
            subprocess.run(extract_command, shell=True)
            self.status_bar.showMessage("Opération de décompression du fichier .tar terminée.")

            # Supprimer le fichier .tar
            os.remove(output_tar)
            self.status_bar.showMessage("Dossier 'usr' contenant les informations du backup placé à l'emplacement du script")

            QMessageBox.information(self, "Backup Extraction",
                                    f"Extraction terminée.")
            return

    def execute_commands(self):
        """Execute the commands"""
        if not self.is_connected:
            QMessageBox.warning(self, "Not Connected", 
                              "Please connect to an appliance first.")
            return
        
        # Get commands
        commands = []
        if self.command_text.toPlainText().strip():
            commands = [cmd.strip() for cmd in self.command_text.toPlainText().split('\n') 
                       if cmd.strip() and not cmd.strip().startswith('#')]
        
        if not commands:
            QMessageBox.warning(self, "No Commands", 
                              "Please enter commands to execute.")
            return
        
        # Confirm execution
        reply = QMessageBox.question(
            self, "Confirm Execution",
            f"Are you sure you want to execute {len(commands)} command(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Disable controls
        self.execute_btn.setEnabled(False)
        self.execute_btn.setText("⏳ Executing...")
        self.stop_btn.setEnabled(True)
        self.execution_progress.setVisible(True)
        self.execution_progress.setValue(0)
        
        # Clear previous results
        self.results_text.clear()
        
        # Start execution thread
        self.executor_thread = CommandExecutorThread(self.client, commands)
        self.executor_thread.command_executed.connect(self.on_command_executed)
        self.executor_thread.progress.connect(self.execution_progress.setValue)
        self.executor_thread.finished.connect(self.on_execution_finished)
        self.executor_thread.start()
        
        # Switch to results tab
        self.tab_widget.setCurrentIndex(2)
    
    def stop_execution(self):
        """Stop the current command execution"""
        if self.executor_thread and self.executor_thread.isRunning():
            reply = QMessageBox.question(
                self, "Stop Execution",
                "Are you sure you want to stop the command execution?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Set flag to indicate execution was stopped
                self._execution_stopped = True
                
                # Terminate the execution thread
                self.executor_thread.terminate()
                self.executor_thread.wait(3000)  # Wait up to 3 seconds for clean termination
                
                # Add stop message to results
                timestamp = time.strftime("%H:%M:%S")
                stop_message = f"⏹️ [{timestamp}] Execution stopped by user\n"
                stop_message += f"{'-' * 80}\n\n"
                
                cursor = self.results_text.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.insertText(stop_message)
                self.results_text.setTextCursor(cursor)
                self.results_text.ensureCursorVisible()
                
                # Reset UI state
                self.on_execution_finished()
                self.status_bar.showMessage("Command execution stopped by user")
    
    def format_long_command(self, command):
        """Format long commands with proper line breaks for better readability"""
        if len(command) <= 80:
            return command
        
        # Split on spaces and rebuild with line breaks at appropriate points
        words = command.split()
        formatted_lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            # If adding this word would exceed 80 characters, start a new line
            if current_length + len(word) + 1 > 80 and current_line:
                formatted_lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + (1 if current_line else 0)
        
        # Add the last line
        if current_line:
            formatted_lines.append(' '.join(current_line))
        
        # Join with proper indentation for continuation lines
        result = formatted_lines[0]
        for line in formatted_lines[1:]:
            result += ' \\\n    ' + line
        
        return result
    
    def on_command_executed(self, command, output, success):
        """Handle individual command execution result"""
        timestamp = time.strftime("%H:%M:%S")
        status_icon = "✅" if success else "❌"
        
        # Format command with proper line breaks for long commands
        formatted_command = self.format_long_command(command)
        
        # Create plain text result
        result_text = f"{status_icon} [{timestamp}] Command:\n"
        result_text += f"{formatted_command}\n\n"
        result_text += f"📤 Output:\n"
        result_text += f"{output}\n"
        result_text += f"{'-' * 80}\n\n"
        
        # Add to results as plain text
        cursor = self.results_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(result_text)
        self.results_text.setTextCursor(cursor)
        self.results_text.ensureCursorVisible()
    
    def on_execution_finished(self):
        """Handle execution completion"""
        self.execution_progress.setVisible(False)
        self.execute_btn.setEnabled(True)
        self.execute_btn.setText("▶️ Execute Commands")
        self.stop_btn.setEnabled(False)
        if not hasattr(self, '_execution_stopped'):
            self.status_bar.showMessage("Command execution completed")
        # Reset the stopped flag
        if hasattr(self, '_execution_stopped'):
            delattr(self, '_execution_stopped')
    
    def execute_terminal_command(self):
        """Execute a single command in the terminal"""
        if not self.is_connected:
            self.append_to_terminal("❌ Error: Not connected to appliance. Please connect first.\n")
            return
        
        command = self.terminal_input.text().strip()
        if not command:
            return
        
        # Add to command history
        self.add_to_command_history(command)
        
        # Show command in terminal
        timestamp = time.strftime("%H:%M:%S")
        self.append_to_terminal(f"[{timestamp}] > {command}\n")
        
        # Clear input and disable controls
        self.terminal_input.clear()
        self.send_cmd_btn.setEnabled(False)
        self.terminal_input.setEnabled(False)
        self.terminal_progress.setVisible(True)
        
        # Execute command in thread
        self.terminal_executor = CommandExecutorThread(self.client, [command])
        self.terminal_executor.command_executed.connect(self.on_terminal_command_executed)
        self.terminal_executor.finished.connect(self.on_terminal_execution_finished)
        self.terminal_executor.start()
    
    def on_terminal_command_executed(self, command, output, success):
        """Handle terminal command execution result"""
        timestamp = time.strftime("%H:%M:%S")
        
        if success:
            # Clean up the output - remove status code lines and format nicely
            lines = output.split('\n')
            clean_output = []
            for line in lines:
                # Skip lines that look like status codes
                if not (line.strip().startswith('100 code=') or 
                       line.strip().startswith('101 code=') or
                       line.strip().startswith('102 code=')):
                    clean_output.append(line)
            
            formatted_output = '\n'.join(clean_output).strip()
            if formatted_output:
                self.append_to_terminal(f"📤 Output:\n{formatted_output}\n")
            else:
                self.append_to_terminal("✅ Command executed successfully (no output)\n")
        else:
            self.append_to_terminal(f"❌ Error: {output}\n")
        
        self.append_to_terminal(f"{'─' * 60}\n\n")
    
    def on_terminal_execution_finished(self):
        """Handle terminal execution completion"""
        self.terminal_progress.setVisible(False)
        self.send_cmd_btn.setEnabled(True)
        self.terminal_input.setEnabled(True)
        self.terminal_input.setFocus()
    
    def append_to_terminal(self, text):
        """Append text to terminal output"""
        cursor = self.terminal_output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.terminal_output.setTextCursor(cursor)
        self.terminal_output.ensureCursorVisible()
    
    def clear_terminal(self):
        """Clear the terminal display"""
        welcome_message = """🛡️ Stormshield SNS Interactive Terminal
═══════════════════════════════════════════════════════════════
Welcome! Enter commands below to interact directly with the appliance.
Connection status will be shown here.

"""
        self.terminal_output.setPlainText(welcome_message)
        self.update_terminal_status()

    def get_full_rights(self):
        """Get full rights on the appliance"""
        if self.client:
            self.client.send_command("system right ticket acquire")
            self.append_to_terminal(f"Private data access right granted\n")
            self.status_bar.showMessage("Private data access right granted")

    def release_rights(self):
        """Release full rights on the appliance"""
        if self.client:
            self.client.send_command("system right ticket release")
            self.append_to_terminal(f"Private data access right released\n")

    def add_to_command_history(self, command):
        """Add command to history dropdown"""
        if command not in self.cmd_history_list:
            self.cmd_history_list.insert(0, command)
            # Keep only last 20 commands
            if len(self.cmd_history_list) > 20:
                self.cmd_history_list = self.cmd_history_list[:20]
            
            # Update dropdown
            self.command_history.clear()
            if self.cmd_history_list:
                self.command_history.addItems(self.cmd_history_list)
            else:
                self.command_history.addItem("No command history")
    
    def load_command_from_history(self, command_text):
        """Load selected command from history into input field"""
        if command_text and command_text != "No command history":
            self.terminal_input.setText(command_text)
            self.terminal_input.setFocus()
    
    def clear_command_history(self):
        """Clear the command history"""
        self.cmd_history_list.clear()
        self.command_history.clear()
        self.command_history.addItem("No command history")
    
    def update_terminal_status(self):
        """Update terminal with current connection status"""
        if self.is_connected:
            status_msg = f"✅ Connected to {self.host_edit.text()} as {self.user_edit.text()}\n"
            status_msg += "Ready to receive commands...\n\n"
        else:
            status_msg = "❌ Not connected to any appliance\n"
            status_msg += "Please connect using the Connection tab first.\n\n"
        
        # Insert status at the end of welcome message
        current_text = self.terminal_output.toPlainText()
        if "Ready to receive commands..." not in current_text and "Not connected to any appliance" not in current_text:
            self.append_to_terminal(status_msg)
    
    def clear_results(self):
        """Clear the results display"""
        self.results_text.clear()
        self.status_bar.showMessage("Results cleared")
    
    def export_results(self):
        """Export results to file"""
        if not self.results_text.toPlainText():
            QMessageBox.information(self, "No Results", "No results to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results",
            f"stormshield_results_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;HTML Files (*.html);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    if file_path.endswith('.html'):
                        f.write(self.results_text.toHtml())
                    else:
                        f.write(self.results_text.toPlainText())
                
                QMessageBox.information(self, "Export Successful", 
                                      f"Results exported to:\n{file_path}")
                self.status_bar.showMessage(f"Results exported to {Path(file_path).name}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
    
    def load_window_settings(self):
        """Load only window geometry settings at startup"""
        try:
            settings = QSettings("snstool", "StormshieldGUI")
            
            # Load window geometry only
            geometry = settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
            
        except Exception as e:
            # If settings loading fails, use defaults
            pass
    
    def load_settings(self):
        """Load saved connection settings"""
        try:
            settings = QSettings("snstool", "StormshieldGUI")
            
            # Load connection settings
            host = settings.value("connection/host", "192.168.1.1")
            port = settings.value("connection/port", 443, type=int)
            user = settings.value("connection/user", "admin")
            # Note: We don't save passwords for security reasons
            
            # Apply loaded settings to UI
            self.host_edit.setText(host)
            self.port_spin.setValue(port)
            self.user_edit.setText(user)
            
            # Load window geometry
            geometry = settings.value("window/geometry")
            if geometry:
                self.restoreGeometry(geometry)
            
            # Load last command file path
            last_file = settings.value("commands/last_file", "")
            if last_file and Path(last_file).exists():
                self.cmdfile_edit.setText(last_file)
                try:
                    with open(last_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.command_text.setPlainText(content)
                except:
                    pass  # Ignore file read errors
            
        except Exception as e:
            # If settings loading fails, use defaults
            pass
    
    def save_settings(self):
        """Save only window geometry settings (no connection data)"""
        try:
            settings = QSettings("snstool", "StormshieldGUI")
            
            # Save only window geometry - no connection settings
            settings.setValue("window/geometry", self.saveGeometry())
            
            # Don't save connection settings automatically anymore
            # Users must explicitly save profiles if they want to store connection data
            
        except Exception as e:
            # Ignore save errors
            pass
    
    def save_connection_info(self, profile_name=None):
        """Save connection information with optional profile name"""
        try:
            host = self.host_edit.text().strip()
            port = self.port_spin.value()
            user = self.user_edit.text().strip()
            
            if not all([host, user]):
                QMessageBox.warning(self, "Missing Information", 
                                  "Please fill in host and username before saving.")
                return False
            
            settings = QSettings("snstool", "StormshieldGUI")
            
            # If no profile name provided, use default
            if not profile_name:
                profile_name = "default"
            
            # Save to specific profile section only
            profile_section = f"profiles/{profile_name}"
            settings.setValue(f"{profile_section}/host", host)
            settings.setValue(f"{profile_section}/port", port)
            settings.setValue(f"{profile_section}/user", user)
            settings.setValue(f"{profile_section}/saved_date", time.strftime("%Y-%m-%d %H:%M:%S"))
            
            # No longer save to "connection" section to avoid automatic persistence
            
            # Add to list of saved profiles
            saved_profiles = settings.value("profiles/list", [])
            if isinstance(saved_profiles, str):
                saved_profiles = [saved_profiles] if saved_profiles else []
            elif not isinstance(saved_profiles, list):
                saved_profiles = []
            
            if profile_name not in saved_profiles:
                saved_profiles.append(profile_name)
                settings.setValue("profiles/list", saved_profiles)
            
            self.status_bar.showMessage(f"Connection profile '{profile_name}' saved successfully")
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save connection: {str(e)}")
            return False
    
    def load_connection_profile(self, profile_name):
        """Load a saved connection profile"""
        try:
            settings = QSettings("snstool", "StormshieldGUI")
            profile_section = f"profiles/{profile_name}"
            
            host = settings.value(f"{profile_section}/host", "")
            port = settings.value(f"{profile_section}/port", 443, type=int)
            user = settings.value(f"{profile_section}/user", "")
            
            if host and user:
                self.host_edit.setText(host)
                self.port_spin.setValue(port)
                self.user_edit.setText(user)
                self.status_bar.showMessage(f"Loaded connection profile '{profile_name}'")
                return True
            else:
                QMessageBox.warning(self, "Profile Error", f"Profile '{profile_name}' not found or incomplete.")
                return False
                
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load profile: {str(e)}")
            return False
    
    def get_saved_profiles(self):
        """Get list of saved connection profiles"""
        try:
            settings = QSettings("snstool", "StormshieldGUI")
            saved_profiles = settings.value("profiles/list", [])
            if isinstance(saved_profiles, str):
                return [saved_profiles] if saved_profiles else []
            elif isinstance(saved_profiles, list):
                return saved_profiles
            else:
                return []
        except:
            return []
    
    def delete_connection_profile(self, profile_name):
        """Delete a saved connection profile"""
        try:
            settings = QSettings("snstool", "StormshieldGUI")
            
            # Remove from profiles list
            saved_profiles = self.get_saved_profiles()
            if profile_name in saved_profiles:
                saved_profiles.remove(profile_name)
                settings.setValue("profiles/list", saved_profiles)
            
            # Remove profile data
            profile_section = f"profiles/{profile_name}"
            settings.remove(profile_section)
            
            self.status_bar.showMessage(f"Connection profile '{profile_name}' deleted")
            return True
            
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", f"Failed to delete profile: {str(e)}")
            return False
    
    def closeEvent(self, event):
        """Handle application closing"""
        # Save settings before closing
        self.save_settings()
        
        if self.connection_thread and self.connection_thread.isRunning():
            self.connection_thread.terminate()
            self.connection_thread.wait()
        
        if self.executor_thread and self.executor_thread.isRunning():
            reply = QMessageBox.question(
                self, "Commands Running",
                "Commands are still executing. Do you want to quit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.executor_thread.terminate()
                self.executor_thread.wait()
            else:
                event.ignore()
                return
        
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()
        
        if hasattr(self, 'terminal_executor') and self.terminal_executor and self.terminal_executor.isRunning():
            self.terminal_executor.terminate()
            self.terminal_executor.wait()
        
        # Disconnect if still connected
        if self.is_connected:
            self.disconnect_from_appliance()
        
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Stormshield SNS CLI GUI")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("snstool")
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show main window
    window = StormshieldGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
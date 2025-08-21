#  Stormshield SNS CLI GUI

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.4+-green.svg)](https://pypi.org/project/PyQt6/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20|%20Linux%20|%20macOS-lightgrey.svg)]()

A modern, user-friendly graphical interface for managing Stormshield SNS appliances. This application transforms the command-line interface into an intuitive GUI with modern styling and advanced features.

##  Features

###  Modern Interface
- **Clean, modern design** with Microsoft Fluent Design inspired styling
- **Tabbed interface** for organized workflow
- **Real-time progress indicators** for connection and command execution
- **Syntax highlighting** for Stormshield commands

###  Connection Management
- **Secure SSL connections** to Stormshield appliances
- **Connection status monitoring** with visual indicators
- **User session conflict warnings** with admin user highlighting
- **Automatic reconnection** capabilities

###  Command Execution
- **Dual input methods**: Load from file or enter commands manually
- **Batch command execution** with progress tracking
- **Real-time command output** display
- **Error handling** with detailed error messages

##  Requirements

- **Python 3.8+** (recommended: Python 3.9 or later)
- **PyQt6** for the graphical interface
- **Stormshield SNS library** for appliance communication
- **Operating System**: Windows 10/11 (tested), Linux, or macOS

##  Quick Start

### Option 1: Automated Setup for Windows (PY to EXE with pyinstaller)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/marson-l/stormshield-cli-gui.git
   cd stormshield-cli-gui
   ```

2. **Run the setup script**:
   ```batch
   scripts\setup.bat
   ```

3. **Launch the application**:
   ```batch
   scripts\launch.bat
   ```

### Option 2: Manual launch (Linux/Windows/MacOS)

1. **Clone the repository and install dependencies**:
   ```bash
   git clone https://github.com/marson-l/stormshield-cli-gui.git
   cd stormshield-cli-gui
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   python src/main_gui.py
   ```

##  Usage Guide

### 1. Connection Setup
1. Enter appliance details (Host/IP, Port, Username, Password)
2. Click "Connect to Appliance"
3. Wait for connection confirmation

### 2. Command Configuration
- Click on "Commands" tab
- **Load from file**: Click "Browse" to select a command file
- **Manual entry**: Type commands directly in the text area

### 3. Execute Commands
1. Click "Execute Commands"
2. Monitor progress in the progress bar
3. View results in the Results tab

### 4. Backup File decryptor
‼️"decbackup.exe" must be into the same folder as the main-gui.py script (or .exe if built).
- You can also find decbackup tool into last "Release packages"
1. Click "Backup Extractor" tab
2. Browse for backup file (*.na)
3. Click "Extract backup file" button
4. Backup extracted into the same folder as the backupfile.na

### 5. Backup & Sytem Info
- On "Connection" page, after connecting to appliance, you can export a fresh backup of the SNS. You can also export system information for troubleshooting purposes.

### 6. Monitoring (WIP)
- You can monitor some of items as CPU, RAM, Interfaces, IPSEC Tunnels, Users, ...
1. Click on "Monitor" tab
2. Click on the item that you want to monitor
3. At the execution, the output is reloaded each 2 seconds
4. Click "STOP" to terminate loop.

##  Building Executable

Run the build script to create a standalone executable:
```batch
scripts\build.bat
```

##  License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

##  Disclaimer

This tool is designed for legitimate network administration purposes. Users are responsible for ensuring they have proper authorization before connecting to any Stormshield appliances.





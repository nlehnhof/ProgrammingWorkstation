# Programming Workstation - Application Documentation

**Branch:** `sparse` (current production branch)  
**Latest Commit:** a7c239c - shrink size  
**Status:** Production-ready with active development of stability improvements

⚠️ **WARNING:** Configuration and environment variable handling for devices are still rough and in progress. Test thoroughly in non-production environments before deploying to production hardware.

---

## EXECUTIVE SUMMARY (For Management)

**What is this?** This is a Device Programming and Management Workstation — a PyQt5-based desktop application that provides a unified interface for managing multiple embedded device types. It consolidates device registration, hardware verification, programming execution, and error logging.

**What does it do?**
- Register and manage multiple device types and configurations
- Verify hardware setup before programming (connection validation with visual diagram)
- Execute device-specific programming scripts (firmware, configuration, testing)
- Centralized error logging with timestamped crash diagnostics
- Generate labels and documentation for each programmed device
- Extensible architecture supporting new device types

**Key Features:**
- Hardware verification step prevents configuration mistakes before programming starts
- Centralized error logging with `logs/` directory containing timestamped crash reports
- Modular device type abstraction for easy extension to new device types
- PyQt5-based GUI with multi-page navigation

**Current Device Support:** Teltonika RUTX routers (see TR_DEVICE_DOCUMENTATION.md for specifics)

**Status:** Production-ready on sparse branch with improved error handling and organization.

---

## ARCHITECTURE OVERVIEW (For Project Leads)

### Core Application Components

**1. Application Entry Point (`main.py`)**
- Initializes PyQt5 application
- Launches MainWindow with Fusion styling
- Sets custom color scheme (white background, green buttons, dark text)
- Single entry point for entire application

**2. Core Manager (`core/manager.py`)**
- Central orchestration for device lifecycle operations
- Loads/saves device credentials from `devices.json` (JSON persistence)
- Credential storage: in-memory with JSON persistence
- Device folder copying/management

**3. Example of Device Type Abstraction (`device_types/`)**
- **Base class:** `base_device.py` (abstract)
- **Implementations:** 
  - `ssh_device.py` - SSH/SFTP-based devices
  - `telnet_device.py` - Telnet-based devices
- **Protocol:** Each device implements `connect()`, `disconnect()`, `upload()`, `run()`
- **Purpose:** Extensibility for adding new device types (Cisco, HPE, etc.)
- **Not currently used in application.**

**4. Error Handling & Logging (`pages/error_log_page.py`)**
- Centralized `LogDialog` for consistent error display
- Creates timestamped crash logs in `logs/` directory
- Global exception hook catches uncaught application errors
- Buffered output collection system (`_output_buffer`)
- Single error popup prevents dialog spam
- Does NOT exit application on error (graceful degradation)

**5. Shared Utilities (`resources/utilities/`)**

| Module | Purpose |
|--------|---------|
| `device_config.py` | Configuration management (DEFAULTS → device_config.json → env vars) |
| `ssh_session.py` | Pooled SSH connections with timeouts and context managers |
| `mac_utils.py` | Robust MAC address extraction from various formats |
| `excel_utils.py` | Header-based Excel column detection with context managers |
| `network_utils.py` | IP validation and subnet calculation |
| `fonts.py` | Consistent UI font definitions |

**6. Application Pages (PyQt5 Stacked Widget)**

| Index | Module | Purpose |
|-------|--------|---------|
| 0 | `pages/home_page.py` | Navigation menu: "Add Device" or "Program Device" |
| 1 | `pages/add_device_page.py` | Device registration form with type selection |
| 2 | `pages/program_page.py` | Device selection and programming launch |
| 3 | `pages/connection_page.py` | Hardware verification (shows wiring diagram) |
| N/A | `pages/error_log_page.py` | Error dialog and crash log saving (triggered as needed) |

### Data Flow

```
User Input (GUI - home_page)
    ↓
[Add Device] → Register new device type + path
    ↓ OR
[Program Device] → Select device → Launch programming
    ↓
[Connection Page] → Hardware verification (visual confirmation)
    ↓ YES
[Program Page] → Device selector interface
    ↓
Device Manager → Load credentials from devices.json
    ↓
Device Handler → Determine device to program
    ↓
Device-Specific Script Execution (e.g., prog_dev.py for TR device)
    ↓
[error_log_page] ← Error dialog + crash log (if error occurs)
    ↓
Completion → Labels, logs, and Excel updates (device-specific)
```

### Project Structure

```
ProgrammingWorkstation/
├── main.py                          # Application entry point
├── core/
│   ├── manager.py                  # Device lifecycle management
│   └── READme.md                   # Core architecture guide
├── device_types/                    # Abstract device interfaces
│   ├── __init__.py
│   ├── base_device.py              # Abstract base class
│   ├── ssh_device.py               # SSH/SFTP implementation
│   └── telnet_device.py            # Telnet implementation
├── devices/                         # Device-specific implementations
│   ├── __init__.py
│   └── TR/                         # Teltonika Router (see TR_DEVICE_DOCUMENTATION.md)
├── pages/                           # PyQt5 UI pages (stacked widget)
│   ├── main_window.py              # Window controller + stacked widget
│   ├── home_page.py                # Home navigation (index 0)
│   ├── add_device_page.py          # Device registration (index 1)
│   ├── program_page.py             # Programming interface (index 2)
│   ├── connection_page.py          # Hardware verification (index 3)
│   └── error_log_page.py           # Centralized error handling
├── resources/
│   ├── utilities/
│   │   ├── device_config.py        # Configuration loader
│   │   ├── ssh_session.py          # Pooled SSH with timeouts
│   │   ├── mac_utils.py            # MAC address extraction
│   │   ├── excel_utils.py          # Excel operations + column detection
│   │   ├── network_utils.py        # IP + subnet validation
│   │   └── fonts.py                # UI fonts
│   └── images/
│       └── router.jpg              # Router wiring diagram (used by connection_page)
├── logs/                            # Timestamped crash logs (auto-created at runtime)
├── devices.json                     # Device credential registry (auto-created)
├── DOCUMENTATION_OVERVIEW.md        # This file (application guide)
├── requirements.txt                 # Python dependencies
└── .git/                            # Version control
```

---

## DETAILED TECHNICAL GUIDE (For Developers)

### Device Manager (`core/manager.py`)

**Purpose:** Orchestrate device registration and lifecycle

**Key Methods:**
```python
def create_device(data: Dict):
    """Register a new device
    
    Args:
        data: {"Name": str, "Path": str, ...}
    
    Creates device entry in devices.json and copies folder to devices/{name}/
    """

def get_credentials(name: str):
    """Retrieve stored credentials from devices.json"""
    
def _load_devices():
    """Load device registry from JSON"""
    
def _save_devices():
    """Save device registry to JSON"""
```

**Device Registration Flow:**
1. User provides: Device name, path to device folder
2. Manager validates inputs (name not empty, path exists)
3. Device folder copied to `devices/{name}/`
4. Credentials stored in `devices.json`

### Configuration Management (`resources/utilities/device_config.py`)

**Purpose:** Externalize device configuration from code with environment override capability

**Precedence (lowest → highest):**
1. **DEFAULTS** - Built-in fallbacks (in device_config.py)
2. **device_config.json** - Device-specific file overrides (in device folder)
3. **Environment variables** - Runtime overrides with `TR_` prefix (device-specific)

**Usage:**
```python
from resources.utilities.device_config import load_config

currdir = os.path.dirname(__file__)
cfg = load_config(currdir)  # Load config with precedence

print(cfg["bbb_ip"])  # Can be from DEFAULTS, file, or env
```

**⚠️ WARNING:** Environment variables should only override if your hardware setup actually uses those values.

### SSH Connection Pooling (`resources/utilities/ssh_session.py`)

**Purpose:** Replace repeated SSH connections with pooled, timeout-protected sessions

**Key Classes:**
```python
class SSHSession:
    """Pooled SSH connection with automatic reconnection and timeouts"""
    
    def ensure_connected(self):
        """Lazy connection (connects on first use)"""
        
    def run(command, timeout=None):
        """Execute command with timeout enforcement"""
        
    def invoke_shell(timeout=None):
        """Return ManagedShell context manager (auto-closes)"""
        
    def upload(local_path, remote_path):
        """SFTP upload using pooled connection"""

class ManagedShell:
    """Context manager wrapper around invoke_shell() channel"""
    
    def __enter__/__exit__(self):
        """Automatic channel cleanup (prevents leaks)"""
```

**Usage:**
```python
with SSHSession(host, user, password, timeout=30) as session:
    session.run("cmd1")           # Reuses connection
    session.run("cmd2")           # Reuses connection
    with session.invoke_shell() as shell:  # Context manager
        shell.send("passwd\n")
        shell.recv(1000)
    # Shell auto-closes on exit
# Connection auto-closes on exit
```

### MAC Address Extraction (`resources/utilities/mac_utils.py`)

**Purpose:** Robustly extract MAC address from shell output (multiple formats supported)

**Supported Formats:**
1. Old ifconfig: `eth0 ... HWaddr 20:97:27:17:9E:4B`
2. New ifconfig: `ether 20:97:27:17:9E:4B txqueuelen 1000`
3. ip link: `link/ether 20:97:27:17:9e:4b brd ff:ff:ff:ff:ff:ff`
4. Bare regex: MAC anywhere in text

**Usage:**
```python
from resources.utilities.mac_utils import extract_mac

mac = extract_mac(ifconfig_output, interface="eth0")
# Returns: "20:97:27:17:9E:4B" or None
```

### Excel Operations (`resources/utilities/excel_utils.py`)

**Purpose:** Dynamic column detection (not hardcoded positions) with guaranteed file closing

**Key Functions:**
```python
@contextmanager
def open_workbook(path):
    """Context manager guaranteeing workbook.close()"""
    
def get_header_map(sheet, header_row=1):
    """Return {column_name: [1-based indices]} (handles duplicates)"""
    
def find_column(header_map, name, occurrence=0):
    """Get column index by header name (supports duplicate headers)"""
    
def find_row_by_value(sheet, value, min_row=2):
    """Find row number where any cell equals value"""
    
def lookup_excel(path, gate):
    """Look up gate config (IP/netmask/gateway) with validation"""
```

**Usage:**
```python
from resources.utilities.excel_utils import open_workbook, get_header_map

with open_workbook(path) as wb:
    sheet = wb.active
    header_map = get_header_map(sheet)  # {"Gate IP": [8], ...}
    ip_col = find_column(header_map, "Gate IP")
    value = sheet.cell(row=row_num, column=ip_col).value
# Workbook auto-closes even on error
```

### Application Pages

**MainWindow (`pages/main_window.py`):**
- QMainWindow with QStackedWidget
- Four pages (indices 0-3) + error dialog (not stacked)
- Navigation: `stacked_widget.setCurrentIndex(page_index)`

**HomePage (Index 0) (`pages/home_page.py`):**
- Two buttons: "Add Device" and "Program Device"
- Navigation point for application

**AddDevice (Index 1) (`pages/add_device_page.py`):**
- Form to register new device
- Inputs: Device name, device type, path to device folder
- Calls DeviceManager.create_device()

**ProgramPage (Index 2) (`pages/program_page.py`):**
- Device selector dropdown
- Launches device-specific programming script
- Displays real-time output

**ConnectionPage (Index 3) (`pages/connection_page.py`):**
- Hardware verification checklist
- Displays router wiring diagram from `resources/images/router.jpg`
- "YES" button to confirm → proceed to ProgramPage
- Prevents accidental misprogramming

**ErrorLogPage (`pages/error_log_page.py`):**
- Triggered on exception (not in stacked widget)
- Shows error dialog with full output
- Saves crash log to `logs/crash_log_TIMESTAMP.txt`
- Prevents application exit (graceful error handling)

---

## CONFIGURATION & ENVIRONMENT VARIABLES

### Device-Specific Configuration

Each device type can define its own configuration file and environment variables:

**Example (Teltonika Router):**
- File: `devices/TR/device_config.json`
- Environment variables: `TR_*` prefix (e.g., `TR_BBB_IP`, `TR_ROUTER_NEW_PASSWORD`)

See **TR_DEVICE_DOCUMENTATION.md** for device-specific configuration details.

### Application-Level Configuration

Currently minimal; most configuration is device-specific:
- Device registry: `devices.json` (auto-created)
- Logs directory: `logs/` (auto-created)
- Device credentials: In-memory + JSON persistence

---

## ANALYSIS: Architecture Quality & Known Issues

### ✅ STRENGTHS

1. **Modular Device Architecture**
   - Abstract base class allows easy extension for new device types
   - Each device type isolated in `devices/` folder
   - SSH/Telnet abstraction for different connection methods

2. **Centralized Error Handling**
   - Single point of error display and logging
   - Timestamped crash logs with full context
   - Global exception hook catches uncaught errors
   - Graceful degradation (app doesn't crash on error)

3. **Improved Utilities Library**
   - Reusable SSH connection pooling with timeouts
   - Robust MAC extraction handles multiple formats
   - Dynamic Excel column detection (not hardcoded)
   - Guaranteed file cleanup (context managers)

4. **Hardware Verification Step**
   - Prevents configuration mistakes before programming
   - Visual diagram ensures operator understands setup
   - Explicit confirmation required to proceed

5. **Multi-Page Navigation**
   - Clear workflow: Home → Add/Program → Connection → Program
   - Stacked widget reduces memory footprint
   - Easy to add new pages

### ⚠️ KNOWN LIMITATIONS

1. **Single Connection Method Per Device Type**
   - Currently: SSH or Telnet at device level
   - Future: Could support fallback (try SSH, then Telnet)

2. **No Device Type Plugin System**
   - New device types require code changes
   - Could be abstracted to dynamic loading

3. **Credentials in JSON**
   - Plain-text in `devices.json`
   - For production: Consider encrypted credential storage

4. **Device Manager Blocking**
   - Device-specific scripts run on main thread
   - Could be moved to thread pool for UI responsiveness

---

## DEVELOPER SETUP

### Installation

```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- PyQt5 (5.15.11) - GUI framework
- paramiko (5.0.0) - SSH/SFTP client
- openpyxl (3.1.5) - Excel operations
- ping3 (5.1.5) - Network utilities

### Adding a New Device Type

1. Create folder: `devices/{DEVICE_NAME}/`
2. Create `device_types/{device_name}_device.py` implementing `base_device.py`
3. Create `devices/{DEVICE_NAME}/programming_script.py` (device-specific logic)
4. Register in device type selector (UI)
5. Add device-specific documentation

### Testing Configuration

To test with custom configuration values:

```bash
# Device-specific env vars (example for TR device)
export TR_BBB_IP="192.168.10.5"
export TR_ROUTER_NEW_IP="192.168.100.1"

python main.py
```

---

## REQUIREMENTS

**Key Dependencies:**
- PyQt5 = 5.15.11
- paramiko = 5.0.0
- openpyxl = 3.1.5
- ping3 = 5.1.5

See `requirements.txt` for complete list.

---

**Last Updated:** 2026-07-23  
**Documentation Status:** Complete - Application framework only (TR device details in TR_DEVICE_DOCUMENTATION.md)

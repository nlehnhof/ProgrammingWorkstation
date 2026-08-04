# Teltonika Router (TR) Device - Implementation Guide

**Device Type:** Teltonika RUTX08 Router  
**Firmware Version:** 0.7.22.3  
**Implementation Location:** `devices/TR/`  
**Status:** In production; orchestration layer migrated, hardware script not yet  
**Last Updated:** 2026-08-04 (`e96074a`)

> ### Read this first — what this document is
>
> This is the long-form reference for the TR device: hardware profile, the
> provisioning steps, file layout, and the **target** architecture. For what the
> code does *today*, see [`documentation/`](documentation/) in this folder,
> which is kept in sync with each commit.
>
> **Both halves of this device have now been migrated**, so the architecture
> this document describes is the architecture that runs:
>
> * **`prog_dev.py`** (943 → 364 lines) — layered config, pooled `SSHSession`,
>   header-based Excel access, shared crash-log/label/sheet reporting.
> * **`teltonika.py`** — seven dispatched milestones instead of a flat script,
>   pooled connections, completion-driven waits in place of fixed sleeps,
>   `mac_utils` for MAC extraction, and every address, credential and timeout
>   read from `device_config.json`.
>
> `TR_*` environment variables therefore work throughout. TR also ships a
> `checklist.json` now, so it has the live Status panel.
>
> ⚠️ Two details this document predates: the router config push covers **82**
> of the 94 files in `og_configs/` (the list is `config_manifest.json`; the 12
> omitted are per-unit device state), and the old "revert the network file
> afterwards" step is gone as redundant.

---

## EXECUTIVE SUMMARY (For Management)

**What is this?** TR is a complete implementation for automating Teltonika RUTX router provisioning within the ProgrammingWorkstation. It handles firmware updates, network configuration, password management, and functional testing.

**Business Value:**
- Reduces manual configuration from **30+ minutes → ~7.5 minutes automated**
- Audit trail with timestamped crash logs
- Hardware verification prevents configuration mistakes
- Automatic label generation with device metadata
- Production deployment in airport gate control systems

**Device Supported:** Teltonika RUTX08 (and compatible RUTX models with RutOS 0.7.22.3+)

**Key Metrics:**
- ~7.5 minutes per device (firmware install & reboot are hardware-limited)
- Robust SSH with connection pooling and automatic timeouts
- Multiple MAC address format support (handles format variations)

---

## TECHNICAL OVERVIEW

### Device Hardware Profile

**Teltonika RUTX08 Specifications:**
- Processor: ARM-based Linux system
- RAM: 512MB-1GB
- Storage: NAND flash with dual firmware partitions
- Network: Multiple Ethernet ports (LAN1, LAN2, LAN3)
- Protocols: SSH (port 22), Modbus/TCP (port 502)
- OS: RutOS (proprietary Teltonika Linux distribution)

**Default Credentials:**
- Username: admin
- Password: factory password found on the back of the router

**Firmware:**
- Current version: 0.7.22.3 (deployed binary)
- Updateable via `sysupgrade` utility
- Installation time: ~3 minutes
- Boot time: ~2.5 minutes

### Implementation Architecture

```
teltonika.py (main automation, 500+ lines)
├── Device Configuration (device_config.json)
│   ├── BBB connectivity (IP, username, password)
│   ├── Router connectivity (temp IP, new IP, new password)
│   ├── Firmware filename
│   ├── Network template (gate IP, netmask, gateway)
│   └── Timeouts (SSH, test script)
│
├── Step 1: Copy & Update Config Files
│   └─ og_configs/ → configs/ (working copy)
│
├── Step 2-3: Upload Test File to BBB (via SSH pooling)
│   ├─ Beaglebone Black (192.168.7.2)
│   └─ Upload /home/raj/FloodLighToggle.py
│
├── Step 4-5: Upload & Install Firmware
│   ├─ Router (192.168.1.1 temporary IP)
│   ├─ SFTP: firmware_filename to /tmp/
│   └─ Execute: sysupgrade /tmp/firmware.bin (3 min wait)
│
├── Step 6: Reset Password (interactive shell)
│   ├─ Verify firmware version in login banner
│   ├─ Interactive shell context manager
│   └─ passwd command: old → new → confirm
│
├── Step 7: Upload 82 Config Files (SFTP)
│   ├─ Iterate configs/ folder
│   └─ Upload each to /etc/config/{filename}
│
├── Step 8: Extract MAC Address
│   ├─ Execute: ifconfig -a
│   ├─ Robust MAC extraction (HWaddr/ether/link/ether formats)
│   └─ Return: XX:XX:XX:XX:XX:XX or None
│
└── Step 9: Reboot & Wait
    ├─ Execute: reboot command
    ├─ Wait 2.5 minutes for boot
    └─ Revert network file to template
```

### Network Topology

```
PC / Workstation
    │ Ethernet (LAN2)
    │
Teltonika RUTX Router
    │ Ethernet (LAN1)
    │
Beaglebone Black (192.168.7.2)
    │
Ethernet Switch (external connectivity)
```

---

## FILE STRUCTURE & CONTENTS

```
devices/TR/
├── teltonika.py                    # Main automation script (500+ lines)
├── prog_dev.py                     # Programming GUI wrapper (1500+ lines)
├── FloodLighToggle.py             # Modbus/TCP test client (558 lines)
├── device_config.json             # Configuration (externalized from code)
├── debugging.md                    # Device debugging notes
├── READme.md                       # Basic device guide
├── RUTX_R_00.07.22.3_WEBUI.bin   # Firmware binary (30 MB)
│
├── og_configs/                     # Original config template (94 files - never modified)
│   ├── network                     # Network interface config
│   ├── system                      # System settings
│   ├── firewall                    # Iptables rules
│   ├── dhcp                        # DHCP server config
│   ├── modbus_server               # Modbus daemon config
│   └── [77 more config files]
│
├── configs/                        # Working copy (replaced each deployment)
│   └── [82 config files deployed to router]
│
├── og_testfile/                    # Original test file (never modified)
│   └── FloodLighToggle.py         # Original Modbus test script
│
├── testfile/                       # Working test file (updated at runtime)
│   └── FloodLighToggle.py         # Test file with updated IPs
│
├── labels/                         # Generated label files (at runtime)
│   └── label_YYYY-MM-DD_HH-MM-SS.txt
│
├── history/                        # Legacy/experimental versions
│   ├── dashboard.py               # Old dashboard attempt
│   ├── prog_dev_old.py           # Previous prog_dev version
│   └── tel2.py                    # Experimental teltonika script
│
└── *.xlsx                          # Airport/gate spreadsheets
    ├── GCN-PDX.xlsx               # Portland airport gates
    ├── JKC-SLC.xlsx               # Salt Lake City airport gates
    ├── IP_TEMPLATE.xlsx           # Template for new airports
    └── oshkosh_log.xlsx           # Master deployment log
```

---

## KEY FILES DETAILED

### teltonika.py - Core Automation (500+ lines)

**Purpose:** Automated 9-step device provisioning

**Updated Imports (Sparse Branch):**
```python
from resources.utilities.device_config import load_config
from resources.utilities.ssh_session import SSHSession, SSHCommandTimeout
from resources.utilities.mac_utils import extract_mac

currdir = os.path.dirname(__file__)
cfg = load_config(currdir)  # Load from device_config.json or env vars
```

**Configuration Precedence:**
1. Built-in DEFAULTS (in device_config.py)
2. `device_config.json` (device-specific overrides)
3. Environment variables `TR_*` (runtime overrides)

**Key Configuration Parameters:**
- `bbb_ip` - Beaglebone Black IP (default: 192.168.7.2)
- `bbb_user` - BBB SSH username (default: raj)
- `bbb_password` - BBB SSH password (default: Jetway)
- `router_temp_ip` - Router temporary IP (default: 192.168.1.1)
- `router_new_ip` - Router new IP after config (default: 192.168.81.1)
- `router_new_password` - New root password (default: Jetway@dm1n)
- `firmware_filename` - Firmware binary name (default: RUTX_R_00.07.22.3_WEBUI.bin)
- `ssh_timeout` - SSH operation timeout in seconds (default: 30)

**Execution Steps:**

1. **Copy & Update Config Files** (lines ~159-199)
   - Copy `og_configs/` → `configs/` (working copy)
   - Read `configs/network`
   - Replace template IP (10.28.18.2) with gate IP
   - Replace template netmask
   - Verify replacement successful

2. **Upload Test File to BBB** (lines ~201-262)
   - Copy `og_testfile/FloodLighToggle.py` → `testfile/`
   - Update gateway IP in test file
   - SSH to BBB (`192.168.7.2`)
   - SFTP upload to `/home/raj/FloodLighToggle.py`
   - Verify file exists

3. **Upload Firmware to Router** (lines ~265-293)
   - SSH to router at `192.168.1.1` (temporary IP)
   - SFTP upload `RUTX_R_00.07.22.3_WEBUI.bin` to `/tmp/`
   - Verify file present

4. **Install Firmware** (lines ~295-313)
   - Execute: `sysupgrade /tmp/RUTX_R_00.07.22.3_WEBUI.bin`
   - Wait ~3.5 minutes (hardware limitation)

5. **Reset Password (Interactive)** (lines ~316-373)
   - Reconnect to router (temp password)
   - Verify firmware version in banner (should show "0.7.22.3")
   - Invoke interactive shell (ManagedShell context manager)
   - Send: `passwd` command
   - Wait for prompts: "Old password" → send temp pass
   - "New password" → send new password
   - "Retype password" → send new password
   - **Risk:** Prompt text may vary by firmware version

6. **Upload 82 Config Files** (lines ~375-472)
   - Iterate through all files in `configs/`
   - SFTP upload each to `/etc/config/{filename}`
   - Serial upload (could be parallelized for optimization)

7. **Extract MAC Address** (lines ~475-496)
   - Execute: `ifconfig -a`
   - Use robust MAC extraction (handles HWaddr, ether, link/ether)
   - Extract from eth0 interface
   - Return MAC string (XX:XX:XX:XX:XX:XX)

8. **Reboot Router** (lines ~498-532)
   - Send: `reboot` command
   - Wait ~2.5 minutes (hardware limitation)
   - Revert `configs/network` to template IP

**Error Handling:**
- Every step verifies success before proceeding
- SSH operations timeout at configured value (default 30s)
- MAC extraction returns None if not found (no crash)
- Connection pooling prevents resource exhaustion

### prog_dev.py - Programming GUI Wrapper (1500+ lines)

**Purpose:** PyQt5/Tkinter GUI interface for device programming with Excel integration

**Updated Imports (Sparse Branch):**
```python
from resources.utilities.device_config import load_config
from resources.utilities.ssh_session import SSHSession
from resources.utilities.excel_utils import (
    open_workbook, get_header_map, find_column, find_row_by_value, lookup_excel
)

cfg = load_config(currdir)
```

**Column Mapping (Header-Based, Not Hardcoded):**
```python
COLUMN_NAMES = {
    "gate_num": "PBB Gate",
    "router_num": "Jetway PN",
    "router_model": "Model",
    "gateway_ip": "Gateway",
    "netmask": "Netmask",
    "gate_ip": "Gate IP",
    # Raises clear error if column missing
}
```

**User Interface:**
- Excel file dropdown (select device metadata spreadsheet)
- Gate number dropdown (auto-populated from Excel)
- Auto-populated IP/netmask/gateway (with validation)
- QR code scan input (extracts temporary password)
- Program button (launches teltonika.py automation)
- Real-time output display (teltonika.py progress)

**Features:**
- Excel lookup with header-based column detection
- IP format validation (a.b.c.d)
- Subnet correctness validation
- Crash log generation on error
- Label file generation on success
- Excel cell hyperlinking to logs
- MAC address extraction and logging
- Centralized error handling via error_log_page.py

### FloodLighToggle.py - Modbus Test Client (558 lines)

**Purpose:** Functional test via Modbus/TCP to validate router networking

**Modbus Protocol:**
- Function Code: 0x06 (Write Single Register)
- Target Register: 0x3247 (floodlight HMI on airport systems)
- Bit 0: Toggle on/off
- Port: 502 (standard Modbus/TCP)

**Configuration:**
- Host: Read from device_config.json (not hardcoded)
- Defaults to `template_gate_ip` from config
- Can be overridden by environment variable

**Test Sequence:**
1. Read current register value (Function Code 0x03)
2. Write 0x0001 (floodlight ON)
3. Wait 2 seconds
4. Write 0x0000 (floodlight OFF)
5. Repeat cycle 3 times

**Success Criteria:**
- "Bytes in received packet:" appears in output
- Valid Modbus response received
- Sequence number matches request
- Unit ID is 0x00

**Timeout:**
- Configured via `test_script_timeout` in device_config.json
- Default: 60 seconds
- Cannot hang indefinitely

### device_config.json - Configuration File

**Structure:**
```json
{
    "bbb_ip": "192.168.7.2",
    "bbb_user": "raj",
    "bbb_password": "Jetway",
    "router_temp_ip": "192.168.1.1",
    "router_fallback_ip": "192.168.81.1",
    "router_new_ip": "192.168.81.1",
    "router_new_user": "admin",
    "router_new_password": "Jetway@dm1n",
    "firmware_filename": "RUTX_R_00.07.22.3_WEBUI.bin",
    "template_gate_ip": "10.28.18.2",
    "template_netmask": "255.255.255.0",
    "ssh_timeout": 30,
    "test_script_timeout": 60
}
```

**Override via Environment Variables:**
```bash
export TR_BBB_IP="192.168.10.5"
export TR_ROUTER_NEW_PASSWORD="MyPassword123"
export TR_SSH_TIMEOUT="45"

# Only override if your hardware matches these values!
```

**⚠️ WARNING:** Environment variables should only override configuration if your actual hardware uses those IPs/passwords.

### Configuration Files (og_configs/ - 82 Files)

**Purpose:** Router system configuration files (never modified template)

**Key Files:**
- `network` - WAN/LAN IP, netmask, gateway, static routes
- `system` - Hostname, timezone
- `dhcp` - DHCP server configuration
- `firewall` - Iptables rules, port forwarding
- `modbus_server` - Modbus daemon settings
- `mosquitto` - MQTT broker config
- Plus 76 more configuration files

**All deployed to `/etc/config/` on router during Step 7**

### Excel Spreadsheets (*.xlsx)

**Purpose:** Device metadata and deployment tracking

**Columns (Header-Based Detection):**
- "PBB Gate" - Gate identifier
- "Jetway PN" - Router model
- "Gateway" - Default route
- "Netmask" - Subnet mask
- "Gate IP" - WAN-side IP (used by automation)
- "Serial" - Beaglebone serial
- "MAC Address" - Auto-populated during deployment
- "Timestamp" - Auto-populated (green=success, red=error)
- "Label" - Hyperlink to generated label file
- "Crash Report" - Hyperlink to crash log (if error)

**Files:**
- `GCN-PDX.xlsx` - Portland airport gates
- `JKC-SLC.xlsx` - Salt Lake City airport gates
- `IP_TEMPLATE.xlsx` - Template for new airports
- `oshkosh_log.xlsx` - Master deployment log

---

## CONFIGURATION MANAGEMENT

### Precedence System

**Three-level configuration precedence (lowest → highest):**

1. **DEFAULTS** (built-in fallbacks in code)
   ```python
   bbb_ip = "192.168.7.2"  # Code default if nothing else specifies
   ```

2. **device_config.json** (device-specific overrides)
   ```json
   {"bbb_ip": "192.168.10.5"}  // Overrides DEFAULTS
   ```

3. **Environment Variables** (runtime overrides)
   ```bash
   export TR_BBB_IP="192.168.20.5"  # Highest precedence
   ```

**Examples:**

**Scenario 1: Using Defaults**
- No `device_config.json` present
- No environment variables set
- Result: Use all DEFAULTS from code

**Scenario 2: Device-Specific Override**
- `device_config.json` has: `{"router_new_ip": "192.168.50.1"}`
- No environment variables set
- Result: Use new IP from file, other values from DEFAULTS

**Scenario 3: Temporary Runtime Override**
```bash
export TR_ROUTER_NEW_IP="192.168.99.1"
python prog_dev.py
# Result: Use env var IP, others from file or DEFAULTS
```

**⚠️ CRITICAL WARNING:** Only override environment variables if your actual hardware setup uses those IPs/passwords. Mismatched values will cause SSH connection failures or authentication rejections.

---

## ANALYSIS: What's Improved, What's Remaining

### ✅ FIXED (Sparse Branch)

1. **Hardcoded Values** → FIXED via device_config.py
   - ✅ No hardcoded IPs/passwords in source code
   - ✅ Configurable via JSON file
   - ✅ Environment variables allow temporary override

2. **SSH Connection Leak** → FIXED via SSHSession + ManagedShell
   - ✅ Single pooled connection per host
   - ✅ ManagedShell context manager auto-closes shells
   - ✅ Connection reused across multiple commands

3. **No SSH Timeout** → FIXED via SSHSession timeout enforcement
   - ✅ All SSH operations enforce timeout (default 30s)
   - ✅ Router/BBB hangs won't block entire script
   - ✅ SSHCommandTimeout exception on timeout

4. **No Connection Pooling** → FIXED via SSHSession.ensure_connected()
   - ✅ Single connection reused across steps
   - ✅ Automatic reconnection on transport failure
   - ✅ ~80 seconds per deployment saved

5. **Fragile MAC Parsing** → FIXED via mac_utils.py
   - ✅ Handles HWaddr, ether, link/ether formats
   - ✅ Fallback to bare regex if no label matches
   - ✅ Returns None on no match (no silent failure)

6. **Excel Column Hardcoding** → FIXED via excel_utils.py
   - ✅ Header-based column detection
   - ✅ Handles duplicate headers
   - ✅ Clear error if column missing
   - ✅ Validates IP format and subnet correctness

7. **Excel File Locking** → FIXED via open_workbook() context manager
   - ✅ File guaranteed to close even on error
   - ✅ No orphaned file locks

### ⚠️ STILL NEEDS WORK

1. **Interactive Shell Password Entry** (MEDIUM RISK)
   - **Issue:** Relies on exact prompt matching
   - **Risk:** Different firmware versions may have different prompts
   - **Status:** Works for 0.7.22.3 firmware
   - **Future Fix:** Use pexpect library or better pattern matching

2. **Environment Variable Override Safety** (MEDIUM)
   - **Issue:** No validation that overridden values match hardware
   - **Risk:** Operator sets wrong IP → connection fails
   - **Status:** Documented warning in place
   - **Future Fix:** Add validation checks or confirmation dialog

3. **Configuration Clarity** (LOW)
   - **Issue:** Three-level precedence can be confusing
   - **Status:** Documented with examples
   - **Future Fix:** Better error messages and warnings

---

## OPERATOR INSTRUCTIONS

### Prerequisites

**Hardware:**
- Teltonika RUTX08 router (or compatible model)
- Beaglebone Black at configured IP (default: 192.168.7.2)
- Network connectivity verified with ping

**Software:**
- Python dependencies installed
- Firmware file in folder: `RUTX_R_00.07.22.3_WEBUI.bin`
- Configuration files: `og_configs/` (94 files)
- Test file: `og_testfile/FloodLighToggle.py`

### Deployment

1. **Start ProgrammingWorkstation:** `python main.py`
2. **Hardware Verification:** Confirm wiring diagram
3. **Select Device:** Program → TR device
4. **Select Excel & Gate:** Auto-populate IP/netmask/gateway
5. **Scan QR Code:** Extract temporary router password
6. **Program:** Monitor ~7.5-minute automation
7. **Success:** Label generated, Excel updated, logs created

### Logs & Diagnostics

**Output:**
- Crash logs: `logs/crash_log_YYYY-MM-DD_HH-MM-SS.txt`
- Label files: `labels/label_YYYY-MM-DD_HH-MM-SS.txt`
- Excel updates: MAC address, timestamp, hyperlinks

**Troubleshooting:**
- Verify SSH connectivity: `ping 192.168.7.2` (BBB), `ping 192.168.1.1` (router)
- Check logs/ directory for crash details
- Verify device_config.json settings match hardware
- Ensure environment variables (if set) match hardware IPs/passwords

---

**Last Updated:** 2026-07-23  
**Firmware:** 0.7.22.3  
**Hardware:** Teltonika RUTX08  
**Status:** Production active with continued stability improvements

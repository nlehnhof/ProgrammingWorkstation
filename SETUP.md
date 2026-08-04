# SETUP.md — First-time setup on a new device

**Version:** 1.0 · **Branch:** `sparse` · **Last updated:** 2026-08-03

How to get the Programming Workstation running on a machine that has never had it
before. For day-to-day work inside the repo, see `documentation/INSTRUCTIONS.md`.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Windows 10/11 | The app is Windows-only: it uses PowerShell (`New-NetIPAddress`) and Win32 UAC APIs. |
| Python 3.13 | Built and tested against 3.13.7. Any 3.13.x should work. |
| An account in the local **Administrators** group | See §5 — the Digi IX20 flow cannot complete without it. |
| Git | To clone the repo. |

**Put the repo on a local disk.** Do not use a mapped network drive (`Z:\`) or a
UNC path. The app relaunches itself elevated, and elevated processes run in a
different logon session that does not inherit mapped drives — it would fail to
find its own files.

---

## 2. Clone and create the environment

`venv/` is **not** in version control, and a copied one would not work anyway
(`pyvenv.cfg` hardcodes the path of the Python that created it). Build a fresh one:

```
git clone <repo-url> ProgrammingWorkstation
cd ProgrammingWorkstation

python -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` covers both running the app and building the .exe (it includes
PyQt5, paramiko, openpyxl, ping3 and pyinstaller).

Two extras are **not** in `requirements.txt` — install them only if you need them:

```
.\venv\Scripts\python.exe -m pip install pytest    # to run the test suite
.\venv\Scripts\python.exe -m pip install Pillow    # only if resources/images/app_icon.ico is missing
```

---

## 3. Run from source

```
.\venv\Scripts\python.exe main.py
```

`main.py` pins its own working directory on startup, so it no longer matters
which folder you launch it from.

On launch you will get a **UAC prompt** — see §5.

---

## 4. Run the tests

Run as a module from the repository root. There is no `conftest.py` or
`pyproject.toml` putting the root on `sys.path`, so a bare `pytest` fails every
test with `ModuleNotFoundError: No module named 'resources'`.

```
.\venv\Scripts\python.exe -m pytest tests/
```

**All 66 tests should pass.** A failure here means something is genuinely wrong
with the environment or the code — there are no known-bad tests to ignore.

(Older notes described 6 failures and 2 collection errors. Those tests were
written against a shared utility layer that had not been implemented yet;
`e96074a` implemented it, and they pass.)

---

## 5. Administrator rights

Programming a Digi IX20 changes **this PC's** network adapter to a static IP
(`New-NetIPAddress`), which Windows only allows for an elevated process.

Windows cannot add privileges to a running process, so the app relaunches itself:
`resources/utilities/elevate.py` calls `ShellExecuteW(..., "runas", ...)`, which
raises the UAC prompt, starts an elevated copy, and exits the original.

What you see depends on the account:

- **Account is a local administrator** → a Yes/No consent prompt. Click Yes.
- **Account is a standard user** → Windows asks for administrator *credentials*,
  which someone must type on every run.
- **Elevation blocked by policy** (`ConsentPromptBehaviorUser = 0` on some
  corporate images) → no prompt at all; the call fails.

In the last two cases the app does not hang. It shows a dialog explaining the
consequence and lets you continue unelevated — everything works except the
**Switching static IP** milestone, which fails with a clear message.

To check whether an account is an administrator (the answer is *not* obvious from
a normal prompt, because UAC hands out a filtered token):

```
whoami /groups | findstr S-1-5-32-544
```

`BUILTIN\Administrators` listed as "Group used for deny only" means the account
**is** an administrator, just not currently elevated. If the line is absent
entirely, the account is a standard user.

---

## 6. Build the packaged .exe (optional)

```
.\venv\Scripts\python.exe -m PyInstaller core/main.spec --noconfirm
```

Output lands in `dist\ProgrammingWorkstation\`. **The build is not complete on
its own** — `devices/` and `core/devices.json` are deliberately left out of the
bundle and must be copied next to the .exe:

```
Copy-Item devices dist\ProgrammingWorkstation\devices -Recurse -Force
New-Item -ItemType Directory -Force dist\ProgrammingWorkstation\core
Copy-Item core\devices.json dist\ProgrammingWorkstation\core\devices.json -Force
```

Final layout:

```
dist\ProgrammingWorkstation\
    main.exe          <- requireAdministrator manifest (uac_admin=True)
    _internal\        <- bundled code and read-only assets
    devices\          <- external, writable, extensible
    core\devices.json
    logs\             <- created at runtime
```

`devices/` stays outside the bundle on purpose: adding a device must not require
a rebuild, and the app **writes** into that tree (Excel stamps, `router_labels/`,
`crash_logs/`). Bundled data is read-only and, in a onefile build, discarded when
the app exits — labels would silently vanish. For the same reason, do not convert
`core/main.spec` back to a onefile build.

`dist/` and `build/` are gitignored, so a packaged build does not travel with the
repo. Rebuild on each machine.

---

## 7. Verify the install

```
# 1. Devices are discovered
.\venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'.'); from resources.utilities.app_paths import app_root, registered_devices; print(app_root()); print(registered_devices())"
#    -> the repo path, then ['TR', 'digiIX20']

# 2. The hardware script loads (exit code 2 = its argument guard fired)
.\venv\Scripts\python.exe devices\digiIX20\digix20.py; echo $LASTEXITCODE

# 3. The GUI opens
.\venv\Scripts\python.exe main.py
```

In the app: **Program Device** → pick `digiIX20`. The right-hand **Status** panel
should list seven greyed-out milestones (Checking IP … Testing). If that panel is
empty, `devices/digiIX20/checklist.json` is missing.

---

## 8. Hardware / network prerequisites

The Digi flow assumes the standard bench layout — see
`devices/digiIX20/instructions.txt`:

1. IX20 connected to the Ethernet switch on **ETH2**
2. PC connected to the Ethernet switch
3. BeagleBone Black connected to the Ethernet switch
4. BeagleBone Black connected to the PC by USB

Defaults live in `devices/digiIX20/device_config.json` (BBB `192.168.7.2`, router
`192.168.2.1`, LAN interface `eth2`). Anything that differs per machine can be
overridden with `DIGIIX20_*` environment variables — e.g. `DIGIIX20_BBB_IP` —
without editing files.

---

## 9. Warnings

- **Never commit real credentials.** `core/devices.json` and
  `devices/*/device_config.json` hold plaintext passwords.
- **Excel files must be closed.** If an airport `.xlsx` is open in Excel, the
  workbook save fails; the app reports it and continues, but the run is not logged.
- **The PC's network adapter is modified during a run.** The script restores DHCP
  in a `finally` block, but if the app is force-killed mid-run the adapter can be
  left on a static IP. Fix: Settings → Network → adapter → IPv4 → Obtain
  automatically.
- **`find_pc_interface_index()` picks the first adapter on the router's subnet.**
  On a machine with a dock, USB-Ethernet dongle, or VPN adapters, confirm it chose
  the right NIC on the first run.

---

## 10. FAQ

**Q: `ModuleNotFoundError: No module named 'resources'` when running tests.**
A: You ran the bare `pytest` executable. Use `python -m pytest` from the repo root (§4).

**Q: The build fails with "Received icon image ... which exists but is not in the correct format".**
A: `resources/images/app_icon.ico` is missing. Note `python-logo.ico` is actually a
BMP with the wrong extension and cannot be used directly — install Pillow and
regenerate, or restore `app_icon.ico` from git.

**Q: The packaged .exe starts and immediately closes, with no window.**
A: Check `dist\ProgrammingWorkstation\logs\` — the crash log is written even when
there is no console.

**Q: The Program Device button stays disabled.**
A: All the cabling checkboxes must be ticked first; they are the pre-flight gate.
If no checkboxes appear at all, `devices/{device}/instructions.txt` is missing.

**Q: Can I add a device without rebuilding the .exe?**
A: Yes — that is why `devices/` sits outside the bundle. Drop in
`devices/{NAME}/` (with `prog_dev.py`, `instructions.txt`, and optionally
`checklist.json` and `device_config.json`) and add an entry to `core/devices.json`.

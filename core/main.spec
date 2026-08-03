# -*- mode: python ; coding: utf-8 -*-
#
# Build from the repo root:   pyinstaller core/main.spec
# Output:                     dist/ProgrammingWorkstation/
#
# After building, copy `devices/` and `core/devices.json` NEXT TO main.exe:
#
#     dist/ProgrammingWorkstation/
#         main.exe
#         _internal/          <- bundled code and read-only assets
#         devices/            <- NOT bundled, see below
#         core/devices.json
#         logs/               <- created at runtime
#
# devices/ is deliberately left out of the bundle for two reasons:
#   1. Extensibility -- adding a device must be a matter of dropping a folder
#      in and editing core/devices.json, not rebuilding the exe.
#   2. It is written to at runtime (Excel stamps, router_labels/, crash_logs/).
#      Bundled data is read-only and, in onefile mode, discarded on exit --
#      labels and crash logs would silently vanish.
# resources/utilities/app_paths.py resolves it beside the exe at runtime.
#
# This is a onedir build (EXE + COLLECT). Do not collapse it back to onefile:
# onefile unpacks to a temp directory that is wiped when the app closes.

import os

from PyInstaller.utils.hooks import collect_submodules

# This spec lives in core/ but the app it builds lives one level up. SPECPATH is
# injected by PyInstaller and is the only reliable anchor -- relative paths here
# would otherwise depend on which directory pyinstaller was invoked from.
ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))


a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        # Read-only assets only. connection_page.py loads router.jpg from here.
        (os.path.join(ROOT, 'resources', 'images'), os.path.join('resources', 'images')),
    ],
    # The device scripts are exec()'d and subprocessed rather than imported, so
    # PyInstaller's static analysis never sees these. Without them the frozen
    # app starts fine and then fails the moment it tries to program a device.
    hiddenimports=[
        'paramiko',
        'openpyxl',
        'ping3',
    ]
    # Whole package rather than a list: digix20.py pulls in wait_utils,
    # ssh_session, device_config and mac_utils, and a new device script will
    # reach for whichever utility it needs. Collecting the package means that
    # doesn't silently break the build.
    + collect_submodules('resources.utilities'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Neither is a runtime dependency: Pillow is a build-time tool (icon
    # conversion) and no live code uses tkinter. Keeps ~20 MB out of the build.
    excludes=['PIL', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Real multi-resolution .ico. NB: resources/images/python-logo.ico is
    # actually a BMP with an .ico extension -- PyInstaller rejects it unless
    # Pillow is installed to convert on the fly.
    icon=[os.path.join(ROOT, 'resources', 'images', 'app_icon.ico')],
    # Bakes requireAdministrator into the exe manifest so Windows elevates
    # before the app starts. The Digi IX20 flow reconfigures this PC's network
    # adapter (New-NetIPAddress), which needs administrator rights.
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ProgrammingWorkstation',
)

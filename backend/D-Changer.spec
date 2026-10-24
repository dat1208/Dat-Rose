# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the D-Changer backend.

Builds the Python engine (the Rose engine with analytics and party mode
removed, plus the updater, profiles and the local JSON API) as a standalone
executable. The Tauri UI starts this as a sidecar; it is not meant to be run
by itself.

Differences from Rose.spec:
  - no party mode (removed from D-Changer)
  - includes the new updater/, profiles/ and api modules
  - named dchanger-backend so the Tauri shell can find the sidecar
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

datas = []

# Assets folder (icons, images).
if Path('assets').is_dir() and os.listdir('assets'):
    datas += [('assets', 'assets')]
    print("[OK] Assets directory bundled")
else:
    print("[WARNING] Assets directory missing or empty")

# Injection tools: binaries vs data files.
injection_binaries = [
    'injection/tools/mod-tools.exe',
    'injection/tools/cslol-dll.dll',
]
# The LTK patcher pair is deliberately not bundled: updater/ltk_patcher.py
# fetches both files from a pinned LTK Manager commit and verifies them at
# startup, so shipping a copy would only go stale (the DLL has an end-of-life
# date) and could shadow the verified one.
injection_data_files = [
    'injection/tools/hashes.game.txt',
    'injection/tools/cslol-dll.stub',
]

binaries = []
for tool in injection_binaries:
    if Path(tool).exists():
        binaries.append((tool, 'injection/tools'))
    else:
        print(f"[WARNING] Missing injection binary: {tool}")

for tool in injection_data_files:
    if Path(tool).exists():
        datas += [(tool, 'injection/tools')]
    else:
        print(f"[WARNING] Missing injection data file: {tool}")

if Path('injection/mods_map.json').exists():
    datas += [('injection/mods_map.json', 'injection')]

try:
    pillow_datas = collect_data_files('PIL')
    if pillow_datas:
        datas += pillow_datas
except Exception as e:
    print(f"[WARNING] Could not collect Pillow data files: {e}")

# Pengu Loader runtime, minus runtime/local files.
pengu_loader_dir = Path('Pengu Loader')
PENGU_LOADER_EXCLUDED_ROOT_NAMES = {'config', 'datastore'}


def _pengu_path_excluded(rel_path: Path) -> bool:
    name = rel_path.name.lower()
    if rel_path.parts and rel_path.parts[0].lower() in PENGU_LOADER_EXCLUDED_ROOT_NAMES:
        return True
    return name.endswith('.log') or name.endswith('.log.old')


if pengu_loader_dir.is_dir():
    if not (pengu_loader_dir / 'Pengu Loader.exe').exists():
        raise RuntimeError("Pengu Loader.exe is missing. Run scripts/build_pengu_loader.py first.")
    bundled = 0
    for src in pengu_loader_dir.rglob('*'):
        if not src.is_file():
            continue
        rel = src.relative_to(pengu_loader_dir)
        if _pengu_path_excluded(rel):
            continue
        datas += [(str(src), str((Path('Pengu Loader') / rel).parent))]
        bundled += 1
    print(f"[OK] Pengu Loader bundled ({bundled} files)")
else:
    print("[WARNING] Pengu Loader directory not found")

hiddenimports = [
    # Entry point and its package
    'main',
    'main.setup',
    'main.setup.console',
    'main.setup.arguments',
    'main.setup.initialization',
    'main.core',
    'main.core.state',
    'main.core.lockfile',
    'main.core.signals',
    'main.core.initialization',
    'main.core.threads',
    'main.core.lcu_handler',
    'main.core.cleanup',
    'main.runtime',
    'main.runtime.loop',
    # Engine
    'injection',
    'injection.classic',
    'injection.core',
    'injection.core.injector',
    'injection.core.manager',
    'injection.game',
    'injection.game.game_monitor',
    'injection.game.game_detector',
    'injection.config',
    'injection.config.config_manager',
    'injection.config.threshold_manager',
    'injection.mods',
    'injection.mods.mod_manager',
    'injection.mods.zip_resolver',
    'injection.overlay',
    'injection.overlay.overlay_manager',
    'injection.overlay.process_manager',
    'injection.tools',
    'injection.tools.tools_manager',
    'injection.tools.patcher',
    'injection.loadingname',
    'injection.loadingname.loading_name',
    'lcu',
    'lcu.core',
    'lcu.core.client',
    'lcu.core.lcu_api',
    'lcu.core.lcu_connection',
    'lcu.core.lockfile',
    'lcu.data',
    'lcu.data.skin_scraper',
    'lcu.data.skin_cache',
    'lcu.data.types',
    'lcu.data.utils',
    'lcu.features',
    'lcu.features.lcu_properties',
    'lcu.features.lcu_skin_selection',
    'lcu.features.lcu_game_mode',
    'lcu.features.lcu_swiftplay',
    'pengu',
    'pengu.core',
    'pengu.core.skin_monitor',
    'pengu.core.websocket_server',
    'pengu.core.http_handler',
    'pengu.communication',
    'pengu.communication.message_handler',
    'pengu.communication.broadcaster',
    'pengu.processing',
    'pengu.processing.skin_processor',
    'pengu.processing.skin_mapping',
    'pengu.processing.flow_controller',
    'state',
    'state.core',
    'state.core.app_status',
    'state.core.shared_state',
    'threads',
    'threads.core',
    'threads.core.phase_thread',
    'threads.core.websocket_thread',
    'threads.core.lcu_monitor_thread',
    'threads.handlers',
    'threads.handlers.champ_thread',
    'threads.handlers.champion_lock_handler',
    'threads.handlers.game_mode_detector',
    'threads.handlers.injection_trigger',
    'threads.handlers.lobby_processor',
    'threads.handlers.phase_handler',
    'threads.handlers.swiftplay_handler',
    'threads.utilities',
    'threads.utilities.loadout_ticker',
    'threads.utilities.timer_manager',
    'threads.utilities.skin_name_resolver',
    'threads.websocket',
    'threads.websocket.websocket_connection',
    'threads.websocket.websocket_event_handler',
    'utils',
    'utils.core',
    'utils.core.logging',
    'utils.core.paths',
    'utils.core.utilities',
    'utils.core.validation',
    'utils.core.normalization',
    'utils.core.historic',
    'utils.core.modpkg',
    'utils.core.security',
    'utils.core.atomic_file',
    'utils.system',
    'utils.system.admin_utils',
    'utils.system.win32_base',
    'utils.system.window_utils',
    'utils.system.resolution_utils',
    'utils.download',
    'utils.download.repo_downloader',
    'utils.download.skin_downloader',
    'utils.download.smart_skin_downloader',
    'utils.download.hashes_downloader',
    'utils.download.hash_updater',
    'utils.integration',
    'utils.integration.tray_manager',
    'utils.integration.tray_settings',
    'utils.integration.pengu_loader',
    'utils.threading',
    'utils.threading.thread_manager',
    # In-client chroma UI (still part of the engine)
    'ui',
    'ui.core',
    'ui.core.user_interface',
    'ui.core.lifecycle_manager',
    'ui.chroma',
    'ui.chroma.panel',
    'ui.chroma.preview_manager',
    'ui.chroma.selector',
    'ui.chroma.ui',
    'ui.chroma.selection_handler',
    'ui.chroma.special_cases',
    'ui.handlers',
    'ui.handlers.historic_mode_handler',
    'ui.handlers.randomization_handler',
    'ui.handlers.skin_display_handler',
    # Launcher
    'launcher',
    'launcher.core',
    'launcher.core.launcher',
    'launcher.sequences',
    'launcher.sequences.hash_check_sequence',
    'launcher.sequences.patcher_sequence',
    'launcher.sequences.skin_sync_sequence',
    'launcher.ui',
    'launcher.ui.update_dialog',
    'launcher.update',
    'launcher.update.github_client',
    'launcher.update.update_downloader',
    'launcher.update.update_installer',
    'launcher.update.update_sequence',
    'launcher.updater',
    # D-Changer additions
    'api',
    'profiles',
    'updater',
    'updater.sources',
    'updater.verify',
    'updater.ltk_patcher',
    # Image processing
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL._imaging',
    'PIL._imagingtk',
    'PIL._tkinter_finder',
    # Networking
    'requests',
    'urllib3',
    'websocket',
    'websockets',
    'certifi',
    # Tray
    'pystray',
    'pystray._win32',
    # Other
    'psutil',
    'xxhash',
    'zstandard',
    'config',
]

excludes = [
    'matplotlib', 'pytest', 'setuptools', 'pip', 'wheel',
    'PySide2', 'PySide6',
    'easyocr', 'torch', 'torchvision', 'cv2', 'numpy', 'scipy', 'mss',
    'pandas', 'pyarrow', 'statsmodels', 'patsy', 'tables',
    'openpyxl', 'xlrd', 'xlwt', 'sqlalchemy',
    'IPython', 'jupyter', 'notebook', 'nbformat', 'nbconvert',
    'sphinx', 'docutils', 'jinja2', 'pygments', 'black', 'mypy',
    'dask', 'distributed', 'numba', 'llvmlite',
    'plotly', 'bokeh', 'panel', 'holoviews', 'pyviz_comms', 'markdown',
    'botocore', 'boto3', 's3transfer',
    'miniupnpc',
]


def filter_binaries(binaries_list):
    # The LTK patcher is not bundled (see injection_binaries above): the updater
    # fetches a pinned, verified pair at startup, so nothing is filtered here.
    return [(name, path, typ) for name, path, typ in binaries_list]


a = Analysis(
    ['main.py'],
    pathex=[str(Path.cwd())],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

a.binaries = filter_binaries(a.binaries)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='dchanger-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='dchanger-backend',
)

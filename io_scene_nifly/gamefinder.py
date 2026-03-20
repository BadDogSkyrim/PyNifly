"""Locate game install directories via Steam/Bethesda Launcher registry entries.

Only active when PYNIFLY_DEV_ROOT is set (development mode). The Blender
extensions program does not allow accessing third-party software installs,
so this is disabled in shipped builds.
"""

import os
import logging
from pathlib import Path

log = logging.getLogger("pynifly")

# Only perform game detection in dev mode.
_ENABLED = 'PYNIFLY_DEV_ROOT' in os.environ

try:
    import winreg
except ImportError:
    winreg = None
    _ENABLED = False


def _find_steam_libraries():
    """Return list of Steam library steamapps paths from the registry + libraryfolders.vdf."""
    if not winreg:
        return []

    steam_keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]

    steam_path = None
    for hive, key, value_name in steam_keys:
        try:
            with winreg.OpenKey(hive, key) as k:
                steam_path = Path(winreg.QueryValueEx(k, value_name)[0])
                break
        except OSError:
            continue

    if not steam_path:
        return []

    libraries = []
    library_file = steam_path / "steamapps" / "libraryfolders.vdf"
    if library_file.exists():
        try:
            with open(library_file, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if '"' in line and ":" in line:
                        try:
                            folder = line.split('"')[3].replace("\\\\", "\\")
                            if os.path.isdir(folder):
                                libraries.append(Path(folder) / "steamapps")
                        except (IndexError, Exception):
                            pass
        except OSError:
            pass

    # Always include default library
    libraries.append(steam_path / "steamapps")
    return libraries


def _find_steam_game(app_id, exe_name):
    """Find a Steam game by app ID, verifying the exe exists."""
    for lib in _find_steam_libraries():
        manifest = lib / f"appmanifest_{app_id}.acf"
        if manifest.exists():
            try:
                with open(manifest, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if '"installdir"' in line:
                            installdir = line.split('"')[-2]
                            game_path = lib / "common" / installdir
                            if (game_path / exe_name).exists():
                                return game_path
                            # Also try parent/common (some vdf layouts)
                            game_path2 = lib.parent / "common" / installdir
                            if (game_path2 / exe_name).exists():
                                return game_path2
            except OSError:
                pass
    return None


F4_APPID = "377160"
F4_EXE = "Fallout4.exe"
SKYRIM_LE_APPID = "72850"
SKYRIM_LE_EXE = "TESV.exe"
SKYRIM_SE_APPID = "489830"
SKYRIM_SE_EXE = "SkyrimSE.exe"


def find_fallout4():
    return _find_steam_game(F4_APPID, F4_EXE)


def find_skyrim():
    return _find_steam_game(SKYRIM_LE_APPID, SKYRIM_LE_EXE)


def find_skyrimse():
    """Find Skyrim SE via Steam or Bethesda Launcher registry."""
    result = _find_steam_game(SKYRIM_SE_APPID, SKYRIM_SE_EXE)
    if result:
        return result

    # Bethesda Launcher (rare)
    if not winreg:
        return None
    for key_path in [
        r"SOFTWARE\WOW6432Node\Bethesda Softworks\Skyrim Special Edition",
        r"SOFTWARE\Bethesda Softworks\Skyrim Special Edition",
    ]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                path = Path(winreg.QueryValueEx(key, "Installed Path")[0])
                if path.is_dir():
                    return path
        except (OSError, FileNotFoundError):
            pass
    return None


game_finders = {
    "FO4": find_fallout4,
    "SKYRIMSE": find_skyrimse,
    "SKYRIM": find_skyrim,
}


def find_game(game_name: str) -> Path | None:
    """Return the install directory for the named game, or None.

    Returns None immediately if not in dev mode (PYNIFLY_DEV_ROOT not set).
    """
    if not _ENABLED:
        return None
    finder = game_finders.get(game_name)
    if finder:
        return finder()
    return None

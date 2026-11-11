import winreg
import os
import json
from pathlib import Path

import logging
log = logging.getLogger("pynifly")

F4_APPID = "377160"   # Fallout 4 Steam AppID
F4_EXE = "Fallout4.exe"
SKYRIM_LE_APPID = "72850"
SKYRIM_LE_EXE = "TESV.exe"
SKYRIM_SE_APPID = "489830"


def _parse_steam_libraries(steam_path: Path) -> list[Path]:
    """Parse libraryfolders.vdf to find all Steam library paths."""
    library_file = steam_path / "steamapps" / "libraryfolders.vdf"
    libraries = []
    if library_file.exists():
        with open(library_file, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if '"' in line and ":" in line:
                    try:
                        folder = line.split('"')[3].replace("\\\\", "\\")
                        if os.path.isdir(folder):
                            libraries.append(Path(folder) / "steamapps")
                    except Exception:
                        pass
    libraries.append(steam_path / "steamapps")
    return libraries


def _find_steam_path() -> Path | None:
    """Find Steam installation path from registry."""
    for key_path in [r"Software\Valve\Steam", r"Software\WOW6432Node\Valve\Steam"]:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
                return Path(winreg.QueryValueEx(k, "SteamPath")[0])
        except OSError:
            continue

    for key_path in [r"SOFTWARE\WOW6432Node\Valve\Steam", r"SOFTWARE\Valve\Steam"]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as k:
                return Path(winreg.QueryValueEx(k, "InstallPath")[0])
        except OSError:
            continue

    return None


def _find_steam_game(appid: str, exe: str = None) -> Path | None:
    """Find a Steam game by app ID, optionally verifying an exe exists."""
    try:
        steam_path = _find_steam_path()
        if not steam_path:
            return None

        for lib in _parse_steam_libraries(steam_path):
            manifest = lib / f"appmanifest_{appid}.acf"
            if manifest.exists():
                with open(manifest, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if '"installdir"' in line:
                            installdir = line.split('"')[-2]
                            game_path = lib / "common" / installdir
                            if exe is None or (game_path / exe).exists():
                                return game_path
    except Exception:
        pass
    return None


def find_fallout4() -> Path | None:
    return _find_steam_game(F4_APPID, F4_EXE)


def find_skyrim() -> Path | None:
    return _find_steam_game(SKYRIM_LE_APPID, SKYRIM_LE_EXE)


def find_skyrimse() -> Path | None:
    result = _find_steam_game(SKYRIM_SE_APPID)
    if result:
        return result

    # Bethesda Launcher installs
    for key_path in [
        r"SOFTWARE\WOW6432Node\Bethesda Softworks\Skyrim Special Edition",
        r"SOFTWARE\Bethesda Softworks\Skyrim Special Edition",
    ]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                path = Path(winreg.QueryValueEx(key, "Installed Path")[0])
                if path.is_dir():
                    return path
        except OSError:
            pass

    return None


_game_finders = {
    "FO4": find_fallout4,
    "SKYRIMSE": find_skyrimse,
    "SKYRIM": find_skyrim,
}

# Steam install folder name (lower case) -> the game whose file formats it loads. The VR
# versions load their flat game's formats.
INSTALL_FOLDERS = {
    "skyrim": "SKYRIM",
    "skyrim special edition": "SKYRIMSE",
    "skyrimvr": "SKYRIMSE",
    "fallout 4": "FO4",
    "fallout 4 vr": "FO4",
    "fallout76": "FO76",
    "fallout new vegas": "FONV",
    "fallout 3": "FO3",
    "fallout 3 goty": "FO3",
    "starfield": "SF",
}

GAME_NAMES = {
    "SKYRIM": "Skyrim LE",
    "SKYRIMSE": "Skyrim SE",
    "FO4": "Fallout 4",
    "FO76": "Fallout 76",
    "FONV": "Fallout New Vegas",
    "FO3": "Fallout 3",
    "SF": "Starfield",
}


def game_of_path(filepath) -> str | None:
    """The game whose Data folder filepath is in ('SKYRIMSE', 'FO4' ...), or None.
    Known by the game's install folder name, or by where an installed game is."""
    p = Path(os.path.abspath(filepath))
    parts = [s.lower() for s in p.parts]
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] == "data" and parts[i-1] in INSTALL_FOLDERS:
            return INSTALL_FOLDERS[parts[i-1]]
    for game in _game_finders:
        data_dir = find_game(game)
        if data_dir:
            try:
                p.relative_to(Path(os.path.abspath(data_dir)))
                return game
            except ValueError:
                pass
    return None


def wrong_game_folder_warning(filepath, game) -> str | None:
    """The warning to give when a file written for game goes into another game's Data
    folder, or None when it doesn't."""
    folder_game = game_of_path(filepath)
    if folder_game is None or folder_game == game:
        return None
    have = GAME_NAMES.get(game, game)
    want = GAME_NAMES.get(folder_game, folder_game)
    return (f"Exported for {have} into a {want} game folder; {want} can't load it. "
            f"Choose {want} as the export's game to write it for {want}: {filepath}")

_cache = {}

def find_game(game_name: str) -> Path | None:
    """
    Returns the Data directory of the specified game, or None if not found.
    Results are cached so registry/filesystem lookups happen at most once per game.
    """
    if game_name not in _cache:
        finder = _game_finders.get(game_name)
        if finder:
            result = finder()
            if result:
                data_dir = result / "Data"
                if data_dir.is_dir():
                    log.info(f"Found {game_name} at {data_dir}")
                    _cache[game_name] = data_dir
                else:
                    _cache[game_name] = None
            else:
                _cache[game_name] = None
        else:
            _cache[game_name] = None
    return _cache[game_name]

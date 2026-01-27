import winreg
import os

import os
import json
import pathlib
import winreg

F4_APPID = "377160"   # Fallout 4 Steam AppID
F4_EXE = "Fallout4.exe"


def find_fallout4():
    return (
        find_fallout4_steam()
        or find_fallout4_xbox()
        or find_fallout4_epic()
    )


# ------------------------------------------------------------
# FO4: STEAM
# ------------------------------------------------------------
def find_fallout4_steam():
    try:
        steam_path = winreg.QueryValueEx(
            winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Valve\Steam"),
            "SteamPath"
        )[0]
    except OSError:
        return None

    steam_path = pathlib.Path(steam_path)
    library_file = steam_path / "steamapps" / "libraryfolders.vdf"
    if not library_file.exists():
        return None

    # Parse libraryfolders.vdf (simple heuristic parser)
    libraries = []
    with open(library_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if '"' in line and "\\" in line:
                parts = line.split('"')
                if len(parts) >= 4:
                    path = parts[3].replace("\\\\", "\\")
                    if os.path.isdir(path):
                        libraries.append(pathlib.Path(path) / "steamapps")

    # Always include default library
    libraries.append(steam_path / "steamapps")

    # Look for Fallout 4 manifest
    for lib in libraries:
        manifest = lib / f"appmanifest_{F4_APPID}.acf"
        if manifest.exists():
            with open(manifest, encoding="utf-8") as f:
                for line in f:
                    if '"installdir"' in line:
                        installdir = line.split('"')[-2]
                        game_path = lib.parent / "common" / installdir
                        if (game_path / F4_EXE).exists():
                            return str(game_path)
    return None


# ------------------------------------------------------------
# FO4: XBOX / GAME PASS
# ------------------------------------------------------------
def find_fallout4_xbox():
    try:
        # Newer Xbox installs use C:\XboxGames\Fallout 4\
        xbox_path = pathlib.Path("C:/XboxGames/Fallout 4")
        if (xbox_path / F4_EXE).exists():
            return str(xbox_path)

        # Older installs live in WindowsApps (restricted)
        wa = pathlib.Path("C:/Program Files/WindowsApps")
        if wa.exists():
            for entry in wa.iterdir():
                if entry.is_dir() and "Fallout4" in entry.name.replace(" ", ""):
                    exe = entry / F4_EXE
                    if exe.exists():
                        return str(entry)
    except Exception:
        pass

    return None


# ------------------------------------------------------------
# FO4: EPIC GAMES
# ------------------------------------------------------------
def find_fallout4_epic():
    # Epic default install path
    epic_default = pathlib.Path("C:/Program Files/Epic Games/Fallout4")
    if (epic_default / F4_EXE).exists():
        return str(epic_default)

    # Epic stores manifests in ProgramData
    manifest_dir = pathlib.Path("C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests")
    if manifest_dir.exists():
        for mf in manifest_dir.glob("*.item"):
            try:
                data = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue

            if data.get("DisplayName", "").lower() == "fallout 4":
                install_path = data.get("InstallLocation")
                if install_path and (pathlib.Path(install_path) / F4_EXE).exists():
                    return install_path

    return None


SKYRIM_LE_APPID = "72850"
SKYRIM_LE_EXE = "TESV.exe"


# ------------------------------------------------------------
# STEAM
# ------------------------------------------------------------
def find_skyrim():
    # Try both 32-bit and 64-bit registry locations
    steam_keys = [
        r"Software\Valve\Steam",
        r"Software\WOW6432Node\Valve\Steam",
    ]

    steam_path = None
    for key in steam_keys:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                steam_path = winreg.QueryValueEx(k, "SteamPath")[0]
                break
        except OSError:
            continue

    if not steam_path:
        return None

    steam_path = pathlib.Path(steam_path)
    library_file = steam_path / "steamapps" / "libraryfolders.vdf"

    if not library_file.exists():
        return None

    # Collect all Steam library paths
    libraries = []

    # Parse libraryfolders.vdf (simple heuristic parser)
    with open(library_file, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if '"' in line and ":" in line:
                try:
                    parts = line.split('"')
                    folder = parts[3].replace("\\\\", "\\")
                    if os.path.isdir(folder):
                        libraries.append(pathlib.Path(folder) / "steamapps")
                except Exception:
                    pass

    # Always include the default Steam library
    libraries.append(steam_path / "steamapps")

    # Search each library for Skyrim LE
    for lib in libraries:
        manifest = lib / f"appmanifest_{SKYRIM_LE_APPID}.acf"
        if manifest.exists():
            installdir = None
            with open(manifest, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if '"installdir"' in line:
                        installdir = line.split('"')[-2]
                        break

            if installdir:
                game_path = lib.parent / "common" / installdir
                if (game_path / SKYRIM_LE_EXE).exists():
                    return str(game_path)

    return None


def find_skyrimse() -> str | None:
    """
    Returns the installation directory of Skyrim Special Edition,
    or None if it cannot be found.
    """
    # 1. Steam installs (most common)
    steam_keys = [
        r"SOFTWARE\WOW6432Node\Valve\Steam",
        r"SOFTWARE\Valve\Steam"
    ]

    skyrim_appid = "489830"  # Skyrim Special Edition

    for key_path in steam_keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
                library_folders = [steam_path]

                # Parse libraryfolders.vdf for additional Steam libraries
                vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
                if os.path.exists(vdf_path):
                    with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if '"' in line and ":" in line:
                                try:
                                    folder = line.split('"')[3]
                                    if os.path.isdir(folder):
                                        library_folders.append(folder)
                                except Exception:
                                    pass

                # Search each library for Skyrim SE
                for lib in library_folders:
                    candidate = os.path.join(lib, "steamapps", "common", "Skyrim Special Edition")
                    if os.path.isdir(candidate):
                        return candidate

        except FileNotFoundError:
            pass

    # 2. Bethesda Launcher installs (rare)
    bethesda_keys = [
        r"SOFTWARE\WOW6432Node\Bethesda Softworks\Skyrim Special Edition",
        r"SOFTWARE\Bethesda Softworks\Skyrim Special Edition"
    ]

    for key_path in bethesda_keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                path, _ = winreg.QueryValueEx(key, "Installed Path")
                if os.path.isdir(path):
                    return path
        except FileNotFoundError:
            pass

    return None


game_finders = {
    "FO4": find_fallout4,
    "SKYRIMSE": find_skyrimse,
    "SKYRIM": find_skyrim,
}


def find_game(game_name: str) -> str | None:
    """
    Returns the installation directory of the specified game,
    or None if it cannot be found.
    """
    finder = game_finders.get(game_name)
    if finder:
        return finder()
    return None


# Example usage:
if __name__ == "__main__":
    path = find_game("SKYRIMSE")
    print("Skyrim SE found at:", path)
    
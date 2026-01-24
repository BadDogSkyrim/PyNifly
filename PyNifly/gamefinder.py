import winreg
import os

def find_game(game_name: str) -> str | None:
    """
    Returns the installation directory of Skyrim Special Edition,
    or None if it cannot be found.
    """
    if game_name != "SKYRIMSE": 
        return None

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


# Example usage:
if __name__ == "__main__":
    path = find_game("SKYRIMSE")
    print("Skyrim SE found at:", path)
    
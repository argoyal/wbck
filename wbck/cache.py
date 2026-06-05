import os
import json

_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".wbck")
_CACHE_FILE = os.path.join(_CACHE_DIR, "cache.json")


def _read():
    if not os.path.exists(_CACHE_FILE):
        return {}
    with open(_CACHE_FILE, "r") as f:
        return json.load(f)


def _write(data):
    os.makedirs(_CACHE_DIR, exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _scan_configs(folder):
    return sorted(f for f in os.listdir(folder) if f.endswith(".json"))


def _display_name(filename):
    return filename.replace("_config.json", "").replace(".json", "")


def set_config_folder(folder_path):
    folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(folder_path):
        raise SystemExit("error: '{}' is not a directory".format(folder_path))
    data = _read()
    data["config_folder"] = folder_path
    data.pop("active_config", None)
    _write(data)
    print("Config folder set to: {}".format(folder_path))
    configs = _scan_configs(folder_path)
    if configs:
        print("Available configs: {}".format(", ".join(_display_name(c) for c in configs)))
        print("Switch with: wbck cache use <name>")
    else:
        print("No config files found in that folder yet.")


def use_config(name):
    data = _read()
    folder = data.get("config_folder")
    if not folder:
        raise SystemExit("error: no config folder set. Run: wbck cache set --config-folder <path>")

    configs = _scan_configs(folder)
    match = next(
        (c for c in configs if c == name or _display_name(c) == name),
        None
    )
    if not match:
        available = ", ".join(_display_name(c) for c in configs) or "none"
        raise SystemExit("error: config '{}' not found. Available: {}".format(name, available))

    data["active_config"] = match
    _write(data)
    print("Switched to: {}".format(_display_name(match)))


def get_active_config_path():
    data = _read()
    folder = data.get("config_folder")
    active = data.get("active_config")
    if not folder or not active:
        return None
    return os.path.join(folder, active)


def has_config_folder():
    return bool(_read().get("config_folder"))


def get_config_path_by_name(name):
    data = _read()
    folder = data.get("config_folder")
    if not folder:
        raise SystemExit("error: no config folder set. Run: wbck cache set --config-folder <path>")
    configs = _scan_configs(folder)
    match = next(
        (c for c in configs if c == name or _display_name(c) == name),
        None
    )
    if not match:
        available = ", ".join(_display_name(c) for c in configs) or "none"
        raise SystemExit("error: config '{}' not found. Available: {}".format(name, available))
    return os.path.join(folder, match)


def get_all_config_paths():
    """Returns a list of all config file paths in the config folder."""
    data = _read()
    folder = data.get("config_folder")
    if not folder:
        raise SystemExit("error: no config folder set. Run: wbck cache set --config-folder <path>")
    configs = _scan_configs(folder)
    if not configs:
        raise SystemExit("error: no config files found in: {}".format(folder))
    return [os.path.join(folder, c) for c in configs]


def show_configs():
    data = _read()
    folder = data.get("config_folder")
    if not folder:
        print("No config folder set. Run: wbck cache set --config-folder <path>")
        return

    active = data.get("active_config")
    configs = _scan_configs(folder)

    if not configs:
        print("No config files found in: {}".format(folder))
        return

    print("Config folder: {}\n".format(folder))
    for cfg in configs:
        marker = "*" if cfg == active else " "
        print("  {} {}".format(marker, _display_name(cfg)))


def clear_cache():
    if not os.path.exists(_CACHE_FILE):
        print("Nothing to clear.")
        return
    os.remove(_CACHE_FILE)
    print("Cache cleared.")

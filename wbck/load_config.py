import json


def _is_enabled(_file):
    data = json.load(open(_file))

    return bool(data["enabled"])


def is_config_loadable(config_path):
    if not _is_enabled(config_path):
        raise SystemError("The configuration file is not enabled")

import os
import json


def _is_enabled(_file):
    data = json.load(open(_file))

    return bool(data["enabled"])


def get_enabled_configs(path):
    _files = os.listdir(path)
    _files = list(map(lambda x: "configs/{}".format(x), _files))
    _files = list(filter(lambda x: ".json" in x, _files))

    return list(filter(_is_enabled, _files))


def load_config():
    config_path = "configs"
    configs = get_enabled_configs(config_path)

    return list(map(lambda x: json.load(open(x)), configs))

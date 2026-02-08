# -*- coding: utf-8 -*-
"""
Load config from ProgramData (Windows) or current dir.
Config file: config.json with keys: token, host, port, log_dir, etc.
"""
import json
import os
import sys

VERSION = "1.0.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9060

if sys.platform == "win32":
    _program_data = os.environ.get("PROGRAMDATA", "C:\\ProgramData")
    DEFAULT_CONFIG_DIR = os.path.join(_program_data, "PosPrintingSuite", "Agent")
    LEGACY_CONFIG_DIR = os.path.join(_program_data, "PosPrintingSuite", "LocalPrinterAgent")
    DEFAULT_LOG_DIR = os.path.join(DEFAULT_CONFIG_DIR, "logs")
else:
    DEFAULT_CONFIG_DIR = os.path.expanduser("~/.local/share/pos_printing_suite_agent")
    LEGACY_CONFIG_DIR = None
    DEFAULT_LOG_DIR = os.path.join(DEFAULT_CONFIG_DIR, "logs")


def _resolve_config_path(config_path):
    if config_path:
        return config_path
    candidates = [os.path.join(DEFAULT_CONFIG_DIR, "config.json")]
    if LEGACY_CONFIG_DIR:
        candidates.append(os.path.join(LEGACY_CONFIG_DIR, "config.json"))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


def load_config(config_path=None):
    config_path = _resolve_config_path(config_path)
    config = {
        "token": "",
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "server_url": "",
        "ping_interval": 30,
        "config_dir": DEFAULT_CONFIG_DIR,
        "log_dir": DEFAULT_LOG_DIR,
    }
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            config.update(data)
            config["config_dir"] = os.path.dirname(config_path)
        except Exception as e:
            sys.stderr.write(f"Config load error: {e}\n")
    if config.get("config_dir"):
        config["log_dir"] = config.get("log_dir") or os.path.join(config["config_dir"], "logs")
    return config

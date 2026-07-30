"""Externalized configuration for device automation scripts.

Previously teltonika.py and prog_dev.py hardcoded the BBB/router IPs,
credentials, and firmware filename directly in source (see NEEDS IMPROVEMENT
#2 in DOCUMENTATION_OVERVIEW.md). Those values now live in a JSON file next
to each device's scripts (`device_config.json`) and can be overridden
per-environment with TR_* environment variables, without touching code.

Precedence (lowest to highest): DEFAULTS -> device_config.json -> env vars.
"""

import json
import os

DEFAULTS = {
    "bbb_ip": "192.168.7.2",
    "bbb_user": "raj",
    "bbb_password": "Jetway",
    "router_temp_ip": "192.168.1.1",
    "router_fallback_ip": "192.168.81.1",
    "router_new_ip": "192.168.81.1",
    "router_new_user": "admin",
    "router_new_password": "Jetway@dm1n",
    "firmware_filename": "RUTX_R_00.07.22.3_WEBUI.bin",
    "template_gate_ip": "10.28.18.2",
    "template_netmask": "255.255.255.0",
    "ssh_timeout": 30,
    "test_script_timeout": 60,
}

_NUMERIC_KEYS = {"ssh_timeout", "test_script_timeout"}

_ENV_PREFIX = "TR_"


def load_config(device_dir, filename="device_config.json", env_prefix=_ENV_PREFIX):
    """Load config for a device, layering file values and env vars over DEFAULTS.

    :param device_dir: folder containing the device's `device_config.json`
        (e.g. the directory teltonika.py lives in).
    """
    config = dict(DEFAULTS)

    config_path = os.path.join(device_dir, filename)
    if os.path.isfile(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            file_config = json.load(f)
        if not isinstance(file_config, dict):
            raise ValueError(
                f"{config_path} must contain a JSON object, got {type(file_config).__name__}"
            )
        config.update(file_config)

    for key in config:
        env_key = f"{env_prefix}{key.upper()}"
        if env_key in os.environ:
            value = os.environ[env_key]
            config[key] = int(value) if key in _NUMERIC_KEYS else value

    return config

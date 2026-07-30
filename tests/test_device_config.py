import json
import os

import pytest

from resources.utilities.device_config import DEFAULTS, load_config


def test_load_config_returns_defaults_when_no_file(tmp_path):
    config = load_config(str(tmp_path))
    assert config == DEFAULTS
    # must be a copy, not the live DEFAULTS dict
    config["bbb_ip"] = "changed"
    assert DEFAULTS["bbb_ip"] != "changed"


def test_load_config_file_overrides_defaults(tmp_path):
    (tmp_path / "device_config.json").write_text(
        json.dumps({"bbb_ip": "10.0.0.5", "ssh_timeout": 45}), encoding="utf-8"
    )
    config = load_config(str(tmp_path))
    assert config["bbb_ip"] == "10.0.0.5"
    assert config["ssh_timeout"] == 45
    # untouched keys keep their default
    assert config["bbb_user"] == DEFAULTS["bbb_user"]


def test_env_var_overrides_file_and_defaults(tmp_path, monkeypatch):
    (tmp_path / "device_config.json").write_text(
        json.dumps({"bbb_ip": "10.0.0.5"}), encoding="utf-8"
    )
    monkeypatch.setenv("TR_BBB_IP", "192.168.99.99")
    config = load_config(str(tmp_path))
    assert config["bbb_ip"] == "192.168.99.99"


def test_env_var_numeric_key_is_coerced_to_int(tmp_path, monkeypatch):
    monkeypatch.setenv("TR_SSH_TIMEOUT", "12")
    config = load_config(str(tmp_path))
    assert config["ssh_timeout"] == 12
    assert isinstance(config["ssh_timeout"], int)


def test_load_config_rejects_non_object_json(tmp_path):
    (tmp_path / "device_config.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(str(tmp_path))


def test_load_config_uses_custom_filename(tmp_path):
    (tmp_path / "other.json").write_text(json.dumps({"bbb_user": "someone"}), encoding="utf-8")
    config = load_config(str(tmp_path), filename="other.json")
    assert config["bbb_user"] == "someone"

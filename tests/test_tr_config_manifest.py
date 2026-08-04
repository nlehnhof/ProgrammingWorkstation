"""Guards the exact set of config files TR pushes to the router.

`teltonika.py` used to carry 82 hardcoded `sftp.put()` calls. Those became
`config_manifest.json`, and the risk in that change is subtle: `og_configs/`
holds 94 files, so anyone "simplifying" the manifest into a directory listing
would start overwriting 12 files of per-unit device state that provisioning is
supposed to leave alone.

These tests exist to make that regression loud.
"""

import json
import os

import pytest

DEVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "devices", "TR")
MANIFEST = os.path.join(DEVICE_DIR, "config_manifest.json")
OG_CONFIGS = os.path.join(DEVICE_DIR, "og_configs")

# Device-local state that must survive provisioning. Verbatim from what the
# original 82 put() calls did *not* include.
DELIBERATELY_SKIPPED = {
    "certificates",
    "log",
    "speedtest",
    "siteman",
    "siteman_devices",
    "siteman_groups",
    "siteman_network",
    "siteman_periodic_reboot",
    "siteman_ping_reboot",
    "siteman_ports",
    "siteman_vlan",
    "siteman_wireless",
}


@pytest.fixture
def manifest():
    with open(MANIFEST, "r", encoding="utf-8") as handle:
        return json.load(handle)["files"]


def test_manifest_still_holds_exactly_the_original_82_files(manifest):
    assert len(manifest) == 82


def test_manifest_has_no_duplicates(manifest):
    assert len(set(manifest)) == len(manifest)


def test_every_manifest_entry_exists_in_the_template_folder(manifest):
    available = set(os.listdir(OG_CONFIGS))
    missing = [name for name in manifest if name not in available]
    assert missing == [], f"manifest lists files not in og_configs/: {missing}"


def test_device_local_state_is_not_pushed(manifest):
    """The whole point of the manifest. Do not replace it with os.listdir()."""
    pushed = set(manifest)
    clobbered = sorted(DELIBERATELY_SKIPPED & pushed)
    assert clobbered == [], (
        f"these hold per-unit device state and must not be overwritten: {clobbered}"
    )


def test_skipped_set_matches_the_template_folder_exactly(manifest):
    """If og_configs/ gains a file, this fails until someone decides whether it
    should be pushed -- which is the decision that should never be implicit."""
    on_disk = {
        name for name in os.listdir(OG_CONFIGS)
        if os.path.isfile(os.path.join(OG_CONFIGS, name))
    }
    assert on_disk - set(manifest) == DELIBERATELY_SKIPPED

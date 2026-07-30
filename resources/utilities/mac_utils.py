"""Robust MAC address extraction from router/BBB shell output.

The old parser in teltonika.py only understood one exact format
(`"eth0" ... "HWaddr" ...`, the old net-tools `ifconfig` style) and broke
silently whenever the router's busybox/ifconfig build printed MACs in a
different style (e.g. "ether xx:xx..." or `ip link`'s "link/ether xx:xx...").
This module tries several known label formats before falling back to a bare
MAC-address regex anywhere in the text.
"""

import re

MAC_RE = re.compile(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})")
LABELS = ("HWaddr", "link/ether", "ether")


def extract_mac(text, interface=None):
    """Return the first MAC address found in `text`, or None.

    If `interface` is given (e.g. "eth0"), lines mentioning it (and the
    couple of lines that follow, since both `ifconfig` and `ip link` wrap
    the address) are searched first before falling back to the whole text.
    """
    if not text:
        return None

    lines = text.splitlines()

    if interface:
        for i, line in enumerate(lines):
            if interface in line:
                for candidate in lines[i : i + 3]:
                    mac = _search_labeled(candidate) or _search_bare(candidate)
                    if mac:
                        return mac

    for line in lines:
        mac = _search_labeled(line) or _search_bare(line)
        if mac:
            return mac

    return None


def _search_labeled(line):
    for label in LABELS:
        if label in line:
            after = line.split(label, 1)[1]
            match = MAC_RE.search(after)
            if match:
                return match.group(1).upper()
    return None


def _search_bare(line):
    match = MAC_RE.search(line)
    if match:
        return match.group(1).upper()
    return None

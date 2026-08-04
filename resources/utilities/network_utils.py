"""IP and subnet validation.

Kept deliberately tiny and dependency-free so device scripts, the Excel layer
and the GUI can all use the same answer to "is this address usable?".
"""

import ipaddress


def is_valid_ip(ip_string):
    """True if `ip_string` is a well-formed IP address."""
    try:
        ipaddress.ip_address(str(ip_string))
        return True
    except ValueError:
        return False


def validate_subnet(ip_str, netmask_str):
    """Check an address against its own netmask.

    Returns (ok, network) where `network` is CIDR text like "10.28.18.0/24",
    or (False, None) if either value is malformed. Returning the network
    rather than just a bool is what lets a caller say *which* subnet an
    address landed in when a gate sheet turns out to disagree with itself.
    """
    try:
        prefix_length = ipaddress.IPv4Network(f"0.0.0.0/{netmask_str}").prefixlen
        network = ipaddress.IPv4Network(f"{ip_str}/{prefix_length}", strict=False)
        return ipaddress.IPv4Address(str(ip_str)) in network, str(network)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
        return False, None


def prefix_length(netmask_str, default=24):
    """Prefix length for a dotted-decimal netmask, falling back to `default`.

    Device scripts need this to build "address/prefix" strings. Having it here
    stops each one from re-deriving it -- and from quietly assuming /24, which
    breaks on the 255.255.255.128 gates in the real sheets.
    """
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{netmask_str}").prefixlen
    except ValueError:
        return default

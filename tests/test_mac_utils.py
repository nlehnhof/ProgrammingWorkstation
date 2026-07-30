from resources.utilities.mac_utils import extract_mac


def test_extract_mac_old_ifconfig_hwaddr_style():
    output = (
        "eth0      Link encap:Ethernet  HWaddr 20:97:27:17:9E:4B\n"
        "          inet addr:10.28.18.2  Bcast:10.28.18.255  Mask:255.255.255.0\n"
    )
    assert extract_mac(output, interface="eth0") == "20:97:27:17:9E:4B"


def test_extract_mac_new_ifconfig_ether_style():
    output = (
        "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500\n"
        "        ether 20:97:27:17:9e:4b  txqueuelen 1000  (Ethernet)\n"
    )
    assert extract_mac(output, interface="eth0") == "20:97:27:17:9E:4B"


def test_extract_mac_ip_link_style():
    output = (
        "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP\n"
        "    link/ether 20:97:27:17:9e:4b brd ff:ff:ff:ff:ff:ff\n"
    )
    assert extract_mac(output, interface="eth0") == "20:97:27:17:9E:4B"


def test_extract_mac_ignores_other_interface_when_interface_specified():
    output = (
        "wlan0     Link encap:Ethernet  HWaddr 11:11:11:11:11:11\n"
        "eth0      Link encap:Ethernet  HWaddr 20:97:27:17:9E:4B\n"
    )
    assert extract_mac(output, interface="eth0") == "20:97:27:17:9E:4B"


def test_extract_mac_falls_back_to_bare_regex_when_no_label_matches():
    output = "some unexpected busybox output with 20:97:27:17:9e:4b embedded"
    assert extract_mac(output) == "20:97:27:17:9E:4B"


def test_extract_mac_returns_none_when_absent():
    assert extract_mac("no mac address here", interface="eth0") is None


def test_extract_mac_returns_none_for_empty_input():
    assert extract_mac("") is None
    assert extract_mac(None) is None

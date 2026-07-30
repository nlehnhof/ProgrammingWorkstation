from resources.utilities.network_utils import is_valid_ip, validate_subnet


def test_is_valid_ip_accepts_valid_ipv4():
    assert is_valid_ip("10.28.18.2") is True


def test_is_valid_ip_rejects_garbage():
    assert is_valid_ip("not-an-ip") is False
    assert is_valid_ip("10.13.16.2322") is False  # real bad data seen in GCN-PDX.xlsx


def test_validate_subnet_true_for_matching_network():
    valid, network = validate_subnet("10.28.18.2", "255.255.255.0")
    assert valid is True
    assert network == "10.28.18.0/24"


def test_validate_subnet_false_for_bad_netmask():
    valid, network = validate_subnet("10.28.18.2", "not-a-netmask")
    assert valid is False
    assert network is None

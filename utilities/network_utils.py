import os
import sys
import ipaddress

def is_valid_ip(ip_string):
    try:
        ipaddress.ip_address(ip_string)
        return True
    except ValueError:
        return False

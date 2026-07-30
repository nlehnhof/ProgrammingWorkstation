#SSH
import subprocess
import time
import paramiko
from pexpect.popen_spawn import PopenSpawn
import re
import threading

#GUI
import time
import ipaddress

import sys
import shutil
import os

# Short and Long Pause (sec)
s_pause = 1
l_pause = 2

if len(sys.argv) > 1:
    gate_ip = sys.argv[1]
    gate_netmask = sys.argv[2]
    gate_gateway = sys.argv[3]
    default_pass = sys.argv[4]
    print("Default pass... \n", flush=True)
    print(default_pass, flush=True)
else:
    gate_name = "UNKNOWN"
    print(gate_name, flush=True)
    sys.exit(0)
    
print(gate_ip, flush=True)
print(gate_netmask, flush=True)
print(gate_gateway, flush=True)
print(default_pass, flush=True)

# Global Variables
ssh_router_ip = '192.168.2.1'
ssh_router_user = 'admin'
router_new_pswd = 'Jetway@dm1n'
gate_subnet_prefix = "24"

ssh_bbb = paramiko.SSHClient()
ssh_router = paramiko.SSHClient()

################## SSH BBB ####################
def ssh_bbb_connect(bbb_ip: str = "192.168.7.2"):
    print("Connecting to BBB", flush=True)
    global ssh_bbb, sftp_bbb
    bbb_user = 'raj'
    bbb_pass = 'Jetway'

    ssh_bbb = paramiko.SSHClient()
    ssh_bbb.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_bbb.connect(bbb_ip, username=bbb_user, password=bbb_pass)
    print("Connected to BBB", flush=True)
    
    sftp_bbb = ssh_bbb.open_sftp()
    time.sleep(s_pause)

def ssh_bbb_run(cmd):
    global ssh_bbb
    stdin, stdout, stderr = ssh_bbb.exec_command(cmd)
    output = stdout.read().decode()
    error = stderr.read().decode()
    if output is not None:
        print("Output:\n", output, flush=True)
    if error is not None:
        print("Errors:\n", error, flush=True)
    return output

def ssh_bbb_upload(file, bbb_file):
    global sftp_bbb
    sftp_bbb.put(file, bbb_file)
    
def ssh_bbb_close():
    print("Closing Connection to BBB", flush=True)
    global ssh_bbb, sftp_bbb
    if sftp_bbb:
        sftp_bbb.close()
    if ssh_bbb:
        ssh_bbb.close()
    time.sleep(s_pause)
    print("Closed Connection to BBB", flush=True)
    
################## SSH IX Router  ####################

def ssh_router_connect():
    print("Connecting to Router")
    global ssh_router_ip, ssh_router, router_new_pswd, default_pass, sftp_router
    print(default_pass, flush=True)

    ssh_router = paramiko.SSHClient()
    ssh_router.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Using Default IP And Temp Password", flush=True)
    time.sleep(1)
    try:
        # IP: 192.168.2.1 U: admin P: whatever is on the router
        ssh_router.connect(ssh_router_ip, username=ssh_router_user, password=default_pass)
    except:
        try:
        # new_pswd  # U: admin P: Jetway@dm1n
            ssh_router.connect(ssh_router_ip, username=ssh_router_user, password=router_new_pswd)
        except:
            return print("Errors in Authentication", flush=True)
    
    print("Connected to Router", flush=True)
    
    shell = ssh_router.invoke_shell()
    time.sleep(s_pause)
    output = shell.recv(5000).decode()
    # sftp_router = ssh_router.open_sftp()
    time.sleep(s_pause)
    
    return output

def ssh_router_run(cmd):
    global ssh_router
    stdin, stdout, stderr = ssh_router.exec_command(cmd)
    output = stdout.read().decode()
    error = stdout.read().decode()
    if output is not None:
        print("Output:\n", output, flush=True)
    if error is not None:
        print("Errors:\n", error, flush=True)
    return output 

def ssh_router_close():
    print("Closing Connection to Router", flush=True)
    global ssh_router, sftp_router
    # if sftp_router:
    #     sftp_router.close()
    if ssh_router:
        ssh_router.close()
    time.sleep(s_pause)
    print("Closed Connection to Router", flush=True)

##############################################
######### START OF AUTOMATION FUNCTIONS ######
##############################################

## Change Router password to Jetway@dm1n
def change_password():
    global ssh_router, router_new_pswd, default_pass, ssh_router_ip
    print("Changing router password...", flush=True)

    ssh_router_connect()
    time.sleep(2)
    shell = ssh_router.invoke_shell()
    time.sleep(2)
    shell.send(b"a\n")
    time.sleep(2)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    shell.send(b"config\n")
    time.sleep(2)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(2)
    shell.send(b"auth user admin\n")
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(5)
    shell.send(f"password {router_new_pswd}\n".encode("utf-8"))
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(5)
    shell.send(b"save\n")
    time.sleep(4)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    if "Enter" in output:
        try:
            shell.send(default_pass.encode("utf-8"))
            time.sleep(5)
            output = shell.recv(4096).decode()
            print(output, flush=True)
        except Exception as e:
            print(f"Error updating password: {e}")

    # print("Password updated.", flush=True)

## Update IP address and gate_gateway : hard-coded netmask (/24)
def firmware_update():
    global ssh_bbb, ssh_router, ssh_router_ip, sftp_bbb
    bbb_ip = None

    print("Updating router firmware...", flush=True)
    # Connect to BBB with 192.168.7.2
    ssh_bbb_connect()
    shell = ssh_bbb.invoke_shell()
    time.sleep(2)
    
    # check ip addr show eth0 for 192.168.2....
    output = ssh_bbb_run("ip addr show eth0")
    pattern_ipv4 = r'\b192.\b168.\b2.\d{1,3}\b'
    ips = re.findall(pattern_ipv4, output)
    print(ips, flush=True)
    if len(ips) > 1 and ips[0] != "192.168.2.255":
        bbb_ip = ips[0]

    # if not, sudo dhclient -v eth0
    if len(ips) < 1:
        print("192.168.2 not in output", flush=True)
        try:
            ssh_bbb_run("sudo -n /sbin/dhclient -v eth0")
            time.sleep(10)
            output = ssh_bbb_run("ip addr show eth0")
            pattern_ipv4 = r'\b192.\b168.\b2.\d{1,3}\b'
            ips = re.findall(pattern_ipv4, output)
            print(ips, flush=True)
            if len(ips) > 1 and ips[0] != "192.168.2.255":
                bbb_ip = ips[0]
        except Exception as e:
            return print(f"Error: {e}")
        # confirm ip addr eth0
        if len(ips) < 1:
            return print("Failed to find ip addr", flush=True)
        bbb_ip = ips[0] if ips[0] != "192.168.2.1" else None
        print(bbb_ip, flush=True)
        if bbb_ip is None:
            return print("Failed to get BBB IP correct.", flush=True)

    # Enter PC terminal
    # PC to BBB transfer file
    # scp ".devices\digiIX20\firmware\01_LATEST_LTS_IX20-25.2.56.67-asof-2026APR14.bin" raj@{BBB_ip}:/home/raj/
    try:
        sftp_bbb.put('./devices/digiIX20/firmware/01_LATEST_LTS_IX20-25.2.56.67-asof-2026APR14.bin', '/home/raj/ix20-25.2.56-firmware.bin')
        print("Firmware copied to BBB", flush=True)
    except Exception as e:
        return print(f"Error Here: {e}")
    
    # close BBB
    ssh_bbb_close()

    # Connect to router
    ssh_router_connect()

    # Router pulls file from BBB
    shell = ssh_router.invoke_shell()
    time.sleep(1)
    output = shell.recv(4096).decode()
    print(output, flush=True)

    # scp host 192.168.2.183 user raj remote /home/raj/01_LATEST_LTS_IX20-25.2.56.67-asof-2026APR14.bin local /tmp/IX20-25.2.56.67-firmware.bin to local
    shell.send(b"a\n")
    time.sleep(1)
    shell.send(f"scp host {bbb_ip} user raj remote /home/raj/01_LATEST_LTS_IX20-25.2.56.67-asof-2026APR14.bin local /tmp/IX20-25.2.56.67-firmware.bin to local\n".encode())
    time.sleep(2)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(2)
    shell.send("Jetway\n".encode())
    time.sleep(12)

    # confirm with ls \tmp\ that the firmware file is there
    shell.send(b"ls /tmp/\n")
    time.sleep(1)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    if "IX20-25.2.56.67-firmware.bin" not in output:
        return print("Failed to copy over firmware file.", flush=True)

    # system firmware update file /tmp/IX20-25.2.56.67-firmware.bin
    shell.send(b"system firmware update file /tmp/IX20-25.2.56.67-firmware.bin\n")
    time.sleep(120)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    if "Firmware update completed" not in output:
        return print("Failed to update firmware", flush=True)
    
    # reboot
    shell.send(b"reboot\n")
    time.sleep(30)
    print("Firmware updated; reboot complete. Move to configurations.", flush=True)

def configure():
    print("Configuring router...", flush=True)
    
    global ssh_bbb, ssh_router, gate_ip, sftp_bbb, ssh_router_ip, gate_subnet_prefix

    # Enter BBB
    ssh_bbb_connect()
    time.sleep(1)

    # Confirm IP
    shell = ssh_bbb.invoke_shell()
    time.sleep(1)
    
    # check ip addr show eth0 for 192.168.2....
    output = ssh_bbb_run("ip addr show eth0")
    pattern_ipv4 = r'\b192.\b168.\b2.\d{1,3}\b'
    ips = re.findall(pattern_ipv4, output)
    print(ips, flush=True)
    if len(ips) > 1 and ips[0] != "192.168.2.255":
        bbb_ip = ips[0]

    # if not, sudo dhclient -v eth0
    if len(ips) < 1:
        print("192.168.2 not in output", flush=True)
        try:
            ssh_bbb_run("sudo -n /sbin/dhclient -v eth0")
            time.sleep(10)
            output = ssh_bbb_run("ip addr show eth0")
            pattern_ipv4 = r'\b192.\b168.\b2.\d{1,3}\b'
            ips = re.findall(pattern_ipv4, output)
            print(ips, flush=True)
            if len(ips) > 1 and ips[0] != "192.168.2.255":
                bbb_ip = ips[0]
        except Exception as e:
            return print(f"Error: {e}")
        # confirm ip addr eth0
        if len(ips) < 1:
            return print("Failed to find ip addr", flush=True)
        bbb_ip = ips[0] if ips[0] != "192.168.2.1" else None
        print(bbb_ip, flush=True)
        if bbb_ip is None:
            return print("Failed to get BBB IP correct.", flush=True)    

    # Copy config file from pc to bbb (sftp)
        # Enter PC terminal
    # PC to BBB transfer file
    try:
        sftp_bbb.put('./devices/digiIX20/configs/99-CONFIG-BMS-asof-2026APR14-Digi-IX20-25.2.56.67.bin', '/home/raj/99-configs-2026-07-29.bin')
        print("Firmware copied to BBB", flush=True)
    except Exception as e:
        return print(f"Error Here: {e}")
    
    # exit bbb
    ssh_bbb_close()

    # Connect to router
    ssh_router_connect()

    # Router pulls file from BBB
    shell = ssh_router.invoke_shell()
    time.sleep(1)
    output = shell.recv(4096).decode()
    print(output, flush=True)

    # copy file to router from bbb
    shell.send(b"a\n")
    time.sleep(1)
    shell.send(f"scp host {bbb_ip} user raj remote /home/raj/99-configs-2026-07-29.bin local /tmp/IX20-99-configs.bin to local\n".encode()) # type:ignore
    time.sleep(2)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(2)
    shell.send("Jetway\n".encode())
    time.sleep(60)

    # confirm with ls \tmp\ that the config file is there
    shell.send(b"ls /tmp/\n")
    time.sleep(1)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    if "IX20-99-configs.bin" not in output:
        return print("Failed to copy over configuration file.", flush=True)
    
    # upload config to router
    # system restore PATH/to/config/file
    shell.send(b"system restore /tmp/IX20-99-configs.bin\n")
    print("1 minute remaining...", flush=True)
    time.sleep(90)
    output = shell.recv(4096).decode()
    print(output, flush=True)

    # reboot
    shell.send(b"reboot\n")
    time.sleep(1)
    output = shell.recv(4096).decode()
    print(output, flush=True)

    # wait
    print("2 minutes remaining in reboot...", flush=True)
    time.sleep(60)
    print("1 minute remaining...", flush=True)
    time.sleep(60)

    # Find current Ethernet interface name and index
    # cmd_find = (
    #     "powershell -Command \""
    #     f"$gw='{ssh_router_ip}'; "
    #     "Get-NetIPConfiguration | "
    #     "Where-Object {$_.IPv4DefaultGateway -and $_.IPv4DefaultGateway.NextHop -eq $gw} | "
    #     "Select -First 1 -ExpandProperty InterfaceIndex"
    #     "\"\n"
    # )
    # shell.send(cmd_find.encode())
    # time.sleep(1)
    # output = shell.recv(4096).decode()
    
    # match = re.search(r"\d+", output)
    # if not match:
    #     raise Exception("Could not find interface index")
    
    # iface_index = match.group(0)
    # print("Interface Index:", iface_index)

    # # remove existing IPs (DHCP cleanup)
    # cmd_remove = (
    #     "powershell -Command \""
    #     f"Get-NetIPAddress -InterfaceIndex {iface_index} | "
    #     "Remove-NetIPAddress -Confirm:$false"
    #     "\"\n"
    # )

    # shell.send(cmd_remove.encode())
    # time.sleep(1)

    # # Set static IP
    # cmd_set = (
    #     "powershell -Command \""
    #     f"New-NetIPAddress -InterfaceIndex {iface_index} "
    #     f"-IPAddress {gate_ip}"
    #     f"-PrefixLength {gate_subnet_prefix}"
    #     f"-DefaultGateway {gate_gateway}"
    #     "\"\n"
    # )

    # shell.send(cmd_set.encode())
    # time.sleep(1)

    # # confirm static ip addr
    # shell.send(b"ipconfig\n")
    # time.sleep(1)
    # output = shell.recv(8192).decode()

    # if gate_ip not in output:
    #     return print("Failed to change static ip addr")

    # print("Continuing on... ", flush=True)

    # # connect to router with new ip addr (192.168.81.5 ; AAAaaa111!!!)
    # ssh_router_ip = "192.168.81.5"
    # router_new_pswd = "AAAaaa111!!!"
    # ssh_router_connect()
    # time.sleep(1)

    # # modify public ip address : config network interface eth1 ipv4
    # shell.send(b"a\n")
    # time.sleep(1)
    # shell.send(b"config\n")
    # time.sleep(1)
    # shell.send(b"network interface eth1 ipv4\n")
    # time.sleep(1)
    # shell.send(f"address {gate_ip}/24".encode())
    # time.sleep(2)
    # shell.send(b"save")
    # time.sleep(1)

    # # check firewall rules
    # shell.send(b"config\n")
    # time.sleep(1)
    # # config firewall dnat
    # shell.send(b"firewall dnat\n")
    # time.sleep(1)
    # # show
    # shell.send(b"show\n")
    # time.sleep(1)
    # output = shell.recv(4096).decode()
    # print(output, flush=True)

    # # read output for port 44818 and label ENIP
    # modbus = False
    # enip = False
    # if "modbus" in output:
    #     modbus = True
    # if "ENIP" in output:
    #     enip = True
    
    # if not modbus and not enip:
    #     return print("Wrong rules", flush=True)
    
    # shell.send(b"save\n")
    # time.sleep(1)
    # shell.send(b"exit\n")
    # time.sleep(1)
    # shell.send(b"q\n")
    # time.sleep(1)

    # ssh_router_close()
    # time.sleep(1)

    return print("Router configured correctly.", flush=True)

print("Starting... ", flush=True)
firmware_update()
# change_password() # change to Jetway@dm1n
configure() # configuration changes router to 192.168.81.5 ; AAAaaa111!!!
print("Done.", flush=True)

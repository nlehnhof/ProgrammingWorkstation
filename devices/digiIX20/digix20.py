#SSH
import subprocess
import time
import paramiko
import pexpect
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
    error = stdout.read().decode()
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
    global ssh_router, router_new_pswd, default_pass
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
            print("Errors in Authentication", flush=True)
    
    print("Connected to Router", flush=True)
    
    shell = ssh_router.invoke_shell()
    time.sleep(s_pause)
    output = shell.recv(5000).decode()
    print("Router Login Output:\n", output, flush=True)
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
    global ssh_router, router_new_pswd, default_pass
    print("Changing router password...", flush=True)

    ssh_router_connect()
    time.sleep(1)

    shell = ssh_router.invoke_shell()

    shell.send(b"a\n")
    time.sleep(1)
    shell.send(b"config\n")
    time.sleep(1)
    shell.send(b"auth user admin\n")
    time.sleep(2)
    shell.send(f"password {router_new_pswd}\n".encode("utf-8"))
    time.sleep(2)
    shell.send(b"save\n")
    output = shell.recv(4096).decode()
    print(output, flush=True)
    if "Enter" in output:
        try:
            shell.send(default_pass.encode("utf-8"))
            time.sleep(2)
            output = shell.recv(4096).decode()
            print(output, flush=True)
        except Exception as e:
            print(f"Error updating password: {e}")

    print("Password updated.", flush=True)

## Update IP address and gate_gateway : hard-coded netmask (/24)
def firmware_update():
    global ssh_bbb, ssh_router, ssh_router_ip

    print("Updating router firmware...", flush=True)
    # Connect to BBB with 192.168.7.2
    ssh_bbb_connect()
    shell = ssh_bbb.invoke_shell()
    time.sleep(2)
    
    # check ip addr show eth0 for 192.168.2....
    ssh_bbb_run("ip addr show eth0")
    time.sleep(2)
    output2 = shell.recv(4096).decode()
    print(output2, flush=True)
    time.sleep(2)
    match = re.search(r"inet (192\.168\.2\.\d{1,3})/", output2)
    if match:
        ip = match.group(1)
        print(ip, flush=True)

    return print("Match: ", match, flush=True)

    # if not, sudo dhclient -v eth0
    if len(ips) < 1:
        print("192.168.2 not in output", flush=True)
        # ssh_bbb_run("sudo dhclient -v eth0")
        # time.sleep(2)
        # output = shell.recv(4096).decode()
        # print(output, flush=True)
        # confirm ip addr eth0
        ips2 = re.findall(r"192\.168\.2\.\d{1,3}\\24", output) 
        print(ips2, flush=True)
        if len(ips2) < 1:
            return print("Failed to find ip addr", flush=True)
        bbb_ip = ips[0] if ips[0] != "192.168.2.1" else None
        if bbb_ip is None:
            return print("Failed to get BBB IP correct.", flush=True)
        bbb_ip = bbb_ip.split(f"\\")

    # close BBB
    ssh_bbb_close()

    # Enter PC terminal
    # PC to BBB transfer file
    # scp ".devices\digiIX20\firmware\01_LATEST_LTS_IX20-25.2.56.67-asof-2026APR14.bin" raj@{BBB_ip}:/home/raj/
    print("Trying pexpect...", flush=True)
    try:
        child = pexpect.spawn('scp ./devices/digiIX20/firmware/01_LATEST_LTS_IX20-25.2.56.67-asof-2026APR14.bin raj@{BBB_ip}:/home/raj/')
        child.expect('password:')
        child.sendline('Jetway')
        child.expect(pexpect.EOF)
        print("File copied", flush=True)
    except pexpect.TIMEOUT:
        return print("Timeout problem")
    except pexpect.ExceptionPexpect as e:
        return print(f"Error: {e}")
    except Exception as e:
        return print(f"Error: {e}")

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
    shell.send("scp host {bbb_ip} user raj remote /home/raj/01_LATEST_LTS_IX20-25.2.56.67-asof-2026APR14.bin local /tmp/IX20-25.2.56.67-firmware.bin to local\n".encode())
    time.sleep(2)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(2)

    # confirm with ls \tmp\ that the firmware file is there
    shell.send(b"ls /tmp/\n")
    time.sleep(1)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    if "IX20-25.2.56.67-firmware.bin" not in output:
        return print("Failed to copy over firmware file.", flush=True)

    # system firmware update file /tmp/IX20-25.2.56.67-firmware.bin
    shell.send(b"system firmware update file /tmp/IX20-25.2.56.67-firmware.bin\n")
    time.sleep(15)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    if "Firmware update completed" not in output:
        return print("Failed to update firmware", flush=True)
    
    # reboot
    shell.send(b"reboot\n")
    time.sleep(30)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    if "closed" in output:
        return print("Firmware updated; reboot complete. Move to configurations.", flush=True)

def configure():
    global ssh_router, ssh_bbb, gate_ip, gate_gateway

    print("Configuring router...", flush=True)

    ssh_router_connect()
    shell = ssh_router.invoke_shell()
    time.sleep(2)
    if shell.recv_ready():
        output = shell.recv(4096).decode("utf-8", errors = "ignore")

    shell.send(b"a\n")
    time.sleep(1)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(3)
    shell.send(b"config\n")
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(2)
    shell.send(b"network interface eth2 ipv4\n")
    time.sleep(2)
    shell.send(b"address\n")
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(1)
    print(gate_ip, flush=True)
    shell.send(f"address {gate_ip}/24\n".encode("utf-8"))
    time.sleep(2)
    output = shell.recv(4096).decode()
    print(output, flush=True)

    if gate_gateway is not None:
        shell.send(f"gateway {gate_gateway}\n".encode("utf-8"))
        time.sleep(1)

    shell.send(b"save\n")
    time.sleep(3)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    shell.send(b"exit\n")
    time.sleep(3)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    shell.send(b"q\n")
    time.sleep(1)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    time.sleep(2)

    shell.send(b"ipconfig /release\n")
    time.sleep(4)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    shell.send(b"ipconfig /renew\n")
    time.sleep(4)
    output = shell.recv(4096).decode()
    print(output, flush=True)
    print("Router configuration is now complete.", flush=True)
    shell.close()
    time.sleep(1)

print("Starting... ", flush=True)
firmware_update()
print("Done.", flush=True)

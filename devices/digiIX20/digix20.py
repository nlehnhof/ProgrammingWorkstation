#SSH
import subprocess
import time
import paramiko
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
    
# Global Variables
ssh_router_ip = '192.168.2.1'
ssh_router_user = 'admin'
router_new_pswd = 'Jetway@dm1n'
password = False

################## SSH BBB ####################
def ssh_bbb_connect():
    print("Connecting to BBB", flush=True)
    global ssh_bbb, sftp_bbb
    bbb_ip = '192.168.7.2'
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
    global ssh_router, sftp_router, router_new_pswd, default_pass
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
    
    sftp_router = ssh_router.open_sftp()
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

def ssh_router_upload(file, router_file):
    global sftp_router
    sftp_router.put(file, router_file)
    
def ssh_router_close():
    print("Closing Connection to Router", flush=True)
    global ssh_router, sftp_router
    if sftp_router:
        sftp_router.close()
    if ssh_router:
        ssh_router.close()
    time.sleep(s_pause)
    print("Closed Connection to Router", flush=True)

##############################################
######### START OF AUTOMATION SCRIPT #########
##############################################

ssh_router_connect()
time.sleep(1)

shell = ssh_router.invoke_shell()

ssh_router_run("a\n")
time.sleep(1)
ssh_router_run("config\n")
time.sleep(1)
ssh_router_run("network interface eth2 ipv4\n")
time.sleep(2)
ssh_router_run("address\n")
time.sleep(1)
output = shell.recv(4096).decode()
print(output, flush=True)

ssh_router_run(f"address {gate_ip}/24\n")
time.sleep(1)
if gate_gateway is not None:
    ssh_router_run(f"gateway {gate_gateway}\n")
    time.sleep(1)

ssh_router_run("save\n")
time.sleep(1)
ssh_router_run("exit\n")
time.sleep(1)
ssh_router_run("q\n")

shell.send(b"ipconfig /release\n")
time.sleep(2)
shell.send(b"ipconfig /renew\n")
time.sleep(4)
print("Router configuration is now complete.", flush=True)
ssh_router_close()
shell.close()
time.sleep(1)

## Change Router password to Jetway@dm1n
if password == True:
    ssh_router_connect()
    time.sleep(1)

    shell = ssh_router.invoke_shell()

    ssh_router_run("a\n")
    time.sleep(1)
    ssh_router_run("config\n")
    time.sleep(1)
    ssh_router_run("auth user admin\n")
    time.sleep(2)
    ssh_router_run(f"password {router_new_pswd}\n")
    time.sleep(2)
    ssh_router_run("save\n")
    time.sleep(1)
    print("Password updated.", flush=True)
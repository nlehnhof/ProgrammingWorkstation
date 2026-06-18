#SSH
import subprocess
import time
import paramiko
from ping3 import ping
import re
import threading

#GUI
# import tkinter as tk
# from tkinter import messagebox
import time
import ipaddress

import sys
import shutil
import os

if len(sys.argv) > 1:
    gate_ip = sys.argv[1]
    gate_netmask = sys.argv[2]
    gate_gateway = sys.argv[3]
    temp_pass = sys.argv[4]
    # my_pass = "Jetway@dm1n"
    # temp_pass = 'y2E8LsZq'
else:
    gate_name = "UNKNOWN"
    sys.exit(1)
    
#print(f"Running Automation for: {gate_ip}", flush=True)

# Short and Long Pause (sec)
s_pause = 1
l_pause = 2

# Global Variables
# ssh_bbb = None
# sftp_bbb = None
# ssh_router = None
# sftp_router = None

# Passwords
new_pswd = "Jetway@dm1n"

################# INFO ####################
#Teltonika router intially had 0.7.11.3 Firmware Version
# Script finishes in 8 mins
        
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
    
################## SSH Router  ####################

def ssh_router_connect(num, admin_num):
    print("Connecting to Router")
    global ssh_router, sftp_router, temp_pass, new_pswd
    router_ip = '192.168.81.1'
    if admin_num == "admin":
        router_user = 'admin'
    else:
        router_user = 'root'
    router_temp_pass = temp_pass
    router_new_pass = new_pswd

    ssh_router = paramiko.SSHClient()
    ssh_router.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if num == "temp":
        print("Using Default IP And Temp Password", flush=True)
        router_ip = "192.168.1.1"
        print(router_ip, flush=True)
        print(router_user, flush=True)
        print(router_temp_pass, flush=True)
        time.sleep(1)
        try:
            # IP: 192.168.1.1 U: root P: y2E8LsZq
            ssh_router.connect(router_ip, username=router_user, password=router_temp_pass)
        except:
            try:
                router_ip = "192.168.81.1"
                # temp_pass = new_pswd  # U: admin P: Jetway@dm1n
                ssh_router.connect(router_ip, username=router_user, password=new_pswd)
            except:
                print("Errors in Authentication", flush=True)
    else:
        # only not use "temp" when we've already updated the backup to the new ip addr
        router_ip = "192.168.81.1"
        router_user = 'admin'
        print("Using New Password", flush=True)
        print(router_user, flush=True)
        print(router_new_pass, flush=True)
        time.sleep(1)
        ssh_router.connect(router_ip, username=router_user, password=router_new_pass)
    
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

######### CHECK IF ROUTER IS ALREADY PROGRAMMED #########
"""
- SSH into BBB
- ssh_bbb_run("ip addr show eth0")
- read output
- if /24 scope global eth0 in output
- return the ip address it's already written to
- else, continue with programming the router
"""
print("Checking if router is already programmed...", flush=True)
ssh_bbb_connect()
time.sleep(s_pause)
output = ssh_bbb_run("ip addr show eth0")
time.sleep(s_pause)

# Regex for IPV4
pattern_ipv4 = r'\b10.\d{1,3}\.\d{1,3}.123\b'
ipv4s = re.findall(pattern_ipv4, output)
print(ipv4s, flush=True)
for addr in ipv4s:
    if addr != "10.28.18.123":
        print(f"Router already programmed to IP:{addr}", flush=True)
        sys.exit(0)

""" 
-Firmware Installation
-Static IP Setup from BBB to router
-1st Login into Router and temp pass change
-Config Files Updates
-Save and Reboot

"""
print("STARTING ROUTER SETUP", flush=True)
time.sleep(s_pause)

ssh_router_connect("temp", "root")

################ Copy Configs from Backup #################

print("Copying Configs from Backup Folder", flush=True)
time.sleep(s_pause)

source_folder = 'og_configs'
destination_folder = 'configs'

os.makedirs(destination_folder, exist_ok=True)

for filename in os.listdir(source_folder):
    source_path = os.path.join(source_folder, filename)
    destination_path = os.path.join(destination_folder)
    
    if os.path.isfile(source_path):
        shutil.copy2(source_path, destination_path)

################ Update Public Gate IP ################# UPDATED

old_ip = "10.28.18.2"  # Matches whats in /config/network wan ip addr
new_ip = str(gate_ip)

old_netmask = "255.255.255.0"
new_netmask = str(gate_netmask)

with open("C:/Users/admin/Documents/teltonika/configs/network", 'r') as file:
    content = file.read()
    
print("Replacing Old Gate Ip", flush=True)
time.sleep(s_pause)
updated_content = content.replace(old_ip, new_ip)

with open("C:/Users/admin/Documents/teltonika/configs/network", 'w') as file:
    file.write(updated_content)

with open("C:/Users/admin/Documents/teltonika/configs/network", 'r') as file:
    verify = file.read()
    if new_ip in verify:
        print("New Gate IP Updated", flush=True)
    else:
        print("Incorrect! New Gate IP Not Updated", flush=True)
        
time.sleep(s_pause)

############# Copy Python Test File to BBB ############ UPDATED

#print("Removed Current Keys for 192.168.7.2")
#result = subprocess.run("ssh-keygen -f 'C:\\Users\\70u3129/.ssh/known_hosts' -R '192.168.7.2' ")
#"ssh-keygen -R 'C:\\Users\\u317029/.ssh/known_hosts' -R '192.168.7.2' "

print("Copying Test File from Backup Folder", flush=True)
time.sleep(s_pause)

source_folder = 'og_testfile'
destination_folder = 'testfile'

os.makedirs(destination_folder, exist_ok=True)

for filename in os.listdir(source_folder):
    source_path = os.path.join(source_folder, filename)
    destination_path = os.path.join(destination_folder, filename)
    
    if os.path.isfile(source_path):
        shutil.copy2(source_path, destination_path)

old_rip = "127.0.0.1"  ## Get the new_ip into FloodLighToggle.py  (different than the other old_ip!!!!!)
new_ip = str(gate_ip)

with open("C:/Users/admin/Documents/teltonika/testfile/FloodLighToggle.py", 'r') as file:
    content = file.read()
    
print("Replacing Old Gate Ip", flush=True)
time.sleep(s_pause)
updated_content = content.replace(old_rip, new_ip)

with open("C:/Users/admin/Documents/teltonika/testfile/FloodLighToggle.py", 'w') as file:
    file.write(updated_content)

with open("C:/Users/admin/Documents/teltonika/testfile/FloodLighToggle.py", 'r') as file:
    verify = file.read()
    if new_ip in verify:
        print("New Gate IP Updated", flush=True)
    else:
        print("Incorrect! New Gate IP Not Updated Tel2", flush=True)
        
time.sleep(s_pause)

ssh_bbb_connect()
print("Copying FloodLighToggle.py File to BBB", flush=True)
time.sleep(s_pause)
ssh_bbb_upload("FloodLighToggle.py", "/home/raj/FloodLighToggle.py")
time.sleep(s_pause)

print("Verifying FloodLighToggle.py File Upload", flush=True)
time.sleep(s_pause)
output = ssh_bbb_run("ls -l /home/raj/")
time.sleep(s_pause)
if "FloodLighToggle.py" in output:
    print("FloodLighToggle.py found on BBB", flush=True)
else:
    print("Incorrect! FloodLighToggle.py not found on BBB!", flush=True)
    ssh_bbb_close()
    exit()
time.sleep(s_pause)
print("\n")

ssh_bbb_close()

############## Copy Firmware to Router ############# UPDATED

ssh_router_connect("temp", "root")

print("Copying Firmware File to Router", flush=True)
# time.sleep(l_pause)
# sftp_router.put("C:/Users/admin/Documents/teltonika/backup-RUTX08-2026-04-09.tar.gz", "/tmp/backup-RUTX08-2026-04-09.tar.gz")
time.sleep(l_pause)
sftp_router.put("C:/Users/admin/Documents/teltonika/RUTX_R_00.07.22.3_WEBUI.bin", "/tmp/RUTX_R_00.07.22.3_WEBUI.bin")

# print("Added Backup File to Router -- Changed IP Addr", flush=True)
print("Added Firmware File to Router", flush=True)
time.sleep(s_pause)

shell = ssh_router.invoke_shell()

shell.send(b"ls -l /tmp/\n")
time.sleep(s_pause)
output = shell.recv(5000).decode()
print(output, flush=True)
time.sleep(s_pause)

if "RUTX_R_00.07.22.3_WEBUI.bin" in output:
    print("Firmware File Found on Router", flush=True)
else:
    print("Incorrect! Firmware File Not Found on Router", flush=True)
    ssh_router_close()
    ssh_bbb_close()
    exit()
    
# if "backup-RUTX08-2026-04-09.tar.gz" in output:
#     print("Backup File Found on Router", flush=True)
# else:
#     print("Incorrect! Backup File Not Found on Router", flush=True)
#     ssh_router_close()
#     ssh_bbb_close()
#     exit()

time.sleep(s_pause)
shell.close()

################# Firmware Install ################# UPDATED

print("Installing Firmware", flush=True)
time.sleep(s_pause)
ssh_router_run("sysupgrade /tmp/RUTX_R_00.07.22.3_WEBUI.bin\n")
time.sleep(s_pause)
output = shell.recv(4096).decode()
print(output)
# print("Waiting for 5 minutes for Install", flush=True)
# time.sleep(60)
print("3 min left", flush=True)
time.sleep(75)
print("2 min left", flush=True)
time.sleep(60)
print("1 min left", flush=True)
time.sleep(60)
# print("1 min left", flush=True)
# time.sleep(60)
print("Install Done", flush=True)
time.sleep(s_pause)

######## First Time Login/Change Pass ######## UPDATED
print("Connecting to Router", flush=True)
output = ssh_router_connect("temp", "root")
time.sleep(s_pause)


if "07.22" in output:
    print("Confirmed Firmware Install", flush=True)
else:
    print("Incorrect! Firmware Not Installed", flush=True)
    ssh_router_close()
    ssh_bbb_close()
    exit()

# shell = ssh_router.invoke_shell()
# time.sleep(s_pause)
# shell.recv(1000)

# print("Resetting Temp Password to New Password", flush=True)
# time.sleep(s_pause)
# shell.send("passwd\n")
# time.sleep(s_pause)
# output = shell.recv(2000).decode()
# #print(output, flush=True)
# time.sleep(s_pause)

# # set new password
# if "Old password" in output:
#     print("Sending Old Password", flush=True)
#     print("temp_pass: ", temp_pass, flush=True)
#     shell.send(temp_pass + '\n')
#     time.sleep(s_pause)
#     output = shell.recv(2000).decode()
#     time.sleep(s_pause)
#     #print(output, flush=True)
#     time.sleep(s_pause)
    
# if "New password" in output:
#     print("Sending New Password", flush=True)
#     shell.send(new_pswd + '\n')
#     time.sleep(s_pause)
#     output = shell.recv(2000).decode()
#     time.sleep(s_pause)
#     #print(output, flush=True)
#     time.sleep(s_pause)

# if "Retype password" in output:
#     print("Confirming New Password", flush=True)
#     shell.send(new_pswd + '\n')
#     time.sleep(s_pause)
#     output = shell.recv(2000).decode()
#     time.sleep(s_pause)
#     #print(output, flush=True)
#     time.sleep(s_pause)

# ssh_router_close()
# time.sleep(s_pause)

# print("Connecting to Router", flush=True)
# ssh_router_connect("new", "root")
# time.sleep(s_pause)

# shell = ssh_router.invoke_shell()
# time.sleep(s_pause)
# shell.recv(1000)

# print("Resetting Temp Password to New Password", flush=True)
# time.sleep(s_pause)
# shell.send("passwd\n")
# time.sleep(s_pause)
# output = shell.recv(2000).decode()
# #print(output, flush=True)
# time.sleep(s_pause)

# # set new password
# if "Old password" in output:
#     print("Sending Old Password", flush=True)
#     shell.send(temp_pass + '\n')
#     time.sleep(s_pause)
#     output = shell.recv(2000).decode()
#     time.sleep(s_pause)
#     #print(output, flush=True)
#     time.sleep(s_pause)
    
# if "New password" in output:
#     print("Sending New Password", flush=True)
#     shell.send(new_pswd + '\n')
#     time.sleep(s_pause)
#     output = shell.recv(2000).decode()
#     time.sleep(s_pause)
#     #print(output, flush=True)
#     time.sleep(s_pause)

# if "Retype password" in output:
#     print("Confirming New Password", flush=True)
#     shell.send(new_pswd + '\n')
#     time.sleep(s_pause)
#     output = shell.recv(2000).decode()
#     time.sleep(s_pause)
#     #print(output, flush=True)
#     time.sleep(s_pause)
    
# print("Done Updating Passwords", flush=True)

# time.sleep(s_pause)
# shell.send("ping 192.168.81.1\n")
# time.sleep(s_pause)
# output = shell.recv(2000).decode()

# if "bytes=32" in output:
#     print("Correct IP address", flush=True)
# else:
#     print("Wrong IP address", flush=True)
#     shell.send("ping 192.168.1.1\n")
#     time.sleep(s_pause)
#     output = shell.recv(2000).decode()
#     if "bytes=32" in output:
#         print("IP address is 192.168.1.1", flush=True)
#     else:
#         print("Something is wrong")

# ssh_router_close()
# time.sleep(s_pause)

############### UPDATE CONFIGURATION ###############

print("Setting Up Configuration File", flush=True)
time.sleep(l_pause)

ssh_router_connect("temp", "root")

############## Config Files to Router ############## UPDATED

#82 config files
print("Copying All Config Files to Router", flush=True)
time.sleep(l_pause)

local_path = "C:/Users/admin/Documents/teltonika/configs"
sftp_router.put(f"{local_path}/avl", "/etc/config/avl")
sftp_router.put(f"{local_path}/bgp", "/etc/config/bgp")
sftp_router.put(f"{local_path}/ble_devices", "/etc/config/ble_devices")
sftp_router.put(f"{local_path}/blesem", "/etc/config/blesem")
sftp_router.put(f"{local_path}/buttons", "/etc/config/buttons")
sftp_router.put(f"{local_path}/call_utils", "/etc/config/call_utils")
sftp_router.put(f"{local_path}/chilli", "/etc/config/chilli")
sftp_router.put(f"{local_path}/cli", "/etc/config/cli")
sftp_router.put(f"{local_path}/connchecker", "/etc/config/connchecker")
sftp_router.put(f"{local_path}/data_sender", "/etc/config/data_sender")
sftp_router.put(f"{local_path}/ddns", "/etc/config/ddns")
sftp_router.put(f"{local_path}/dfota", "/etc/config/dfota")
sftp_router.put(f"{local_path}/dhcp", "/etc/config/dhcp")
sftp_router.put(f"{local_path}/dmvpn", "/etc/config/dmvpn")
sftp_router.put(f"{local_path}/dot1x", "/etc/config/dot1x")
sftp_router.put(f"{local_path}/dropbear", "/etc/config/dropbear")
sftp_router.put(f"{local_path}/eigrp", "/etc/config/eigrp")
sftp_router.put(f"{local_path}/email_to_sms", "/etc/config/email_to_sms")
sftp_router.put(f"{local_path}/etherwake", "/etc/config/etherwake")
sftp_router.put(f"{local_path}/event_juggler", "/etc/config/event_juggler")
sftp_router.put(f"{local_path}/firewall", "/etc/config/firewall")
sftp_router.put(f"{local_path}/fstab", "/etc/config/fstab")
sftp_router.put(f"{local_path}/gps", "/etc/config/gps")
sftp_router.put(f"{local_path}/hostblock", "/etc/config/hostblock")
sftp_router.put(f"{local_path}/impulse_counter", "/etc/config/impulse_counter")
sftp_router.put(f"{local_path}/io_scheduler", "/etc/config/io_scheduler")
sftp_router.put(f"{local_path}/ioman", "/etc/config/ioman")
sftp_router.put(f"{local_path}/ip_blockd", "/etc/config/ip_blockd")
sftp_router.put(f"{local_path}/ipsec", "/etc/config/ipsec")
sftp_router.put(f"{local_path}/landingpage", "/etc/config/landingpage")
sftp_router.put(f"{local_path}/mdcollectd", "/etc/config/mdcollectd")
sftp_router.put(f"{local_path}/modbus_client", "/etc/config/modbus_client")
sftp_router.put(f"{local_path}/modbus_server", "/etc/config/modbus_server")
sftp_router.put(f"{local_path}/modbusgateway", "/etc/config/modbusgateway")
sftp_router.put(f"{local_path}/mosquitto", "/etc/config/mosquitto")
sftp_router.put(f"{local_path}/mqtt_pub", "/etc/config/mqtt_pub")
sftp_router.put(f"{local_path}/multi_wifi", "/etc/config/multi_wifi")
sftp_router.put(f"{local_path}/mwan3", "/etc/config/mwan3")
sftp_router.put(f"{local_path}/network", "/etc/config/network")
sftp_router.put(f"{local_path}/nhrp", "/etc/config/nhrp")
sftp_router.put(f"{local_path}/nlbwmon", "/etc/config/nlbwmon")
sftp_router.put(f"{local_path}/ntpclient", "/etc/config/ntpclient")
sftp_router.put(f"{local_path}/ntpserver", "/etc/config/ntpserver")
sftp_router.put(f"{local_path}/openssl", "/etc/config/openssl")
sftp_router.put(f"{local_path}/openvpn", "/etc/config/openvpn")
sftp_router.put(f"{local_path}/operctl", "/etc/config/operctl")
sftp_router.put(f"{local_path}/ospf", "/etc/config/ospf")
sftp_router.put(f"{local_path}/overview", "/etc/config/overview")
sftp_router.put(f"{local_path}/package_restore", "/etc/config/package_restore")
sftp_router.put(f"{local_path}/password_policy", "/etc/config/password_policy")
sftp_router.put(f"{local_path}/periodic_reboot", "/etc/config/periodic_reboot")
sftp_router.put(f"{local_path}/ping_reboot", "/etc/config/ping_reboot")
sftp_router.put(f"{local_path}/pptpd", "/etc/config/pptpd")
sftp_router.put(f"{local_path}/privoxy", "/etc/config/privoxy")
sftp_router.put(f"{local_path}/profiles", "/etc/config/profiles")
sftp_router.put(f"{local_path}/relayd", "/etc/config/relayd")
sftp_router.put(f"{local_path}/rip", "/etc/config/rip")
sftp_router.put(f"{local_path}/rms_mqtt", "/etc/config/rms_mqtt")
sftp_router.put(f"{local_path}/rpcd", "/etc/config/rpcd")
sftp_router.put(f"{local_path}/rs_console", "/etc/config/rs_console")
sftp_router.put(f"{local_path}/rs_modbus", "/etc/config/rs_modbus")
sftp_router.put(f"{local_path}/rs_modem", "/etc/config/rs_modem")
sftp_router.put(f"{local_path}/rs_overip", "/etc/config/rs_overip")
sftp_router.put(f"{local_path}/rut_fota", "/etc/config/rut_fota")
sftp_router.put(f"{local_path}/sim_switch", "/etc/config/sim_switch")
sftp_router.put(f"{local_path}/simcard", "/etc/config/simcard")
sftp_router.put(f"{local_path}/sms_gateway", "/etc/config/sms_gateway")
sftp_router.put(f"{local_path}/sms_utils", "/etc/config/sms_utils")
sftp_router.put(f"{local_path}/snmpd", "/etc/config/snmpd")
sftp_router.put(f"{local_path}/snmptrap", "/etc/config/snmptrap")
sftp_router.put(f"{local_path}/sqm", "/etc/config/sqm")
sftp_router.put(f"{local_path}/stunnel", "/etc/config/stunnel")
sftp_router.put(f"{local_path}/system", "/etc/config/system")
sftp_router.put(f"{local_path}/travelmate", "/etc/config/travelmate")
sftp_router.put(f"{local_path}/uhttpd", "/etc/config/uhttpd")
sftp_router.put(f"{local_path}/ulogd", "/etc/config/ulogd")
sftp_router.put(f"{local_path}/user_groups", "/etc/config/user_groups")
sftp_router.put(f"{local_path}/vrrpd", "/etc/config/vrrpd")
sftp_router.put(f"{local_path}/vuci", "/etc/config/vuci")
sftp_router.put(f"{local_path}/widget", "/etc/config/widget")
sftp_router.put(f"{local_path}/wifi_scanner", "/etc/config/wifi_scanner")
sftp_router.put(f"{local_path}/xl2tpd", "/etc/config/xl2tpd")

print("Copied All Config Files to Router", flush=True)
time.sleep(l_pause)

#################### Get MAC Address ##################### UPDATED
mac = None

shell = ssh_router.invoke_shell()
time.sleep(s_pause)
shell.recv(1000)

print("Getting MAC Address", flush=True)
time.sleep(s_pause)
shell.send(b"ifconfig -a\n")
time.sleep(s_pause)
output = shell.recv(2000).decode()
for line in output.splitlines():
    if new_ip in line:
        print("Found new ip in output", flush=True)
    if "eth0" in line and "HWaddr" in line:
        mac = line.split("HWaddr")[1].strip()
        break
if mac:
    print("MAC Addr: " + mac, flush=True)
else:
    print("MAC Address Not Correctly Extracted", flush=True)
    
time.sleep(s_pause)

######################## Reboot ########################## UPDATED

print("Rebooting Router", flush=True)
time.sleep(l_pause)
ssh_router_run("reboot\n")
time.sleep(s_pause)

old_ip = str(gate_ip)
new_ip = "10.28.18.2"   ## WAN IP address for the router without programming -- Just reset the files for next time

with open("C:/Users/admin/Documents/teltonika/configs/network", 'r') as file:
    content = file.read()
    
print("Reverting Network File", flush=True)
time.sleep(s_pause)
updated_content = content.replace(old_ip, new_ip)

with open("C:/Users/admin/Documents/teltonika/configs/network", 'w') as file:
    file.write(updated_content)

with open("C:/Users/admin/Documents/teltonika/configs/network", 'r') as file:
    verify = file.read()
    if new_ip in verify:
        print("New IP revert: ", new_ip, flush=True)
        print("Network File Reverted", flush=True)
    else:
        print("Incorrect! Network File Not Reverted", flush=True)
        
print("Please Wait 1.5 Mins for Reboot", flush=True)
time.sleep(30)
print("1 min left", flush=True)
time.sleep(60)
# print("1 min left", flush=True)
# time.sleep(60)
print("Reboot Done", flush=True)
time.sleep(s_pause)

print("FINISHED SETTING UP ROUTER")
time.sleep(s_pause)
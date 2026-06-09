#SSH
import subprocess
import time
import paramiko
from ping3 import ping

#GUI
import tkinter as tk
from tkinter import messagebox
import time

# Short and Long Pause (sec)
s_pause = 1
l_pause = 2

# Global Variables
ssh_bbb = None
sftp_bbb = None
ssh_router = None
sftp_router = None

################# INFO ####################
#Teltonika router intially had 0.7.11.3 Firmware Version

################## GUI ####################

def valid_character(char):
    return char.isdigit() or char =='.'
    
def submit_all():
    global vlan_ip
    vlan_ip = vlan_entry.get()

    if vlan_ip:
        root.destroy()
    else:
        messagebox.showwarning("Input Error", "All Fields Must Be Filled")
        
################## BBB ####################

def ssh_bbb_connect():
    print("Connecting to BBB")
    global ssh_bbb, sftp_bbb
    bbb_ip = '192.168.7.2'
    bbb_user = 'raj'
    bbb_pass = 'Jetway'

    ssh_bbb = paramiko.SSHClient()
    ssh_bbb.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_bbb.connect(bbb_ip, username=bbb_user, password=bbb_pass)
    print("Connected to BBB")
    
    sftp_bbb = ssh_bbb.open_sftp()
    time.sleep(s_pause)

def ssh_bbb_run(cmd):
    global ssh_bbb
    stdin, stdout, stderr = ssh_bbb.exec_command(cmd)
    output = stdout.read().decode()
    error = stdout.read().decode()
    if output is not None:
        print("Output:\n", output)
    if error is not None:
        print("Errors:\n", error)
    return output

def ssh_bbb_upload(file, bbb_file):
    global sftp_bbb
    sftp_bbb.put(file, bbb_file)
    
def ssh_bbb_close():
    print("Closing Connection to BBB")
    global ssh_bbb, sftp_bbb
    if sftp_bbb:
        sftp_bbb.close()
    if ssh_bbb:
        ssh_bbb.close()
    time.sleep(s_pause)
    print("Closed Connection to BBB")

################### Router ###################

def shell_router_connect(num):
    print("Connecting to Router")
    time.sleep(s_pause)
    shell = ssh_run_shell(ssh_bbb, "ssh root@192.168.1.1", num)
    print("Connected to Router")
    time.sleep(s_pause)
    return shell
    
def shell_router_close():
    print("Closing Router Shell Session")
    time.sleep(s_pause)
    shell.send("exit\n")
    shell.close()
    print("Closed Router Shell Session")
    time.sleep(s_pause)
    
########### Password Prompt Handler ###########
  
def ssh_run_shell(client, command, num=None):
    global ssh_bbb
    global ssh_router

    # passwords
    bbb_pass = "Jetway"
    router_temp_pass = "y2E8LsZq"
    router_pass = "AAAaaa111!!!"
    
    shell = client.invoke_shell()
    time.sleep(1)
    shell.recv(1000)
    
    shell.send(command + '\n')
    time.sleep(1)
    output = shell.recv(1000).decode()
    
    #add static ip
    if "[sudo] password for" in output:
        shell.send(bbb_pass + '\n')
        time.sleep(1)
        output += shell.recv(2000).decode()
    
    #authenticity issue
    if "authenticity of host" in output:
        shell.send("yes" + '\n')
        time.sleep(1)
        output += shell.recv(2000).decode()
    
    #router password handling
    if "root@192" in output:
        print("Password Type: ", num)
        if num == "temp":
            shell.send(router_temp_pass + '\n')
        else:
            shell.send(router_pass + '\n')
        time.sleep(1)
        output += shell.recv(2000).decode()
    
    print("Output:\n", output)
    return shell, client, output

################# Ping Test ##################

def ssh_ping(client, target_ip):
    global ssh_bbb, ssh_router
    attempt = 0
    
    #Try Ping Test
    while attempt < 3:
        print("Trying to Ping", target_ip)
        time.sleep(s_pause)
        stdin, stdout, stderr = client.exec_command(f"ping -c 4 {target_ip}")
        output = stdout.read().decode()
        error = stderr.read().decode()
        print("Ping Output:\n", output)
        if error:
            print("Ping Error: \n, error")
        if " 0% packet loss" in output:
            print("Connection Successful!")
            break
        else:
            print("Connection Unsuccessful :(")
            attempt += 1
            time.sleep(s_pause)
    
    #Connection failed after 3 attempts
    if attempt == 3:
        print("Connection Failed after 3 Tries. Abort.")
        if client == ssh_bbb:
            ssh_bbb_close()
            exit()
                
    time.sleep(s_pause)
    
##############################################
######### START OF AUTOMATION SCRIPT #########
##############################################

""" 
-Firmware Installation
-Static IP Setup from BBB to router
-1st Login into Router and temp pass change
-Config Files Updates
-Save and Reboot

"""

print("STARTING AUTOMATIC ROUTER SETUP PROCESS")
time.sleep(l_pause)

################ User Enter IPs #################

root = tk.Tk()
root.title("InHand Router Information")

vcmd = (root.register(valid_character), '%S')

#vlan1
tk.Label(root, text="Enter Public IP:").grid(row=0, column=0, padx=10, pady=5, sticky='e')
vlan_entry = tk.Entry(root, width=30, validate="key", validatecommand=vcmd)
vlan_entry.grid(row=0, column=1, padx=10, pady=5)

tk.Button(root, text="Submit", command=submit_all).grid(row=2, columnspan=2,pady=20)

root.mainloop()

time.sleep(s_pause)
print("The Public IP is", vlan_ip)
time.sleep(s_pause)

############ Copy Firmware to BBB ############

ssh_bbb_connect()

""" print("Copying Firmware File to BBB")
time.sleep(s_pause)
ssh_bbb_upload("RUTX_R_00.07.14.3_WEBUI.bin", "/home/raj/RUTX_R_00.07.14.3_WEBUI.bin")
time.sleep(s_pause)
print("Added Firmware File to BBB")
time.sleep(s_pause)
print("Verify Firmware File Upload")
time.sleep(s_pause)
output = ssh_bbb_run("ls -l /home/raj/")
time.sleep(s_pause)
if "RUTX_R_00.07.14.3_WEBUI.bin" in output:
    print("RUTX_R_00.07.14.3_WEBUI.bin found on BBB")
else:
    print("RUTX_R_00.07.14.3_WEBUI.bin not found on BBB! Aborting Script.")
    ssh_bbb_close()
    exit()
time.sleep(l_pause)
print("\n") """

########## Copy Python Test Files to BBB #########

""" print("Copying FloodLighOn.py File to BBB")
time.sleep(s_pause)
ssh_bbb_upload("FloodLighOn.py", "/home/raj/FloodLighOn.py")
time.sleep(s_pause)

print("Verifying FloodLighOn.py File Upload")
time.sleep(s_pause)
output = ssh_bbb_run("ls -l /home/raj/")
time.sleep(s_pause)
if "FloodLighOn.py" in output:
    print("FloodLighOn.py found on BBB")
else:
    print("FloodLighOn.py not found on BBB! Aborting Script.")
    ssh_bbb_close()
    exit()
time.sleep(s_pause)

time.sleep(l_pause)
print("\n")

print("Copying FloodLighOff.py File to BBB")
time.sleep(s_pause)
ssh_bbb_upload("FloodLighOff.py", "/home/raj/FloodLighOff.py")
time.sleep(s_pause)

print("Verifying FloodLighOff.py File Upload")
time.sleep(s_pause)
output = ssh_bbb_run("ls -l /home/raj/")
time.sleep(s_pause)
if "FloodLighOff.py" in output:
    print("FloodLighOff.py found on BBB")
else:
    print("FloodLighOff.py not found on BBB! Aborting Script.")
    ssh_bbb_close()
    exit()
time.sleep(s_pause) """

############## Setup Static IP ##############

print("Setting Up Static IP of BBB to Router")
time.sleep(s_pause)
print("Displaying Current IP(s)")
time.sleep(s_pause)
ssh_bbb_run("ip addr show eth0")
time.sleep(s_pause)
print("Adding Static IP to access Router")
time.sleep(s_pause)
ssh_run_shell(ssh_bbb, "sudo ip addr add local 192.168.1.2/24 dev eth0")
print("Added 192.168.1.2/24 Static IP addto eth0")
time.sleep(s_pause)
print("Displaying Current IP(s)")
time.sleep(s_pause)
ssh_bbb_run("ip addr show eth0")
time.sleep(l_pause)

################## Ping Test ##################

print("Testing Static IP")
ssh_ping(ssh_bbb,"192.168.1.1")   
time.sleep(s_pause)

######## First Time Login/Change Pass ########

""" ssh_bbb_run("ssh-keygen -f '/home/raj/.ssh/known_hosts' -R '192.168.1.1' ")
time.sleep(s_pause)
shell, client, _ = shell_router_connect("new")

print("Resetting Temporary Password to New Password")
time.sleep(s_pause)
shell.send("passwd\n")
time.sleep(s_pause)
output = shell.recv(2000).decode()

# set new password
if "New password" in output:
    shell.send("AAAaaa111!!!" + '\n')
    time.sleep(s_pause)
    output += shell.recv(2000).decode()
    time.sleep(s_pause)

if "Retype password" in output:
    shell.send("AAAaaa111!!!" + '\n')
    time.sleep(s_pause)
    output += shell.recv(2000).decode()
    time.sleep(s_pause)
print("Reset Temporary Password to New Password")
time.sleep(s_pause)

shell_router_close() """

############### Testing New Password ###############

""" print("Testing New Password")
time.sleep(s_pause)
shell, client, _ = shell_router_connect("new")

shell_router_close() """

############## Copy Firmware to Router #############

""" print("Copying Firmware File to Router")
time.sleep(s_pause)
ssh_run_shell(ssh_bbb, "scp /home/raj/RUTX_R_00.07.14.3_WEBUI.bin root@192.168.1.1:/tmp/", "new")
print("Added Firmware File to Router")
time.sleep(s_pause)

shell, client, _ = shell_router_connect("new")
output = ""
shell.send("ls -l /tmp/\n")
time.sleep(s_pause)
output += shell.recv(5000).decode()
print(output)
time.sleep(s_pause)

if "RUTX_R_00.07.14.3_WEBUI.bin" in output:
    print("Firmware File Found on Router")
else:
    print("Firmware File Not Found on Router")
    shell_router_close()
    ssh_bbb_close()
    exit()
        
shell_router_close() """

################# Firmware Install #################

""" shell, client, _ = shell_router_connect("new")
shell.send("sysupgrade /tmp/RUTX_R_00.07.14.3_WEBUI.bin\n")
time.sleep(s_pause)
output = shell.recv(4096).decode()
print(output) 
shell_router_close() """

############### UPDATE CONFIGURATION ###############

print("Setting Up Configuration File")
time.sleep(l_pause)

############## Config Files to Router ##############

print("Copying Updated Network Config File to Router")
time.sleep(s_pause)
ssh_run_shell(ssh_bbb, "scp /home/raj/network root@192.168.1.1:/etc/config/network", "new")
print("Added Updated Network Config File to Router")
time.sleep(l_pause)

print("Copying Updated Firewall Config File to Router")
time.sleep(s_pause)
ssh_run_shell(ssh_bbb, "scp /home/raj/network root@192.168.1.1:/etc/config/firewall", "new")
print("Added Updated Firewall Config File to Router")
time.sleep(l_pause)

################# Save and Reboot ##################

shell, client, _ = shell_router_connect("new")
print("Rebooting") 
shell.send("reboot\n")
time.sleep(s_pause)
shell_router_close()

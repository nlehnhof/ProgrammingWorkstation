#GUI
import tkinter as tk
from tkinter import messagebox
import time
import ipaddress

# Short and Long Pause (sec)
s_pause = 1
l_pause = 2

################## GUI ####################

def valid_character(char):
    return char.isdigit() or char =='.'
    
def submit_all():
    global gate_ip
    gate_ip = vlan_entry.get()

    try:
        ipaddress.IPv4Address(gate_ip)
        root.destroy()
    except ValueError:
        messagebox.showwarning("Input Error", "Invalid IP Address")
        
################### User Enter IPs ####################

root = tk.Tk()
root.title("InHand Router Information")

vcmd = (root.register(valid_character), '%S')

tk.Label(root, text="Enter Public IP:").grid(row=0, column=0, padx=10, pady=5, sticky='e')
vlan_entry = tk.Entry(root, width=30, validate="key", validatecommand=vcmd)
vlan_entry.grid(row=0, column=1, padx=10, pady=5)

tk.Button(root, text="Submit", command=submit_all).grid(row=2, columnspan=2,pady=20)

root.mainloop()

time.sleep(s_pause)
print("The Public IP is", gate_ip)
time.sleep(s_pause)

################ Update Public Gate IP #################

old_ip = "10.3.16.53"
new_ip = str(gate_ip)

with open("C:/Users/u317029/Documents/teltonika/test.txt", 'r') as file:
    content = file.read()

print("Replacing Old Gate Ip")
time.sleep(s_pause)
updated_content = content.replace(old_ip, new_ip)

with open("C:/Users/u317029/Documents/teltonika/test.txt", 'w') as file:
    file.write(updated_content)
    
print("New Gate IP Updated")
time.sleep(s_pause)
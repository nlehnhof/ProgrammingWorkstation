### Debugging May 29th

Error: The Router IP Address is not matching what is on the spreadsheet. This is throwing everything off.
Next: Confirm this is a repeatable issue.
Thoughts: Look at "old_ip" and "new_ip" logic, especially the "Reboot / Reset" logic in teltonika.py. Make sure that "old_ip" and "new_ip" match what is currently in FloodLighToggle.py so when we write the router's new ip to the FloodLighToggle.py test, it can find the old_ip to replace.

With the BBB in the WAN port, it kept failing. Switching it to the LAN1 port which matches Raj's tutorial.
I'm switching back to the WAN port.

Results:
First Test
Expected: JKC-SLC   24    10002    10.24.100.2
Output: 10.28.18.123

Second Test
Expected: JKC-SLC 21 10000 10.28.18.2
Output:   10.28.18.123

Third Test
Expected: GCN-PDX 11 20000 10.20.15.22
Output:   10.28.18.123

Weird thing: so far it looks like everything is writing correctly. FloodLighToggle.py and configs/network are all writing correctly and have the correct IP address. But when I ping that address from the BBB, it can't reach it. The following error is blocking us from downloading the config files to the router, so the new ip address, though written correctly to all the files isn't making it to the router itself.

When I tried to go using the web broswer to see what was up, it told me I needed a firmware update for the device.

```
Closing Connection to BBB
Closed Connection to BBB
Connecting to Router
Using Temp Password
root
y2E8LsZq
Traceback (most recent call last):
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 271, in <module>
ssh_router_connect("temp", "root")

File "C:\Users\admin\Documents\teltonika\teltonika.py", line 102, in ssh_router_connect
ssh_router.connect(router_ip, username=router_user, password=router_temp_pass)

File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 407, in connect
raise NoValidConnectionsError(errors)
paramiko.ssh_exception.NoValidConnectionsError: [Errno None] Unable to connect to port 22 on 192.168.1.1
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged
```

### June 1st
After a weekend, I wanted to see if things would reset better. The classic turn it off and back on again principle.
Output:
Wed Jun  4 10:41:17 UTC 2025 upgrade: Saving config files...

Test: JKC-SLC 10001 10.120.30.4
Result: JKC-SLC 10001 EVERYTHING WROTE CORRECTLY EXCEPT FOR CONFIGS/NETWORK
I can't ping anything from BBB.
 
 
Copying Test File from Backup Folder
Replacing Old Gate Ip
New Gate IP Updated
Connecting to BBB
Connected to BBB
Copying FloodLighToggle.py File to BBB
Verifying FloodLighToggle.py File Upload
total 129364
-rw-r--r-- 1 raj raj    13429 Mar 13  2025 FloodLighOff.py
-rwxr-xr-x 1 raj raj    13344 Mar 13  2025 FloodLighOff.py.BAK
-rw-r--r-- 1 raj raj    13839 Mar 13  2025 FloodLighOn.py
-rwxr-xr-x 1 raj raj    13343 Mar 13  2025 FloodLighOn.py.BAK
-rw-r--r-- 1 raj raj    14601 Mar 13 04:13 FloodLighToggle.py
-rw-r--r-- 1 raj raj    14753 Mar 13  2025 FloodLighToggle.py.save
-rw-r--r-- 1 raj raj 14988572 Mar 13  2025 IR9-V1.0.0.r20039.bin
-rw-r--r-- 1 raj raj 27234078 Mar 13  2025 RUTX_R_00.07.14.3_WEBUI.bin
-rw-r--r-- 1 raj raj 27889612 Mar 13  2025 RUTX_R_00.07.15_WEBUI.bin
-rw-r--r-- 1 raj raj     6056 Mar 13  2025 firewall
-rw-r--r-- 1 raj raj 35001901 Mar 13  2025 firmware-IX20-22.5.50.62.bin
-rw-r--r-- 1 raj raj     2210 Mar 13  2025 network
-rw-r--r-- 1 raj raj 27234078 Mar 13  2025 root@192.168.81.1

FloodLighToggle.py found on BBB

10.120.30.123
Setting Up Static IP of BBB to Router
Displaying Current IP(s)
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 60:e8:5b:14:e8:ca brd ff:ff:ff:ff:ff:ff
    inet 10.28.18.123/24 brd 10.28.18.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.81.123/24 brd 192.168.81.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.8.123/24 brd 192.168.8.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::62e8:5bff:fe14:e8ca/64 scope link 
       valid_lft forever preferred_lft forever

Adding Static IP to access Router
sudo ip addr add local 10.120.30.123/24 dev eth0

Added 10.120.30.123/24 Static IP to eth0
Displaying Current IP(s)
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 60:e8:5b:14:e8:ca brd ff:ff:ff:ff:ff:ff
    inet 10.28.18.123/24 brd 10.28.18.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.81.123/24 brd 192.168.81.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.8.123/24 brd 192.168.8.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 10.120.30.123/24 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::62e8:5bff:fe14:e8ca/64 scope link 
       valid_lft forever preferred_lft forever

After running the TEST, I can ping 10.120.30.123 and 10.28.18.123. So it looks like it correctly updated the router. I now need to figure out what is breaking during the test that prevents the test from finishing.

THOUGHT 1: I checked the FloodLighToggle.py script from the BBB (nano FloodLighToggle.py). The g_host address was still on the default. Looking in dashboard.py, the script was uploading the original floodlight script instead of the testfile/script that had the updated ip addr. I updated the uploading addresses.
THOUGHT 2: Right now, the new ip addr getting put in g_host is the original from the spreadsheet, but the BBB can only ping the xx.xxx.xx.123/24 address, not the original. Would that be messing things up?

Rerunning script after resetting router...

After running the programming script, the BBB still can only ping the default IP address with 10.28.18.123, but can't access the new IP address.

After testing, still broke, though the FloodLighToggle.py file correctly wrote the new IP address (not the xx.123 address). So THOUGHT 1 has been tested/fixed. On to THOUGHT 2.

Rerunning script after resetting router...
Again, failed to connect.

THOUGHT 3: I ran a port checker through the python socket package for 10.120.30.123 from the BBB. I originally pinged 10.120.30.123 to make sure it was accessible. Ports 22 and 80 returned open. In FloodLighToggle.py, the port is being defined as 502, which is not open.  

Rerunning script after resetting router...
The BBB still doesn't see the new IP address after the programming. It does seem to see it after the testing.

Another thought. I need to connect to the router and explore, but the internet thing admin page isn't working.


DIRECTLY AFTER RUNNING THE PROGRAMMING... FROM BBB...
raj@BBB:~$ ip addr show
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
2: dummy0: <BROADCAST,NOARP> mtu 1500 qdisc noop state DOWN group default qlen 1000
    link/ether 9e:1d:ca:79:33:c5 brd ff:ff:ff:ff:ff:ff
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 60:e8:5b:14:e8:ca brd ff:ff:ff:ff:ff:ff
    inet 10.28.18.123/24 brd 10.28.18.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.81.123/24 brd 192.168.81.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.8.123/24 brd 192.168.8.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::62e8:5bff:fe14:e8ca/64 scope link
       valid_lft forever preferred_lft forever
4: usb0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 60:e8:5b:14:e8:cd brd ff:ff:ff:ff:ff:ff
    inet 192.168.7.2/24 brd 192.168.7.255 scope global usb0
       valid_lft forever preferred_lft forever
    inet6 fe80::62e8:5bff:fe14:e8cd/64 scope link
       valid_lft forever preferred_lft forever
5: usb1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 60:e8:5b:14:e8:cf brd ff:ff:ff:ff:ff:ff
    inet 192.168.6.2/24 brd 192.168.6.255 scope global usb1
       valid_lft forever preferred_lft forever
    inet6 fe80::62e8:5bff:fe14:e8cf/64 scope link
       valid_lft forever preferred_lft forever
6: can0: <NOARP,ECHO> mtu 16 qdisc noop state DOWN group default qlen 10
    link/can

When I log into the router admin portal, it shows WAN IP ADDR as 10.120.30.4 (private network). This is the correct IP address. So why can't the BBB see it?

Or is it that in the test script, I add local ip to BBB and Setting Up Static IP of BBB to Router?

Router IP Address according to admin portal : 10.120.30.4
Router IP Address according to configs/network : 10.120.30.4
Eth0 as seen by BBB after programming: 
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 60:e8:5b:14:e8:ca brd ff:ff:ff:ff:ff:ff
    inet 10.28.18.123/24 brd 10.28.18.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.81.123/24 brd 192.168.81.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.8.123/24 brd 192.168.8.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::62e8:5bff:fe14:e8ca/64 scope link
       valid_lft forever preferred_lft forever

Eth0 as seen by BBB after testing: 
3: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether 60:e8:5b:14:e8:ca brd ff:ff:ff:ff:ff:ff
    inet 10.28.18.123/24 brd 10.28.18.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.81.123/24 brd 192.168.81.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 192.168.8.123/24 brd 192.168.8.255 scope global eth0
       valid_lft forever preferred_lft forever
    inet 10.120.30.123/24 scope global eth0
       valid_lft forever preferred_lft forever
    inet6 fe80::62e8:5bff:fe14:e8ca/64 scope link
       valid_lft forever preferred_lft forever

So now that I'm pretty sure everything is connecting correctly, I wanted to run the test script line by line. We are having some issues there with crashes. Good news is that the HMI and PLC and BBB and Router are all connecting and communicating. We see that with the "build complete" and "connect complete" returns.

raj@BBB:~$ python FloodLighToggle.py
JetDock
build complete
connect complete
12
bytearray(b'\x00\x00\x00\x00\x00\x06\x00\x032G\x00\x01')
sent
0
The remote side closed the connection unexpectedly.
Bytes in received packet:
53 65 31 2B 49 48 63 69
Bytes at offset 2 and 3 must be zero
12
bytearray(b'\x00\x01\x00\x00\x00\x06\x00\x062G\x00\x01')
Traceback (most recent call last):
  File "/home/raj/FloodLighToggle.py", line 560, in <module>
    sys.exit(main())
  File "/home/raj/FloodLighToggle.py", line 551, in main
    interact()
  File "/home/raj/FloodLighToggle.py", line 503, in interact
    send()
  File "/home/raj/FloodLighToggle.py", line 410, in send
    g_socket.send(g_spacket[0:g_slength])
BrokenPipeError: [Errno 32] Broken pipe



Closing Connection to BBB
Closed Connection to BBB
Connecting to Router
Using Temp Password
root
y2E8LsZq
Traceback (most recent call last):
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 271, in <module>
ssh_router_connect("temp", "root")

File "C:\Users\admin\Documents\teltonika\teltonika.py", line 102, in ssh_router_connect
ssh_router.connect(router_ip, username=router_user, password=router_temp_pass)
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 483, in connect
self._auth(
username,
...<9 lines>...
passphrase,
)
^
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 814, in _auth
raise saved_exception
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 801, in _auth
self._transport.auth_password(username, password)
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\transport.py", line 1632, in auth_password
return self.auth_handler.wait_for_response(my_event)
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\auth_handler.py", line 263, in wait_for_response
raise e
paramiko.ssh_exception.AuthenticationException: Authentication failed.
An Error Occurred: can only concatenate str (not "int") to str
Osh

Closing Connection to BBB
Closed Connection to BBB
Connecting to Router
Using Temp Password
root
Jetway@dm1n
Traceback (most recent call last):
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 275, in <module>
ssh_router_connect("temp", "root")

File "C:\Users\admin\Documents\teltonika\teltonika.py", line 106, in ssh_router_connect
ssh_router.connect(router_ip, username=router_user, password=router_temp_pass)

File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 384, in connect
sock.connect(addr)
TimeoutError: [WinError 10060] A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to r

FileNotFoundError: [WinError 3] The system cannot find the path specified: 'og_configs'
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged

Closing Connection to BBB
Closed Connection to BBB
Connecting to Router
Using Temp Password
admin
Jetway@dm1n
Traceback (most recent call last):
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 276, in <module>
ssh_router_connect("temp", "root")

File "C:\Users\admin\Documents\teltonika\teltonika.py", line 107, in ssh_router_connect
ssh_router.connect(router_ip, username=router_user, password=router_temp_pass)

File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 407, in connect
raise NoValidConnectionsError(errors)
paramiko.ssh_exception.NoValidConnectionsError: [Errno None] Unable to connect to port 22 on 192.168.1.1
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged

Using Temp Password
admin
Jetway@dm1n

Using Temp Password
root
Jetway@dm1n

Using Temp Password
root
y2E8LsZq

Using Temp Password
admin
y2E8LsZq

Using Temp Password
admin
AAAaaa111!!!

Using Temp Password
root
AAAaaa111!!!

-------------------------

Authentication issues with the router and the script. It won't even connect. I do a factory reset and it changed it from 192.168.81.1 to 192.168.1.1. Don't know why. I changed the password to be exactly what's in the script, but it won't authenticate. I know the password and username are correct and getting passed in correctly because I hard coded them into the script. I also can log in through the browser with the credentials.

Just added the backup files and it reset the router to xxx.xxx.81.1 so we're all good now. I just ran through the password and username and it's the same as the other ones. I'll update the code and try it right now.   ---- SAME ERROR

Replacing Old Gate Ip
New Gate IP Updated
Copying Test File from Backup Folder
Replacing Old Gate Ip
New Gate IP Updated
Connecting to BBB
Connected to BBB
Copying FloodLighToggle.py File to BBB
Verifying FloodLighToggle.py File Upload
Output:
total 129372
-rw-r--r-- 1 raj raj    13429 Mar 13 06:11 FloodLighOff.py
-rwxr-xr-x 1 raj raj    13344 Mar 13 05:19 FloodLighOff.py.BAK
-rw-r--r-- 1 raj raj    13839 Mar 13 06:11 FloodLighOn.py
-rwxr-xr-x 1 raj raj    13343 Mar 13 05:19 FloodLighOn.py.BAK
-rw-r--r-- 1 raj raj    14601 Mar 13 09:24 FloodLighToggle.py
-rw-r--r-- 1 raj raj    14804 Mar 13 06:54 FloodLighToggle.py.save
-rw-r--r-- 1 raj raj 14988572 Mar 13  2025 IR9-V1.0.0.r20039.bin
-rw-r--r-- 1 raj raj 27234078 Mar 13 06:29 RUTX_R_00.07.14.3_WEBUI.bin
-rw-r--r-- 1 raj raj 27889612 Mar 13  2025 RUTX_R_00.07.15_WEBUI.bin
-rw-r--r-- 1 raj raj      824 Mar 13 05:39 check_ports.sh
-rw-r--r-- 1 raj raj     6056 Mar 13 04:40 firewall
-rw-r--r-- 1 raj raj 35001901 Mar 13 07:11 firmware-IX20-22.5.50.62.bin
-rw-r--r-- 1 raj raj     2210 Mar 13  2025 network
-rw-r--r-- 1 raj raj      637 Mar 13 05:57 python_check_ports.py
-rw-r--r-- 1 raj raj 27234078 Mar 13  2025 root@192.168.81.1

Errors:

FloodLighToggle.py found on BBB


Closing Connection to BBB
Closed Connection to BBB
Connecting to Router
Using Temp Password
admin
Jetway@dm1n
Traceback (most recent call last):
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 279, in <module>
ssh_router_connect("temp", "admin")
^
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 110, in ssh_router_connect
ssh_router.connect(router_ip, username=router_user, password=router_temp_pass)

File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 483, in connect
self._auth(
username,
^
...<9 lines>...
passphrase,
)
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 814, in _auth
raise saved_exception
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 801, in _auth
self._transport.auth_password(username, password)
^^^
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\transport.py", line 1632, in auth_password
return self.auth_handler.wait_for_response(my_event)
"C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\auth_handler.py", line 263, in wait_for_response
raise e
paramiko.ssh_exception.AuthenticationException: Authentication failed.
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged

### Authentication Error

Traceback (most recent call last):
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 284, in <module>
ssh_router_connect("temp", "admin")
^
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 113, in ssh_router_connect
ssh_router.connect(router_ip, username=router_user, password=router_temp_pass)

File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 483, in connect
self._auth(
username,
...<9 lines>...
passphrase,
)
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 814, in _auth
raise saved_exception
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 801, in _auth
self._transport.auth_password(username, password)
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\transport.py", line 1632, in auth_password
return self.auth_handler.wait_for_response(my_event)
"C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\auth_handler.py", line 263, in wait_for_response
raise e
paramiko.ssh_exception.AuthenticationException: Authentication failed.
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged

WE MADE IT PASSED THE AUTHENTICATION ERROR!! The username and password I used in the browser did not match the username for the sshd shell. It was "root" and "Jetway@dm1n".

#### Closed Authentication Error

### Firmware Error

Teltonika RUTX series 2026

--------------------------------------------------------

Device:     RUTX08

Kernel:     6.6.119

Firmware:   RUTX_R_00.07.22.3

Build:      87e33b723e

Build date: 2026-05-15 07:21:19

root@RUTX08:~#
Incorrect! Firmware File Not Found on Router

#### Closed Firmware

### Authentication Part 2
Waiting for 3.5 minutes for Install
3 min left
2 min left
1 min left
Install Done
Connecting to Router
Connecting to Router
Using Temp Password
192.168.81.1
admin
Jetway@dm1n
Errors in Authentication
Connected to Router
Traceback (most recent call last):
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 341, in <module>
output = ssh_router_connect("temp", "admin")
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 130, in ssh_router_connect
shell = ssh_router.invoke_shell()
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\client.py", line 595, in invoke_shell
chan = self._transport.open_session()
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\transport.py", line 988, in open_session
return self.open_channel(
^^
...<2 lines>...
timeout=timeout,

)
^
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\transport.py", line 1119, in open_channel
raise e
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\transport.py", line 2195, in run
ptype, m = self.packetizer.read_message()
e "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\packet.py", line 496, in read_message
header = self.read_all(self.__block_size_in, check_rekey=True)
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\packet.py", line 324, in read_all
raise EOFError()
EOFError
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged

#### FIXED AUTH 2 ERROR

### Random Error
root@RUTX08:~#
Copying All Config Files to Router
Copied All Config Files to Router
Getting MAC Address
MAC Addr: 20:97:27:17:9E:4B
Rebooting Router
Output:
Failed to find mctl UBUS object

Errors:

Reverting Network File
New IP revert:  10.28.18.2
Network File Reverted
Please Wait 2.5 Mins for Reboot
2 min left
1 min left
Reboot Done
FINISHED SETTING UP ROUTER

The mctl UBUS object not found response came as an output, not an error. Nothing broke (that I know of) so I'm going to keep moving forward, but may have to come back to this.

#### STILL FINISHED, BUT MAY HAVE TO CHECK THE ERROR LATER.

```
NOTE: I've been pinging 192.168.81.1 this whole time. It returned the whole time the router was being programmed except for when we were rebooting the router, but then it came back on its own. Good thing, right?
```

## TEST SCRIPT

### Connection Error (Again)
JetDock
Connection failed: [Errno 111] Connection refused
Not connected
Not connected
Not connected
Not connected
Not connected
Not connected
Not connected
Already disconnected


Oshkosh Log: Info Couldn't be Logged
BROKEN SOMEWHERE

I just pinged 192.168.81.7 (the PLC). It's returning like normal. Let me explore the connection error.

[/] The BBB can ping the new router IP address.
[/] The PC can ping the PLC
[/] What's up?

#### Fixed --- IP Address issue in FloodLighToggle.py (had .123 instead of .xx)

### IT WORKED

### Repeatability
- [-] Factory Reset
- [-] Check Router IP Address - Can I ping? NO --- I can ping 192.168.1.1
   - [-] If not, check configs
      - Logged into 192.168.1.1 with "admin; y2E8LsZq" -- no port forwards
      - Reset password to "Jetway@dm1n"
      - Current firmware version is 07.22.3 (This is correct.)
      - Updating configs...
      - Configs updated
      - I can now ping 192.168.81.1 -- port forwards are correct
   - [-] If configs are wrong, update firmware on router and backups
   - [-] Can I ping the IP Address now? YES 
- [-] Run Programming
- [-] Did it work?
   - [-] Check Files
   - [-] configs/network -- since we have revert checked on, the configs/network files and og_configs/network files are showing the original/default IP address for the router.
   - [-] testfile/FloodLighToggle.py
- [-] Run Testing
- [-] Did it work? YES!!!
- [-] Celebrate!!

I can also test it through the BBB mutliple times by running **python FloodLighToggle.py**.

### FROM FACTORY RESET
Now, I'm trying to develop the script to work from a factory reset.

Closing Connection to BBB
Closed Connection to BBB
Connecting to Router
Traceback (most recent call last):
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 293, in <module>
ssh_router_connect("temp", "root") 
File "C:\Users\admin\Documents\teltonika\teltonika.py", line 99, in ssh_router_connect
router_temp_pass = temp_pass
UnboundLocalError: cannot access local variable 'temp_pass' where it is not associated with a value
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged

FIRST LOGIN FIXED

#### The Router didn't update to 192.168.81.1 on its own. Working on automating backup and configs update.
File "C:\Users\admin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\paramiko\auth_handler.py", line 263, in wait_for_response
raise e
paramiko.ssh_exception.AuthenticationException: Authentication failed.
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged

#### FIXED: CHANGED AUTH LOGIC TO WORK FOR FACTORY RESET; CONFIG REBOOT HANDLED ALREADY BY SCRIPT

### ADDING FEATURE: CHECK IF ROUTER IS ALREADY PROGRAMMED
Router already programmed to IP:{addr}
An Error Occurred: can only concatenate str (not "int") to str
Oshkosh Log: Info Couldn't be Logged
Router already programmed to IP:10.28.18

['10.28.18.123', '10.28.18.255', '192.168.81.123', '192.168.81.255', '192.168.8.123', '192.168.8.255', '10.120.30.123']

['10.28.18.123', '192.168.81.123', '192.168.8.123', '10.120.30.123']
Router not programmed... continuing to program...
Router not programmed... continuing to program...
Router not programmed... continuing to program...
Router already programmed to IP:10.120.30.123

['10.28.18.123', '10.120.30.123']
Router already programmed to IP:10.120.30.123

#### SUCCESS ADDING FEATURE: CHECK IF PROGRAMMED

### Improvements and Timing
First Run from Reset: 
07:15 min for initial programming
00:30 min for testing.

Possible improvements: 
Remove 30 secs on Firmware Install wait
Remove 1 min on Reboot

Result:
Second Run from Reset:
06:25 min for programming
00:40 min for testing.
~07:00 min for full re-programming

### ADDED TIMING SCRIPT AND AUTOMATED RUN_TEST_SCRIPT SO TEST BUTTON IS NOT NEEDED IF PROGRAMMING ROUTER
Execution Time: 427.479487 seconds
Ex Time in Minutes: 7.124658

### SUMMARY OF FIRST WEEK
* I set up the hardware and connections for the Programming Workstation for the Teltonika Routers.
* I improved Authentication Logic to allow Factory Reset programming
* I added a feature to "Check if Router is Already Programmed"
* I automated the test script to run after programming script finishes (removed need for test button when programming routers)
* I updated the test button so return to "normal" state after a test is ran -- Allows routers to be tested without requiring a full reset / re-programming
* I added a timing feature to return the full amount of time for a programming & test run
* I eliminated the need to change passwords during programming -- increases speed
* I reduced the programming time per router by 2 minutes (~20% faster)
* I consolidated operator input to the beginning of a programming run -- eliminates the need for operator overwatch during programming

NEXT STEPS:
* Abstract Device Programming Station Application
   - Draft architecture and get feedback
   - Simple working demonstration
   - Add Draft for Programming Workstation for Teltonika Routers
   - Refine PWTR draft
   - Add Test for PWTR
   - Get feedback
   - Working Demonstration
* Printer Automation for Labels?
   - John is setting up a meeting with Brady
   - HellermannTyton? Not going to work

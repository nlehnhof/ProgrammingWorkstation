#! /usr/bin/python3
#
# Andy Cranston T/A (Trading As) Cranston Innovation
#
# @(!--#) @(#) mbdebug.py, version 007, 17-march-2020
#
# Modbus/TCP client debugger tool
#
# Links:
#
#    https://unserver.xyz/modbus-guide/
#

############################################################################

DEBUG = False

############################################################################

import sys
import os
import argparse
import time
import socket
import select
#import argparse

############################################################################

MAX_PACKET_SIZE = 65536
MIN_PACKET_SIZE = 6
SUPPORTED_FCS = [ 0x01, 0x03, 0x04, 0x05, 0x06, 0x2b ]


############################################################################

# Initialize parser
#arser = argparse.ArgumentParser(description="A simple script to demonstrate command-line arguments")

# Adding optional argument
#arser.add_argument("-n", "--name", type=str, help="Name of the user")
#arser.add_argument("-a", "--age", type=int, help="Age of the user")
#args = parser.parse_args()
#col = args.position
#sample = args.sample

#print col
#print sample


#
# globals
#

g_host       = '127.0.0.1'                   # default host
g_port       = 502                           # default Modbus-TCP port number
g_socket     = -1                            # socket
g_active     = False                         # connected flag
g_sequence   = 0                             # sequence number
g_unitid     = 0                             # unit/slave ID
g_address    = 0                             # address
g_data       = 1                             # data word to send
g_fc         = 3                             # function code
g_spacket    = bytearray(MAX_PACKET_SIZE)    # packet to be sent
g_slength    = 0                             # length of packet to be sent
g_rpacket    = bytearray(MAX_PACKET_SIZE)    # packet received
g_rlength    = 0                             # length of received packet
g_prompt     = 'MB>'                         # user prompt

KCDB1 = 0
KCDB2 = 0

############################################################################

def text2int(text, low, high):
    if len(text) == 0:
        return -1

    if text.isdigit():
        try:
            i = int(text)
        except ValueError:
            return -1
    elif len(text) >= 3:
        if text[0:2] == '0x':
            try:
                i = int(text, base=16)
            except ValueError:
                return -1
    else:
        return -1

    if i < low:
        return -1

    if i > high:
        return -1

    return i

############################################################################

def fc2text(fc):
    if fc not in SUPPORTED_FCS:
        fctext = 'Unsupported'
    elif fc == 0x01:
        fctext = 'Read Coils'
    elif fc == 0x02:
        fctext = 'Read Discrete Inputs'
    elif fc == 0x03:
        fctext = 'Read Holding Registers'
    elif fc == 0x04:
        fctext = 'Read Input Registers'
    elif fc == 0x05:
        fctext = 'Write Single Coil'
    elif fc == 0x06:
        fctext = 'Write Single Register'
    elif fc == 0x2b:
        fctext = 'Read ID Info'
    else:
        fctext = 'Unsupported'

    return fctext

############################################################################

def printprompt():
    global g_prompt

    print('{}'.format(g_prompt), end='', flush=True)

    return

############################################################################

def connect():
    global g_host
    global g_port
    global g_socket
    global g_active
    
    if g_active:
        print('Already connected - try disconnect command')
        return
    
    try:
        g_socket = socket.create_connection((g_host, g_port))
    except IOError as e:
        print('Connection failed: {}'.format(e))
        return
    except ConnectionRefusedError:
        print('Connecton refused')
        return
    except TimeoutError:
        print('Timeout')
        return

    g_active = True
    
    return    
    
############################################################################

def disconnect():
    global g_socket
    global g_active
    
    if g_active == False:
        print('Already disconnected')
        return
    
    g_socket.close()

    g_active = False
    
    return    
    
############################################################################

def incrementsequence():
    global g_sequence

    g_sequence += 1

    if g_sequence > 0xFFFF:
        g_sequence = 0

    return

############################################################################

def build():
    global g_spacket
    global g_slength
    global g_sequence
    global g_unitid
    global g_fc
    global g_address
    global g_data
    
    g_spacket[0]  = (g_sequence & 0xFF00) >> 8
    g_spacket[1]  = (g_sequence & 0x00FF) >> 0

    ### incrementsequence()
    
    g_spacket[2]  = 0x00
    g_spacket[3]  = 0x00
        
    g_spacket[6]  = g_unitid & 0xFF
    g_spacket[7]  = g_fc & 0xFF

    if g_fc in [ 0x01, 0x03, 0x04, 0x05 , 0x06 ]:
        g_slength = 12
        
        g_spacket[8]  = (g_address & 0xFF00) >> 8
        g_spacket[9]  = (g_address & 0x00FF) >> 0
        g_spacket[10] = (g_data & 0xFF00) >> 8
        g_spacket[11] = (g_data & 0x00FF) >> 0
    elif g_fc in [ 0x2b ]:
        g_slength = 8
    else:
        print('Error: Unsupported function code {}'.format(g_fc))        
        return False
        
    g_spacket[4] = ((g_slength - 6) & 0xFF00) >> 8
    g_spacket[5] = ((g_slength - 6) & 0x00FF) >> 0

    ### for i in range(0, g_slength):
    ###      print('{:02X} '.format(g_spacket[i]), end='')
    ### print('')        

    return True

############################################################################

def showold():
    global g_host
    global g_port
    global g_unitid
    global g_sequence
    global g_fc
    global g_address
    global g_data

    print('Host: {:20}   Port: {}'.format(g_host, g_port))
    print('Unit ID: {}   Seq: {}'.format(g_unitid, g_sequence))
    print('FC: {}   Address: {}   Data: {}'.format(g_fc, g_address, g_data))

    return

############################################################################

def show():
    global g_spacket
    global g_slength

    if build() != True:
        return

    if g_slength == 0:
        print('Send packet not yet built')
        return

    print('Bytes in packet to be sent:')

    for i in range(0, g_slength):
         print('{:02X} '.format(g_spacket[i]), end='')
    print('')        

    if g_slength < MIN_PACKET_SIZE:
        print('Send packet too short ({} bytes) - needs to be at least {} bytes'.format(g_slength, MIN_PACKET_SIZE))
        return

    if (g_spacket[2] != 0) or (g_spacket[3] != 0):
        print('Bytes at offset 2 and 3 must be zero')
        return

    datalength = (g_spacket[4] * 256) + g_spacket[5]

    if datalength != (g_slength - 6):
        print('Length encoding bytes at offset 4 and 5 are incorrect')
        return

    if datalength == 0:
        print('No actual Modbus data present in packet which is unusual')
        return

    seqnum = (g_spacket[0] * 256) + g_spacket[1]

    unitid = g_spacket[6]

    if datalength == 1:
        print('Modbus data only 1 byte long with unit ID = {} which is unusual'.format(unitid))
        return

    fc = g_spacket[7]

    if fc in [ 0x2b ]:
        if datalength > 2:
            print('Function code 0x2b has extra bytes which is unusual')
            return
    elif fc in [ 0x01, 0x03, 0x05 ]:
        if datalength != 6:
            print('Function code 0:{:02X} is incorrect length'.format(fc))
            return
    else:
        print('Function code 0x{:02x} is not supported by this utility'.format(fc))
        return

    addr = (g_spacket[8] * 256) + g_spacket[9] 
    data = (g_spacket[10] * 256) + g_spacket[11] 

    print('Sequence.....: 0x{:04x}   Data length: 0x{:04X}   Unit ID: 0x{:02X}'.format(seqnum, datalength, unitid))
    print('Function code: 0x{:02X}     {}'.format(fc, fc2text(fc)))
    print('Address......: 0x{:04X}   Data: 0x{:04X}'.format(addr, data))
    

    return

############################################################################

def showreceived():
    global g_rpacket
    global g_rlength

    if g_rlength < MIN_PACKET_SIZE:
        print('Received packet too short ({} bytes) - needs to be at least {} bytes'.format(g_rlength, MIN_PACKET_SIZE))
        return

    if (g_rpacket[2] != 0) or (g_rpacket[3] != 0):
        print('Bytes at offset 2 and 3 must be zero')
        return

    datalength = (g_rpacket[4] * 256) + g_rpacket[5]

    if datalength != (g_rlength - 6):
        print('Length encoding bytes at offset 4 and 5 are incorrect')
        return

    if datalength == 0:
        print('No actual Modbus data present in received packet which is unusual')
        return

    seqnum = (g_rpacket[0] * 256) + g_rpacket[1]

    unitid = g_rpacket[6]

    if datalength == 1:
        print('Received Modbus data only 1 byte long with unit ID = {} which is unusual'.format(unitid))
        return

    fc = g_rpacket[7]

    print('Sequence.....: 0x{:04x}   Data length: 0x{:04X}   Unit ID: 0x{:02X}'.format(seqnum, datalength, unitid))
    print('Function code: 0x{:02X}     {}'.format(fc, fc2text(fc)))

    if fc == 0x03:
        if datalength < 3:
             print('Error: no byte count')
             return

        bytecount = g_rpacket[8]

        if bytecount == 0:
             print('Info: byte count is zero which is unusual')
             return

        if (bytecount % 2) != 0:
            print('Error: byte count should be a multiple of 2 - it is {}'.format(bytecount))
            return

        if (datalength - 3) != bytecount:
            print('Error: byte count of {} does not match length of packet'.format(bytecount))
            return

        for i in range(0, bytecount // 2):
            offset = 9 + (i * 2)
            print('0x{:04X} '.format((g_rpacket[offset] * 256) + g_rpacket[offset+1]), end='')
        print('')
    else:
        for i in range(8, g_rlength):
            print('{:02X} '.format(g_rpacket[i]), end='')
        print('')        

    return

############################################################################

def send():
    global KCDB1
    global KCDB2
    global g_socket
    global g_active
    global g_spacket
    global g_slength
    global g_rpacket
    global g_rlength
    
    if g_active == False:
        print('Not connected')
        return

    if build() != True:
        return

    ### show()
    
    g_socket.send(g_spacket[0:g_slength])

    incrementsequence()

    countdown = 100

    while True:
        ready, dummy1, dummy2 = select.select([g_socket], [], [], 0.01)

        if len(ready) > 0:
            break

        countdown -= 1

        if countdown < 0:
            print('Timed out')
            return

    g_rlength = 0

    while True:
        ready, dummy1, dummy2 = select.select([g_socket], [], [], 0.01)

        ### print(ready)
      
        if len(ready) == 0:
            break;

        dbyte = g_socket.recv(1)

        g_rpacket[g_rlength] = dbyte[0]

        g_rlength += 1
        
    if g_rlength == 0:
        print('No data bytes recieved')
        return

    #print('KCDB1: ', g_rpacket[9])   # is 0x##00
    KCDB1 = g_rpacket[9]
    KCDB2 = g_rpacket[10]
    #print('KCDB2: ', g_rpacket[10]) # is 0x00##

    print('Bytes in received packet:')

    for i in range(0, g_rlength):
        print('{:02X} '.format(g_rpacket[i]), end='')
        #print(' i=',i) #KCDB put this line in
    print('')

    showreceived()
        
    return

############################################################################

def interact():
    global KCDB1
    global KCDB2
    global g_host
    global g_port
    global g_fc
    global g_unitid
    global g_address
    global g_data
    global g_sequence
    
    while True:
        build()
            
        connect()
        g_fc = 3 # Read Holding Registers
        g_address = 0x3247 # Address of floodLight HMI PB
        send() # Read
        #print('KCDB1 = ',KCDB1)
        #print('KCDB2 = ',KCDB2)

        for i in range(0,3):
            g_fc = 6 # Write Single Register
            KCDBData = KCDB1 << 8
            KCDBData = KCDB2 + KCDBData
            g_data = 0x0001 | KCDBData # write single bit floodlight on
            send()
            
            time.sleep(2)
            
            g_fc = 6 # Write Single Register
            KCDBData = KCDB1 << 8
            KCDBData = KCDB2 + KCDBData
            g_data = KCDBData ^ 0x0001 # write single bit floodlight off
            send()
            
            time.sleep(2)
            
        disconnect()
        break
    return

############################################################################

def main():
    global progname
    global g_host
    global g_port
    global g_prompt
    print('JetDock')
    parser = argparse.ArgumentParser()

    parser.add_argument('--host',      help='Modbus host',    default=g_host)
    parser.add_argument('--port',      help='Modbus port',    default=str(g_port))
    parser.add_argument('--prompt',    help='prompt string',  default=g_prompt)
    parser.add_argument('--auto',      help='auto connect',   action='store_true')
        
    args = parser.parse_args()

    g_host = args.host

    g_port = text2int(args.port, 0, 0xFFFF)

    if g_port == -1:
        print('{}: bad port value'.format(progname), file=sys.stderr)
        sys.exit(1)

    g_prompt = args.prompt

    if args.auto:
        printprompt()
        print('connect')
        connect()
        
    interact()
    
    return 0

############################################################################

progname = os.path.basename(sys.argv[0])

try:
    sys.exit(main())
except KeyboardInterrupt:
    print('')
    print('*** Program stopped by user typing Ctrl^C or Ctrl^Break ***')
    sys.exit(1)
     
# end of file

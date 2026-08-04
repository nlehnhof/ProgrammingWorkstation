This folder contains all the files and code necessary to program the Teltonika RuTX08 router.

For a walkthrough of how it all runs, see [`documentation/`](documentation/) in this folder.

FOLDERS
> Configs: The configuration files that set up and define the router settings. We change the network file to change the wifi ip address.
> crash_logs: Holds the files for any errors or failures.
> history: Holds miscellaneous files from an older version.
> labels: Holds the .txt files generated with the router updated information (ip, netmask, sn, etc.). The label files are automatically moved here after they are printed.
> og_configs: the original configuration files before they are updated according to the input airport and gate information (updates the ip addr). Config files are copied to configs folder before being updated to protect the original files.
> og_testfile: the original testfile FloodLighToggle.py with the default gate (127.0.0.1). This file is copied to testfile and then updated to the new ip address.
> router_labels: label .txt files are written here first. The Brady printer watches for files that are added and then prints them. Once printed, the files are moved to labels folder.
> testfile: the FloodLighToggle.py file that tests the newly programmed router to make sure it was programmed correctly. This file is the one copied to the BeagleBone Black.

FILES
> debugging.md: The file where I've recorded bugs, attempts, and the solution.
> FloodLighToggle.py: the file used to test connection between the router and PLC/HMI. Pulled from open-source.
> Excel files: Each excel file represents an airport. The airport should fill out the gates and gate information per the template. This data is then programmed to the router by updating the configs/testfile/etc..
> prog_dev.py: the file the application calls. It orchestrates a run; teltonika.py
  is what actually touches the router. Rewritten in e96074a onto the shared
  utilities in resources/utilities/, so the Excel, crash-log and label handling
  it used to spell out by hand now lives in one place and is shared with the
  Digi IX20.
    > run_main_script:
        > Reads the gate's IP/netmask/gateway from the airport sheet, looked up
          by column NAME (not position), and refuses to continue if the sheet
          data is unusable.
        > Runs teltonika.py to program the router, watching its output in a
          single pass for failures and the MAC address.
        > On failure: writes a crash log, stamps the sheet with a red
          timestamp, writes NO label, and stops.
        > On success: writes the label, stamps the sheet in black, then runs
          the test script.
    > run_test_script:
        > Copies the testfile over to the BBB and points it at the new gate IP.
        > Verifies FloodLighToggle.py arrived on the BBB.
        > Gives the BBB a static ip on the gate subnet to access the router,
          using the sheet's real netmask rather than assuming /24.
        > Verifies that static ip.
        > Runs the toggle test script (FloodLighToggle.py).
        > Records every failure to a crash log and stamps the test columns.
> RUTX_R_00.07.22.3_WEBUI.bin: the updated firmware file that is downloaded to the router.
> teltonika.py: the file that actually runs the programming of the router.
  NOT yet migrated to the shared utilities -- it still holds its own SSH code,
  fixed waits, and hardcoded addresses/passwords. See documentation/CODE_EXPLAIN.md.
    > Holds the logic for connecting to the BBB and Router. 
    > Performs all the tasks required for updating the configs/network file and testfile with the new ip address. 
    > Copies the configs and firmware to the router. Updates the router.
    > Copies the testfile to the BBB.
    > Reverts the configs and testfile in the main directory back to their defaults.
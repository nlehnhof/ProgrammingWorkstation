This code builds the Programming Workstation for Variable Devices. The idea is that the application can hold the various devices that we need to program, consolidating everything. The application should allow users to:
- add devices (with all their configs, firmware, programs, shared folders, data, etc.)
- program/test devices

DIR:
> build
    Holds the automatic build for the .bat file that allows launch from the desktop.
> core
    Holds the top-level modules for the application:
        > devices.json
            A json file that contains the device information. The device name is the main key. Device information may include: username, password, ip addr, etc.. Device information must include Name and Path.
        > main.py
            Launches the application.
        > manager.py
            A manager to control and manipulate devices.
            > Create Device
                When the user selects Create Device in the Add_Device_Page, the application takes the input keys and values and writes to the devices.json file. Each device requires a key that is "Name" and "Path". Path refers to the local folder that contains that device's firmware, configs, and programming functions. On Create Device, the folder is copied to the devices folder.
            > Get Credentials
                A function that based on the device name given, retrieves that device information from the json file.
            > Load Devices
                A function that loads the devices detailed in the json file to a dictionary within the device manager.
            > Save Devices
                After a device is added to the device dictionary within the device manager, save devices is called to push the new device to the json file.
            > manager = DeviceManager()
                Initializes one device manager for the entire application.
        > READme.md
            This description and explanation of the code and application.
        > requirements.txt
            Details the packages and versions required in the environment to run the application.
> device_types (Not Used - But possibly could be used later for variability)
    The functionality of how the devices communicate with each other and how to connect with them. Currently not used except for in the add device page. An abstract base class builds the foundation, requiring each type have a connect, disconnect, upload, and run function.
    > __init__
        Get the device types and their functions. Make them accessible for the application.
> devices
    The folder where added devices are stored. Each devices is a folder that contains the firmware, configs, and code required to program the specific device.
    > __init__
        Makes a list of the available devices accessible to the application.
> logs
    Each time the application runs, the outputs are written to a log_datetime.txt file. Any errors or outputs are recorded and saved in this folder.
> pages
    The top-level directory that contains the actual application pages.
    > add_device_page.py
        Users can add device information. 
    > connection_page.py
        A page that shows the correct wiring of the device (router). Before programming, the user must select "yes" to confirm that the wiring is correct.
    > error_log_page.py
        This page holds the logic that compiles all outputs--print statements and errors--into the log file. It also creates the pop-up window that displays the errors in the application.
    > home_page.py
        The home page for the application. It welcomes the user and provides two options: add device, program device.
    > main_window.py
        Holds the stacked_widget logic to allow navigation between the pages. No display that is the main window. This is the high-level class for navigation.
    > program_page.py
        The UI and logic to allow the device to be programmed. Currently, it is only set up for the router. User selects the device, airport, and gate, then scans the qr code on the router to get the router username/pswd. On "submit", and "program device", the application runs the prog_dev.py file in the device's folder (devices/{device_name}).
> resources
    This folder holds the miscillaneous things to streamline the application.
    > images
        Holds the image used for instructions (connection_page.py).
    > packages
        Holds all the packages needed in the environment.
    > past_versions
        Holds the old versions of the application for version control.
    > utilities
        Excel functions, fonts, and network utilities (ip validity).
> router_labels
    Holds the .txt files that contain the information for the label print-out. The printer listens for additions to this folder for automated printing.
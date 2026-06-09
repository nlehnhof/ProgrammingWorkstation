This code builds the Programming Workstation for Variable Devices. The idea is that the application can hold the various devices that we need to program, consolidating everything. The application should allow users to:
- add devices (with all their configs, firmware, programs, shared folders, data, etc.)
- edit devices
- program devices
- test devices

I'm going to start working on abstracting devices.
Each device needs:
* Functions:
    - connect
    - disconnect
    - upload
    - run
* Basics:
    - Authentication Style
    - username
    - pswd
* Files:
    - configs?
    - firmware?
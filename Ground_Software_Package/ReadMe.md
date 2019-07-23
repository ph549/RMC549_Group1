# Software Overview

## serial_communication.py

This file is used to communicate with the Arduino (recieving downlink data and sending uplink data) and logs the data to a .txt file on computer. See documentation within the file for how to operate.

## live_plotting.py

This file is used to collected and parse the data from the log .txt files and plot them in real time during the flight for the ground station operators. 
See documentation within the file for how to operate.

## real_time_plotting_new.py

2019: use this file for plotting the data during the flight.
I apologize for the inconsistent naming.
Several variables need to be manually set beforehand: see note to users 1 and the section below the import statements. 

## generate_dummy_logs.py

This file is used to generate dummy log files for the purpose of running/debuging the live_plotting.py script without actually being connected to a LoRa device and recieving data from another LoRa device.

## arduino_ground Folder

This folder contains the file of the program that runs on the ground station arduino.
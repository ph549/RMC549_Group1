# generate log files to test live plots
import time

# get the data to use: data file from last year's flight
file_name = r'C:/Users/kimdu/Documents/ph549/20190718_data_test.txt'
data = open(file_name, 'rb').readlines()
for i in range(len(data)):
    data[i] = data[i].decode()[:-2]

# save the data at a normal rate
fil = r'C:/Users/kimdu/Documents/ph549/Telemetry_logs/test.txt'
for i in range(len(data)):
    with open(fil, 'a') as file:
        file.write(data[i]+"\n")
    time.sleep(3)
    print("did it")
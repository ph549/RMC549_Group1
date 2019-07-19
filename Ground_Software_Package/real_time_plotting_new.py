'''
file: live_plotting.py
Created by: Curtis Puetz 2018-07-08
Improved by: Kimberlee Dube 2019-07-16

note to users:

1) you must hard code in the location you want to LOAD from your log files within the
read_last_line_in_data_log() function on the line:
log_file_path = r"C:\\Users\puetz\Desktop\Telemtry_logs"

2) the 'plot_pause_for_interactive' variable should be a little bit faster than the rate of
data being written to the log files in serial_communication.py (i.e. 'check_for_data_delay'
variable). It can easily be 1 second. This allows for CPU usage to remain low, since the program
does not check the log file as often.

3) you must be generating data for this program to do anything. So either serial_communication.py
needs to be running and receiving data from the balloon, or generate_dummy_logs.py needs to be
running to generate artificial data. In the latter, a text file needs to be supplied to
generate_dummy_logs.py with reasonable data, and the log_file_paths in both 'generate_dummy_logs.py'
and this program need to be appropriate.

4) the png files used for the longitude latitude maps needs to be set to your location (you also
need to generate the constrains of the picture manually)
'''

import datetime
import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.image as mpimg
import cartopy.crs as ccrs
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER

# **** VARIABLES TO DEFINE BEFORE FLIGHT **************
location_of_base_image = r'C:/Users/kimdu/Documents/ph549/basemap.png'

home_lat = 52.4904018
home_lon = -105.719035

# coordinates of background image
left_lon = -107.7
right_lon = -103.7
bottom_lat = 50.7
top_lat = 54.3

approx_start_time = datetime.datetime(2019, 7, 17, 1, 1, 1)
approx_end_time = datetime.datetime(2019, 7, 17, 23, 1, 1)
# ****************************************************

plt.style.use('plotstyle.mplstyle')


def make_map(projection=ccrs.PlateCarree()):
    """
    Code from https://ocefpaf.github.io/python4oceanographers/blog/2015/06/22/osm/
    """
    fig, ax = plt.subplots(figsize=(9, 13),
                           subplot_kw=dict(projection=projection))
    gl = ax.gridlines(draw_labels=True)
    gl.xlabels_top = gl.ylabels_right = False
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    return fig, ax


def save_map_image(loc):
    """
    Code adapted from https://ocefpaf.github.io/python4oceanographers/blog/2015/06/22/osm/
    Grab google maps image covering geographic area given by 'extent'
     and save image to file for use as background map.
    Use this function to generate the basemap image. It is also possible to plot data
    directly on the cartopy object (map_ax) which provides higher resolution,
     however that requires an internet connection onsite.
    :param loc: path defining location to save image
    :return: nothing
    """

    import cartopy.io.img_tiles as cimgt
    extent = [left_lon, right_lon, bottom_lat, top_lat]
    request = cimgt.GoogleTiles()
    map_fig, map_ax = make_map(projection=request.crs)
    map_ax.set_extent(extent)
    map_ax.add_image(request, 10)
    # put star at launch site
    map_ax.plot(home_lon, home_lat, marker='*', color='black', markersize=10,
                transform=ccrs.Geodetic())
    map_ax.savefig(loc)


def set_up_plots():
    '''
    Set the the axes of the desired plots
    Written by Curtis Puetz 2018-07-07
    Completely changed by Kimberlee Dube 2019-07-17
    :return: None
    '''

    fig, axes = plt.subplots(2, 2, figsize=(20, 15), num=1,
                             sharex=False, sharey=False)
    ax0 = axes[0, 0]
    ax0.set_title('Altitude')
    ax0.set_xlabel('Time')
    ax0.set_ylabel('Altitude [m]')

    ax1 = axes[0, 1]
    ax1.set_title('Internal Temperature')
    ax1.set_xlabel('Temperature [$\degree$C]')
    ax1.set_ylabel('Altitude [m]')

    ax2 = axes[1, 1]
    ax2.set_title('External Temperature')
    ax2.set_xlabel('Temperature [$\degree$C]')
    ax2.set_ylabel('Altitude [m]')

    ax3 = axes[1, 0]
    ax3.set_title('Geiger Counters')
    ax3.set_xlabel('Count/Time')
    ax3.set_ylabel('Altitude [m]')
    ax3.legend([Line2D([0], [0], color='red', lw=4),
                Line2D([0], [0], color='blue', lw=4)], ['C1', 'C2'])
    plt.tight_layout()

    map_fig, map_ax = plt.subplots(figsize=(9, 13))
    map_ax.set_title("Where my payload at?")
    img = mpimg.imread(location_of_base_image)
    imgplot = map_ax.imshow(img)

    return axes, map_ax, img


def plot_data(data, header_data, axes, map_ax, img):
    '''
    Plot a single data point for each of the plots defined in 'set_up_plots()'
    This will occur each time a comma separated data list is received

    Written by Curtis Puetz 2018-07-07
    Rewritten by Kimberlee Dube 2019-07-17

    :param data: the list of data generated from the downlinked comma separated data list
    :return: None
    '''

    pi_time = datetime.datetime.strptime(data[0], '%Y%m%d_%X.%f')
    # isolate the floats and save them in a dictionary (while checking the units of altitude)
    data = data[1:]  # removes the time datetime value
    header_data = header_data[1:]  # removes the time datetime value
    data_dict = dict(zip(header_data, data))
    if data_dict['Altu'] == "KM":
        alt_factor = 1000
    else:
        alt_factor = 1
    data_dict['Alt'] *= alt_factor
    del data_dict['Altu']
    del data_dict['NS']
    del data_dict['EW']
    data_float = [[] for i in range(len(data_dict))]
    for i, dai in enumerate(list(data_dict.values())):
        if dai == "":
            data_float[i] = ""
        else:
            data_float[i] = float(dai)
    data_dict = dict(zip(list(data_dict.keys()), data_float))

    # Change in altitude over time
    if not data_dict['Alt'] == "":
        axes[0, 0].scatter(pi_time, data_dict['Alt'], color='green')
        # Need to manually set the approximate flight start
        # and end times for the plot to look nice
        axes[0, 0].set_xlim([approx_start_time, approx_end_time])

    # Altitude profile of internal temperature
    if not data_dict['TC'] == "" and not data_dict['Alt'] == "":
        axes[0, 1].scatter(data_dict['TC'], data_dict['Alt'], color='green')

    # Altitude profile of external temperature
    if not data_dict['temp'] == "" and not data_dict['Alt'] == "":
        axes[1, 1].scatter(data_dict['temp'], data_dict['Alt'], color='green')

    # Altitude profiles of Geiger counter measurements
    if not data_dict['C1'] == "":
        axes[1, 0].scatter(data_dict['C1'], data_dict['Alt'], color='red', label='C1')
    if not data_dict['C2'] == "":
        axes[1, 0].scatter(data_dict['C2'], data_dict['Alt'], color='blue', label='C2')

    # Map of geographic location
    if not data_dict['LtDgMn'] == "" and not data_dict['LnDgMn'] == "":
        lat = int(data_dict['LtDgMn']/100) + (data_dict['LtDgMn'] - int(data_dict['LtDgMn']/100)*100)/60
        lon = -(int(data_dict['LnDgMn']/100) + (data_dict['LnDgMn'] - int(data_dict['LnDgMn']/100)*100)/60)

        # change to sask coords for testing
        #lat = 52 + (lat % 1)
        #lon = -105 + (lon % 1)

        index_y = np.interp(lat, np.linspace(bottom_lat, top_lat, len(img)), np.arange(0, len(img))[::-1])
        index_x = np.interp(lon, np.linspace(left_lon, right_lon, len(img[0])), np.arange(0, len(img[0])))

        # map_ax.plot(lon, lat, marker='o', color='red', markersize=5,
        #            transform=ccrs.Geodetic())
        map_ax.scatter(index_x, index_y, marker='o', color='red')

    plt.pause(0.05)


def read_last_line_in_data_log():
    """
    This function will read the last line in the data log file and return it
    Written by Daniel Letros, 2018-07-03
    :return: None
    """
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d")
    log_file_path = r'C:/Users/kimdu/Documents/ph549/Telemetry_logs'
    log_file_path += os.sep + timestamp
    file_name = log_file_path + os.sep + timestamp + "_data.txt"
    # file_name = r'C:/Users/kimdu/Documents/ph549/Telemetry_logs/test.txt' # test generated data
    try:
        with open(file_name, 'rb') as f:
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b'\n':
                f.seek(-2, os.SEEK_CUR)
            content = f.readline().decode()
    except:
        with open(file_name, 'rb') as f:
            content = f.readlines()[-1].decode()
    return content


if __name__ == '__main__':

    header_2018 = ['PiTS', 'ATSms', 'UTC', 'LtDgMn', 'NS', 'LnDgMn', 'EW',
                   'Nsat', 'Alt', 'Altu', 'Acxms2', 'Acyms2', 'Aczms2', 'Gyxrs',
                    'Gyyrs', 'Gyzrs', 'MgxuT', 'MgyuT', 'MgzuT', 'Elxdg', 'Elydg',
                    'Elzdg', 'LAcxms2', 'LAcyms2', 'LAczms2', 'Gvxms2', 'Gvyms2',
                    'Gvzms2', 'TC', 'SyCl03', 'GyCl03', 'AcCl03', 'MgCl03',
                    '', 'C1', 'C2', 'SC', 'RSSI']

    header = ['PiTS', 'ATSms', 'UTC', 'LtDgMn', 'NS', 'LnDgMn', 'EW',
              'Nsat', 'Alt', 'Altu', 'Acxms2', 'Acyms2', 'Aczms2', 'Gyxrs',
              'Gyyrs', 'Gyzrs', 'MgxuT', 'MgyuT', 'MgzuT', 'Elxdg', 'Elydg',
              'Elzdg', 'LAcxms2', 'LAcyms2', 'LAczms2', 'Gvxms2', 'Gvyms2',
              'Gvzms2', 'TC', 'SyCl03', 'GyCl03', 'AcCl03', 'MgCl03',
              'C1', 'C2', 'GN', 'BBL1', 'IRL1', 'BBL2', 'IRL2',
              'BBL3', 'IRL3', 'temp']

    plot_pause_for_interactive = 4
    axes, map_ax, img = set_up_plots()
    plt.ion()
    hold = ""
    while True:
        data = read_last_line_in_data_log()
        if data == hold:
            plt.pause(plot_pause_for_interactive)
            continue
        hold = data
        data = data[:-2]  # remove newline character
        print(data)
        if data[0] == "P":  # first character of header string
            header_data = data.split(',')
        elif data[0] == '2':  # first character of a row of good data (starts with year)
            data = data.split(',')
            plot_data(data, header, axes, map_ax, img)





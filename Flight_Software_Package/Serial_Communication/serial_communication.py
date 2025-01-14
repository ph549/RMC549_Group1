from Common.FSW_Common import *


class SerialCommunication(FlightSoftwareParent):
    """
    This class is designed to handle generic serial communication for the RMC 549 balloon(s).
    There is an enforced "call and respond" scheme but it can be intentionally circumvented by when needed.

    The i2c photosensors are handled by this class as well. It is not a elegant way of integrating the sensors code wise
    but it was the quickest so it was done due to time constraints.

    Written by Daniel Letros, 2018-06-27
    """

    def __init__(self, logging_object: Logger, list_of_photosensors: list) -> None:
        """
        Init of class.

        Written by Daniel Letros, 2018-06-27

        :param logging_object: Reference to logging object.
        :param list_of_photosensors: List of photosensors.
        """
        # Serial_communication class will handle the data acq from the i2c pi sensors.
        # If they are good load them up to be queued on data calls.
        self.list_of_photosensors = []
        for sensor in list_of_photosensors:
            if sensor.sensor_is_valid:
                self.list_of_photosensors.append(sensor)

        self.default_buadrate  = 9600  # Buadrate of the serial communication.
        self.default_timeout   = 8     # Default time out on serial communication calls.
        self.main_delay        = 0.5   # Main delay for the thread.
        self.reconnection_wait = 5     # Time to wait when attempting a reconnection if something is wrong.
        self.arduino_reset_pin = 23    # A BCM layout pi pin which can trigger a power cycle on the arduino.

        super().__init__("SerialCommunication", logging_object) # Run parent init.

        # Keep track of active serial ports and if they have a problem or not.
        self.port_list        = dict()
        self.ports_are_good   = False

        # Locks so different threads won't try to access the same variable at the same time.
        self.serial_mutex          = threading.Lock()  # General lock on serial communication
        self.uplink_commands_mutex = threading.Lock()  # Lock on accessing and using uplink commands

        # Keeps track uplink commands and if they have been processed.
        self.last_uplink_commands_valid         = False
        self.last_uplink_seen_by_system_control = False
        self.last_uplink_commands               = [""]

        self.expect_read_after_write = False  # Used to facilitate a call and respond system by default.
                                              # Can be circumvented by changing state elsewhere in code.

        self.read_request_buffer  = []  # buffer of ports to read from, [port, message_type], ...]
        self.write_request_buffer = []  # buffer of ports to write to, [[port, message], ...]

        try:
            # Configure the cutoff pin
            if self.system_name == 'MajorTom' or self.system_name == 'Rocky' or self.system_name == 'ColonelTom' or self.system_name == 'Creed':
                GPIO.setwarnings(False)
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.arduino_reset_pin, GPIO.OUT, initial=GPIO.LOW)
        except:
            self.log_error("Could not configure BCM pin [%s]"% self.arduino_reset_pin)

    def load_yaml_settings(self)->None:
        """
        This function loads in settings from the master_config.yaml file.

        Written by Daniel Letros, 2018-06-30

        :return: None
        """
        dirname = os.path.dirname(__file__)
        filename = os.path.join(dirname, self.yaml_config_path)
        with open(filename, 'r') as stream:
            content = yaml.load(stream)['serial_communication']
        self.default_buadrate  = content['default_baud_rate']
        self.default_timeout   = content['default_timeout']
        self.reconnection_wait = content['reconnection_wait']
        self.main_delay        = content['main_delay']
        self.arduino_reset_pin = content['arduino_reset_pin']


    def find_serial_ports(self, baudrate: int = None, timeout: float = None) -> None:
        """
        This function finds active serial ports and makes the serial connections. This function should
        only be run on startup or if something has changed with the connections.

        Code from : https://stackoverflow.com/questions/12090503/listing-available-com-ports-with-python

        Adapted by: Daniel Letros, 2018-06-27

        :param baudrate: buadrate of the connection
        :param timeout: Communication timeout
        :raises EnvironmentError: On unsupported platform
        :return: List of the serial ports available
        """
        self.start_function_diagnostics("find_serial_ports")

        if baudrate is None:
            baudrate = self.default_buadrate
        if timeout is None:
            timeout = self.default_timeout

        # Clear old connections if any.
        for port in self.port_list:
            self.port_list[port].close()
        self.port_list.clear()

        # Determine ports on current OS.
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty".
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            # Try opening port. If fail ignore it, else add it.
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass

        # Open ports.
        if self.system_name == 'MajorTom' or self.system_name == 'Rocky' or self.system_name == 'ColonelTom' or self.system_name == 'Creed':
            try:
                result.remove('/dev/ttyAMA0')  # AMA0 seems to be always "active" as is the Pi's PL011, remove it.
            except:
                self.log_error("Could not remove [/dev/ttyAMA0] from port list.")
        for port in result:
            self.port_list[port] = serial.Serial(port=port, baudrate=baudrate,
                               parity=serial.PARITY_NONE,
                               stopbits=serial.STOPBITS_ONE,
                               bytesize=serial.EIGHTBITS,
                               timeout=timeout,
                               writeTimeout=timeout)

        self.end_function_diagnostics("find_serial_ports")

    def readline_from_serial(self, port: str, type: str) -> None:
        """
        This function will read data on the port up to a EOL char and return it.

        If the expected information to be read in is science data then append the i2c photosensor stuff
        onto it.

        Written by Daniel Letros, 2018-06-27

        :param port: port to do the communication over.
        :param type: type of data expected, dictated which file it is logged to.
        :return: None
        """
        self.start_function_diagnostics("readline_from_serial")
        try:
            # Read in data and strip it of unwanted chars.
            new_data = self.port_list[port].readline().decode('utf-8').strip()
            new_data = new_data.replace("\n", "")
            new_data = new_data.replace("\r", "")
            if new_data == "" and type != "RX":
                self.log_error("[%s] returned no data. Attempting reconnect." % port)
                self.reset_serial_connection()
                return
            elif type == "DATA":
                # Try to get sensor data quickly. Should be multithreaded for
                # max time resolution but this has to be quick and dirty right now.
                current_sensor_data   = []
                for sensor in self.list_of_photosensors:
                    if sensor.sensor_is_valid:
                        current_sensor_data.append(sensor._get_data())
                # Append Pi photo sensor data if valid.
                for data in current_sensor_data:
                    # Valid photo sensor so append the header information.
                    if new_data[-1] != ",":
                        # Append ',' if not there at end.
                        new_data += ","
                    new_data += str(data[0])
                    new_data += ","
                    new_data += str(data[1])
                # remove ',' at end if needed.
                if new_data[-1] == ",":
                    new_data = new_data[0:-1]

                self.log_data(new_data)
            elif type == "ID":
                self.log_id(new_data)
            elif type == "HEADER":

                # Append Pi photo sensor data if valid.
                for sensor in self.list_of_photosensors:
                    if sensor.sensor_is_valid:
                        # Valid photo sensor so append the header information.
                        if new_data[-1] != ",":
                            # Append ',' if not there at end.
                            new_data += ","
                        new_data += sensor.data_header_addition
                    # remove ',' at end if needed.
                    if new_data[-1] == ",":
                        new_data = new_data[0:-1]
                new_data = "PiTS," + new_data
                self.log_header(new_data)
            elif type == "TX":
                self.log_tx_event(new_data)
            elif type == "RX" and new_data != "":
                self.log_rx_event(new_data)
                # Assume uplink commands will be a comma delimited list joined in one string.
                with self.uplink_commands_mutex:
                    self.last_uplink_commands               = new_data.split(',')
                    self.last_uplink_commands_valid         = True
                    self.last_uplink_seen_by_system_control = False
            if new_data != "":
                self.log_info("received [%s] information over [%s]" % (type, port))

        except Exception as err:
            self.log_error("readline_from_serial %s"%str(err))
            self.reset_serial_connection()
        self.end_function_diagnostics("readline_from_serial")

    def write_to_serial(self, port: str, message) -> None:
        """
        This function will write data to the port during serial communication.

        Written by Daniel Letros, 2018-06-27

        :param port: The port for the serial communication
        :param message: The message/data to write
        :return: None
        """
        self.start_function_diagnostics("write_to_serial")
        # self.log_info("sending [%s] over [%s] with type [%s]" % (message, port,type(message)))
        if type(message) is str:
            msg = message.encode('utf-8')
        if type(message) is bytes:
            msg = message
        try:
            # self.log_info("msg form is [%s] and is of type %s" % (msg,type(msg)))
            self.port_list[port].write(serial.to_bytes(msg))
            if message is not "RX":
                message.strip()
                message = message.replace("\n", "")
                message = message.replace("\r", "")
                # self.log_info("sent [%s] over [%s]" % (message, port))
        except Exception as err:
            self.log_error("write_to_serial %s with message %s and the message is a %s" % (str(err),str(msg),type(msg)))
            self.reset_serial_connection()
        self.end_function_diagnostics("write_to_serial")

    def log_id(self, log_message: str) -> None:
        """
        This function will que the input message to be logged as a device id line to the notifications log file.

        Written by Daniel Letros, 2018-06-27

        :param log_message: ID message to log
        :return: None
        """
        self.logger.notifications_logging_buffer.append("ID << %s << %s << %s << %s\n" % (
            datetime.datetime.utcnow().strftime("%Y%m%d_%H:%M:%S.%f"), self.system_name, self.class_name, log_message))

    def log_header(self, log_message: str) -> None:
        """
        This function will que the input message to be logged as a data header to the notifications log file.

        Written by Daniel Letros, 2018-06-27

        :param log_message: Header message to log
        :return: None
        """
        self.logger.notifications_logging_buffer.append("HEADER << %s << %s << %s << %s\n" % (
            datetime.datetime.utcnow().strftime("%Y%m%d_%H:%M:%S.%f"), self.system_name, self.class_name, log_message))

    def log_tx_event(self, log_message: str) -> None:
        """
        This function will que the input message to be logged as a TX sent event to the notifications log file.

        Written by Daniel Letros, 2018-07-03

        :param log_message: TX message to log
        :return: None
        """
        self.logger.notifications_logging_buffer.append("TX << %s << %s << %s << %s\n" % (
            datetime.datetime.utcnow().strftime("%Y%m%d_%H:%M:%S.%f"), self.system_name, self.class_name, log_message))

    def log_rx_event(self, log_message: str) -> None:
        """
        This function will que the input message to be logged as a RX received event to the notifications log file.

        Written by Daniel Letros, 2018-07-04

        :param log_message: RX message to log
        :return: None
        """
        self.logger.notifications_logging_buffer.append("RX << %s << %s << %s << %s\n" % (
            datetime.datetime.utcnow().strftime("%Y%m%d_%H:%M:%S.%f"), self.system_name, self.class_name, log_message))

    def reset_serial_connection(self):
        """
        This function attempts a reset and reconnection to all serial connected devices in event of fail.

        Written by Daniel Letros, 2018-07-06

        :return: None
        """
        self.start_function_diagnostics("reset_serial_connection")
        # Something is wrong. Wait for some data transition to get stable.
        time.sleep(self.reconnection_wait)
        if self.system_name == 'MajorTom' or self.system_name == 'Rocky' or self.system_name == 'ColonelTom' or self.system_name == 'Creed':
            # Do power cycle pin for arduino.
            GPIO.output(self.arduino_reset_pin, GPIO.LOW)
            time.sleep(self.reconnection_wait/2)
            GPIO.output(self.arduino_reset_pin, GPIO.HIGH)
        # Do a full communication reset in this software.
        self.ports_are_good          = False
        self.read_request_buffer     = []
        self.write_request_buffer    = []
        self.expect_read_after_write = False
        for port in self.port_list:
            self.port_list[port].reset_input_buffer()
            self.port_list[port].reset_output_buffer()
        self.end_function_diagnostics("reset_serial_connection")

    def run(self):
        print("%s << %s << Starting Thread" % (self.system_name, self.class_name))
        while self.should_thread_run:
            msg="No assigned"
            if len(self.write_request_buffer) > 0:
                wmsg=self.write_request_buffer
                # self.log_info("Messages in buffer: %s" % str(wmsg))
                # self.log_info("To send: %s at type %s" % (str(wmsg[0]),type(wmsg[0][1])))
                if not self.expect_read_after_write:
                    msg=wmsg
            elif len(self.read_request_buffer) > 0:
                rmsg=self.read_request_buffer
                # self.log_info("Reading: %s" % str(rmsg))
                if self.expect_read_after_write:
                    msg=rmsg
            try:
                if len(self.read_request_buffer) > 0 and self.expect_read_after_write:
                    self.readline_from_serial(self.read_request_buffer[0][0], self.read_request_buffer[0][1])
                    del self.read_request_buffer[0]
                    self.expect_read_after_write = False
                elif len(self.write_request_buffer) > 0 and not self.expect_read_after_write:                    
#                    self.log_info("sending [%s] " % self.write_request_buffer[0][1])
#                    self.log_info("over [%s] " % self.write_request_buffer[0][0])
#                    self.log_info("with type [%s]" % type(self.write_request_buffer[0][1]))
                    self.write_to_serial(self.write_request_buffer[0][0], self.write_request_buffer[0][1])
                    del self.write_request_buffer[0]
                    self.expect_read_after_write = True
            except Exception as err:
                self.log_error("Main function error [%s] on message %s" % (str(err),str(msg)))

            time.sleep(self.main_delay)
        print("%s << %s << Exiting Thread" % (self.system_name, self.class_name))

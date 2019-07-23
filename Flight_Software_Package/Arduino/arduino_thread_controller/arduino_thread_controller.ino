/*
   file: arduino_thread_controller.ino

   Main program for the retrieval of data from balloon payload sensors.
   Designed for an Adafruit Feather M0 Adalogger and to be powered through
   its micro-USB port by a Raspberry Pi. The Pi also uses serial communication
   through the micro-USB port to send instructions to the arduino, and the
   arduino sends data back to the Pi over this connection.

   Telemetry is performed with LoRa using the library RH_RF95.h, found here:
   https://github.com/adafruit/RadioHead
*/

#include <SensorThread.h>     // library of customized threads for each sensor type
#include <ThreadController.h> // use ThreadController to manage all sensor threads
#include <RH_RF95.h>
#include <Adafruit_Sensor.h>
#include <Sydafruit_TSL2561_U.h>

// Telemetry definitions
#define RFM95_CS 5            // slave select pin
#define RFM95_RST 6           // reset pin
#define RFM95_INT 9           // interrupt pin
#define RF95_FREQ 434.0       // frequency, must match ground transceiver!
#define LED 13                // LED pin
// Singleton instance of the radio driver
RH_RF95 rf95(RFM95_CS, RFM95_INT);

// Comma separated List of unprocessed commands from ground station
String ground_commands = "";

// create handlers for IMU and pressure sensor
Adafruit_BNO055 bno = Adafruit_BNO055(55);

// create thread for each sensor
SensorThread* gps_thread = new GPSSensorThread();
SensorThread* imu_thread = new IMUSensorThread(&bno);
SensorThread* geiger_thread = new GeigerSensorThread(10, 11, 12, 13);
SensorThread* light_thread = new LightSensorThread();
SensorThread* ambient_temp_thread = new AmbientTempSensorThread();

// create controller to hold the threads
ThreadController controller = ThreadController();

// booleans to check if sensors should be run
bool doIMU;
bool doTelemetry;


bool byteMatch(char b1, char b2, bool fold) {
  //Serial.print("ByteMatching ");Serial.print((int)b1);Serial.print(" to ");Serial.println((int)b2);
  if (fold) return (map(b1, 65, 90, 97, 122) == map(b2, 65, 90, 97, 122));
  if (!fold) return (b1 == b2);
}


bool listMatch(char b1, char* b2, int numComp, bool fold) {
  for (int i = 0; i < numComp; i++) {
    if (byteMatch(b1, *(b2 + i), fold)) {
      return 1;
      break;
    }
  }
  return 0;
}


bool likeStr(char* ins, int off, char* comps, int num, bool fold) {
  for (int i = 0; i < num; i++) {
    if (!byteMatch(*(ins + i + off), *(comps + i), fold)) {
      return 0;
      break;
    }
  }
  return 1;
}

void setup() {
  // ------------------------ Changing the baud rate of GPS Serial1 port ---------------------------
  Serial1.begin(4800);
  Serial1.write("$PTNLSPT,115200,8,N,1,4,4*11\r\n");
  delay(1000);
  Serial1.end();
  // -----------------------------------------------------------------------------------------------

  Serial1.begin(115200); // Setting up GPS serial com
  Serial1.write("$PTNLSCR,,,,,,,3,,*5B\r\n"); // A safety precaution to keep GPS module in the AIR mode.
  delay(1000);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  // Initialize the IMU
  doIMU = bno.begin();
  if (!doIMU) {
    // could send an error message to the Pi here
  }

  // Initialize telemetry
  pinMode(RFM95_RST, OUTPUT);
  pinMode(LED, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);
  delay(100);
  // manual reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);
  doTelemetry = rf95.init();
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  doTelemetry = doTelemetry && rf95.setFrequency(RF95_FREQ);
  // Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on
  // The default transmitter power is 13dBm, using PA_BOOST.
  // If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then
  // you can set transmitter powers from 5 to 23 dBm:
  rf95.setTxPower(23, false);   // set power to maximum of 23 dBm
  delay(1000);

  // set correct serial port to talk to Pi
  // not related to telemetry
  Serial.begin(115200);

  // add each thread to the controller
  controller.add(gps_thread);
  controller.add(imu_thread);
  controller.add(geiger_thread);
  controller.add(light_thread);
  controller.add(ambient_temp_thread);
}

void loop() {
  // put main program code here, to loop forever:

  String full_data;  // full data array to send to Pi
  String temp_data;  // temporary data holder for each sensor
  char pi_command[251]; // command from Pi to do something
  int j = 0;
  String deviceName = "MajorTomLight";
  char blanks[3]={10, 13, 32};

  // check for instruction from Pi
  if (Serial.available() > 0) {
    int len = Serial.available();
    // read in instruction
    while (Serial.available() > 0) {
      pi_command[j++] = (char)Serial.read();
    }
    pi_command[j--]=0;
    //Serial.print("got command: ");Serial.println(pi_command);//Serial.println(j);
    while (listMatch(pi_command[j], blanks,3,0)) { //remove whitespace, newline, and line feed
      //Serial.print((int)pi_command[j]);
      pi_command[j] = 0;
      j-=1;
    }
    //Serial.print(pi_command);Serial.println(j);

    if (likeStr(pi_command, 0, "ID", 2, 1)) {
      // Pi has asked for arduino ID and sensor(s) ID.
      full_data.concat(deviceName);
      for (int i = 0; i < controller.size(); i++)
      {
        // get sensor ID
        temp_data = ((SensorThread*) controller.get(i))->getSensorName();
        // append to final data output
        full_data.concat(",");
        full_data.concat(temp_data);
      }
      // Send data to Pi
      Serial.println(full_data);
    }

    else if (likeStr(pi_command, 0, "HEADER", 6, 1)) {
      // Pi has asked for data headers
      full_data.concat("ATSms");
      for (int i = 0; i < controller.size(); i++)
      {
        // get sensor ID
        temp_data = ((SensorThread*) controller.get(i))->getSensorHeader();
        // append to final data output
        full_data.concat(",");
        full_data.concat(temp_data);
      }
      // Send data to Pi
      Serial.println(full_data);
    }

    else if (likeStr(pi_command, 0, "DATA", 4, 1)) {
      // Pi has asked for new sensor data
      // This will instruct each sensor thread to measure and save its data
      controller.run();
      // get the current time
      unsigned long time = millis();
      full_data.concat(time);
      for (int i = 0; i < controller.size(); i++) {
        // get sensor data
        temp_data = ((SensorThread*) controller.get(i))->getSensorData();
        // append to final data output
        full_data.concat(",");
        full_data.concat(temp_data);
      }
      // Send data to Pi
      Serial.println(full_data);
    }

    else if (likeStr(pi_command, 0, "TX", 2, 1)) {
      // Pi has asked to transmit data to ground
      if (doTelemetry) {
        char radiopacket[len - 1];
        memcpy(&radiopacket[0], &pi_command[2], len - 2);

        // send data to the ground
        rf95.send((uint8_t *)radiopacket, len - 1);
        //Serial.println(radiopacket);
        rf95.waitPacketSent();
      }
      // send OK to the Pi
      Serial.println("OK");
    }
    else if (likeStr(pi_command, 0, "RX", 2, 1)) {
      // Pi has asked for commands from ground
      // Send the command list
      Serial.println(ground_commands);
      // Clear the command list
      ground_commands = "";
    }
    else {// Do nothing. Pi will know of error on timeout.
    }
  }

  // Check for commands from ground
  if (doTelemetry && rf95.available()) {
    // Receive the message
    uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
    uint8_t len = sizeof(buf);
    if (rf95.recv(buf, &len)) {
      // save to command list
      ground_commands.concat(String((char*)buf));
    }
    // append signal strength
    ground_commands.concat(String(rf95.lastRssi()));
    ground_commands.concat(",");
  }
}

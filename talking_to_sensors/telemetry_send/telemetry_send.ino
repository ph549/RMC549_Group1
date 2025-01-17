#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <utility/imumaths.h>
#include <SPI.h>
#include <RH_RF95.h>
#include <string.h>
 
#define RFM95_CS 5
#define RFM95_RST 6
#define RFM95_INT 9
 
// Change to 434.0 or other frequency, must match RX's freq!
#define RF95_FREQ 434.0
 
// Singleton instance of the radio driver
RH_RF95 rf95(RFM95_CS, RFM95_INT);
 
Adafruit_BNO055 bno = Adafruit_BNO055(55);

void setup(void) 
{

  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);
 
  while (!Serial);
  Serial.begin(9600);
  delay(100);
 
  Serial.println("Arduino LoRa TX Test!");
 
  // manual reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);
 
  while (!rf95.init()) {
    Serial.println("LoRa radio init failed");
    while (1);
  }
  Serial.println("LoRa radio init OK!");
 
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  if (!rf95.setFrequency(RF95_FREQ)) {
    Serial.println("setFrequency failed");
    while (1);
  }
  Serial.print("Set Freq to: "); Serial.println(RF95_FREQ);
  
  // Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on
 
  // The default transmitter power is 13dBm, using PA_BOOST.
  // If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then 
  // you can set transmitter powers from 5 to 23 dBm:
  rf95.setTxPower(23, false);

  /* Initialise the sensor */
  if(!bno.begin())
  {
    /* There was a problem detecting the BNO055 ... check your connections */
    Serial.print("Ooops, no BNO055 detected ... Check your wiring or I2C ADDR!");
    while(1);
  }

  delay(1000);

  // IMU stuff
  //bno.setExtCrystalUse(true);
}

String getvec(Adafruit_BNO055::adafruit_vector_type_t sensor_type, String title){
  imu::Vector<3> data_vector = bno.getVector(sensor_type);
  String thin1 = title + ": X: " + String(data_vector[0]) + " Y: " + String(data_vector[1]) + " Z: " + String(data_vector[2]);
  return thin1;
}

void loop(void) {
  Serial.println("Sending to rf95_server");
  // Send a message to rf95_server
  String all = getvec(Adafruit_BNO055::VECTOR_ACCELEROMETER, "A") + getvec(Adafruit_BNO055::VECTOR_GYROSCOPE, "Gy") + getvec(Adafruit_BNO055::VECTOR_MAGNETOMETER , "M") + getvec(Adafruit_BNO055::VECTOR_EULER, "E") + getvec(Adafruit_BNO055::VECTOR_LINEARACCEL, "LA") + getvec(Adafruit_BNO055::VECTOR_GRAVITY, "Gr");
  int temp = bno.getTemp();
  all = all + "T: " + String(temp);
  int len_data = all.length() + 1;
  char radiopacket[len_data];
  all.toCharArray(radiopacket, len_data);

  Serial.print("Sending "); Serial.println(radiopacket);
  
  Serial.println("Sending..."); delay(10);
  rf95.send((uint8_t *)radiopacket, len_data);
 
  Serial.println("Waiting for packet to complete...");
  rf95.waitPacketSent();
  // Now wait for a reply
  uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
  uint8_t len = sizeof(buf);
 
  Serial.println("Waiting for reply..."); delay(10);
  if (rf95.waitAvailableTimeout(1000))
  { 
    // Should be a reply message for us now   
    if (rf95.recv(buf, &len))
   {
      Serial.print("Got reply: ");
      Serial.println((char*)buf);
      Serial.print("RSSI: ");
      Serial.println(rf95.lastRssi(), DEC);    
    }
    else
    {
      Serial.println("Receive failed");
    }
  }
  else
  {
    Serial.println("No reply, is there a listener around?");
  }
  delay(1000);

}

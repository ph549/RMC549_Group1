// Arduino9x_RX
#include <SPI.h>
#include <RH_RF95.h>
#define RFM95_CS 5
#define RFM95_RST 6
#define RFM95_INT 9
// Change to 434.0 or other frequency, must match RX's freq!
#define RF95_FREQ 434.0
// Singleton instance of the radio driver
RH_RF95 rf95(RFM95_CS, RFM95_INT);
// Blinky on receipt
#define LED 13

int UnByte(char b1, char b2) {
  return b1 << 8 + b2;
}

char * UnCrush(unsigned char* buf, uint8_t len) {
  char msg[255];
  int q = 0;
  int i = 0;
  while (i <= len) {
    Serial.print(i); Serial.print(" char is: "); Serial.println(buf[i]);
    if (buf[i] == 36) { //String by $, end on #
      while (buf[i++] != 35) {
        Serial.print(i); Serial.print(" char is: "); Serial.println(buf[i]);
        msg[q++] = buf[i];
      }
    }
    if (buf[i] == 35) {
      while (buf[i++] != 36) {
        Serial.print(i); Serial.print(" char is: "); Serial.println(buf[i]);
        msg[q++] = UnByte(buf[i], buf[i++]);
      }
    }
    i++;
  }
  Serial.print("Uncrushed:"); Serial.println(msg);
  return msg;
}


void setup() {
  pinMode(LED, OUTPUT);
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  while (!Serial);
  Serial.begin(9600);
  delay(100);
  Serial.println("Arduino LoRa RX Test!");

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
}

void loop() {
  uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
  uint8_t cmd[RH_RF95_MAX_MESSAGE_LEN];
  uint8_t len = sizeof(buf);
  if (rf95.available())  {// Should be a message for us now
    if (rf95.recv(buf, &len)) {
      digitalWrite(LED, HIGH);
      RH_RF95::printBuffer("Received: ", buf, len);
      delay(10);
      Serial.print("Got "); Serial.print(len); Serial.println(" bytes:");
      Serial.println((char*)buf);
      //Serial.println(UnCrush(buf, len));
      Serial.print("RSSI: "); Serial.println(rf95.lastRssi(), DEC);
      // Send a reply
      uint8_t data[] = "And hello back to you";
      rf95.send(data, sizeof(data));
      rf95.waitPacketSent();
      Serial.println("Sent a reply");
      digitalWrite(LED, LOW);
    }
    else
    {
      Serial.println("Receive failed");
    }
  }
  if (Serial.available() > 0) {
    digitalWrite(LED, HIGH);
    int i = 0;
    while (Serial.available() > 0) {
      cmd[i++] = Serial.read();
      if (i >= RH_RF95_MAX_MESSAGE_LEN) {
        Serial.println("Message to long");
        i = 0;
      }
    }
    uint8_t* toSend;
    memcpy(toSend, cmd, i);
    rf95.send(toSend, i);
    rf95.waitPacketSent();
    Serial.println(*toSend);
    digitalWrite(LED, LOW);
  }
}

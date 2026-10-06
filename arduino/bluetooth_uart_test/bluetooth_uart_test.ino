#include <SoftwareSerial.h>

// SoftwareSerial(rxPin, txPin)
SoftwareSerial BTSerial(10, 11);

unsigned long lastSend = 0;
byte sentCount = 0;

void setup() {
  Serial.begin(115200);
  BTSerial.begin(9600);
  BTSerial.listen();
  Serial.println("Bluetooth UART test started");
}

void loop() {
  // Send five valid IoT server messages, two seconds apart.
  if (sentCount < 5 && millis() - lastSend >= 2000) {
    const char message[] = "[PI]DIAG@PING\n";
    size_t queued = BTSerial.write((const uint8_t *)message, sizeof(message) - 1);
    Serial.print("Queued for BT: ");
    Serial.print(queued);
    Serial.print(" bytes: ");
    Serial.print(message);
    lastSend = millis();
    sentCount++;
  }

  // Show every byte received from the module, without protocol parsing.
  while (BTSerial.available()) {
    Serial.write(BTSerial.read());
  }
}

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <SoftwareSerial.h>
#include <stdio.h>
#include <string.h>

// HC-06 TX -> Arduino D2(RX), HC-06 RX <- Arduino D3(TX).
// Keep the module UART setting at 9600. LCD address may be 0x3F on other units.
LiquidCrystal_I2C lcd(0x27, 16, 2);
SoftwareSerial btSerial(2, 3);

const byte MAX_BUFFER = 64;
char rxBuffer[MAX_BUFFER];
byte rxIndex = 0;
bool discardPacket = false;

unsigned int totalCount = 0;
unsigned int passCount = 0;
unsigned int failCount = 0;
unsigned int remainingSeconds = 0;
bool countsKnown = false;
bool timeKnown = false;

// Write exactly 16 columns so old characters never remain on the LCD.
void printLcdLine(byte row, const char *text) {
  lcd.setCursor(0, row);
  byte column = 0;
  while (column < 16 && text[column] != '\0') {
    lcd.print(text[column]);
    column++;
  }
  while (column < 16) {
    lcd.print(' ');
    column++;
  }
}

void showWaitingScreen() {
  countsKnown = false;
  timeKnown = false;
  totalCount = passCount = failCount = remainingSeconds = 0;
  printLcdLine(0, "  GAME WAITING");
  printLcdLine(1, "     READY!");
}

void showGameScreen() {
  char timeText[6] = "--:--";
  char totalText[3] = "--";
  char passText[3] = "--";
  char failText[3] = "--";
  char line1[17];
  char line2[17];

  if (timeKnown) {
    snprintf(timeText, sizeof(timeText), "%02u:%02u",
             (remainingSeconds / 60) % 100, remainingSeconds % 60);
  }
  if (countsKnown) {
    snprintf(totalText, sizeof(totalText), "%02u", totalCount % 100);
    snprintf(passText, sizeof(passText), "%02u", passCount % 100);
    snprintf(failText, sizeof(failText), "%02u", failCount % 100);
  }
  snprintf(line1, sizeof(line1), "T:%s TOTAL:%s", timeText, totalText);
  snprintf(line2, sizeof(line2), "PASS:%s  FAIL:%s", passText, failText);
  printLcdLine(0, line1);
  printLcdLine(1, line2);
}

// Require exact field count and unsigned decimal values, without atoi truncation.
bool parseValues(const char *text, unsigned int *values,
                 byte fieldCount, unsigned int maximum) {
  for (byte i = 0; i < fieldCount; i++) {
    unsigned int value = 0;
    byte digits = 0;
    while (*text >= '0' && *text <= '9') {
      if (++digits > 4) return false;
      value = value * 10 + (unsigned int)(*text - '0');
      if (value > maximum) return false;
      text++;
    }
    if (digits == 0) return false;
    values[i] = value;
    if (i < fieldCount - 1) {
      if (*text != '@') return false;
      text++;
    }
  }
  return *text == '\0';
}

void replyCount() {
  // The destination in an outgoing packet is PI.
  btSerial.print("[PI]APPLIED@COUNT@");
  btSerial.print(totalCount);
  btSerial.print('@');
  btSerial.print(passCount);
  btSerial.print('@');
  btSerial.print(failCount);
  btSerial.print('\n');
  Serial.println("[ACK] COUNT applied");
}

void replyTime() {
  btSerial.print("[PI]APPLIED@TIME@");
  btSerial.print(remainingSeconds);
  btSerial.print('\n');
  Serial.println("[ACK] TIME applied");
}

void processPacket(const char *packet) {
  Serial.print("[RECV] ");
  Serial.println(packet);

  // After server routing, the header is the sender PI, not recipient ARD.
  if (strncmp(packet, "[PI]", 4) != 0) {
    Serial.println("[IGNORE] sender is not PI");
    return;
  }
  const char *command = packet + 4;
  unsigned int values[3];

  if (strncmp(command, "COUNT@", 6) == 0) {
    if (!parseValues(command + 6, values, 3, 99) ||
        values[1] + values[2] > values[0]) {
      Serial.println("[IGNORE] invalid COUNT");
      return;
    }
    totalCount = values[0];
    passCount = values[1];
    failCount = values[2];
    countsKnown = true;
    showGameScreen();
    replyCount();
  } else if (strncmp(command, "TIME@", 5) == 0) {
    if (!parseValues(command + 5, values, 1, 3600)) {
      Serial.println("[IGNORE] invalid TIME");
      return;
    }
    remainingSeconds = values[0];
    timeKnown = true;
    showGameScreen();
    replyTime();
  } else if (strcmp(command, "RESET") == 0) {
    showWaitingScreen();
  } else if (strcmp(command, "STOP") == 0) {
    // Preserve the last values. No local timer exists to stop.
    Serial.println("[ACTION] STOP: display retained");
  } else if (strcmp(command, "START") == 0) {
    // Optional legacy command; COUNT/TIME work without START.
    showWaitingScreen();
    Serial.println("[ACTION] START: waiting for COUNT/TIME");
  } else {
    Serial.println("[IGNORE] unknown command");
  }
}

void setup() {
  delay(1500);
  Serial.begin(9600);
  btSerial.begin(9600);
  lcd.init();
  lcd.backlight();
  showWaitingScreen();
  Serial.println("[SYSTEM] LCD client ready: PI COUNT/TIME, UART 9600");
}

void loop() {
  while (btSerial.available() > 0) {
    char c = (char)btSerial.read();
    if (c == '\n' || c == '\r') {
      if (!discardPacket && rxIndex > 0) {
        rxBuffer[rxIndex] = '\0';
        processPacket(rxBuffer);
      }
      rxIndex = 0;
      discardPacket = false;
    } else if (!discardPacket) {
      if (c == '\0' || rxIndex >= MAX_BUFFER - 1) {
        // Drop the entire malformed/oversized line until its next delimiter.
        discardPacket = true;
        rxIndex = 0;
        Serial.println("[IGNORE] malformed/oversized packet");
      } else {
        rxBuffer[rxIndex++] = c;
      }
    }
  }
  // Pi owns the clock. No local countdown and no sleep during UART reception.
}

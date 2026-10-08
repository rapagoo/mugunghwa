#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <SoftwareSerial.h>
#include <stdio.h>
#include <string.h>

// HC-06 TX -> Arduino D2(RX)
// HC-06 RX <- Arduino D3(TX)
// 실제 배선이 D10/D11이면 아래 생성자의 핀을 변경하세요.
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

// 한 줄을 정확히 16칸 출력해 이전 문자가 남지 않도록 합니다.
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

  totalCount = 0;
  passCount = 0;
  failCount = 0;
  remainingSeconds = 0;

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
    snprintf(
      timeText,
      sizeof(timeText),
      "%02u:%02u",
      (remainingSeconds / 60) % 100,
      remainingSeconds % 60
    );
  }

  if (countsKnown) {
    snprintf(totalText, sizeof(totalText), "%02u", totalCount % 100);
    snprintf(passText, sizeof(passText), "%02u", passCount % 100);
    snprintf(failText, sizeof(failText), "%02u", failCount % 100);
  }

  snprintf(
    line1,
    sizeof(line1),
    "T:%s TOTAL:%s",
    timeText,
    totalText
  );

  snprintf(
    line2,
    sizeof(line2),
    "PASS:%s  FAIL:%s",
    passText,
    failText
  );

  printLcdLine(0, line1);
  printLcdLine(1, line2);
}

// 지정한 개수의 음이 아닌 정수만 허용합니다.
// 음수, 빈 필드, 추가 필드, 범위 초과는 거부합니다.
bool parseValues(
  const char *text,
  unsigned int *values,
  byte fieldCount,
  unsigned int maximum
) {
  for (byte i = 0; i < fieldCount; i++) {
    unsigned int value = 0;
    byte digits = 0;

    while (*text >= '0' && *text <= '9') {
      if (++digits > 4) {
        return false;
      }

      value = value * 10 + (unsigned int)(*text - '0');

      if (value > maximum) {
        return false;
      }

      text++;
    }

    if (digits == 0) {
      return false;
    }

    values[i] = value;

    if (i < fieldCount - 1) {
      if (*text != '@') {
        return false;
      }

      text++;
    }
  }

  return *text == '\0';
}

void replyCount() {
  // 송신 헤더의 PI는 응답을 받을 목적지입니다.
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

  // 서버 중계 후 수신 헤더는 발신자 PI입니다.
  // Arduino 자신의 ID인 ARD와 비교하면 안 됩니다.
  if (strncmp(packet, "[PI]", 4) != 0) {
    Serial.println("[IGNORE] sender is not PI");
    return;
  }

  const char *command = packet + 4;
  unsigned int values[3];

  // [PI]COUNT@전체@통과@탈락
  if (strncmp(command, "COUNT@", 6) == 0) {
    if (
      !parseValues(command + 6, values, 3, 99) ||
      values[1] + values[2] > values[0]
    ) {
      Serial.println("[IGNORE] invalid COUNT");
      return;
    }

    totalCount = values[0];
    passCount = values[1];
    failCount = values[2];
    countsKnown = true;

    // 기존 남은 시간은 유지합니다.
    showGameScreen();
    replyCount();
  }

  // [PI]TIME@남은초
  else if (strncmp(command, "TIME@", 5) == 0) {
    if (!parseValues(command + 5, values, 1, 3600)) {
      Serial.println("[IGNORE] invalid TIME");
      return;
    }

    remainingSeconds = values[0];
    timeKnown = true;

    // 기존 인원수는 유지합니다.
    showGameScreen();
    replyTime();
  }

  else if (strcmp(command, "RESET") == 0) {
    showWaitingScreen();
  }

  else if (strcmp(command, "STOP") == 0) {
    // 자체 타이머가 없으므로 마지막 화면을 유지합니다.
    Serial.println("[ACTION] STOP: display retained");
  }

  else if (strcmp(command, "START") == 0) {
    // 선택적 호환 명령입니다.
    // 현재 게임은 START 없이 COUNT/TIME만으로 표시됩니다.
    showWaitingScreen();
    Serial.println("[ACTION] START: waiting for COUNT/TIME");
  }

  else {
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

  Serial.println(
    "[SYSTEM] LCD client ready: PI COUNT/TIME, UART 9600"
  );
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
    }

    else if (!discardPacket) {
      if (c == '\0' || rxIndex >= MAX_BUFFER - 1) {
        // 잘못되거나 너무 긴 패킷은 다음 개행까지 버립니다.
        discardPacket = true;
        rxIndex = 0;

        Serial.println("[IGNORE] malformed/oversized packet");
      }

      else {
        rxBuffer[rxIndex++] = c;
      }
    }
  }

  // 시간 계산은 Pi가 담당합니다.
  // 자체 카운트다운과 UART 수신 중 절전 처리는 사용하지 않습니다.
}
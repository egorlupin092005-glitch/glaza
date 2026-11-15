// Glaza: two-axis tabletop pointer, Arduino Uno/Nano (ATmega328P).
#include <Servo.h>
#include <string.h>

Servo panServo;
Servo tiltServo;
const byte PAN_PIN = 9;
const byte TILT_PIN = 10;
// Rest pose for this pointer. Following still uses its existing working angles.
const int HOME_PAN = 0;
const int HOME_TILT = 0;
int commandedPan = HOME_PAN;
int commandedTilt = HOME_TILT;
char line[48];
byte used = 0;
bool overflow = false;

// Strict bounded decimal parser: rejects negatives, overflow and trailing data.
bool number(const char *&p, unsigned long &value) {
  value = 0;
  byte count = 0;
  while (*p >= '0' && *p <= '9') {
    if (++count > 5) return false;
    value = value * 10 + (*p++ - '0');
  }
  return count > 0;
}

void processLine() {
  if (strcmp(line, "HELLO") == 0) {
    Serial.print(F("POSE "));
    Serial.print(HOME_PAN);
    Serial.print(' ');
    Serial.print(HOME_TILT);
    Serial.print(' ');
    Serial.print(commandedPan);
    Serial.print(' ');
    Serial.println(commandedTilt);
    Serial.println(F("GLAZA 1"));
    return;
  }
  if (line[0] != 'S' || line[1] != ' ') return;
  const char *p = line + 2;
  unsigned long seq, pan, tilt;
  if (!number(p, seq) || *p++ != ' ') return;
  if (!number(p, pan) || *p++ != ' ') return;
  if (!number(p, tilt) || *p != '\0') return;
  // Allow the path between the usual range and this board's rest position.
  if (seq > 65535 || pan < (unsigned long)min(10, HOME_PAN) ||
      pan > (unsigned long)max(170, HOME_PAN) ||
      tilt < (unsigned long)min(10, HOME_TILT) ||
      tilt > (unsigned long)max(170, HOME_TILT)) return;
  commandedPan = (int)pan;
  commandedTilt = (int)tilt;
  panServo.write(commandedPan);
  tiltServo.write(commandedTilt);
  Serial.print(F("OK "));
  Serial.print(seq);
  Serial.print(' ');
  Serial.print(pan);
  Serial.print(' ');
  Serial.println(tilt);
}

void setup() {
  Serial.begin(115200);
  // Set the first pulse before enabling the outputs on the AVR.
  panServo.write(commandedPan);
  tiltServo.write(commandedTilt);
  panServo.attach(PAN_PIN);
  tiltServo.attach(TILT_PIN);
  Serial.println(F("BOOT"));
}

void loop() {
  // No parseInt(), delay() or unbounded String allocation.
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      if (!overflow) {
        line[used] = '\0';
        processLine();
      }
      used = 0;
      overflow = false;
    } else if (c != '\r') {
      if (used < sizeof(line)-1) line[used++] = c;
      else overflow = true;
    }
  }
  // If USB/data stops, the Servo library holds the last commanded position.
}

#include <Servo.h>

Servo pan_servo;
Servo tilt_servo;

int current_pan = 90;
int current_tilt = 90;

void setup() {
  Serial.begin(9600);
  pan_servo.attach(9);
  tilt_servo.attach(10);
  pan_servo.write(current_pan);
  tilt_servo.write(current_tilt);
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    int comma = cmd.indexOf(',');
    if (comma > 0) {
      int pan = cmd.substring(0, comma).toInt();
      int tilt = cmd.substring(comma + 1).toInt();
      pan = constrain(pan, 0, 180);
      tilt = constrain(tilt, 0, 180);
      pan_servo.write(pan);
      tilt_servo.write(tilt);
      current_pan = pan;
      current_tilt = tilt;
    }
  }
}

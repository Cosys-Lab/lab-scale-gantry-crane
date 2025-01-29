#include <Encoder.h>
#include <Wire.h>

/* Assign a unique ID to this sensor at the same time */

/* Set up the Encoder object */
Encoder angleMeter(2,3);

// Scaling variable to convert counts to degrees
float counts_to_deg = 360.0/8096.0;

long prev_angle = 0;
long prev_time = 0;
float angle = 0;
float angular_vel = 0;
float angular_vel_smooth = 0;
int i = 0;


void setup() {
#ifndef ESP8266
  while (!Serial); // for Leonardo/Micro/Zero
#endif
  Serial.begin(115200);

  prev_time = millis();
}

void loop() {
  /* Read angle */
  long time = micros();
  long angle_raw = angleMeter.read();
  angle = angle_raw*counts_to_deg;
  // halve the sample rate of the angular velocity
  angular_vel += counts_to_deg*float(angle_raw - prev_angle)/(float(time - prev_time)/1000000.0); //
  prev_time = time;
  prev_angle = angle_raw;
  if(i%15==0){
    // bit of averaging for smoothing
    angular_vel_smooth = angular_vel/15.0;
    angular_vel = 0;
  }
  Serial.print(angle); Serial.print(" ");
  Serial.println(angular_vel_smooth);
  ++i;
}

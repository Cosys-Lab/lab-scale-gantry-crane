# Arduino

We use an Arduino Uno for monitoring and controlling the angle measuring encoder, the anemometer, the electromagnet (and the fischertechnik conveyor belt).

The folders contain:

- [arduino-shield-hardware](arduino-shield-hardware/)  
  The KiCad files of the optional Arduino shield.
- [arduino-shield-software](arduino-shield-software/)  
  The software to flash on the Arduino.
- [mqtt-wrapper](mqtt-wrapper/)  
  An MQTT wrapper around the Serial interface of the Arduino. Not needed when you only want to monitor the sensors.
#include "Encoder.h"
#include "PinChangeInterrupt.h"

#define START_SENSOR_PIN 10
#define END_SENSOR_PIN 11
#define PULSE_SENSOR_PIN 12
#define FORWARD_PIN 5
#define BACKWARD_PIN 7
#define ELECTROMAGNET_PIN 9

#define DEBOUNCE_THRESHOLD 10 // Number of consecutive stable samples required

volatile bool runDebounce = false;
bool usingInterrupt = false;
volatile unsigned long pulseCount = 0;
volatile unsigned long targetPulseCount = 0;
volatile bool stopAtSensor = false;
volatile int sensorToStopAt = 0;
volatile bool moveCompleted = false;
bool conveyorRunning = false;
int conveyorDirection = 0;  // 1 for forward, -1 for backward, 0 for stopped
unsigned long prev_millis = 0;
unsigned long prev_millis_angle = 0;

String commandBuffer = ""; // Buffer to store the command

/* Set up the Encoder object */
Encoder angleMeter(2,3);

// Scaling variable to convert counts to degrees
float counts_to_deg = 360.0/8096.0;

long prev_angle = 0;
long prev_time = 0;
float angle = 0;
float angular_vel = 0;
float angular_vel_smooth = 0;

// Function prototypes
void setup();
void loop();
void processCommand(String command);
void startConveyor(int direction);
void stopConveyor();
void movePulses(int direction, unsigned long pulses);
void moveToSensor(int direction, int sensorPin);
void querySensors();
//void pulseISR();
void startSensorISR();
void stopSensorISR();
void debouncePulse();
void pulseCheck();
void setElectroMagnet(int onOff);
void updateAngle();
void printAngle();

void setup() {
  Serial.begin(115200);
  pinMode(START_SENSOR_PIN, INPUT);
  pinMode(END_SENSOR_PIN, INPUT);
  pinMode(PULSE_SENSOR_PIN, INPUT);
  pinMode(FORWARD_PIN, OUTPUT);
  pinMode(BACKWARD_PIN, OUTPUT);
  pinMode(ELECTROMAGNET_PIN, OUTPUT);
  setElectroMagnet(0);

  attachPinChangeInterrupt(digitalPinToPinChangeInterrupt(START_SENSOR_PIN), startSensorISR, FALLING);
  attachPinChangeInterrupt(digitalPinToPinChangeInterrupt(END_SENSOR_PIN), stopSensorISR, FALLING);
  //attachPinChangeInterrupt(digitalPinToPinChangeInterrupt(PULSE_SENSOR_PIN), pulseISR, CHANGE); too bouncy to be used inside an ISR unfortunately

  prev_time = millis();
}

void loop() {
  while (Serial.available() > 0) {
    char receivedChar = Serial.read();
    Serial.print(receivedChar);
    commandBuffer += receivedChar;
    if (receivedChar == '\n') {
      commandBuffer.trim();
      processCommand(commandBuffer);
      commandBuffer = ""; // Clear the buffer after processing the command
    }
  }

  // debounce pulse every 1 ms, 50 consecutive bounces seems like a good value?
  // breaks if the arduino operates for more than 50 days.
  if(millis() > prev_millis){
    debouncePulse();
    prev_millis = millis();
  }
  // update as fast as possible
  updateAngle();
  // output at 100 Hz?
  if(millis() > prev_millis_angle+100){
    printAngle();
    prev_millis_angle = millis();
  }
  
  pulseCheck();
}

void processCommand(String command) {
  if (command.startsWith("G1")) {
    // Example: G1 F (Forward indefinitely)
    //          G1 B (Backward indefinitely)
    char direction = command.charAt(3);
    if (direction == 'F') {
      if (conveyorRunning)
      {
        stopConveyor();
      }
      
      startConveyor(1);
      Serial.println("OK " + command);
    } else if (direction == 'B') {
        if (conveyorRunning)
      {
        stopConveyor();
      }
      startConveyor(-1);
      Serial.println("OK " + command);
    }
  } else if (command.startsWith("G2")) {
    // Example: G2 F 100 (Forward 100 pulses)
    char direction = command.charAt(3);
    int targetPulses = command.substring(5).toInt();
    if (direction == 'F') {
      movePulses(1, targetPulses);
      Serial.println("OK " + command);
    } else if (direction == 'B') {
      movePulses(-1, targetPulses);
      Serial.println("OK " + command);
    }
  } else if (command.startsWith("G3")) {
    // Example: G3 F (Forward until the payload reaches the end sensor)
    char direction = command.charAt(3);
    if (direction == 'F') {
      moveToSensor(1, END_SENSOR_PIN);
      Serial.println("OK " + command);
    } else if (direction == 'B') {
      moveToSensor(-1, START_SENSOR_PIN);
      Serial.println("OK " + command);
    }
  } else if (command.startsWith("G4")) {
    // Example: G4 (Query sensor states)
    querySensors();
  } else if (command.startsWith("G5")) {
    // Example: G5 (Stop the conveyor)
    stopConveyor();
    Serial.println("OK G5");
  } else if (command.startsWith("G6")) {
    // add code for the electromagnet -> do experimentation for current and dutycycle first.
    int target = command.substring(3).toInt();// 0 = off >0 = on
    setElectroMagnet(target);
  } else {
    Serial.println("NOK " + command);
  }
}

void startConveyor(int direction) {
  conveyorDirection = direction;
  conveyorRunning = true;
  if (direction == 1) {
    digitalWrite(FORWARD_PIN, HIGH);
  } else if (direction == -1) {
    digitalWrite(BACKWARD_PIN, HIGH);
  }
}

void stopConveyor() {
  digitalWrite(FORWARD_PIN, LOW);
  digitalWrite(BACKWARD_PIN, LOW);
  conveyorRunning = false;
  conveyorDirection = 0;
  targetPulseCount = 0;
  stopAtSensor = false;
}

void movePulses(int direction, unsigned long pulses) {
    if (conveyorRunning){
        stopConveyor();
    }
    pulseCount = 0;
    targetPulseCount = pulses;
    moveCompleted = false;
    startConveyor(direction);
}

void moveToSensor(int direction, int sensorPin) {
    if (conveyorRunning){
        // when already running, stop operation to configure the new running mode.
        stopConveyor();
    }
  stopAtSensor = true;
  sensorToStopAt = sensorPin;
  moveCompleted = false;
  startConveyor(direction);
}

void querySensors() {
  bool startSensor = digitalRead(START_SENSOR_PIN);
  bool endSensor = digitalRead(END_SENSOR_PIN);
  Serial.print("START_SENSOR:");
  Serial.print(startSensor ? "1" : "0");
  Serial.print(", END_SENSOR:");
  Serial.print(endSensor ? "1" : "0");
  Serial.print(", PULSE_COUNT:");
  Serial.println(pulseCount);
}

void startSensorISR() {
    if (stopAtSensor && sensorToStopAt == START_SENSOR_PIN){
            stopConveyor();
    }
}

void stopSensorISR() {
    if (stopAtSensor && sensorToStopAt == END_SENSOR_PIN){
            stopConveyor();
    }
}

void pulseCheck() {
  if (targetPulseCount > 0 && pulseCount >= targetPulseCount) {
    stopConveyor();
  }
}

void debouncePulse(){
    static uint8_t stable_count = 0;   // Count of consecutive stable readings
    static bool last_stable_state = digitalRead(PULSE_SENSOR_PIN); // Last confirmed stable state
    static bool last_read = last_stable_state;

    bool current_read = digitalRead(PULSE_SENSOR_PIN); // Read the raw button state

    // Check if the current reading is the same as the last reading
    if (current_read == last_read) {
        // Increment the stable count if state is consistent
        if (stable_count < DEBOUNCE_THRESHOLD) {
            stable_count++;
        }
    } else {
        // Reset the stable count if the state changes
        stable_count = 0;
    }
    // assign current_read to last_reading.
    last_read = current_read;

    // If stable count reaches threshold, confirm the new state
    if (stable_count >= DEBOUNCE_THRESHOLD) {
        // if this changed the state, increase the pulsecount
        if(last_stable_state != current_read){
            pulseCount++;
        }
        last_stable_state = current_read;
    }
}

void setElectroMagnet(int onOff){
    if(onOff){
        // 10% dutycycle.
        analogWrite(ELECTROMAGNET_PIN, 50);
    } else {
        analogWrite(ELECTROMAGNET_PIN, 0);
    }
}

void updateAngle(){
    static int i = 0;

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
}

void printAngle(){
    Serial.print("A: ");
    Serial.print(angle); 
    Serial.print(",V: ");
    Serial.println(angular_vel_smooth);
}

// /*
// from https://forum.arduino.cc/t/what-is-the-easiest-way-to-run-some-code-each-millisecond-for-a-certain-amount-of-time/897345/3

// On AVRs, I've seen people enable one of the "Compare Match" interrupts on Timer0.
// This time is already running at about a 1ms rate (1/1024 s) till wrap-around, so any compare value will also interrupt every 1/1024 s.
// If you're not using PWM pins, you can set the compare register to an arbitrary value.
// If you ARE using PWM, whatever value is loaded by PWM will still cause an interrupt every 1/1024 s...

// For example: Adafruit_GPS/shield_sdlog.ino at master · adafruit/Adafruit_GPS · GitHub
// */
// void useTimerInterrupt(bool v) {
//   if (v) {
//     // Timer0 is already used for millis() - we'll just interrupt somewhere
//     // in the middle and call the "Compare A" function above
//     OCR0A = 0xAF;
//     TIMSK0 |= _BV(OCIE0A);
//     usingInterrupt = true;
//   }
//   else {
//     // do not call the interrupt function COMPA anymore
//     TIMSK0 &= ~_BV(OCIE0A);
//     usingInterrupt = false;
//   }
// }

// ISR(TIMER0_COMPA_vect) {
//     runDebounce = true;
// }
import serial
import time
import json
import paho.mqtt.client as mqtt
import threading

class ArduinoMQTTController:
    def __init__(self, device_id, serial_port, baud_rate=115200, broker_address='localhost', broker_port=1883):
        self.device_id = device_id
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.serial_connection = None
        self.mqtt_client = mqtt.Client()

    def setup_serial_connection(self):
        try:
            self.serial_connection = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            print("Serial connection established.")
        except serial.SerialException as e:
            print(f"Error connecting to serial port: {e}")

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT Broker with result code {rc}")
        # Subscribe to command topics
        command_topic = f"command/bip-server/{self.device_id}/req/#"
        client.subscribe(command_topic)

    def on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split('/')
            command = topic_parts[-1]
            if len(topic_parts) == 6:  # Command with request-id
                request_id = topic_parts[-2]
                response_needed = True
            else:
                request_id = None
                response_needed = False

            print(f"Received MQTT message: {msg.payload.decode()} on topic {msg.topic}")
            payload = json.loads(msg.payload.decode())

            print(payload)
            
            # Send command to Arduino
            response_status = self.send_command(command, payload)

            if response_needed:
                response_topic = f"command/bip-server/{self.device_id}/res/{request_id}/{response_status}"
                client.publish(response_topic, response_status)
        except Exception as e:
            print(f"Error handling MQTT message: {e}")

    def send_command(self, command, params):
        try:
            if self.serial_connection and self.serial_connection.is_open:
                if command == "G1":
                    dir = params["dir"]
                    cmd = f"G1 {dir}"
                elif command == "G2":
                    dir = params.get("dir", "F")
                    steps = params.get("steps", 0)
                    cmd = f"G2 {dir}{steps}"
                elif command == "G3":
                    dir = params.get("dir", "F")
                    cmd = f"G3 {dir}"
                elif command == "G4":
                    cmd = "G4"
                elif command == "G5":
                    cmd = "G5"
                elif command == "G6":
                    onoff = params.get("onoff", 0)
                    cmd = f"G6 {onoff}"
                else:
                    print(f"Unknown command: {command}")
                    return 400  # Bad request
                
                print(cmd)

                self.serial_connection.write(str.encode(cmd + "\r\n"))
                self.serial_connection.flush()
                # time.sleep(0.1)
                # response = self.serial_connection.readline().decode().strip()
                # print(f"Arduino response: {response}")
                # if response.startswith("NOK"):
                #     return 400  # Bad request
                return 200  # OK
            else:
                print("Serial connection is not open.")
                return 400  # Bad request
        except Exception as e:
            print(f"Error sending command to Arduino: {e}")
            return 400  # Bad request

    # def read_encoder_data(self):
    #     while True:
    #         pass
        #     try:
        #         if self.serial_connection and self.serial_connection.is_open:
        #             line = self.serial_connection.readline().decode().strip()
        #             if line.startswith("A:") and ",V:" in line:
        #                 angle, velocity = line.split(",V:")
        #                 angle = float(angle.replace("A: ", ""))
        #                 velocity = float(velocity)
        #                 telemetry = {
        #                     "angle": angle,
        #                     "velocity": velocity
        #                 }
        #                 telemetry_topic = f"telemetry/bip-server/{self.device_id}"
        #                 self.mqtt_client.publish(telemetry_topic, json.dumps(telemetry))
        #                 time.sleep(0.01)  # Adjust as necessary to avoid high CPU usage
        #     except Exception as e:
        #         print(f"Error reading encoder data: {e}")
        #         break

    def run(self):
        # Set up Serial connection
        self.setup_serial_connection()
        
        # Set up MQTT client callbacks
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        # Connect to the MQTT broker
        self.mqtt_client.connect(self.broker_address, self.broker_port, 60)

        # Start a separate thread to continuously read encoder data
        # encoder_thread = threading.Thread(target=self.read_encoder_data, daemon=True)
        # encoder_thread.start()

        # Start the MQTT loop
        self.mqtt_client.loop_forever()

if __name__ == "__main__":
    DEVICE_ID = "conveyor-1"  # Replace with your actual device identifier
    SERIAL_PORT = "COM6"  # Replace with your actual serial port

    controller = ArduinoMQTTController(device_id=DEVICE_ID, serial_port=SERIAL_PORT)
    controller.run()

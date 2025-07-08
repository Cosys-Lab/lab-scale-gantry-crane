from paho.mqtt import client as mqtt
import random
import serial
import json
import time
import threading
import re

# MQTT Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

DEVICE_ID = 1

SUB_TOPIC = "command/bip-server/" + str(DEVICE_ID) + "/req/#"
RESPOND_TOPIC = "command/bip-server/" + str(DEVICE_ID) + "/res/"
PUB_TOPIC = "telemetry/bip-server/" + str(DEVICE_ID)

# Serial Configuration
SERIAL_PORT = 'COM14'  # Change to your serial ports
BAUD_RATE = 115200

# Initialize Serial
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
except serial.SerialException as e:
    print(f"Failed to initialize serial connection: {e}")
    ser = None

request_id = " "


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(SUB_TOPIC)
        print("subscribed to :" + SUB_TOPIC)
    else:
        print("Failed to connect, return code %d\n", rc)


def on_message(client, userdata, msg):
    #print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")
    print(f"Received message on `{msg.topic}` topic")
    topic_parts = msg.topic.split('/')
    res_topic = topic_parts[-2]
    last_partition = topic_parts[-1]
    try:
        unknown_command = False
        if last_partition in (["G1","G2","G3","G4","G5","G6"]):
            payload = json.loads(msg.payload.decode())  # Assuming payload is JSON
            command = ""
            match last_partition:
                case "G1":
                    dir = payload.get("dir")
                    if dir is None:
                        raise KeyError("Missing 'dir' key for G1 command.")
                    command = last_partition + " " + dir
                    print("Handling Group G1")
                case "G2":
                    dir = payload.get("dir")
                    pulses = payload.get("pulses")
                    if dir is None or pulses is None:
                        raise KeyError("Missing 'dir' or 'pulses' key for G2 command.")
                    command = last_partition + " " + dir + " " + str(pulses)
                    print("Handling Group G2")
                case "G3":
                    dir = payload.get("dir")
                    if dir is None:
                        raise KeyError("Missing 'dir' key for G3 command.")
                    command = last_partition + " " + dir
                    print("Handling Group G3")
                case "G4":
                    global request_id
                    request_id = (msg.topic).split("/")[-2]
                    command = last_partition
                    print("Handling Group G4" + request_id)
                case "G5":
                    command = last_partition
                    print("Handling Group G5")
                case "G6":
                    on_off = payload.get("on/off")
                    if on_off is None:
                        raise KeyError("Missing 'on/off' key for G6 command.")
                    command = last_partition + " " + str(on_off)
                    print("Handling Group G6")
                case _:
                    print("Group not recognized")
                    unknown_command = True

        if not unknown_command:
            # Send command to serial if available
            ser.write((command + '\n').encode())
            print(f"Sent to Serial: {command}")
            if last_partition != "G4":
                response_topic = f"command/bip-server/{DEVICE_ID}/res/{res_topic}/{last_partition}"
                response_payload = {}
                serialized_marker_ids = json.dumps(response_payload)
                client.publish(response_topic, serialized_marker_ids, qos=2)
                print(f"Published trajectory to topic: {response_topic}")

    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
    except KeyError as e:
        print(f"Missing key in payload: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while processing the message: {e}")


def extract_json(data_string):
    # Regex to find key-value pairs in the format `key: value`
    pattern = r'(\w+):\s*([\d.]+)'
    
    # Find all matches (key-value pairs)
    matches = re.findall(pattern, data_string)
    
    # Convert matches into a dictionary
    json_data = {key: float(value) for key, value in matches}

    return json_data


# Function to read from serial and send to MQTT
def serial_to_mqtt():
    while True:
        if ser and ser.in_waiting > 0:
            try:
                serial_data = ser.readline().decode('utf-8').rstrip()
                if serial_data:
                    json_dict = extract_json(serial_data)
                    if "A" in json_dict and "V" in json_dict:
                        client.publish(PUB_TOPIC, json.dumps(json_dict))
                    elif "START_SENSOR" in json_dict:
                        global request_id
                        client.publish(RESPOND_TOPIC + request_id +"/G4", json.dumps(json_dict))
            except (UnicodeDecodeError, ValueError) as e:
                print(f"Error reading from serial: {e}")
            except Exception as e:
                print(f"An unexpected error occurred while processing serial data: {e}")

        time.sleep(0.01)  # Adjust as needed to avoid high CPU usage


if __name__ == "__main__":
    # Create an instance of the MQTT client
    client = mqtt.Client()

    # Assign the callbacks
    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to the broker
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    client.loop_start()
    serial_thread = threading.Thread(target=serial_to_mqtt, daemon=True)
    serial_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")

    # Clean up
    if ser:
        ser.close()
    client.loop_stop()
    client.disconnect()

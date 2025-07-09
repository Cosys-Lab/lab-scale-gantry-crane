from unittest.mock import Mock
import paho.mqtt.client as mqtt
import pickle
import json
import logging
from gantrylib.trajectory_generator import TrajectoryGenerator, MockTrajectoryGenerator

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
REQUEST_TOPIC = "trajectory/request"

logging.basicConfig(level=logging.INFO)

class MQTTTrajectoryServer:
    def __init__(self, config, broker=MQTT_BROKER, port=MQTT_PORT, mock=False):
        if mock:
            self.generator = MockTrajectoryGenerator(config)
        else:
            self.generator = TrajectoryGenerator(config)
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(broker, port, 60)

    def on_connect(self, client, userdata, flags, rc):
        logging.info(f"Connected to MQTT broker with result code {rc}")
        client.subscribe(REQUEST_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            # Expecting a JSON payload: {"start": float, "stop": float, "method": str, "request_id": str}
            payload = json.loads(msg.payload.decode())
            start = payload["start"]
            stop = payload["stop"]
            method = payload.get("method", "rockit")
            request_id = payload["request_id"]  # Now required

            logging.info(f"Received trajectory request: start={start}, stop={stop}, method={method}, request_id={request_id}")

            result = self.generator.generateTrajectory(start, stop, method=method)
            pickled_result = pickle.dumps(result)

            # Publish the pickled result to a unique topic for this request
            reply_topic = f"trajectory/response/{request_id}"
            client.publish(reply_topic, pickled_result)
            logging.info(f"Published trajectory to {reply_topic}")

        except Exception as e:
            logging.info(f"Error handling message: {e}")

    def serve_forever(self):
        logging.info("TrajectoryMQTTServer started. Waiting for requests...")
        self.client.loop_forever()

# Example usage:
if __name__ == "__main__":
    # Example config, replace with your actual config loading
    config = {
        "pendulum mass": 1.0,
        "pendulum damping": 0.1,
        "rope length": 1.0,
        "cart velocity limit": 2.0,
        "rope angle limit": 1.57
    }
    server = MQTTTrajectoryServer(config)
    server.serve_forever()
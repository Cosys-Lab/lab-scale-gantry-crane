import importlib
import subprocess
import sys
import time
import logging

try:
    import psutil
except ImportError:
    psutil = None

from gantrylib.trajectory_generator import TrajectoryGenerator, AbstractTrajectoryGenerator
from gantrylib.trajectory_generator import MQTTCientTrajectoryGenerator

class TrajectoryGeneratorFactory:
    @staticmethod
    def is_mqtt_server_running(script_name="trajectory_server.py"):
        """Check if the MQTT server process is already running."""
        if psutil is None:
            logging.warning("psutil not installed, cannot check for running server. Will always spawn a new one.")
            return False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and script_name in proc.info['cmdline'][-1]:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, IndexError):
                continue
        return False

    @staticmethod
    def spawn_mqtt_server(config, timeout=5):
        """Spawn the MQTT server as a subprocess and wait until it's running."""
        proc = subprocess.Popen([sys.executable, "-m", "gantrylib.trajectory_server"])
        logging.info("Spawned MQTT server process.")
        # Poll for the server to be running, up to timeout seconds
        start_time = time.time()
        while time.time() - start_time < timeout:
            if TrajectoryGeneratorFactory.is_mqtt_server_running():
                logging.info("MQTT server is now running.")
                return proc
            time.sleep(0.1)
        logging.warning("MQTT server did not start within timeout.")
        return proc

    @classmethod
    def create(cls, mode, config):
        """
        Factory method for trajectory generators.
        mode: 'local' or 'mqtt'
        config: configuration dictionary
        """
        if mode == "local":
            return TrajectoryGenerator(config)
        elif mode == "mqtt":
            if not cls.is_mqtt_server_running():
                cls.spawn_mqtt_server(config)
            return MQTTCientTrajectoryGenerator(config)
        else:
            raise ValueError(f"Unknown mode: {mode}")
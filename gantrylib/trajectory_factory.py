import threading
import sys
import time
import logging

try:
    import psutil
except ImportError:
    psutil = None

from gantrylib.trajectory_generator import MockTrajectoryGenerator, TrajectoryGenerator
from gantrylib.trajectory_generator import MQTTCientTrajectoryGenerator
from gantrylib.trajectory_server import MQTTTrajectoryServer

class TrajectoryGeneratorFactory:
    _server_thread = None
    _server = None

    @classmethod
    def spawn_mqtt_server(cls, config, timeout=5, mock_generator=False):
        """Start the MQTT server in a background thread.
        
        Args:
            config: Configuration dictionary
            timeout: Maximum time to wait for server startup
            mock_generator: If True, starts server in mock mode
        """
        if cls._server_thread and cls._server_thread.is_alive():
            logging.info("MQTT server already running")
            return

        # Create server instance
        cls._server = MQTTTrajectoryServer(config, mock=mock_generator)
        
        # Start server in thread
        cls._server_thread = threading.Thread(
            target=cls._server.serve_forever,
            name="MQTTTrajectoryServerThread",
            daemon=True  # Thread will exit when main program exits
        )
        cls._server_thread.start()
        
        # Wait for server to start
        start_time = time.time()
        while time.time() - start_time < timeout:
            if cls._server_thread.is_alive():
                logging.info("MQTT server is now running")
                return
            time.sleep(0.1)
            
        logging.warning("MQTT server did not start within timeout")

    @classmethod
    def create(cls, mode, config, mock_generator=False):
        """
        Factory method for trajectory generators.
        mode: 'local' or 'mqtt'
        config: configuration dictionary
        """
        if mode == "local":
            return TrajectoryGenerator(config)
        elif mode == "mqtt-client":
            return MQTTCientTrajectoryGenerator(config)
        elif mode == "mqtt-client-server":
            cls.spawn_mqtt_server(config, mock_generator=mock_generator)
            return MQTTCientTrajectoryGenerator(config)
        elif mode == "mock":
            return MockTrajectoryGenerator(config)
        else:
            raise ValueError(f"Unknown mode: {mode}")
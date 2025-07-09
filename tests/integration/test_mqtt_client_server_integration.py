import unittest
import time
from gantrylib.trajectory_factory import TrajectoryGeneratorFactory
import numpy as np

class TestTrajectoryFactoryIntegration(unittest.TestCase):
    def setUp(self):
        self.config = {
            "mqtt_broker": "localhost",
            "mqtt_port": 1883,
            "mqtt_request_topic": "trajectory/request",
            "pendulum mass": 0.1,
            "pendulum damping": 0.1,
            "rope length": 0.5,
            "cart velocity limit": 2.0,
            "rope angle limit": 0.785  # pi/4 radians
        }

    def test_mqtt_client_mode_with_server(self):
        """Test MQTT client mode with manually spawned server.
        This test requires an MQTT broker to be running in the background."""
        
        # First spawn the server
        TrajectoryGeneratorFactory.spawn_mqtt_server(self.config, mock_generator=True)
        
        try:
            # Create client-only generator
            generator = TrajectoryGeneratorFactory.create("mqtt-client", self.config)
    
            # Generate test trajectory
            start, stop = 0.0, 1.0
            result = generator.generateTrajectory(start, stop)
            
            ts, xs, dxs, ddxs, thetas, dthetas, ddthetas, us = result
            
            # Check mock returns the right arrays (as generated in the mock)
            np.testing.assert_array_equal(ts, np.linspace(0, 1, 10))
            np.testing.assert_array_equal(xs, np.linspace(start, stop, 10))
            np.testing.assert_array_equal(dxs, np.gradient(xs, ts))
            np.testing.assert_array_equal(ddxs, np.gradient(dxs, ts))
            np.testing.assert_array_equal(thetas, np.zeros_like(ts))
            np.testing.assert_array_equal(dthetas, np.zeros_like(ts))
            np.testing.assert_array_equal(ddthetas, np.zeros_like(ts))
            np.testing.assert_array_equal(us, np.zeros_like(ts))
            
            # Check mock boundary conditions
            self.assertEqual(xs[0], start)
            self.assertEqual(xs[-1], stop)
        
        finally:
            # Clean up server
            if TrajectoryGeneratorFactory._server_thread:
                TrajectoryGeneratorFactory._server_thread = None
            if TrajectoryGeneratorFactory._server:
                TrajectoryGeneratorFactory._server = None

if __name__ == '__main__':
    unittest.main()
import unittest
from gantrylib.trajectory_factory import TrajectoryGeneratorFactory
from gantrylib.trajectory_generator import TrajectoryGenerator, MockTrajectoryGenerator
import numpy as np

class TestTrajectoryFactory(unittest.TestCase):

    def setUp(self):
        self.config = {
            "pendulum mass": 1.0,
            "pendulum damping": 0.1,
            "rope length": 0.5,
            "cart velocity limit": 2.0,
            "rope angle limit": np.pi/4
        }
        
    def test_create_local_mode(self):
        generator = TrajectoryGeneratorFactory.create("local", self.config)
        self.assertIsInstance(generator, TrajectoryGenerator)

    def test_create_mock_mode(self):
        generator = TrajectoryGeneratorFactory.create("mock", self.config)
        self.assertIsInstance(generator, MockTrajectoryGenerator)

    def test_create_invalid_mode(self):
        with self.assertRaises(ValueError):
            TrajectoryGeneratorFactory.create("invalid", self.config)

    def test_create_mqtt_client_server_mode(self):
        """ this test requires an MQTT broker to be running in the background
        It tests the factories ability to spawn an MQTT server running a mock generator,
        and the communication between the client and that server."""
        generator = TrajectoryGeneratorFactory.create("mqtt-client-server", self.config, mock_generator=True)

        start, stop = 0.0, 1.0
        result = generator.generateTrajectory(start, stop)
        
        ts, xs, dxs, ddxs, thetas, dthetas, ddthetas, us = result
        
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

    def tearDown(self):
        # Clean up server thread if running
        if TrajectoryGeneratorFactory._server_thread:
            TrajectoryGeneratorFactory._server_thread = None
        if TrajectoryGeneratorFactory._server:
            TrajectoryGeneratorFactory._server = None

if __name__ == '__main__':
    unittest.main()
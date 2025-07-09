import unittest
import numpy as np
from gantrylib.trajectory_generator import TrajectoryGenerator, MockTrajectoryGenerator

class TestTrajectoryGenerator(unittest.TestCase):
    def setUp(self):
        self.config = {
            "pendulum mass": 1.0,
            "pendulum damping": 0.1,
            "rope length": 0.5,
            "cart velocity limit": 2.0,
            "rope angle limit": np.pi/4
        }
        self.generator = TrajectoryGenerator(self.config)
        self.mock_generator = MockTrajectoryGenerator()

    def test_generator_initialization(self):
        self.assertEqual(self.generator.mp, 1.0)
        self.assertEqual(self.generator.dp, 0.1)
        self.assertEqual(self.generator.r, 0.5)
        self.assertEqual(self.generator.v_cart_lim, 2.0)
        self.assertEqual(self.generator.theta_lim, np.pi/4)

    def test_rockit_trajectory_generation(self):
        start, stop = 0.0, 1.0
        result = self.generator.generateTrajectory(start, stop, method='rockit')
        
        # Check if trajectory is returned
        if result is not None:
            ts, xs, dxs, ddxs, thetas, dthetas, ddthetas, us = result
            
            # Check array lengths match
            self.assertEqual(len(ts), len(xs))
            self.assertEqual(len(ts), len(dxs))
            self.assertEqual(len(ts), len(ddxs))
            self.assertEqual(len(ts), len(thetas))
            self.assertEqual(len(ts), len(dthetas))
            self.assertEqual(len(ts), len(ddthetas))
            
            # Check boundary conditions
            self.assertAlmostEqual(xs[0], start, places=2)
            self.assertAlmostEqual(xs[-1], stop, places=2)
            
            # Check velocity limits
            self.assertTrue(np.all(np.abs(dxs) <= self.config["cart velocity limit"]))
            
            # Check angle limits
            self.assertTrue(np.all(np.abs(thetas) <= self.config["rope angle limit"]))

    def test_lqr_trajectory_generation(self):
        start, stop = 0.0, 1.0
        result = self.generator.generateTrajectory(start, stop, method='lqr')
        
        if result is not None:
            ts, xs, dxs, ddxs, thetas, dthetas, ddthetas, us = result
            
            # Check array lengths match
            self.assertEqual(len(ts), len(xs))
            self.assertEqual(len(ts), len(dxs))
            self.assertEqual(len(ts), len(ddxs))
            self.assertEqual(len(ts), len(thetas))
            self.assertEqual(len(ts), len(dthetas))
            self.assertEqual(len(ts), len(ddthetas))
            
            # Check boundary conditions
            self.assertAlmostEqual(xs[0], start, places=2)
            self.assertAlmostEqual(xs[-1], stop, places=2)
            
            # Check velocity limits
            self.assertTrue(np.all(np.abs(dxs) <= self.config["cart velocity limit"]))

    def test_invalid_method(self):
        with self.assertRaises(ValueError):
            self.generator.generateTrajectory(0.0, 1.0, method='invalid')

    def test_mock_generator(self):
        start, stop = 0.0, 1.0
        result = self.mock_generator.generateTrajectory(start, stop)
        
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

if __name__ == '__main__':
    unittest.main()
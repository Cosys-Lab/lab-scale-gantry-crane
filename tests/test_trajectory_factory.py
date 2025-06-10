import unittest
from gantrylib.trajectory_factory import create_trajectory

class TestTrajectoryFactory(unittest.TestCase):
    def test_create_trajectory(self):
        trajectory = create_trajectory()
        self.assertIsNotNone(trajectory)
        self.assertEqual(trajectory.type, 'default')

if __name__ == '__main__':
    unittest.main()
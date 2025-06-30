import struct
import unittest
from unittest.mock import patch, MagicMock
from gantrylib.crane_io_uc import CraneIOUC, MockCraneIOUC, SerialCraneIOUC

class TestMockCraneIOUC(unittest.TestCase):
    def setUp(self):
        self.mock_uc = MockCraneIOUC()

    def test_initial_values(self):
        self.assertEqual(self.mock_uc.angle, 0.0)
        self.assertEqual(self.mock_uc.omega, 0.0)
        self.assertEqual(self.mock_uc.windspeed, 0.0)

    def test_get_status_returns_zeros(self):
        angle, omega, windspeed = self.mock_uc.getStatus()
        self.assertEqual(angle, 0.0)
        self.assertEqual(omega, 0.0)
        self.assertEqual(windspeed, 0.0)

    def test_zeroWind_and_zeroAngle_do_not_crash(self):
        # zeroWind should not raise
        self.mock_uc.zeroWind()
        # zeroAngle should not raise (uses readAngle, which is not implemented, so we patch it)
        self.mock_uc.readAngle = MagicMock(return_value=(1.23, 0.0, 0.0))
        self.mock_uc.zeroAngle()
        self.assertEqual(self.mock_uc.angle_offset, 1.23)

class TestSerialCraneIOUC(unittest.TestCase):
    @patch('gantrylib.crane_io_uc.serial.Serial')
    def setUp(self, mock_serial):
        # Patch serial.Serial for all tests in this class
        self.mock_serial_instance = MagicMock()
        mock_serial.return_value = self.mock_serial_instance
        config = {
            "CraneIOUCPort": "COM1",
            "CraneIOUCBaudrate": 115200
        }
        self.uc = SerialCraneIOUC(config)

    def test_init_sets_serial_params(self):
        self.assertEqual(self.uc.port, "COM1")
        self.assertEqual(self.uc.baudrate, 115200)
        self.assertTrue(hasattr(self.uc, "conn"))
        self.assertTrue(hasattr(self.uc, "get_status_lock"))

    @patch('gantrylib.crane_io_uc.serial.Serial')
    def test_getStatus_with_valid_packet(self, mock_serial):
        # Prepare a valid packet: start byte + 3 floats (angle, omega, windspeed)
        angle, omega, windspeed = 1.1, 2.2, 3.3
        packet = b'\x01' + struct.pack('<fff', angle, omega, windspeed)
        # Simulate serial read
        uc = SerialCraneIOUC({"CraneIOUCPort": "COM2", "CraneIOUCBaudrate": 9600})
        uc.conn.read = MagicMock(return_value=packet)
        uc.conn.in_waiting = len(packet)
        # Call getStatus
        result = uc.getStatus()
        self.assertAlmostEqual(result[0], angle)
        self.assertAlmostEqual(result[1], omega)
        self.assertAlmostEqual(result[2], windspeed)

    @patch('gantrylib.crane_io_uc.serial.Serial')
    def test_getStatus_with_no_data_returns_last(self, mock_serial):
        uc = SerialCraneIOUC({"CraneIOUCPort": "COM3", "CraneIOUCBaudrate": 9600})
        uc.conn.read = MagicMock(return_value=b'')
        uc.conn.in_waiting = 0
        uc.angle = 5.5
        uc.omega = 6.6
        uc.windspeed = 7.7
        result = uc.getStatus()
        self.assertEqual(result, (5.5, 6.6, 7.7))

    @patch('gantrylib.crane_io_uc.serial.Serial')
    def test_zeroWind_and_zeroAngle(self, mock_serial):
        uc = SerialCraneIOUC({"CraneIOUCPort": "COM4", "CraneIOUCBaudrate": 9600})
        # Patch getStatus to return a windspeed of 10.0
        uc.getStatus = MagicMock(return_value=(0.0, 0.0, 10.0))
        uc.zeroWind()
        self.assertEqual(uc.wind_offset, 10.0)
        # Patch readAngle to return angle of 2.5
        uc.readAngle = MagicMock(return_value=(2.5, 0.0, 0.0))
        uc.zeroAngle()
        self.assertEqual(uc.angle_offset, 2.5)

if __name__ == '__main__':
    unittest.main()
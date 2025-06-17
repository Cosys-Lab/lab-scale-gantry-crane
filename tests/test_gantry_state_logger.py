import unittest
from unittest.mock import Mock
import threading
import time
from gantrylib.gantry_state_logger import CraneStateLogger

class TestCraneStateLogger(unittest.TestCase):
    def setUp(self):
        self.mock_crane = Mock()
        self.mock_db_writer = Mock()
        # Set mock crane state return value
        self.mock_crane.getState.return_value = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
        
        self.logger = CraneStateLogger(
            self.mock_crane, 
            self.mock_db_writer,
            logging_rate=1000.0,
            write_rate=100.0,
            buffer_size=100
        )

    def test_init(self):
        self.assertEqual(self.logger.logging_interval, 0.001)
        self.assertEqual(self.logger.write_interval, 0.01)
        self.assertEqual(self.logger.measurement_queue.maxsize, 100)

    def test_context_manager(self):
        with self.logger as l:
            time.sleep(0.05)  # Let it log some data
        # Verify logging was started and stopped
        self.assertIsNotNone(l.start_time)
        self.assertFalse(l.running.is_set())

    def test_start_stop_logging(self):
        self.logger.start_logging()
        self.assertTrue(isinstance(self.logger.logging_thread, threading.Thread))
        self.assertTrue(isinstance(self.logger.writer_thread, threading.Thread))
        time.sleep(0.05)  # Let it log some data
        self.logger.stop_logging()
        self.assertFalse(self.logger.running.is_set())

    def test_pause_resume(self):
        self.logger.start_logging()
        time.sleep(0.05)  # Let it log some data
        self.logger.pause()
        time.sleep(0.05)
        # Verify no new measurements added during pause
        self.assertEqual(self.logger.measurement_queue.qsize(), 0)  # Because pause flushes
        # verify logging paused
        self.assertFalse(self.logger.running.is_set())
        self.logger.resume()
        time.sleep(0.05)
        # Verify logging resumed
        self.assertTrue(self.logger.running.is_set())
        self.logger.stop_logging()

    def test_cleanup(self):
        self.logger.start_logging()
        time.sleep(0.05)
        self.logger.stop_logging()
        self.logger.cleanup()
        self.mock_db_writer.cleanup_continuous_logging.assert_called_once()

    def test_error_handling(self):
        # Set up error conditions
        self.mock_crane.getState.side_effect = Exception("Sensor error")
        self.mock_db_writer.store_measurements.side_effect = Exception("DB error")
        
        self.logger.start_logging()
        time.sleep(0.05)
        self.logger.stop_logging()
        # Should not raise exceptions, errors should be logged
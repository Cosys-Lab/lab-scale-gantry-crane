from abc import ABC, abstractmethod
from queue import Queue
import threading
import time
from datetime import datetime
import logging

from gantrylib.crane import Crane
from gantrylib.gantry_database_io import DatabaseInterface


class StateLoggerInterface(ABC):

    def __init__(self):
        self.crane = None

    @abstractmethod
    def start_logging(self) -> None:
        pass
    
    @abstractmethod
    def stop_logging(self) -> None:
        pass
    
    @abstractmethod
    def flush_buffer(self) -> None:
        pass

    @abstractmethod
    def pause(self) -> None:
        pass
    
    @abstractmethod
    def resume(self) -> None:
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        pass

class CraneStateLogger(StateLoggerInterface):
    def __init__(self, crane: Crane, db_writer: DatabaseInterface, logging_rate: float = 100.0, write_rate: float = 10.0, buffer_size: int = 1000, machine_id: int = 1) -> None:
        super().__init__()
        self.crane = crane
        self.db_writer = db_writer
        self.logging_interval = 1.0 / logging_rate
        self.write_interval = 1.0 / write_rate
        self.measurement_queue = Queue(maxsize=buffer_size)
        self.running = threading.Event()
        self.paused = threading.Event()
        self.logging_thread = None
        self.writer_thread = None
        self.machine_id = machine_id
        self.db_lock = threading.Lock()
        self.start_time = datetime.now()  # Store the start time for cleanup

    def __enter__(self):
        self.start_logging()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_logging()
        self.flush_buffer()

    def start_logging(self) -> None:
        self.running.set()
        self.paused.clear()
        self.logging_thread = threading.Thread(target=self._logging_loop)
        self.writer_thread = threading.Thread(target=self._writer_loop)
        self.logging_thread.start()
        self.writer_thread.start()

    def stop_logging(self) -> None:
        self.paused.clear()
        logging.info("Unpaused threads")
        self.running.clear()
        logging.info("Cleared running flag")
        if self.logging_thread and self.logging_thread.is_alive():
            self.logging_thread.join()
            logging.info("Logging thread joined")
        if self.writer_thread and self.writer_thread.is_alive():
            self.writer_thread.join()
            logging.info("Writer thread joined")

    def flush_buffer(self) -> None:
        """Write remaining measurements to database"""
        measurements = []
        while not self.measurement_queue.empty():
            measurements.append(self.measurement_queue.get())
        if measurements:
            with self.db_lock:
                try:
                    self.db_writer.store_state(self.machine_id, 0, measurements)
                except Exception as e:
                    logging.error(f"Failed to write measurements to database: {e}")

    def _logging_loop(self) -> None:
        """Main logging loop that captures crane state"""
        sample_count = 0
        start_run = time.time()
        while self.running.is_set():
            while self.paused.is_set():
                # If paused, wait until resumed
                time.sleep(0.1)

            start_time = time.time()
            
            try:
                x_cart, v_cart, x_hoist, v_hoist, theta, omega, wspeed = self.crane.getState()
                ts = datetime.now()

                # database unit is m, not mm, therefore divide by 1000
                measurement = (ts, x_cart/1000, v_cart/1000, x_hoist/1000, v_hoist/1000, theta, omega, wspeed)

                if not self.measurement_queue.full():
                    self.measurement_queue.put(measurement)
                else:
                    logging.warning("Measurement buffer full, dropping measurement")
                    
            except Exception as e:
                logging.error(f"Error logging crane state: {e}")

            # Sleep for remaining time to maintain logging rate
            elapsed = time.time() - start_time
            if elapsed < self.logging_interval:
                time.sleep(self.logging_interval - elapsed)
            else:
                logging.warning("Logging loop took too long, skipping sleep")
                time.sleep(0.1)  # attempt at fixing hang in the program that I don't get.

            sample_count += 1
            if sample_count % 50 == 0:  # Log stats every 50 samples
                elapsed = time.time() - start_run
                actual_rate = sample_count / elapsed
                logging.debug(f"Actual sampling rate: {actual_rate:.2f} Hz")

    def _writer_loop(self) -> None:
        """Main database writer loop"""
        measurements = []
        seen_timestamps = set()  # Track timestamps we've already processed

        while self.running.is_set():
            while self.paused.is_set():
                # If paused, wait until resumed
                time.sleep(0.1)

            start_time = time.time()
            
            # Collect measurements from queue
            while not self.measurement_queue.empty():
                measurement = self.measurement_queue.get()
                ts = measurement[0]  # Get timestamp from measurement tuple

                # Only add if we haven't seen this timestamp before
                if ts not in seen_timestamps:
                    measurements.append(measurement)
                    seen_timestamps.add(ts)
                else:
                    logging.warning(f"Duplicate timestamp detected: {ts}")

            # Write to database if enough time has passed
            if measurements:
                with self.db_lock:
                    try:          
                        self.db_writer.store_state(self.machine_id, 0, measurements)
                        logging.debug(f"Wrote {len(measurements)} measurements to database")
                        measurements = []
                        seen_timestamps.clear()
                    except Exception as e:
                        logging.error(f"Failed to write measurements to database: {e}")

            # Sleep for remaining time to maintain writing rate
            elapsed = time.time() - start_time
            if elapsed < self.write_interval:
                time.sleep(self.write_interval - elapsed)
            else:
                logging.warning("Writer loop took too long, skipping sleep")
                time.sleep(0.1)  # attempt at fixing hang in the program that I don't get.
                
    def pause(self) -> None:
        """Pause logging temporarily"""
        self.paused.set()
        
    def resume(self) -> None:
        """Resume logging"""
        self.paused.clear()

    def cleanup(self) -> None:
        """Remove all logged data from database"""
        if self.start_time:
            try:
                self.db_writer.cleanup_continuous_logging(self.start_time, self.machine_id)
                logging.info(f"Continuous logging data cleaned up from start time {self.start_time} for machine ID {self.machine_id}")
            except Exception as e:
                logging.error(f"Failed to cleanup continuous logging data: {e}")

class NullStateLogger(StateLoggerInterface):

    def start_logging(self) -> None:
        pass
    
    def stop_logging(self) -> None:
        pass
    
    def flush_buffer(self) -> None:
        pass
        
    def pause(self) -> None:
        pass
    
    def resume(self) -> None:
        pass
    
    def cleanup(self) -> None:
        pass
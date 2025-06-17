from abc import ABC, abstractmethod
from queue import Queue
import threading
import time
from datetime import datetime
import logging


class StateLoggerInterface(ABC):
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
    def __init__(self, crane, db_writer, logging_rate: float = 100.0, write_rate: float = 10.0, buffer_size: int = 1000):
        self.crane = crane
        self.db_writer = db_writer
        self.logging_interval = 1.0 / logging_rate
        self.write_interval = 1.0 / write_rate
        self.measurement_queue = Queue(maxsize=buffer_size)
        self.running = threading.Event()
        self.logging_thread = None
        self.writer_thread = None

    def __enter__(self):
        self.start_logging()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_logging()
        self.flush_buffer()

    def start_logging(self) -> None:
        self.start_time = datetime.now()
        self.running.set()
        self.logging_thread = threading.Thread(target=self._logging_loop)
        self.writer_thread = threading.Thread(target=self._writer_loop)
        self.logging_thread.start()
        self.writer_thread.start()

    def stop_logging(self) -> None:
        self.running.clear()
        if self.logging_thread and self.logging_thread.is_alive():
            self.logging_thread.join()
        if self.writer_thread and self.writer_thread.is_alive():
            self.writer_thread.join()

    def flush_buffer(self) -> None:
        """Write remaining measurements to database"""
        measurements = []
        while not self.measurement_queue.empty():
            measurements.append(self.measurement_queue.get())
        if measurements:
            try:
                self.db_writer.store_measurements(measurements, run_id=0)
            except Exception as e:
                logging.error(f"Failed to write measurements to database: {e}")

    def _logging_loop(self) -> None:
        """Main logging loop that captures crane state"""
        while self.running.is_set():
            start_time = time.time()
            
            try:
                x_cart, v_cart, x_hoist, v_hoist, theta, omega, wspeed = self.crane.getState()
                timestamp = datetime.now()

                measurement = {
                    'timestamp': timestamp,
                    'x_cart': x_cart,
                    'v_cart': v_cart, 
                    'x_hoist': x_hoist,
                    'v_hoist': v_hoist,
                    'theta': theta,
                    'omega': omega,
                    'windspeed': wspeed
                }
                
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

    def _writer_loop(self) -> None:
        """Main database writer loop"""
        measurements = []
        last_write = time.time()

        while self.running.is_set():
            current_time = time.time()
            
            # Collect measurements from queue
            while not self.measurement_queue.empty():
                measurements.append(self.measurement_queue.get())

            # Write to database if enough time has passed
            if current_time - last_write >= self.write_interval and measurements:
                try:
                    self.db_writer.store_measurements(measurements, run_id=0)
                    measurements = []
                    last_write = current_time
                except Exception as e:
                    logging.error(f"Failed to write measurements to database: {e}")

            time.sleep(0.1)  # Prevent busy waiting
    
    def pause(self) -> None:
        """Pause logging temporarily"""
        self.running.clear()
        # Flush current buffer before pausing
        self.flush_buffer()
        
    def resume(self) -> None:
        """Resume logging"""
        self.running.set()

    def cleanup(self) -> None:
        """Remove all logged data from database"""
        if self.start_time:
            try:
                self.db_writer.cleanup_continuous_logging(self.start_time)
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
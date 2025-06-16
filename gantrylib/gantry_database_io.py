from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import psycopg
import logging
import numpy as np

class DatabaseInterface(ABC):
    """Abstract base class for database operations"""

    @abstractmethod
    def connect(self):
        """Establish connection to the database"""
        pass

    @abstractmethod
    def disconnect(self):
        """Close database connection"""
        pass

    @abstractmethod
    def get_next_run_id(self, machine_id: int) -> int:
        """Get the next available run ID for given machine"""
        pass

    @abstractmethod
    def store_run(self, run_id: int, machine_id: int, start_time: datetime):
        """Store run information"""
        pass

    @abstractmethod
    def store_trajectory(self, machine_id: int, run_id: int, trajectory: tuple):
        """Store trajectory data"""
        pass

    @abstractmethod
    def store_measurement(self, machine_id: int, run_id: int, measurement: tuple):
        """Store measurement data"""
        pass

class PostgresDatabase(DatabaseInterface):
    """PostgreSQL implementation of DatabaseInterface"""

    def __init__(self, host: str, dbname: str, user: str, password: str):
        self.connection_string = f"host={host} dbname={dbname} user={user} password={password}"
        self.conn = None

    def connect(self):
        try:
            self.conn = psycopg.connect(self.connection_string)
            logging.info("Connected to PostgreSQL database")
        except Exception as e:
            logging.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self):
        if self.conn:
            try:
                self.conn.close()
                logging.info("Disconnected from PostgreSQL database")
            except Exception as e:
                logging.error(f"Error disconnecting from database: {e}")

    def get_next_run_id(self, machine_id: int) -> int:
        if not self.conn:
            return 0
        
        with self.conn.cursor() as cur:
            cur.execute("SELECT MAX(run_id) FROM run WHERE machine_id = %s", (machine_id,))
            try:
                run_id = cur.fetchall()[0][0] + 1
            except Exception:
                # if an exception occurs, there simply aren't any runs yet.
                # so add run number 0.
                run_id = 0
        return run_id

    def store_run(self, run_id: int, machine_id: int, start_time: datetime):
        if not self.conn:
            return
        
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO run (run_id, machine_id, starttime) VALUES (%s, %s, %s)",
                (run_id, machine_id, start_time)
            )
        self.conn.commit()

    def store_trajectory(self, machine_id: int, run_id: int, trajectory: tuple):
        if not self.conn:
            return

        with self.conn.cursor() as cur:
            with cur.copy("COPY trajectory (ts, machine_id, run_id, quantity, value) FROM stdin") as copy:
                quantities = ['position', 'velocity', 'acceleration', 
                            'angular position', 'angular velocity',
                            'angular acceleration', 'force']
                for idx, qty in enumerate(quantities, 1):
                    for (t, data) in zip(trajectory[0], trajectory[idx]):
                        copy.write_row((t, machine_id, run_id, qty, data))
        self.conn.commit()

    def store_measurement(self, machine_id: int, run_id: int, measurement: tuple):
        if not self.conn:
            return

        with self.conn.cursor() as cur:
            with cur.copy("COPY measurement (ts, machine_id, run_id, quantity, value) FROM stdin") as copy:
                quantities = ['position', 'velocity', 'acceleration', 
                            'angular position', 'angular velocity']
                for idx, qty in enumerate(quantities, 1):
                    for (ts, data) in zip(measurement[0], measurement[idx]):
                        copy.write_row((ts, machine_id, run_id, qty, data))
        self.conn.commit()

class MockDatabase(DatabaseInterface):
    """Mock database implementation for testing"""
    def connect(self):
        pass

    def disconnect(self):
        pass

    def get_next_run_id(self, machine_id: int) -> int:
        return 0

    def store_run(self, run_id: int, machine_id: int, start_time):
        pass

    def store_trajectory(self, machine_id: int, run_id: int, trajectory: tuple):
        pass

    def store_measurement(self, machine_id: int, run_id: int, measurement: tuple):
        pass

class NullDatabase(DatabaseInterface):
    """Null object pattern implementation for when no database is needed"""
    def connect(self):
        pass

    def disconnect(self):
        pass

    def get_next_run_id(self, machine_id: int) -> int:
        return 0

    def store_run(self, run_id: int, machine_id: int, start_time):
        pass

    def store_trajectory(self, machine_id: int, run_id: int, trajectory: tuple):
        pass

    def store_measurement(self, machine_id: int, run_id: int, measurement: tuple):
        pass
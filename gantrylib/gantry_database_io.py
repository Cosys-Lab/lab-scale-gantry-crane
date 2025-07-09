from abc import ABC, abstractmethod
from datetime import datetime
from typing import List
import psycopg
import logging

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

    @abstractmethod
    def store_state(self, machine_id: int, run_id: int, state: tuple):
        """Store state data"""
        pass

    @abstractmethod
    def commit(self):
        """Commit current transaction"""
        pass

    @abstractmethod
    def cleanup_continuous_logging(self, start_time: datetime, machine_id: int) -> None:
        """Remove continuous logging data from start_time onwards"""
        pass

class PostgresDatabase(DatabaseInterface):
    """PostgreSQL implementation of DatabaseInterface"""

    def __init__(self, host: str, dbname: str, user: str, password: str, auto_commit: bool = False):
        self.connection_string = f"host={host} dbname={dbname} user={user} password={password}"
        self.conn = None
        self.auto_commit = auto_commit

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
        if self.auto_commit:
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
        if self.auto_commit:
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
        if self.auto_commit:
            self.conn.commit()
    
    def store_state(self, machine_id: int, run_id: int, state: tuple):
        if not self.conn:
            return
        
        state = tuple(map(list, zip(*state)))  # Convert list of tuples to tuple of lists for copy

        try:
            with self.conn.cursor() as cur:
                with cur.copy("COPY measurement (ts, machine_id, run_id, quantity, value) FROM stdin") as copy:
                    quantities = ['position', 'velocity', 'position vertical', 'velocity vertical',
                                'angular position', 'angular velocity', 'windspeed']
                    for idx, qty in enumerate(quantities, 1):
                        for (ts, data) in zip(state[0], state[idx]):
                            copy.write_row((ts, machine_id, run_id, qty, data))
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Error storing state data: {e}")
            
        if self.auto_commit:
            self.conn.commit()

    def commit(self):
        self.conn.commit()

    def cleanup_continuous_logging(self, start_time: datetime, machine_id: int) -> None:
        """Remove all measurements with run_id=0 from start_time onwards"""
        if not self.conn:
            return
        
        with self.conn.cursor() as cur:
            cur.execute(
                """DELETE FROM measurement
                   WHERE run_id = 0
                   AND ts >= %s
                   AND machine_id = %s""",
                (start_time, machine_id)
            )
        if self.auto_commit:
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

    def commit(self):
        pass

    def cleanup_continuous_logging(self, start_time: datetime, machine_id: int) -> None:
        pass

    def store_state(self, machine_id: int, run_id: int, state: tuple):
        pass

class NullDatabase(DatabaseInterface):
    """Null object pattern implementation for when no database is needed"""
    def connect(self):
        pass

    def disconnect(self):
        pass

    def get_next_run_id(self, machine_id: int) -> int:
        logging.warning("NullDatabase: get_next_run_id called, returning 0")
        return 0

    def store_run(self, run_id: int, machine_id: int, start_time):
        logging.warning("NullDatabase: store_run called, but no action taken")
        pass

    def store_trajectory(self, machine_id: int, run_id: int, trajectory: tuple):
        logging.warning("NullDatabase: store_trajectory called, but no action taken")
        pass

    def store_measurement(self, machine_id: int, run_id: int, measurement: tuple):
        logging.warning("NullDatabase: store_measurement called, but no action taken")
        pass

    def commit(self):
        logging.warning("NullDatabase: commit called, but no action taken")
        pass

    def cleanup_continuous_logging(self, start_time: datetime, machine_id: int) -> None:
        logging.warning("NullDatabase: cleanup_continuous_logging called, but no action taken")
        pass

    def store_state(self, machine_id: int, run_id: int, state: tuple):
        logging.warning("NullDatabase: store_state called, but no action taken")
        pass
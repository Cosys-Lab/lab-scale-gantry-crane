import unittest
from datetime import datetime, timedelta
from gantrylib.gantry_database_io import PostgresDatabase

class TestDatabaseIO(unittest.TestCase):
    def setUp(self):
        self.pg_db = PostgresDatabase(
            host='localhost',
            dbname='gantrycrane',
            user='postgres', 
            password='postgres',
            auto_commit=False
        )
        
    def test_postgres_connection(self):
        self.pg_db.connect()
        self.assertIsNotNone(self.pg_db.conn)
        self.pg_db.disconnect()
        
    def test_get_next_run_id(self):
        self.pg_db.connect()
        run_id = self.pg_db.get_next_run_id(1)
        self.assertIsInstance(run_id, int)
        self.pg_db.disconnect()
        
    def test_store_run(self):
        self.pg_db.connect()
        test_time = datetime.now()
        run_id = self.pg_db.get_next_run_id(1)
        self.pg_db.store_run(run_id, 1, test_time)
        self.pg_db.disconnect()
        
    def test_store_trajectory(self):
        self.pg_db.connect()
        run_id = self.pg_db.get_next_run_id(1)
        test_time = datetime.now()
        self.pg_db.store_run(run_id, 1, test_time)
        
        base_time = datetime.now()
        timestamps = [base_time + timedelta(seconds=0.1*i) for i in range(3)]
        trajectory = (
            timestamps,  # timestamps as datetime objects
            [1.0, 1.1, 1.2],  # position
            [0.1, 0.2, 0.3],  # velocity
            [0.01, 0.02, 0.03],  # acceleration
            [0.1, 0.2, 0.3],  # angular position
            [0.01, 0.02, 0.03],  # angular velocity
            [0.001, 0.002, 0.003],  # angular acceleration
            [5.0, 5.1, 5.2]  # force
        )
        self.pg_db.store_trajectory(1, run_id, trajectory)
        self.pg_db.disconnect()

    def test_store_measurement(self):
        self.pg_db.connect()
        run_id = self.pg_db.get_next_run_id(1)
        test_time = datetime.now()
        self.pg_db.store_run(run_id, 1, test_time)

        base_time = datetime.now()
        timestamps = [base_time + timedelta(seconds=0.1*i) for i in range(3)]
        measurement = (
            timestamps,  # timestamps as datetime objects
            [1.0, 1.1, 1.2],  # position
            [0.1, 0.2, 0.3],  # velocity 
            [0.01, 0.02, 0.03],  # acceleration
            [0.1, 0.2, 0.3],  # angular position
            [0.01, 0.02, 0.03]  # angular velocity
        )
        self.pg_db.store_measurement(1, run_id, measurement)
        self.pg_db.disconnect()

    def test_store_state(self):
        self.pg_db.connect()
        run_id = self.pg_db.get_next_run_id(1)
        test_time = datetime.now()
        self.pg_db.store_run(run_id, 1, test_time)

        base_time = datetime.now()
        state = [
            (base_time + timedelta(seconds=0.1*i),  # timestamp
             1.0 + i*0.1,  # position
             0.1 + i*0.1,  # velocity
             0.5 + i*0.1,  # position vertical
             0.2 + i*0.1,  # velocity vertical
             0.1 + i*0.1,  # angular position
             0.01 + i*0.01,  # angular velocity
             2.0 + i*0.1)  # windspeed
            for i in range(3)
        ]
        self.pg_db.store_state(1, run_id, state)
        self.pg_db.disconnect()

if __name__ == '__main__':
    unittest.main()
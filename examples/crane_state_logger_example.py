# Not tested, just for reference on how to set up the logger with a controller and database.

from unittest.mock import Mock
from gantrylib.gantry_database_io import PostgresDatabase
from gantrylib.gantry_state_logger import CraneStateLogger
from gantrylib.gantry_controller import GantryController
from gantrylib.crane import Crane   
import time
import numpy as np
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

mock_crane = Mock()
pg_db = PostgresDatabase(
    host='localhost',
    dbname='gantrycrane',
    user='postgres', 
    password='postgres',
    auto_commit=True
)
pg_db.connect()
# Set mock crane state return value
def get_mock_state():
    t = time.time()
    return (
        np.sin(2*np.pi*1*t),    # 1 Hz
        np.sin(2*np.pi*2*t),    # 2 Hz
        np.sin(2*np.pi*5*t),    # 5 Hz
        np.sin(2*np.pi*10*t),   # 10 Hz
        np.sin(2*np.pi*20*t),   # 20 Hz
        np.sin(2*np.pi*40*t),   # 40 Hz
        np.sin(2*np.pi*100*t)    # 100 Hz
    )

mock_crane.getState.side_effect = get_mock_state

logger = CraneStateLogger(
    mock_crane, 
    pg_db,
    logging_rate=100.0,
    write_rate=10,
    buffer_size=150
)

# run for 5 seconds to populate the database
with logger as l:
    # l.start_logging() the context manager already calls this...
    start_time = time.time()
    while time.time() - start_time < 1.555:
        queue_size = l.measurement_queue.qsize()
        if queue_size > 0:
            logging.debug(f"Queue size: {queue_size}")
        time.sleep(0.2)
    l.stop_logging()
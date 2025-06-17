# Not tested, just for reference on how to set up the logger with a controller and database.

from gantrylib.gantry_database_io import PostgresDatabase
from gantrylib.gantry_state_logger import CraneStateLogger
from gantrylib.gantry_controller import GantryController
from gantrylib.crane import Crane   

# Create single database instance
db = PostgresDatabase(
    host="localhost",
    dbname="gantry",
    user="user",
    password="password"
)
db.connect()

# when using two instances here, probably best to have the logger use auto_commit=True
# and the controller use auto_commit=False (since you only want to write a complete trajectory)
# that means you run two instances of the PostgresDatabase

# Use same db instance for both components
crane = Crane(config)
controller = GantryController(crane, db)
logger = CraneStateLogger(crane, db)

try:
    with logger:
        controller.execute_trajectory(...)
finally:
    db.disconnect()
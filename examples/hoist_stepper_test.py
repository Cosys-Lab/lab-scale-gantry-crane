import time
import yaml
from gantrylib.motors import HoistStepper
import logging

logging.basicConfig(level=logging.DEBUG)

# Load config from YAML
with open("./crane-properties.yaml", "r") as f:
    config = yaml.safe_load(f)

# Extract relevant config values
port = config.get("hoist_motor_port", "COM11")
calibrated = config.get("hoist_calibrated", False)
encoder_counts = config.get("hoist_encoder_counts", 65536)
pulley_circumference = config.get("hoist_pulley_circumference", 66)
position_limit = config.get("hoist_position_limit", 200)

# Initialize HoistStepper (will home if not calibrated)
hoist = HoistStepper(
    port=port,
    calibrated=calibrated,
    encoder_counts=encoder_counts,
    pulley_circumference=pulley_circumference,
    position_limit=position_limit
)

# Move up and down between 0 and 20 cm (0.2 m)
for _ in range(3):
    print("Moving to 20 cm...")
    hoist.movePosition(200)  # 200 mm = 20 cm
    time.sleep(3)
    print("Moving to 0 cm...")
    hoist.movePosition(0)
    time.sleep(3)
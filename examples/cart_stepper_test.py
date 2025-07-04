import time
import yaml
from gantrylib.motors import CartStepper
import logging

logging.basicConfig(level=logging.INFO)

# Load config from YAML
with open("./crane-properties.yaml", "r") as f:
    config = yaml.safe_load(f)

# Extract relevant config values
port = config.get("cart_motor_port", "COM11")
calibrated = config.get("cart_calibrated", False)
encoder_counts = config.get("cart_encoder_counts", 65536)
pulley_circumference = config.get("cart_pulley_circumference", 40)
position_limit = config.get("cart_position_limit", 630)

# Initialize CartStepper (will home if not calibrated)
cart = CartStepper(
    port=port,
    calibrated=calibrated,

    encoder_counts=encoder_counts,
    pulley_circumference=pulley_circumference,
    position_limit=position_limit
)

# Move back and forth between 0 and 20 cm (0.2 m)
for _ in range(3):
    print("Moving to 20 cm...")
    cart.movePosition(200*cart.mm_to_counts)  # 200 mm = 20 cm
    time.sleep(3)
    print("Moving to 0 cm...")
    cart.movePosition(0*cart.mm_to_counts)
    time.sleep(3)

# logging.info("Position limit")
# logging.info(cart.position_limit)

# cart.setTorqueMode()
# cart.setTorque(0)  # Disable torque

# logging.info("printing position")
# while True:
#     logging.info(cart.getPosition())
#     time.sleep(1)  # Poll position every 100 ms

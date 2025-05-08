"""
Script that calibrates the crane (zeros all axes).

Should only be run once after crane has been connected.

Rerun if crane has been moved incorrectly.
"""

import logging
import sys
from  gantrylib.gantry_controller import PhysicalGantryController

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    with PhysicalGantryController("./crane-properties.yaml") as gc:
        pass
import tkinter as tk
from unittest.mock import MagicMock
from gantrylib.gantry_controller import MockGantryController
from gantrylib.hmi import MotionGUI
import yaml


if __name__ == "__main__":
    root = tk.Tk()
    with open("./crane-properties.yaml", "r") as file:
        crane_properties = yaml.safe_load(file)
        with MockGantryController(crane_properties) as crane_controller:
            mock_crane = MagicMock()
            mock_crane.getState = MagicMock(return_value=(0, 0, 0, 0, 0, 0, 0))
            crane_controller.crane = mock_crane
            app = MotionGUI(root, crane_controller)
            root.mainloop()
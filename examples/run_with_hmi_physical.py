import tkinter as tk
from gantrylib.gantry_controller import PhysicalGantryController
from gantrylib.hmi import MotionGUI
import yaml


if __name__ == "__main__":
    root = tk.Tk()
    with open("./crane-properties.yaml", "r") as file:
        crane_properties = yaml.safe_load(file)
        with PhysicalGantryController(crane_properties) as crane_controller:
            app = MotionGUI(root, crane_controller)
            root.mainloop()
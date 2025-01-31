import logging
import sys
from matplotlib import pyplot as plt

from gantrylib.gantry_controller import PhysicalGantryController

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    with PhysicalGantryController("./crane-properties.yaml") as gc:
        gc.hoist(0.3)
        traj, meas = gc.moveWithoutLog(0.6)
        fig, (ax1, ax2, ax3, ax4) = plt.subplots(4)
        ax1.plot(traj[0], traj[1])
        ax1.plot(meas[0], meas[1])
        ax2.plot(traj[0], traj[2])
        ax2.plot(meas[0], meas[2])
        ax3.plot(traj[0], traj[4])
        ax3.plot(meas[0], meas[4])
        ax4.plot(traj[0], traj[3])
        ax4.plot(meas[0], meas[3])
        plt.show()
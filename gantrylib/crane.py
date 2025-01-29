# class for the tmc4671 based crane
# based on stepper_config.py

import time
from datetime import datetime, timedelta
import numpy as np
from gantryLib.motors import GantryStepper, HoistStepper
import re
import serial

from pytrinamic.connections import ConnectionManager
from pytrinamic.ic import TMC4671
from scipy.signal import savgol_filter
from scipy.signal import correlate

import logging

class Crane:
    """
    Class to control the crane.
    """

    def __init__(self, gantryPort, hoistPort, angleUARTPort, gantryUARTPort, calibrated = False, I_max = 1) -> None:
        
        # create motors
        self.gantryStepper = GantryStepper(port=gantryPort, calibrated=calibrated, I_max= I_max)
        self.hoistStepper = HoistStepper(port=hoistPort, calibrated=calibrated)
        # set waypoints to empty
        self.waypoints = []

        # create serial connections for logging, or None if no logging is needed.
        if angleUARTPort is not None:
            self.angleUART = serial.Serial(angleUARTPort, 115200)
        else:
            self.angleUART = None

        # angle pattern regex
        self.pattern = re.compile(r"(-?\d*\.\d*) (-?\d*\.\d*)\r\n")

        # last angle
        self.lastAngle = 0
        self.lastAccel = 0
        self.lastOmega = 0

        self.buffer = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.gantryStepper.mc_interface.close()
        self.hoistStepper.mc_interface.close()
        if self.angleUART is not None:
            self.angleUART.close()
        self.gantryUART.close()

    def setWaypoints(self, waypoints):
        self.waypoints = waypoints

    def executeWaypointsPositionV3(self):
        """
        Attempt to execute the waypoints in position mode,
        works with "global" timing rather than delta timing.

        """
        self.gantryStepper.setPositionMode()

        # logging:
        # we can log the following: t, x, v, theta
        # omega is not logged but is calculated afterwards
        # by differentiating theta w.r.t. t

        # assume t = 0
        t = [0]
        x = [self.gantryStepper.getPosition()/self.gantryStepper.mm_to_counts]
        v = [0]
        theta = [0]
        omega_arduino = [0]
        a = [0]
        wp_dt = []
        # reset angle logger input buffer
        if self.angleUART is not None:
            self.angleUART.reset_input_buffer()

        # set target position
        self.gantryStepper.setAccelLimit(2147483647)
        self.gantryStepper.setVelocityLimit(abs(self.waypoints[1].v*self.gantryStepper.mm_s_to_rpm))
        t0 = time.time()
        now = 0
        self.gantryStepper.setPosition(self.waypoints[-1].x * self.gantryStepper.mm_to_counts)

        for wp in self.waypoints[1:]:
            
            wp_start = time.time()
            # in proper version I must not forget to consider direction of the movement as well.
            while(now < wp.t):
                now = time.time() - t0

            self.gantryStepper.setVelocityLimit(abs(wp.v)*self.gantryStepper.mm_s_to_rpm)
            
            # logging
            
            t.append(time.time() - t0)
            tick = time.time()
            #x.append(self.mc.read_register(self.mc.REG.PID_POSITION_ACTUAL, signed=True))
            x.append(self.gantryStepper.getPosition()) 
            #v.append(self.mc.read_register(self.mc.REG.PID_VELOCITY_ACTUAL, signed=True))
            v.append(self.gantryStepper.getVelocity())
            dt = time.time() - tick
            new_a, new_theta, new_omega = self.readAngle()
            theta.append(new_theta)
            a.append(new_a)
            omega_arduino.append(new_omega)
            
            #print("logging time:" +str(dt)) 
            wp_end = time.time()
            wp_dt.append(wp_end-wp_start)


        self.gantryStepper.setTorqueMode()
        # self.hoistStepper.setTorqueMode()
        self.gantryStepper.setTorque(0)
        # self.hoistStepper.setTorque(0)

        # For logging:
        # returned angle requires scaling and is expected to be in radians
        # also need to flip the sign
        # (for scaling, see curve_fitting.py in angle-calibration folder)
        theta = [-1/0.806*angle*2*np.pi/360 for angle in theta] # 0.806 is experimentally derived scaling factor of angle
        omega_arduino = [-1/0.806*angular_vel*2*np.pi/360 for angular_vel in omega_arduino]
        # we don't have omega, calculate it with numpy gradient
        # apply filtering first because taking derivative gets noisy quick
        omega = np.gradient(savgol_filter(np.array(theta), 15, 6), np.array(t))
        # x is still in counts and should be in meters
        x = [xs/self.gantryStepper.mm_to_counts/1000 for xs in x]
        # v is also in the wrong unit, should m/s^2
        v = [vs/self.gantryStepper.mm_s_to_rpm/1000 for vs in v]

        logging.info("wp dt:" + str(wp_dt))
        logging.info("dt: " + str(np.array(t[1:-1]) - np.array(t[0:-2])))
        logging.info("tstep: " + str(len(t)))
        logging.info("max dt" + str(max(np.array(t[1:-1]) - np.array(t[0:-2]))))
        logging.info("a" + str(a))

        logging.info("Comparison between two omegas")
        logging.info("Arduino based:" + str(omega_arduino))
        logging.info("derivation based:" + str(omega))

        omega = omega_arduino

        # there seems to be a small chance that two timestamps are the same,
        # which gives an error when writing to database.
        # Likely has to do with the microsecond accuracy of datetime 
        # solution: round to microseconds, then use numpy unique to filter out duplicates.
        un, un_idx = np.unique(np.round(np.array(t),6), return_index=True)

        t = np.array(t)[un_idx]
        theta = np.array(theta)[un_idx]
        omega = np.array(omega)[un_idx]
        x = np.array(x)[un_idx]
        v = np.array(v)[un_idx]
        a = np.array(a)[un_idx]
        
        return (t, x, v, a, theta, omega)

    def _testMove(self):
        self.gantryStepper._testMove()
        # self.hoistStepper._testMove()

    def homeAllAxes(self):
        self.gantryStepper.setPositionMode()
        # self.hoistStepper.setPositionMode()
        self.gantryStepper.setPosition(0)
        # self.hoistStepper.setPosition(0)
        self.gantryStepper.setLimits(acc=2147483647, vel=420)
        # self.hoistStepper.setLimits(acc=2147483647, vel=420)

        start = time.time()
        while(round(self.gantryStepper.getPosition(), -2) != 0 and round(self.gantryStepper.getPosition(), -2) !=0 and time.time() - start < 20):
            pass

    def homeGantry(self):
        self.gantryStepper.setPositionMode()
        self.gantryStepper.setPosition(0)
        self.gantryStepper.setLimits(acc=2147483647, vel=420)

        start = time.time()
        while(round(self.gantryStepper.getPosition(), -2) != 0 and time.time() - start < 20):
            pass
    
    def readAngle(self):
        if self.angleUART is not None:
            # Add incoming data to the buffer
            self.buffer += self.angleUART.read(self.angleUART.in_waiting).decode('utf-8')

            # Find all matches in the buffer
            matches = self.pattern.findall(self.buffer)

            # Check if a match is found
            if matches:
                last_match = matches[-1]

                theta = -1* float(last_match[0])
                omega = -1* float(last_match[1])

                # Remove the parsed data from the buffer, keep only the last (unparsed) part
                self.buffer = self.buffer.split(last_match[2])[-1]
 
                self.lastAngle = theta # * 1/0.76023946 scale factor that might be needed
                self.lastOmega = omega
                return a, theta, omega
            else:
                # No match found, return None
                logging.info("no match, returning previous values")
                return 0, self.lastAngle, self.lastOmega
        else:
            return (0, 0, 0)


class Waypoint():

    def __init__(self, t, x, v, a, l = 150, dr = 0, ddr = 0) -> None:
        self.x = x
        self.v = v
        self.a = a
        self.l = l
        self.dr = dr
        self.ddr = ddr
        self.t = t


# class for the tmc4671 based crane
# based on stepper_config.py

import struct
import time
import numpy as np
from gantrylib.motors import GantryStepper, HoistStepper
import re
import serial

from scipy.signal import savgol_filter

import logging

class Crane:
    """
    A class representing the gantrycrane.
    """

    def __init__(self, config: dict) -> None:
        """Initializes a Crane instance.

        Args:
            gantryPort (string): Serial port of the motor controller controlling the lateral movement motor.
            hoistPort (string): Serial port of the motor controller controlling the hoisting motor.
            angleUARTPort (string): Serial port of the Arduino that measures the swing angle
            gantryUARTPort (string): unused
            calibrated (bool, optional): Whether the crane's motors are already calibrated or not. Defaults to False.
            I_max (int, optional): Maximal motor current. Defaults to 1A
        """

        # create motors
        I_max = config["cart acceleration limit"] * 0.167 + 0.833
        self.gantryStepper = GantryStepper(port=config["gantryPort"], calibrated=config["calibrated"], I_max=I_max)
        self.hoistStepper = HoistStepper(port=config["hoistPort"], calibrated=config["calibrated"])
        # set waypoints to empty
        self.waypoints = []

        # create serial connections for logging, or None if no logging is needed.
        if config["angleUARTPort"] is not None:
            self.angleUART = serial.Serial(config["angleUARTPort"], 115200)
        else:
            self.angleUART = None

        # angle pattern regex
        # self.pattern = re.compile(r"(-?\d*\.\d*) (-?\d*\.\d*) (-?\d*\.\d*)\r\n")
        self.pattern = re.compile(b'\x01(.{12})') # new pattern for bytearrays and uncompressed floats.
        self.packet_size = 13
        self.start_byte = 0x01

        # last angle
        self.lastAngle = 0
        self.lastAccel = 0
        self.lastOmega = 0
        self.lastwindspeed = 0

        #self.buffer = ""
        self.buffer = bytearray(b'')

        self.angleZero = 0
        self.windZero = 0

    def __enter__(self):
        """Enter the runtime context for the crane.

        Returns:
            Crane: The crane instance
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context and clean up resources.

        Args:
            exc_type (Type[BaseException] or None): The type of the exception if one was raised, else None.
            exc_value (BaseException or None): The exception instance if one was raised, else None.
            traceback (TracebackType or None): The traceback object if an exception was raised, else None.
        """
        self.gantryStepper.mc_interface.close()
        self.hoistStepper.mc_interface.close()
        if self.angleUART is not None:
            self.angleUART.close()
        self.gantryUART.close()

    def setWaypoints(self, waypoints):
        """Sets the waypoints to be executed by the crane.

        Args:
            waypoints (list[Waypoint]): List of Waypoints.
        """
        self.waypoints = waypoints

    def executeWaypointsPosition(self):
        """Attempt to execute the waypoints in position mode.

        Works by setting the waypoint and altering the motor's velocity limit as the trajectory moves along.

        Returns:
            tuple(list[float], list[float], list[float], list[float], list[float], list[float]): tuple(t, x, v, a, theta, omega), 
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
        wspeed = [0]
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
            new_theta, new_omega, new_wspeed = self.readAngle()
            new_a = 0 # not measured for now.
            theta.append(new_theta)
            a.append(new_a)
            omega_arduino.append(new_omega)
            wspeed.append(new_wspeed)
            
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
        """Make the crane perform a testmove

        Added for internal testing purposes, don't use.
        """
        self.gantryStepper._testMove()
        # self.hoistStepper._testMove()

    def homeAllAxes(self):
        """Homes all axes.

        Hoiststepper isn't homed, since we don't have a proper automated homing procedure for it.
        """
        self.gantryStepper.setPositionMode()
        # self.hoistStepper.setPositionMode()
        self.gantryStepper.setPosition(0)
        # self.hoistStepper.setPosition(0)
        self.gantryStepper.setLimits(acc=2147483647, vel=420)
        # self.hoistStepper.setLimits(acc=2147483647, vel=420)

        start = time.time()
        while(round(self.gantryStepper.getPosition(), -2) != 0 and round(self.gantryStepper.getPosition(), -2) !=0 and time.time() - start < 20):
            pass

    def homeCart(self):
        """Homes the cart on the gantry
        """
        if self.gantryStepper.calibrated:
            logging.info("Homing gantry")
            self.gantryStepper.setPositionMode()
            self.gantryStepper.setPosition(0)
            self.gantryStepper.setLimits(acc=2147483647, vel=420)

            start = time.time()
            while(round(self.gantryStepper.getPosition(), -2) != 0 and time.time() - start < 20):
                pass
            logging.info("Cart homed")
        else:
            self.gantryStepper._homeAndCalibrate()
    
    def homeHoist(self):
        logging.info("Homing hoist")
        # can't really home the hoist in closed loop mode, so do so with calbrate function.
        self.hoistStepper._homeAndCalibrate()
        logging.info("Hoist homed")
    
    def readAngle(self):
        """Reads the latest received angle from the angleUART

        Returns:
            tuple(float, float): Tuple(theta, omega)
        """
        if self.angleUART is not None:
            # Add incoming data to the buffer
            self.buffer += bytearray(self.angleUART.read(self.angleUART.in_waiting))

            # find all matches in the buffer
            matches = self.pattern.findall(self.buffer)

            # check if a match was found
            if matches:
                # Get the last match
                last = matches[-1]

                # Unpack the bytes into floats
                floats = struct.unpack('<fff', last)

                # Remove the processed bytes from the buffer
                self.buffer = self.buffer.split(last)[-1]
                self.lastAngle = floats[0] - self.angleZero
                self.lastOmega = floats[1]
                self.lastwindspeed = floats[2] - self.windZero
                return self.lastAngle, self.lastOmega, self.lastwindspeed
            else:
                return self.lastAngle, self.lastOmega, self.lastwindspeed
        else:
            return (0, 0, 0)
        
    def moveCartVelocity(self, velocity):
        self.gantryStepper.moveVelocity(velocity)

    def moveHoistVelocity(self, velocity):
        self.hoistStepper.moveVelocity(velocity)

    def moveCartPosition(self, position, velocity):
        self.gantryStepper.movePosition(position*1000*self.gantryStepper.mm_to_counts, velocity)

    def moveHoistPosition(self, position, velocity):
        logging.info(f"Hoist target position: {position*1000*self.hoistStepper.mm_to_counts}")
        self.hoistStepper.movePosition(position*1000*self.hoistStepper.mm_to_counts, velocity)

    def zeroWind(self):
        _, _, windspeed = self.readAngle()
        self.windZero = windspeed + self.windZero

    def zeroAngle(self):
        angle, _, _ = self.readAngle()
        self.angleZero = angle + self.angleZero

    def getState(self):
        x_cart = self.gantryStepper.getPositionMm()
        v_cart = self.gantryStepper.getVelocityMms()
        x_hoist = self.hoistStepper.getPositionMm()
        v_hoist = self.hoistStepper.getVelocityMms()
        (theta, omega, wspeed) = self.readAngle()
        return (x_cart, v_cart, x_hoist, v_hoist, theta, omega, wspeed)


class Waypoint():
    """A class representing a Waypoint, that is, one point in a trajectory
    """

    def __init__(self, t, x, v, a, l = 150, dr = 0, ddr = 0) -> None:
        self.x = x
        self.v = v
        self.a = a
        self.l = l
        self.dr = dr
        self.ddr = ddr
        self.t = t


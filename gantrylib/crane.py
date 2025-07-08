from threading import Thread
import threading
import time
import numpy as np
from gantrylib.motors import CartStepper, HoistStepper

from scipy.signal import savgol_filter

import logging
from abc import ABC, abstractmethod

from gantrylib.crane_io_uc_factory import CraneIOUCFactory

class Crane(ABC):
    """
    Abstract base class representing the crane interface.
    """

    @abstractmethod
    def homeCart(self):
        pass

    @abstractmethod
    def homeHoist(self):
        pass

    @abstractmethod
    def homeAllAxes(self):
        pass

    @abstractmethod
    def setWaypoints(self, waypoints):
        pass

    @abstractmethod
    def executeWaypointsPosition(self):
        pass

    @abstractmethod
    def moveCartVelocity(self, velocity):
        pass

    @abstractmethod
    def moveHoistVelocity(self, velocity):
        pass

    @abstractmethod
    def moveCartPosition(self, position, velocity):
        pass

    @abstractmethod
    def moveHoistPosition(self, position, velocity):
        pass

    @abstractmethod
    def getState(self):
        pass

class MockCrane(Crane):
    """
    Mock implementation of the Crane interface for testing.
    """

    def __init__(self, *args, **kwargs):
        self.waypoints = []
        self.angle = 0.0
        self.omega = 0.0
        self.windspeed = 0.0
        self.x_cart = 0.0
        self.v_cart = 0.0
        self.x_hoist = 0.0
        self.v_hoist = 0.0

    def setWaypoints(self, waypoints):
        self.waypoints = waypoints

    def executeWaypointsPosition(self):
        t = [0.0]
        x = [self.x_cart]
        v = [self.v_cart]
        a = [0.0]
        theta = [self.angle]
        omega = [self.omega]
        return (t, x, v, a, theta, omega)

    def homeAllAxes(self):
        self.x_cart = 0.0
        self.x_hoist = 0.0

    def homeCart(self):
        self.x_cart = 0.0

    def homeHoist(self):
        self.x_hoist = 0.0

    def moveCartVelocity(self, velocity):
        self.v_cart = velocity

    def moveHoistVelocity(self, velocity):
        self.v_hoist = velocity

    def moveCartPosition(self, position, velocity):
        self.x_cart = position
        self.v_cart = velocity

    def moveHoistPosition(self, position, velocity):
        self.x_hoist = position
        self.v_hoist = velocity

    def getState(self):
        return (self.x_cart, self.v_cart, self.x_hoist, self.v_hoist, self.angle, self.omega, self.windspeed)

class PhysicalCrane(Crane):
    """
    A class representing the gantrycrane.
    """

    def __init__(self, config: dict) -> None:
        """Initializes a Crane instance.
        """

        # create motors
        I_max = config["cart_acceleration_limit"] * 0.167 + 0.833 # where does this come from?
        self.cartStepper = CartStepper(port=config["cart_motor_port"], 
                                           calibrated=config["cart_calibrated"], 
                                           I_max=I_max, 
                                           encoder_counts=config["cart_encoder_counts"],
                                           position_limit=config["cart_position_limit"],
                                           pulley_circumference=config["cart_pulley_circumference"])
        self.hoistStepper = HoistStepper(port=config["hoist_motor_port"], 
                                         calibrated=config["hoist_calibrated"], 
                                         encoder_counts=config["hoist_encoder_counts"],
                                         position_limit=config["hoist_position_limit"],
                                         pulley_circumference=config["hoist_pulley_circumference"],)

        # create crane I/O uc interface.
        self.crane_io_uc = CraneIOUCFactory.create_crane_io_uc(config)

        # set waypoints to empty
        self.waypoints = []

        self.hoist_max_length = config["hoist_max_length"]  # Maximum length of the hoist cable in mm

        self.get_state_lock = threading.Lock()


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
        self.cartStepper.mc_interface.close()
        self.hoistStepper.mc_interface.close()
        if self.crane_io_uc is not None:
            self.crane_io_uc.close()
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
        self.cartStepper.setPositionMode()

        # logging:
        # we can log the following: t, x, v, theta
        # omega is not logged but is calculated afterwards
        # by differentiating theta w.r.t. t

        # assume t = 0
        t = [0]
        x = [self.cartStepper.getPositionMm()]
        v = [0]
        theta = [0]
        omega_arduino = [0]
        wspeed = [0]
        a = [0]
        wp_dt = []
        # reset angle logger input buffer
        if self.crane_io_uc is not None:
            self.crane_io_uc.reset_input_buffer()

        # set target position
        self.cartStepper.setAccelLimit(2147483647)
        self.cartStepper.setVelocityLimit(abs(self.waypoints[1].v*self.cartStepper.mm_s_to_rpm))
        t0 = time.time()
        now = 0
        self.cartStepper.setPositionMm(self.waypoints[-1].x)

        for wp in self.waypoints[1:]:
            
            wp_start = time.time()
            # in proper version I must not forget to consider direction of the movement as well.
            while(now < wp.t):
                now = time.time() - t0

            self.cartStepper.setVelocityLimit(abs(wp.v)*self.cartStepper.mm_s_to_rpm)
            
            # logging
            
            t.append(time.time() - t0)
            tick = time.time()
            #x.append(self.mc.read_register(self.mc.REG.PID_POSITION_ACTUAL, signed=True))
            x.append(self.cartStepper.getPositionMm()) 
            #v.append(self.mc.read_register(self.mc.REG.PID_VELOCITY_ACTUAL, signed=True))
            v.append(self.cartStepper.getVelocity())
            dt = time.time() - tick
            new_theta, new_omega, new_wspeed = self.crane_io_uc.getState()
            new_a = 0 # not measured for now.
            theta.append(new_theta)
            a.append(new_a)
            omega_arduino.append(new_omega)
            wspeed.append(new_wspeed)
            
            #print("logging time:" +str(dt)) 
            wp_end = time.time()
            wp_dt.append(wp_end-wp_start)


        self.cartStepper.setTorqueMode()
        # self.hoistStepper.setTorqueMode()
        self.cartStepper.setTorque(0)
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
        # x is in mm and should be in meters
        x = [xs/1000 for xs in x]
        # v is also in the wrong unit, should m/s^2 and not rpm
        v = [vs/self.cartStepper.mm_s_to_rpm/1000 for vs in v]

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
        self.cartStepper._testMove()
        # self.hoistStepper._testMove()

    def homeAllAxes(self):
        """Homes all axes.

        Hoiststepper isn't homed, since we don't have a proper automated homing procedure for it.
        """
        self.cartStepper.setPositionMode()
        # self.hoistStepper.setPositionMode()
        self.cartStepper.setPosition(0)
        # self.hoistStepper.setPosition(0)
        self.cartStepper.setLimits(acc=2147483647, vel=420)
        # self.hoistStepper.setLimits(acc=2147483647, vel=420)

        start = time.time()
        while(round(self.cartStepper.getPosition(), -2) != 0 and round(self.cartStepper.getPosition(), -2) !=0 and time.time() - start < 20):
            pass

    def homeCart(self):
        """Homes the cart on the gantry
        """
        if self.cartStepper.calibrated:
            logging.info("Homing gantry")
            self.cartStepper.setPositionMode()
            self.cartStepper.setPosition(0)
            self.cartStepper.setLimits(acc=2147483647, vel=420)

            start = time.time()
            while(round(self.cartStepper.getPosition(), -2) != 0 and time.time() - start < 20):
                pass
            logging.info("Cart homed")
        else:
            self.cartStepper._homeAndCalibrate()
    
    def homeHoist(self):
        logging.info("Homing hoist")
        # can't really home the hoist in closed loop mode, so do so with calbrate function.
        self.hoistStepper._homeAndCalibrate()
        logging.info("Hoist homed")   
        
    def moveCartVelocity(self, velocity):
        # velocity in rpm
        self.cartStepper.moveVelocity(velocity)

    def moveHoistVelocity(self, velocity):
        # velocity in rpm
        self.hoistStepper.moveVelocity(velocity)

    def moveCartPosition(self, position, velocity):
        # position in millimeters.
        # flip cart axis around (motors treat rightnmost position as 0, we treat leftmost position as 0)
        tgt_mot = abs(position - self.cartStepper.position_limit_mm)
        self.cartStepper.movePositionMm(tgt_mot, velocity)

    def moveHoistPosition(self, position, velocity):
        # position in millimeters.
        logging.info(f"Hoist target position: {position} mm")
        self.hoistStepper.movePositionMm(position, velocity)

    def moveHoistRopeLength(self, rope_length, velocity):
        # rope_length in millimeters.
        # With hoist length, we should just flip it around, longest length is position 0)
        rope_length = min(rope_length, self.hoistStepper.hoist_max_length)
        tgt_mot = abs(rope_length - self.hoistStepper.position_limit_mm)
        self.hoistStepper.movePositionMm(tgt_mot, velocity)

    def getRopeLength(self):
        return self.hoist_max_length - self.hoistStepper.getPositionMm()

    def getState(self):
        # is it getState that is not thread safe?
        # yes, seemed like it was. Logging should be fixed now?
        with self.get_state_lock:
            x_cart = self.cartStepper.getPositionMm()
            v_cart = self.cartStepper.getVelocityMms()
            x_hoist = self.hoistStepper.getPositionMm()
            v_hoist = self.hoistStepper.getVelocityMms()
            (theta, omega, wspeed) = self.crane_io_uc.getState()
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


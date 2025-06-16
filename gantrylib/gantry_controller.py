from abc import abstractmethod
from os import write
import pickle
from threading import Event
from typing_extensions import override
import yaml
from gantrylib.gantry_database_io_factory import GantryDatabaseFactory
from gantrylib.trajectory_generator import TrajectoryGenerator
import psycopg
from datetime import timedelta, datetime
from time import sleep
import logging
import sys
from gantrylib.crane import Crane, Waypoint
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import correlate

class GantryController():
    """A class representing a controller for the gantry crane
    """

    def __init__(self, config: dict) -> None:
        """Initialize a GantryController instance

        Args:
            config (dict): Configuration dictionary holding details of the gantry crane.
        """

        # machine identification in database
        self.id = config["machine id"]
        self.name = config["machine name"]
        # connection to database
        if config["connect to db"]:
            logging.info("Connecting to database")
            self.dbconn = GantryDatabaseFactory.create_database("postgres", config)
            self.dbconn.connect()
        else:
            logging.info("Not connecting to database")
            self.dbconn = GantryDatabaseFactory.create_database("none", config)

        self.simulatortopic = config["simulator topic"]
        self.validatortopic = config["validator topic"]

        self.tg = TrajectoryGenerator(config)

        self.run = self.dbconn.get_next_run_id(self.id)

        self.repls = config["replications"]

        logging.info("Initialized " + str(self))

        # initialize to None, PhysicalGantryController will override it.
        # Note to self: might break mockGantryController
        self.crane = None
        self.position = 0

    def __enter__(self):
        """Enter the runtime context of the gantry controller.

        Returns:
            GantryController: The instance of the GantryController
        """
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context and clean up resources

        Args:
            exc_type (Type[BaseException] or None): The type of the exception if one was raised, else None.
            exc_value (BaseException or None): The exception instance if one was raised, else None.
            traceback (TracebackType or None): The traceback object if an exception was raised, else None.
        """
        try:
            self.dbconn.disconnect()
        except Exception:
            pass
    
    @abstractmethod
    def connectToCrane(self):
        """Method to connect to the gantry crane.

        This method must be implemented by subclasses to define how to connect to a specific gantry crane.
        """
        pass
    
    def generateTrajectory(self, start, stop, genmethod = "ocp"):
        """Generate a trajectory using the trajectory generator

        Args:
            start (float): The start position of the trajectory
            stop (float): The stop position of the trajectory
            genmethod (str, optional): Method of generation, either "ocp" or "lqr". Defaults to "ocp".

        Returns:
            tuple: Tuple containing the trajectory
        """
        # retrieve rope length and configure it in the trajectory generator
        if self.crane:
            hoistpos = self.crane.hoistStepper.getPositionMm()
            logging.info(f"Hoist position is {hoistpos} mm")
            self.tg.r = (350-hoistpos)/1000
            logging.info(f"Rope length is {self.tg.r} m")
        if genmethod == 'ocp':
            return self.tg.generateTrajectory(start, stop)
        else:
            return self.tg.generateTrajectoryLQR(start, stop)

    def moveOptimally(self, target, generator = 'ocp', write_to_db = False, validate = False):
        """Make a movement and log it to a database

        Args:
            target (float): target position in meters
            generator (str, optional): Method of generation, either "ocp" or "lqr". Defaults to "ocp".

        Returns:
            tuple(tuple, tuple): A tuple containing the generated trajectory and the measured trajectory
        """
        if validate and not write_to_db:
            logging.info("Validation is not possible without writing to the database. Will not perform validation.")

        logging.info("Generating trajectory to " + str(target))
        traj = self.generateTrajectory(self.crane.gantryStepper.getPositionMm()/1000, target, generator)
        sleep(1.5) # sleep needed for initialization of the Arduino
        # TODO: check if the sleep is still needed? I don't think it is.
        logging.info("Trajectory generated")

        
        logging.info("Executing trajectory")
        t_start = datetime.now()
        measurement = self.executeTrajectory(traj)
        logging.info("Trajectory executed, updating position")
        self.position = measurement[1][-1]
        # align measurement to trajectory for storing
        measurement = self._align_measurement_to_trajectory(traj, measurement)

        # update traj en measurement to have timestamps in datetime format for db
        traj[0] = [t_start + timedelta(seconds=t) for t in traj[0]]
        measurement[0] = [t_start + timedelta(seconds=t) for t in measurement[0]]
        logging.info("Trajectory and measurement timestamps updated")

        if write_to_db:
            self._updateRunNumber()
            logging.info("Run number updated to " + str(self.run))
            # fetch run number from database
            logging.info("Storing in database")
            self.storeTrajectory(traj)

        if validate and write_to_db:
            logging.info("Trajectory stored, notifying simulator")
            self.notifySimulator()
            logging.info("Simulator notified")
        
        if write_to_db:
            logging.info("Storing measurement in database")
            self.storeMeasurement(measurement)
            logging.info("Measurement stored in database")

        if validate and write_to_db:
            logging.info("notifying validator")
            self.notifyValidator()
            logging.info("Validator notified")
        
        logging.info("Trajectory executed")
        return traj, measurement   

    @abstractmethod
    def executeTrajectory(self, traj):
        """Execute a trajectory

        This methods must be implemented by subclasses to define how the trajectory is executed.

        Args:
            traj (tuple): Trajectory tuple as returned by the TrajectoryGenerator
        """
        pass
    
    def moveTrajectoryWithoutLog(self, traj):
        """Move according to the given trajectory

        Args:
            traj (tuple): Trajectory as returned by the trajectory generator.

        Returns:
            tuple: The measured trajectory
        """
        # generate a trajectory to executs
        # trajectory is a tuple of shape: (ts, xs, dxs, ddxs, thetas, dthetas, ddthetas, us)
        # execute the trajectory
        # measurement is a tuple of shape (t, x, v, a, theta, omega)   
        sleep(2)
        measurement = self.executeTrajectory(traj)
        self.position = measurement[1][-1]
        # align measurement to trajectory for storing
        measurement = self._align_measurement_to_trajectory(traj, measurement)
        return measurement
    
    def _find_time_shift(self, time1, trace1, time2, trace2):
        """Finds the time shift between two traces

        Is used to correct any potential timeshift between the trajectory and the measurement.

        Args:
            time1 (list[float]): First time traces.
            trace1 (list[float]): First datapoints.
            time2 (list[float]): Second time traces
            trace2 (list[float]): Second datapoints.

        Returns:
            float: the time shift
        """        
        # Interpolate the second trace onto the time points of the first trace
        interpolated_trace2 = np.interp(time1, time2, trace2)

        # Cross-correlate the two traces
        cross_corr = correlate(trace1, interpolated_trace2, mode='full')

        # Find the index of the maximum correlation
        shift_index = np.argmax(cross_corr)
        zero_lag_index = len(trace1) - 1
        lag = shift_index - zero_lag_index

        # Compute time step (assumes uniform spacing)
        dt = time1[1] - time1[0]

        # Convert lag to time shift
        time_shift = lag * dt

        return time_shift
    
    def _align_time_based_signals(time1, trace1, time2, trace2):
        """Aligns two traces

        Args:
            time1 (list[float]): First time traces.
            trace1 (list[float]): First datapoints.
            time2 (list[float]): Second time traces.
            trace2 (list[float]): Second datapoints.

        Returns:
            list[float]: The algined trace.
        """        
        # Interpolate the second trace onto the time points of the first trace
        interpolated_trace2 = np.interp(time1, time2, trace2)

        # Cross-correlate the two traces
        cross_corr = correlate(trace1, interpolated_trace2, mode='full')

        # Find the index of the maximum correlation
        shift_index = np.argmax(cross_corr)

        # Calculate the time shift in samples
        time_shift = time1[shift_index] - time1[-1]

        # Interpolate the second trace again with the calculated time shift
        aligned_trace2 = np.interp(time1, time2 + time_shift, trace2)

        return aligned_trace2

    def _align_measurement_to_trajectory(self, traj, measurement):
        """Align a trajectory and measurement

        Args:
            traj (tuple): Trajectory tuple as given by trajectory generator.
            measurement (tuple): Measurement as measured by executing the trajectory.

        Returns:
            tuple: The aligned measurement
        """        
        # align measurements with the trajectory based on v trace
        measurement = list(measurement)
        # The time shift is in fact 1 sample of trajectory points, so I don't need
        # to compute it, I can get it from there.
        # note that this is great, because otherwise I'd have had a problem
        # when it comes to the faulty data.
        time_shift = self._find_time_shift(traj[0], traj[2], measurement[0], measurement[2])
        logging.info("time shift is " + str(time_shift) + " seconds")
        logging.info("difference between trajectory points" + str(traj[0][0] - traj[0][1]))
        time_shift = traj[0][0] - traj[0][1]
        for i in range(1, 6):
            measurement[i] = np.interp(traj[0], measurement[0] + time_shift, measurement[i])
        measurement[0] = traj[0]

        return tuple(measurement)
    
    @abstractmethod
    def simpleMove(self, target):
        """Perform a simple lateral move without trajectory generation

        Must be implemented by subclasses.

        Args:
            target (float): The target position
        """         
        pass

    @abstractmethod
    def hoist(self, pos):
        """Perform a hoisting movement

        Must be implemented by subclasses.

        Args:
            pos (float): The target height
        """        
        pass
    
class MockGantryController(GantryController): 
    """
    MockGantryController has all the functionality of the real
    controller, but mocks the execution of the trajectory by
    overriding the executeTrajectory method
    """

    def __init__(self, properties_file) -> None:
        """Initialize a MockGantryController Instance

        Args:
            properties_file (string): path to a properties file
        """        
        super().__init__(properties_file)
        self.position = 0

    def __enter__(self):
        """Enter the runtime context of the gantry controller.

        Returns:
            MockGantryController: The instance of the MockGantryController
        """          
        return super().__enter__()
    
    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context and clean up resources

        Args:
            exc_type (Type[BaseException] or None): The type of the exception if one was raised, else None.
            exc_value (BaseException or None): The exception instance if one was raised, else None.
            traceback (TracebackType or None): The traceback object if an exception was raised, else None.
        """
        return super().__exit__(exc_type, exc_value, traceback)
    
    @override
    def connectToCrane(self):
        """Connect to the mock crane. This is a no-op

        Returns:
            int: returns zero
        """        
        return 0
    
    @override
    def executeTrajectory(self, traj):
        """Execute a trajectory on the crane

        The mock crane does not really execute the trajectory,
        but just returns the ideal trajectory as if it was executed.
        The function sleeps until the real end time of the trajectory has passed.

        Args:
            traj (tuple): The trajectory as generated by generateTrajectory.

        Returns:
            tuple: the mock measurement with noise.
        """        
        curr_time = datetime.min
        real_time = [curr_time + timedelta(seconds=ts) for ts in traj[0]]
        # sleep for the duration of the trajectory to "execute" it
        sleep(max(0, traj[0][-1]))
        # add a bit of measurement noise to the trajectory
        noise = np.random.normal(loc=0, scale=0.005, size = (5, len(traj[0])))
        return (traj[0], traj[1] + noise[0,:], traj[2] + noise[1,:], traj[3] + noise[2,:], traj[4] + noise[3,:], traj[5] + noise[4,:])
        return (real_time, traj[1], traj[2], traj[4], traj[5])
    
    @override
    def simpleMove(self, target):
        """Mock a simple lateral movement

        Args:
            target (float): The target position

        Returns:
            float: Returns the target as is.
        """        
        return target

    @override
    def hoist(self, pos):
        """Mock a hoist movement

        Args:
            pos (float): The target height

        Returns:
            float: Returns the target as is.
        """        
        return pos

class PhysicalGantryController(GantryController):
    """The PhysicalGantryController class is a subclass of the GantryController
    It is the class to use when a real gantry crane is connected to the system.
    """    

    def __init__(self, properties_file) -> None:
        """Initialize a PhysicalGantryController instance.

        Args:
            properties_file (string): Path to a properties file
        """        
        super().__init__(properties_file)
        self.crane = self.connectToCrane(properties_file)
        self.position = self.crane.gantryStepper.getPositionMm()/1000

    def __enter__(self):
        """Enter the runtime context of the gantry controller.

        Returns:
            PhysicalGantryController: The instance of the PhysicalGantryController
        """
        return super().__enter__()
    
    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context and clean up resources

        Args:
            exc_type (Type[BaseException] or None): The type of the exception if one was raised, else None.
            exc_value (BaseException or None): The exception instance if one was raised, else None.
            traceback (TracebackType or None): The traceback object if an exception was raised, else None.
        """
        return super().__exit__(exc_type, exc_value, traceback)

    @override
    def connectToCrane(self, config: dict):
        """Connect to the physical crane.

        Args:
            config (dict): The configuration dictionary

        Returns:
            Crane: a Crane instance
        """
        crane = Crane(config)
        return crane

    @override
    def executeTrajectory(self, traj):
        """Execute a trajectory on the crane.

        traj is a tuple returned by generate trajectory.
        has the following shape:
        ts      : sample times of solution  [s]
        xs      : positions of solution     [m]
        dxs     : velocity of solution      [m/s]
        ddxs    : acceleration of solution  [m/s^2]
        thetas  : angular position of solution  [rad]
        dthetas : angular velocity of solution  [rad/s]
        ddthetas: angular acceleration of solution  [rad/s^2]
        us      : input force acting on cart [N]

        ret is a tuple with the following shape:
        tuple(ts, x, v, theta, omega)
        x : position
        v : velocity
        theta : angular position
        omega : angular velocity

        Args:
            traj (tuple): The trajectory as generated by generateTrajectory.

        Returns:
            tuple: the measured trajectory
        """        
        # convert trajectory to waypoints executable by the crane class
        waypoints = [Waypoint(t, x*1000, v*1000, a*1000) for t, x, v, a in \
                     zip(traj[0], traj[1], traj[2], traj[3])]

        # set waypoints in crane.
        self.crane.waypoints = waypoints

        # execute the waypoints (starting condition check?)
        ret = self.crane.executeWaypointsPosition()

        """
        ret is a tuple (t, x, v, theta, omega)
        ---
        t: sample time (datetime object)
        x: position at times t, in m
        v: velocity at time t, in m/s
        theta: angular position at times t, in rad
        omega: angular velocity at times t, in rad/s^2
        """
        return ret
    
    @override
    def hoist(self, pos):
        """Hoist to target position (in meters)

        Args:
            pos (float): Position in meters

        Returns:
            float: the exact final position
        """        
        # inverts direction.
        print(f"pos in counts: {self.crane.hoistStepper.mm_to_counts * pos * 1000}")
        tgt = int(458752 - self.crane.hoistStepper.mm_to_counts * pos * 1000)
        self.crane.hoistStepper.setPosition(tgt)
        while (round(self.crane.hoistStepper.getPosition(), -2) != round(tgt, -2)):
            print(f"position not yet reached: {round(self.crane.hoistStepper.getPosition(), -2)}, {tgt}")
            sleep(1)
        return (458752 - self.crane.hoistStepper.getPosition())/self.crane.hoistStepper.mm_to_counts/1000
    
    @override
    def simpleMove(self, target):
        """Perform a simple lateral move without trajectory generation.

        Args:
            target (float): The position to move to in meters

        Returns:
            float: The actual end position
        """
        self.crane.gantryStepper.setPositionMode()
        self.crane.gantryStepper.setAccelLimit(2147483647)
        self.crane.gantryStepper.setVelocityLimit(2000)
        self.crane.gantryStepper.setPosition(target * 1000*self.crane.gantryStepper.mm_to_counts)
        # wait for move to complete.
        while (round(self.crane.gantryStepper.getPosition(), -2) != round(target * 1000*self.crane.gantryStepper.mm_to_counts, -2)):
            sleep(0.1)
        
        return self.crane.gantryStepper.getPosition()/self.crane.gantryStepper.mm_to_counts/1000

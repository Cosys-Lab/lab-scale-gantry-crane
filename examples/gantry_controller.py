from abc import abstractmethod
import pickle
from threading import Event
from typing_extensions import override
import yaml
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

    def __init__(self, properties_file) -> None:
        """
        Parameters
        ----------
        properties_file : String
            path to the properties file of the gantrycrane
        """

        # load properties file
        with open(properties_file, 'r') as f:
            props = yaml.safe_load(f)
            # machine identification in database
            self.id = props["machine id"]
            self.name = props["machine name"]
            # connection to database
            self.dbaddr = "host="+props["database address"]\
                                    + " dbname=" + props["database name"]\
                                    + " user=" + props["database user"]\
                                    + " password=" + props["database password"]
            self.connect_to_db = props["connect to db"]
            if self.connect_to_db:
                self.dbconn = psycopg.connect(self.dbaddr)
            else:
                self.dbconn = None
            self.simulatortopic = props["simulator topic"]
            self.validatortopic = props["validator topic"]

        self.position = 0
        if self.dbconn:
            with self.dbconn.cursor() as cur:
                cur.execute("SELECT MAX(run_id) FROM run WHERE machine_id = 1;")
                try:
                    self.run = cur.fetchall()[0][0] + 1
                except Exception:
                    # if an exception occurs, there simply aren't any runs yet.
                    # so add run number 0.
                    self.run = 0
        self.repls = props["replications"]

        logging.info("Initialized " + str(self))

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.dbconn.close()
        except Exception:
            pass
    
    @abstractmethod
    def connectToCrane(self):
        """
        TODO: add code to connect to the crane here.

        returns current position
        """
        return 0
    
    def generateTrajectory(self, start, stop, genmethod = "ocp"):
        # Publish the request to generate a trajectory
        # TODO: add code to generate trajectory
        return self.received_trajectory

    def moveWithLog(self, target, generator = 'ocp'):
        """
        Move to target position with log in the database

        Parameters:
        -----------
        target : float [m]
            target position
        generator : strign
            'ocp', 'lqr'
        """
        logging.info("Generating trajectory to " + str(target))
        traj = self.generateTrajectory(self.position, target, generator)
        sleep(1.5) # sleep needed for initialization of the Arduino
        logging.info("Trajectory generated, storing in database")
        self.storeTrajectory(traj)
        logging.info("Trajectory stored, notifying simulator")
        self.notifySimulator()
        logging.info("Simulator notified, executing trajectory")
        measurement = self.executeTrajectory(traj)
        logging.info("Trajectory executed, updating position and storing measurement")
        self.position = measurement[1][-1]
        # align measurement to trajectory for storing
        measurement = self._align_measurement_to_trajectory(traj, measurement)
        self.storeMeasurement(measurement)
        logging.info("Measurement stored in database, notifying validator")
        self.notifyValidator()
        logging.info("Validator notified, finished move")
        self.run += 1
        return traj, measurement

    def storeTrajectory(self, traj):
        """
        traj is assumed to be tuple as returned by generateTrajectory
        format: (ts, xs, dxs, ddxs, thetas, dthetas, ddthetas)
        ts      : sample times of solution  [s]
        xs      : positions of solution     [m]
        dxs     : velocity of solution      [m/s]
        ddxs    : acceleration of solution  [m/s^2]
        thetas  : angular position of solution  [rad]
        dthetas : angular velocity of solution  [rad/s]
        ddthetas: angular acceleration of solution  [rad/s^2]
        us      : input force acting on cart [N]
        """
        # TODO: add the storing code again
        return   

    @abstractmethod
    def executeTrajectory(self, traj):
        pass

    def storeMeasurement(self, measurement):
        """
        Note: name of functions is chose to match the names of the
        tables in the database.

        measurement is assumed to be a tuple as returned by
        executeTrajectory
        format: (ts, x, v, a, theta, omega)
        ts : timestamps [datetime format]
        x : position [m]
        v : velocity [m/s]
        a : acceleration [m/s2]
        theta : angular position [rad]
        omega : angular velocity [rad/s]
        """
        # TODO: Add the storing code again
        return 

    def moveWithoutLog(self, target, generator='ocp'):
        """
        Move to target position without log in the database. This type
        of move therefore does not count as a run, it also does not
        signal the simulator and validator, since no run was performed

        Parameters:
        -----------
        target : float [m]
            target position
        """
        # generate a trajectory to executs
        # trajectory is a tuple of shape: (ts, xs, dxs, ddxs, thetas, dthetas, ddthetas, us)
        traj = self.generateTrajectory(self.position, target, generator)
        logging.info(traj)
        # execute the trajectory
        # measurement is a tuple of shape (t, x, v, a, theta, omega)   
        measurement = self.executeTrajectory(traj)
        self.position = measurement[1][-1]
        # align measurement to trajectory for storing
        measurement = self._align_measurement_to_trajectory(traj, measurement)
        return traj, measurement
    
    def moveTrajectoryWithoutLog(self, traj):
        """
        Move to target position without log in the database. This type
        of move therefore does not count as a run, it also does not
        signal the simulator and validator, since no run was performed

        Parameters:
        -----------
        target : float [m]
            target position
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
        # Interpolate the second trace onto the time points of the first trace
        interpolated_trace2 = np.interp(time1, time2, trace2)

        # Cross-correlate the two traces
        cross_corr = correlate(trace1, interpolated_trace2, mode='full')

        # Find the index of the maximum correlation
        shift_index = np.argmax(cross_corr)

        # Calculate the time shift in samples
        time_shift = time1[shift_index] - time1[-1]

        return time_shift
    
    def _align_time_based_signals(time1, trace1, time2, trace2):
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
        pass

    @abstractmethod
    def hoist(self, pos):
        pass
    
class MockGantryController(GantryController):
    """
    MockGantryController has all the functionality of the real
    controller, but mocks the execution of the trajectory by
    overriding the executeTrajectory method
    """

    def __init__(self, properties_file) -> None:
        super().__init__(properties_file)
        self.position = 0

    def __enter__(self):
        return super().__enter__()
    
    def __exit__(self, exc_type, exc_value, traceback):
        return super().__exit__(exc_type, exc_value, traceback)
    
    @override
    def connectToCrane(self):
        return 0
    
    @override
    def executeTrajectory(self, traj):
        """
        Executes trajectory on the crane

        traj is the trajectory as generated by generateTrajectory

        this mock version just returns the ideal trajectory as if it
        was executed perfectly. The ideal timestamps are replaced
        with real system timestamps, and the function sleeps
        until the real end time of the trajectory has passed.

        Returns
        -------
        tuple(ts, x, v, theta, omega)
        x : position
        v : velocity
        theta : angular position
        omega : angular velocity
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
        return target

    @override
    def hoist(self, pos):
        return pos

class PhysicalGantryController(GantryController):

    def __init__(self, properties_file) -> None:
        super().__init__(properties_file)
        self.crane = self.connectToCrane(properties_file)

    def __enter__(self):
        return super().__enter__()
    
    def __exit__(self, exc_type, exc_value, traceback):
        return super().__exit__(exc_type, exc_value, traceback)

    @override
    def connectToCrane(self, properties_file):
        with open(properties_file, 'r+') as f:
            props = yaml.safe_load(f)
            # machine identification in database
            gantryPort = props["gantryPort"]
            hoistPort = props["hoistPort"]
            # angleUARTPort = props["angleUARTPort"]
            angleUARTPort = None
            # gantryUARTPort = props["gantryUARTPort"]
            gantryUARTPort = None
            calibrated = props["calibrated"]
            I_max = props["cart acceleration limit"] * 0.167 + 0.833
            crane = Crane(gantryPort, hoistPort, angleUARTPort, gantryUARTPort, calibrated=bool(calibrated), I_max = I_max)
            return crane
    
    @override
    def executeTrajectory(self, traj):
        """
        executes trajectory on the crane

        this shouls spawn 2 processes, one for executing the trajectory,
        one for logging the trace.

        traj is the trajectory as generated by generateTrajectory

        Parameters
        ----------
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

        Returns
        -------
        tuple(ts, x, v, theta, omega)
        x : position
        v : velocity
        theta : angular position
        omega : angular velocity

        why not use these symbols everywhere?
        """

        # convert trajectory to waypoints executable by the crane class
        waypoints = [Waypoint(t, x*1000, v*1000, a*1000) for t, x, v, a in \
                     zip(traj[0], traj[1], traj[2], traj[3])]

        # set waypoints in crane.
        self.crane.waypoints = waypoints

        # execute the waypoints (starting condition check?)
        ret = self.crane.executeWaypointsPositionV3()

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
        """
        Hoists to target position (in meters)

        returns the exact final position
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
        """
        command to do a simple move. This move is a slow move
        without trajectory generation. Can be used e.g. for 
        """
        self.crane.gantryStepper.setPositionMode()
        self.crane.gantryStepper.setAccelLimit(2147483647)
        self.crane.gantryStepper.setVelocityLimit(2000)
        self.crane.gantryStepper.setPosition(target * 1000*self.crane.gantryStepper.mm_to_counts)
        # wait for move to complete.
        while (round(self.crane.gantryStepper.getPosition(), -2) != round(target * 1000*self.crane.gantryStepper.mm_to_counts, -2)):
            sleep(0.1)
        
        return self.crane.gantryStepper.getPosition()/self.crane.gantryStepper.mm_to_counts/1000

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

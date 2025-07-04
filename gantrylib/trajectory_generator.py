from abc import ABC, abstractmethod
from rockit import *
from casadi import *
import numpy as np
from scipy.constants import g
import scipy.linalg as la
from scipy.integrate import solve_ivp
import paho.mqtt.client as mqtt
import pickle
import json
import logging
import threading
import uuid

class AbstractTrajectoryGenerator(ABC):
    """Abstract interface for trajectory generators."""

    @abstractmethod
    def generateTrajectory(self, start, stop):
        pass

class TrajectoryGenerator(AbstractTrajectoryGenerator):
    """A class to generate an optimal trajectory that moves the crane laterally from one position to another one.
    """

    def __init__(self, config: dict) -> None:
        """ Initialize a TrajectoryGenerator instance.

        Args:
            config (dict): A dictionary containing problem details.
        """
        self.mp = config["pendulum_mass"]
        self.dp = config["pendulum_damping"]
        self.r = config["rope_length"]
        # self.a_cart_lim = props["cart acceleration limit"]
        self.a_cart_lim = 2.5
        self.v_cart_lim = config["cart_velocity_limit"]
        # eval this since pi/2 is a string in the yaml
        self.theta_lim = config["rope_angle_limit"]

    def  generateTrajectory(self, start, stop, method='rockit'):
        if method == 'rockit':
            return self._generateTrajectoryRockit(start, stop)
        elif method == 'lqr':
            return self._generateTrajectoryLQR(start, stop)
        else:
            raise ValueError(f"Unknown method: {method}. Use 'rockit' or 'lqr'.")

    def _generateTrajectoryRockit(self, start, stop):
        """Generates an optimal, monotone trajectory from start to stop,
        adhering to the limits imposed by the configurationfile used
        to create the TrajectoryGenerator

        Args:
            start (float): start position of the trajectory
            stop (float): stop position of the trajectory

        Returns:
            tuple: tuple (ts, xs, dxs, ddxs, thetas, dthetas, ddthetas) where
                ts      : sample times of solution  [s]
                xs      : positions of solution     [m]
                dxs     : velocity of solution      [m/s]
                ddxs    : acceleration of solution  [m/s^2]
                thetas  : angular position of solution  [rad]
                dthetas : angular velocity of solution  [rad/s]
                ddthetas: angular acceleration of solution  [rad/s^2]
        """
        # -------------------------------
        # Problem parameters
        # -------------------------------
        mc = 1          # mass of cart [kg]
        rd = 0
        
        r = self.r
        a_cart_lim = self.a_cart_lim
        v_cart_lim = self.v_cart_lim
        theta_lim = self.theta_lim

        nx = 4 # system is composed of 4 states
        nu = 1 # the system has 1 input

        # original settings
        # Tf    = 4           # control horizon [s]
        # Nhor  = 60          # number of control intervals

        # new settings in an attempt to reduce errors
        Tf    = 5         # control horizon [s]
        Nhor  = 100        # number of control intervals

        # settings to try and get corrected erroneous trajectories
        # worked! number of samples per control horizon stays the same though :)
        # Tf    = 6         # control horizon [s]
        # Nhor  = 120        # number of control intervals

        #Initial and final state
        current_X = vertcat(start, 0, 0, 0)     # initial state
        final_X = vertcat(stop, 0, 0, 0)     # desired terminal state

        # -------------------------------
        # Set OCP
        # -------------------------------
        ocp = Ocp(T=FreeTime(Tf))

        # supposedly, you can set T to freetime, and add an objective add_obj(ocp.T) to solve a problem in minimum time.
        # and example can be found in "motion_planner_MPC.py".

        # States
        x       = ocp.state()   # cart position, [m]
        theta   = ocp.state()   # pendulum angle, [rad]
        xd      = ocp.state()   # cart velocity, [m/s]
        thetad  = ocp.state()   # angular velocity of pendulum, [rad/s]

        # Controls
        u = ocp.control(1, order=0)     # controls cart

        # Define parameter?
        X_0 = ocp.parameter(nx)

        # Specify ODE
        ocp.set_der(x, xd)
        ocp.set_der(theta, thetad)
        ocp.set_der(xd, u/mc)
        ocp.set_der(thetad, -1*g*mc*sin(theta)/r 
                            - 2*mc*thetad*rd/r 
                            - u*cos(theta)/(mc*r))

        # Lagrange objective? => what does this mean?
        # Just intpreting it: integral of all controls (squared) should
        #  be minimized, but why the name Lagrange objective?
        ocp.add_objective(0.01*ocp.integral(u**2)) # minimize control input
        ocp.add_objective(ocp.T) # minimize time of the trajectory

        # todo constraint below.
        X = vertcat(x, theta, xd, thetad)
        # See MPC example https://gitlab.kuleuven.be/meco-software/rockit/-/blob/master/examples/motion_planning_MPC.py

        # Initial constraints
        # At t0, states should be initial states X_0
        ocp.subject_to(ocp.at_t0(X)==X_0)
        # At t_final, states should be final state       
        ocp.subject_to(ocp.at_tf(X)==final_X)   

        # Path constraints

        # max cart acceleration m/s^2
        ocp.subject_to(-a_cart_lim <= (ocp.der(xd) <= a_cart_lim)) 
        # max x feedrate m/s
        ocp.subject_to(-v_cart_lim <=(xd <= v_cart_lim))
        # max theta angle
        ocp.subject_to(-theta_lim <=(theta <= theta_lim)) 
        # monotone velocity and position path
        if stop > start:
            ocp.subject_to(xd >= 0)
        else:
            ocp.subject_to(xd <= 0)

        # Pick a solution method
        ocp.solver('ipopt')

        # Make it concrete for this ocp
        ocp.method(MultipleShooting(N=Nhor,M=1,intg='rk'))
        """
        N is the number of control intervals solved with 
        MultipleShooting.
        M is the number of integration steps in each control interval.
        
        Why the need for M? It could be that the constraints are only
        met at the edge of the control intervals, with M > 1 you
        introduce substeps at which the constraints are also tested.
        See: https://youtu.be/dS4U_k6B904?t=580 at the bit about 
        nonsensical constraints

        'rk' means runge kutta method.
        """


        # -------------------------------
        # Solve the OCP wrt a parameter value (for the first time)
        # -------------------------------
        # Set initial value for parameters
        ocp.set_value(X_0, current_X)
        ocp.set_initial(theta, 0)
        ocp.set_initial(x, 0.2)
        ocp.set_initial(xd, 0)
        ocp.set_initial(thetad, 0)
        # Solve
        try:
            sol = ocp.solve()

            ts, us = sol.sample(u, grid="integrator")
            ts, xs = sol.sample(x, grid="integrator")
            ts, dxs = sol.sample(xd, grid="integrator")
            ts, thetas = sol.sample(theta, grid="integrator")
            ts, dthetas = sol.sample(thetad, grid="integrator")
            ts, ddxs = sol.sample(ocp.der(xd), grid="integrator")
            ts, ddthetas = sol.sample(ocp.der(thetad),\
                                      grid="integrator")

            return (ts, xs, dxs, ddxs, thetas, dthetas, ddthetas, us)
        
        except Exception as e:
            ocp.show_infeasibilities(1e-7)
            pass
            print(e)
            # raise e
            print(ocp.debug)
            return None    
        
    def _generateTrajectoryLQR(self, start, stop):
        """Generates an optimal trajectory using a Linear Quadratic Regulator

        Args:
            start (float): Start position
            stop (float): Stop position

        Returns:
            tuple: tuple (ts, xs, dxs, ddxs, thetas, dthetas, ddthetas) where
                ts      : sample times of solution  [s]
                xs      : positions of solution     [m]
                dxs     : velocity of solution      [m/s]
                ddxs    : acceleration of solution  [m/s^2]
                thetas  : angular position of solution  [rad]
                dthetas : angular velocity of solution  [rad/s]
                ddthetas: angular acceleration of solution  [rad/s^2]
        """
        v_max = 2*self.v_cart_lim # simple initialization
        i = 0
        while v_max > self.v_cart_lim and i < 2000:
            q_v=1*(i+1)
            # Constants
            g = 9.81

            # Initial Conditions
            x0 = [start-stop, 0, 0, 0]

            # System Dynamics
            A = np.array([[0, 1, 0, 0],
                        [0, 0, 0, 0],
                        [0, 0, 0, 1],
                        [0, 0, -g/self.r, 0]])

            B = np.array([[0],
                        [1],
                        [0],
                        [-1/self.r]])

            C = np.array([[1, 1, 1, 1]])
            D = np.array([[0]])

            # Control Law
            Q = np.array([[1, 0, 0, 0],
                        [0, q_v, 0, 0],
                        [0, 0, 1, 0],
                        [0, 0, 0, 1]])
            R = np.array([[0.5]])
            # Solve the continuous time LQR controller for a linear system
            X = la.solve_continuous_are(A, B, Q, R)
            K = np.dot(np.linalg.inv(R), np.dot(B.T, X))

            # Closed loop system dynamics
            A_cl = A - np.dot(B, K)

            # Define the state-space system as a function
            def state_space(t, x):
                return A_cl @ x

            # Time vector
            t = np.arange(0, 10, 0.05)

            # Solve the initial value problem for the closed-loop system
            sol = solve_ivp(state_space, [t[0], t[-1]], x0, t_eval=t)

            dxdt = A_cl @ sol.y

            # compute new i and v_max in case we need to loop again
            i = i+1
            v_max = np.max(sol.y[1, :])
        
        if i < 2000:
            # found a good solution, return it.
            return (sol.t, sol.y[0, :] + (stop-start), sol.y[1, :], dxdt[1,:], sol.y[2, :], sol.y[3, :], dxdt[3,:], dxdt[1,:])
        else:
            return None

class MockTrajectoryGenerator(AbstractTrajectoryGenerator):
    """Mock implementation for testing."""

    def __init__(self, *args, **kwargs):
        pass

    def generateTrajectory(self, start, stop, method=None):
        # Return dummy data
        ts = np.linspace(0, 1, 10)
        xs = np.linspace(start, stop, 10)
        dxs = np.gradient(xs, ts)
        ddxs = np.gradient(dxs, ts)
        thetas = np.zeros_like(ts)
        dthetas = np.zeros_like(ts)
        ddthetas = np.zeros_like(ts)
        us = np.zeros_like(ts)
        return (ts, xs, dxs, ddxs, thetas, dthetas, ddthetas, us)
    
class MQTTCientTrajectoryGenerator(AbstractTrajectoryGenerator):
    """
    MQTT client that requests trajectories from a remote TrajectoryMQTTServer.
    """

    def __init__(self, config: dict, timeout=10):
        self.broker = config.get("mqtt_broker", "localhost")
        self.port = config.get("mqtt_port", 1883)
        self.request_topic = config.get("mqtt_request_topic", "trajectory/request")
        self.timeout = timeout
        self._client = mqtt.Client()
        self._client.on_message = self._on_message
        self._client.connect(self.broker, self.port, 60)
        self._responses = {}
        self._lock = threading.Lock()
        self._client.loop_start()

    def _on_message(self, client, userdata, msg):
        try:
            request_id = msg.topic.split("/")[-1]
            with self._lock:
                self._responses[request_id] = msg.payload
            logging.info(f"Received response for request_id={request_id}")
        except Exception as e:
            logging.info(f"Error in on_message: {e}")

    def generateTrajectory(self, start, stop, method='rockit'):
        request_id = str(uuid.uuid4())
        reply_topic = f"trajectory/response/{request_id}"

        # Subscribe to the unique reply topic
        self._client.subscribe(reply_topic)

        payload = {
            "start": start,
            "stop": stop,
            "method": method,
            "request_id": request_id
        }
        self._client.publish(self.request_topic, json.dumps(payload))
        logging.info(f"Published trajectory request with request_id={request_id}")

        # Wait for the response
        response = None
        for _ in range(int(self.timeout * 10)):
            with self._lock:
                if request_id in self._responses:
                    response = self._responses.pop(request_id)
                    break
            threading.Event().wait(0.1)

        # Unsubscribe from the reply topic
        self._client.unsubscribe(reply_topic)

        if response is None:
            raise TimeoutError(f"No response received for request_id={request_id} within {self.timeout} seconds.")

        # Unpickle the result
        result = pickle.loads(response)
        return result

    def __del__(self):
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass
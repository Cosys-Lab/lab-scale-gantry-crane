import yaml
from rockit import *
from casadi import *
import numpy as np
from numpy import pi
from scipy.constants import g
import matplotlib.pyplot as plt
import csv
from scipy.io import savemat
import scipy.linalg as la
from scipy.integrate import solve_ivp

class TrajectoryGenerator:

    def __init__(self, properties_file) -> None:
        """
        Parameters
        ----------
        properties_file : String
            path to the properties file of the crane whose trajectories
            will be calculated
        """
        with open(properties_file, 'r') as f:
            props = yaml.safe_load(f)
            self.mp = props["pendulum mass"]
            self.dp = props["pendulum damping"]
            self.r = props["rope length"]
            # self.a_cart_lim = props["cart acceleration limit"]
            self.a_cart_lim = 2.5
            self.v_cart_lim = props["cart velocity limit"]
            # eval this since pi/2 is a string in the yaml
            self.theta_lim = eval(props["rope angle limit"])

    def generateTrajectory(self, start, stop):
        """
        Generates an optimal, monotone trajectory from start to stop,
        adhering to the limits imposed by the configurationfile used
        to create the TrajectoryGenerator

        Parameters
        ----------
        start : float
            start position of the trajectory
        stop : float
            stop position of the trajectory

        Returns
        -------
        tuple (ts, xs, dxs, ddxs, thetas, dthetas, ddthetas)
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
        
    def generateTrajectoryLQR(self, start, stop):
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

        return sol, dxdt

    def saveToCSV(self, filename, data, columnnames):
        """
        Saves output to CSV file, for example, see __main__
        """
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(columnnames)
            for row in zip(*data):
                writer.writerow(row)

    def saveDataToMat(self, filename, data, keys):
        """
        Saves output to mat file
        """
        dic = dict(zip(keys, data))
        savemat(filename, dic)

    def saveParamToMat(self, filename):
        """
        Saves parameters of this current trajectory generator to a mat
        file that is to be stored together with the generated trajectory
        I might need that in matlab
        """
        dic = {"mp": self.mp, "dp": self.dp, "r": self.r}
        savemat(filename, dic)

if __name__ == "__main__":
    tg = TrajectoryGenerator("crane-properties.yaml")
    (t, x, dx, ddx, theta, omega, alpha, u) = tg.generateTrajectory(0, 0.65)
    print("dt:")
    print(t[1:-1] - t[0:-2])
    fig, (ax1, ax2) = plt.subplots(2)
    ax1.plot(t, x)
    ax1.plot(t, dx)
    ax2.plot(t, ddx)
    #tg.saveToCSV('testfile.csv', (t, x, dx, ddx, theta, omega, alpha, u), ("t", "x", "v", "a", "theta", "omega", "alpha", "u"))
    #tg.saveParamToMat('params.mat')
    #tg.saveDataToMat('data.mat', (t, x, dx, ddx, theta, omega, alpha, u), ("t", "x", "v", "a", "theta", "omega", "alpha", "u"))
    plt.show()
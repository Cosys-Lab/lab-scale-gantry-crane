from scipy.integrate import solve_ivp
import numpy as np
from scipy.constants import g
from scipy.interpolate import interp1d

class GantrySimulation():

    def __init__(self, r=0.15, mp=0.084, v_max = 0.400, a_max = 2.5) -> None:
        """
        Parameters:
        -----------
        parameters of the simulation.
        """
        self.r = r
        self.mp = mp
        self.mc = 1
        self.v_max = v_max
        self.a_max = a_max

    def sign(self, num):
        return -1 if num < 0 else 1

    def odefun(self, t, y, f, v_tgt):
        """
        Parameters
        ----------
        t : current time step
        y : state vector
            y[0] = x
            y[1] = v (that's dx/dt)
            y[2] = theta
            y[3] = omega (that's dtheta/dt)
        tu : time of u vector
        u : input vector
        """
        u = f(t)
        v_tgt_smpl = v_tgt(t+0.01)

        # local assignment to save writing self. every time
        mc = self.mc
        r = self.r
        rd = 0 # is in the formula for when you want to have adjustable rope

        # state vector:
        x = y[0]
        v = y[1] # dx/dt
        theta = y[2]
        omega = y[3] # dtheta/dt

        rounding = 5

        a = u/mc
        # if round(v, rounding) < np.round(v_tgt_smpl, rounding):
        #     # when v has not hit v_tgt yet, keep accelerating at the maximum rate
        #     a = u/mc
        #     #a = self.a_max
        # elif round(v, rounding) > np.round(v_tgt_smpl, rounding):
        #     # for deceleration follow u without limits
        #     a = u/mc # dv/dt
        # else:
        # # if we are within range of v_target and don't need to decelerate, just set 0
        #     a = 0
        #     # a = u/mc # dv/dt
        #     # a = self.a_max * self.sign(a) if min(abs(a), self.a_max) == self.a_max else a
             
        alpha = -1*g*mc*np.sin(theta)/r - 2*mc*omega*rd/r\
                - a*np.cos(theta)/(mc*r)
        
        dy = np.zeros(np.size(y))
        dy[0] = self.v_max * self.sign(v) if min(abs(v), self.v_max) == self.v_max else v
        dy[1] = a
        dy[2] = omega
        dy[3] = alpha

        return dy

    
    def simulate(self, y_init, t, tu, u, v):
        """
        simulate the gantrycrane

        """
        f = interp1d(tu, u, kind='zero')
        v_tgt = interp1d(tu, v, kind='zero', bounds_error=False, fill_value="extrapolate")
        sol = solve_ivp(lambda t, y: self.odefun(t, y, f, v_tgt),\
                                  [t[0], t[-1]], y_init, t_eval=t)

        sol.y[1] = np.clip(sol.y[1], -self.v_max, self.v_max)      
        return sol

if __name__ == "__main__":
    import psycopg
    import matplotlib.pyplot as plt

    with psycopg.connect("host=127.0.0.1 dbname=gantrycrane user=postgres") as conn:
        with conn.cursor() as cur:
            quantities = ["position", "velocity", "acceleration", "angular position", "angular velocity", "angular acceleration", "force"]
            query = "select ts, value, quantity from trajectory "\
                        + "where machine_id = " + str(1)  \
                        + " and run_id = " + str(24) \
                        + " and quantity in (" + str(quantities)[1:-1] + ")" \
                        + " order by quantity, ts;"
            cur.execute(query)
            ret = cur.fetchall()
            # reuse column names
            ts = np.array([row[0] for row in ret])
            value = np.array([row[1] for row in ret])
            quantity = np.array([row[2] for row in ret])
            trajectory = {}
            for qty in quantities:
                idx = quantity == qty
                trajectory[qty] = {}
                # convert from datetime to just seconds (might have to do this earlier, but numpy seems to be able to cope with datetime)
                trajectory[qty]["ts"] = np.array([td.total_seconds() for td in (ts[idx] - ts[idx][0])])
                trajectory[qty]["value"] = value[idx]

        # simulation
        gs = GantrySimulation()
        
        sol = gs.simulate([0, 0, 0, 0], trajectory["force"]["ts"], trajectory["force"]["ts"], trajectory["force"]["value"])

        fig, (ax1, ax2, ax3) = plt.subplots(3)
        ax1.plot(sol.t, sol.y[0])
        ax1.plot(trajectory["position"]["ts"], trajectory["position"]["value"])
        ax2.plot(sol.t, sol.y[1])
        ax2.plot(trajectory["velocity"]["ts"], trajectory["velocity"]["value"])

        plt.show()

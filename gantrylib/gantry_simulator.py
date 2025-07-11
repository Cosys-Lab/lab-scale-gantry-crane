from gantrylib.gantry_simulation import GantrySimulation
import concurrent.futures as cf
import psycopg
from datetime import timedelta, datetime
import numpy as np
import os
import logging
import sys
# from psycopgpool import pool

# due to using multiprocessing there is a lot of stuff that needs to be
# defined at the module level instead of in a class.

mqttclient = None
validatortopic = None
# need this here otherwise signal_done function can't reach it 
# (it has but one allowed parameter)

def simulate(sim, traj_id, machine_id, repl_id, t_now, dbaddr, x0, theta0, omega0):
    """
    function that simulates one replication
    Parameters
    ----------
    sim : GantrySimulator
        Instance of GantrySimulator that has been initialized with
        randomly sampled values
    traj_id : id of the trajectory (TODO: correct name is run_id...)
    machine_id : id of the machine
    repl_id : id of this replication
    dbconn : connection to the database
    t_now : zero time for writing the time vector to the database
    """
    # need to call this in every thread for logging to work, since these are separate processes that's needed.
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    # start by opening connection to database
    simid = str(traj_id) + "." + str(repl_id)
    logging.info("Simulation " + simid + "started")
    with psycopg.connect(dbaddr) as dbconn:
        logging.info(simid + " got db connection " + str(dbconn))
        with dbconn.cursor() as cur:
            # fetch the trajectory input force data
            cur.execute(f"""SELECT ts, value FROM trajectory WHERE machine_id = {machine_id} 
                        AND run_id = {traj_id} AND quantity = 'force';""")
            rows = cur.fetchall()
            # bit of processing to go from datetime to just plain seconds
            u = [row[1] for row in rows]
            t_now = rows[0][0] # override t_now with this timestamp
            ts = [(row[0] - rows[0][0]).total_seconds() for row in rows]
            # fetch the trajectory velocity data (for limiting)
            cur.execute(f"""SELECT ts, value FROM trajectory WHERE machine_id = {machine_id} 
                        AND run_id = {traj_id} AND quantity = 'velocity';""")
            rows = cur.fetchall()
            # bit of processing to go from datetime to just plain seconds
            v = [row[1] for row in rows]
            # fetch intial values for x, v, theta and omega
            try:
                cur.execute(f"""select quantity, value from trajectory 
                            where machine_id = {machine_id} 
                            AND run_id = {traj_id} 
                            and quantity  in ('position', 'velocity', 'angular position', 'angular velocity')
                            and ts = (select min(ts) from trajectory t2 
                            where machine_id = {machine_id} 
                            AND run_id = {traj_id} 
                            and quantity  in ('position', 'velocity', 'angular position', 'angular velocity'));""")
            except Exception as e:
                logging.error(simid + " Error fetching initial conditions: " + str(e))
            rows = cur.fetchall()
            
            # shape will be sth like:
            # angular position	0
            # angular velocity	0.0
            # position	0.0
            # velocity	-0
            # this needs to be ordered into y_init (x0, v0, theta0, omega0)
            # easiest is to cast to dict I guess
            initvals = dict(rows)
            y_init = [initvals["position"] + x0,\
                        initvals["velocity"],\
                        initvals["angular position"] + theta0,\
                        initvals["angular velocity"] + omega0]
            # I guess we now have everything to setup the simulation
            try:
                sol = sim.simulate(y_init, ts, ts, u, v)
            except Exception as e:
                logging.error(simid + "Error in simulation: " + str(e))
            # simulation results can now be written to the database
            t_db = [t_now + timedelta(seconds=ts) for ts in sol.t]
            quantities = ['position', 'velocity', 'angular position', \
                        'angular velocity']
            # insert the data into simulationdatapoint
            with cur.copy("""COPY simulationdatapoint (ts, machine_id, run_id, 
                        replication_nr, quantity, value) FROM stdin""") as copy:
                # write all quantities
                for idx, qty in enumerate(quantities):
                    for (t, data) in zip(t_db, sol.y[idx]):
                        copy.write_row((t, machine_id, traj_id, repl_id, qty, data))
            # commit to database
            dbconn.commit()
        logging.info(simid + " Wrote results to database")
    logging.info(f"{simid}: Exited dbconn context.")

class GantrySimulator():

    def __init__(self, config: dict) -> None:
        """
        Parameters
        ----------
        properties_file : String
            path to the properties file of the gantrycrane
        """
        # load properties file
        self.id = config["machine_id"]
        self.name = config["machine_name"]
        self.rope_length_SD = config["rope_length_SD"]
        self.position_SD = config["position_SD"]
        self.theta_SD = config["theta_SD"]
        self.omega_SD = config["omega_SD"]
        self.mp = config["pendulum_mass"]
        # random generator for sampling of parameters
        self.rng = np.random.default_rng()
        # executor for parallel jobs
        self.executor = cf.ProcessPoolExecutor(max_workers=max(os.cpu_count()-4, 4))
        
        # db setup
        self.dbaddr = "host="+config["db_address"]\
                    + " dbname=" + config["db_name"]\
                    + " user=" + config["db_user"] + " password=" + config["db_password"]
        self.dbconn = psycopg.connect(self.dbaddr)

        logging.info("Created simulator " + str(self))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.dbconn.close()
        except Exception:
            pass
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def run_simulations(self, run_id, repls, rope_length):
        """
        run simulations
        run_id is the ID of the simulation run
        repls is the number of replications to run
        rope_length (legacy, this is not logged, it really should have been...)
        """
        # create new simulation in database
        with self.dbconn.cursor() as cur:
            cur.execute("""INSERT INTO simulation (run_id, 
                        machine_id, num_replications)
                        VALUES (%s, %s, %s)""", (run_id, self.id, repls))
        self.dbconn.commit()
        logging.info(f"Setting up {repls} replications")
        repls_ids = [i for i in range(repls)]
        # sample values of r, x0, theta0 and omega0 for the simulation objects
        rs = self.rng.normal(rope_length, self.rope_length_SD, repls) # 
        x0s = self.rng.normal(0, self.position_SD, repls)
        theta0s = self.rng.logistic(0, self.theta_SD, repls)
        omega0s = self.rng.logistic(0, self.omega_SD, repls)
        sims = [GantrySimulation(r=r, mp=self.mp) for r in rs]
        t_now = datetime.min
        logging.info("Submitting jobs to processing pool")
        futs = [self.executor.submit(simulate, sim, run_id, self.id, repl_id, t_now, self.dbaddr, x0, theta0, omega0) for (sim, repl_id, x0, theta0, omega0) in zip(sims, repls_ids, x0s, theta0s, omega0s)]
        logging.info(str([str(fut.__hash__()) for fut in futs]))
        out = cf.wait(futs, 5)
        while out.not_done:
            logging.info(f"Done: {out.done}")
            logging.info(f"Not done: {out.not_done}")
            for fut in out.not_done:
                logging.info(f"Future {fut.__hash__()} state: {'done' if fut.done() else 'running'}")
            out = cf.wait(futs, 5)
        logging.info("All simulations completed")

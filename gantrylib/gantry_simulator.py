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

ppe_futures = {}
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
            cur.execute("SELECT ts, value FROM trajectory WHERE machine_id = %s \
                        AND run_id = %s AND quantity = 'force';",(machine_id, traj_id))
            rows = cur.fetchall()
            logging.info(simid + " fetched trajectory input data")
            # bit of processing to go from datetime to just plain seconds
            u = [row[1] for row in rows]
            ts = [(row[0] - rows[0][0]).total_seconds() for row in rows]
            # fetch intial values for x, v, theta and omega
            logging.info(simid + " fetching IC")
            try:
                cur.execute("select quantity, value \
                        from trajectory \
                        where machine_id = " + str(machine_id) + \
                        "AND run_id = " + str(traj_id) + \
                        "and quantity  in ('position', 'velocity', 'angular position', 'angular velocity') \
                        and ts = (\
                        select min(ts) from trajectory t2 \
                        where machine_id = " + str(machine_id) + \
                        "AND run_id = " + str(traj_id) + \
                        "and quantity  in ('position', 'velocity', 'angular position', 'angular velocity'));")
            except Exception as e:
                logging.error(simid + " Error fetching initial conditions: " + str(e))
            logging.info(simid + "Executed query for IC")
            rows = cur.fetchall()
            
            # shape will be sth like:
            # angular position	0
            # angular velocity	0.0
            # position	0.0
            # velocity	-0
            # this needs to be ordered into y_init (x0, v0, theta0, omega0)
            # easiest is to cast to dict I guess
            initvals = dict(rows)
            logging.info(simid + " IC: " + str(initvals))
            y_init = [initvals["position"] + x0,\
                        initvals["velocity"],\
                        initvals["angular position"] + theta0,\
                        initvals["angular velocity"] + omega0]
            logging.info(simid + " fetched initial conditions: " + str(y_init))
            # I guess we now have everything to setup the simulation
            sol = sim.simulate(y_init, ts, ts, u)
            logging.info(simid + " Simulation results: " + str(sol))
            logging.info(simid + " Simulated: " + str(sol))
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

def signal_done(fut):
    logging.info(str(fut.__hash__()))
    traj_id = ppe_futures.pop(fut.__hash__()) # use pop since it returns the value
    # check if id still exists in the ppe_futures.values
    if traj_id not in set(ppe_futures.values()):
        # if not, all those processes have returned and we can signal validator that simulations are done.
        # ret = mqttclient.publish(validatortopic, payload=str({"traj_id": traj_id, "src": "Simulator"}), qos = 2, retain=False)
        # ret.wait_for_publish()
        logging.info("all simulations of trajectory " + str(traj_id) + " are done")

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
        logging.info("Setting up replications")
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
        global ppe_futures
        for fut in futs:
            fut.add_done_callback(signal_done)
            ppe_futures[fut.__hash__()] = run_id
        logging.info("Simulations Done")

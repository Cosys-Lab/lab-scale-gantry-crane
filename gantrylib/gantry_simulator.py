from typing import Any
from gantrylib.gantry_simulation import GantrySimulation
import yaml
from multiprocessing.connection import Client, Listener
import concurrent.futures as cf
import psycopg
from psycopg_pool import ConnectionPool
from datetime import timedelta, datetime
import numpy as np
import os
import logging
import sys
import paho.mqtt.client as mqtt
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
            logging.info(simid + " fetched initial conditions: " + str(y_init))
            # I guess we now have everything to setup the simulation
            sol = sim.simulate(y_init, ts, ts, u)
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
        ret = mqttclient.publish(validatortopic, payload=str({"traj_id": traj_id, "src": "Simulator"}), qos = 2, retain=False)
        ret.wait_for_publish()
        logging.info("all simulations of trajectory " + str(traj_id) + " are done")

class GantrySimulator():

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
            self.simulatortopic = props["simulator topic"]
            self.validatortopic = props["validator topic"]
            global validatortopic
            validatortopic = self.validatortopic
            self.r_mean = props["r mean"]
            self.r_SD = props["r SD"]
            self.x0_SD = props["x0 SD"]
            self.theta0_SD = props["theta0 SD"]
            self.omega0_SD = props["omega0 SD"]
            self.mp = props["pendulum mass"]
            # random generator for sampling of parameters
            self.rng = np.random.default_rng()
            # executor for parallel jobs
            self.executor = cf.ProcessPoolExecutor(max_workers=max(os.cpu_count()-4, 4))
            
            # mqtt setup
            self.mqttc = mqtt.Client("Simulator")
            global mqttclient
            mqttclient = self.mqttc
            self.mqttc.on_connect = self.on_connect
            self.mqttc.message_callback_add(self.simulatortopic, self.on_simulatorTopicMessage)

            # db setup
            self.dbaddr = "host="+props["database address"]\
                        + " dbname=" + props["database name"]\
                        + " user=" + props["database user"]
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

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected with result code" + str(rc))

        # subscribe to topics
        self.mqttc.subscribe(self.simulatortopic, qos = 2)

    def on_simulatorTopicMessage(self, client, userdata, msg):
        logging.info("Received message: " + str(msg.payload))

        # what was in start can now go in this callback
        req = eval(msg.payload)
        # create new simulation in database
        # use a connection from the pool for this
        logging.info("Creating new simulation in database")
        with self.dbconn.cursor() as cur:
            cur.execute("""INSERT INTO simulation (run_id, 
                        machine_id, num_replications)
                        VALUES (%s, %s, %s)""", (req["traj_id"], \
                        self.id, req["repls"]))
        self.dbconn.commit()
        logging.info("Setting up replications")
        repls = [i for i in range(req["repls"])]
        # sample values of r, x0, theta0 and omega0 for the simulation objects
        rs = self.rng.normal(self.r_mean, self.r_SD, req["repls"])
        # these should be added as deviation from the initial condition
        x0s = self.rng.normal(0, self.x0_SD, req["repls"])
        theta0s = self.rng.logistic(0, self.theta0_SD, req["repls"])
        omega0s = self.rng.logistic(0, self.omega0_SD, req["repls"])
        # instantiate simulations
        sims = [GantrySimulation(r=r, mp=self.mp) for r in rs]
        # Use minimal datetime for 0 of the simulations
        t_now = datetime.min
        # create futures
        logging.info("Submitting jobs to processing pool")
        futs = [self.executor.submit(simulate, sim, req["traj_id"], self.id, repl_id, t_now, self.dbaddr, x0, theta0, omega0) for (sim, repl_id, x0, theta0, omega0) in zip(sims, repls, x0s, theta0s, omega0s)]
        logging.info(str([str(fut.__hash__()) for fut in futs]))
        global ppe_futures
        for fut in futs:
            fut.add_done_callback(signal_done)
            ppe_futures[fut.__hash__()] = req["traj_id"]
        logging.info("Done, waiting for new request")

    def start(self):
        logging.info("Simulator" + str(self) +  "started, will continuously listen for messages")
        self.mqttc.connect("localhost")
        self.mqttc.loop_forever()

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    with GantrySimulator("./crane-properties.yaml") as gs:
        try:
            gs.start()
        except KeyboardInterrupt:
            pass



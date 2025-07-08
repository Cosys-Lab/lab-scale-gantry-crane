import sys
import logging
import yaml
import os
import paho.mqtt.client as mqtt
import concurrent.futures as cf
import numpy as np
from datetime import datetime, timedelta
from model_validation_metrics.distance_metrics import normalized_euclidean_metric, mahalanobis_distance, rootMeanSquaredError
from model_validation_metrics.frequentist_metric import calculate_frequentist_metric_interpolated, calculate_global_frequentist_metric
from model_validation_metrics.reliability_metric import calculate_reliability_metric

import psycopg

def numToSQL(x):
    if np.isnan(x):
        return "'NaN'"
    elif np.isinf(x):
        return "'infinity'"
    else:
        return str(x)

def validate(traj_id, machine_id, metrics, quantities, dbaddr):
    # this function is going to be a bit cumbersome, since I haven't
    # been particularly consistent in how the metrics are called.
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    logging.info("Validation process started")

    with psycopg.connect(dbaddr) as dbconn:

        logging.info("got dbconn " + str(dbconn))
        # step one is retrieving for this trajectory id and machine id
        # - the trajectory log (table measurement)
        # - the simulation replications (table simulationdatapoint)
        # the first is easy, the second is a bit harder.
        # I could do filtering in python to save queries to the
        # database, but since premature optimzation is the root of all
        # evil I'll just go with database queries for now.

        with dbconn.cursor() as cur:
            # retrieve trajectory log for the needed quantities
            query = "select ts, value, quantity from measurement "\
                        + "where machine_id = " + str(machine_id)  \
                        + " and run_id = " + str(traj_id) \
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

            # same for the simulated replications
            query = "select ts, value, quantity, replication_nr  from simulationdatapoint "\
            + "where machine_id = " + str(machine_id) \
            + " and run_id = " + str(traj_id)  \
            + " and quantity in (" + str(quantities)[1:-1] + ")" \
            + " order by quantity, replication_nr, ts;"
            cur.execute(query)
            ret = cur.fetchall()
            ts = np.array([row[0] for row in ret])
            value = np.array([row[1] for row in ret])
            quantity = np.array([row[2] for row in ret])
            replication_nr = np.array([row[3] for row in ret])
            repls = replication_nr[-1] + 1 # number of replications
            simulation = {}
            for qty in quantities:
                simulation[qty] = {}
                qty_idx = quantity == qty
                for repl in range(repls):
                    simulation[qty][repl] = {}
                    repl_idx = (replication_nr == repl) & qty_idx
                    simulation[qty][repl]["ts"] = ts[repl_idx]
                    # same conversion to seconds. Note: technically each replication has
                    # the same ts, but maybe in the future this might not be the case
                    simulation[qty][repl]["ts"] = np.array([td.total_seconds() for td in (ts[repl_idx] - ts[repl_idx][0])])
                    simulation[qty][repl]["value"] = value[repl_idx]
                    # final step: the majority of the metrics assume
                    # equal sampling times between experiment and measurement
                    # Assume the measured sampling times are the ones wanted,
                    # and the simulation times are interpolated to those values.
                    simulation[qty][repl]["value"] = np.interp(trajectory[qty]["ts"],\
                                                              simulation[qty][repl]["ts"],\
                                                              simulation[qty][repl]["value"])
                    simulation[qty][repl]["ts"] = trajectory[qty]["ts"]

            # other note: the metrics take all kinds of shapes of inputs
            # e.g. lists of (ts, vals), M x N arrays, mean and std etc.
            # storing in these dictionaries seemed the easiest way to
            # easily loop over all quantities and built whatever input
            # shape is needed by the metric.

        # can now go to the calculation of all the metrics
        t_min = datetime.min
        for qty in quantities:
            if "root mean squared error" in metrics:
                replications = []
                for repl in simulation[qty].values():
                    replications.append(repl["value"])
                
                d = rootMeanSquaredError(trajectory[qty]["value"], replications)

                #t_db = [t_min + timedelta(seconds=ts) for ts in trajectory[qty]["ts"]]
                t_db = [t_min]

                with dbconn.cursor() as cur:
                    with cur.copy("""COPY rootmeansquarederror (machine_id, 
                                  run_id, quantity, ts, distance) 
                                  FROM stdin""") as copy:
                        for (t, data) in zip(t_db, [d]):
                            # write all quantities
                            copy.write_row((machine_id, traj_id, qty, t, data))
            if "normalized euclidean distance" in metrics:
                # expects P: 1xN array of predicition
                #         D: 1xN array of data
                #         D_std: 1xN standard deviation of the data
                # In my case data and prediction are swapped.
                # three steps need to happen:
                # 1. calculate mean of replications
                # 2. calculate std of replications
                # 3. calculate the metric
                replications = []
                for repl in simulation[qty].values():
                    replications.append(repl["value"])

                replications = np.array(replications)
                d, d_ne = normalized_euclidean_metric(trajectory[qty]["value"],
                                                    np.mean(replications, axis=0),
                                                    np.std(replications, axis=0))
                
                t_db = [t_min + timedelta(seconds=ts) for ts in trajectory[qty]["ts"]]

                with dbconn.cursor() as cur:
                    with cur.copy("""COPY normalizedeuclideandistance (
                                  machine_id, run_id, quantity, ts, distance)
                                  FROM stdin""") as copy:
                        for (t, data) in zip(t_db, d):
                            # write all quantities
                            copy.write_row((machine_id, traj_id, qty, t, data))
                    query = "insert into totalnormalizedeuclideandistance (machine_id, run_id, quantity, distance) values"\
                                + "("+str(machine_id) +"," + str(traj_id)+ ","\
                                + "'"+qty+"'" + "," + str(d_ne)+");"
                    cur.execute(query)
            if "mahalanobis distance" in metrics:
                """
                Expects: D : M x N numpy array
                    Experimentally obtained Data, as a numpy array of length N,
                    with M replications per datapoint.
    
                P : 1 x N numpy array
                    Model prediction as a 1 x N numpy array.

                Therefore I need to group the replications together
                """
                replications = []
                for repl in simulation[qty].values():
                    replications.append(repl["value"])

                replications = np.array(replications)

                d_mahalanobis = mahalanobis_distance(trajectory[qty]["value"], replications)
                # get cursor to write to database
                with dbconn.cursor() as cur:
                    query = "insert into mahalanobisdistance (machine_id, run_id, quantity, distance) values"\
                    + "(" + str(machine_id) + "," + str(traj_id) + ","\
                    + "'" + qty + "'" + "," + numToSQL(d_mahalanobis) +");"
                    cur.execute(query)
            if "frequentist metric" in metrics:
                """
                X : List of 2xN numpy array
                    The replicated experimental measurements. Assumed to be a list of at least two 2xN numpy arrays, in which
                    the first row represents x and the second f(x). Each numpy array in the list may have a different length N,
                    and the values may be spaced at random, but x_0 and x_end of the final interpolation will be the intersection
                    of the various arrays in X and the single array in y, therefore if all datapoints must be used, ensure x_0 and x_end of each x array are equal.
                
                y : 2xN numpy array
                    Model prediction as a 2xN numpy array, where the first row represents x and the second f(x).
                    y may have a different length N, than the arrays in X, and the values may be spaced at random,
                    but x_0 and x_end of the final interpolation will be the intersection of the arrays in X and the array in y,
                    therefore if all datapoints must be used, ensure x_0 and x_end of each array are equal.
                """
                replications = []
                for repl in simulation[qty].values():
                    replications.append([repl["ts"], repl["value"]])

                replications = np.array(replications)

                x_final, mu_x, E_x, conf_interval_x, f_y_interpolated = calculate_frequentist_metric_interpolated(replications, np.array([trajectory[qty]["ts"], trajectory[qty]["value"]]))
                
                t_db = [t_min + timedelta(seconds=ts) for ts in x_final]

                mu_x = mu_x + conf_interval_x
                E_x = E_x + conf_interval_x
                with dbconn.cursor() as cur:
                    with cur.copy("""COPY frequentistmetric (machine_id, 
                                  run_id, quantity, ts, mu_lower, mu_upper,
                                   error_lower, error_upper) FROM stdin""") as copy:
                        for (t, mu_x_e, E_x_e) in zip(t_db, mu_x.T, E_x.T):
                            copy.write_row((machine_id, traj_id, qty, t, mu_x_e[0], mu_x_e[1], E_x_e[0], E_x_e[1]))

            if "global frequentist metric" in metrics:
                replications = []
                for repl in simulation[qty].values():
                    replications.append([repl["ts"], repl["value"]])

                replications = np.array(replications)

                avg_rel_err, avg_rel_conf_ind, max_rel_err = calculate_global_frequentist_metric(replications, np.array([trajectory[qty]["ts"], trajectory[qty]["value"]]))

                with dbconn.cursor() as cur:
                    query = "insert into globalfrequentistmetric (machine_id, run_id, quantity, average_relative_error, average_relative_confidence_indicator, maximum_relative_error) values"\
                            + "(" + str(machine_id) + "," + str(traj_id) + ","\
                            + "'" + qty + "'" + ","\
                            + numToSQL(avg_rel_err)+ ","\
                            + numToSQL(avg_rel_conf_ind) + ","\
                            + numToSQL(max_rel_err) + ");"
                    cur.execute(query)
                pass
            if "reliability metric" in metrics:
                pass
                
            # rollback for now, since there will be bugs    
            dbconn.commit()
    logging.info("Validation process finished")


class Validator:

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
                        + " user=" + props["database user"]
            # self.dbconn = psycopg.connect(self.dbaddr)
            self.validatortopic = props["validator topic"]
            # executor for parallel jobs
            self.executor = cf.ProcessPoolExecutor(max_workers=max(os.cpu_count()-4, 4))
            
            # dict to store validation requests as described in the on_validatorTopicMessage
            self.validationrequest = {}

            # mqtt setup
            self.mqttc = mqtt.Client("Validator")
            self.mqttc.on_connect = self.on_connect
            self.mqttc.message_callback_add(self.validatortopic, self.on_validatorTopicMessage)


        logging.info("Created validator " + str(self))

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.mqttc.disconnect() # not sure if needed

    def on_connect(self, client, userdata, flags, rc):
        logging.info("Connected with result code" + str(rc))
        # subscribe to topics
        self.mqttc.subscribe(self.validatortopic, qos = 2)       

    def on_validatorTopicMessage(self, client, userdata, msg):
        """
        The message will have the following structure:
        {"traj_id": id, "src": "Controller"/"Simulator"}

        For each received trajectory, the validator must keep track of
        having received a message from controller and simulator.
        Once a message for both has been received, a validation process
        may be spawned to calculate the validation metrics of that
        trajectory.

        a dictionary with a tuple (controller_bool, simulator_bool) 
        seems the simplest way.
        """
        logging.info("Received message: " + str(msg.payload))

        req = eval(msg.payload)
        if req["traj_id"] not in self.validationrequest.keys():
            # no request has been made yet, so create it.
            self.validationrequest[req["traj_id"]] = [1,0] if req["src"] == "Controller" else [0, 1]
            logging.info("Validation request stored" + str(self.validationrequest))
        else:
            # the request already exists.
            if req["src"] == "Controller":
                self.validationrequest[req["traj_id"]][0] = 1
            elif req["src"] == "Simulator":
                self.validationrequest[req["traj_id"]][1] = 1
            
            logging.info("Validation request updated" + str(self.validationrequest))

            if 0 not in self.validationrequest[req["traj_id"]]:
                logging.info("Spawning validation process for" + str(req["traj_id"]))
                # no zeros means controller and simulator made a request
                # remove the entry from the validationrequest
                self.validationrequest.pop(req["traj_id"])
                # spawn a validation process
                metrics_to_calc = ['normalized euclidean distance',
                                     'mahalanobis distance',
                                     'frequentist metric',
                                     'global frequentist metric',
                                        'reliability metric', 'root mean squared error']
                qties_to_calc = ['position', 'velocity', 'angular position',
                                  'angular velocity']
                self.executor.submit(validate, req["traj_id"], self.id, 
                                     metrics_to_calc, qties_to_calc, 
                                     self.dbaddr)
    
    def start(self):
        logging.info("Validator" + str(self) + "started, will continuously listen for messages")
        self.mqttc.connect("localhost")
        self.mqttc.loop_forever()

if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    with Validator("./crane-properties.yaml") as v:
        v.start()

    #---------------------------------------------------
    # Code below is the correcting code used to correct the calculated
    # frequentist metric
    #---------------------------------------------------
        # metrics_to_calc = ['normalized euclidean distance']
        # qties_to_calc = ['position', 'velocity', 'angular position',
        #                           'angular velocity']
        
        # for i in range(100, 160):
        #     validate(i, 1, metrics_to_calc, qties_to_calc, v.dbaddr)
    
    
    # validate(60, 1, datetime.datetime.now(), ['normalized euclidean distance',
    #                                  'mahalanobis distance',
    #                                  'frequentist metric',
    #                                  'global frequentist metric',
    #                                     'reliability metric', 'root mean squared error'], 
    #                                         ['position', 'velocity', 
    #                                          'angular position', 
    #                                             'angular velocity'])
    

    

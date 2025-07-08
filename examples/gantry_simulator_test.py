

import yaml

from gantrylib.gantry_simulator import GantrySimulator

if __name__ == "__main__":
    with open("./crane-properties.yaml", "r") as file:
        crane_properties = yaml.safe_load(file)
        with GantrySimulator(crane_properties) as simulator:
            # run a simulation with 10 replications
            simulator.run_simulations(run_id=12, repls=1, rope_length=0.5)
            print("Simulations completed successfully.")
            # You can add more code here to interact with the simulator or check results

        
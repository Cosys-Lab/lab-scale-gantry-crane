from gantrylib.gantry_validator import Validator
import yaml


if __name__ == "__main__":
    with open("./crane-properties.yaml", "r") as file:
        crane_properties = yaml.safe_load(file)
        with Validator(crane_properties) as validator:
            validator.run_validation(28)
            print("Simulations completed successfully.")
            # You can add more code here to interact with the simulator or check results

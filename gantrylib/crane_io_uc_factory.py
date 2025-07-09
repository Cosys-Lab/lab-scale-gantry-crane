from gantrylib.crane_io_uc import CraneIOUC, MockCraneIOUC, SerialCraneIOUC

class CraneIOUCFactory:

    @classmethod
    def create_crane_io_uc(self, config: dict) -> CraneIOUC:
        """
        Factory function to create a CraneIOUC instance.

        Args:
            config (dict): Configuration dictionary. Should contain a key 'crane_IOUC_type' with value 'mock' or 'serial'.
                        For 'serial', must also contain 'crane_IOUC_port' and 'crane_IOUC_baudrate'.

        Returns:
            CraneIOUC: An instance of MockCraneIOUC or SerialCraneIOUC.
        """
        io_type = config.get("crane_IOUC_type", None).lower()
        if io_type == "mock" or io_type is None:
            return MockCraneIOUC()
        elif io_type == "serial":
            return SerialCraneIOUC(config)
        else:
            raise ValueError(f"Unknown CraneIOUC type: {io_type}")
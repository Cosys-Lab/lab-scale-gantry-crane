from enum import Enum
from abc import ABC, abstractmethod
from gantrylib.database_io import PostgresDatabase, DatabaseInterface

class DatabaseType(Enum):
    """Enum defining supported database types"""
    POSTGRES = "postgres"
    MOCK = "mock"
    NONE = "none"

class GantryDatabaseFactory:
    """Factory class for creating database connections"""

    @staticmethod
    def create_database(db_type: DatabaseType, config: dict) -> DatabaseInterface:
        """Create a database instance based on type and configuration

        Args:
            db_type (DatabaseType): Type of database to create
            config (dict): Database configuration parameters

        Returns:
            DatabaseInterface: Instance of database interface implementation

        Raises:
            ValueError: If db_type is not supported
        """
        if db_type == DatabaseType.POSTGRES:
            return PostgresDatabase(
                host=config["database address"],
                dbname=config["database name"],
                user=config["database user"],
                password=config["database password"]
            )
        elif db_type == DatabaseType.MOCK:
            # For testing purposes
            return MockDatabase()
        elif db_type == DatabaseType.NONE:
            return NullDatabase()
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

class MockDatabase(DatabaseInterface):
    """Mock database implementation for testing"""
    def connect(self):
        pass

    def disconnect(self):
        pass

    def get_next_run_id(self, machine_id: int) -> int:
        return 0

    def store_run(self, run_id: int, machine_id: int, start_time):
        pass

    def store_trajectory(self, machine_id: int, run_id: int, trajectory: tuple):
        pass

    def store_measurement(self, machine_id: int, run_id: int, measurement: tuple):
        pass

class NullDatabase(DatabaseInterface):
    """Null object pattern implementation for when no database is needed"""
    def connect(self):
        pass

    def disconnect(self):
        pass

    def get_next_run_id(self, machine_id: int) -> int:
        return 0

    def store_run(self, run_id: int, machine_id: int, start_time):
        pass

    def store_trajectory(self, machine_id: int, run_id: int, trajectory: tuple):
        pass

    def store_measurement(self, machine_id: int, run_id: int, measurement: tuple):
        pass
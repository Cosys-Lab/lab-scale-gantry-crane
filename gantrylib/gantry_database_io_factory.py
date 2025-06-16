from enum import Enum
from gantrylib.gantry_database_io import PostgresDatabase, DatabaseInterface, MockDatabase, NullDatabase

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

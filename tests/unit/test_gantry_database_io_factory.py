import unittest
from unittest.mock import patch, MagicMock
from gantrylib.gantry_database_io_factory import GantryDatabaseFactory, DatabaseType
from gantrylib.gantry_database_io import PostgresDatabase, MockDatabase, NullDatabase

class TestGantryDatabaseFactory(unittest.TestCase):
    def setUp(self):
        self.config = {
            "database address": "localhost",
            "database name": "test_db",
            "database user": "test_user", 
            "database password": "test_pass"
        }

    def test_create_postgres_database(self):
        db = GantryDatabaseFactory.create_database(DatabaseType.POSTGRES, self.config)
        self.assertIsInstance(db, PostgresDatabase)

    def test_create_mock_database(self):
        db = GantryDatabaseFactory.create_database(DatabaseType.MOCK, self.config)
        self.assertIsInstance(db, MockDatabase)

    def test_create_null_database(self):
        db = GantryDatabaseFactory.create_database(DatabaseType.NONE, self.config)
        self.assertIsInstance(db, NullDatabase)

    def test_invalid_database_type(self):
        with self.assertRaises(ValueError):
            GantryDatabaseFactory.create_database("invalid_type", self.config)

    def test_postgres_database_correct_params(self):
        with patch('gantrylib.gantry_database_io_factory.PostgresDatabase') as mock_postgres:
            GantryDatabaseFactory.create_database(DatabaseType.POSTGRES, self.config)
            mock_postgres.assert_called_once_with(
                host="localhost",
                dbname="test_db",
                user="test_user",
                password="test_pass"
            )

if __name__ == '__main__':
    unittest.main()
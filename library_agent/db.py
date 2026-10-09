"""One place for the database connection.

Every other file asks this module for a driver. If we move to another
graph database later (for example PostgreSQL + Apache AGE), this is
the file that changes.
"""

import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def get_driver():
    """Open a connection to Neo4j using the settings in .env."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.environ["NEO4J_PASSWORD"]
    return GraphDatabase.driver(uri, auth=(user, password))

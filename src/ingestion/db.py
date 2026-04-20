import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_NAME = os.getenv("DB_NAME", "markets_project")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", os.getenv("USER", ""))


def get_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
    )

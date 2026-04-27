import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_NAME     = os.getenv("DB_NAME", "markets_project")
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_USER     = os.getenv("DB_USER", os.getenv("USER", ""))
DB_PASSWORD = os.getenv("DB_PASSWORD")  # required in prod; None on local
DATABASE_URL = os.getenv("DATABASE_URL")  # if Northflank/Heroku-style URL is provided, use it directly


def get_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    kwargs = dict(dbname=DB_NAME, host=DB_HOST, port=DB_PORT, user=DB_USER)
    if DB_PASSWORD:
        kwargs["password"] = DB_PASSWORD
    return psycopg2.connect(**kwargs)

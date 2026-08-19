"""
Base de données SQLite — une table par source de données.

Table `books`   <- données nettoyées de Books to Scrape (Selenium)
Table `cars`     <- données nettoyées de Gaaraas (Selenium)
"""
import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SCHEMA_BOOKS = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    V1_titre TEXT,
    V2_prix REAL,
    V3_disponibilite TEXT,
    V4_nb_produits_page INTEGER,
    V5_note INTEGER,
    V6_nb_reviews INTEGER,
    V7_description TEXT,
    V8_categorie TEXT,
    V9_tax REAL,
    page INTEGER,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

SCHEMA_CARS = """
CREATE TABLE IF NOT EXISTS cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    V1_marque TEXT,
    V2_modele TEXT,
    V3_annee INTEGER,
    V4_prix REAL,
    V5_kilometrage REAL,
    V6_boite_vitesse TEXT,
    V7_region TEXT,
    energie TEXT,
    url_annonce TEXT,
    page INTEGER,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_connection()
    conn.execute(SCHEMA_BOOKS)
    conn.execute(SCHEMA_CARS)
    conn.commit()
    conn.close()


def save_dataframe(df: pd.DataFrame, table: str, if_exists: str = "append"):
    """Enregistre un DataFrame nettoyé dans la table SQL correspondante ('books' ou 'cars')."""
    if df.empty:
        return
    conn = get_connection()
    df.to_sql(table, conn, if_exists=if_exists, index=False)
    conn.close()


def load_table(table: str) -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def clear_table(table: str):
    conn = get_connection()
    conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()

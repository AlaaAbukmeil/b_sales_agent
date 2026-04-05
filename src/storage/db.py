"""
SQLite database for storing call results and iteration metrics.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = "data/calls.db"


def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            iteration INTEGER,
            script_version INTEGER,
            persona_id TEXT,
            persona_name TEXT,
            transcript TEXT,
            evaluation TEXT,
            outcome TEXT,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS iterations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            iteration_number INTEGER,
            script_version INTEGER,
            total_calls INTEGER,
            success_count INTEGER,
            partial_count INTEGER,
            failed_count INTEGER,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def store_call(iteration: int, script_version: int, persona: dict,
               transcript: list, evaluation: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO calls
           (iteration, script_version, persona_id, persona_name,
            transcript, evaluation, outcome, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            iteration,
            script_version,
            persona.get("id", "unknown"),
            persona.get("name", "Unknown"),
            json.dumps(transcript, ensure_ascii=False),
            json.dumps(evaluation, ensure_ascii=False),
            evaluation.get("outcome", "unknown"),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def store_iteration(iteration_number: int, script_version: int,
                    total: int, success: int, partial: int, failed: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO iterations
           (iteration_number, script_version, total_calls,
            success_count, partial_count, failed_count, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (iteration_number, script_version, total, success, partial, failed,
         datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_iteration_stats() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM iterations ORDER BY iteration_number")
    rows = c.fetchall()
    conn.close()
    return rows
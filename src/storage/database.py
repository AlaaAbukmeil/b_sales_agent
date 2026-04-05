"""
SQLite database for storing call transcripts, scores, and iterations.
"""

import os
import json
import sqlite3
from typing import List, Dict, Optional


class Database:
    """Simple SQLite storage for simulation data."""

    def __init__(self, db_path: str = "data/calls.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                call_number INTEGER NOT NULL,
                persona TEXT NOT NULL,
                persona_prompt TEXT,
                transcript TEXT NOT NULL,
                scores TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS iterations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                avg_scores TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                version INTEGER NOT NULL,
                script TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def save_call(
        self,
        run_id: str,
        iteration: int,
        call_number: int,
        persona: str,
        persona_prompt: str,
        transcript: List[Dict],
        scores: Dict,
    ):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO calls (run_id, iteration, call_number, persona, persona_prompt, transcript, scores)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                iteration,
                call_number,
                persona,
                persona_prompt,
                json.dumps(transcript),
                json.dumps(scores),
            ),
        )
        conn.commit()
        conn.close()

    def save_iteration(self, run_id: str, iteration: int, avg_scores: Dict):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO iterations (run_id, iteration, avg_scores)
            VALUES (?, ?, ?)
            """,
            (run_id, iteration, json.dumps(avg_scores)),
        )
        conn.commit()
        conn.close()

    def save_script(self, run_id: str, version: int, script: str):
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO scripts (run_id, version, script)
            VALUES (?, ?, ?)
            """,
            (run_id, version, script),
        )
        conn.commit()
        conn.close()

    def get_calls(self, run_id: Optional[str] = None) -> List[Dict]:
        conn = self._connect()
        cursor = conn.cursor()

        if run_id:
            cursor.execute(
                "SELECT * FROM calls WHERE run_id = ? ORDER BY iteration, call_number",
                (run_id,),
            )
        else:
            cursor.execute("SELECT * FROM calls ORDER BY created_at DESC")

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            d = dict(zip(columns, row))
            d["transcript"] = json.loads(d["transcript"])
            d["scores"] = json.loads(d["scores"])
            results.append(d)

        return results

    def get_report(self) -> List[Dict]:
        """Get a structured report grouped by iteration for the most recent run."""
        conn = self._connect()
        cursor = conn.cursor()

        # Get most recent run_id
        cursor.execute("SELECT run_id FROM iterations ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            conn.close()
            return []

        run_id = row[0]

        # Get iterations
        cursor.execute(
            "SELECT iteration, avg_scores FROM iterations WHERE run_id = ? ORDER BY iteration",
            (run_id,),
        )
        iterations = cursor.fetchall()

        report = []
        for it_num, avg_scores_json in iterations:
            # Get calls for this iteration
            cursor.execute(
                """
                SELECT call_number, persona, scores
                FROM calls
                WHERE run_id = ? AND iteration = ?
                ORDER BY call_number
                """,
                (run_id, it_num),
            )
            calls = [
                {
                    "call_number": r[0],
                    "persona": r[1],
                    "scores": json.loads(r[2]),
                }
                for r in cursor.fetchall()
            ]

            report.append({
                "iteration": it_num,
                "avg_scores": json.loads(avg_scores_json),
                "calls": calls,
            })

        conn.close()
        return report
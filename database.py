import sqlite3
from pathlib import Path
from typing import Dict, List, Optional


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    class_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, class_name)
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    mode TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    target INTEGER NOT NULL DEFAULT 100,
    correct_bits INTEGER NOT NULL DEFAULT 0,
    wrong_attempts INTEGER NOT NULL DEFAULT 0,
    timeout_attempts INTEGER NOT NULL DEFAULT 0,
    questions_completed INTEGER NOT NULL DEFAULT 0,
    perfect_questions INTEGER NOT NULL DEFAULT 0,
    precision REAL NOT NULL DEFAULT 0,
    report_path TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    decimal_value INTEGER NOT NULL,
    binary_value TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    wrong_attempts INTEGER NOT NULL DEFAULT 0,
    correct_bits INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    expected_digit TEXT NOT NULL,
    entered_digit TEXT NOT NULL,
    weight INTEGER NOT NULL,
    is_correct INTEGER NOT NULL,
    response_time REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
);
"""


class GameDatabase:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def get_or_create_student(self, name: str, class_name: str) -> int:
        name = " ".join(name.strip().split())
        class_name = " ".join(class_name.strip().split())
        row = self.conn.execute(
            "SELECT id FROM students WHERE lower(name)=lower(?) AND lower(class_name)=lower(?)",
            (name, class_name),
        ).fetchone()
        if row:
            return int(row["id"])
        cur = self.conn.execute(
            "INSERT INTO students(name, class_name) VALUES (?, ?)", (name, class_name)
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def create_session(self, student_id: int, mode: str, target: int = 100) -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions(student_id, mode, target) VALUES (?, ?, ?)",
            (student_id, mode, target),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def create_question(self, session_id: int, decimal_value: int, binary_value: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO questions(session_id, decimal_value, binary_value) VALUES (?, ?, ?)",
            (session_id, decimal_value, binary_value),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def record_attempt(
        self,
        question_id: int,
        position: int,
        expected: str,
        entered: str,
        weight: int,
        is_correct: bool,
        response_time: float,
    ) -> None:
        self.conn.execute(
            """INSERT INTO attempts
               (question_id, position, expected_digit, entered_digit, weight, is_correct, response_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (question_id, position, expected, entered, weight, int(is_correct), response_time),
        )
        self.conn.commit()

    def finish_question(self, question_id: int, wrong_attempts: int, correct_bits: int) -> None:
        self.conn.execute(
            """UPDATE questions
               SET finished_at=CURRENT_TIMESTAMP, wrong_attempts=?, correct_bits=?, completed=1
               WHERE id=?""",
            (wrong_attempts, correct_bits, question_id),
        )
        self.conn.commit()

    def finish_session(self, session_id: int, stats: Dict, report_path: Optional[str] = None) -> None:
        self.conn.execute(
            """UPDATE sessions SET
               finished_at=CURRENT_TIMESTAMP, score=?, correct_bits=?, wrong_attempts=?, timeout_attempts=?,
               questions_completed=?, perfect_questions=?, precision=?, report_path=?
               WHERE id=?""",
            (
                stats["score"], stats["correct_bits"], stats["wrong_attempts"], stats["timeout_attempts"],
                stats["questions_completed"], stats["perfect_questions"], stats["precision"],
                report_path, session_id,
            ),
        )
        self.conn.commit()

    def set_report_path(self, session_id: int, report_path: str) -> None:
        self.conn.execute("UPDATE sessions SET report_path=? WHERE id=?", (report_path, session_id))
        self.conn.commit()

    def session_stats(self, session_id: int) -> Dict:
        session = self.conn.execute(
            """SELECT s.*, st.name, st.class_name
               FROM sessions s JOIN students st ON st.id=s.student_id WHERE s.id=?""",
            (session_id,),
        ).fetchone()
        if not session:
            raise KeyError(session_id)

        errors_by_weight = {
            int(r["weight"]): int(r["n"])
            for r in self.conn.execute(
                """SELECT a.weight, COUNT(*) n FROM attempts a
                   JOIN questions q ON q.id=a.question_id
                   WHERE q.session_id=? AND a.is_correct=0
                   GROUP BY a.weight ORDER BY a.weight DESC""",
                (session_id,),
            )
        }

        question_rows = self.conn.execute(
            """SELECT q.*, COALESCE(SUM(CASE WHEN a.is_correct=0 THEN 1 ELSE 0 END),0) AS error_count
               FROM questions q LEFT JOIN attempts a ON a.question_id=q.id
               WHERE q.session_id=? GROUP BY q.id ORDER BY q.id""",
            (session_id,),
        ).fetchall()

        questions: List[Dict] = []
        max_wrong_streak = 0
        recovered_first_try_after_error = 0
        error_positions = 0
        response_times_correct = []
        response_times_wrong = []

        for q in question_rows:
            attempts = self.conn.execute(
                "SELECT * FROM attempts WHERE question_id=? ORDER BY id", (q["id"],)
            ).fetchall()
            by_pos: Dict[int, List[sqlite3.Row]] = {}
            for a in attempts:
                by_pos.setdefault(int(a["position"]), []).append(a)
                (response_times_correct if a["is_correct"] else response_times_wrong).append(float(a["response_time"]))

            position_details = []
            for pos, arr in sorted(by_pos.items()):
                wrong_before = 0
                for a in arr:
                    if a["is_correct"]:
                        break
                    wrong_before += 1
                if wrong_before:
                    error_positions += 1
                    max_wrong_streak = max(max_wrong_streak, wrong_before)
                    if wrong_before == 1 and arr[-1]["is_correct"]:
                        recovered_first_try_after_error += 1
                position_details.append({
                    "position": pos,
                    "attempts": len(arr),
                    "wrong_before_correct": wrong_before,
                    "weight": int(arr[0]["weight"]),
                })

            errors = [
                {
                    "position": int(a["position"]),
                    "entered": a["entered_digit"],
                    "expected": a["expected_digit"],
                    "weight": int(a["weight"]),
                    "response_time": float(a["response_time"]),
                }
                for a in attempts if not a["is_correct"]
            ]
            questions.append({
                "id": int(q["id"]),
                "decimal": int(q["decimal_value"]),
                "binary": q["binary_value"],
                "completed": bool(q["completed"]),
                "errors": errors,
                "position_details": position_details,
            })

        result = dict(session)
        result["errors_by_weight"] = errors_by_weight
        result["questions"] = questions
        result["max_wrong_streak"] = max_wrong_streak
        result["recovered_first_try_after_error"] = recovered_first_try_after_error
        result["error_positions"] = error_positions
        result["avg_correct_response_time"] = (
            sum(response_times_correct) / len(response_times_correct) if response_times_correct else 0.0
        )
        result["avg_wrong_response_time"] = (
            sum(response_times_wrong) / len(response_times_wrong) if response_times_wrong else 0.0
        )
        return result

    def recent_sessions(self, limit: int = 50) -> List[Dict]:
        rows = self.conn.execute(
            """SELECT s.id, s.started_at, s.finished_at, s.mode, s.score, s.precision,
                      s.questions_completed, st.name, st.class_name
               FROM sessions s JOIN students st ON st.id=s.student_id
               WHERE s.finished_at IS NOT NULL
               ORDER BY s.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

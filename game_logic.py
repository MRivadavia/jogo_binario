from dataclasses import dataclass, field
import random
import time
from typing import Dict, List, Optional


@dataclass
class AttemptResult:
    correct: bool
    entered: str
    expected: str
    position: int
    weight: int
    delta: int
    score: int
    question_complete: bool
    target_reached: bool
    response_time: float


@dataclass
class QuestionState:
    decimal_value: int
    binary_value: str
    position: int = 0
    wrong_attempts: int = 0
    attempts_by_position: Dict[int, int] = field(default_factory=dict)
    bit_started_at: float = field(default_factory=time.monotonic)

    @property
    def weights(self) -> List[int]:
        n = len(self.binary_value)
        return [2 ** (n - i - 1) for i in range(n)]

    @property
    def answer_so_far(self) -> str:
        return self.binary_value[: self.position]

    @property
    def display_slots(self) -> str:
        done = list(self.answer_so_far)
        pending = ["_"] * (len(self.binary_value) - self.position)
        return "  ".join(done + pending)


class BinaryGameEngine:
    """Pure game logic, independent from Kivy and Android APIs."""

    CORRECT_POINTS = 5
    WRONG_PENALTY = 3

    def __init__(self, target_score: int = 100, min_decimal: int = 2, max_decimal: int = 255):
        self.target_score = target_score
        self.min_decimal = min_decimal
        self.max_decimal = max_decimal
        self.score = 0
        self.correct_bits = 0
        self.wrong_attempts = 0
        self.timeout_attempts = 0
        self.questions_completed = 0
        self.perfect_questions = 0
        self.current: Optional[QuestionState] = None
        self.last_decimal: Optional[int] = None

    def reset(self) -> None:
        self.score = 0
        self.correct_bits = 0
        self.wrong_attempts = 0
        self.timeout_attempts = 0
        self.questions_completed = 0
        self.perfect_questions = 0
        self.current = None
        self.last_decimal = None

    def new_question(self, decimal_value: Optional[int] = None) -> QuestionState:
        if decimal_value is None:
            choices = list(range(self.min_decimal, self.max_decimal + 1))
            if self.last_decimal in choices and len(choices) > 1:
                choices.remove(self.last_decimal)
            decimal_value = random.choice(choices)
        if not self.min_decimal <= decimal_value <= self.max_decimal:
            raise ValueError("Número decimal fora do intervalo configurado.")
        self.last_decimal = decimal_value
        self.current = QuestionState(decimal_value, format(decimal_value, "b"))
        return self.current

    def submit(self, entered: str, *, now: Optional[float] = None, timeout: bool = False) -> AttemptResult:
        if self.current is None:
            raise RuntimeError("Nenhuma questão ativa.")
        if entered not in {"0", "1", "TEMPO"}:
            raise ValueError("A entrada deve ser 0, 1 ou TEMPO.")

        now = time.monotonic() if now is None else now
        q = self.current
        pos = q.position
        expected = q.binary_value[pos]
        weight = q.weights[pos]
        response_time = max(0.0, now - q.bit_started_at)
        q.attempts_by_position[pos] = q.attempts_by_position.get(pos, 0) + 1

        is_correct = (not timeout) and entered == expected
        if is_correct:
            delta = self.CORRECT_POINTS
            self.score += delta
            self.correct_bits += 1
            q.position += 1
            q.bit_started_at = now
        else:
            delta = -self.WRONG_PENALTY
            self.score = max(0, self.score + delta)
            self.wrong_attempts += 1
            q.wrong_attempts += 1
            if timeout:
                self.timeout_attempts += 1
            q.bit_started_at = now

        complete = q.position >= len(q.binary_value)
        if complete:
            self.questions_completed += 1
            if q.wrong_attempts == 0:
                self.perfect_questions += 1

        return AttemptResult(
            correct=is_correct,
            entered=entered,
            expected=expected,
            position=pos,
            weight=weight,
            delta=delta,
            score=self.score,
            question_complete=complete,
            target_reached=complete and self.score >= self.target_score,
            response_time=response_time,
        )

    @property
    def precision(self) -> float:
        total = self.correct_bits + self.wrong_attempts
        return (self.correct_bits / total * 100.0) if total else 0.0

    @property
    def progress_ratio(self) -> float:
        return min(1.0, self.score / self.target_score) if self.target_score else 1.0

import os
from pathlib import Path

os.environ.setdefault("KIVY_ORIENTATION", "Portrait")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.utils import platform

from database import GameDatabase
from game_logic import BinaryGameEngine
from reports import MODE_NAMES, pedagogical_opinion, report_text, save_report


CHALLENGE_SECONDS = 10.0


class StartScreen(Screen):
    def start_game(self):
        name = self.ids.student_name.text.strip()
        class_name = self.ids.class_name.text.strip()
        mode_label = self.ids.mode_spinner.text
        mode = {
            "Aprendizagem": "learning",
            "Treinamento": "training",
            "Desafio": "challenge",
        }.get(mode_label, "training")
        if not name:
            self.ids.start_message.text = "Informe o nome do estudante."
            return
        self.ids.start_message.text = ""
        app = App.get_running_app()
        app.sound_enabled = self.ids.sound_toggle.state == "down"
        app.vibration_enabled = self.ids.vibration_toggle.state == "down"
        app.start_session(name, class_name, mode)


class GameScreen(Screen):
    timer_value = NumericProperty(CHALLENGE_SECONDS)
    timer_visible = BooleanProperty(False)

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        if not app.engine.current:
            return
        q = app.engine.current
        self.ids.decimal_label.text = str(q.decimal_value)
        self.ids.answer_label.text = q.display_slots
        self.ids.score_label.text = f"{app.engine.score} / {app.engine.target_score}"
        self.ids.progress.max = app.engine.target_score
        self.ids.progress.value = min(app.engine.score, app.engine.target_score)
        self.ids.position_label.text = f"Dígito {q.position + 1} de {len(q.binary_value)}"
        if app.mode == "learning":
            self.ids.weights_label.text = "Pesos:  " + "   ".join(str(w) for w in q.weights)
        else:
            self.ids.weights_label.text = ""
        self.timer_visible = app.mode == "challenge"
        self.ids.mode_label.text = f"Modo: {MODE_NAMES.get(app.mode, app.mode)}"

    def press_bit(self, bit):
        App.get_running_app().submit_bit(bit)


class ReportScreen(Screen):
    current_session_id = NumericProperty(0)

    def load_session(self, session_id: int):
        app = App.get_running_app()
        stats = app.db.session_stats(session_id)
        self.current_session_id = session_id
        level, opinion = pedagogical_opinion(stats)
        q = int(stats.get("questions_completed") or 0)
        perfect = int(stats.get("perfect_questions") or 0)
        perfect_pct = (perfect / q * 100.0) if q else 0.0
        self.ids.report_title.text = f"{stats['name']} — {MODE_NAMES.get(stats['mode'], stats['mode'])}"
        self.ids.report_summary.text = (
            f"Pontuação: {stats['score']}   |   Precisão: {float(stats['precision']):.1f}%\n"
            f"Questões: {q}   |   Bits corretos: {stats['correct_bits']}   |   Erros: {stats['wrong_attempts']}\n"
            f"Questões sem erro: {perfect_pct:.1f}%   |   Classificação: {level}"
        )
        self.ids.report_body.text = report_text(stats)
        self.ids.opinion_label.text = opinion
        self.ids.report_path.text = stats.get("report_path") or "Relatório exibido a partir do banco de dados."

    def replay(self):
        app = App.get_running_app()
        stats = app.db.session_stats(self.current_session_id)
        app.start_session(stats["name"], stats["class_name"], stats["mode"])


class HistoryScreen(Screen):
    def on_pre_enter(self, *args):
        self.refresh_history()

    def refresh_history(self):
        app = App.get_running_app()
        box = self.ids.history_box
        box.clear_widgets()
        rows = app.db.recent_sessions(50)
        if not rows:
            box.add_widget(Label(text="Ainda não há partidas concluídas.", size_hint_y=None, height="56dp"))
            return
        for row in rows:
            text = (
                f"{row['name']} | Turma {row['class_name'] or '-'}\n"
                f"{row['started_at']}  •  {MODE_NAMES.get(row['mode'], row['mode'])}  •  "
                f"{row['score']} pts  •  {float(row['precision']):.1f}%"
            )
            btn = Button(text=text, size_hint_y=None, height="78dp", halign="left", valign="middle")
            btn.bind(size=lambda inst, value: setattr(inst, "text_size", (value[0] - 24, None)))
            sid = int(row["id"])
            btn.bind(on_release=lambda _btn, session_id=sid: app.open_report(session_id))
            box.add_widget(btn)


class RootManager(ScreenManager):
    pass


class BinaryApp(App):
    title = "Binário: Acerto ou Erre"
    mode = StringProperty("training")
    sound_enabled = BooleanProperty(True)
    vibration_enabled = BooleanProperty(True)

    def build(self):
        ##############
        #def build(self):
        print("ETAPA 1 - antes do KV", flush=True)
        Builder.load_file(str(Path(__file__).with_name("binario.kv")))

        print("ETAPA 2 - KV carregado", flush=True)

        root = RootManager()

        print("ETAPA 3 - RootManager criado", flush=True)

        root.add_widget(StartScreen())

        print("ETAPA 4 - StartScreen criada", flush=True)

        root.add_widget(GameScreen())

        print("ETAPA 5 - GameScreen criada", flush=True)

        root.add_widget(ReportScreen())

        print("ETAPA 6 - ReportScreen criada", flush=True)

        root.add_widget(HistoryScreen())

        print("ETAPA 7 - HistoryScreen criada", flush=True)

        self.data_dir = Path(self.user_data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        print("ETAPA 8 - diretório criado", flush=True)

        self.reports_dir = self.data_dir / "relatorios"

        self.db = GameDatabase(
        str(self.data_dir / "binario_acerto_ou_erre.sqlite3")
        )

        print("ETAPA 9 - banco criado", flush=True)

        self.engine = BinaryGameEngine(
             target_score=100,
             min_decimal=2,
             max_decimal=255
        )

        print("ETAPA 10 - engine criada", flush=True)

        self.student_id = None
        self.session_id = None
        self.question_id = None
        self.timer_event = None
        self.challenge_deadline = None

        print("ETAPA 11 - verificando sons", flush=True)

        assets = Path(__file__).with_name("assets")

        correct_path = assets / "correct.wav"
        wrong_path = assets / "wrong.wav"

        self.correct_sound = None
        self.wrong_sound = None

        if correct_path.exists():
            print("Carregando correct.wav...", flush=True)
            self.correct_sound = SoundLoader.load(str(correct_path))
        else:
            print("correct.wav não encontrado - continuando sem som.", flush=True)

        if wrong_path.exists():
            print("Carregando wrong.wav...", flush=True)
            self.wrong_sound = SoundLoader.load(str(wrong_path))
        else:
            print("wrong.wav não encontrado - continuando sem som.", flush=True)

        print("ETAPA 12 - build concluído", flush=True)

        return root

        return root

    def on_stop(self):
        if getattr(self, "timer_event", None):
            self.timer_event.cancel()
        if getattr(self, "db", None):
            self.db.close()

    def start_session(self, name: str, class_name: str, mode: str):
        self.cancel_timer()
        self.mode = mode
        self.engine.reset()
        self.student_id = self.db.get_or_create_student(name, class_name)
        self.session_id = self.db.create_session(self.student_id, mode, self.engine.target_score)
        self.new_question()
        self.root.current = "game"
        self.root.get_screen("game").ids.feedback.text = "Escolha o primeiro bit."

    def new_question(self):
        q = self.engine.new_question()
        self.question_id = self.db.create_question(self.session_id, q.decimal_value, q.binary_value)
        self.start_bit_timer()
        if self.root and self.root.has_screen("game"):
            self.root.get_screen("game").refresh()

    def start_bit_timer(self):
        self.cancel_timer()
        if self.mode != "challenge":
            return
        import time
        self.challenge_deadline = time.monotonic() + CHALLENGE_SECONDS
        self.timer_event = Clock.schedule_interval(self.update_timer, 0.1)
        game = self.root.get_screen("game")
        game.timer_value = CHALLENGE_SECONDS

    def cancel_timer(self):
        if self.timer_event is not None:
            self.timer_event.cancel()
            self.timer_event = None
        self.challenge_deadline = None

    def update_timer(self, _dt):
        if self.mode != "challenge" or not self.challenge_deadline:
            return False
        import time
        remaining = max(0.0, self.challenge_deadline - time.monotonic())
        self.root.get_screen("game").timer_value = remaining
        if remaining <= 0:
            self.submit_bit("TEMPO", timeout=True)
            return False
        return True

    def submit_bit(self, bit: str, timeout: bool = False):
        if not self.engine.current or self.question_id is None:
            return
        result = self.engine.submit(bit, timeout=timeout)
        self.db.record_attempt(
            self.question_id,
            result.position,
            result.expected,
            result.entered,
            result.weight,
            result.correct,
            result.response_time,
        )

        game = self.root.get_screen("game")
        if result.correct:
            game.ids.feedback.text = f"✓ Bit correto: +5 pontos. Peso {result.weight}."
            self.feedback(success=True)
        else:
            reason = "Tempo esgotado" if timeout else f"Bit {bit} incorreto"
            game.ids.feedback.text = f"✗ {reason}: -3 pontos. A posição continua bloqueada."
            self.feedback(success=False)

        game.refresh()

        if result.question_complete:
            q = self.engine.current
            self.db.finish_question(self.question_id, q.wrong_attempts, len(q.binary_value))
            self.cancel_timer()
            if result.target_reached:
                Clock.schedule_once(lambda _dt: self.finish_session(), 0.45)
            else:
                game.ids.feedback.text += "  Questão concluída!"
                Clock.schedule_once(lambda _dt: self.new_question(), 0.65)
        else:
            self.start_bit_timer()

    def feedback(self, success: bool):
        if self.sound_enabled:
            sound = self.correct_sound if success else self.wrong_sound
            if sound:
                sound.stop()
                sound.play()
        if self.vibration_enabled and platform == "android":
            try:
                from plyer import vibrator
                vibrator.vibrate(0.04 if success else 0.10)
            except Exception:
                pass

    def current_stats_dict(self):
        return {
            "score": self.engine.score,
            "correct_bits": self.engine.correct_bits,
            "wrong_attempts": self.engine.wrong_attempts,
            "timeout_attempts": self.engine.timeout_attempts,
            "questions_completed": self.engine.questions_completed,
            "perfect_questions": self.engine.perfect_questions,
            "precision": self.engine.precision,
        }

    def finish_session(self):
        self.cancel_timer()
        stats = self.current_stats_dict()
        self.db.finish_session(self.session_id, stats)
        detailed = self.db.session_stats(self.session_id)
        path = save_report(detailed, str(self.reports_dir))
        self.db.set_report_path(self.session_id, path)
        self.open_report(self.session_id)

    def open_report(self, session_id: int):
        screen = self.root.get_screen("report")
        screen.load_session(session_id)
        self.root.current = "report"

    def end_session_early(self):
        """Finish a partial session and still produce its pedagogical report."""
        if self.session_id is None:
            self.go_home()
            return
        self.finish_session()

    def go_home(self):
        self.cancel_timer()
        self.root.current = "start"

    def go_history(self):
        self.cancel_timer()
        self.root.current = "history"


if __name__ == "__main__":
    BinaryApp().run()

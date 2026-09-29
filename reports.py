from pathlib import Path
import re
from typing import Dict, Tuple


MODE_NAMES = {
    "learning": "Aprendizagem",
    "training": "Treinamento",
    "challenge": "Desafio",
}


def _safe_filename(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9áàâãéêíóôõúç_-]+", "_", text, flags=re.IGNORECASE)
    return text.strip("_") or "aluno"


def pedagogical_opinion(stats: Dict) -> Tuple[str, str]:
    precision = float(stats.get("precision") or 0)
    questions = int(stats.get("questions_completed") or 0)
    perfect = int(stats.get("perfect_questions") or 0)
    perfect_rate = (perfect / questions * 100.0) if questions else 0.0
    wrong = int(stats.get("wrong_attempts") or 0)
    timeouts = int(stats.get("timeout_attempts") or 0)
    errors_by_weight = stats.get("errors_by_weight", {})
    max_streak = int(stats.get("max_wrong_streak") or 0)
    error_positions = int(stats.get("error_positions") or 0)
    recovered = int(stats.get("recovered_first_try_after_error") or 0)

    if precision >= 95 and perfect_rate >= 75:
        level = "Apropriação muito consistente"
        opening = (
            "O estudante demonstrou apropriação muito consistente da conversão de números decimais "
            "para a representação binária. As decisões por posição foram majoritariamente corretas e "
            "as questões foram resolvidas com pouca necessidade de revisão das escolhas." 
        )
    elif precision >= 85:
        level = "Boa apropriação"
        opening = (
            "O estudante demonstrou boa apropriação da conversão decimal-binária. Os acertos predominam "
            "e os erros observados tendem a ser pontuais, indicando uma estratégia de resolução já estabelecida." 
        )
    elif precision >= 70:
        level = "Apropriação parcial"
        opening = (
            "O estudante demonstrou apropriação parcial do conteúdo. Há compreensão funcional da conversão, "
            "mas ainda ocorrem oscilações em determinadas posições binárias, recomendando consolidação dos valores posicionais." 
        )
    else:
        level = "Em desenvolvimento"
        opening = (
            "A apropriação do conteúdo encontra-se em desenvolvimento. A frequência de tentativas incorretas indica "
            "que a relação entre o número decimal, as potências de dois e a escolha de cada bit ainda precisa ser sistematizada." 
        )

    detail_parts = []
    if errors_by_weight:
        ranked = sorted(errors_by_weight.items(), key=lambda kv: (-kv[1], -kv[0]))
        top = ranked[:3]
        detail_parts.append(
            "As maiores concentrações de erro ocorreram nos pesos "
            + ", ".join(f"{w} ({n} erro{'s' if n != 1 else ''})" for w, n in top)
            + "."
        )
    else:
        detail_parts.append("Não houve concentração de erro em nenhum peso binário durante a partida.")

    if error_positions:
        recovery_rate = recovered / error_positions * 100.0
        if recovery_rate >= 70:
            detail_parts.append(
                "Após um primeiro erro, o estudante recuperou a escolha correta na tentativa seguinte na maior parte das posições, "
                "o que sugere boa capacidade de revisão imediata da estratégia."
            )
        elif max_streak >= 3:
            detail_parts.append(
                f"Houve pelo menos uma posição com {max_streak} tentativas incorretas consecutivas, sinalizando dificuldade persistente "
                "e não apenas erro ocasional."
            )

    if timeouts:
        detail_parts.append(
            f"No modo com limite de tempo foram registrados {timeouts} esgotamento(s) de tempo; esse dado deve ser interpretado "
            "separadamente dos erros conceituais, pois pode refletir velocidade de processamento."
        )

    recommendation = (
        "Recomenda-se retomar explicitamente a decomposição do decimal em potências de 2 e relacionar cada decisão 0/1 "
        "ao valor posicional correspondente, priorizando os pesos em que o relatório registrou maior incidência de erro."
        if wrong else
        "O desempenho permite avançar para conversões com maior amplitude numérica e para atividades que relacionem a escrita binária "
        "à decomposição em potências de 2."
    )

    return level, " ".join([opening] + detail_parts + [recommendation])


def report_text(stats: Dict) -> str:
    level, opinion = pedagogical_opinion(stats)
    q_total = int(stats.get("questions_completed") or 0)
    perfect = int(stats.get("perfect_questions") or 0)
    perfect_rate = (perfect / q_total * 100.0) if q_total else 0.0

    lines = [
        "BINÁRIO: ACERTO OU ERRE",
        "RELATÓRIO DE APRENDIZAGEM",
        "=" * 72,
        f"Estudante: {stats.get('name', '')}",
        f"Turma: {stats.get('class_name', '') or '-'}",
        f"Modo: {MODE_NAMES.get(stats.get('mode'), stats.get('mode', ''))}",
        f"Início: {stats.get('started_at', '')}",
        f"Término: {stats.get('finished_at', '') or ''}",
        "",
        "SÍNTESE DA PARTIDA",
        "-" * 72,
        f"Pontuação final: {stats.get('score', 0)} / meta {stats.get('target', 100)}",
        f"Questões concluídas: {q_total}",
        f"Bits corretos: {stats.get('correct_bits', 0)}",
        f"Tentativas incorretas: {stats.get('wrong_attempts', 0)}",
        f"Esgotamentos de tempo: {stats.get('timeout_attempts', 0)}",
        f"Precisão por tentativa: {float(stats.get('precision') or 0):.1f}%",
        f"Questões sem nenhum erro: {perfect} de {q_total} ({perfect_rate:.1f}%)",
        f"Tempo médio dos bits corretos: {float(stats.get('avg_correct_response_time') or 0):.2f} s",
        f"Tempo médio das tentativas incorretas: {float(stats.get('avg_wrong_response_time') or 0):.2f} s",
        "",
        "ERROS POR PESO BINÁRIO",
        "-" * 72,
    ]

    errors_by_weight = stats.get("errors_by_weight", {})
    if errors_by_weight:
        for weight, count in sorted(errors_by_weight.items(), reverse=True):
            lines.append(f"Peso {weight:>3}: {count} erro(s)")
    else:
        lines.append("Nenhum erro registrado.")

    lines += ["", "QUESTÕES EM QUE HOUVE DIFICULDADE", "-" * 72]
    wrong_questions = [q for q in stats.get("questions", []) if q.get("errors")]
    if not wrong_questions:
        lines.append("Nenhuma questão apresentou tentativa incorreta.")
    else:
        for idx, q in enumerate(wrong_questions, 1):
            lines.append(f"{idx}. Decimal {q['decimal']} | Binário correto: {q['binary']}")
            for e in q["errors"]:
                entered = "tempo esgotado" if e["entered"] == "TEMPO" else e["entered"]
                lines.append(
                    f"   - posição {e['position'] + 1}: digitado {entered}; esperado {e['expected']}; "
                    f"peso {e['weight']}; tempo {e['response_time']:.2f} s"
                )

    lines += [
        "",
        "RECUPERAÇÃO APÓS ERROS",
        "-" * 72,
        f"Posições que tiveram ao menos um erro: {stats.get('error_positions', 0)}",
        f"Posições recuperadas logo na tentativa seguinte: {stats.get('recovered_first_try_after_error', 0)}",
        f"Maior sequência de erros na mesma posição: {stats.get('max_wrong_streak', 0)}",
        "",
        "PARECER PEDAGÓGICO",
        "-" * 72,
        f"Classificação: {level}",
        "",
        opinion,
        "",
        "Observação: o parecer é uma síntese automática baseada nos dados desta partida e deve ser interpretado pelo professor "
        "em conjunto com outras evidências de aprendizagem.",
    ]
    return "\n".join(lines)


def save_report(stats: Dict, reports_dir: str) -> str:
    out = Path(reports_dir)
    out.mkdir(parents=True, exist_ok=True)
    student = _safe_filename(str(stats.get("name", "aluno")))
    session_id = stats.get("id", "sessao")
    path = out / f"{student}_sessao_{session_id}.txt"
    path.write_text(report_text(stats), encoding="utf-8")
    return str(path)

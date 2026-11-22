"""Validation for model-generated candidate evaluations."""
from __future__ import annotations

import math
from typing import Any


def validate_evaluations(data: Any, resume_count: int) -> list[dict[str, Any]]:
    """Require exactly one valid, indexed evaluation for every submitted resume."""
    if not isinstance(data, dict):
        raise ValueError("A resposta da IA precisa ser um objeto JSON")
    candidates = data.get("candidatos")
    if candidates is None:
        candidates = data.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != resume_count:
        raise ValueError("A IA não retornou avaliações para todos os currículos")
    if resume_count < 1:
        raise ValueError("O lote precisa conter ao menos um currículo")

    seen_indices: set[int] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("Cada avaliação precisa ser um objeto")

        index = candidate.get("indice_curriculo")
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError("Índice de currículo inválido")
        if not 1 <= index <= resume_count:
            raise ValueError("Índice de currículo fora do lote")
        if index in seen_indices:
            raise ValueError(f"índice duplicado na resposta da IA: {index}")
        seen_indices.add(index)

        if not isinstance(candidate.get("identificacao_candidato"), dict):
            raise ValueError(f"Identificação inválida para o currículo {index}")
        evaluation = candidate.get("avaliacao_vaga")
        if not isinstance(evaluation, dict):
            raise ValueError(f"Avaliação inválida para o currículo {index}")
        score = evaluation.get("score_geral")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError(f"score inválido para o currículo {index}")
        if not math.isfinite(score) or not 0 <= score <= 100:
            raise ValueError(f"score fora do intervalo 0–100 para o currículo {index}")
        decision = evaluation.get("decisao_triagem")
        if not isinstance(decision, str) or not decision.strip():
            raise ValueError(f"Decisão ausente para o currículo {index}")

    if seen_indices != set(range(1, resume_count + 1)):
        raise ValueError("A IA não retornou avaliações para todos os currículos")
    return candidates

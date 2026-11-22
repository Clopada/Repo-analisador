"""Ponto de entrada alternativo (compatibilidade).

O código de execução fica em ``automacao_run.py``. Este módulo apenas
reexporta as funções para quem já usava ``python main.py``.
"""
from automacao_run import (  # noqa: F401
    MAX_CHARS_POR_PDF,
    MAX_TOTAL_CHARS,
    ciclo,
    curriculos_da_vaga,
    executar_loop,
    extrair_texto_pdf,
    extrair_vaga,
    inserir_curriculo,
    main,
    obter_vagas_com_lote_completo,
    processar_vaga,
    registrar_processado,
    remover_curriculos,
)

__all__ = [
    "MAX_CHARS_POR_PDF",
    "MAX_TOTAL_CHARS",
    "ciclo",
    "curriculos_da_vaga",
    "executar_loop",
    "extrair_texto_pdf",
    "extrair_vaga",
    "inserir_curriculo",
    "main",
    "obter_vagas_com_lote_completo",
    "processar_vaga",
    "registrar_processado",
    "remover_curriculos",
]

if __name__ == "__main__":
    main()

import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Carrega o .env do diretório do projeto (não do diretório atual),
# para funcionar mesmo quando o script é iniciado de outro lugar.
load_dotenv(BASE_DIR / ".env")


def _clean_env(valor) -> str:
    """Remove espaços e quotes circundantes de um valor lido do .env."""
    valor = str(valor).strip()
    if len(valor) >= 2 and ((valor[0] == '"' and valor[-1] == '"') or
                            (valor[0] == "'" and valor[-1] == "'")):
        valor = valor[1:-1]
    return valor


def _obrigatorio(nome) -> str:
    valor = (os.getenv(nome) or "").strip()
    if not valor:
        raise RuntimeError(f"Variável de ambiente obrigatória não definida: {nome}")
    return _clean_env(valor)


def _inteiro(nome, padrao, minimo=1):
    try:
        valor = int(_clean_env(os.getenv(nome, padrao)).strip())
    except (TypeError, ValueError):
        valor = int(padrao)
    return max(minimo, valor)


def _caminho(nome, padrao):
    valor = _clean_env(os.getenv(nome, padrao)).strip()
    caminho = Path(valor).expanduser()
    if not caminho.is_absolute():
        caminho = BASE_DIR / caminho
    return str(caminho)


def _scopes():
    bruto = _clean_env(os.getenv("SCOPES"))
    if bruto:
        try:
            dados = json.loads(bruto)
            if isinstance(dados, list) and dados:
                return [str(item) for item in dados]
        except (TypeError, ValueError):
            pass
    return ["https://mail.google.com/"]


EMAIL = _obrigatorio("EMAIL")
DESTINATARIO = _obrigatorio("DESTINATARIO")
NVIDIA_API_KEY = _obrigatorio("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

LIMITE_LOTE = _inteiro("LIMITE_LOTE", "10")
INTERVALO_MINUTOS = _inteiro("INTERVALO_MINUTOS", "60")
INTERVALO_SEGUNDOS = _inteiro("INTERVALO_SEGUNDOS", "0", minimo=0)
IA_TIMEOUT = float(os.getenv("IA_TIMEOUT", "180") or 180)
IA_TENTATIVAS = _inteiro("IA_TENTATIVAS", "3")

MAX_PDFS_POR_EMAIL = _inteiro("MAX_PDFS_POR_EMAIL", "10")

DB_PATH = _caminho("DB_PATH", "triagem.db")
PDF_DIR = _caminho("PDF_DIR", "pdfs")

SCOPES = _scopes()

# Valores de exemplo do .env.example: indicam configuração não preenchida.
_PLACEHOLDERS = {
    "seu-email@gmail.com",
    "sua-conta@gmail.com",
    "destino@empresa.com.br",
    "sua-chave-de-api",
}


def _placeholder(valor):
    v = (valor or "").strip().lower()
    return (
        v in _PLACEHOLDERS
        or v.startswith("sua-chave")
        or v.startswith("seu-email")
        or v.endswith("-aqui")
    )


def validar_configuracao() -> list[str]:
    """Retorna uma lista de problemas de configuração (vazia = tudo certo)."""
    problemas = []
    valores = {
        "EMAIL": EMAIL,
        "DESTINATARIO": DESTINATARIO,
        "NVIDIA_API_KEY": NVIDIA_API_KEY,
        "NVIDIA_BASE_URL": NVIDIA_BASE_URL,
        "NVIDIA_MODEL": NVIDIA_MODEL,
    }
    for nome, valor in valores.items():
        if _placeholder(valor):
            problemas.append(f"{nome} ainda está com o valor de exemplo no .env")
        elif nome in ("EMAIL", "DESTINATARIO") and "@" not in valor:
            problemas.append(f"{nome} não parece um e-mail válido: {valor!r}")
        elif nome == "NVIDIA_API_KEY" and not valor:
            problemas.append("NVIDIA_API_KEY está vazia no .env")
        elif nome == "NVIDIA_MODEL" and not valor:
            problemas.append("NVIDIA_MODEL está vazia no .env")
        elif nome == "NVIDIA_BASE_URL" and not valor:
            problemas.append("NVIDIA_BASE_URL está vazia no .env")

    return problemas

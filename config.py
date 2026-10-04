import os
from dotenv import load_dotenv

load_dotenv()


def _obrigatorio(nome):
    valor = os.getenv(nome)
    if not valor:
        raise RuntimeError(f"Variável de ambiente obrigatória não definida: {nome}")
    return valor


EMAIL = _obrigatorio("EMAIL")
DESTINATARIO = _obrigatorio("DESTINATARIO")
NVIDIA_API_KEY = _obrigatorio("NVIDIA_API_KEY")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

LIMITE_LOTE = int(os.getenv("LIMITE_LOTE", "20"))
INTERVALO_MINUTOS = int(os.getenv("INTERVALO_MINUTOS", "60"))

DB_PATH = "triagem.db"
PDF_DIR = "pdfs"

SCOPES = [
    "https://mail.google.com/",
]
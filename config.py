# Preencha com seus dados
EMAIL = "email_para_ser_monitorado"
DESTINATARIO = "email_para_enviar_relatorio"
NVIDIA_API_KEY = "sua_apikey_nemotron"
NVIDIA_MODEL = "nvidia/nemotron-3-super-120b-a12b"
NVIDIA_BASE_URL = "url_nemotron"

LIMITE_LOTE = 2         # currículos por vaga
INTERVALO_MINUTOS = 1     # tempo entre cada verificação

DB_PATH = "triagem.db"
PDF_DIR = "pdfs"

# Escopos necessários
SCOPES = [
    "https://mail.google.com/",                        # IMAP + SMTP
    "https://www.googleapis.com/auth/gmail.modify",
]
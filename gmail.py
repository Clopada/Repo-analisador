import base64
import imaplib
import os
import socket
import smtplib
import tempfile
import time
from email import message_from_bytes
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import (
    BASE_DIR,
    DESTINATARIO,
    EMAIL,
    PDF_DIR,
    SCOPES,
    MAX_PDFS_POR_EMAIL,
)

socket.setdefaulttimeout(30)

MAX_PDF_BYTES = 10 * 1024 * 1024

TOKEN_PATH = BASE_DIR / "token.json"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"


def _salvar_token(conteudo):
    """Grava o token OAuth atomicamente com permissões restritas no POSIX."""
    fd, temporario = tempfile.mkstemp(prefix=".token.", dir=TOKEN_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            if os.name == "posix":
                os.fchmod(arquivo.fileno(), 0o600)
            arquivo.write(conteudo)
        os.replace(temporario, TOKEN_PATH)
    finally:
        try:
            os.unlink(temporario)
        except FileNotFoundError:
            pass


def obter_credenciais():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Arquivo de credenciais do Google não encontrado: {CREDENTIALS_PATH}. "
                    "Baixe o credentials.json no Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        _salvar_token(creds.to_json())
    return creds


def _auth_string(email, token):
    return f"user={email}\1auth=Bearer {token}\1\1"


def identificador_mensagem(msg, uid):
    """Retorna Message-ID ou fallback único e estável para a caixa INBOX."""
    message_id = (msg.get("Message-ID") or "").strip()
    return message_id or f"imap-uid:{uid}"


def conectar_imap(creds):
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
    status, _ = imap.authenticate("XOAUTH2", lambda x: _auth_string(EMAIL, creds.token).encode())
    if status != "OK":
        raise RuntimeError(f"Falha na autenticação IMAP (status {status})")
    return imap


def buscar_nao_lidos(creds=None):
    creds = creds or obter_credenciais()
    imap = conectar_imap(creds)
    try:
        imap.select("INBOX")
        # Busca todos os emails não lidos e filtra no Python
        # Usa timeout mais longo para evitar travamento
        status, mensagens = imap.uid("search", None, "UNSEEN")
        if status != "OK" or not mensagens:
            return []
        ids = mensagens[0].split()
        if not ids:
            return []
        todos_emails = []
        for uid in ids:
            try:
                status, dados = imap.uid("fetch", uid, "(RFC822)")
            except Exception as e:
                print(f"  [ERRO] Falha ao buscar email {uid}: {e}", flush=True)
                continue
            if status != "OK" or not dados or not isinstance(dados[0], tuple):
                continue
            todos_emails.append((uid.decode("ascii"), message_from_bytes(dados[0][1])))
        return todos_emails
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass


def extrair_pdf(msg, pasta=None):
    pasta = pasta or PDF_DIR
    os.makedirs(pasta, exist_ok=True)
    anexos = []

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if not filename or not filename.lower().endswith(".pdf"):
            continue

        # Sanitiza nome (evita path traversal)
        nome_limpo = os.path.basename(filename)
        nome_limpo = "".join(c for c in nome_limpo if c.isalnum() or c in " ._-()").strip()
        if not nome_limpo.lower().endswith(".pdf"):
            nome_limpo += ".pdf"
        if len(nome_limpo) > 150:
            nome_limpo = nome_limpo[:145] + ".pdf"

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        if len(payload) > MAX_PDF_BYTES:
            print(f"  [PDF] Ignorado {nome_limpo}: {len(payload)} bytes > limite", flush=True)
            continue

        if not payload.startswith(b"%PDF-"):
            print(f"  [PDF] Ignorado {nome_limpo}: não é PDF real", flush=True)
            continue

        nome_final = f"{time.time_ns()}_{nome_limpo}"
        caminho = os.path.join(pasta, nome_final)

        with open(caminho, "wb") as f:
            f.write(payload)

        anexos.append((caminho, nome_limpo))
        if len(anexos) >= MAX_PDFS_POR_EMAIL:
            print(
                f"  [PDF] Limite de {MAX_PDFS_POR_EMAIL} PDFs por e-mail atingido; "
                "os demais anexos foram ignorados.",
                flush=True,
            )
            break

    return anexos


def marcar_como_lido(creds, num_imap):
    imap = conectar_imap(creds)
    try:
        imap.select("INBOX")
        status, _ = imap.uid("store", str(num_imap), "+FLAGS", "(\\Seen)")
        if status != "OK":
            raise RuntimeError(f"Falha ao marcar UID {num_imap} como lido: {status}")
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass


def enviar_email(assunto, html, anexos, anexo_html=None):
    creds = obter_credenciais()
    msg = MIMEMultipart()
    msg["From"] = EMAIL
    msg["To"] = DESTINATARIO
    msg["Subject"] = assunto
    msg.attach(MIMEText(html, "html", "utf-8"))

    if anexo_html:
        conteudo_html, nome_html = anexo_html
        part = MIMEApplication(conteudo_html.encode("utf-8"), _subtype="html")
        part.add_header("Content-Disposition", "attachment", filename=nome_html)
        msg.attach(part)

    for caminho, nome in anexos:
        with open(caminho, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=nome)
        msg.attach(part)

    auth = f"user={EMAIL}\1auth=Bearer {creds.token}\1\1"
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
    try:
        server.ehlo()
        server.starttls()
        server.ehlo()
        codigo, resposta = server.docmd(
            "AUTH", "XOAUTH2 " + base64.b64encode(auth.encode()).decode()
        )
        if codigo != 235:
            raise RuntimeError(f"Falha na autenticação SMTP ({codigo}): {resposta!r}")
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass

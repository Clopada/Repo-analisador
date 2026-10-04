import imaplib
import smtplib
import base64
import os
import socket
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email import message_from_bytes
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import EMAIL, DESTINATARIO, SCOPES

socket.setdefaulttimeout(30)

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDFS_POR_EMAIL = 5


def obter_credenciais():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


def _auth_string(email, token):
    return f"user={email}\1auth=Bearer {token}\1\1"


def conectar_imap(creds):
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
    imap.authenticate("XOAUTH2", lambda x: _auth_string(EMAIL, creds.token).encode())
    return imap


def buscar_nao_lidos():
    creds = obter_credenciais()
    imap = conectar_imap(creds)
    try:
        imap.select("INBOX")
        status, mensagens = imap.search(None, '(UNSEEN SUBJECT "VAGA")')
        if status != "OK":
            return []
        ids = mensagens[0].split()
        resultados = []
        for num in ids:
            status, dados = imap.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            msg = message_from_bytes(dados[0][1])
            resultados.append((num.decode(), msg))
        return resultados
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass


def extrair_pdf(msg, pasta="pdfs"):
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

        nome_final = f"{int(time.time()*1000)}_{nome_limpo}"
        caminho = os.path.join(pasta, nome_final)

        with open(caminho, "wb") as f:
            f.write(payload)

        anexos.append((caminho, nome_limpo))
        if len(anexos) >= MAX_PDFS_POR_EMAIL:
            break

    return anexos


def marcar_como_lido(creds, num_imap):
    imap = conectar_imap(creds)
    try:
        imap.select("INBOX")
        imap.store(num_imap, "+FLAGS", "\\Seen")
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
    msg.attach(MIMEText(html, "html"))

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
    server.starttls()
    server.ehlo()
    server.docmd("AUTH", "XOAUTH2 " + base64.b64encode(auth.encode()).decode())
    server.send_message(msg)
    server.quit()
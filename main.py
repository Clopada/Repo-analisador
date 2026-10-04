import time
import re
import os
import json
from datetime import datetime

import db
import gmail
import ia
import report
from config import LIMITE_LOTE, INTERVALO_MINUTOS

VAGA_REGEX = re.compile(r"VAGA[\s:\-]*([^\r\n]+)", re.IGNORECASE)

MAX_CHARS_POR_PDF = 30_000
MAX_TOTAL_CHARS = 200_000


def extrair_vaga(assunto):
    m = VAGA_REGEX.search(assunto)
    if not m:
        return None
    vaga = m.group(1).strip().lower()
    vaga = re.sub(r"\s+", " ", vaga)
    vaga = re.sub(r"[\/\\?*\[\]:]", "-", vaga)
    return vaga[:90]


def processar_vaga(vaga, limite):
    curriculos = db.curriculos_da_vaga(vaga, limite)
    if len(curriculos) < limite:
        return

    print(f"[{vaga}] Processando lote de {len(curriculos)} currículos...", flush=True)

    textos = []
    total_chars = 0
    for c in curriculos:
        try:
            from pypdf import PdfReader
            reader = PdfReader(c["caminho_pdf"])
            texto = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            print(f"  [PDF] Erro ao ler {c['caminho_pdf']}: {e}", flush=True)
            texto = ""

        if len(texto) > MAX_CHARS_POR_PDF:
            texto = texto[:MAX_CHARS_POR_PDF] + "\n[... texto truncado ...]"

        total_chars += len(texto)
        if total_chars > MAX_TOTAL_CHARS:
            print(f"  [PDF] Limite total de texto atingido, ignorando os demais.", flush=True)
            break

        if not texto.strip():
            print(f"  [PDF] Aviso: {c['nome_arquivo']} sem texto extraível", flush=True)
        textos.append((c["nome_arquivo"], texto))

    com_texto = [t for t in textos if t[1].strip()]
    if not com_texto:
        print(f"[{vaga}] Nenhum PDF com texto extraível. Abortando lote.", flush=True)
        return

    try:
        resposta = ia.avaliar_curriculos(vaga, textos)
    except Exception as e:
        print(f"[{vaga}] Erro na IA: {e}", flush=True)
        return

    jt = resposta.strip()
    if "```" in jt:
        jt = jt.replace("```json", "").replace("```", "").strip()
    ini = jt.find("{")
    if ini > 0:
        jt = jt[ini:]
    try:
        dados = json.loads(jt)
        avaliacoes = dados.get("candidatos", [])
    except Exception as e:
        print(f"[{vaga}] Erro parse IA: {e}", flush=True)
        print(f"  Bruto (500): {jt[:500]}", flush=True)
        return

    if not avaliacoes:
        print(f"[{vaga}] IA não retornou candidatos. Abortando.", flush=True)
        return

    arquivos_orig = [
        {"posicao": i + 1, "nome_arquivo": c["nome_arquivo"]}
        for i, c in enumerate(curriculos)
    ]
    corpo_html = report.gerar_corpo_email(vaga, avaliacoes)
    anexo_html = report.gerar_anexo_relatorio(vaga, avaliacoes, arquivos_orig)

    anexos_pdf = [(c["caminho_pdf"], c["nome_arquivo"]) for c in curriculos]
    assunto = f"Triagem em Lote - Vaga {vaga.title()}"
    try:
        gmail.enviar_email(
            assunto,
            corpo_html,
            anexos_pdf,
            anexo_html=(anexo_html, "relatorio_completo.html")
        )
    except Exception as e:
        print(f"[{vaga}] Erro ao enviar e-mail: {e}", flush=True)
        return

    for c in curriculos:
        db.registrar_processado(c["message_id"])
        try:
            os.remove(c["caminho_pdf"])
        except Exception:
            pass
    db.limpar_vaga(vaga)

    print(f"[{vaga}] Lote processado e limpo.", flush=True)


def ciclo():
    print(f"\n[{datetime.now()}] Verificando caixa...", flush=True)

    try:
        creds = gmail.obter_credenciais()
    except Exception as e:
        print(f"Erro ao obter credenciais: {e}", flush=True)
        return

    try:
        emails = gmail.buscar_nao_lidos()
        print(f"  {len(emails)} e-mail(s) não lido(s).", flush=True)
    except Exception as e:
        print(f"Erro ao buscar e-mails: {e}", flush=True)
        return

    for num_imap, msg in emails:
        try:
            assunto = msg.get("Subject", "") or ""
            remetente = msg.get("From", "") or ""
            message_id = msg.get("Message-ID", "") or ""

            vaga = extrair_vaga(assunto)
            if not vaga:
                continue

            if db.ja_processado(message_id):
                gmail.marcar_como_lido(creds, num_imap)
                continue

            anexos = gmail.extrair_pdf(msg)
            if not anexos:
                continue

            for caminho, nome_arquivo in anexos:
                db.inserir_curriculo(vaga, message_id, remetente, assunto, nome_arquivo, caminho)
                print(f"  + {vaga} <- {nome_arquivo}", flush=True)

            gmail.marcar_como_lido(creds, num_imap)
        except Exception as e:
            print(f"Erro processando e-mail: {e}", flush=True)

    for v in db.vagas_com_lote_completo(limite=LIMITE_LOTE):
        processar_vaga(v["vaga"], LIMITE_LOTE)


def main():
    db.init()
    os.makedirs("pdfs", exist_ok=True)
    print(f"Triagem iniciada. LIMITE_LOTE = {LIMITE_LOTE}. Intervalo = {INTERVALO_MINUTOS} min.", flush=True)
    while True:
        try:
            ciclo()
        except Exception as e:
            print(f"Erro no ciclo: {e}", flush=True)
        print(f"Aguardando {INTERVALO_MINUTOS} minutos...", flush=True)
        time.sleep(INTERVALO_MINUTOS * 2)


if __name__ == "__main__":
    main()
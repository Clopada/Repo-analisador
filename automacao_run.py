"""
Automação de Triagem de Currículos por E-mail.

Executa automaticamente:
  1. Verifica caixa de entrada (IMAP) procurando e-mails com vaga
  2. Extrai PDFs de currículos dos e-mails
  3. Envia para a IA (NVIDIA NIM) para análise
  4. Gera relatório HTML e envia por e-mail
  5. Registra no banco de dados (SQLite)

Executável via:
  python automacao_run.py          # modo contínuo
  python automacao_run.py --once   # executa uma vez e para
  python automacao_run.py --intervalo=30       # intervalo em minutos
  python automacao_run.py --intervalo-seconds=30  # intervalo em segundos (debug)
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.setrecursionlimit(10000)
socket.setdefaulttimeout(60)

MAX_CHARS_POR_PDF = 30_000
MAX_TOTAL_CHARS = 200_000

# Regex para e-mails do tipo "VAGA" (formato atual)
VAGA_REGEX = re.compile(r"VAGA[\s:\-]*([^\r\n]+)", re.IGNORECASE)

# Regex para e-mails do tipo "Trabalhe Conosco" (novo formato)
# Ex: "Trabalhe Conosco -- Nova candidatura: NOME DO CANDIDATO"
TRABALHE_CONOSCO_REGEX = re.compile(
    r"Trabalhe[\s:\\-]*(?:Conosco|CONOSCO)[\s:\\-]*Nova[\s]+Candidatura[\s:：]*\s*(.+)",
    re.IGNORECASE
)

# Regex para extrair dados do corpo do email "Trabalhe Conosco"
# Formato real do corpo (campos podem estar na mesma linha):
# Nome: X E-mail: X Telefone: X Data de nascimento: X
# Cidade: X Endereço: X
# Escolaridade: X Área de interesse: X Último cargo: X
# Indicação: X Consentimento para recrutamento: true Origem: X
TRABALHE_CONOSCO_BODY_REGEX = re.compile(
    r"Nome:\s*(?P<nome>[^\n]+?)\s*E-mail:\s*(?P<email>[^\n]+?)\s*"
    r"Telefone:\s*(?P<telefone>[^\n]+?)\s*Data de nascimento:\s*(?P<data_nascimento>[^\n]+?)\s*"
    r"Cidade:\s*(?P<cidade>[^\n]+?)\s*Endereço:\s*(?P<endereco>[^\n]+?)\s*"
    r"Escolaridade:\s*(?P<escolaridade>[^\n]+?)\s*"
    r"Área de interesse:\s*(?P<area_de_interesse>[^\n]+?)\s*"
    r"Último cargo:\s*(?P<ultimo_cargo>[^\n]+?)\s*"
    r"Indicação:\s*(?P<indicacao>[^\n]+?)\s*"
    r"Consentimento para recrutamento:\s*(?P<consentimento>[^\n]+?)\s*"
    r"Origem:\s*(?P<origem>[^\n]+?)\s*$",
    re.IGNORECASE | re.MULTILINE
)


def _carregar_config_env() -> None:
    """Carrega variáveis de ambiente do arquivo .env se existir."""
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
    elif (BASE_DIR / ".env.example").exists():
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env.example", override=False)


_carregar_config_env()


def _problemas_config() -> list[str]:
    from config import validar_configuracao

    return validar_configuracao()


def iniciar_db() -> None:
    """Inicializa o banco de dados SQLite."""
    from db import init

    init()


def obter_areas_com_lote_completo(limite=20):
    """Retorna lista de áreas de interesse que atingiram o limite de currículos."""
    from db import vagas_com_lote_completo as _db_areas

    return _db_areas(limite=limite)


def registrar_processado(message_id: str) -> None:
    """Registra um e-mail como processado no banco."""
    from db import registrar_processado as _reg

    _reg(message_id)


def inserir_curriculo(
    vaga: str,
    area_de_interesse: str,
    message_id: str,
    remetente: str,
    assunto: str,
    nome_arquivo: str,
    caminho_pdf: str,
) -> None:
    """Insere um currículo no banco."""
    from db import inserir_curriculo as _ins

    _ins(vaga, area_de_interesse, message_id, remetente, assunto, nome_arquivo, caminho_pdf)


def remover_curriculos(ids: list[int]) -> None:
    """Remove do banco somente os currículos já processados."""
    from db import remover_curriculos as _rem

    _rem(ids)


def curriculos_da_vaga(vaga: str, limite: int = 20) -> list[dict]:
    """Retorna currículos de uma vaga."""
    from db import curriculos_da_vaga as _cur

    return _cur(vaga, limite=limite)


def extrair_texto_pdf(caminho_pdf: str, max_chars: int = MAX_CHARS_POR_PDF) -> str:
    """Extrai texto de um PDF, truncando se necessário."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(caminho_pdf)
        texto = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        print(f"  [PDF] Erro ao ler {caminho_pdf}: {exc}", flush=True)
        return ""

    if len(texto) > max_chars:
        texto = texto[:max_chars] + "\n[... texto truncado ...]"
    return texto


def extrair_vaga(assunto: str) -> str | None:
    """Extrai o nome da vaga do assunto do e-mail (formato VAGA)."""
    m = VAGA_REGEX.search(assunto or "")
    if not m:
        return None
    vaga = m.group(1).strip().lower()
    vaga = re.sub(r"\s+", " ", vaga)
    vaga = re.sub(r"[\/\\?*\\[\\]:]", "-", vaga)
    return vaga[:90]


def extrair_email_trabalhe_conosco(assunto: str, corpo: str) -> dict | None:
    """Extrai os dados do e-mail 'Trabalhe Conosco' e retorna um dicionário com os campos.

    Formato esperado no corpo:
      Nome: X
      E-mail: X
      Telefone: X
      ...
    """
    m = TRABALHE_CONOSCO_REGEX.search(assunto or "")
    if not m:
        return None

    dados = {
        "area_de_interesse": "",
        "ultimo_cargo": "",
        "indicao": "",
        "consentimento": "",
        "origem": "",
        "nome": "",
        "email": "",
        "telefone": "",
        "data_nascimento": "",
        "cidade": "",
        "endereco": "",
        "escolaridade": "",
    }

    # Primeiro tenta extrair do corpo usando regex específica
    body_match = TRABALHE_CONOSCO_BODY_REGEX.search(corpo or "")
    if body_match:
        for key in dados:
            if key in body_match.groupdict():
                dados[key] = body_match.group(key).strip()
        return dados

    # Fallback: procura pelo nome no assunto e depois pelo corpo
    nome_match = re.search(r"Nova candidatura:\s*(.+)", assunto or "", re.IGNORECASE)
    if nome_match:
        dados["nome"] = nome_match.group(1).strip()

    return dados


def processar_area(area, limite: int) -> None:
    """Processa um lote de currículos de uma área de interesse (novo formato)."""
    from db import curriculos_da_vaga
    from ia import avaliar_curriculos, extrair_json
    from report import gerar_anexo_relatorio, gerar_corpo_email
    from validation import validate_evaluations

    curriculos = curriculos_da_vaga(area, limite=limite)
    if len(curriculos) < limite:
        return

    print(f"[{area}] Processando lote de {len(curriculos)} currículos de interesse...", flush=True)

    itens = []
    total_chars = 0
    for posicao, c in enumerate(curriculos, 1):
        texto = extrair_texto_pdf(c["caminho_pdf"])

        if total_chars + len(texto) > MAX_TOTAL_CHARS:
            print("  [PDF] Limite total de texto atingido, ignorando os demais.", flush=True)
            break

        total_chars += len(texto)
        if not texto.strip():
            print(f"  [PDF] Aviso: {c['nome_arquivo']} sem texto extraível", flush=True)

        itens.append(
            {
                "id": c["id"],
                "message_id": c["message_id"],
                "posicao": posicao,
                "nome_arquivo": c["nome_arquivo"],
                "caminho_pdf": c["caminho_pdf"],
                "texto": texto,
                "area_de_interesse": c["area_de_interesse"],
            }
        )

    if not itens:
        print(f"[{area}] Nenhum currículo pôde ser lido. Abortando lote.", flush=True)
        return

    if not any(item["texto"].strip() for item in itens):
        print(f"[{area}] Nenhum PDF com texto extraível. Abortando lote.", flush=True)
        return

    textos = [(item["nome_arquivo"], item["texto"]) for item in itens]

    try:
        resposta = avaliar_curriculos(area, textos)
    except Exception as exc:
        print(f"[{area}] Erro na IA: {exc}", flush=True)
        return

    try:
        avaliacoes = validate_evaluations(extrair_json(resposta), len(itens))
    except Exception as exc:
        print(f"[{area}] Erro parse IA: {exc}", flush=True)
        print(f"  Bruto (500): {resposta.strip()[:500]}", flush=True)
        # Tentativas adicionais: remontar a partir do final do JSON
        for _ in range(2):
            try:
                nova_resposta = extrair_json(resposta, tentativas=2)
                avaliacoes = validate_evaluations(nova_resposta, len(itens))
                resposta = nova_resposta
                break
            except Exception as exc2:
                print(f"  Retry parse IA: {exc2}", flush=True)
                if _ < 1:
                    continue
        else:
            return

    if not avaliacoes:
        print(f"[{area}] IA não retornou candidatos. Abortando.", flush=True)
        return

    arquivos_orig = [
        {"posicao": item["posicao"], "nome_arquivo": item["nome_arquivo"]}
        for item in itens
    ]

    try:
        corpo_html = gerar_corpo_email(area, avaliacoes)
        anexo_html = gerar_anexo_relatorio(area, avaliacoes, arquivos_orig)
    except Exception as exc:
        print(f"[{area}] Erro gerando relatório: {exc}", flush=True)
        return

    anexos_pdf = [(item["caminho_pdf"], item["nome_arquivo"]) for item in itens]
    assunto = f"Triagem em Lote - {area}"

    try:
        from gmail import enviar_email

        enviar_email(
            assunto,
            corpo_html,
            anexos_pdf,
            anexo_html=(anexo_html, "relatorio_completo.html"),
        )
    except Exception as exc:
        print(f"[{area}] Erro ao enviar e-mail: {exc}", flush=True)
        return

    # Só remove o que foi realmente processado; currículos excedentes do lote
    # permanecem no banco para o próximo ciclo.
    ids = [item["id"] for item in itens]
    for message_id in {item["message_id"] for item in itens}:
        registrar_processado(message_id)
    for item in itens:
        try:
            os.remove(item["caminho_pdf"])
        except Exception:
            pass
    remover_curriculos(ids)

    print(f"[{area}] Lote processado e limpo ({len(itens)} currículos).", flush=True)


def ciclo(parar_evento: threading.Event | None = None) -> None:
    """Executa um ciclo de verificação da caixa de entrada."""
    from db import ja_processado
    from gmail import (
        buscar_nao_lidos,
        extrair_pdf,
        identificador_mensagem,
        marcar_como_lido,
        obter_credenciais,
    )

    print(f"\n[{datetime.now()}] Verificando caixa...", flush=True)

    try:
        creds = obter_credenciais()
    except Exception as exc:
        print(f"Erro ao obter credenciais: {exc}", flush=True)
        return

    try:
        emails = buscar_nao_lidos(creds)
        print(f"  {len(emails)} e-mail(s) não lido(s).", flush=True)
    except Exception as exc:
        print(f"Erro ao buscar e-mails: {exc}", flush=True)
        return

    for num_imap, msg in emails:
        if parar_evento is not None and parar_evento.is_set():
            return
        try:
            assunto = msg.get("Subject", "") or ""
            remetente = msg.get("From", "") or ""
            message_id = identificador_mensagem(msg, num_imap)

            # Verifica se é email do tipo VAGA (formato atual)
            vaga = extrair_vaga(assunto)
            if vaga:
                # É um email do tipo VAGA - manage like before
                if ja_processado(message_id):
                    marcar_como_lido(creds, num_imap)
                    continue

                anexos = extrair_pdf(msg)
                if not anexos:
                    print(f"  [AVISO] E-mail sem PDF válido: {assunto!r}", flush=True)
                    marcar_como_lido(creds, num_imap)
                    continue

                for caminho, nome_arquivo in anexos:
                    inserir_curriculo(vaga, message_id, remetente, assunto, nome_arquivo, caminho)
                    print(f"  + {vaga} <- {nome_arquivo}", flush=True)

                marcar_como_lido(creds, num_imap)
                continue

            # Verifica se é email do tipo Trabalhe Conosco
            dados_email = extrair_email_trabalhe_conosco(assunto, msg.get("Body", ""))
            if dados_email:
                # É um email do tipo Trabalhe Conosco
                area_de_interesse = dados_email.get("area_de_interesse", "").strip().lower()
                if not area_de_interesse:
                    print(f"  [AVISO] E-mail Trabalhe Conosco sem área de interesse: {assunto!r}", flush=True)
                    marcar_como_lido(creds, num_imap)
                    continue

                if ja_processado(message_id):
                    marcar_como_lido(creds, num_imap)
                    continue

                anexos = extrair_pdf(msg)
                if not anexos:
                    print(f"  [AVISO] E-mail Trabalhe Conosco sem PDF válido: {assunto!r}", flush=True)
                    marcar_como_lido(creds, num_imap)
                    continue

                for caminho, nome_arquivo in anexos:
                    # Usa a área de interesse como identificador
                    inserir_curriculo(area_de_interesse, message_id, remetente, assunto, nome_arquivo, caminho)
                    print(f"  + {area_de_interesse} <- {nome_arquivo} (Trabalhe Conosco)", flush=True)

                marcar_como_lido(creds, num_imap)
                continue

            # Email desconhecido, ignora
            print(f"  [AVISO] Email não reconhecido: {assunto!r}", flush=True)
            marcar_como_lido(creds, num_imap)

        except Exception as exc:
            print(f"Erro processando e-mail: {exc}", flush=True)

    from config import LIMITE_LOTE

    for area in obter_areas_com_lote_completo(limite=LIMITE_LOTE):
        if parar_evento is not None and parar_evento.is_set():
            return
        processar_area(area["vaga"], LIMITE_LOTE)


def executar_loop(
    intervalo_segundos: int | None = None,
    parar_evento: threading.Event | None = None,
) -> None:
    """Loop principal, com suporte a parada cooperativa (usado pela GUI)."""
    from config import INTERVALO_MINUTOS, PDF_DIR

    problemas = _problemas_config()
    if problemas:
        mensagem = "Configuração incompleta no .env:\n" + "\n".join(
            f" - {p}" for p in problemas
        )
        print(mensagem, flush=True)
        raise RuntimeError(mensagem)

    iniciar_db()
    os.makedirs(PDF_DIR, exist_ok=True)

    if intervalo_segundos is None:
        intervalo_segundos = max(1, INTERVALO_MINUTOS) * 60

    print(
        f"Triagem iniciada. Intervalo = {intervalo_segundos} segundos.",
        flush=True,
    )

    while True:
        try:
            ciclo(parar_evento)
        except Exception as exc:
            print(f"Erro no ciclo: {exc}", flush=True)

        if parar_evento is not None:
            if parar_evento.wait(intervalo_segundos):
                print("Execução interrompida pelo usuário.", flush=True)
                return
        else:
            print(f"Aguardando {intervalo_segundos} segundos...", flush=True)
            time.sleep(intervalo_segundos)


def main(argv: list[str] | None = None) -> None:
    """Loop principal da automação."""
    from config import INTERVALO_MINUTOS, INTERVALO_SEGUNDOS

    parser = argparse.ArgumentParser(description="Automação de Triagem de Currículos por E-mail")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Executa um ciclo e para",
    )
    parser.add_argument(
        "--intervalo",
        type=int,
        default=None,
        help="Intervalo entre ciclos em minutos (sobrescreve a configuração)",
    )
    parser.add_argument(
        "--intervalo-seconds",
        type=int,
        default=None,
        help="Intervalo em segundos (para debug)",
    )
    args = parser.parse_args(argv)

    # Define o intervalo padrão: se o usuário setou INTERVALO_SEGUNDOS no .env
    # ele será usado; caso contrário, o valor em minutos é convertido.
    if INTERVALO_SEGUNDOS > 0:
        intervalo_segundos = max(1, INTERVALO_SEGUNDOS)
    else:
        intervalo_segundos = max(1, INTERVALO_MINUTOS) * 60

    if args.intervalo is not None:
        intervalo_segundos = max(1, args.intervalo) * 60
    if args.intervalo_seconds is not None:
        intervalo_segundos = max(1, args.intervalo_seconds)

    problemas = _problemas_config()
    if problemas:
        print("Não foi possível iniciar: configuração incompleta no .env", flush=True)
        for p in problemas:
            print(f" - {p}", flush=True)
        print(f"Edite: {BASE_DIR / '.env'}", flush=True)
        raise SystemExit(2)

    iniciar_db()
    if args.once:
        ciclo()
        return

    try:
        executar_loop(intervalo_segundos)
    except RuntimeError as exc:
        print(f"Erro: {exc}", flush=True)


if __name__ == "__main__":
    main()

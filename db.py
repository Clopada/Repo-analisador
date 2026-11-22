import sqlite3
from datetime import datetime
from config import DB_PATH


def _conn():
    return sqlite3.connect(DB_PATH, timeout=30)


def init():
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS curriculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vaga TEXT NOT NULL,
            area_de_interesse TEXT NOT NULL DEFAULT '',
            message_id TEXT NOT NULL,
            remetente TEXT,
            assunto TEXT,
            nome_arquivo TEXT,
            caminho_pdf TEXT,
            criado_em TEXT,
            processado INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS processados (
            message_id TEXT PRIMARY KEY,
            processado_em TEXT
        )
    """)
    conn.commit()
    conn.close()


def ja_processado(message_id):
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT 1 FROM processados WHERE message_id = ?", (message_id,))
    r = c.fetchone()
    conn.close()
    return r is not None


def registrar_processado(message_id):
    conn = _conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO processados VALUES (?, ?)",
              (message_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def inserir_curriculo(vaga, area_de_interesse, message_id, remetente, assunto, nome_arquivo, caminho_pdf):
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO curriculos
        (vaga, area_de_interesse, message_id, remetente, assunto, nome_arquivo, caminho_pdf, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (vaga, area_de_interesse, message_id, remetente, assunto, nome_arquivo, caminho_pdf,
          datetime.now().isoformat()))
    conn.commit()
    conn.close()


def vagas_com_lote_completo(limite=20):
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        SELECT area_de_interesse, COUNT(*) as total
        FROM curriculos
        WHERE processado = 0
        GROUP BY area_de_interesse
        HAVING total >= ?
    """, (limite,))
    resultado = [{"vaga": r[0], "total": r[1]} for r in c.fetchall()]
    conn.close()
    return resultado


def curriculos_da_vaga(area_de_interesse, limite=20):
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        SELECT id, area_de_interesse, message_id, remetente, nome_arquivo, caminho_pdf
        FROM curriculos
        WHERE area_de_interesse = ? AND processado = 0
        ORDER BY criado_em
        LIMIT ?
    """, (area_de_interesse, limite))
    r = [{"id": x[0], "area_de_interesse": x[1], "message_id": x[2], "remetente": x[3],
          "nome_arquivo": x[4], "caminho_pdf": x[5]} for x in c.fetchall()]
    conn.close()
    return r


def marcar_processados(ids):
    """Marca como processados somente os currículos informados."""
    ids = [int(i) for i in ids if i is not None]
    if not ids:
        return
    conn = _conn()
    c = conn.cursor()
    c.executemany("UPDATE curriculos SET processado = 1 WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    conn.close()


def remover_curriculos(ids):
    """Remove somente os currículos informados (evita perder os excedentes do lote)."""
    ids = [int(i) for i in ids if i is not None]
    if not ids:
        return
    conn = _conn()
    c = conn.cursor()
    c.executemany("DELETE FROM curriculos WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    conn.close()


def limpar_vaga(vaga):
    """Remove TODOS os currículos da vaga (use com cuidado)."""
    conn = _conn()
    c = conn.cursor()
    c.execute("DELETE FROM curriculos WHERE vaga = ?", (vaga,))
    conn.commit()
    conn.close()
"""
Interface de Configuração e Controle da Automação de Triagem.

Interface gráfica (tkinter) com abas:
  1. E-mail (IMAP/IMAP + SMTP para envio)
  2. IA (NVIDIA NIM / provedor de IA)
  3. Banco de Dados (SQLite)
  4. Operação & Suporte (execução, logs, reinício)
"""
from __future__ import annotations

import queue
import sys
import threading
import traceback
from pathlib import Path
from tkinter import ttk, messagebox, scrolledtext
import tkinter as tk

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

_PLACEHOLDERS = {
    "seu-email@gmail.com",
    "sua-conta@gmail.com",
    "destino@empresa.com.br",
    "sua-chave-de-api",
}


def _env_atual() -> dict:
    try:
        from dotenv import dotenv_values

        return dict(dotenv_values(BASE_DIR / ".env") or {})
    except Exception:
        return {}


_ENV = _env_atual()


def _valor_env(chave: str, padrao: str = "") -> str:
    """Valor atual do .env; ignora placeholders do .env.example."""
    valor = _ENV.get(chave)
    if valor is None or str(valor).strip() == "":
        return padrao
    valor = str(valor)
    baixo = valor.strip().lower()
    if (
        valor.strip() in _PLACEHOLDERS
        or baixo.startswith("sua-chave")
        or baixo.startswith("seu-email")
        or baixo.endswith("-aqui")
    ):
        return ""
    return valor


def _formatar_env(chave: str, valor: str) -> str:
    escapado = str(valor).replace("\\", "\\\\").replace('"', '\\"')
    return f'{chave}="{escapado}"'


def _salvar_env(valores: dict) -> None:
    """Atualiza o .env preservando as chaves que não foram editadas."""
    path = BASE_DIR / ".env"
    existentes = []
    if path.exists():
        existentes = path.read_text(encoding="utf-8").splitlines()

    pendentes = {k: v for k, v in valores.items()}
    linhas = []
    for linha in existentes:
        if "=" in linha and not linha.lstrip().startswith("#"):
            chave = linha.split("=", 1)[0].strip()
            if chave in pendentes:
                linhas.append(_formatar_env(chave, pendentes.pop(chave)))
                continue
        linhas.append(linha)

    for chave, valor in pendentes.items():
        linhas.append(_formatar_env(chave, valor))

    path.write_text("\n".join(linhas).rstrip("\n") + "\n", encoding="utf-8")

try:
    import db as db_mod
    from db import init as db_init
except Exception:
    db_mod = None
    db_init = None

try:
    import gmail as gmail_mod
    from gmail import obter_credenciais
except Exception:
    gmail_mod = None
    obter_credenciais = None

try:
    import ia as ia_mod
    from ia import avaliar_curriculos
except Exception:
    ia_mod = None
    avaliar_curriculos = None

try:
    import report as report_mod
except Exception:
    report_mod = None

try:
    import automacao_run as automacao
except Exception:
    automacao = None


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
ABAS = [
    ("E-mail", "email"),
    ("IA", "ia"),
    ("Banco de Dados", "db"),
    ("Operação", "operacao"),
]

INICIAR_CONEXAO_BTN = "Conectar"
TESTAR_EMAIL_BTN = "Testar Conexão"
TESTAR_IA_BTN = "Testar Conexão IA"
TESTAR_DB_BTN = "Testar Banco"
PARAR_EXEC_BTN = "Parar Execução"
REINICIAR_BTN = "Reiniciar Automação"
SALVAR_BTN = "Salvar Configurações"
TESTAR_ENVIAR_BTN = "Testar Envio"
LOG_VAZIO = "━" * 60 + "\n"


class ConfigView:
    """Interface gráfica de configuração da automação."""

    def __init__(self, root: ttk.Widget) -> None:
        self.root = root
        self.root.title("Triagem IA — Configurações")
        self.root.geometry("900x650")
        self.root.minsize(800, 600)

        self.log_text = ""
        self.log_lock = threading.Lock()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.executando = False
        self.parar_evento = threading.Event()
        self.thread_execucao = None

        self._construir_ui()

    # ------------------------------------------------------------------
    # Construção da interface
    # ------------------------------------------------------------------
    def _construir_ui(self) -> None:
        self._criar_menu()
        self._criar_notebook()
        self._criar_abas()
        self._criar_atalhos()
        self._botoes_execucao(executando=False)
        self._atualizar_log(LOG_VAZIO + "Interface pronta.\n")
        self._drenar_log()

    def _criar_atalhos(self) -> None:
        self.root.bind("<Control-s>", lambda _e: self._salvar_todas())
        self.root.bind("<Control-t>", lambda _e: self._teste_email())
        self.root.bind("<Control-r>", lambda _e: self._reiniciar_automacao())
        self.root.bind("<Control-l>", lambda _e: self._limpar_log_e_widget())

    def _criar_menu(self) -> None:
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Salvar Configurações", command=self._salvar_todas)
        filemenu.add_command(label="Sair", command=self.root.quit)
        menubar.add_cascade(label="Arquivo", menu=filemenu)
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Sobre / Suporte", command=self._mostrar_sobre)
        menubar.add_cascade(label="Ajuda", menu=helpmenu)
        self.root.config(menu=menubar)

    def _criar_notebook(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Toolbar com botoes de acao
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(fill="x", padx=10, pady=(0, 10))

        self.btn_salvar = ttk.Button(
            self.toolbar, text="💾 Salvar Configurações", command=self._salvar_todas
        )
        self.btn_salvar.pack(side="left", padx=5)

        self.btn_sobre = ttk.Button(
            self.toolbar, text="ℹ️ Sobre", command=self._mostrar_sobre
        )
        self.btn_sobre.pack(side="left", padx=5)

        # Padrao para barras de botoes
        style = ttk.Style()
        style.configure("Toolbar.TButton", padding=(8, 6))

    def _criar_abas(self) -> None:
        self.aba_email = ConfigTabEmail(self.notebook, self)
        self.aba_ia = ConfigTabIA(self.notebook, self)
        self.aba_db = ConfigTabDB(self.notebook, self)
        self.aba_op = ConfigTabOperacao(self.notebook, self)

        self.notebook.add(self.aba_email.frame, text="📧 E-mail")
        self.notebook.add(self.aba_ia.frame, text="🤖 IA")
        self.notebook.add(self.aba_db.frame, text="🗄️ Banco")
        self.notebook.add(self.aba_op.frame, text="⚙️ Operação & Suporte")

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
    def _salvar_todas(self) -> None:
        tabs = [self.aba_email, self.aba_ia, self.aba_db, self.aba_op]
        for tab in tabs:
            tab.salvar()

        if self.executando:
            self._log("Configurações salvas. Pare e inicie novamente para aplicar.\n")
            messagebox.showinfo(
                "Sucesso",
                "Configurações salvas.\n\nA automação está em execução: "
                "pare e inicie novamente para aplicar as mudanças.",
            )
            return

        self._recarregar_modulos()
        messagebox.showinfo("Sucesso", "Configurações salvas e recarregadas.")
        self._atualizar_log("Configurações salvas.\n")

    def _recarregar_modulos(self) -> None:
        """Recarrega .env e módulos para aplicar mudanças sem reiniciar a GUI."""
        import importlib

        global _ENV

        try:
            from dotenv import load_dotenv

            load_dotenv(BASE_DIR / ".env", override=True)
        except Exception:
            pass

        _ENV = _env_atual()

        for nome in ("config", "db", "gmail", "ia", "report", "automacao_run"):
            modulo = sys.modules.get(nome)
            if modulo is None:
                continue
            try:
                importlib.reload(modulo)
            except Exception as exc:
                self._log(f"[AVISO] Não foi possível recarregar {nome}: {exc}\n")

    def _mostrar_sobre(self) -> None:
        msg = (
            "Triagem IA — Configurações\n\n"
            "Desenvolvido por: [Seu Nome]\n"
            "Versão: 1.0.0\n\n"
            "Atalhos úteis:\n"
            "  Ctrl+S — Salvar todas as configurações\n"
            "  Ctrl+T — Testar conexão\n"
            "  Ctrl+R — Reiniciar automação\n"
            "  Ctrl+L — Limpar log"
        )
        messagebox.showinfo("Sobre", msg)

    def _iniciar_execucao(self) -> None:
        if self.executando:
            return
        if self.thread_execucao and self.thread_execucao.is_alive():
            messagebox.showinfo(
                "Aguarde", "A execução anterior ainda está finalizando. Tente novamente em instantes."
            )
            return

        self._recarregar_modulos()

        problemas = []
        try:
            from config import validar_configuracao

            problemas = validar_configuracao()
        except Exception as exc:
            problemas = [str(exc)]

        if problemas:
            messagebox.showerror(
                "Configuração incompleta",
                "Corrija o .env antes de iniciar:\n\n" + "\n".join(f"• {p}" for p in problemas),
            )
            return

        if not messagebox.askyesno(
            "Confirmar",
            "Iniciar automação?\n\nA aplicação rodará em segundo plano, "
            "verificando e-mails periodicamente.",
        ):
            return

        self.parar_evento.clear()
        self.executando = True
        self._botoes_execucao(executando=True)
        self.thread_execucao = threading.Thread(target=self._executar_em_bg, daemon=True)
        self.thread_execucao.start()
        self._log("Automação iniciada.\n")

    def _parar_execucao(self) -> None:
        if not self.executando:
            return
        self.parar_evento.set()
        self.executando = False
        self._botoes_execucao(executando=False)
        self._log("Solicitada parada da automação (ela para após o ciclo atual).\n")
        messagebox.showinfo("Parando", "A automação será interrompida após o ciclo atual.")

    def _reiniciar_automacao(self) -> None:
        if self.thread_execucao and self.thread_execucao.is_alive():
            self.parar_evento.set()
            self.thread_execucao.join(timeout=3)
        self.executando = False
        self._iniciar_execucao()

    def _executar_em_bg(self) -> None:
        try:
            from automacao_run import executar_loop

            executar_loop(parar_evento=self.parar_evento)
        except Exception as exc:
            self._log_erro(exc)
            self.root.after(
                0,
                lambda erro=exc: messagebox.showerror(
                    "Erro na automação", f"A automação foi interrompida:\n{erro}"
                ),
            )
        finally:
            self.executando = False
            self.root.after(0, lambda: self._botoes_execucao(executando=False))
            self._log("Automação finalizada.\n")

    def _teste_email(self) -> None:
        """Testa conexão IMAP com o Gmail."""
        if not gmail_mod:
            messagebox.showerror("Erro", "Módulo gmail não disponível.")
            return

        try:
            creds = obter_credenciais()
            imap = gmail_mod.conectar_imap(creds)
            try:
                imap.select("INBOX")
            finally:
                imap.logout()
            messagebox.showinfo("Sucesso", "Conexão IMAP com o Gmail OK.")
            self._log("Teste de e-mail: OK (conexão IMAP).\n")
        except Exception as exc:
            messagebox.showerror("Falha no teste", f"Não foi possível conectar ao Gmail:\n{exc}")
            self._log_erro(exc)

    def _teste_ia(self) -> None:
        """Valida a configuração da API da IA."""
        if not ia_mod:
            messagebox.showerror("Erro", "Módulo ia não disponível (dependências instaladas?).")
            return

        try:
            api_key = self.aba_ia.get_valor_key("NVIDIA_API_KEY")
            if not api_key:
                messagebox.showerror("Erro", "Informe a API key do provedor de IA.")
                return
            if api_key.strip() in _PLACEHOLDERS:
                messagebox.showerror("Erro", "A API key ainda é o valor de exemplo do .env.")
                return

            messagebox.showinfo("Sucesso", "Configuração da IA carregada.")
            self._log("Teste de IA: configuração OK.\n")
        except Exception as exc:
            messagebox.showerror("Falha no teste", f"Não foi possível validar a IA:\n{exc}")
            self._log_erro(exc)

    def _teste_db(self) -> None:
        """Testa conexão com o banco de dados."""
        if db_mod is None:
            messagebox.showerror("Erro", "Módulo db não disponível.")
            return

        try:
            db_init()
            messagebox.showinfo("Sucesso", "Banco de dados OK.")
            self._log("Teste de banco: OK.")
        except Exception as exc:
            messagebox.showerror("Falha no teste", f"Não foi possível conectar ao banco:\n{exc}")
            self._log_erro(exc)

    def _teste_envio(self) -> None:
        """Testa envio de e-mail de teste."""
        if not gmail_mod:
            messagebox.showerror("Erro", "Módulo gmail não disponível.")
            return

        try:
            from gmail import enviar_email

            teste_html = "<p>Teste de envio de e-mail da automação Triagem IA.</p>"
            enviar_email("Teste — Triagem IA", teste_html, [], anexo_html=None)
            messagebox.showinfo("Sucesso", "E-mail de teste enviado com sucesso.")
            self._log("Teste de envio: OK.")
        except Exception as exc:
            messagebox.showerror("Falha no teste", f"Não foi possível enviar e-mail:\n{exc}")
            self._log_erro(exc)

    def _log(self, msg: str) -> None:
        """Adiciona uma linha ao log (seguro para threads)."""
        with self.log_lock:
            self.log_text += msg
        self.log_queue.put(msg)

    def _log_erro(self, exc: Exception) -> None:
        """Registra uma exceção no log."""
        texto = f"[ERRO] {exc}\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) + "\n"
        with self.log_lock:
            self.log_text += texto
        self.log_queue.put(texto)

    def _drenar_log(self) -> None:
        """Move as mensagens da fila para o widget na thread da interface."""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._atualizar_sem_botao(self.aba_op.log_text, msg)
        except queue.Empty:
            pass
        self.root.after(150, self._drenar_log)

    def _limpar_log(self) -> None:
        with self.log_lock:
            self.log_text = ""

    def _limpar_log_e_widget(self) -> None:
        self._limpar_log()
        self.aba_op.log_text.config(state="normal")
        self.aba_op.log_text.delete(1.0, "end")
        self.aba_op.log_text.config(state="disabled")

    def _botoes_execucao(self, executando: bool) -> None:
        """Ajusta os botões conforme a automação está rodando ou parada."""
        aba = getattr(self, "aba_op", None)
        if aba is None:
            return
        aba.btn_iniciar.state(["disabled"] if executando else ["!disabled"])
        aba.btn_parar.state(["!disabled"] if executando else ["disabled"])
        aba.btn_reiniciar.state(["!disabled"] if executando else ["disabled"])

    def _atualizar_sem_botao(self, widget, msg: str) -> None:
        """Atualiza um widget (ex.: log) sem reativar botões."""
        widget.config(state="normal")
        widget.insert("end", msg)
        widget.see("end")
        widget.config(state="disabled")

    def _atualizar_log(self, msg: str) -> None:
        self._log(msg)


# ---------------------------------------------------------------------------
# Aba: E-mail
# ---------------------------------------------------------------------------
class ConfigTabEmail:
    def __init__(self, notebook: ttk.Notebook, owner: ConfigView) -> None:
        self.owner = owner
        self.frame = ttk.Frame(notebook)

        self.vars = {}

        self._criar_widgets()

    def _criar_widgets(self) -> None:
        ttk.Label(self.frame, text="Configurações de E-mail (Gmail)").pack(anchor="w", padx=10, pady=(10, 5))

        campos = [
            ("E-mail (remetente)", "EMAIL", ""),
            ("Destinatário", "DESTINATARIO", ""),
        ]

        for label, key, default in campos:
            if key is None:
                continue
            frame = ttk.Frame(self.frame)
            frame.pack(fill="x", padx=10, pady=5)
            ttk.Label(frame, text=label).pack(side="left")
            var = ttk.Entry(frame, width=60)
            var.insert(0, _valor_env(key, default))
            var.pack(side="left", fill="x", expand=True, padx=5)
            self.vars[key] = var

        # Botões de teste
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill="x", padx=10, pady=10)
        self.btn_teste_email = ttk.Button(btn_frame, text="Testar Conexão", command=self._cmd_teste_email)
        self.btn_teste_email.pack(side="left", padx=5)

        ttk.Label(self.frame, text="OBS: Para o OAuth, o primeiro acesso exigirá autorização via navegador.").pack(anchor="w", padx=10, pady=(5, 10))

    def _cmd_teste_email(self) -> None:
        self.owner._teste_email()

    def salvar(self) -> None:
        _salvar_env({key: var.get().strip() for key, var in self.vars.items()})

    def get_valor_key(self, key: str = "") -> str:
        var = self.vars.get(key)
        return var.get().strip() if var is not None else ""


# ---------------------------------------------------------------------------
# Aba: IA
# ---------------------------------------------------------------------------
class ConfigTabIA:
    def __init__(self, notebook: ttk.Notebook, owner: ConfigView) -> None:
        self.owner = owner
        self.frame = ttk.Frame(notebook)
        self.vars = {}

        self._criar_widgets()

    def _criar_widgets(self) -> None:
        ttk.Label(self.frame, text="Configurações de IA").pack(anchor="w", padx=10, pady=(10, 5))

        campos = [
            ("API Key", "NVIDIA_API_KEY", ""),
            ("Modelo", "NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
            ("URL Base", "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            ("Timeout (s)", "IA_TIMEOUT", "180"),
            ("Tentativas", "IA_TENTATIVAS", "3"),
        ]

        for label, key, default in campos:
            frame = ttk.Frame(self.frame)
            frame.pack(fill="x", padx=10, pady=5)
            ttk.Label(frame, text=label).pack(side="left")
            var = ttk.Entry(frame, width=60)
            var.insert(0, _valor_env(key, default))
            var.pack(side="left", fill="x", expand=True, padx=5)
            self.vars[key] = var

        # Dica sobre segurança
        ttk.Label(
            self.frame,
            text="⚠️  A chave de API pode ficar exposta se o .env for compartilhado. "
                 "Garanta que .gitignore inclua o arquivo .env.",
            foreground="#b91c1c",
        ).pack(anchor="w", padx=10, pady=(5, 10))

    def salvar(self) -> None:
        _salvar_env({key: var.get().strip() for key, var in self.vars.items()})

    def get_valor_key(self, key: str = "") -> str:
        var = self.vars.get(key)
        return var.get().strip() if var is not None else ""


# ---------------------------------------------------------------------------
# Aba: Banco de Dados
# ---------------------------------------------------------------------------
class ConfigTabDB:
    def __init__(self, notebook: ttk.Notebook, owner: ConfigView) -> None:
        self.owner = owner
        self.frame = ttk.Frame(notebook)
        self.vars = {}

        self._criar_widgets()

    def _criar_widgets(self) -> None:
        ttk.Label(self.frame, text="Configurações de Banco de Dados").pack(anchor="w", padx=10, pady=(10, 5))

        frame = ttk.Frame(self.frame)
        frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(frame, text="Caminho do banco (SQLite):").pack(side="left")
        var = ttk.Entry(frame, width=60)
        var.insert(0, _valor_env("DB_PATH", "triagem.db"))
        var.pack(side="left", fill="x", expand=True, padx=5)
        self.vars["DB_PATH"] = var

        frame2 = ttk.Frame(self.frame)
        frame2.pack(fill="x", padx=10, pady=5)
        ttk.Label(frame2, text="Diretório de PDFs:").pack(side="left")
        var2 = ttk.Entry(frame2, width=60)
        var2.insert(0, _valor_env("PDF_DIR", "pdfs"))
        var2.pack(side="left", fill="x", expand=True, padx=5)
        self.vars["PDF_DIR"] = var2

        ttk.Label(
            self.frame,
            text="OBS: O banco é um arquivo SQLite local. Atualize a configuração se "
                 "mover para outro ambiente.",
            foreground="#b91c1c",
        ).pack(anchor="w", padx=10, pady=(5, 10))

    def salvar(self) -> None:
        _salvar_env({key: var.get().strip() for key, var in self.vars.items()})

    def get_valor_key(self, key: str = "") -> str:
        var = self.vars.get(key)
        return var.get().strip() if var is not None else ""


# ---------------------------------------------------------------------------
# Aba: Operação & Suporte
# ---------------------------------------------------------------------------
class ConfigTabOperacao:
    def __init__(self, notebook: ttk.Notebook, owner: ConfigView) -> None:
        self.owner = owner
        self.frame = ttk.Frame(notebook)

        self.vars = {}
        self._criar_widgets()

    def _criar_widgets(self) -> None:
        ttk.Label(self.frame, text="Operação & Suporte").pack(anchor="w", padx=10, pady=(10, 5))

        # Botões de controle
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill="x", padx=10, pady=5)
        self.btn_iniciar = ttk.Button(btn_frame, text="Iniciar Automação", command=self._cmd_iniciar)
        self.btn_iniciar.pack(side="left", padx=5)
        self.btn_parar = ttk.Button(btn_frame, text="Parar", command=self._cmd_parar)
        self.btn_parar.pack(side="left", padx=5)
        self.btn_reiniciar = ttk.Button(btn_frame, text="Reiniciar", command=self._cmd_reiniciar)
        self.btn_reiniciar.pack(side="left", padx=5)

        # Testes
        btn_teste = ttk.Frame(btn_frame)
        btn_teste.pack(side="right", padx=10)
        self.btn_teste_email = ttk.Button(btn_teste, text="Testar E-mail", command=self._cmd_teste_email)
        self.btn_teste_email.pack(side="left", padx=5)
        self.btn_teste_ia = ttk.Button(btn_teste, text="Testar IA", command=self._cmd_teste_ia)
        self.btn_teste_ia.pack(side="left", padx=5)
        self.btn_teste_db = ttk.Button(btn_teste, text="Testar Banco", command=self._cmd_teste_db)
        self.btn_teste_db.pack(side="left", padx=5)
        self.btn_teste_envio = ttk.Button(btn_teste, text="Testar Envio", command=self._cmd_teste_envio)
        self.btn_teste_envio.pack(side="left", padx=5)

        # Log
        log_frame = ttk.LabelFrame(self.frame, text="Log de Execução")
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=25, width=90, font=("Consolas", 9), state="disabled"
        )
        self.log_text.pack(fill="both", expand=True)

        ttk.Button(log_frame, text="Limpar Log", command=self._cmd_limpar_log).pack(anchor="e", padx=10, pady=(0, 5))

    def _cmd_iniciar(self) -> None:
        self.owner._iniciar_execucao()

    def _cmd_parar(self) -> None:
        self.owner._parar_execucao()

    def _cmd_reiniciar(self) -> None:
        self.owner._reiniciar_automacao()

    def _cmd_teste_email(self) -> None:
        self.owner._teste_email()

    def _cmd_teste_ia(self) -> None:
        self.owner._teste_ia()

    def _cmd_teste_db(self) -> None:
        self.owner._teste_db()

    def _cmd_teste_envio(self) -> None:
        self.owner._teste_envio()

    def _cmd_limpar_log(self) -> None:
        self.owner._limpar_log_e_widget()

    def salvar(self) -> None:
        """A aba de operação não mantém configurações próprias."""
        return

    def get_valor_key(self, key: str = "") -> str:
        var = self.vars.get(key)
        return var.get().strip() if var is not None else ""


# ---------------------------------------------------------------------------
# Aplicação principal
# ---------------------------------------------------------------------------
def main() -> None:
    root = tk.Tk()
    ConfigView(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""Interface gráfica (Tkinter): só desenha e chama o Sistema. As regras ficam nos outros módulos.

Uma janela com quatro abas, as mesmas áreas do terminal:
paciente, painel, especialista e administrador.
"""
import tkinter as tk
from tkinter import messagebox, ttk

from clinica.especialistas.cadastro import CONSULTORIOS
from clinica.modelos import ESPECIALIDADES_ATIVAS, Especialidade, Prioridade
from clinica.painel import formatar_espera
from clinica.sistema import Sistema

INTERVALO_ATUALIZACAO_MS = 2000      # painel e estados se atualizam a cada 2 segundos

FONTE_TITULO = ("Helvetica", 18, "bold")
FONTE_CODIGO = ("Helvetica", 56, "bold")
FONTE_TEXTO = ("Helvetica", 12)
FONTE_PAINEL = ("Helvetica", 15)
FONTE_RELATORIO = ("Courier", 10)

PRIORITARIAS = [p for p in Prioridade if p != Prioridade.NORMAL]


class Dialogos:
    """Caixas de mensagem. Nos testes, uma subclasse troca por respostas prontas."""

    def info(self, texto: str) -> None:
        messagebox.showinfo("Clínica", texto)

    def erro(self, texto: str) -> None:
        messagebox.showerror("Clínica", texto)

    def confirmar(self, texto: str) -> bool:
        return messagebox.askyesno("Clínica", texto)


def _rotulo_especialista(sistema: Sistema, especialidade: Especialidade) -> str:
    if sistema.cadastro.tem_especialista(especialidade):
        return especialidade.value
    return f"{especialidade.value} (sem especialista)"


# --- Aba do paciente --------------------------------------------------------------

class AbaPaciente(ttk.Frame):
    """Escolhe a especialidade e o tipo de senha e mostra a senha retirada."""

    def __init__(self, pai, sistema: Sistema, dialogos: Dialogos):
        super().__init__(pai, padding=16)
        self._sistema = sistema
        self._dialogos = dialogos
        self._especialidade = tk.StringVar()          # guarda o nome do enum escolhido
        self._tipo = tk.StringVar(value="N")
        self._codigo = tk.StringVar(value="---")
        self._detalhes = tk.StringVar(value="Escolha a especialidade e retire a sua senha.")
        self.botoes_especialidade: dict[Especialidade, ttk.Radiobutton] = {}

        ttk.Label(self, text="Retirar senha", font=FONTE_TITULO).grid(
            row=0, column=0, columnspan=2, sticky="w")

        quadro = ttk.LabelFrame(self, text="1. Especialidade", padding=12)
        quadro.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=12)
        for linha, especialidade in enumerate(ESPECIALIDADES_ATIVAS):
            botao = ttk.Radiobutton(quadro, text=especialidade.value,
                                    value=especialidade.name, variable=self._especialidade)
            botao.grid(row=linha, column=0, sticky="w", pady=4)
            self.botoes_especialidade[especialidade] = botao

        quadro = ttk.LabelFrame(self, text="2. Tipo de senha", padding=12)
        quadro.grid(row=1, column=1, sticky="nsew", pady=12)
        ttk.Radiobutton(quadro, text="Normal (N)", value="N", variable=self._tipo,
                        command=self._atualizar_tipo).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Radiobutton(quadro, text="Prioritária (P)", value="P", variable=self._tipo,
                        command=self._atualizar_tipo).grid(row=1, column=0, sticky="w", pady=4)
        self.combo_prioridade = ttk.Combobox(
            quadro, state="disabled", width=26,
            values=[p.descricao for p in PRIORITARIAS])
        self.combo_prioridade.grid(row=2, column=0, sticky="w", pady=(8, 0))

        self.botao_retirar = ttk.Button(self, text="Retirar senha", command=self.retirar)
        self.botao_retirar.grid(row=2, column=0, columnspan=2, sticky="ew", ipady=8)

        resultado = ttk.LabelFrame(self, text="Sua senha", padding=12)
        resultado.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        ttk.Label(resultado, textvariable=self._codigo, font=FONTE_CODIGO,
                  anchor="center").pack(fill="x")
        ttk.Label(resultado, textvariable=self._detalhes, font=FONTE_TEXTO,
                  anchor="center", justify="center").pack(fill="x")

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _atualizar_tipo(self) -> None:
        self.combo_prioridade.configure(state="readonly" if self._tipo.get() == "P" else "disabled")
        if self._tipo.get() == "P" and self.combo_prioridade.current() == -1:
            self.combo_prioridade.current(0)

    def atualizar(self) -> None:
        """Desabilita as especialidades sem especialista (RN06)."""
        for especialidade, botao in self.botoes_especialidade.items():
            tem = self._sistema.cadastro.tem_especialista(especialidade)
            botao.configure(text=_rotulo_especialista(self._sistema, especialidade),
                            state="normal" if tem else "disabled")
            if not tem and self._especialidade.get() == especialidade.name:
                self._especialidade.set("")

    def retirar(self) -> None:
        nome = self._especialidade.get()
        if not nome:
            self._dialogos.erro("Escolha uma especialidade.")
            return
        especialidade = Especialidade[nome]

        prioridade = Prioridade.NORMAL
        if self._tipo.get() == "P":
            if self.combo_prioridade.current() == -1:
                self._dialogos.erro("Escolha o tipo de prioridade.")
                return
            prioridade = PRIORITARIAS[self.combo_prioridade.current()]

        try:
            senha = self._sistema.emitir_senha(especialidade, prioridade)
        except ValueError as erro:
            self._dialogos.erro(str(erro))
            return

        gerenciador = self._sistema.gerenciador
        a_frente = gerenciador.pessoas_a_frente(especialidade, senha.numero)
        espera = gerenciador.tempo_espera_senha(especialidade, senha.numero)
        self._codigo.set(senha.codigo)
        self._detalhes.set(f"{especialidade.value}\nPessoas à frente: {a_frente}\n"
                           f"Espera estimada: {formatar_espera(espera)} (sem garantia de tempo)")


# --- Aba do painel ----------------------------------------------------------------

class AbaPainel(ttk.Frame):
    """Última chamada e situação completa da fila de cada especialidade."""

    def __init__(self, pai, sistema: Sistema):
        super().__init__(pai, padding=16)
        self._sistema = sistema

        estilo = ttk.Style(self)
        estilo.configure("Painel.Treeview", font=("Helvetica", 10), rowheight=42)
        estilo.configure("Painel.Treeview.Heading", font=("Helvetica", 10, "bold"))

        ttk.Label(self, text="Painel de atendimento", font=FONTE_TITULO).pack(anchor="w")
        self.tabela = ttk.Treeview(
            self, style="Painel.Treeview", height=len(ESPECIALIDADES_ATIVAS), selectmode="none",
            columns=("especialidade", "senha", "categoria", "consultorio", "quantidade",
                     "aguardando", "espera"), show="headings")
        for coluna, titulo, largura in (("especialidade", "Especialidade", 145),
                                        ("senha", "Última", 70),
                                        ("categoria", "Categoria", 145),
                                        ("consultorio", "Consultório", 80),
                                        ("quantidade", "Aguardando", 80),
                                        ("aguardando", "Senhas em espera", 220),
                                        ("espera", "Espera", 100)):
            self.tabela.heading(coluna, text=titulo)
            self.tabela.column(coluna, width=largura, anchor="w" if coluna == "especialidade" else "center")
        self.tabela.pack(fill="both", expand=True, pady=12)
        barra_horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.tabela.xview)
        self.tabela.configure(xscrollcommand=barra_horizontal.set)
        barra_horizontal.pack(fill="x")
        ttk.Label(self, text="As senhas em espera aparecem na ordem prevista de chamada. "
                            "A espera é uma estimativa, sem garantia de tempo.",
                  font=FONTE_TEXTO, wraplength=820, justify="left").pack(anchor="w")

    def atualizar(self) -> None:
        self.tabela.delete(*self.tabela.get_children())
        for linha in self._sistema.painel.linhas():
            self.tabela.insert("", "end", values=(
                linha.especialidade.value,
                linha.senha or "-",
                linha.categoria or "-",
                linha.consultorio or "-",
                linha.quantidade_aguardando,
                ", ".join(linha.senhas_aguardando) or "-",
                formatar_espera(linha.espera_estimada_min)))


# --- Aba do especialista ----------------------------------------------------------

class AbaEspecialista(ttk.Frame):
    """O especialista escolhe o consultório, chama a próxima senha e finaliza o atendimento."""

    def __init__(self, pai, sistema: Sistema, dialogos: Dialogos, ao_mudar):
        super().__init__(pai, padding=16)
        self._sistema = sistema
        self._dialogos = dialogos
        self._ao_mudar = ao_mudar          # avisa a janela para atualizar as outras abas
        self._quem = tk.StringVar()
        self._situacao = tk.StringVar()

        ttk.Label(self, text="Área do especialista", font=FONTE_TITULO).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self, text="Consultório:", font=FONTE_TEXTO).grid(row=1, column=0, sticky="w", pady=16)
        self.combo_consultorio = ttk.Combobox(
            self, state="readonly", width=5, values=[str(n) for n in sorted(CONSULTORIOS)])
        self.combo_consultorio.grid(row=1, column=1, sticky="w", padx=8)
        self.combo_consultorio.bind("<<ComboboxSelected>>", lambda _evento: self.atualizar())

        ttk.Label(self, textvariable=self._quem, font=("Helvetica", 14, "bold")).grid(
            row=2, column=0, columnspan=3, sticky="w")
        ttk.Label(self, textvariable=self._situacao, font=FONTE_TEXTO).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(4, 16))

        self.botao_chamar = ttk.Button(self, text="Chamar próxima senha", command=self.chamar)
        self.botao_chamar.grid(row=4, column=0, columnspan=2, sticky="ew", ipady=8, padx=(0, 8))
        self.botao_finalizar = ttk.Button(self, text="Finalizar atendimento", command=self.finalizar)
        self.botao_finalizar.grid(row=4, column=2, sticky="ew", ipady=8)
        self.columnconfigure(2, weight=1)
        self.atualizar()

    def _consultorio(self) -> int | None:
        texto = self.combo_consultorio.get()
        return int(texto) if texto else None

    def atualizar(self) -> None:
        consultorio = self._consultorio()
        pode_chamar = pode_finalizar = False
        if consultorio is None:
            self._quem.set("Escolha o seu consultório.")
            self._situacao.set("")
        else:
            especialista = self._sistema.cadastro.buscar_por_consultorio(consultorio)
            if especialista is None:
                self._quem.set("Nenhum especialista cadastrado neste consultório.")
                self._situacao.set("")
            else:
                self._quem.set(f"{especialista.nome} - {especialista.especialidade.value}")
                atendimento = self._sistema.gerenciador.atendimento_em(consultorio)
                if atendimento is None:
                    self._situacao.set("Consultório livre.")
                    pode_chamar = not self._sistema.gerenciador.dia_encerrado
                else:
                    self._situacao.set(f"Em atendimento: senha {atendimento.codigo}")
                    pode_finalizar = True
        self.botao_chamar.configure(state="normal" if pode_chamar else "disabled")
        self.botao_finalizar.configure(state="normal" if pode_finalizar else "disabled")

    def chamar(self) -> None:
        try:
            senha = self._sistema.chamar_proxima(self._consultorio())
        except ValueError as erro:
            self._dialogos.erro(str(erro))
            return
        if senha is None:
            self._dialogos.info("Não há senhas aguardando nesta especialidade.")
        self._ao_mudar()

    def finalizar(self) -> None:
        try:
            self._sistema.finalizar_atendimento(self._consultorio())
        except ValueError as erro:
            self._dialogos.erro(str(erro))
            return
        self._ao_mudar()


# --- Aba do administrador ---------------------------------------------------------

class AbaAdministrador(ttk.Frame):
    """Login (ou primeiro acesso) e, depois, cadastro, relatório e encerramento do dia."""

    def __init__(self, pai, sistema: Sistema, dialogos: Dialogos, ao_mudar):
        super().__init__(pai, padding=16)
        self._sistema = sistema
        self._dialogos = dialogos
        self._ao_mudar = ao_mudar
        self._usuario = tk.StringVar()
        self._senha = tk.StringVar()
        self._repita = tk.StringVar()
        self._nome = tk.StringVar()
        self._titulo_login = tk.StringVar()
        self._texto_botao_login = tk.StringVar()

        self._quadro_login = ttk.Frame(self)
        self._quadro_area = ttk.Frame(self)
        self._montar_login()
        self._montar_area()
        self.atualizar()

    # Login ---------------------------------------------------------------------

    def _montar_login(self) -> None:
        q = self._quadro_login
        ttk.Label(q, textvariable=self._titulo_login, font=FONTE_TITULO).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(q, text="Usuário:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(q, textvariable=self._usuario, width=28).grid(row=1, column=1, pady=4)
        ttk.Label(q, text="Senha:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(q, textvariable=self._senha, show="*", width=28).grid(row=2, column=1, pady=4)
        self._rotulo_repita = ttk.Label(q, text="Repita a senha:")
        self._campo_repita = ttk.Entry(q, textvariable=self._repita, show="*", width=28)
        self._rotulo_repita.grid(row=3, column=0, sticky="w", pady=4)
        self._campo_repita.grid(row=3, column=1, pady=4)
        self.botao_login = ttk.Button(q, textvariable=self._texto_botao_login, command=self.entrar)
        self.botao_login.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0), ipady=4)

    def entrar(self) -> None:
        usuario, senha = self._usuario.get(), self._senha.get()
        if not self._sistema.tem_administrador:                 # primeiro acesso
            if senha != self._repita.get():
                self._dialogos.erro("As senhas não conferem.")
                return
            try:
                self._sistema.criar_administrador(usuario, senha)
            except ValueError as erro:
                self._dialogos.erro(str(erro))
                return
        elif not self._sistema.entrar_como_admin(usuario, senha):
            self._dialogos.erro("Usuário ou senha incorretos.")
            return
        self._senha.set("")
        self._repita.set("")
        self.atualizar()

    # Área do administrador -----------------------------------------------------

    def _montar_area(self) -> None:
        q = self._quadro_area
        ttk.Label(q, text="Área do administrador", font=FONTE_TITULO).grid(
            row=0, column=0, columnspan=2, sticky="w")

        cadastro = ttk.LabelFrame(q, text="Cadastrar especialista", padding=10)
        cadastro.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=10)
        ttk.Label(cadastro, text="Nome:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(cadastro, textvariable=self._nome, width=24).grid(row=0, column=1, pady=3)
        ttk.Label(cadastro, text="Especialidade:").grid(row=1, column=0, sticky="w", pady=3)
        self.combo_especialidade = ttk.Combobox(
            cadastro, state="readonly", width=21, values=[e.value for e in ESPECIALIDADES_ATIVAS])
        self.combo_especialidade.grid(row=1, column=1, pady=3)
        ttk.Label(cadastro, text="Consultório:").grid(row=2, column=0, sticky="w", pady=3)
        self.combo_consultorio = ttk.Combobox(
            cadastro, state="readonly", width=21, values=[str(n) for n in sorted(CONSULTORIOS)])
        self.combo_consultorio.grid(row=2, column=1, pady=3)
        ttk.Button(cadastro, text="Cadastrar", command=self.cadastrar).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        lista = ttk.LabelFrame(q, text="Especialistas cadastrados", padding=10)
        lista.grid(row=1, column=1, sticky="nsew", pady=10)
        self.tabela = ttk.Treeview(lista, height=5, show="headings", selectmode="none",
                                   columns=("consultorio", "nome", "especialidade"))
        for coluna, titulo, largura in (("consultorio", "Consultório", 90),
                                        ("nome", "Nome", 150), ("especialidade", "Especialidade", 130)):
            self.tabela.heading(coluna, text=titulo)
            self.tabela.column(coluna, width=largura)
        self.tabela.pack(fill="both", expand=True)

        botoes = ttk.Frame(q)
        botoes.grid(row=2, column=0, columnspan=2, sticky="ew")
        ttk.Button(botoes, text="Ver relatório do dia", command=self.ver_relatorio).pack(side="left", padx=(0, 8))
        ttk.Button(botoes, text="Encerrar o dia e gerar relatório", command=self.encerrar_dia).pack(side="left", padx=(0, 8))
        ttk.Button(botoes, text="Iniciar novo dia", command=self.iniciar_novo_dia).pack(side="left", padx=(0, 8))
        ttk.Button(botoes, text="Sair da área", command=self.sair).pack(side="right")

        self.texto_relatorio = tk.Text(q, height=12, font=FONTE_RELATORIO, state="disabled", wrap="none")
        self.texto_relatorio.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        q.columnconfigure(0, weight=1)
        q.columnconfigure(1, weight=1)
        q.rowconfigure(3, weight=1)

    def cadastrar(self) -> None:
        indice = self.combo_especialidade.current()
        if indice == -1 or self.combo_consultorio.current() == -1:
            self._dialogos.erro("Escolha a especialidade e o consultório.")
            return
        try:
            especialista = self._sistema.cadastrar_especialista(
                                        self._nome.get(), ESPECIALIDADES_ATIVAS[indice], int(self.combo_consultorio.get()))
        except (ValueError, PermissionError) as erro:
            self._dialogos.erro(str(erro))
            return
        self._nome.set("")
        self._dialogos.info(f"Cadastrado: {especialista.nome} - {especialista.especialidade.value}, "
                            f"consultório {especialista.consultorio}.")
        self._ao_mudar()

    def _mostrar_relatorio(self) -> None:
        texto = self._sistema.relatorio_do_dia()
        self.texto_relatorio.configure(state="normal")
        self.texto_relatorio.delete("1.0", "end")
        self.texto_relatorio.insert("1.0", texto)
        self.texto_relatorio.configure(state="disabled")

    def ver_relatorio(self) -> None:
        try:
            self._mostrar_relatorio()
        except PermissionError as erro:
            self._dialogos.erro(str(erro))

    def encerrar_dia(self) -> None:
        if not self._dialogos.confirmar("Encerrar o dia marca como não atendidas as senhas que "
                                        "ainda aguardam. Confirmar?"):
            return
        try:
            caminho = self._sistema.encerrar_dia()
        except (ValueError, PermissionError) as erro:
            self._dialogos.erro(str(erro))
            return
        self._mostrar_relatorio()
        self._dialogos.info(f"Dia encerrado. Relatório salvo em {caminho}.")
        self._ao_mudar()

    def iniciar_novo_dia(self) -> None:
        try:
            self._sistema.iniciar_novo_dia()
        except (ValueError, PermissionError) as erro:
            self._dialogos.erro(str(erro))
            return
        self._dialogos.info("Novo dia iniciado.")
        self._ao_mudar()

    def sair(self) -> None:
        self._sistema.sair_do_admin()
        self.texto_relatorio.configure(state="normal")
        self.texto_relatorio.delete("1.0", "end")
        self.texto_relatorio.configure(state="disabled")
        self.atualizar()

    # Estado --------------------------------------------------------------------

    def atualizar(self) -> None:
        if self._sistema.admin_logado:
            self._quadro_login.pack_forget()
            self._quadro_area.pack(fill="both", expand=True)
            self.tabela.delete(*self.tabela.get_children())
            for e in sorted(self._sistema.cadastro.listar(), key=lambda e: e.consultorio):
                self.tabela.insert("", "end", values=(e.consultorio, e.nome, e.especialidade.value))
            return

        self._quadro_area.pack_forget()
        self._quadro_login.pack(anchor="center", pady=30)
        if self._sistema.tem_administrador:
            self._titulo_login.set("Entrar como administrador")
            self._texto_botao_login.set("Entrar")
            self._rotulo_repita.grid_remove()
            self._campo_repita.grid_remove()
        else:
            self._titulo_login.set("Primeiro acesso: crie a conta do administrador")
            self._texto_botao_login.set("Criar conta")
            self._rotulo_repita.grid()
            self._campo_repita.grid()


# --- Janela principal -------------------------------------------------------------

class Janela(tk.Tk):
    def __init__(self, sistema: Sistema, dialogos: Dialogos | None = None):
        super().__init__()
        self._sistema = sistema
        dialogos = dialogos or Dialogos()
        self.title("Clínica - Sistema de Senhas")
        self.geometry("920x660")
        self.minsize(860, 600)

        self._status = tk.StringVar()
        if sistema.dias_fechados_ao_iniciar:
            dias = ", ".join(f"{dia:%d/%m/%Y}" for dia in sistema.dias_fechados_ao_iniciar)
            self._status.set(f"Relatório gerado ao iniciar para o(s) dia(s) que ficaram abertos: {dias}.")

        self._abas = ttk.Notebook(self)
        self.aba_paciente = AbaPaciente(self._abas, sistema, dialogos)
        self.aba_painel = AbaPainel(self._abas, sistema)
        self.aba_especialista = AbaEspecialista(self._abas, sistema, dialogos, self.atualizar_tudo)
        self.aba_administrador = AbaAdministrador(self._abas, sistema, dialogos, self.atualizar_tudo)
        for aba, titulo in ((self.aba_paciente, "Retirar senha"), (self.aba_painel, "Painel"),
                            (self.aba_especialista, "Especialista"),
                            (self.aba_administrador, "Administrador")):
            self._abas.add(aba, text=titulo)
        self._abas.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        ttk.Label(self, textvariable=self._status, anchor="w").pack(fill="x", padx=10, pady=4)
        self._abas.bind("<<NotebookTabChanged>>", lambda _evento: self.atualizar_tudo())

        self.atualizar_tudo()
        self.after(INTERVALO_ATUALIZACAO_MS, self._ciclo)

    def atualizar_tudo(self) -> None:
        for aba in (self.aba_paciente, self.aba_painel, self.aba_especialista, self.aba_administrador):
            aba.atualizar()

    def _ciclo(self) -> None:
        """Roda de tempos em tempos: vira o dia se for preciso e atualiza as telas."""
        caminho = self._sistema.verificar_virada_do_dia()
        if caminho is not None:
            self._status.set(f"O dia virou: o dia anterior foi encerrado e o relatório foi salvo em {caminho}.")
        self.atualizar_tudo()
        self.after(INTERVALO_ATUALIZACAO_MS, self._ciclo)

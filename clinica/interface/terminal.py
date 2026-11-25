"""Interface de terminal: só menus e mensagens. As regras ficam no Sistema.

`entrada`, `entrada_senha` e `saida` podem ser trocadas, o que permite testar os
menus sem digitar nada de verdade.
"""
import getpass
from collections.abc import Callable
from datetime import date

from clinica.especialistas.cadastro import CONSULTORIOS
from clinica.modelos import ESPECIALIDADES_ATIVAS, Especialidade, Prioridade
from clinica.painel import formatar_espera
from clinica.sistema import Sistema

TENTATIVAS_LOGIN = 3


class Terminal:
    def __init__(self, sistema: Sistema,
                 entrada: Callable[[str], str] = input,
                 entrada_senha: Callable[[str], str] = getpass.getpass,
                 saida: Callable[[str], None] = print):
        self._sistema = sistema
        self._entrada = entrada
        self._entrada_senha = entrada_senha
        self._saida = saida

    # --- Laço principal ----------------------------------------------------------

    def executar(self) -> None:
        try:
            for dia in self._sistema.dias_fechados_ao_iniciar:
                self._saida(f"Relatório de {dia:%d/%m/%Y} gerado automaticamente "
                            "(o dia anterior não tinha sido encerrado).")
            while True:
                self._avisar_virada_do_dia()
                self._saida("\n=== CLÍNICA - SISTEMA DE SENHAS ===")
                opcao = self._menu(["Retirar senha", "Painel de atendimento",
                                    "Área do especialista", "Área do administrador"],
                                   sair="Sair")
                if opcao == 0:
                    break
                {1: self._retirar_senha,
                 2: self._mostrar_painel,
                 3: self._area_especialista,
                 4: self._area_administrador}[opcao]()
        except (EOFError, KeyboardInterrupt):
            self._saida("")
        self._saida("Sistema encerrado.")

    def _avisar_virada_do_dia(self) -> None:
        caminho = self._sistema.verificar_virada_do_dia()
        if caminho is not None:
            self._saida(f"\nO dia virou: o dia anterior foi encerrado e o relatório "
                        f"foi salvo em {caminho}.")

    # --- Entrada de dados --------------------------------------------------------

    def _ler_opcao(self, texto: str, minimo: int, maximo: int) -> int:
        while True:
            resposta = self._entrada(texto).strip()
            if resposta.isdigit() and minimo <= int(resposta) <= maximo:
                return int(resposta)
            self._saida(f"Opção inválida. Digite um número de {minimo} a {maximo}.")

    def _menu(self, opcoes: list[str], sair: str = "Voltar") -> int:
        for numero, opcao in enumerate(opcoes, start=1):
            self._saida(f"  {numero}) {opcao}")
        self._saida(f"  0) {sair}")
        return self._ler_opcao("Opção: ", 0, len(opcoes))

    def _escolher_especialidade(self, avisar_sem_especialista: bool = False) -> Especialidade | None:
        especialidades = list(ESPECIALIDADES_ATIVAS)
        self._saida("\nEspecialidades:")
        for numero, especialidade in enumerate(especialidades, start=1):
            aviso = ""
            if avisar_sem_especialista and not self._sistema.cadastro.tem_especialista(especialidade):
                aviso = "  (sem especialista no momento)"
            self._saida(f"  {numero}) {especialidade.value}{aviso}")
        self._saida("  0) Voltar")
        escolha = self._ler_opcao("Especialidade: ", 0, len(especialidades))
        return especialidades[escolha - 1] if escolha else None

    # --- Paciente ----------------------------------------------------------------

    def _retirar_senha(self) -> None:
        especialidade = self._escolher_especialidade(avisar_sem_especialista=True)
        if especialidade is None:
            return

        prioridade = Prioridade.NORMAL
        if self._ler_tipo_de_senha() == "P":
            prioridade = self._escolher_prioridade()
            if prioridade is None:
                return

        try:
            senha = self._sistema.emitir_senha(especialidade, prioridade)
        except ValueError as erro:
            self._saida(f"Não foi possível emitir a senha: {erro}")
            return

        gerenciador = self._sistema.gerenciador
        a_frente = gerenciador.pessoas_a_frente(especialidade, senha.numero)
        espera = gerenciador.tempo_espera_senha(especialidade, senha.numero)
        self._saida(f"\n>>> Sua senha: {senha.codigo} ({especialidade.value})")
        self._saida(f"    Pessoas à frente: {a_frente}")
        self._saida(f"    Espera estimada: {formatar_espera(espera)} (sem garantia de tempo)")

    def _ler_tipo_de_senha(self) -> str:
        while True:
            resposta = self._entrada("Tipo de senha - Normal (N) ou Prioritária (P): ").strip().upper()
            if resposta in ("N", "P"):
                return resposta
            self._saida("Digite N para normal ou P para prioritária.")

    def _escolher_prioridade(self) -> Prioridade | None:
        prioritarias = [p for p in Prioridade if p != Prioridade.NORMAL]
        self._saida("\nTipo de prioridade:")
        for prioridade in prioritarias:
            self._saida(f"  {prioridade.value}) {prioridade.descricao}")
        self._saida("  0) Voltar")
        escolha = self._ler_opcao("Prioridade: ", 0, len(prioritarias))
        return Prioridade(escolha) if escolha else None

    # --- Painel ------------------------------------------------------------------

    def _mostrar_painel(self) -> None:
        self._saida("\n" + self._sistema.painel.texto())

    # --- Especialista (RF08) -----------------------------------------------------

    def _area_especialista(self) -> None:
        consultorio = self._ler_opcao("Número do seu consultório (0 para voltar): ",
                                      0, max(CONSULTORIOS))
        if consultorio == 0:
            return
        especialista = self._sistema.cadastro.buscar_por_consultorio(consultorio)
        if especialista is None:
            self._saida(f"Não há especialista cadastrado no consultório {consultorio}.")
            return

        while True:
            self._saida(f"\nConsultório {consultorio} - {especialista.nome} "
                        f"({especialista.especialidade.value})")
            opcao = self._menu(["Chamar próxima senha", "Finalizar atendimento"])
            if opcao == 0:
                return
            try:
                if opcao == 1:
                    senha = self._sistema.chamar_proxima(consultorio)
                    if senha is None:
                        self._saida("Não há senhas aguardando nesta especialidade.")
                    else:
                        self._saida(f"Chamando a senha {senha.codigo} no consultório {consultorio}.")
                else:
                    senha = self._sistema.finalizar_atendimento(consultorio)
                    self._saida(f"Atendimento da senha {senha.codigo} finalizado.")
            except ValueError as erro:
                self._saida(f"Erro: {erro}")

    # --- Administrador (RF01, RF09 a RF12) ---------------------------------------

    def _area_administrador(self) -> None:
        if not self._entrar_como_admin():
            return
        try:
            while True:
                self._saida("\n--- Área do administrador ---")
                opcao = self._menu(["Cadastrar especialista", "Listar especialistas",
                                    "Ver relatório do dia", "Encerrar o dia e gerar relatório",
                                    "Iniciar novo dia", "Consultar relatório por data"],
                                   sair="Sair da área")
                if opcao == 0:
                    return
                {1: self._cadastrar_especialista,
                 2: self._listar_especialistas,
                 3: self._ver_relatorio,
                 4: self._encerrar_dia,
                 5: self._iniciar_novo_dia,
                 6: self._consultar_relatorio_por_data}[opcao]()
        finally:
            self._sistema.sair_do_admin()

    def _entrar_como_admin(self) -> bool:
        if not self._sistema.tem_administrador:
            return self._criar_administrador()
        for _ in range(TENTATIVAS_LOGIN):
            usuario = self._entrada("Usuário: ")
            senha = self._entrada_senha("Senha: ")
            if self._sistema.entrar_como_admin(usuario, senha):
                return True
            self._saida("Usuário ou senha incorretos.")
        self._saida("Número de tentativas excedido.")
        return False

    def _criar_administrador(self) -> bool:
        self._saida("\nPrimeiro acesso: crie a conta do administrador.")
        usuario = self._entrada("Usuário: ")
        senha = self._entrada_senha("Senha: ")
        if self._entrada_senha("Repita a senha: ") != senha:
            self._saida("As senhas não conferem.")
            return False
        try:
            self._sistema.criar_administrador(usuario, senha)
        except ValueError as erro:
            self._saida(f"Não foi possível criar a conta: {erro}")
            return False
        self._saida("Administrador criado.")
        return True

    def _cadastrar_especialista(self) -> None:
        nome = self._entrada("Nome do especialista: ")
        especialidade = self._escolher_especialidade()
        if especialidade is None:
            return
        consultorio = self._ler_opcao(f"Consultório ({min(CONSULTORIOS)} a {max(CONSULTORIOS)}): ",
                                      min(CONSULTORIOS), max(CONSULTORIOS))
        try:
            especialista = self._sistema.cadastrar_especialista(nome, especialidade, consultorio)
        except (ValueError, PermissionError) as erro:
            self._saida(f"Não foi possível cadastrar: {erro}")
            return
        self._saida(f"Cadastrado: {especialista.nome} - {especialista.especialidade.value}, "
                    f"consultório {especialista.consultorio}.")

    def _listar_especialistas(self) -> None:
        especialistas = sorted(self._sistema.cadastro.listar(), key=lambda e: e.consultorio)
        if not especialistas:
            self._saida("Nenhum especialista cadastrado.")
            return
        for e in especialistas:
            self._saida(f"  Consultório {e.consultorio:>2} - {e.nome} ({e.especialidade.value})")

    def _ver_relatorio(self) -> None:
        self._saida("\n" + self._sistema.relatorio_do_dia())

    def _consultar_relatorio_por_data(self) -> None:
        while True:
            texto = self._entrada("Data do relatório (AAAA-MM-DD): ").strip()
            try:
                dia = date.fromisoformat(texto)
                break
            except ValueError:
                self._saida("Data inválida. Use o formato AAAA-MM-DD.")

        self._saida("\n" + self._sistema.relatorio_do_dia(dia))
        formato = self._menu(["Exportar CSV", "Exportar Excel", "Não exportar"])
        if formato == 0 or formato == 3:
            return
        try:
            caminho = (self._sistema.exportar_relatorio_csv(dia) if formato == 1
                       else self._sistema.exportar_relatorio_excel(dia))
        except OSError as erro:
            self._saida(f"Não foi possível exportar o relatório: {erro}")
            return
        self._saida(f"Relatório exportado para {caminho}.")

    def _encerrar_dia(self) -> None:
        self._saida("Encerrar o dia marca como não atendidas as senhas que ainda aguardam.")
        if self._entrada("Confirmar (s/n)? ").strip().lower() != "s":
            self._saida("Operação cancelada.")
            return
        try:
            caminho = self._sistema.encerrar_dia()
        except ValueError as erro:
            self._saida(f"Erro: {erro}")
            return
        self._saida(f"Dia encerrado. Relatório salvo em {caminho}.\n")
        self._saida(self._sistema.relatorio_do_dia())

    def _iniciar_novo_dia(self) -> None:
        try:
            self._sistema.iniciar_novo_dia()
        except ValueError as erro:
            self._saida(f"Erro: {erro}")
            return
        self._saida("Novo dia iniciado.")

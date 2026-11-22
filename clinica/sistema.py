"""Sistema: junta cadastro, filas, painel, banco e relatório numa única porta de entrada.

O terminal e, depois, a interface gráfica falam só com esta classe. As regras continuam
nos módulos de baixo; aqui ficam a ordem de abertura do dia, o acesso restrito do
administrador e a gravação no SQLite.
"""
from collections.abc import Callable
from datetime import date
from pathlib import Path

from clinica.especialistas import Administrador, CadastroEspecialistas
from clinica.filas import GerenciadorFilas
from clinica.modelos import Especialidade, Especialista, Prioridade, Senha, StatusSenha
from clinica.painel import Painel
from clinica.relatorio import Relatorio, Repositorio
from clinica.relatorio.relatorio import PASTA_PADRAO


class Sistema:
    """Ponto único de acesso às funções da clínica."""

    def __init__(self, repositorio: Repositorio | None = None,
                 pasta_relatorios: str | Path = PASTA_PADRAO,
                 hoje: Callable[[], date] = date.today):
        """`hoje` existe para os testes poderem simular a virada do dia."""
        self._repositorio = repositorio or Repositorio()
        self._pasta_relatorios = Path(pasta_relatorios)
        self._hoje = hoje
        self._admin_logado = False

        # 1) Cadastro e administrador voltam do banco.
        self.cadastro = CadastroEspecialistas()
        for e in self._repositorio.listar_especialistas():
            self.cadastro.cadastrar(e.nome, e.especialidade, e.consultorio)
        self._administrador = self._repositorio.carregar_administrador()

        # 2) Dias anteriores que ficaram abertos são fechados e ganham relatório.
        self.relatorio = Relatorio(self._repositorio)
        self.dias_fechados_ao_iniciar = self._fechar_dias_anteriores()

        # 3) As filas de hoje voltam do banco, e daqui em diante tudo é gravado.
        self.gerenciador = GerenciadorFilas(self.cadastro, ao_mudar=self._repositorio.salvar_senha)
        self._dia_aberto = self._hoje()
        self.gerenciador.restaurar_dia(self._repositorio.listar_senhas(self._dia_aberto))
        self.painel = Painel(self.gerenciador)

    # --- Dia ---------------------------------------------------------------------

    def _caminho_relatorio(self, dia: date) -> Path:
        return self._pasta_relatorios / f"relatorio_{dia.isoformat()}.txt"

    def _fechar_dias_anteriores(self) -> list[date]:
        """Fecha os dias passados que ficaram abertos (programa fechado antes do encerramento).

        Quem aguardava vira não atendido (as senhas não passam para o dia seguinte) e quem
        estava em atendimento conta como atendido, sem hora de finalização.
        """
        fechados = []
        for dia in self._repositorio.dias_com_senhas():
            if dia >= self._hoje() or self._caminho_relatorio(dia).exists():
                continue
            for senha in self._repositorio.listar_senhas(dia):
                if senha.status == StatusSenha.AGUARDANDO:
                    senha.status = StatusSenha.NAO_ATENDIDA
                elif senha.status == StatusSenha.EM_ATENDIMENTO:
                    senha.status = StatusSenha.FINALIZADA
                else:
                    continue
                self._repositorio.salvar_senha(senha)
            self.relatorio.salvar_arquivo(dia, self._pasta_relatorios)
            fechados.append(dia)
        return fechados

    def verificar_virada_do_dia(self) -> Path | None:
        """Se a data mudou com o sistema aberto, encerra o dia anterior e abre o novo.

        Devolve o caminho do relatório gerado, ou None se nada precisou ser feito.
        Não exige administrador, porque é automático. O terminal chama a cada menu;
        a interface gráfica pode chamar de tempos em tempos.
        """
        hoje = self._hoje()
        if hoje == self._dia_aberto:
            return None
        anterior, self._dia_aberto = self._dia_aberto, hoje
        if self.gerenciador.dia_encerrado:     # o administrador já encerrou e gerou o relatório
            self.gerenciador.iniciar_novo_dia()
            return None
        self.gerenciador.encerrar_dia()
        caminho = self.relatorio.salvar_arquivo(anterior, self._pasta_relatorios)
        self.gerenciador.iniciar_novo_dia()
        return caminho

    # --- Administrador (RF09) ----------------------------------------------------

    @property
    def tem_administrador(self) -> bool:
        return self._administrador is not None

    @property
    def admin_logado(self) -> bool:
        return self._admin_logado

    def criar_administrador(self, usuario: str, senha: str) -> None:
        """Primeiro acesso: cria a conta e já entra com ela."""
        if self._administrador is not None:
            raise ValueError("Já existe um administrador cadastrado.")
        administrador = Administrador(usuario, senha)     # ValueError se vazio
        self._repositorio.salvar_administrador(administrador)
        self._administrador = administrador
        self._admin_logado = True

    def entrar_como_admin(self, usuario: str, senha: str) -> bool:
        if self._administrador is None:
            raise ValueError("Nenhum administrador cadastrado.")
        self._admin_logado = self._administrador.autenticar(usuario, senha)
        return self._admin_logado

    def sair_do_admin(self) -> None:
        self._admin_logado = False

    def _exigir_admin(self) -> None:
        if not self._admin_logado:
            raise PermissionError("Acesso restrito ao administrador.")

    # --- Ações do administrador --------------------------------------------------

    def cadastrar_especialista(self, nome: str, especialidade: Especialidade,
                               consultorio: int) -> Especialista:
        """RF01. Valida as regras do cadastro e grava no banco."""
        self._exigir_admin()
        especialista = self.cadastro.cadastrar(nome, especialidade, consultorio)
        self._repositorio.salvar_especialista(especialista)
        return especialista

    def relatorio_do_dia(self, dia: date | None = None) -> str:
        """RF12. Texto do relatório de hoje (ou do dia pedido), mesmo com o dia em andamento."""
        self._exigir_admin()
        return self.relatorio.gerar_texto(dia or self._dia_aberto)

    def exportar_relatorio_csv(self, dia: date) -> Path:
        """Exporta as senhas do dia em CSV, na pasta dos relatórios, e devolve o caminho."""
        self._exigir_admin()
        return self.relatorio.salvar_csv(dia, self._pasta_relatorios)

    def exportar_relatorio_excel(self, dia: date) -> Path:
        """Exporta as senhas do dia em Excel (.xlsx), na pasta dos relatórios, e devolve o caminho."""
        self._exigir_admin()
        return self.relatorio.salvar_excel(dia, self._pasta_relatorios)

    def encerrar_dia(self) -> Path:
        """Encerra o dia, gera o relatório (RF10) e devolve o caminho do arquivo."""
        self._exigir_admin()
        self.gerenciador.encerrar_dia()               # ValueError se já estava encerrado
        return self.relatorio.salvar_arquivo(self._dia_aberto, self._pasta_relatorios)

    def iniciar_novo_dia(self) -> None:
        self._exigir_admin()
        self.gerenciador.iniciar_novo_dia()

    # --- Paciente e especialista (sem login) -------------------------------------

    def emitir_senha(self, especialidade: Especialidade,
                     prioridade: Prioridade = Prioridade.NORMAL) -> Senha:
        return self.gerenciador.emitir_senha(especialidade, prioridade)

    def chamar_proxima(self, consultorio: int) -> Senha | None:
        return self.gerenciador.chamar_proxima(consultorio)

    def finalizar_atendimento(self, consultorio: int) -> Senha:
        return self.gerenciador.finalizar_atendimento(consultorio)

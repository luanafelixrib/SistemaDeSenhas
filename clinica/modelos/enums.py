"""Enums do sistema: especialidades, prioridades e status das senhas."""

from enum import Enum


class Especialidade(Enum):
    """Especialidades médicas disponíveis na clínica."""
    CLINICA_GERAL = "Clínica Geral"
    PEDIATRIA = "Pediatria"
    GINECOLOGIA = "Ginecologia"
    CARDIOLOGIA = "Cardiologia"


class Prioridade(Enum):
    """Prioridades de atendimento.

    O código numérico define a ordem de chamada: quanto menor, mais urgente.
    NORMAL (7) é a senha comum: não entra no heap das prioritárias, fica numa fila FIFO
    e só é chamada quando não há prioritária aguardando.
    """
    IDOSO_80 = 1
    IDOSO_60 = 2
    PCD = 3
    GESTANTE = 4
    OBESO = 5
    CRIANCA_COLO = 6
    NORMAL = 7

    @property
    def descricao(self) -> str:
        """Nome para exibir em menus e no relatório."""
        return _DESCRICOES[self]


_DESCRICOES = {
    Prioridade.IDOSO_80: "Idosos 80+",
    Prioridade.IDOSO_60: "Idosos de 60 a 79 anos",
    Prioridade.PCD: "PCD",
    Prioridade.GESTANTE: "Gestantes",
    Prioridade.OBESO: "Obesos",
    Prioridade.CRIANCA_COLO: "Crianças no colo",
    Prioridade.NORMAL: "Normal",
}


class StatusSenha(Enum):
    """Status de uma senha."""
    AGUARDANDO = "Aguardando"
    EM_ATENDIMENTO = "Em Atendimento"
    FINALIZADA = "Finalizada"
    NAO_ATENDIDA = "Não Atendida"

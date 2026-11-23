"""Entidades do sistema: especialista e senha."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .enums import Especialidade, Prioridade, StatusSenha


@dataclass(frozen=True)
class Especialista:
    """Representa um especialista médico."""
    nome: str
    especialidade: Especialidade
    consultorio: int


@dataclass
class Senha:
    """Representa uma senha gerada para atendimento."""
    numero: int
    especialidade: Especialidade
    prioridade: Prioridade
    status: StatusSenha = StatusSenha.AGUARDANDO
    hora_geracao: datetime = field(default_factory=datetime.now)
    hora_chamada: Optional[datetime] = None
    hora_finalizacao: Optional[datetime] = None
    consultorio: Optional[int] = None
    especialista: Optional[Especialista] = None

    @property
    def codigo(self) -> str:
        """Código exibido ao paciente: N (normal) ou P (prioritária) + número com 3 dígitos."""
        letra = "N" if self.prioridade == Prioridade.NORMAL else "P"
        return f"{letra}{self.numero:03d}"

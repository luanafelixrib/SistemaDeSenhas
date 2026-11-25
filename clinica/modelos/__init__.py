"""Modelos do sistema de senhas da clínica: especialidades, prioridades, senhas e especialistas."""

from .entidades import Especialista, Senha
from .enums import ESPECIALIDADES_ATIVAS, Especialidade, Prioridade, StatusSenha

__all__ = ["Especialidade", "ESPECIALIDADES_ATIVAS", "Prioridade", "StatusSenha", "Especialista", "Senha"]

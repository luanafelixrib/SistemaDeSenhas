"""Relatório: persistência em SQLite e relatório diário de atendimento."""

from .relatorio import Relatorio, Resumo, resumir
from .repositorio import Repositorio

__all__ = ["Relatorio", "Repositorio", "Resumo", "resumir"]

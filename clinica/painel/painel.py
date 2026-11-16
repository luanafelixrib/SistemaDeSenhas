"""Painel: prepara os dados de chamada e de espera para exibição (RF06, RF07).

Este módulo não desenha nada: devolve dados puros. Terminal e interface gráfica
usam as mesmas linhas, então trocar de um para o outro não mexe na lógica.
"""
from dataclasses import dataclass

from clinica.filas import GerenciadorFilas
from clinica.modelos import Especialidade


@dataclass
class LinhaPainel:
    """Uma linha do painel: a última chamada e a espera estimada de uma especialidade."""
    especialidade: Especialidade
    senha: str | None = None                # código da última senha chamada (ex.: "P002")
    consultorio: int | None = None          # consultório para onde ela foi chamada
    espera_estimada_min: int | None = None  # None: sem especialista ou dia encerrado


class Painel:
    """Monta as linhas do painel a partir do estado do GerenciadorFilas."""

    def __init__(self, gerenciador: GerenciadorFilas):
        self._gerenciador = gerenciador

    def linhas(self) -> list[LinhaPainel]:
        """Uma linha por especialidade, na ordem do enum."""
        linhas = []
        for especialidade in Especialidade:
            ultima = self._gerenciador.ultima_chamada(especialidade)
            linhas.append(LinhaPainel(
                especialidade=especialidade,
                senha=ultima.codigo if ultima else None,
                consultorio=ultima.consultorio if ultima else None,
                espera_estimada_min=self._gerenciador.tempo_espera_estimado(especialidade),
            ))
        return linhas

    def texto(self) -> str:
        """Painel em texto, para o terminal."""
        cabecalho = f"{'ESPECIALIDADE':<15} {'SENHA':<7} {'CONSULTÓRIO':<12} ESPERA ESTIMADA"
        linhas = [cabecalho, "-" * len(cabecalho)]
        for linha in self.linhas():
            senha = linha.senha or "-"
            consultorio = str(linha.consultorio) if linha.consultorio else "-"
            linhas.append(
                f"{linha.especialidade.value:<15} {senha:<7} {consultorio:<12} "
                f"{_formatar_espera(linha.espera_estimada_min)}"
            )
        return "\n".join(linhas)


def _formatar_espera(minutos: int | None) -> str:
    """Texto da espera. É uma estimativa, sem garantia de tempo (RN05)."""
    if minutos is None:
        return "indisponível"
    if minutos == 0:
        return "sem espera"
    return f"~{minutos} min"

"""Painel: prepara os dados de chamada e de espera para exibição (RF06, RF07).

Este módulo não desenha nada: devolve dados puros. Terminal e interface gráfica
usam as mesmas linhas, então trocar de um para o outro não mexe na lógica.
"""
from dataclasses import dataclass

from clinica.filas import GerenciadorFilas
from clinica.modelos import Especialidade


@dataclass
class LinhaPainel:
    """Chamada mais recente e situação da fila de uma especialidade."""
    especialidade: Especialidade
    senha: str | None = None                # código da última senha chamada (ex.: "P002")
    categoria: str | None = None            # categoria da última senha chamada
    consultorio: int | None = None          # consultório para onde ela foi chamada
    quantidade_aguardando: int = 0
    senhas_aguardando: tuple[str, ...] = ()  # ordem prevista de chamada
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
            aguardando = self._gerenciador.senhas_aguardando(especialidade)
            linhas.append(LinhaPainel(
                especialidade=especialidade,
                senha=ultima.codigo if ultima else None,
                categoria=ultima.prioridade.descricao if ultima else None,
                consultorio=ultima.consultorio if ultima else None,
                quantidade_aguardando=len(aguardando),
                senhas_aguardando=tuple(s.codigo for s in aguardando),
                espera_estimada_min=self._gerenciador.tempo_espera_estimado(especialidade),
            ))
        return linhas

    def texto(self) -> str:
        """Painel em texto, para o terminal."""
        cabecalho = (f"{'ESPECIALIDADE':<15} {'ÚLTIMA':<7} {'CATEGORIA':<24} "
                     f"{'CONS.':<6} {'AGUARDANDO':<10} {'SENHAS EM ESPERA':<24} ESPERA")
        linhas = [cabecalho, "-" * len(cabecalho)]
        for linha in self.linhas():
            senha = linha.senha or "-"
            categoria = linha.categoria or "-"
            consultorio = str(linha.consultorio) if linha.consultorio else "-"
            codigos = ", ".join(linha.senhas_aguardando) or "-"
            linhas.append(
                f"{linha.especialidade.value:<15} {senha:<7} {categoria:<24} "
                f"{consultorio:<6} {linha.quantidade_aguardando:<10} {codigos:<24} "
                f"{formatar_espera(linha.espera_estimada_min)}"
            )
        return "\n".join(linhas)


def formatar_espera(minutos: int | None) -> str:
    """Texto da espera. É uma estimativa, sem garantia de tempo (RN05)."""
    if minutos is None:
        return "indisponível"
    if minutos == 0:
        return "sem espera"
    return f"~{minutos} min"

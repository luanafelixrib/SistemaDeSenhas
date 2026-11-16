"""Relatório diário de atendimento (RF10 a RF12).

Lê as senhas do dia no SQLite, calcula os números e monta o texto. Não depende de
tela: o terminal e a interface gráfica mostram o mesmo texto.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from clinica.modelos import Especialidade, Prioridade, Senha, StatusSenha

from .repositorio import Repositorio

PASTA_PADRAO = "relatorios"


@dataclass
class Resumo:
    """Números de um conjunto de senhas."""
    emitidas: int
    atendidas: int           # FINALIZADA
    nao_atendidas: int       # NAO_ATENDIDA
    em_aberto: int           # AGUARDANDO ou EM_ATENDIMENTO (só aparece com o dia em andamento)
    espera_media: float | None    # minutos, da emissão até a chamada
    duracao_media: float | None   # minutos, da chamada até a finalização


def _media_minutos(intervalos: list[timedelta]) -> float | None:
    if not intervalos:
        return None
    return sum(i.total_seconds() for i in intervalos) / len(intervalos) / 60


def resumir(senhas: list[Senha]) -> Resumo:
    """Calcula os números de um grupo de senhas.

    A duração média só usa atendimentos com hora de finalização registrada: os que o
    sistema fechou sozinho no fim do dia contam como atendidos, mas ficam de fora da média.
    """
    esperas = [s.hora_chamada - s.hora_geracao for s in senhas if s.hora_chamada]
    duracoes = [s.hora_finalizacao - s.hora_chamada
                for s in senhas if s.hora_chamada and s.hora_finalizacao]
    return Resumo(
        emitidas=len(senhas),
        atendidas=sum(s.status == StatusSenha.FINALIZADA for s in senhas),
        nao_atendidas=sum(s.status == StatusSenha.NAO_ATENDIDA for s in senhas),
        em_aberto=sum(s.status in (StatusSenha.AGUARDANDO, StatusSenha.EM_ATENDIMENTO)
                      for s in senhas),
        espera_media=_media_minutos(esperas),
        duracao_media=_media_minutos(duracoes),
    )


def _minutos(valor: float | None) -> str:
    """Ex.: 12,5 min (vírgula, como no Brasil). Sem dados: '-'."""
    if valor is None:
        return "-"
    return f"{valor:.1f} min".replace(".", ",")


def _tabela(cabecalho: list[str], linhas: list[list[str]], esquerda: tuple[int, ...] = (0,)) -> list[str]:
    """Alinha as colunas: as de `esquerda` (texto) à esquerda e as demais (números) à direita."""
    larguras = [max(len(linha[i]) for linha in [cabecalho] + linhas) for i in range(len(cabecalho))]

    def formatar(linha: list[str]) -> str:
        celulas = [linha[i].ljust(larguras[i]) if i in esquerda else linha[i].rjust(larguras[i])
                   for i in range(len(linha))]
        return "  " + "  ".join(celulas)

    return [formatar(cabecalho), "  " + "  ".join("-" * l for l in larguras)] + \
           [formatar(linha) for linha in linhas]


class Relatorio:
    """Monta o relatório de um dia a partir do que está no banco."""

    def __init__(self, repositorio: Repositorio):
        self._repositorio = repositorio

    def gerar_texto(self, dia: date) -> str:
        senhas = self._repositorio.listar_senhas(dia)
        saida = [f"RELATÓRIO DE ATENDIMENTO - {dia.strftime('%d/%m/%Y')}", ""]
        if not senhas:
            saida.append("Nenhuma senha foi emitida neste dia.")
            return "\n".join(saida) + "\n"

        resumo = resumir(senhas)
        saida += [
            "RESUMO DO DIA",
            f"  Senhas emitidas.................. {resumo.emitidas}",
            f"  Atendidas........................ {resumo.atendidas}",
            f"  Não atendidas.................... {resumo.nao_atendidas}",
        ]
        if resumo.em_aberto:
            saida.append(f"  Em aberto (dia em andamento)..... {resumo.em_aberto}")
        saida += [
            f"  Espera média até a chamada....... {_minutos(resumo.espera_media)}",
            f"  Duração média do atendimento..... {_minutos(resumo.duracao_media)}",
            "",
            "POR ESPECIALIDADE",
        ]

        linhas = []
        for especialidade in Especialidade:
            grupo = [s for s in senhas if s.especialidade == especialidade]
            if grupo:
                r = resumir(grupo)
                linhas.append([especialidade.value, str(r.emitidas), str(r.atendidas),
                               str(r.nao_atendidas), _minutos(r.espera_media),
                               _minutos(r.duracao_media)])
        saida += _tabela(["Especialidade", "Emitidas", "Atendidas", "Não atend.",
                          "Espera média", "Duração média"], linhas)

        saida += ["", "POR PRIORIDADE"]
        linhas = []
        for prioridade in Prioridade:
            grupo = [s for s in senhas if s.prioridade == prioridade]
            if grupo:
                r = resumir(grupo)
                linhas.append([prioridade.descricao, str(r.emitidas), str(r.atendidas),
                               str(r.nao_atendidas)])
        saida += _tabela(["Prioridade", "Emitidas", "Atendidas", "Não atend."], linhas)

        atendidas = [s for s in senhas if s.status == StatusSenha.FINALIZADA and s.especialista]
        if atendidas:
            saida += ["", "POR ESPECIALISTA"]
            linhas = []
            consultorios = sorted({s.consultorio for s in atendidas})
            for consultorio in consultorios:
                grupo = [s for s in atendidas if s.consultorio == consultorio]
                especialista = grupo[0].especialista
                linhas.append([f"Consultório {consultorio}", especialista.nome,
                               especialista.especialidade.value, str(len(grupo)),
                               _minutos(resumir(grupo).duracao_media)])
            saida += _tabela(["Consultório", "Especialista", "Especialidade",
                              "Atendimentos", "Duração média"], linhas, esquerda=(0, 1, 2))

        sem_hora = sum(1 for s in atendidas if s.hora_finalizacao is None)
        if sem_hora:
            saida += ["", f"Obs.: {sem_hora} atendimento(s) foi(ram) encerrado(s) automaticamente "
                          "no fechamento do dia. Contam como atendidos, mas ficam fora da "
                          "duração média."]
        saida += ["", "Os tempos são médias reais do dia, calculadas com os horários registrados."]
        return "\n".join(saida) + "\n"

    def salvar_arquivo(self, dia: date, pasta: str | Path = PASTA_PADRAO) -> Path:
        """Grava o relatório em `pasta/relatorio_AAAA-MM-DD.txt` e devolve o caminho."""
        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"relatorio_{dia.isoformat()}.txt"
        caminho.write_text(self.gerar_texto(dia), encoding="utf-8")
        return caminho

"""Repositório SQLite: senhas do dia, cadastro de especialistas e administrador (RNF05).

Só este módulo conhece SQL. O resto do sistema fala com ele por métodos simples,
então dá para trocar o banco sem mexer nas filas, no painel ou no relatório.
"""
import sqlite3
from datetime import date, datetime
from pathlib import Path

from clinica.especialistas import Administrador
from clinica.modelos import Especialidade, Especialista, Prioridade, Senha, StatusSenha

CAMINHO_PADRAO = "dados/clinica.db"

_TABELAS = """
CREATE TABLE IF NOT EXISTS senhas (
    especialidade    TEXT    NOT NULL,
    numero           INTEGER NOT NULL,
    prioridade       INTEGER NOT NULL,
    status           TEXT    NOT NULL,
    hora_geracao     TEXT    NOT NULL,
    hora_chamada     TEXT,
    hora_finalizacao TEXT,
    consultorio      INTEGER,
    especialista     TEXT,
    PRIMARY KEY (especialidade, numero, hora_geracao)
);
CREATE TABLE IF NOT EXISTS especialistas (
    consultorio  INTEGER PRIMARY KEY,
    nome         TEXT NOT NULL,
    especialidade TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS administrador (
    usuario TEXT PRIMARY KEY,
    salt    BLOB NOT NULL,
    hash    BLOB NOT NULL
);
"""


def _para_texto(momento: datetime | None) -> str | None:
    return momento.isoformat() if momento else None


def _de_texto(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


class Repositorio:
    """Grava e lê os dados da clínica no SQLite.

    Use `":memory:"` como caminho nos testes: o banco some quando o programa termina.
    """

    def __init__(self, caminho: str | Path = CAMINHO_PADRAO):
        if str(caminho) != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self._conexao = sqlite3.connect(str(caminho))
        with self._conexao:
            self._conexao.executescript(_TABELAS)

    def fechar(self) -> None:
        self._conexao.close()

    # --- Senhas -----------------------------------------------------------------

    def salvar_senha(self, senha: Senha) -> None:
        """Grava a senha, ou atualiza se ela já existe.

        A chave é (especialidade, número, hora de geração). A hora de geração nunca muda,
        e assim, se a numeração recomeçar no mesmo dia (encerrar e iniciar outro dia),
        as senhas antigas não são sobrescritas.
        """
        with self._conexao:
            self._conexao.execute(
                "INSERT OR REPLACE INTO senhas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    senha.especialidade.name,
                    senha.numero,
                    senha.prioridade.value,
                    senha.status.name,
                    _para_texto(senha.hora_geracao),
                    _para_texto(senha.hora_chamada),
                    _para_texto(senha.hora_finalizacao),
                    senha.consultorio,
                    senha.especialista.nome if senha.especialista else None,
                ),
            )

    def listar_senhas(self, dia: date) -> list[Senha]:
        """Todas as senhas geradas no dia, na ordem em que foram emitidas."""
        linhas = self._conexao.execute(
            "SELECT especialidade, numero, prioridade, status, hora_geracao, hora_chamada, "
            "hora_finalizacao, consultorio, especialista FROM senhas "
            "WHERE substr(hora_geracao, 1, 10) = ? ORDER BY hora_geracao, numero",
            (dia.isoformat(),),
        ).fetchall()
        senhas = []
        for (esp, numero, prioridade, status, geracao, chamada,
             finalizacao, consultorio, nome_especialista) in linhas:
            especialidade = Especialidade[esp]
            especialista = None
            if consultorio is not None and nome_especialista is not None:
                especialista = Especialista(nome_especialista, especialidade, consultorio)
            senhas.append(Senha(
                numero=numero,
                especialidade=especialidade,
                prioridade=Prioridade(prioridade),
                status=StatusSenha[status],
                hora_geracao=_de_texto(geracao),
                hora_chamada=_de_texto(chamada),
                hora_finalizacao=_de_texto(finalizacao),
                consultorio=consultorio,
                especialista=especialista,
            ))
        return senhas

    def dias_com_senhas(self) -> list[date]:
        """Dias que têm pelo menos uma senha gravada, do mais antigo ao mais recente."""
        linhas = self._conexao.execute(
            "SELECT DISTINCT substr(hora_geracao, 1, 10) FROM senhas ORDER BY 1"
        ).fetchall()
        return [date.fromisoformat(texto) for (texto,) in linhas]

    # --- Especialistas ----------------------------------------------------------

    def salvar_especialista(self, especialista: Especialista) -> None:
        with self._conexao:
            self._conexao.execute(
                "INSERT OR REPLACE INTO especialistas VALUES (?, ?, ?)",
                (especialista.consultorio, especialista.nome, especialista.especialidade.name),
            )

    def listar_especialistas(self) -> list[Especialista]:
        linhas = self._conexao.execute(
            "SELECT nome, especialidade, consultorio FROM especialistas ORDER BY consultorio"
        ).fetchall()
        return [Especialista(nome, Especialidade[esp], consultorio)
                for nome, esp, consultorio in linhas]

    # --- Administrador ----------------------------------------------------------

    def salvar_administrador(self, administrador: Administrador) -> None:
        """Guarda só usuário, salt e hash. A senha em texto nunca chega aqui (RNF06)."""
        with self._conexao:
            self._conexao.execute(
                "INSERT OR REPLACE INTO administrador VALUES (?, ?, ?)",
                administrador.dados_para_guardar(),
            )

    def carregar_administrador(self) -> Administrador | None:
        """O administrador cadastrado, ou None na primeira execução."""
        linha = self._conexao.execute(
            "SELECT usuario, salt, hash FROM administrador LIMIT 1"
        ).fetchone()
        if linha is None:
            return None
        usuario, salt, hash_senha = linha
        return Administrador.restaurar(usuario, salt, hash_senha)

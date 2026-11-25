"""Repositório SQLite: senhas do dia, cadastro de especialistas e administrador (RNF05).

Só este módulo conhece SQL. O resto do sistema fala com ele por métodos simples,
então dá para trocar o banco sem mexer nas filas, no painel ou no relatório.
"""
from collections.abc import Callable
from contextlib import contextmanager
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import TypeVar

from clinica.especialistas import Administrador
from clinica.modelos import Especialidade, Especialista, Prioridade, Senha, StatusSenha

CAMINHO_PADRAO = "dados/clinica.db"

_T = TypeVar("_T")

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
        self._caminho = Path(caminho) if str(caminho) != ":memory:" else None
        if self._caminho is not None:
            self._caminho.parent.mkdir(parents=True, exist_ok=True)
        self._conexao = self._abrir_conexao(str(caminho), em_memoria=self._caminho is None)
        with self._transacao():
            self._conexao.executescript(_TABELAS)

    @staticmethod
    def _abrir_conexao(alvo: str, *, em_memoria: bool) -> sqlite3.Connection:
        conexao = sqlite3.connect(alvo, timeout=10.0)
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.execute("PRAGMA busy_timeout = 10000")
        if not em_memoria:
            conexao.execute("PRAGMA journal_mode = WAL")
            conexao.execute("PRAGMA synchronous = NORMAL")
        return conexao

    @contextmanager
    def _transacao(self):
        """Garante commit ao concluir e rollback limpo em caso de erro/interrupção."""
        if self._conexao.in_transaction:
            yield self._conexao
            return
        self._conexao.execute("BEGIN")
        try:
            yield self._conexao
        except BaseException:
            if self._conexao.in_transaction:
                self._conexao.rollback()
            raise
        else:
            if self._conexao.in_transaction:
                self._conexao.commit()

    def executar_em_transacao(self, operacao: Callable[[], _T]) -> _T:
        """Executa um conjunto de operações do repositório de forma atômica."""
        with self._transacao():
            return operacao()

    def verificar_integridade(self) -> bool:
        """Verifica se o banco SQLite passa no PRAGMA integrity_check."""
        resultado = self._conexao.execute("PRAGMA integrity_check").fetchall()
        return len(resultado) == 1 and resultado[0][0] == "ok"

    def criar_backup(self, destino: str | Path) -> Path:
        """Gera uma cópia consistente do banco atual no caminho indicado."""
        destino_path = Path(destino)
        destino_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destino_path.with_name(f".{destino_path.name}.tmp")
        try:
            with sqlite3.connect(str(temp_path), timeout=10.0) as backup_conn:
                self._conexao.backup(backup_conn)
            temp_path.replace(destino_path)
        except BaseException:
            if temp_path.exists():
                temp_path.unlink()
            raise
        return destino_path

    def restaurar_backup(self, origem_backup: str | Path) -> None:
        """Restaura explicitamente o banco em disco a partir de um backup íntegro.

        Não apaga nem sobrescreve o banco atual se o backup não existir ou falhar
        na checagem de integridade. Exige que o repositório tenha sido criado com
        caminho em arquivo.
        """
        if self._caminho is None:
            raise RuntimeError("Não é possível restaurar backup em banco ':memory:'.")
        origem_path = Path(origem_backup)
        if not origem_path.is_file():
            raise FileNotFoundError(f"Arquivo de backup não encontrado: {origem_path}")

        with sqlite3.connect(str(origem_path), timeout=10.0) as teste_conn:
            integridade = teste_conn.execute("PRAGMA integrity_check").fetchall()
            if not (len(integridade) == 1 and integridade[0][0] == "ok"):
                raise ValueError(f"Backup inválido ou corrompido: {origem_path}")

        temp_destino = self._caminho.with_name(f".{self._caminho.name}.restore.tmp")
        shutil.copy2(origem_path, temp_destino)

        self.fechar()
        try:
            temp_destino.replace(self._caminho)
        except BaseException:
            if temp_destino.exists():
                temp_destino.unlink()
            self._conexao = self._abrir_conexao(str(self._caminho), em_memoria=False)
            raise
        self._conexao = self._abrir_conexao(str(self._caminho), em_memoria=False)

    def fechar(self) -> None:
        if self._conexao is not None:
            self._conexao.close()

    # --- Senhas -----------------------------------------------------------------

    def salvar_senha(self, senha: Senha) -> None:
        """Grava a senha, ou atualiza se ela já existe.

        A chave é (especialidade, número, hora de geração). A hora de geração nunca muda,
        e assim, se a numeração recomeçar no mesmo dia (encerrar e iniciar outro dia),
        as senhas antigas não são sobrescritas.
        """
        with self._transacao():
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
        with self._transacao():
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
        with self._transacao():
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
    
    
"""Autenticação do administrador (RF09 e RNF06)."""

import hashlib
import hmac
import os

ITERACOES_HASH = 100_000


def _gerar_hash(senha: str, salt: bytes) -> bytes:
    """Gera o hash da senha com o salt informado (pbkdf2_hmac, sha256)."""
    # .encode() transforma o texto em bytes, que é o que o hashlib aceita.
    # O pbkdf2_hmac mistura a senha com o salt e repete o processo ITERACOES_HASH vezes.
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), salt, ITERACOES_HASH)


class Administrador:
    """Conta do administrador. Guarda apenas o salt e o hash da senha (RNF06)."""

    def __init__(self, usuario: str, senha: str):
        """Levanta ValueError se usuário ou senha estiverem vazios."""
        usuario = usuario.strip()
        # Não usamos strip() na senha: espaço pode fazer parte dela e mudaria o hash.
        if not usuario or not senha:
            raise ValueError("Usuário e senha não podem ser vazios.")
        self.usuario = usuario
        # Salt: 16 bytes aleatórios, únicos para esta conta. Pode ficar guardado junto do hash.
        self._salt = os.urandom(16)
        # Guardamos só o hash. A senha em si nunca é salva em nenhum atributo (RNF06).
        self._hash = _gerar_hash(senha, self._salt)

    @classmethod
    def restaurar(cls, usuario: str, salt: bytes, hash_senha: bytes) -> "Administrador":
        """Recria a conta a partir do que foi guardado no banco (sem a senha original)."""
        admin = cls.__new__(cls)  # pula o __init__, que exigiria a senha em texto
        admin.usuario = usuario
        admin._salt = salt
        admin._hash = hash_senha
        return admin

    def dados_para_guardar(self) -> tuple[str, bytes, bytes]:
        """(usuario, salt, hash): o que pode ir para o banco. A senha nunca vai (RNF06)."""
        return self.usuario, self._salt, self._hash

    def autenticar(self, usuario: str, senha: str) -> bool:
        """RF09. Devolve True só se usuário e senha conferem."""
        usuario_ok = usuario.strip() == self.usuario
        # Refaz o hash da senha digitada com o MESMO salt guardado no cadastro.
        hash_digitado = _gerar_hash(senha, self._salt)
        # compare_digest compara sem vazar informação pelo tempo de resposta (o == vazaria).
        senha_ok = hmac.compare_digest(self._hash, hash_digitado)
        return usuario_ok and senha_ok

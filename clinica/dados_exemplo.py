"""Popula o banco com dados de exemplo para a apresentação.

Uso (na pasta raiz do projeto):
    python -m clinica.dados_exemplo

O usuário e a senha abaixo existem só para demonstração.
"""
from clinica.modelos import Especialidade
from clinica.sistema import Sistema

USUARIO = "admin"
SENHA = "admin123"

# (nome, especialidade, consultório): 3 por especialidade.
ESPECIALISTAS = [
    ("Dra. Ana Lima", Especialidade.CLINICA_GERAL, 1),
    ("Dr. Bruno Reis", Especialidade.CLINICA_GERAL, 2),
    ("Dra. Carla Souza", Especialidade.CLINICA_GERAL, 3),
    ("Dr. Daniel Costa", Especialidade.PEDIATRIA, 4),
    ("Dra. Elisa Martins", Especialidade.PEDIATRIA, 5),
    ("Dr. Fabio Rocha", Especialidade.PEDIATRIA, 6),
    ("Dra. Gabriela Nunes", Especialidade.GINECOLOGIA, 7),
    ("Dra. Helena Duarte", Especialidade.GINECOLOGIA, 8),
    ("Dra. Isabela Prado", Especialidade.GINECOLOGIA, 9),
    ("Dr. Joao Mendes", Especialidade.CARDIOLOGIA, 10),
    ("Dr. Lucas Ferraz", Especialidade.CARDIOLOGIA, 11),
    ("Dra. Marina Teixeira", Especialidade.CARDIOLOGIA, 12),
]


def popular(sistema: Sistema) -> int:
    """Cadastra os especialistas que faltam e devolve quantos foram cadastrados."""
    # 1) Login: cria o admin se não existe; senão, entra com o que já existe.
    if not sistema.tem_administrador:
        sistema.criar_administrador(USUARIO, SENHA)
    elif not sistema.entrar_como_admin(USUARIO, SENHA):
        raise ValueError("Já existe um administrador com outra senha; nada foi cadastrado.")

    # 2) Cadastro sem repetir: se o consultório já tem alguém, pula.
    cadastrados = 0
    try:
        for nome, especialidade, consultorio in ESPECIALISTAS:
            if sistema.cadastro.buscar_por_consultorio(consultorio) is not None:
                continue
            sistema.cadastrar_especialista(nome, especialidade, consultorio)
            cadastrados += 1
    finally:
        # 3) Sai do modo administrador mesmo que o cadastro falhe no meio.
        sistema.sair_do_admin()
    return cadastrados


if __name__ == "__main__":
    total = popular(Sistema())
    print(f"{total} especialistas cadastrados.")
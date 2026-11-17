"""Ponto de entrada do sistema de senhas da clínica. Execute na raiz do projeto: python main.py"""
from clinica.interface.terminal import Terminal
from clinica.sistema import Sistema


def main() -> None:
    Terminal(Sistema()).executar()


if __name__ == "__main__":
    main()

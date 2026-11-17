"""Ponto de entrada do sistema de senhas da clínica. Execute na raiz do projeto:

    python main.py              abre a interface gráfica (Tkinter)
    python main.py --terminal   usa o menu de terminal
"""
import sys

from clinica.sistema import Sistema


def main() -> None:
    sistema = Sistema()
    if "--terminal" in sys.argv[1:]:
        from clinica.interface.terminal import Terminal
        Terminal(sistema).executar()
    else:
        from clinica.interface.janela import Janela
        Janela(sistema).mainloop()


if __name__ == "__main__":
    main()

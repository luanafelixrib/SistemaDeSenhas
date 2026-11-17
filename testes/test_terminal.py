"""Testes do terminal, com respostas digitadas por um roteiro.

Rodar na raiz do projeto: python -m unittest discover
"""
import tempfile
import unittest
from pathlib import Path

from clinica.interface.terminal import Terminal
from clinica.modelos import Especialidade
from clinica.relatorio import Repositorio
from clinica.sistema import Sistema


class BaseTerminal(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.repo = Repositorio(":memory:")

    def rodar(self, respostas, senhas=(), sistema=None) -> str:
        """Roda o terminal com as respostas dadas e devolve tudo o que ele mostrou."""
        sistema = sistema or Sistema(self.repo, self.pasta)
        entradas, segredos, saidas = iter(respostas), iter(senhas), []
        Terminal(sistema,
                 entrada=lambda _: next(entradas),
                 entrada_senha=lambda _: next(segredos),
                 saida=saidas.append).executar()
        return "\n".join(saidas)


class TestFluxoCompleto(BaseTerminal):
    def test_do_primeiro_acesso_ao_relatorio(self):
        respostas = [
            "4", "admin",                       # área do administrador: primeiro acesso
            "1", "Dra. Ana", "4", "1",          # cadastrar: Cardiologia, consultório 1
            "2",                                # listar
            "0",                                # sair da área
            "1", "4", "N",                      # retirar senha normal de Cardiologia
            "1", "4", "P", "4",                 # retirar senha prioritária (gestante)
            "2",                                # painel
            "3", "1", "1", "1", "2", "0",       # especialista: chama, chama de novo (erro), finaliza
            "2",                                # painel
            "4", "admin",                       # administrador: login
            "3", "4", "s", "0",                 # relatório, encerrar o dia, sair da área
            "0",                                # sair
        ]
        saida = self.rodar(respostas, senhas=["segredo", "segredo", "segredo"])

        self.assertIn("Administrador criado.", saida)
        self.assertIn("Consultório  1 - Dra. Ana (Cardiologia)", saida)
        self.assertIn("Sua senha: N001 (Cardiologia)", saida)
        self.assertIn("Sua senha: P002 (Cardiologia)", saida)
        self.assertIn("Pessoas à frente: 0", saida)           # a prioritária passa na frente
        self.assertIn("Chamando a senha P002 no consultório 1.", saida)
        self.assertIn("já tem atendimento aberto", saida)
        self.assertIn("Atendimento da senha P002 finalizado.", saida)
        self.assertIn("RELATÓRIO DE ATENDIMENTO", saida)
        self.assertIn("Dia encerrado. Relatório salvo em", saida)
        self.assertEqual(len(list(self.pasta.glob("relatorio_*.txt"))), 1)
        self.assertTrue(saida.endswith("Sistema encerrado."))


class TestEntradas(BaseTerminal):
    def test_opcao_invalida_pede_de_novo(self):
        saida = self.rodar(["9", "abc", "", "0"])
        self.assertEqual(saida.count("Opção inválida"), 3)
        self.assertIn("Sistema encerrado.", saida)

    def test_ctrl_d_encerra_sem_erro(self):
        sistema = Sistema(self.repo, self.pasta)
        saidas = []

        def entrada(_):
            raise EOFError

        Terminal(sistema, entrada=entrada, saida=saidas.append).executar()
        self.assertEqual(saidas[-1], "Sistema encerrado.")


class TestPaciente(BaseTerminal):
    def sistema_com_cardiologia(self):
        sistema = Sistema(self.repo, self.pasta)
        sistema.criar_administrador("admin", "segredo")
        sistema.cadastrar_especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        sistema.sair_do_admin()
        return sistema

    def test_especialidade_sem_especialista_nao_emite_senha(self):
        saida = self.rodar(["1", "2", "N", "0"], sistema=self.sistema_com_cardiologia())
        self.assertIn("Pediatria  (sem especialista no momento)", saida)
        self.assertIn("Não foi possível emitir a senha", saida)

    def test_tipo_de_senha_invalido_pede_de_novo(self):
        saida = self.rodar(["1", "4", "x", "N", "0"], sistema=self.sistema_com_cardiologia())
        self.assertIn("Digite N para normal ou P para prioritária.", saida)
        self.assertIn("Sua senha: N001", saida)

    def test_voltar_na_prioridade_nao_emite_senha(self):
        saida = self.rodar(["1", "4", "P", "0", "0"], sistema=self.sistema_com_cardiologia())
        self.assertNotIn("Sua senha", saida)


class TestEspecialista(BaseTerminal):
    def test_consultorio_sem_especialista(self):
        saida = self.rodar(["3", "5", "0"])
        self.assertIn("Não há especialista cadastrado no consultório 5.", saida)

    def test_sem_senhas_aguardando(self):
        sistema = Sistema(self.repo, self.pasta)
        sistema.criar_administrador("admin", "segredo")
        sistema.cadastrar_especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        saida = self.rodar(["3", "1", "1", "0", "0"], sistema=sistema)
        self.assertIn("Não há senhas aguardando nesta especialidade.", saida)


class TestAdministrador(BaseTerminal):
    def test_senhas_diferentes_no_primeiro_acesso(self):
        saida = self.rodar(["4", "admin", "0"], senhas=["segredo", "outra"])
        self.assertIn("As senhas não conferem.", saida)

    def test_primeiro_acesso_com_senha_vazia(self):
        saida = self.rodar(["4", "admin", "0"], senhas=["", ""])
        self.assertIn("Não foi possível criar a conta", saida)

    def test_login_errado_tres_vezes_bloqueia(self):
        sistema = Sistema(self.repo, self.pasta)
        sistema.criar_administrador("admin", "segredo")
        sistema.sair_do_admin()
        saida = self.rodar(["4", "admin", "admin", "admin", "0"],
                           senhas=["x", "y", "z"], sistema=sistema)
        self.assertEqual(saida.count("Usuário ou senha incorretos."), 3)
        self.assertIn("Número de tentativas excedido.", saida)
        self.assertFalse(sistema.admin_logado)

    def test_sair_da_area_tira_o_acesso(self):
        sistema = Sistema(self.repo, self.pasta)
        sistema.criar_administrador("admin", "segredo")
        sistema.sair_do_admin()
        self.rodar(["4", "admin", "0", "0"], senhas=["segredo"], sistema=sistema)
        self.assertFalse(sistema.admin_logado)

    def test_cadastro_com_erro_mostra_o_motivo(self):
        respostas = ["4", "admin", "1", "Dra. Ana", "4", "1",
                     "1", "Dr. Beto", "2", "1",         # consultório 1 já ocupado
                     "0", "0"]
        saida = self.rodar(respostas, senhas=["segredo", "segredo"])
        self.assertIn("Cadastrado: Dra. Ana - Cardiologia, consultório 1.", saida)
        self.assertIn("Não foi possível cadastrar: Consultório 1 já ocupado.", saida)

    def test_encerrar_dia_cancelado(self):
        respostas = ["4", "admin", "4", "n", "0", "0"]
        saida = self.rodar(respostas, senhas=["segredo", "segredo"])
        self.assertIn("Operação cancelada.", saida)
        self.assertEqual(list(self.pasta.glob("relatorio_*.txt")), [])

    def test_iniciar_novo_dia_sem_encerrar_mostra_erro(self):
        respostas = ["4", "admin", "5", "0", "0"]
        saida = self.rodar(respostas, senhas=["segredo", "segredo"])
        self.assertIn("Erro: Encerre o dia atual antes de iniciar outro.", saida)


if __name__ == "__main__":
    unittest.main()

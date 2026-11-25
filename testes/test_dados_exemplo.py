"""Testes dos dados de exemplo."""
import tempfile
import unittest
from pathlib import Path

from clinica.dados_exemplo import popular
from clinica.modelos import ESPECIALIDADES_ATIVAS, Especialidade
from clinica.relatorio import Repositorio
from clinica.sistema import Sistema


class TestDadosExemplo(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio(":memory:")
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)

    def abrir(self) -> Sistema:
        """Abre o sistema sobre o mesmo banco (como fechar e reabrir o programa)."""
        return Sistema(self.repo, self.pasta)

    def ocupados(self, sistema) -> int:
        """Quantos consultórios (1 a 12) têm especialista."""
        return sum(1 for n in range(1, 13)
                   if sistema.cadastro.buscar_por_consultorio(n) is not None)

    def test_cadastra_nove_especialistas(self):
        sistema = self.abrir()
        total = popular(sistema)
        self.assertEqual(total, 9)

    def test_tres_por_especialidade(self):
        sistema = self.abrir()
        popular(sistema)
        for especialidade in ESPECIALIDADES_ATIVAS:
            doutores = [n for n in range(1, 13)
                        if sistema.cadastro.buscar_por_consultorio(n) is not None
                        and sistema.cadastro.buscar_por_consultorio(n).especialidade == especialidade]
            self.assertEqual(len(doutores), 3)

    def test_rodar_duas_vezes_nao_duplica(self):
        sistema = self.abrir()
        popular(sistema)
        segunda = popular(sistema)
        self.assertEqual(segunda, 0)
        self.assertEqual(self.ocupados(sistema), 9)

    def test_dados_continuam_depois_de_reabrir(self):
        popular(self.abrir())
        reaberto = self.abrir()
        self.assertIsNotNone(reaberto.cadastro.buscar_por_consultorio(1))
        self.assertEqual(self.ocupados(reaberto), 9)

    def test_admin_criado_consegue_entrar(self):
        popular(self.abrir())
        reaberto = self.abrir()
        self.assertTrue(reaberto.entrar_como_admin("admin", "admin123"))

    def test_admin_com_outra_senha_levanta_erro(self):
        sistema = self.abrir()
        sistema.criar_administrador("admin", "outra-senha")
        sistema.sair_do_admin()
        with self.assertRaises(ValueError):
            popular(sistema)
        self.assertIsNone(sistema.cadastro.buscar_por_consultorio(1))
        self.assertEqual(self.ocupados(sistema), 0)

    def test_erro_no_meio_do_cadastro_nao_deixa_admin_logado(self):
        sistema = self.abrir()
        sistema.criar_administrador("admin", "admin123")
        for consultorio in (1, 2, 3):  # três pediatras já ocupam os consultórios 1 a 3
            sistema.cadastrar_especialista(
                f"Pediatra {consultorio}", Especialidade.PEDIATRIA, consultorio)
        with self.assertRaises(ValueError):  # o Dr. Daniel (Pediatria) estoura o limite de 3
            popular(sistema)
        self.assertFalse(sistema.admin_logado)


if __name__ == "__main__":
    unittest.main()

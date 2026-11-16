"""Testes do painel e do código da senha.

Rodar na raiz do projeto: python -m unittest discover
"""
import unittest

from clinica.especialistas import CadastroEspecialistas
from clinica.filas import GerenciadorFilas
from clinica.modelos import Especialidade, Prioridade, Senha
from clinica.painel import LinhaPainel, Painel


def montar_clinica():
    """Cardiologia com 2 consultórios (1 e 2) e Pediatria com 1 (3); as outras sem especialista."""
    cadastro = CadastroEspecialistas()
    cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
    cadastro.cadastrar("Dr. Beto", Especialidade.CARDIOLOGIA, 2)
    cadastro.cadastrar("Dra. Carla", Especialidade.PEDIATRIA, 3)
    gerenciador = GerenciadorFilas(cadastro)
    return gerenciador, Painel(gerenciador)


class TestCodigoSenha(unittest.TestCase):
    def test_normal_comeca_com_n(self):
        senha = Senha(1, Especialidade.PEDIATRIA, Prioridade.NORMAL)
        self.assertEqual(senha.codigo, "N001")

    def test_prioritaria_comeca_com_p(self):
        for prioridade in Prioridade:
            if prioridade != Prioridade.NORMAL:
                senha = Senha(12, Especialidade.PEDIATRIA, prioridade)
                self.assertEqual(senha.codigo, "P012")

    def test_numero_com_tres_digitos(self):
        self.assertEqual(Senha(7, Especialidade.PEDIATRIA, Prioridade.NORMAL).codigo, "N007")
        self.assertEqual(Senha(123, Especialidade.PEDIATRIA, Prioridade.NORMAL).codigo, "N123")


class TestPainel(unittest.TestCase):
    def setUp(self):
        self.gerenciador, self.painel = montar_clinica()

    def test_uma_linha_por_especialidade_na_ordem_do_enum(self):
        linhas = self.painel.linhas()
        self.assertEqual([l.especialidade for l in linhas], list(Especialidade))
        self.assertTrue(all(isinstance(l, LinhaPainel) for l in linhas))

    def test_sem_chamada_nao_mostra_senha_nem_consultorio(self):
        linha = self.linha(Especialidade.CARDIOLOGIA)
        self.assertIsNone(linha.senha)
        self.assertIsNone(linha.consultorio)

    def test_mostra_a_ultima_senha_chamada_e_o_consultorio(self):
        self.gerenciador.emitir_senha(Especialidade.CARDIOLOGIA)
        self.gerenciador.emitir_senha(Especialidade.CARDIOLOGIA, Prioridade.GESTANTE)
        self.gerenciador.chamar_proxima(1)   # a gestante (P002) passa na frente
        self.gerenciador.chamar_proxima(2)   # depois a normal (N001)
        linha = self.linha(Especialidade.CARDIOLOGIA)
        self.assertEqual((linha.senha, linha.consultorio), ("N001", 2))

    def test_mantem_a_ultima_chamada_depois_de_finalizar(self):
        self.gerenciador.emitir_senha(Especialidade.PEDIATRIA, Prioridade.PCD)
        self.gerenciador.chamar_proxima(3)
        self.gerenciador.finalizar_atendimento(3)
        linha = self.linha(Especialidade.PEDIATRIA)
        self.assertEqual((linha.senha, linha.consultorio), ("P001", 3))

    def test_espera_usa_os_consultorios_ativos(self):
        for _ in range(5):
            self.gerenciador.emitir_senha(Especialidade.CARDIOLOGIA)
        self.assertEqual(self.linha(Especialidade.CARDIOLOGIA).espera_estimada_min, 75)

    def test_especialidade_sem_especialista_fica_indisponivel(self):
        self.assertIsNone(self.linha(Especialidade.GINECOLOGIA).espera_estimada_min)
        self.assertIsNone(self.linha(Especialidade.CLINICA_GERAL).espera_estimada_min)

    def test_fila_vazia_com_especialista_tem_espera_zero(self):
        self.assertEqual(self.linha(Especialidade.PEDIATRIA).espera_estimada_min, 0)

    def test_depois_do_encerramento_o_painel_nao_quebra_e_zera(self):
        self.gerenciador.emitir_senha(Especialidade.CARDIOLOGIA)
        self.gerenciador.chamar_proxima(1)
        self.gerenciador.encerrar_dia()
        for linha in self.painel.linhas():
            self.assertIsNone(linha.senha)
            self.assertIsNone(linha.consultorio)
            self.assertIsNone(linha.espera_estimada_min)

    def test_texto_mostra_codigo_consultorio_e_espera(self):
        self.gerenciador.emitir_senha(Especialidade.CARDIOLOGIA, Prioridade.IDOSO_80)
        self.gerenciador.emitir_senha(Especialidade.CARDIOLOGIA)
        self.gerenciador.chamar_proxima(2)
        texto = self.painel.texto()
        self.assertIn("P001", texto)
        self.assertIn("~15 min", texto)
        self.assertIn("indisponível", texto)
        self.assertIn("Cardiologia", texto)

    def linha(self, especialidade):
        return next(l for l in self.painel.linhas() if l.especialidade == especialidade)


if __name__ == "__main__":
    unittest.main()

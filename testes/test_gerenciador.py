"""Testes do GerenciadorFilas (erros, encerramento do dia e estimativa de espera)."""
import unittest

from clinica.especialistas import CadastroEspecialistas
from clinica.filas import GerenciadorFilas
from clinica.modelos import Especialidade, StatusSenha

CARDIO = Especialidade.CARDIOLOGIA
PEDIATRIA = Especialidade.PEDIATRIA


class TestGerenciadorFilas(unittest.TestCase):
    def setUp(self):
        # Roda antes de CADA teste: monta um cenário limpo.
        # Cardiologia com 2 consultórios (1 e 2); Pediatria sem ninguém.
        self.cadastro = CadastroEspecialistas()
        self.cadastro.cadastrar("Dr. Ana", CARDIO, 1)
        self.cadastro.cadastrar("Dr. Bruno", CARDIO, 2)
        self.gerenciador = GerenciadorFilas(self.cadastro)

    # --- Erros ---
    def test_nao_emite_senha_de_especialidade_sem_especialista(self):
        # Pediatria não tem especialista cadastrado (RN06): deve dar ValueError.
        with self.assertRaises(ValueError):
            self.gerenciador.emitir_senha(PEDIATRIA)

    def test_chamar_consultorio_inexistente_levanta_erro(self):
        # Não há especialista cadastrado no consultório 12.
        with self.assertRaises(ValueError):
            self.gerenciador.chamar_proxima(12)

    def test_chamar_consultorio_ocupado_levanta_erro(self):
        self.gerenciador.emitir_senha(CARDIO)
        self.gerenciador.emitir_senha(CARDIO)
        self.gerenciador.chamar_proxima(1)
        # O consultório 1 ainda não finalizou o atendimento: não pode chamar de novo.
        with self.assertRaises(ValueError):
            self.gerenciador.chamar_proxima(1)

    def test_finalizar_sem_atendimento_levanta_erro(self):
        # Ninguém foi chamado no consultório 1, então não há o que finalizar.
        with self.assertRaises(ValueError):
            self.gerenciador.finalizar_atendimento(1)

    # --- Encerramento do dia ---
    def test_encerrar_dia_marca_status_e_hora(self):
        em_atendimento = self.gerenciador.emitir_senha(CARDIO)   # senha 1
        aguardando = self.gerenciador.emitir_senha(CARDIO)       # senha 2
        self.gerenciador.chamar_proxima(1)    # chama a senha 1 (fica EM_ATENDIMENTO)

        self.gerenciador.encerrar_dia()

        # Quem ainda aguardava vira "não atendida".
        self.assertEqual(aguardando.status, StatusSenha.NAO_ATENDIDA)
        # Quem estava em atendimento conta como atendida...
        self.assertEqual(em_atendimento.status, StatusSenha.FINALIZADA)
        # ...mas sem hora de finalização, porque o horário real é desconhecido.
        self.assertIsNone(em_atendimento.hora_finalizacao)

    def test_nao_emite_depois_de_encerrado(self):
        self.gerenciador.encerrar_dia()
        # Com o dia encerrado, emitir senha é proibido.
        with self.assertRaises(ValueError):
            self.gerenciador.emitir_senha(CARDIO)

    def test_numeracao_recomeca_no_novo_dia(self):
        self.gerenciador.emitir_senha(CARDIO)
        self.gerenciador.emitir_senha(CARDIO)
        self.gerenciador.encerrar_dia()
        self.gerenciador.iniciar_novo_dia()          # reabre a emissão
        nova = self.gerenciador.emitir_senha(CARDIO)
        # As filas foram recriadas, então o contador volta ao início.
        self.assertEqual(nova.numero, 1)

    # --- Estimativa de espera ---
    # Fórmula: pessoas à frente x 30 min / consultórios ativos (arredondado para cima).
    def test_estimativa_geral_com_5_aguardando_e_2_consultorios(self):
        for _ in range(5):
            self.gerenciador.emitir_senha(CARDIO)
        # 5 x 30 / 2 = 75 minutos
        self.assertEqual(self.gerenciador.tempo_espera_estimado(CARDIO), 75)

    def test_estimativa_por_senha(self):
        for _ in range(5):
            self.gerenciador.emitir_senha(CARDIO)
        # {número da senha: minutos esperados}
        # senha 1 tem 0 à frente: 0 x 30 / 2 = 0
        # senha 2 tem 1 à frente: 1 x 30 / 2 = 15
        # senha 5 tem 4 à frente: 4 x 30 / 2 = 60
        esperado = {1: 0, 2: 15, 5: 60}
        for numero, minutos in esperado.items():
            self.assertEqual(
                self.gerenciador.tempo_espera_senha(CARDIO, numero), minutos)


if __name__ == "__main__":
    unittest.main()
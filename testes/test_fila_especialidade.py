"""Testes da FilaEspecialidade (heap das prioritárias + deque das normais)."""
import unittest

from clinica.filas.fila_especialidade import FilaEspecialidade
from clinica.modelos import Especialidade, Prioridade


class TestFilaEspecialidade(unittest.TestCase):
    def setUp(self):
        self.fila = FilaEspecialidade(Especialidade.CARDIOLOGIA)

    def test_prioritaria_passa_na_frente_da_normal(self):
        normal = self.fila.emitir(Prioridade.NORMAL)
        idosa = self.fila.emitir(Prioridade.IDOSO_80)
        # a normal chegou primeiro, mas quem deve ser chamada antes?
        self.assertEqual(self.fila.proxima(), idosa)
        self.assertEqual(self.fila.proxima(), normal)

    def test_normais_saem_em_ordem_de_chegada(self):
        a = self.fila.emitir(Prioridade.NORMAL)
        b = self.fila.emitir(Prioridade.NORMAL)
        c = self.fila.emitir(Prioridade.NORMAL)
        saida = [self.fila.proxima() for _ in range(3)]
        self.assertEqual(saida, [a, b, c])

    def test_ordem_entre_prioridades(self):
        gestante = self.fila.emitir(Prioridade.GESTANTE)
        idoso80_a = self.fila.emitir(Prioridade.IDOSO_80)
        idoso60 = self.fila.emitir(Prioridade.IDOSO_60)
        idoso80_b = self.fila.emitir(Prioridade.IDOSO_80)

        saida = [self.fila.proxima() for _ in range(4)]

        # código 1 primeiro (e entre os dois 1, quem chegou antes),
        # depois o 2, e por último o 4
        self.assertEqual(saida, [idoso80_a, idoso80_b, idoso60, gestante])

    def test_posicao_na_fila(self):
        normal = self.fila.emitir(Prioridade.NORMAL)
        idosa = self.fila.emitir(Prioridade.IDOSO_80)

        # a idosa chegou depois, mas está na frente: ninguém fica antes dela
        self.assertEqual(self.fila.posicao(idosa.numero), 0)
        # só a idosa fica antes da normal
        self.assertEqual(self.fila.posicao(normal.numero), 1)
        # um número que não existe na fila
        self.assertIsNone(self.fila.posicao(999))


if __name__ == "__main__":
    unittest.main()
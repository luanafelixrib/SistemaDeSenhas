"""Testes unitários do cadastro de especialistas.

Rodar na raiz do projeto: python -m unittest testes.test_cadastro_especialistas
"""
import unittest
from dataclasses import FrozenInstanceError

from clinica.especialistas import CadastroEspecialistas
from clinica.modelos import Especialidade, Especialista


class TestCadastroEspecialistas(unittest.TestCase):
    def setUp(self):
        self.cadastro = CadastroEspecialistas()

    def test_rejeita_nome_vazio_ou_so_com_espacos(self):
        for nome in ("", "   ", "\t\n"):
            with self.subTest(nome=nome), self.assertRaises(ValueError):
                self.cadastro.cadastrar(nome, Especialidade.CARDIOLOGIA, 1)

        self.assertEqual(self.cadastro.listar(), [])

    def test_rejeita_consultorio_fora_do_intervalo(self):
        for consultorio in (0, 13):
            with self.subTest(consultorio=consultorio), self.assertRaises(ValueError):
                self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, consultorio)

        self.assertEqual(self.cadastro.listar(), [])

    def test_rejeita_consultorio_ja_ocupado_mesmo_em_outra_especialidade(self):
        ana = self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)

        with self.assertRaises(ValueError):
            self.cadastro.cadastrar("Dr. Beto", Especialidade.PEDIATRIA, 1)

        self.assertEqual(self.cadastro.listar(), [ana])

    def test_limita_tres_especialistas_por_especialidade(self):
        cadastrados = [
            self.cadastro.cadastrar(nome, Especialidade.CARDIOLOGIA, consultorio)
            for nome, consultorio in (
                ("Dra. Ana", 1),
                ("Dr. Beto", 2),
                ("Dra. Carla", 3),
            )
        ]

        with self.assertRaises(ValueError):
            self.cadastro.cadastrar("Dr. Davi", Especialidade.CARDIOLOGIA, 4)

        pediatra = self.cadastro.cadastrar("Dra. Eva", Especialidade.PEDIATRIA, 4)
        self.assertEqual(self.cadastro.listar(), cadastrados + [pediatra])

    def test_busca_por_consultorio_encontra_ou_retorna_none(self):
        ana = self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)

        self.assertEqual(self.cadastro.buscar_por_consultorio(1), ana)
        self.assertIsNone(self.cadastro.buscar_por_consultorio(2))

    def test_lista_todos_ou_filtra_por_especialidade(self):
        ana = self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        beto = self.cadastro.cadastrar("Dr. Beto", Especialidade.PEDIATRIA, 2)
        carla = self.cadastro.cadastrar("Dra. Carla", Especialidade.CARDIOLOGIA, 3)

        self.assertEqual(self.cadastro.listar(), [ana, beto, carla])
        self.assertEqual(
            self.cadastro.listar(Especialidade.CARDIOLOGIA),
            [ana, carla],
        )
        self.assertEqual(self.cadastro.listar(Especialidade.GINECOLOGIA), [])

    def test_conta_consultorios_ativos_por_especialidade(self):
        self.assertEqual(self.cadastro.consultorios_ativos(Especialidade.CARDIOLOGIA), 0)
        self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        self.cadastro.cadastrar("Dr. Beto", Especialidade.CARDIOLOGIA, 2)
        self.cadastro.cadastrar("Dra. Carla", Especialidade.PEDIATRIA, 3)

        self.assertEqual(self.cadastro.consultorios_ativos(Especialidade.CARDIOLOGIA), 2)
        self.assertEqual(self.cadastro.consultorios_ativos(Especialidade.PEDIATRIA), 1)

    def test_alterar_lista_retornada_nao_altera_cadastro_interno(self):
        ana = self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        retornada = self.cadastro.listar()
        retornada.clear()
        retornada.append(Especialista("Dr. Beto", Especialidade.PEDIATRIA, 2))

        self.assertEqual(self.cadastro.listar(), [ana])
        self.assertIsNone(self.cadastro.buscar_por_consultorio(2))
        self.assertEqual(self.cadastro.consultorios_ativos(Especialidade.CARDIOLOGIA), 1)

    def test_aceita_consultorios_nas_bordas_1_e_12(self):
        primeiro = self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        ultimo = self.cadastro.cadastrar("Dr. Beto", Especialidade.PEDIATRIA, 12)
        self.assertEqual(self.cadastro.buscar_por_consultorio(1), primeiro)
        self.assertEqual(self.cadastro.buscar_por_consultorio(12), ultimo)

    def test_nome_e_salvo_sem_espacos_nas_pontas(self):
        especialista = self.cadastro.cadastrar("  Dra. Ana  ", Especialidade.CARDIOLOGIA, 1)
        self.assertEqual(especialista.nome, "Dra. Ana")

    def test_cadastra_tres_especialistas_em_cada_uma_das_quatro_especialidades(self):
        consultorio = 1
        for especialidade in Especialidade:
            for numero in range(3):
                self.cadastro.cadastrar(
                    f"Dr. {especialidade.name} {numero}", especialidade, consultorio)
                consultorio += 1
        self.assertEqual(len(self.cadastro.listar()), 12)
        for especialidade in Especialidade:
            self.assertEqual(self.cadastro.consultorios_ativos(especialidade), 3)

    def test_tem_especialista_so_depois_de_cadastrar_na_especialidade(self):
        self.assertFalse(self.cadastro.tem_especialista(Especialidade.CARDIOLOGIA))
        self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        self.assertTrue(self.cadastro.tem_especialista(Especialidade.CARDIOLOGIA))
        self.assertFalse(self.cadastro.tem_especialista(Especialidade.PEDIATRIA))

    def test_especialista_cadastrado_nao_pode_ser_alterado_por_fora(self):
        ana = self.cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        with self.assertRaises(FrozenInstanceError):
            self.cadastro.listar()[0].consultorio = 99
        self.assertEqual(ana.consultorio, 1)
        self.assertEqual(self.cadastro.buscar_por_consultorio(1), ana)


if __name__ == "__main__":
    unittest.main()

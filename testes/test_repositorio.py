"""Testes do repositório SQLite.

Rodar na raiz do projeto: python -m unittest discover
"""
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from clinica.especialistas import Administrador
from clinica.modelos import Especialidade, Especialista, Prioridade, Senha, StatusSenha
from clinica.relatorio import Repositorio


def senha(numero=1, geracao=datetime(2026, 11, 16, 10, 0), **campos):
    base = dict(numero=numero, especialidade=Especialidade.CARDIOLOGIA,
                prioridade=Prioridade.NORMAL, hora_geracao=geracao)
    base.update(campos)
    return Senha(**base)


class TestSenhas(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio(":memory:")

    def tearDown(self):
        self.repo.fechar()

    def test_grava_e_le_todos_os_campos(self):
        ana = Especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        original = senha(
            numero=7, prioridade=Prioridade.GESTANTE, status=StatusSenha.FINALIZADA,
            hora_chamada=datetime(2026, 11, 16, 10, 10), hora_finalizacao=datetime(2026, 11, 16, 10, 40),
            consultorio=1, especialista=ana)
        self.repo.salvar_senha(original)

        lida, = self.repo.listar_senhas(date(2026, 11, 16))
        self.assertEqual(lida, original)

    def test_campos_vazios_voltam_como_none(self):
        self.repo.salvar_senha(senha())
        lida, = self.repo.listar_senhas(date(2026, 11, 16))
        self.assertIsNone(lida.hora_chamada)
        self.assertIsNone(lida.hora_finalizacao)
        self.assertIsNone(lida.consultorio)
        self.assertIsNone(lida.especialista)
        self.assertEqual(lida.status, StatusSenha.AGUARDANDO)

    def test_salvar_de_novo_atualiza_em_vez_de_duplicar(self):
        s = senha()
        self.repo.salvar_senha(s)
        s.status = StatusSenha.NAO_ATENDIDA
        self.repo.salvar_senha(s)

        lidas = self.repo.listar_senhas(date(2026, 11, 16))
        self.assertEqual(len(lidas), 1)
        self.assertEqual(lidas[0].status, StatusSenha.NAO_ATENDIDA)

    def test_numeracao_reiniciada_no_mesmo_dia_nao_sobrescreve(self):
        self.repo.salvar_senha(senha(numero=1, geracao=datetime(2026, 11, 16, 9, 0)))
        self.repo.salvar_senha(senha(numero=1, geracao=datetime(2026, 11, 16, 15, 0)))
        self.assertEqual(len(self.repo.listar_senhas(date(2026, 11, 16))), 2)

    def test_lista_so_o_dia_pedido_na_ordem_de_emissao(self):
        self.repo.salvar_senha(senha(numero=2, geracao=datetime(2026, 11, 16, 11, 0)))
        self.repo.salvar_senha(senha(numero=1, geracao=datetime(2026, 11, 16, 10, 0)))
        self.repo.salvar_senha(senha(numero=1, geracao=datetime(2026, 11, 17, 10, 0)))

        hoje = self.repo.listar_senhas(date(2026, 11, 16))
        self.assertEqual([s.numero for s in hoje], [1, 2])
        self.assertEqual(len(self.repo.listar_senhas(date(2026, 11, 17))), 1)
        self.assertEqual(self.repo.listar_senhas(date(2026, 11, 18)), [])


class TestCadastro(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio(":memory:")

    def tearDown(self):
        self.repo.fechar()

    def test_especialistas_voltam_ordenados_por_consultorio(self):
        self.repo.salvar_especialista(Especialista("Dr. Beto", Especialidade.PEDIATRIA, 5))
        self.repo.salvar_especialista(Especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1))
        self.assertEqual(
            self.repo.listar_especialistas(),
            [Especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1),
             Especialista("Dr. Beto", Especialidade.PEDIATRIA, 5)])

    def test_sem_administrador_devolve_none(self):
        self.assertIsNone(self.repo.carregar_administrador())

    def test_administrador_volta_e_continua_autenticando(self):
        self.repo.salvar_administrador(Administrador("admin", "segredo123"))
        admin = self.repo.carregar_administrador()
        self.assertTrue(admin.autenticar("admin", "segredo123"))
        self.assertFalse(admin.autenticar("admin", "errada"))
        self.assertFalse(admin.autenticar("outro", "segredo123"))

    def test_a_senha_do_administrador_nao_e_gravada(self):
        self.repo.salvar_administrador(Administrador("admin", "segredo123"))
        linhas = self.repo._conexao.execute("SELECT * FROM administrador").fetchall()
        self.assertNotIn(b"segredo123", b"".join(
            v if isinstance(v, bytes) else str(v).encode() for linha in linhas for v in linha))


class TestSegurancaTransacoesERecuperacao(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio(":memory:")

    def tearDown(self):
        self.repo.fechar()

    def test_transacao_em_lote_persiste_tudo_quando_da_certo(self):
        def operacao():
            self.repo.salvar_especialista(Especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1))
            self.repo.salvar_senha(senha(numero=1))
            self.repo.salvar_senha(senha(numero=2))

        self.repo.executar_em_transacao(operacao)

        self.assertTrue(self.repo.verificar_integridade())
        self.assertEqual(len(self.repo.listar_especialistas()), 1)
        self.assertEqual([s.numero for s in self.repo.listar_senhas(date(2026, 11, 16))], [1, 2])

    def test_falha_no_meio_da_operacao_faz_rollback_sem_deixar_metade(self):
        self.repo.salvar_senha(senha(numero=1, status=StatusSenha.AGUARDANDO))

        def operacao_com_falha():
            self.repo.salvar_especialista(Especialista("Dr. Carlos", Especialidade.PEDIATRIA, 2))
            self.repo.salvar_senha(senha(numero=1, status=StatusSenha.FINALIZADA))
            raise RuntimeError("Queda simulada no meio da gravação")

        with self.assertRaises(RuntimeError):
            self.repo.executar_em_transacao(operacao_com_falha)

        self.assertEqual(self.repo.listar_especialistas(), [])
        senhas_dia = self.repo.listar_senhas(date(2026, 11, 16))
        self.assertEqual(len(senhas_dia), 1)
        self.assertEqual(senhas_dia[0].status, StatusSenha.AGUARDANDO)
        self.assertTrue(self.repo.verificar_integridade())

    def test_backup_e_restauracao_explicita_em_disco(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta_path = Path(pasta)
            banco_path = pasta_path / "clinica.db"
            backup_path = pasta_path / "backup" / "clinica_bkp.db"

            repo = Repositorio(banco_path)
            repo.salvar_especialista(Especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1))
            repo.salvar_senha(senha(numero=1, status=StatusSenha.AGUARDANDO))
            repo.criar_backup(backup_path)

            # Altera o banco principal depois do backup (não apaga nem restaura sozinho)
            repo.salvar_senha(senha(numero=1, status=StatusSenha.FINALIZADA))
            repo.salvar_senha(senha(numero=2, status=StatusSenha.AGUARDANDO))
            repo.fechar()

            # Reabre e restaura explicitamente o backup
            repo_restaurado = Repositorio(banco_path)
            repo_restaurado.restaurar_backup(backup_path)

            self.assertTrue(repo_restaurado.verificar_integridade())
            senhas_dia = repo_restaurado.listar_senhas(date(2026, 11, 16))
            self.assertEqual(len(senhas_dia), 1)
            self.assertEqual(senhas_dia[0].status, StatusSenha.AGUARDANDO)
            repo_restaurado.fechar()

    def test_restauracao_invalida_nao_apaga_dados_atuais(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta_path = Path(pasta)
            banco_path = pasta_path / "clinica.db"
            backup_invalido = pasta_path / "corrompido.db"
            backup_invalido.write_bytes(b"nao e um sqlite valido")

            repo = Repositorio(banco_path)
            repo.salvar_senha(senha(numero=10))

            with self.assertRaises(ValueError):
                repo.restaurar_backup(backup_invalido)

            self.assertEqual([s.numero for s in repo.listar_senhas(date(2026, 11, 16))], [10])
            repo.fechar()

    def test_restauracao_de_arquivo_inexistente_nao_mexe_no_banco(self):
        with tempfile.TemporaryDirectory() as pasta:
            repo = Repositorio(Path(pasta) / "clinica.db")
            repo.salvar_senha(senha(numero=10))

            with self.assertRaises(FileNotFoundError):
                repo.restaurar_backup(Path(pasta) / "nao_existe.db")

            self.assertEqual([s.numero for s in repo.listar_senhas(date(2026, 11, 16))], [10])
            repo.fechar()

    def test_restaurar_backup_em_banco_na_memoria_levanta_erro(self):
        with self.assertRaises(RuntimeError):
            self.repo.restaurar_backup("qualquer.db")

    def test_backup_nao_deixa_arquivo_temporario_nem_trava_o_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta_path = Path(pasta)
            repo = Repositorio(pasta_path / "clinica.db")
            repo.salvar_senha(senha(numero=1))

            backup = repo.criar_backup(pasta_path / "bkp" / "copia.db")

            self.assertEqual(list(backup.parent.glob(".*.tmp")), [])
            backup.unlink()  # no Windows falharia se o backup ainda estivesse aberto
            self.assertFalse(backup.exists())
            repo.fechar()


class TestPersistenciaEmDisco(unittest.TestCase):
    def test_dados_continuam_depois_de_fechar_e_reabrir(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "subpasta" / "clinica.db"   # a pasta é criada sozinha
            repo = Repositorio(caminho)
            repo.salvar_senha(senha())
            repo.salvar_especialista(Especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1))
            repo.fechar()

            repo = Repositorio(caminho)
            self.assertEqual(len(repo.listar_senhas(date(2026, 11, 16))), 1)
            self.assertEqual(len(repo.listar_especialistas()), 1)
            repo.fechar()


if __name__ == "__main__":
    unittest.main()
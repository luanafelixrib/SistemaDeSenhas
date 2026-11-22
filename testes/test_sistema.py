"""Testes do Sistema (abertura do dia, administrador, gravação e restauração).

Rodar na raiz do projeto: python -m unittest discover
"""
import tempfile
import unittest
import zipfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

from clinica.modelos import Especialidade, Especialista, Prioridade, Senha, StatusSenha
from clinica.relatorio import Repositorio
from clinica.sistema import Sistema

CARDIO = Especialidade.CARDIOLOGIA
DIA_ANTIGO = date.today() - timedelta(days=6)    # um dia que ficou para trás, qualquer que seja "hoje"


def hora_antiga(hora, minuto):
    return datetime.combine(DIA_ANTIGO, time(hora, minuto))


class BaseSistema(unittest.TestCase):
    def setUp(self):
        self.repo = Repositorio(":memory:")
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.dia = [date.today()]          # relógio falso: mude self.dia[0] para virar o dia

    def abrir(self) -> Sistema:
        """Abre o sistema sobre o mesmo banco: equivale a fechar e reabrir o programa."""
        return Sistema(self.repo, self.pasta, hoje=lambda: self.dia[0])

    def sistema_com_admin_e_especialista(self) -> Sistema:
        sistema = self.abrir()
        sistema.criar_administrador("admin", "segredo")
        sistema.cadastrar_especialista("Dra. Ana", CARDIO, 1)
        return sistema


class TestAdministrador(BaseSistema):
    def test_primeiro_acesso_cria_a_conta_e_entra(self):
        sistema = self.abrir()
        self.assertFalse(sistema.tem_administrador)
        sistema.criar_administrador("admin", "segredo")
        self.assertTrue(sistema.tem_administrador)
        self.assertTrue(sistema.admin_logado)

    def test_nao_cria_um_segundo_administrador(self):
        sistema = self.sistema_com_admin_e_especialista()
        with self.assertRaises(ValueError):
            sistema.criar_administrador("outro", "senha")

    def test_conta_continua_depois_de_reabrir_mas_sem_estar_logado(self):
        self.sistema_com_admin_e_especialista()
        sistema = self.abrir()
        self.assertTrue(sistema.tem_administrador)
        self.assertFalse(sistema.admin_logado)
        self.assertFalse(sistema.entrar_como_admin("admin", "errada"))
        self.assertTrue(sistema.entrar_como_admin("admin", "segredo"))

    def test_sair_do_admin_tira_o_acesso(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.sair_do_admin()
        with self.assertRaises(PermissionError):
            sistema.cadastrar_especialista("Dr. Beto", CARDIO, 2)

    def test_acoes_do_administrador_exigem_login(self):
        sistema = self.abrir()
        with self.assertRaises(PermissionError):
            sistema.cadastrar_especialista("Dra. Ana", CARDIO, 1)
        with self.assertRaises(PermissionError):
            sistema.encerrar_dia()
        with self.assertRaises(PermissionError):
            sistema.relatorio_do_dia()
        with self.assertRaises(PermissionError):
            sistema.iniciar_novo_dia()


class TestCadastro(BaseSistema):
    def test_especialista_cadastrado_volta_ao_reabrir(self):
        self.sistema_com_admin_e_especialista()
        sistema = self.abrir()
        self.assertEqual(sistema.cadastro.listar(), [Especialista("Dra. Ana", CARDIO, 1)])

    def test_cadastro_invalido_nao_vai_para_o_banco(self):
        sistema = self.sistema_com_admin_e_especialista()
        with self.assertRaises(ValueError):          # consultório já ocupado
            sistema.cadastrar_especialista("Dr. Beto", Especialidade.PEDIATRIA, 1)
        self.assertEqual(len(self.repo.listar_especialistas()), 1)


class TestGravacao(BaseSistema):
    def test_cada_etapa_da_senha_fica_gravada(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)
        self.assertEqual(self.repo.listar_senhas(self.dia[0])[0].status, StatusSenha.AGUARDANDO)
        sistema.chamar_proxima(1)
        self.assertEqual(self.repo.listar_senhas(self.dia[0])[0].status, StatusSenha.EM_ATENDIMENTO)
        sistema.finalizar_atendimento(1)
        gravada = self.repo.listar_senhas(self.dia[0])[0]
        self.assertEqual(gravada.status, StatusSenha.FINALIZADA)
        self.assertIsNotNone(gravada.hora_finalizacao)

    def test_encerrar_dia_gera_o_relatorio_em_arquivo(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)
        caminho = sistema.encerrar_dia()
        self.assertEqual(caminho, self.pasta / f"relatorio_{self.dia[0].isoformat()}.txt")
        self.assertIn("Senhas emitidas.................. 1", caminho.read_text(encoding="utf-8"))
        self.assertEqual(self.repo.listar_senhas(self.dia[0])[0].status, StatusSenha.NAO_ATENDIDA)

    def test_nao_encerra_duas_vezes_e_depois_inicia_novo_dia(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.encerrar_dia()
        with self.assertRaises(ValueError):
            sistema.encerrar_dia()
        with self.assertRaises(ValueError):
            sistema.emitir_senha(CARDIO)
        sistema.iniciar_novo_dia()
        sistema.emitir_senha(CARDIO)

    def test_relatorio_do_dia_funciona_com_o_dia_em_andamento(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)
        self.assertIn("Em aberto", sistema.relatorio_do_dia())


class TestExportacao(BaseSistema):
    def sistema_com_uma_senha_atendida(self) -> Sistema:
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)
        sistema.chamar_proxima(1)
        sistema.finalizar_atendimento(1)
        return sistema

    def test_exportar_csv_cria_o_arquivo_na_pasta_dos_relatorios(self):
        sistema = self.sistema_com_uma_senha_atendida()
        caminho = sistema.exportar_relatorio_csv(self.dia[0])
        self.assertEqual(caminho, self.pasta / f"relatorio_{self.dia[0].isoformat()}.csv")
        conteudo = caminho.read_text(encoding="utf-8-sig")
        self.assertIn("N001", conteudo)
        self.assertIn("Dra. Ana", conteudo)

    def test_exportar_excel_cria_o_arquivo_na_pasta_dos_relatorios(self):
        sistema = self.sistema_com_uma_senha_atendida()
        caminho = sistema.exportar_relatorio_excel(self.dia[0])
        self.assertEqual(caminho, self.pasta / f"relatorio_{self.dia[0].isoformat()}.xlsx")
        self.assertTrue(zipfile.is_zipfile(caminho))    # um .xlsx é um zip de XMLs

    def test_exportar_exige_login_de_administrador(self):
        sistema = self.sistema_com_uma_senha_atendida()
        sistema.sair_do_admin()
        with self.assertRaises(PermissionError):
            sistema.exportar_relatorio_csv(self.dia[0])
        with self.assertRaises(PermissionError):
            sistema.exportar_relatorio_excel(self.dia[0])

    def test_exportar_dia_sem_senhas_gera_so_o_cabecalho(self):
        sistema = self.sistema_com_admin_e_especialista()
        caminho = sistema.exportar_relatorio_csv(self.dia[0])
        linhas = caminho.read_text(encoding="utf-8-sig").strip().splitlines()
        self.assertEqual(len(linhas), 1)


class TestRestauracao(BaseSistema):
    """Fechar e reabrir o programa no meio do dia não pode perder a fila (RNF05)."""

    def test_fila_painel_e_numeracao_voltam(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)                          # N001
        sistema.emitir_senha(CARDIO)                          # N002
        sistema.emitir_senha(CARDIO, Prioridade.GESTANTE)     # P003
        sistema.chamar_proxima(1)                             # P003 em atendimento

        sistema = self.abrir()                                # "reabriu o programa"

        linha = next(l for l in sistema.painel.linhas() if l.especialidade == CARDIO)
        self.assertEqual((linha.senha, linha.consultorio), ("P003", 1))
        self.assertEqual(sistema.gerenciador.pessoas_a_frente(CARDIO, 1), 0)
        self.assertEqual(sistema.gerenciador.pessoas_a_frente(CARDIO, 2), 1)
        self.assertEqual(sistema.emitir_senha(CARDIO).numero, 4)     # numeração continua

    def test_atendimento_em_andamento_volta_para_o_consultorio(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)
        sistema.chamar_proxima(1)

        sistema = self.abrir()
        with self.assertRaises(ValueError):                   # o consultório continua ocupado
            sistema.chamar_proxima(1)
        senha = sistema.finalizar_atendimento(1)
        self.assertEqual((senha.codigo, senha.status), ("N001", StatusSenha.FINALIZADA))

    def test_ordem_de_chamada_e_mantida_depois_de_reabrir(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)                          # N001
        sistema.emitir_senha(CARDIO, Prioridade.OBESO)        # P002
        sistema.emitir_senha(CARDIO, Prioridade.IDOSO_80)     # P003
        sistema.emitir_senha(CARDIO)                          # N004

        sistema = self.abrir()
        chamadas = []
        for _ in range(4):
            chamadas.append(sistema.chamar_proxima(1).codigo)
            sistema.finalizar_atendimento(1)
        self.assertEqual(chamadas, ["P003", "P002", "N001", "N004"])

    def test_reabrir_nao_grava_nada_de_novo(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)
        antes = self.repo.listar_senhas(self.dia[0])
        self.abrir()
        self.assertEqual(self.repo.listar_senhas(self.dia[0]), antes)


class TestDiasAnteriores(BaseSistema):
    def senha_antiga(self, numero, status, **campos):
        return Senha(numero, CARDIO, Prioridade.NORMAL, status,
                     hora_geracao=hora_antiga(9, numero), **campos)

    def test_dia_que_ficou_aberto_e_fechado_ao_iniciar(self):
        ana = Especialista("Dra. Ana", CARDIO, 1)
        self.repo.salvar_senha(self.senha_antiga(1, StatusSenha.AGUARDANDO))
        self.repo.salvar_senha(self.senha_antiga(
            2, StatusSenha.EM_ATENDIMENTO, hora_chamada=hora_antiga(9, 30),
            consultorio=1, especialista=ana))
        self.repo.salvar_senha(self.senha_antiga(
            3, StatusSenha.FINALIZADA, hora_chamada=hora_antiga(9, 10),
            hora_finalizacao=hora_antiga(9, 40), consultorio=1, especialista=ana))

        sistema = self.abrir()

        self.assertEqual(sistema.dias_fechados_ao_iniciar, [DIA_ANTIGO])
        self.assertTrue((self.pasta / f"relatorio_{DIA_ANTIGO.isoformat()}.txt").exists())
        n1, n2, n3 = self.repo.listar_senhas(DIA_ANTIGO)
        self.assertEqual(n1.status, StatusSenha.NAO_ATENDIDA)
        self.assertEqual(n2.status, StatusSenha.FINALIZADA)
        self.assertIsNone(n2.hora_finalizacao)               # fora da média
        self.assertIsNotNone(n3.hora_finalizacao)            # a finalizada de verdade é mantida

    def test_dia_ja_fechado_nao_e_refeito(self):
        self.repo.salvar_senha(self.senha_antiga(1, StatusSenha.AGUARDANDO))
        self.abrir()
        self.assertEqual(self.abrir().dias_fechados_ao_iniciar, [])

    def test_dia_de_hoje_nao_e_fechado_ao_iniciar(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.emitir_senha(CARDIO)
        self.assertEqual(self.abrir().dias_fechados_ao_iniciar, [])


class TestViradaDoDia(BaseSistema):
    def test_sem_mudanca_de_data_nao_faz_nada(self):
        sistema = self.sistema_com_admin_e_especialista()
        self.assertIsNone(sistema.verificar_virada_do_dia())

    def test_data_mudou_encerra_o_dia_anterior_e_abre_o_novo(self):
        sistema = self.sistema_com_admin_e_especialista()
        anterior = self.dia[0]
        sistema.emitir_senha(CARDIO)                          # fica aguardando

        self.dia[0] = anterior + timedelta(days=1)
        caminho = sistema.verificar_virada_do_dia()

        self.assertEqual(caminho, self.pasta / f"relatorio_{anterior.isoformat()}.txt")
        self.assertTrue(caminho.exists())
        self.assertEqual(self.repo.listar_senhas(anterior)[0].status, StatusSenha.NAO_ATENDIDA)
        self.assertEqual(sistema.emitir_senha(CARDIO).numero, 1)   # dia novo, numeração nova

    def test_dia_ja_encerrado_pelo_administrador_so_reabre(self):
        sistema = self.sistema_com_admin_e_especialista()
        sistema.encerrar_dia()
        self.dia[0] += timedelta(days=1)
        self.assertIsNone(sistema.verificar_virada_do_dia())
        sistema.emitir_senha(CARDIO)                          # não dá erro: o dia foi reaberto


if __name__ == "__main__":
    unittest.main()

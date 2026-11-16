"""Testes do relatório diário e da gravação automática pelo GerenciadorFilas.

Rodar na raiz do projeto: python -m unittest discover
"""
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from clinica.especialistas import CadastroEspecialistas
from clinica.filas import GerenciadorFilas
from clinica.modelos import Especialidade, Especialista, Prioridade, Senha, StatusSenha
from clinica.relatorio import Relatorio, Repositorio, resumir

DIA = date(2026, 11, 16)
ANA = Especialista("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
BETO = Especialista("Dr. Beto", Especialidade.CARDIOLOGIA, 2)


def hora(h, m):
    return datetime(2026, 11, 16, h, m)


def senhas_do_dia():
    """4 senhas com horários conhecidos.

    N001 Cardiologia: espera 10 min, atendimento 30 min (Ana)
    P002 Cardiologia (gestante): espera 15 min, atendimento 20 min (Beto)
    N003 Pediatria: não atendida
    N004 Cardiologia: espera 19 min, encerrada automaticamente (sem hora de finalização)
    """
    return [
        Senha(1, Especialidade.CARDIOLOGIA, Prioridade.NORMAL, StatusSenha.FINALIZADA,
              hora(10, 0), hora(10, 10), hora(10, 40), 1, ANA),
        Senha(2, Especialidade.CARDIOLOGIA, Prioridade.GESTANTE, StatusSenha.FINALIZADA,
              hora(10, 5), hora(10, 20), hora(10, 40), 2, BETO),
        Senha(3, Especialidade.PEDIATRIA, Prioridade.NORMAL, StatusSenha.NAO_ATENDIDA,
              hora(10, 30)),
        Senha(4, Especialidade.CARDIOLOGIA, Prioridade.NORMAL, StatusSenha.FINALIZADA,
              hora(10, 31), hora(10, 50), None, 1, ANA),
    ]


def repositorio_com(senhas):
    repo = Repositorio(":memory:")
    for s in senhas:
        repo.salvar_senha(s)
    return repo


class TestResumo(unittest.TestCase):
    def test_contagens_e_medias(self):
        r = resumir(senhas_do_dia())
        self.assertEqual((r.emitidas, r.atendidas, r.nao_atendidas, r.em_aberto), (4, 3, 1, 0))
        self.assertAlmostEqual(r.espera_media, (10 + 15 + 19) / 3)
        # a duração ignora o atendimento sem hora de finalização: (30 + 20) / 2
        self.assertAlmostEqual(r.duracao_media, 25.0)

    def test_sem_dados_nao_quebra(self):
        r = resumir([])
        self.assertEqual((r.emitidas, r.atendidas), (0, 0))
        self.assertIsNone(r.espera_media)
        self.assertIsNone(r.duracao_media)

    def test_senhas_aguardando_contam_como_em_aberto(self):
        aguardando = Senha(1, Especialidade.PEDIATRIA, Prioridade.NORMAL, hora_geracao=hora(9, 0))
        r = resumir([aguardando])
        self.assertEqual((r.em_aberto, r.atendidas, r.nao_atendidas), (1, 0, 0))
        self.assertIsNone(r.espera_media)


class TestTextoDoRelatorio(unittest.TestCase):
    def setUp(self):
        self.texto = Relatorio(repositorio_com(senhas_do_dia())).gerar_texto(DIA)

    def test_cabecalho_com_a_data(self):
        self.assertIn("RELATÓRIO DE ATENDIMENTO - 16/11/2026", self.texto)

    def test_resumo_do_dia(self):
        self.assertIn("Senhas emitidas.................. 4", self.texto)
        self.assertIn("Atendidas........................ 3", self.texto)
        self.assertIn("Não atendidas.................... 1", self.texto)
        self.assertIn("14,7 min", self.texto)    # espera média
        self.assertIn("25,0 min", self.texto)    # duração média
        self.assertNotIn("Em aberto", self.texto)

    def test_tem_as_tres_secoes(self):
        for titulo in ("POR ESPECIALIDADE", "POR PRIORIDADE", "POR ESPECIALISTA"):
            self.assertIn(titulo, self.texto)

    def test_por_especialidade_e_prioridade(self):
        self.assertIn("Cardiologia", self.texto)
        self.assertIn("Pediatria", self.texto)
        self.assertNotIn("Ginecologia", self.texto)   # nenhuma senha nesse dia
        self.assertIn("Gestantes", self.texto)
        self.assertIn("Normal", self.texto)

    def test_por_especialista(self):
        self.assertIn("Consultório 1", self.texto)
        self.assertIn("Dra. Ana", self.texto)
        self.assertIn("Dr. Beto", self.texto)

    def test_avisa_sobre_atendimento_encerrado_automaticamente(self):
        self.assertIn("Obs.: 1 atendimento(s)", self.texto)

    def test_dia_sem_senhas(self):
        texto = Relatorio(Repositorio(":memory:")).gerar_texto(DIA)
        self.assertIn("Nenhuma senha foi emitida neste dia.", texto)

    def test_dia_em_andamento_mostra_em_aberto(self):
        aguardando = Senha(1, Especialidade.PEDIATRIA, Prioridade.NORMAL, hora_geracao=hora(9, 0))
        texto = Relatorio(repositorio_com([aguardando])).gerar_texto(DIA)
        self.assertIn("Em aberto (dia em andamento)..... 1", texto)
        self.assertNotIn("POR ESPECIALISTA", texto)


class TestArquivo(unittest.TestCase):
    def test_salva_o_txt_em_utf8_com_a_data_no_nome(self):
        relatorio = Relatorio(repositorio_com(senhas_do_dia()))
        with tempfile.TemporaryDirectory() as pasta:
            caminho = relatorio.salvar_arquivo(DIA, Path(pasta) / "relatorios")
            self.assertEqual(caminho.name, "relatorio_2026-11-16.txt")
            conteudo = caminho.read_text(encoding="utf-8")
        self.assertIn("RELATÓRIO DE ATENDIMENTO", conteudo)
        self.assertEqual(conteudo, relatorio.gerar_texto(DIA))


class TestGravacaoAutomatica(unittest.TestCase):
    """GerenciadorFilas + Repositorio: o relatório sai do que foi gravado durante o dia."""

    def setUp(self):
        self.repo = Repositorio(":memory:")
        cadastro = CadastroEspecialistas()
        cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        self.gerenciador = GerenciadorFilas(cadastro, ao_mudar=self.repo.salvar_senha)

    def test_avisa_a_cada_mudanca_de_estado(self):
        avisos = []
        cadastro = CadastroEspecialistas()
        cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        gerenciador = GerenciadorFilas(cadastro, ao_mudar=lambda s: avisos.append(s.status))

        gerenciador.emitir_senha(Especialidade.CARDIOLOGIA)
        gerenciador.chamar_proxima(1)
        gerenciador.finalizar_atendimento(1)
        self.assertEqual(avisos, [StatusSenha.AGUARDANDO, StatusSenha.EM_ATENDIMENTO,
                                  StatusSenha.FINALIZADA])

    def test_funciona_sem_ninguem_ouvindo(self):
        cadastro = CadastroEspecialistas()
        cadastro.cadastrar("Dra. Ana", Especialidade.CARDIOLOGIA, 1)
        GerenciadorFilas(cadastro).emitir_senha(Especialidade.CARDIOLOGIA)   # não deve dar erro

    def test_dia_completo_fica_gravado(self):
        g = self.gerenciador
        for _ in range(3):
            g.emitir_senha(Especialidade.CARDIOLOGIA)
        g.chamar_proxima(1)
        g.finalizar_atendimento(1)      # N001: finalizada normalmente
        g.chamar_proxima(1)             # N002: fica aberta até o fim do dia
        g.encerrar_dia()                # N002 finalizada à força, N003 não atendida

        n1, n2, n3 = self.repo.listar_senhas(date.today())
        self.assertEqual([n1.status, n2.status, n3.status],
                         [StatusSenha.FINALIZADA, StatusSenha.FINALIZADA, StatusSenha.NAO_ATENDIDA])
        self.assertIsNotNone(n1.hora_finalizacao)
        self.assertEqual(n1.especialista.nome, "Dra. Ana")
        self.assertIsNone(n2.hora_finalizacao)      # encerrada automaticamente
        self.assertIsNone(n3.hora_chamada)

    def test_relatorio_do_dia_gravado_automaticamente(self):
        g = self.gerenciador
        g.emitir_senha(Especialidade.CARDIOLOGIA, Prioridade.PCD)
        g.chamar_proxima(1)
        g.finalizar_atendimento(1)
        texto = Relatorio(self.repo).gerar_texto(date.today())
        self.assertIn("Senhas emitidas.................. 1", texto)
        self.assertIn("PCD", texto)

    def test_finalizacao_automatica_nao_define_hora(self):
        g = self.gerenciador
        g.emitir_senha(Especialidade.CARDIOLOGIA)
        g.chamar_proxima(1)
        senha = g.finalizar_atendimento(1, automatico=True)
        self.assertEqual(senha.status, StatusSenha.FINALIZADA)
        self.assertIsNone(senha.hora_finalizacao)


if __name__ == "__main__":
    unittest.main()

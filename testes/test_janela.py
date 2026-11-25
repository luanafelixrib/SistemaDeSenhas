"""Testes da interface gráfica. Precisam de tela e do Tkinter; sem isso, são pulados.

Rodar na raiz do projeto: python -m unittest discover
"""
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

from clinica.modelos import Especialidade, Prioridade, Senha, StatusSenha
from clinica.relatorio import Repositorio
from clinica.sistema import Sistema

try:
    import tkinter as tk
    from clinica.interface.janela import Dialogos, Janela
    _raiz = tk.Tk()
    _raiz.destroy()
    TEM_TELA = True
except Exception:          # sem Tkinter instalado ou sem ambiente gráfico
    TEM_TELA = False
    Dialogos = object

CARDIO = Especialidade.CARDIOLOGIA


class DialogosFalsos(Dialogos):
    """Guarda as mensagens em vez de abrir caixas na tela."""

    def __init__(self, confirma=True):
        self.infos, self.erros, self.confirma = [], [], confirma

    def info(self, texto):
        self.infos.append(texto)

    def erro(self, texto):
        self.erros.append(texto)

    def confirmar(self, texto):
        return self.confirma


def estado(widget) -> str:
    return str(widget.cget("state"))


@unittest.skipUnless(TEM_TELA, "sem Tkinter ou sem tela")
class BaseJanela(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.pasta = Path(pasta.name)
        self.repo = Repositorio(":memory:")
        self.sistema = Sistema(self.repo, self.pasta)
        self.dialogos = DialogosFalsos()
        self.janela = Janela(self.sistema, self.dialogos)
        self.addCleanup(self.janela.destroy)

    def com_cardiologia(self):
        """Cadastra a Dra. Ana (Cardiologia, consultório 1) e sai da área do administrador."""
        self.sistema.criar_administrador("admin", "segredo")
        self.sistema.cadastrar_especialista("Dra. Ana", CARDIO, 1)
        self.sistema.sair_do_admin()
        self.janela.atualizar_tudo()

    def logar_admin(self):
        self.sistema.criar_administrador("admin", "segredo")
        self.janela.atualizar_tudo()


class TestAbaPaciente(BaseJanela):
    def test_sem_especialista_as_opcoes_ficam_desabilitadas(self):
        aba = self.janela.aba_paciente
        for botao in aba.botoes_especialidade.values():
            self.assertEqual(estado(botao), "disabled")
        self.assertIn("(sem especialista)", aba.botoes_especialidade[CARDIO].cget("text"))

    def test_so_a_especialidade_com_especialista_fica_habilitada(self):
        self.com_cardiologia()
        botoes = self.janela.aba_paciente.botoes_especialidade
        self.assertEqual(estado(botoes[CARDIO]), "normal")
        self.assertEqual(estado(botoes[Especialidade.PEDIATRIA]), "disabled")

    def test_retirar_sem_escolher_especialidade(self):
        self.com_cardiologia()
        self.janela.aba_paciente.retirar()
        self.assertEqual(self.dialogos.erros, ["Escolha uma especialidade."])

    def test_senha_normal(self):
        self.com_cardiologia()
        aba = self.janela.aba_paciente
        aba._especialidade.set(CARDIO.name)
        aba.retirar()
        self.assertEqual(aba._codigo.get(), "N001")
        self.assertIn("Cardiologia", aba._detalhes.get())
        self.assertIn("Pessoas à frente: 0", aba._detalhes.get())

    def test_senha_prioritaria_escolhendo_o_tipo(self):
        self.com_cardiologia()
        aba = self.janela.aba_paciente
        self.assertEqual(estado(aba.combo_prioridade), "disabled")
        aba._especialidade.set(CARDIO.name)
        aba._tipo.set("P")
        aba._atualizar_tipo()
        self.assertEqual(estado(aba.combo_prioridade), "readonly")
        aba.combo_prioridade.current(3)                       # Gestantes
        aba.retirar()
        self.assertEqual(aba._codigo.get(), "P001")
        senha = self.repo.listar_senhas(date.today())[0]
        self.assertEqual(senha.prioridade, Prioridade.GESTANTE)

    def test_prioritaria_passa_na_frente_e_mostra_pessoas_a_frente(self):
        self.com_cardiologia()
        aba = self.janela.aba_paciente
        aba._especialidade.set(CARDIO.name)
        aba.retirar()                                          # N001
        aba._tipo.set("P")
        aba._atualizar_tipo()
        aba.combo_prioridade.current(0)                        # Idosos 80+
        aba.retirar()                                          # P002 vai para a frente
        self.assertIn("Pessoas à frente: 0", aba._detalhes.get())


class TestAbaPainel(BaseJanela):
    def valores(self, especialidade):
        for item in self.janela.aba_painel.tabela.get_children():
            valores = self.janela.aba_painel.tabela.item(item, "values")
            if valores[0] == especialidade.value:
                return [str(v) for v in valores]

    def test_mostra_uma_linha_por_especialidade(self):
        self.janela.aba_painel.atualizar()
        self.assertEqual(len(self.janela.aba_painel.tabela.get_children()), len(Especialidade))
        self.assertEqual(self.valores(CARDIO)[6], "indisponível")

    def test_mostra_a_ultima_chamada(self):
        self.com_cardiologia()
        self.sistema.emitir_senha(CARDIO)
        self.sistema.emitir_senha(CARDIO)
        self.sistema.chamar_proxima(1)
        self.janela.aba_painel.atualizar()
        self.assertEqual(self.valores(CARDIO),
                         ["Cardiologia", "N001", "Normal", "1", "1", "N002", "~30 min"])


class TestAbaEspecialista(BaseJanela):
    def escolher(self, consultorio):
        aba = self.janela.aba_especialista
        aba.combo_consultorio.set(str(consultorio))
        aba.atualizar()
        return aba

    def test_sem_escolher_consultorio_os_botoes_ficam_desabilitados(self):
        aba = self.janela.aba_especialista
        self.assertEqual(estado(aba.botao_chamar), "disabled")
        self.assertEqual(estado(aba.botao_finalizar), "disabled")

    def test_consultorio_sem_especialista(self):
        aba = self.escolher(5)
        self.assertIn("Nenhum especialista", aba._quem.get())
        self.assertEqual(estado(aba.botao_chamar), "disabled")

    def test_chamar_e_finalizar(self):
        self.com_cardiologia()
        self.sistema.emitir_senha(CARDIO)
        aba = self.escolher(1)
        self.assertEqual(aba._quem.get(), "Dra. Ana - Cardiologia")
        self.assertEqual(estado(aba.botao_chamar), "normal")

        aba.chamar()
        self.assertEqual(aba._situacao.get(), "Em atendimento: senha N001")
        self.assertEqual(estado(aba.botao_chamar), "disabled")
        self.assertEqual(estado(aba.botao_finalizar), "normal")

        aba.finalizar()
        self.assertEqual(aba._situacao.get(), "Consultório livre.")
        self.assertEqual(estado(aba.botao_chamar), "normal")
        self.assertEqual(self.repo.listar_senhas(date.today())[0].status, StatusSenha.FINALIZADA)

    def test_chamar_sem_senhas_aguardando_avisa(self):
        self.com_cardiologia()
        aba = self.escolher(1)
        aba.chamar()
        self.assertEqual(self.dialogos.infos, ["Não há senhas aguardando nesta especialidade."])
        self.assertEqual(aba._situacao.get(), "Consultório livre.")


class TestAbaAdministrador(BaseJanela):
    def test_primeiro_acesso_cria_a_conta(self):
        aba = self.janela.aba_administrador
        self.assertEqual(aba._texto_botao_login.get(), "Criar conta")
        aba._usuario.set("admin")
        aba._senha.set("segredo")
        aba._repita.set("segredo")
        aba.entrar()
        self.assertTrue(self.sistema.admin_logado)
        self.assertEqual(aba._quadro_area.winfo_manager(), "pack")
        self.assertEqual(aba._quadro_login.winfo_manager(), "")

    def test_senhas_diferentes_no_primeiro_acesso(self):
        aba = self.janela.aba_administrador
        aba._usuario.set("admin")
        aba._senha.set("segredo")
        aba._repita.set("outra")
        aba.entrar()
        self.assertEqual(self.dialogos.erros, ["As senhas não conferem."])
        self.assertFalse(self.sistema.tem_administrador)

    def test_login_errado_e_certo(self):
        self.sistema.criar_administrador("admin", "segredo")
        self.sistema.sair_do_admin()
        aba = self.janela.aba_administrador
        aba.atualizar()
        self.assertEqual(aba._texto_botao_login.get(), "Entrar")
        aba._usuario.set("admin")
        aba._senha.set("errada")
        aba.entrar()
        self.assertEqual(self.dialogos.erros, ["Usuário ou senha incorretos."])
        aba._senha.set("segredo")
        aba.entrar()
        self.assertTrue(self.sistema.admin_logado)

    def test_cadastrar_especialista_atualiza_lista_e_aba_do_paciente(self):
        self.logar_admin()
        aba = self.janela.aba_administrador
        aba._nome.set("Dra. Ana")
        aba.combo_especialidade.current(3)                     # Cardiologia
        aba.combo_consultorio.current(0)                       # consultório 1
        aba.cadastrar()
        self.assertEqual(len(aba.tabela.get_children()), 1)
        self.assertEqual(estado(self.janela.aba_paciente.botoes_especialidade[CARDIO]), "normal")
        self.assertEqual(len(self.repo.listar_especialistas()), 1)

    def test_cadastro_invalido_mostra_o_erro(self):
        self.logar_admin()
        aba = self.janela.aba_administrador
        aba.cadastrar()                                        # nada escolhido
        self.assertEqual(self.dialogos.erros, ["Escolha a especialidade e o consultório."])
        aba._nome.set("")
        aba.combo_especialidade.current(3)
        aba.combo_consultorio.current(0)
        aba.cadastrar()                                        # nome vazio
        self.assertEqual(len(self.dialogos.erros), 2)
        self.assertEqual(self.repo.listar_especialistas(), [])

    def test_encerrar_dia_gera_o_relatorio_na_tela_e_em_arquivo(self):
        self.com_cardiologia()
        self.sistema.emitir_senha(CARDIO)
        self.sistema.entrar_como_admin("admin", "segredo")
        self.janela.atualizar_tudo()
        aba = self.janela.aba_administrador
        aba.encerrar_dia()
        self.assertIn("RELATÓRIO DE ATENDIMENTO", aba.texto_relatorio.get("1.0", "end"))
        self.assertEqual(len(list(self.pasta.glob("relatorio_*.txt"))), 1)
        self.assertIn("Dia encerrado", self.dialogos.infos[-1])

    def test_encerrar_dia_cancelado_nao_faz_nada(self):
        self.com_cardiologia()
        self.sistema.entrar_como_admin("admin", "segredo")
        self.dialogos.confirma = False
        self.janela.aba_administrador.encerrar_dia()
        self.assertEqual(list(self.pasta.glob("relatorio_*.txt")), [])
        self.assertFalse(self.sistema.gerenciador.dia_encerrado)

    def test_depois_de_encerrar_o_botao_de_chamar_fica_desabilitado_ate_novo_dia(self):
        self.com_cardiologia()
        self.sistema.emitir_senha(CARDIO)
        self.sistema.entrar_como_admin("admin", "segredo")
        aba_esp = self.janela.aba_especialista
        aba_esp.combo_consultorio.set("1")
        self.janela.aba_administrador.encerrar_dia()
        self.assertEqual(estado(aba_esp.botao_chamar), "disabled")
        self.janela.aba_administrador.iniciar_novo_dia()
        self.assertEqual(estado(aba_esp.botao_chamar), "normal")

    def test_sair_da_area_volta_para_o_login(self):
        self.logar_admin()
        aba = self.janela.aba_administrador
        aba.sair()
        self.assertFalse(self.sistema.admin_logado)
        self.assertEqual(aba._quadro_login.winfo_manager(), "pack")


@unittest.skipUnless(TEM_TELA, "sem Tkinter ou sem tela")
class TestAoAbrir(unittest.TestCase):
    def test_avisa_quando_um_dia_anterior_foi_fechado_ao_iniciar(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        repo = Repositorio(":memory:")
        antigo = date.today() - timedelta(days=6)
        repo.salvar_senha(Senha(1, CARDIO, Prioridade.NORMAL,
                                hora_geracao=datetime.combine(antigo, time(9, 0))))
        janela = Janela(Sistema(repo, pasta.name), DialogosFalsos())
        self.addCleanup(janela.destroy)
        self.assertIn(f"{antigo:%d/%m/%Y}", janela._status.get())


if __name__ == "__main__":
    unittest.main()

"""Testes unitários do Administrador (RF09 e RNF06).

Rodar na raiz do projeto: python -m unittest testes.test_administrador
"""
import unittest

from clinica.especialistas import Administrador


class TestCriacao(unittest.TestCase):
    def test_rejeita_usuario_vazio_ou_so_com_espacos(self):
        for usuario in ("", "   ", "\t\n"):
            with self.subTest(usuario=usuario), self.assertRaises(ValueError):
                Administrador(usuario, "senha123")

    def test_rejeita_senha_vazia(self):
        with self.assertRaises(ValueError):
            Administrador("admin", "")

    def test_guarda_o_usuario_sem_espacos_nas_pontas(self):
        admin = Administrador("  admin  ", "senha123")
        self.assertEqual(admin.usuario, "admin")

    def test_senha_so_com_espaco_e_valida_porque_a_senha_nao_leva_strip(self):
        admin = Administrador("admin", " ")
        self.assertTrue(admin.autenticar("admin", " "))
        self.assertFalse(admin.autenticar("admin", "  "))


class TestAutenticacao(unittest.TestCase):
    def setUp(self):
        self.admin = Administrador("admin", "senha123")

    def test_autentica_com_usuario_e_senha_corretos(self):
        self.assertTrue(self.admin.autenticar("admin", "senha123"))

    def test_rejeita_senha_errada(self):
        self.assertFalse(self.admin.autenticar("admin", "errada"))

    def test_rejeita_usuario_errado(self):
        self.assertFalse(self.admin.autenticar("outro", "senha123"))

    def test_rejeita_usuario_e_senha_errados(self):
        self.assertFalse(self.admin.autenticar("outro", "errada"))

    def test_rejeita_senha_vazia_sem_levantar_erro(self):
        self.assertFalse(self.admin.autenticar("admin", ""))

    def test_usuario_digitado_com_espacos_nas_pontas_ainda_autentica(self):
        self.assertTrue(self.admin.autenticar("  admin ", "senha123"))

    def test_senha_diferencia_maiusculas_de_minusculas(self):
        self.assertFalse(self.admin.autenticar("admin", "SENHA123"))


class TestArmazenamento(unittest.TestCase):
    """RNF06: só salt e hash podem ser guardados, nunca a senha em texto."""

    def setUp(self):
        self.admin = Administrador("admin", "senha123")

    def test_senha_nao_aparece_em_nenhum_atributo(self):
        for valor in vars(self.admin).values():
            texto = valor.decode("latin-1") if isinstance(valor, bytes) else str(valor)
            self.assertNotIn("senha123", texto)

    def test_dados_para_guardar_devolve_usuario_salt_e_hash(self):
        usuario, salt, hash_senha = self.admin.dados_para_guardar()
        self.assertEqual(usuario, "admin")
        self.assertEqual(len(salt), 16)       # os.urandom(16)
        self.assertEqual(len(hash_senha), 32)  # sha256 gera 32 bytes
        self.assertNotEqual(hash_senha, b"senha123")

    def test_mesma_senha_em_duas_contas_gera_salt_e_hash_diferentes(self):
        outro = Administrador("admin", "senha123")
        _, salt_a, hash_a = self.admin.dados_para_guardar()
        _, salt_b, hash_b = outro.dados_para_guardar()
        self.assertNotEqual(salt_a, salt_b)
        self.assertNotEqual(hash_a, hash_b)

    def test_restaurar_recria_a_conta_sem_precisar_da_senha_original(self):
        restaurado = Administrador.restaurar(*self.admin.dados_para_guardar())
        self.assertEqual(restaurado.usuario, "admin")
        self.assertTrue(restaurado.autenticar("admin", "senha123"))

    def test_conta_restaurada_continua_rejeitando_credenciais_erradas(self):
        restaurado = Administrador.restaurar(*self.admin.dados_para_guardar())
        self.assertFalse(restaurado.autenticar("admin", "errada"))
        self.assertFalse(restaurado.autenticar("outro", "senha123"))


if __name__ == "__main__":
    unittest.main()

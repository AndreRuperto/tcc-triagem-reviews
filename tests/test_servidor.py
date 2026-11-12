"""Testes do servidor local dos paineis (src/servidor.py)."""

import http.client
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from src import servidor


class TestServidor(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        raiz = Path(self.pasta.name)
        (raiz / "steam").mkdir()
        (raiz / "painel.html").write_text("<p>exemplo</p>", encoding="utf-8")
        (raiz / "steam" / "painel.html").write_text("<p>steam</p>", encoding="utf-8")
        self.srv = servidor.criar_servidor(raiz, 0)   # porta 0 = qualquer porta livre
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.pasta.cleanup()

    def pedir(self, metodo, caminho):
        """Requisição sem seguir redirecionamento: (status, Location, corpo)."""
        conexao = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1])
        conexao.request(metodo, caminho)
        resposta = conexao.getresponse()
        corpo = resposta.read().decode("utf-8")
        conexao.close()
        return resposta.status, resposta.getheader("Location"), corpo

    def test_pagina_inicial_lista_os_paineis_pelas_rotas(self):
        with urllib.request.urlopen(self.base + "/") as r:
            corpo = r.read().decode("utf-8")
        self.assertIn('href="/steam"', corpo)
        self.assertIn('href="/exemplo"', corpo)

    def test_rota_limpa_serve_o_painel(self):
        self.assertEqual(self.pedir("GET", "/steam"), (200, None, "<p>steam</p>"))
        self.assertEqual(self.pedir("GET", "/exemplo"), (200, None, "<p>exemplo</p>"))
        self.assertEqual(self.pedir("HEAD", "/steam")[0], 200)

    def test_endereco_antigo_redireciona_mantendo_a_consulta(self):
        self.assertEqual(self.pedir("GET", "/steam/painel.html")[:2], (301, "/steam"))
        self.assertEqual(self.pedir("GET", "/painel.html?x=1")[:2], (301, "/exemplo?x=1"))
        self.assertEqual(self.pedir("GET", "/steam/")[:2], (301, "/steam"))

    def test_rota_que_nao_existe_da_404(self):
        self.assertEqual(self.pedir("GET", "/nao-existe")[0], 404)

    def test_nao_sai_da_pasta_nem_lista_arquivos(self):
        # ".." é resolvido dentro da pasta de relatórios (como o navegador faz), nunca fora dela
        self.assertEqual(self.pedir("GET", "/%2e%2e/%2e%2e/etc/passwd")[0], 404)
        self.assertEqual(self.pedir("GET", "/../steam")[0], 200)
        (Path(self.pasta.name) / "dados").mkdir()
        (Path(self.pasta.name) / "dados" / "a.csv").write_text("x", encoding="utf-8")
        self.assertEqual(self.pedir("GET", "/dados/")[0], 404)        # sem listagem de pasta
        self.assertEqual(self.pedir("GET", "/dados/a.csv")[0], 200)   # arquivo pedido pelo nome continua

    def test_nome_da_rota(self):
        self.assertEqual(servidor.rota_do_painel("steam/painel.html"), "/steam")
        self.assertEqual(servidor.rota_do_painel("coletas/fev/painel.html"), "/coletas/fev")
        self.assertEqual(servidor.rota_do_painel("painel.html"), "/exemplo")

    def test_pagina_inicial_resume_cada_painel(self):
        dados = {"total": 400, "com_indicador": 50, "por_jogo": {"A": {}, "B": {}}, "gerado": "12/11/2026 10:00",
                 "versao_base": "1.1", "periodo": ["2026-02-04", "2026-11-10"]}
        html = '<script type="application/json" id="dados">' + json.dumps(dados) + "</script>"
        (Path(self.pasta.name) / "steam" / "painel.html").write_text(html, encoding="utf-8")
        with urllib.request.urlopen(self.base + "/") as r:
            corpo = r.read().decode("utf-8")
        self.assertIn("400 reviews de 2 jogos, 12,5% com algum indicador", corpo)
        self.assertIn("escritos entre 04/02/2026 e 10/11/2026", corpo)
        self.assertIn("gerado em 12/11/2026 10:00, base de conhecimento v1.1", corpo)
        self.assertIn(":root[data-tema=\"escuro\"]", corpo)   # mesmos tokens de tema do painel

    def test_painel_sem_dados_nao_quebra_a_pagina_inicial(self):
        self.assertEqual(servidor.resumo_do_painel(Path(self.pasta.name) / "painel.html")["total"], None)

    def test_serve_o_painel_sem_cache(self):
        with urllib.request.urlopen(self.base + "/steam") as r:
            self.assertEqual(r.read().decode("utf-8"), "<p>steam</p>")
            self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_escuta_so_na_maquina_local_por_padrao(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()

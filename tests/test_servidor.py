"""Testes do servidor local dos paineis (src/servidor.py)."""

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

    def test_pagina_inicial_lista_os_paineis(self):
        with urllib.request.urlopen(self.base + "/") as r:
            corpo = r.read().decode("utf-8")
        self.assertIn('href="steam/painel.html"', corpo)
        self.assertIn('href="painel.html"', corpo)

    def test_serve_o_painel_sem_cache(self):
        with urllib.request.urlopen(self.base + "/steam/painel.html") as r:
            self.assertEqual(r.read().decode("utf-8"), "<p>steam</p>")
            self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_escuta_so_na_maquina_local_por_padrao(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()

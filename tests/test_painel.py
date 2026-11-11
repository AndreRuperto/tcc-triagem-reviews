"""Testes do painel HTML (src/painel.py)."""

import json
import re
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src import painel


def dados_do_html(html: str) -> dict:
    bruto = re.search(r'<script type="application/json" id="dados">(.*?)</script>', html, re.S).group(1)
    return json.loads(bruto.replace("<\\/", "</"))


class TestMarcarTrechos(unittest.TestCase):
    def test_literal_com_acento_e_maiusculas_aponta_o_texto_original(self):
        texto = "O jogo FECHA   Sozinho e a protagonista não é atraente."
        trechos = painel.marcar_trechos(texto, ["fecha sozinho"], ["nao e atraente"])
        self.assertEqual([texto[a:b] for a, b, _, _ in trechos], ["FECHA   Sozinho", "não é atraente"])
        self.assertEqual([(g, r) for _, _, g, r in trechos], [("t", False), ("a", False)])

    def test_casamento_pelo_radical(self):
        texto = "Comecou a LAGAR demais"
        trechos = painel.marcar_trechos(texto, ["lag (via radical)"], [])
        self.assertEqual([(texto[a:b], g, r) for a, b, g, r in trechos], [("LAGAR", "t", True)])

    def test_nao_marca_pedaco_de_palavra(self):
        self.assertEqual(painel.marcar_trechos("um flagrante", ["lag"], []), [])


class TestGerarPainel(unittest.TestCase):
    def classificados(self):
        return pd.DataFrame({
            "id_review": ["1", "2"], "jogo": ["J1", "J2"],
            "texto_original": ["Travando toda hora", "<script>alert(1)</script> rosto feio"],
            "escore_tecnico": [2, 0], "escore_afetivo": [0, 3],
            "indicadores_tecnicos": ["travando", ""], "indicadores_afetivos": ["", "rosto feio"],
            "categoria": ["Tecnico", "Afetivo-visual"], "confianca": [1.0, 1.0],
            "regra_acionada": ["R1", "R2"], "versao_base": ["1.1", "1.1"], "recomendado": ["nao", "nao"],
        })

    def test_gera_html_com_os_dados_e_sem_injetar_o_texto(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.classificados().to_csv(Path(pasta) / "reviews_classificados.csv", index=False, encoding="utf-8-sig")
            html = painel.gerar_painel(Path(pasta)).read_text(encoding="utf-8")
        # o texto do review so aparece escapado dentro do JSON, nunca como tag
        self.assertNotIn("<script>alert(1)</script>", html)
        dados = dados_do_html(html)
        self.assertEqual(dados["total"], 2)
        self.assertEqual(dados["geral"]["Tecnico"], 1)
        self.assertEqual(dados["por_jogo"]["J2"]["Afetivo-visual"], 1)
        self.assertEqual(dados["indicadores"]["a"], [["rosto feio", 1]])
        self.assertIsNone(dados["avaliacao"])
        r2 = [r for r in dados["reviews"] if r["id"] == "2"][0]
        self.assertEqual(r2["texto"][r2["marcas"][0][0]:r2["marcas"][0][1]], "rosto feio")

    def test_inclui_a_avaliacao_quando_existe(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            self.classificados().to_csv(pasta / "reviews_classificados.csv", index=False, encoding="utf-8-sig")
            (pasta / "avaliacao").mkdir()
            pd.DataFrame({"categoria": ["Tecnico", "Afetivo-visual", "Misto", "Indefinido"],
                          "precisao": [1.0, 1.0, 0, 0], "revocacao": [1.0, 1.0, 0, 0],
                          "f1": [1.0, 1.0, 0, 0], "suporte": [1, 1, 0, 0]}).to_csv(pasta / "avaliacao" / "metricas.csv", index=False)
            pd.DataFrame([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
                         index=["manual:Tecnico", "manual:Afetivo-visual", "manual:Misto", "manual:Indefinido"],
                         columns=["sistema:Tecnico", "sistema:Afetivo-visual", "sistema:Misto", "sistema:Indefinido"]
                         ).to_csv(pasta / "avaliacao" / "matriz_confusao.csv")
            (pasta / "avaliacao" / "resumo.txt").write_text("Kappa de Cohen entre anotadores: 0.8100 (n=2)\n", encoding="utf-8")
            dados = dados_do_html(painel.gerar_painel(pasta).read_text(encoding="utf-8"))
        av = dados["avaliacao"]
        self.assertEqual((av["n"], av["acuracia"], av["f1_macro"], av["kappa"]), (2, 1.0, 1.0, 0.81))


if __name__ == "__main__":
    unittest.main()

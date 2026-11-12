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

    def test_achado_e_contexto_da_coleta(self):
        df = self.classificados()
        df["categoria"] = ["Tecnico", "Indefinido"]
        df["data_criacao"] = ["2025-02-16", "2025-01-30"]
        df["idioma"] = ["brazilian", "brazilian"]
        df["votos_util"] = [0, 3]
        dados = painel.montar_dados(df)
        self.assertEqual(dados["com_indicador"], 1)
        self.assertEqual(dados["periodo"], ["2025-01-30", "2025-02-16"])
        self.assertEqual(dados["idiomas"], ["português (Brasil)"])
        self.assertEqual(dados["fonte"], "Steam")
        self.assertEqual(dados["titulo"], painel.TITULO)

    def test_sem_colunas_da_steam_o_contexto_fica_vazio(self):
        dados = painel.montar_dados(self.classificados())
        self.assertEqual((dados["periodo"], dados["idiomas"], dados["fonte"]), (None, [], ""))
        self.assertEqual(dados["com_indicador"], 2)

    def test_recomendacao_por_categoria_e_por_jogo(self):
        df = self.classificados()
        df["recomendado"] = ["sim", "nao"]
        dados = painel.montar_dados(df)
        self.assertEqual(dados["recomendacao"]["Tecnico"], {"sim": 1, "nao": 0})
        self.assertEqual(dados["recomendacao"]["Afetivo-visual"], {"sim": 0, "nao": 1})
        self.assertEqual(dados["rec_por_jogo"], {"J1": [1, 1], "J2": [0, 1]})

    def test_sem_recomendacao_nao_ha_secao(self):
        df = self.classificados().drop(columns=["recomendado"])
        dados = painel.montar_dados(df)
        self.assertIsNone(dados["recomendacao"])
        self.assertEqual(dados["rec_por_jogo"], {})

    def test_celula_vazia_nao_vira_nan(self):
        df = self.classificados()
        df["recomendado"] = [float("nan"), "sim"]
        df["data_criacao"] = [float("nan"), "2025-02-01"]
        r1 = [r for r in painel.montar_dados(df)["reviews"] if r["id"] == "1"][0]
        self.assertEqual((r1["rec"], r1["data"]), ("", ""))

    def test_lista_completa_de_indicadores_ordenada(self):
        df = pd.concat([self.classificados()] * 3, ignore_index=True)
        df["id_review"] = [str(i) for i in range(len(df))]
        df.loc[0, "indicadores_tecnicos"] = "travando; bug (via radical)"
        ind = painel.montar_dados(df)["indicadores"]["t"]
        self.assertEqual([list(par) for par in ind], [["travando", 3], ["bug", 1]])

    def test_metadados_da_steam_no_review(self):
        df = self.classificados()
        df["votos_util"] = [3, float("nan")]
        df["horas_na_review"] = [12.5, ""]
        r = {x["id"]: x for x in painel.montar_dados(df)["reviews"]}
        self.assertEqual((r["1"]["util"], r["1"]["horas"]), (3, 12.5))
        self.assertEqual((r["2"]["util"], r["2"]["horas"]), (None, None))

    def test_rotulos_manuais_deixam_a_matriz_clicavel(self):
        av = {"n": 1, "acuracia": 1.0, "f1_macro": 1.0, "kappa": None, "metricas": [], "matriz": [],
              "rotulos": {"1": "Tecnico"}}
        dados = painel.montar_dados(self.classificados(), av)
        r = {x["id"]: x for x in dados["reviews"]}
        self.assertTrue(dados["clicavel"])
        self.assertEqual((r["1"]["man"], r["2"]["man"]), ("Tecnico", ""))
        self.assertNotIn("rotulos", dados["avaliacao"])   # nao vai duplicado no HTML
        self.assertIn("rotulos", av)                      # e o dict de quem chamou nao e alterado

    def test_html_tem_temas_e_cabecalho_de_impressao(self):
        dados = painel.montar_dados(self.classificados())
        dados["titulo"] = 'Título com "aspas"'
        html = painel.montar_html(dados)
        self.assertNotIn("__TOKENS_", html)
        self.assertNotIn("__CABECALHO_IMPRESSAO__", html)
        # tema escuro: pelo sistema (se não forçado claro) e forçado pelo seletor
        self.assertIn(':root:not([data-tema="claro"])', html)
        self.assertIn(':root[data-tema="escuro"]', html)
        self.assertEqual(html.count(painel.TOKENS_ESCURO), 2)
        # impressão sempre no tema claro, com o título escapado no cabeçalho da página
        self.assertIn('@top-left { content: "Título com \\"aspas\\", base de conhecimento v1.1', html)
        self.assertIn('id="b-apresentacao"', html)

    def test_indice_aponta_para_secoes_que_existem(self):
        html = painel.montar_html(painel.montar_dados(self.classificados()))
        alvos = re.findall(r'<a href="#(sec-[a-z]+)">', html)
        self.assertEqual(len(alvos), 7)
        for alvo in alvos:
            self.assertIn(f'id="{alvo}"', html)

    def test_marcador_dentro_de_um_review_nao_e_substituido(self):
        df = self.classificados()
        df.loc[0, "texto_original"] = "texto com __TOKENS_CLARO__ dentro"
        html = painel.montar_html(painel.montar_dados(df))
        self.assertIn("__TOKENS_CLARO__ dentro", dados_do_html(html)["reviews"][0]["texto"])

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

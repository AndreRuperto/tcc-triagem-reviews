"""Testes da coleta (com a API simulada), da amostragem e da avaliacao."""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src import amostragem, avaliacao, coleta_steam


def review_api(rid, texto, positivo=False, horas_min=120):
    return {
        "recommendationid": str(rid), "review": texto, "voted_up": positivo,
        "timestamp_created": 1767225600,  # 2026-01-01 UTC
        "votes_up": 3, "votes_funny": 1, "language": "brazilian",
        "steam_purchase": True, "received_for_free": False,
        "author": {"steamid": "76561190000000000", "playtime_forever": horas_min},
    }


def pagina(**campos):
    """Uma pagina no formato da GetAppReviews: tudo dentro de "response"."""
    return {"response": campos}


class RespostaFalsa:
    status_code = 200

    def __init__(self, dados):
        self.dados = dados

    def raise_for_status(self):
        pass

    def json(self):
        return self.dados


class SessaoFalsa:
    """Devolve as paginas na ordem e registra os cursores pedidos."""

    def __init__(self, paginas):
        self.paginas, self.cursores, self.headers = list(paginas), [], {}
        self.urls, self.entradas = [], []

    def get(self, url, params, timeout):
        self.urls.append(url)
        entrada = json.loads(params["input_json"])
        self.entradas.append(entrada)
        self.cursores.append(entrada["cursor"])
        return RespostaFalsa(self.paginas.pop(0) if self.paginas else {"response": {"reviews": [], "cursor": "fim"}})


class TestColetaSteam(unittest.TestCase):
    def test_converte_sem_gravar_o_autor(self):
        linha = coleta_steam.converter_review(review_api(7, "Fecha sozinho", horas_min=90), "Jogo X")
        self.assertEqual(linha["id_review"], "7")
        self.assertEqual(linha["recomendado"], "nao")
        self.assertEqual(linha["data_criacao"], "2026-01-01")
        self.assertEqual(linha["horas_jogadas"], 1.5)
        self.assertEqual(linha["horas_na_review"], 0.0)
        self.assertNotIn("76561190000000000", str(linha))
        self.assertEqual(set(linha), set(coleta_steam.COLUNAS))

    def test_pagina_pelo_cursor_e_para_no_maximo(self):
        sessao = SessaoFalsa([
            pagina(cursor="c1", reviews=[review_api(1, "a"), review_api(2, "b")]),
            pagina(cursor="c2", reviews=[review_api(3, "c"), review_api(4, "d")]),
        ])
        linhas = coleta_steam.coletar(10, "J", maximo=3, pausa=0, sessao=sessao)
        self.assertEqual([l["id_review"] for l in linhas], ["1", "2", "3"])
        self.assertEqual(sessao.cursores, ["*", "c1"])

    def test_pede_a_api_nova_com_enums_numericos_e_review_bombing_incluido(self):
        sessao = SessaoFalsa([pagina(cursor="c1", reviews=[review_api(1, "a")])])
        coleta_steam.coletar(2651280, "J", maximo=1, pausa=0, sessao=sessao)
        self.assertEqual(sessao.urls[0], "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/")
        e = sessao.entradas[0]
        self.assertEqual(e["appid"], 2651280)
        self.assertEqual(e["filter"], 1)              # recent
        self.assertEqual(e["languages"], ["brazilian"])
        self.assertEqual(e["purchase_type"], 1)       # todas as compras
        self.assertEqual(e["review_type"], 0)         # positivas e negativas
        self.assertIs(e["filter_offtopic_activity"], False)

    def test_opcoes_de_ordenacao(self):
        e = json.loads(coleta_steam.montar_parametros("*", "brazilian", "helpful", 1)["input_json"])
        self.assertEqual((e["filter"], e["day_range"]), (0, 0))
        e = json.loads(coleta_steam.montar_parametros("*", "brazilian", "recent", 1, False)["input_json"])
        self.assertIs(e["filter_offtopic_activity"], True)
        self.assertNotIn("day_range", e)
        with self.assertRaises(ValueError):
            coleta_steam.montar_parametros("*", "brazilian", "all", 1)

    def test_periodo_vira_timestamps_utc(self):
        e = json.loads(coleta_steam.montar_parametros("*", "brazilian", "recent", 1,
                                                      periodo=("2025-01-30", "2025-02-28"))["input_json"])
        self.assertEqual(e["date_range_start"], 1738195200)   # 2025-01-30 00:00:00 UTC
        self.assertEqual(e["date_range_end"], 1740787199)     # 2025-02-28 23:59:59 UTC

    def test_lote_usa_o_periodo_de_cada_jogo(self):
        sessao = SessaoFalsa([pagina(cursor="c1", reviews=[review_api(1, "a")])])
        with tempfile.TemporaryDirectory() as pasta:
            coleta_steam.coletar_lote([{"appid": 5, "jogo": "J", "periodo": ["2025-01-30", "2025-02-28"]}],
                                      1, "brazilian", "recent", Path(pasta), pausa=0, sessao=sessao)
        self.assertEqual(sessao.entradas[0]["date_range_start"], 1738195200)

    def test_para_quando_a_api_repete_reviews(self):
        sessao = SessaoFalsa([pagina(cursor="c1", reviews=[review_api(1, "a")]),
                              pagina(cursor="c2", reviews=[review_api(1, "a")])])
        linhas = coleta_steam.coletar(10, "J", maximo=100, pausa=0, sessao=sessao)
        self.assertEqual(len(linhas), 1)

    def test_informa_total_disponivel(self):
        sessao = SessaoFalsa([pagina(cursor="c1", query_summary={"total_reviews": 873},
                                     reviews=[review_api(1, "a")])])
        info = {}
        coleta_steam.coletar(10, "J", maximo=1, pausa=0, sessao=sessao, info=info)
        self.assertEqual(info["total_disponivel"], 873)

    def test_resposta_que_nao_e_json(self):
        class RespostaHtml(RespostaFalsa):
            def json(self):
                raise ValueError("Expecting value")
        sessao = SessaoFalsa([])
        sessao.get = lambda url, params, timeout: RespostaHtml(None)
        with self.assertRaisesRegex(RuntimeError, "nao devolveu JSON"):
            coleta_steam.coletar(10, "J", maximo=5, pausa=0, sessao=sessao)

    def test_lote_segue_quando_um_jogo_falha(self):
        sessao = SessaoFalsa([
            {"erro": "sem response"},
            pagina(cursor="c1", query_summary={"total_reviews": 2},
                   reviews=[review_api(1, "a"), review_api(2, "b")]),
        ])
        jogos = [{"appid": 1, "jogo": "Ruim"}, {"appid": 2, "jogo": "Bom"}]
        with tempfile.TemporaryDirectory() as pasta:
            resumo = coleta_steam.coletar_lote(jogos, 5, "brazilian", "recent", Path(pasta), pausa=0, sessao=sessao)
            self.assertTrue((Path(pasta) / "steam_2.csv").exists())
            self.assertFalse((Path(pasta) / "steam_1.csv").exists())
        self.assertTrue(resumo[0]["erro"])
        self.assertEqual((resumo[1]["coletadas"], resumo[1]["disponiveis"], resumo[1]["erro"]), (2, 2, ""))

    def test_limite_de_requisicoes(self):
        class Resposta429(RespostaFalsa):
            status_code = 429
        sessao = SessaoFalsa([])
        sessao.get = lambda url, params, timeout: Resposta429(None)
        with self.assertRaisesRegex(RuntimeError, "429"):
            coleta_steam.coletar(10, "J", maximo=5, pausa=0, sessao=sessao)

    def test_lista_de_jogos_do_projeto_e_valida(self):
        with open(Path(__file__).resolve().parent.parent / "config" / "jogos.json", encoding="utf-8") as f:
            jogos = json.load(f)["jogos"]
        self.assertTrue(jogos)
        for jogo in jogos:
            self.assertIsInstance(jogo["appid"], int)
            self.assertTrue(jogo["jogo"])

    def test_falha_da_api(self):
        sessao = SessaoFalsa([{"erro": "sem response"}])
        with self.assertRaisesRegex(RuntimeError, "inesperada"):
            coleta_steam.coletar(10, "J", maximo=5, pausa=0, sessao=sessao)


def classificados_falsos():
    cats = ["Indefinido"] * 60 + ["Tecnico"] * 30 + ["Afetivo-visual"] * 7 + ["Misto"] * 3
    return pd.DataFrame({
        "id_review": [str(i) for i in range(len(cats))],
        "jogo": "J", "texto_original": [f"texto {i}" for i in range(len(cats))],
        "categoria": cats,
    })


class TestAmostragem(unittest.TestCase):
    def test_tamanho_e_minimo_por_categoria(self):
        amostra = amostragem.sortear_amostra(classificados_falsos(), 40, minimo_por_categoria=10)
        contagem = amostra["categoria"].value_counts()
        self.assertEqual(len(amostra), 40)
        self.assertEqual(amostra["id_review"].nunique(), 40)
        self.assertEqual(contagem["Misto"], 3)            # tinha menos que o minimo: entram todos
        self.assertEqual(contagem["Afetivo-visual"], 7)
        self.assertGreaterEqual(contagem["Tecnico"], 10)

    def test_tamanho_menor_que_a_soma_dos_minimos(self):
        amostra = amostragem.sortear_amostra(classificados_falsos(), 5, minimo_por_categoria=15)
        self.assertEqual(len(amostra), 5)
        self.assertEqual(amostra["categoria"].nunique(), 4)   # todas as categorias continuam representadas

    def test_reprodutivel(self):
        a = amostragem.sortear_amostra(classificados_falsos(), 30)
        b = amostragem.sortear_amostra(classificados_falsos(), 30)
        self.assertEqual(list(a["id_review"]), list(b["id_review"]))

    def test_planilha_cega_nao_mostra_o_sistema(self):
        planilha = amostragem.planilha_cega(amostragem.sortear_amostra(classificados_falsos(), 20))
        self.assertEqual(list(planilha.columns), amostragem.COLUNAS_ROTULAGEM)
        self.assertTrue((planilha["categoria_manual"] == "").all())


class TestAvaliacao(unittest.TestCase):
    def setUp(self):
        self.classificados = pd.DataFrame({
            "id_review": ["1", "2", "3", "4"], "jogo": "J",
            "texto_original": ["a", "b", "c", "d"],
            "categoria": ["Tecnico", "Tecnico", "Afetivo-visual", "Indefinido"],
            "indicadores_tecnicos": ["bug", "lag", "", ""], "indicadores_afetivos": ["", "", "rosto feio", ""],
            "regra_acionada": ["R1", "R1", "R2", "R4"],
        })

    def test_padroniza_categorias(self):
        self.assertEqual(avaliacao.padronizar_categoria(" Técnico "), "Tecnico")
        self.assertEqual(avaliacao.padronizar_categoria("afetivo visual"), "Afetivo-visual")
        self.assertEqual(avaliacao.padronizar_categoria("M"), "Misto")
        self.assertEqual(avaliacao.padronizar_categoria(float("nan")), "")
        with self.assertRaises(ValueError):
            avaliacao.padronizar_categoria("talvez")

    def test_metricas_e_divergencias(self):
        gabarito = pd.DataFrame({"id_review": ["1", "2", "3", "4"],
                                 "categoria_manual": ["Tecnico", "Indefinido", "Afetivo-visual", "Indefinido"]})
        with tempfile.TemporaryDirectory() as pasta:
            r = avaliacao.avaliar(self.classificados, gabarito, destino=Path(pasta))
            for nome in ["metricas.csv", "matriz_confusao.csv", "matriz_confusao.png", "divergencias.csv",
                         "comparacao.csv", "resumo.txt"]:
                self.assertTrue((Path(pasta) / nome).exists(), nome)
            comparacao = pd.read_csv(Path(pasta) / "comparacao.csv", encoding="utf-8-sig", dtype=str)
            self.assertEqual(list(comparacao.columns), ["id_review", "categoria_manual", "categoria"])
            self.assertEqual(len(comparacao), 4)
        self.assertEqual(r["acuracia"], 0.75)
        tec = r["por_categoria"].set_index("categoria").loc["Tecnico"]
        self.assertEqual(tec["precisao"], 0.5)
        self.assertEqual(tec["revocacao"], 1.0)
        self.assertEqual(list(r["divergencias"]["id_review"]), ["2"])
        self.assertEqual(r["matriz"].loc["manual:Indefinido", "sistema:Tecnico"], 1)

    def test_id_inexistente_no_gabarito(self):
        gabarito = pd.DataFrame({"id_review": ["99"], "categoria_manual": ["Tecnico"]})
        with self.assertRaises(ValueError):
            avaliacao.avaliar(self.classificados, gabarito)

    def test_kappa_entre_anotadores(self):
        a = pd.DataFrame({"id_review": ["1", "2", "3", "4"], "categoria_manual": ["Tecnico", "Tecnico", "Misto", "Indefinido"]})
        b = pd.DataFrame({"id_review": ["1", "2", "3", "4"], "categoria_manual": ["Tecnico", "Tecnico", "Misto", "Indefinido"]})
        r = avaliacao.avaliar(self.classificados, a, segundo=b)
        self.assertEqual(r["kappa"], 1.0)

    def test_ignora_linhas_ainda_nao_rotuladas(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "g.csv"
            pd.DataFrame({"id_review": ["1", "2"], "texto_original": ["a", "b"],
                          "categoria_manual": ["T", ""], "observacao": ["", ""]}).to_csv(caminho, index=False)
            self.assertEqual(list(avaliacao.ler_gabarito(caminho)["id_review"]), ["1"])

    def test_gabarito_vazio_da_erro_claro(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "g.csv"
            pd.DataFrame({"id_review": ["1"], "categoria_manual": [""]}).to_csv(caminho, index=False)
            with self.assertRaisesRegex(ValueError, "nenhuma linha"):
                avaliacao.ler_gabarito(caminho)


if __name__ == "__main__":
    unittest.main()

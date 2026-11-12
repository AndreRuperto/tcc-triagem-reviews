"""
Testes do sistema especialista. Rodar na raiz do projeto com:

    python -m unittest discover -s tests

Usam a base de conhecimento real (config/base_conhecimento.json), para
que qualquer alteracao de indicadores ou pesos que quebre um caso
documentado seja percebida.
"""

import json
import unittest
from pathlib import Path

from src.classificador import (
    apply_decision_rule,
    calculate_confidence,
    find_indicators,
    normalize_text,
    classify_review,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent

with (PROJECT_DIR / "config" / "base_conhecimento.json").open(encoding="utf-8") as f:
    KB = json.load(f)


def classify(text):
    return classify_review(text, KB)


class TestNormalizacao(unittest.TestCase):
    def test_remove_acentos_pontuacao_e_links(self):
        self.assertEqual(
            normalize_text("Não ABRE!! veja https://x.com/a"), "nao abre veja"
        )

    def test_valor_nulo(self):
        self.assertEqual(normalize_text(None), "")


class TestRegrasDeDecisao(unittest.TestCase):
    def test_matriz_de_classificacao(self):
        self.assertEqual(apply_decision_rule(2, 0), ("Tecnico", "R1"))
        self.assertEqual(apply_decision_rule(0, 2), ("Afetivo-visual", "R2"))
        self.assertEqual(apply_decision_rule(1, 3), ("Misto", "R3"))
        self.assertEqual(apply_decision_rule(0, 0), ("Indefinido", "R4"))

    def test_confianca(self):
        self.assertEqual(calculate_confidence(0, 0), 0.0)
        self.assertEqual(calculate_confidence(3, 0), 1.0)
        self.assertEqual(calculate_confidence(1, 3), 0.75)


class TestSemDuplaContagem(unittest.TestCase):
    """Indicadores com o mesmo radical contam uma unica vez (v1.2/v1.3)."""

    def test_literal_do_segundo_indicador(self):
        # "fecha sozinho" casava via radical e "fechando sozinho"
        # literalmente: antes da v1.3 o escore era 6.
        r = classify("O jogo esta fechando sozinho")
        self.assertEqual(r["escore_tecnico"], 3)
        self.assertEqual(r["indicadores_tecnicos"], "fechando sozinho")

    def test_literal_do_primeiro_indicador(self):
        r = classify("O jogo fecha sozinho")
        self.assertEqual(r["escore_tecnico"], 3)
        self.assertEqual(r["indicadores_tecnicos"], "fecha sozinho")

    def test_singular_e_plural(self):
        self.assertEqual(classify("Muitos bugs")["escore_tecnico"], 1)
        self.assertEqual(classify("Um bug")["escore_tecnico"], 1)

    def test_travamento(self):
        self.assertEqual(classify("Travamento constante")["escore_tecnico"], 2)

    def test_ordem_da_base_nao_altera_escore(self):
        invertida = dict(reversed(list(KB["tecnico"].items())))
        texto = normalize_text("fechando sozinho e muitos bugs")
        self.assertEqual(
            find_indicators(texto, invertida)[0],
            find_indicators(texto, KB["tecnico"])[0],
        )


class TestCasamentoPorRadical(unittest.TestCase):
    def test_variacao_morfologica(self):
        r = classify("Fechou sozinho no meio da fase")
        self.assertEqual(r["categoria"], "Tecnico")
        self.assertIn("(via radical)", r["indicadores_tecnicos"])

    def test_radical_curto_demais_nao_casa(self):
        # RSLP reduz "trava" e "trem" a "tr"; "trem" nao e indicador.
        self.assertEqual(classify("O trem chegou atrasado")["categoria"], "Indefinido")

    def test_trava_casa_literalmente(self):
        self.assertEqual(classify("O jogo trava toda hora")["categoria"], "Tecnico")


class TestCasosDocumentados(unittest.TestCase):
    """Os 7 reviews de data/reviews_entrada.csv."""

    def test_review_3_e_misto(self):
        # docs/observacoes_teste_v1.md: o RSLP nao aproxima "cai" de
        # "caiu", entao a base v1.1 cadastra "servidor cai".
        r = classify("O servidor cai e a protagonista parece um homem.")
        self.assertEqual(r["categoria"], "Misto")
        self.assertEqual(r["regra_acionada"], "R3")

    def test_demais_reviews(self):
        esperados = {
            "O jogo fecha sozinho durante a primeira fase.": "Tecnico",
            "A personagem principal tem um rosto estranho.": "Afetivo-visual",
            "Gostei da historia e da jogabilidade.": "Indefinido",
            "Travando toda hora, impossivel jogar.": "Tecnico",
            "Personagem feia e sem feminilidade nenhuma.": "Afetivo-visual",
            "Otimo jogo, recomendo bastante.": "Indefinido",
        }
        for texto, categoria in esperados.items():
            with self.subTest(texto=texto):
                self.assertEqual(classify(texto)["categoria"], categoria)


class TestLimitacoesConhecidas(unittest.TestCase):
    """
    Comportamentos sabidamente errados, mantidos para documentar as
    limitacoes do metodo (capitulo 6.3 do TCC). Se algum destes testes
    falhar depois de uma melhoria, atualize-o e a documentacao.
    """

    def test_negacao_nao_e_tratada(self):
        self.assertEqual(classify("O jogo nao tem bug nenhum")["categoria"], "Tecnico")


if __name__ == "__main__":
    unittest.main()

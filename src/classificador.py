"""
Modulo do sistema especialista: normalizacao de texto, calculo de
escores, aplicacao de regras de decisao e calculo de confianca.

Ver TCC - Capitulo 3.5 (Etapa 4: classificacao por IA simbolica)
e Apendice A (pseudocodigo) para a fundamentacao teorica completa.

v1.1: adiciona normalizacao morfologica (stemming RSLP) como camada
complementar a comparacao literal, para tratar variacoes de conjugacao
verbal e flexao de genero/numero nao previstas na base de conhecimento
(ex: "fecha sozinho" vs "fechando sozinho"). O stemming e uma tecnica
simbolica/deterministica (reducao ao radical por regras linguisticas
explicitas), nao envolve interpretacao semantica ou aprendizado
estatistico, preservando a auditabilidade da classificacao (RNF3).

v1.2: corrige dupla contagem de indicadores diferentes que reduzem
ao mesmo radical (ex: "fecha sozinho" e "fechando sozinho"), que
inflava o escore ao contar duas vezes a mesma variacao morfologica
de um unico conceito. Ver docs/observacoes_teste_v1.md.
"""

import re
import unicodedata

import nltk
from nltk.stem import RSLPStemmer

try:
    nltk.data.find("stemmers/rslp")
except LookupError:
    nltk.download("rslp")

_stemmer = RSLPStemmer()


def remove_accents(value: str) -> str:
    """Remove acentos de uma string, preservando as letras base."""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    )


def normalize_text(value) -> str:
    """
    Padroniza o texto para comparacao com os indicadores:
    minusculas, sem acentos, sem links, sem pontuacao.
    A versao original do comentario NUNCA e alterada (RNF5 do TCC).
    """
    if value is None:
        return ""

    text = str(value).lower()
    text = remove_accents(text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def stem_phrase(phrase: str) -> str:
    """
    Aplica o stemmer RSLP a cada palavra de uma expressao normalizada,
    reduzindo cada termo ao seu radical (ex: "caindo" -> "caind").
    Obs.: o RSLP NAO une "cai" e "caiu" (cada um fica como esta); por
    isso "servidor cai" foi cadastrado explicitamente na base.
    """
    return " ".join(_stemmer.stem(word) for word in phrase.split())


def find_indicators(text: str, indicators: dict) -> tuple:
    """
    Verifica quais indicadores de um grupo estao presentes no texto,
    em duas etapas:

    1) Comparacao literal (expressao exata, como no TCC original)
    2) Comparacao por radical (stemming), aplicada apenas se a etapa 1
       nao encontrar o indicador.

    Indicadores diferentes que reduzem ao MESMO radical (ex: "fecha
    sozinho" e "fechando sozinho") sao contados apenas UMA vez, para
    evitar dupla contagem de variacoes morfologicas do mesmo conceito.

    O metodo de casamento (literal ou via radical) fica registrado
    para fins de auditoria.
    """
    score = 0
    found = []
    stemmed_text = stem_phrase(text)
    matched_stems = set()

    for indicator, weight in indicators.items():
        normalized_indicator = normalize_text(indicator)
        stemmed_indicator = stem_phrase(normalized_indicator)

        literal_pattern = (
            r"(?<![a-z0-9])" + re.escape(normalized_indicator) + r"(?![a-z0-9])"
        )
        if re.search(literal_pattern, text):
            score += int(weight)
            found.append(indicator)
            matched_stems.add(stemmed_indicator)
            continue

        if stemmed_indicator in matched_stems:
            # Ja contabilizado por outro indicador com o mesmo radical
            # nesta mesma chamada - evita dupla contagem.
            continue

        stem_pattern = (
            r"(?<![a-z0-9])" + re.escape(stemmed_indicator) + r"(?![a-z0-9])"
        )
        if stemmed_indicator and re.search(stem_pattern, stemmed_text):
            score += int(weight)
            found.append(f"{indicator} (via radical)")
            matched_stems.add(stemmed_indicator)

    return score, found


def calculate_confidence(technical_score: int, affective_score: int) -> float:
    """
    Calcula o nivel de confianca conforme formula 3.3 do TCC.
    """
    total = technical_score + affective_score
    if total == 0:
        return 0.0
    return round(max(technical_score, affective_score) / total, 4)


def apply_decision_rule(technical_score: int, affective_score: int) -> tuple:
    """
    Aplica a matriz de classificacao (Tabela 3 do TCC).
    """
    if technical_score > 0 and affective_score == 0:
        return "Tecnico", "R1"
    if affective_score > 0 and technical_score == 0:
        return "Afetivo-visual", "R2"
    if technical_score > 0 and affective_score > 0:
        return "Misto", "R3"
    return "Indefinido", "R4"


def classify_review(original_text, knowledge_base: dict) -> dict:
    """
    Funcao principal: classifica um comentario com base na base de
    conhecimento, retornando escore, indicadores, categoria, regra
    e nivel de confianca.
    """
    normalized_text = normalize_text(original_text)

    technical_score, technical_indicators = find_indicators(
        normalized_text, knowledge_base["tecnico"]
    )
    affective_score, affective_indicators = find_indicators(
        normalized_text, knowledge_base["afetivo_visual"]
    )

    category, rule = apply_decision_rule(technical_score, affective_score)
    confidence = calculate_confidence(technical_score, affective_score)

    return {
        "texto_padronizado": normalized_text,
        "escore_tecnico": technical_score,
        "escore_afetivo": affective_score,
        "indicadores_tecnicos": "; ".join(technical_indicators),
        "indicadores_afetivos": "; ".join(affective_indicators),
        "categoria": category,
        "confianca": confidence,
        "regra_acionada": rule,
    }

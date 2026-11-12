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

v1.3: a correcao da v1.2 dependia da ordem dos indicadores na base
(se o casamento por radical vinha antes do literal, o escore ainda era
somado duas vezes). Agora o casamento literal roda para todos os
indicadores antes do casamento por radical. Radicais de uma unica
palavra com menos de 3 letras deixam de casar sozinhos (overstemming
do RSLP, ex: "trava" e "trem" -> "tr"). Ver docs/decisao_stemming.md.
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

    prepared = []
    for indicator, weight in indicators.items():
        normalized_indicator = normalize_text(indicator)
        prepared.append(
            (indicator, int(weight), normalized_indicator, stem_phrase(normalized_indicator))
        )

    # Etapa 1: comparacao literal. Roda para TODOS os indicadores antes
    # da etapa por radical, para que o casamento exato tenha prioridade
    # no registro de auditoria independentemente da ordem na base.
    for indicator, weight, normalized_indicator, stemmed_indicator in prepared:
        if stemmed_indicator in matched_stems:
            # Mesmo radical ja contabilizado (ex: "bug" e "bugs").
            continue
        if _contains(text, normalized_indicator):
            score += weight
            found.append(indicator)
            matched_stems.add(stemmed_indicator)

    # Etapa 2: comparacao por radical, apenas para indicadores cujo
    # radical ainda nao foi contabilizado.
    for indicator, weight, _normalized, stemmed_indicator in prepared:
        if stemmed_indicator in matched_stems:
            continue
        if not _stem_is_reliable(stemmed_indicator):
            continue
        if _contains(stemmed_text, stemmed_indicator):
            score += weight
            found.append(f"{indicator} (via radical)")
            matched_stems.add(stemmed_indicator)

    return score, found


# Radicais de uma unica palavra com menos letras que isso sao ambiguos
# demais para casar sozinhos (ex: RSLP reduz "trava" e "trem" a "tr").
MIN_SINGLE_WORD_STEM_LENGTH = 3


def _stem_is_reliable(stemmed_indicator: str) -> bool:
    """Indica se o radical e especifico o bastante para o casamento por radical."""
    if not stemmed_indicator:
        return False
    if " " in stemmed_indicator:
        return True
    return len(stemmed_indicator) >= MIN_SINGLE_WORD_STEM_LENGTH


def _contains(text: str, expression: str) -> bool:
    """Busca a expressao no texto respeitando limites de palavra."""
    pattern = r"(?<![a-z0-9])" + re.escape(expression) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


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

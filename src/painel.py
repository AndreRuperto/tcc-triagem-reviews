"""
Painel de resultados em HTML (um arquivo so, funciona offline).

Gerado automaticamente por main.py e por src/avaliacao.py dentro da
pasta de relatorios. Para gerar de novo a partir de uma pasta pronta:

    python -m src.painel --pasta reports

Le reviews_classificados.csv (e avaliacao/, se existir) e grava
painel.html na mesma pasta. Os indicadores casados literalmente sao
marcados no proprio texto do review, para a classificacao ser auditavel
a olho; os casados via radical aparecem na lista de indicadores.

Seguranca: os textos dos reviews sao de terceiros. Eles vao para o HTML
como dados JSON e sao inseridos na pagina so com textContent (nunca como
HTML), entao um review com <script> aparece como texto.
"""

import argparse
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.classificador import normalize_text, stem_phrase
from src.estilo import TOKENS_CLARO, TOKENS_ESCURO

CATEGORIAS = ["Tecnico", "Afetivo-visual", "Misto", "Indefinido"]
LIMITE_TEXTO = 6000
MARCA_RADICAL = " (via radical)"
TITULO = "Triagem de reviews de jogos digitais com IA simbólica"
NOMES_IDIOMA = {"brazilian": "português (Brasil)", "portuguese": "português (Portugal)",
                "english": "inglês", "spanish": "espanhol", "latam": "espanhol (América Latina)"}


def _normalizar_char(c: str) -> str:
    """Normaliza um caractere mantendo o comprimento 1 (para mapear posicoes)."""
    n = unicodedata.normalize("NFKD", c.lower())
    n = "".join(ch for ch in n if not unicodedata.combining(ch))[:1] or " "
    return n if ("a" <= n <= "z" or "0" <= n <= "9") else " "


def marcar_trechos(texto: str, tecnicos: list, afetivos: list) -> list:
    """
    Posicoes [inicio, fim, grupo, via_radical] dos indicadores no texto
    original. Grupo: "t" (tecnico) ou "a" (afetivo-visual). Indicadores
    com o sufixo " (via radical)" sao procurados pelo radical de cada
    palavra (mesmo RSLP do classificador), os demais literalmente.
    Trechos sobrepostos ficam com o primeiro encontrado.
    """
    espelho = "".join(_normalizar_char(c) for c in texto)
    palavras_texto = [(m.start(), m.end(), stem_phrase(m.group())) for m in re.finditer(r"[a-z0-9]+", espelho)]
    trechos = []
    for grupo, indicadores in (("t", tecnicos), ("a", afetivos)):
        for indicador in indicadores:
            via_radical = indicador.endswith(MARCA_RADICAL)
            palavras = normalize_text(indicador.removesuffix(MARCA_RADICAL)).split()
            if not palavras:
                continue
            if not via_radical:
                padrao = r"(?<![a-z0-9])" + r"\s+".join(map(re.escape, palavras)) + r"(?![a-z0-9])"
                trechos += [[m.start(), m.end(), grupo, False] for m in re.finditer(padrao, espelho)]
                continue
            radicais = [stem_phrase(p) for p in palavras]
            k = len(radicais)
            for i in range(len(palavras_texto) - k + 1):
                janela = palavras_texto[i:i + k]
                if [w[2] for w in janela] == radicais:
                    trechos.append([janela[0][0], janela[-1][1], grupo, True])
    trechos.sort()
    sem_sobreposicao, fim = [], -1
    for inicio, final, grupo, radical in trechos:
        if inicio >= fim:
            sem_sobreposicao.append([inicio, final, grupo, radical])
            fim = final
    return sem_sobreposicao


def _texto(valor) -> str:
    """Texto de uma celula do CSV; vazio para NaN/None (pandas le celula vazia como NaN)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip()


def _para_utf16(texto: str, trechos: list) -> list:
    """
    Converte as posicoes dos trechos de caracteres (Python) para unidades
    UTF-16 (JavaScript): um emoji vale 1 aqui e 2 no navegador, e sem a
    conversao as marcas depois dele sairiam deslocadas.
    """
    if texto.isascii() or not trechos:
        return trechos
    acumulado = [0]
    for c in texto:
        acumulado.append(acumulado[-1] + (2 if ord(c) > 0xFFFF else 1))
    return [[acumulado[ini], acumulado[fim], grupo, radical] for ini, fim, grupo, radical in trechos]


def _lista(valor) -> list:
    if not isinstance(valor, str) or not valor.strip():
        return []
    return [parte.strip() for parte in valor.split(";") if parte.strip()]


def _numero(valor, tipo=float):
    """Numero de uma celula do CSV, ou None se vazia/invalida."""
    try:
        if valor is None or (isinstance(valor, float) and pd.isna(valor)) or str(valor).strip() == "":
            return None
        return tipo(float(valor))
    except (TypeError, ValueError):
        return None


def montar_dados(classificados: pd.DataFrame, avaliacao: dict = None) -> dict:
    avaliacao = dict(avaliacao) if avaliacao else None
    rotulos = avaliacao.pop("rotulos", {}) if avaliacao else {}
    reviews = []
    contagem_ind = {"t": {}, "a": {}}
    for linha in classificados.itertuples(index=False):
        texto = str(getattr(linha, "texto_original", "") or "")
        ind_t = _lista(getattr(linha, "indicadores_tecnicos", ""))
        ind_a = _lista(getattr(linha, "indicadores_afetivos", ""))
        for grupo, lista in (("t", ind_t), ("a", ind_a)):
            for ind in lista:
                nome = ind.removesuffix(MARCA_RADICAL)
                contagem_ind[grupo][nome] = contagem_ind[grupo].get(nome, 0) + 1
        # linhas em branco repetidas so ocupam espaco na tela
        cortado = re.sub(r"\n\s*\n+", "\n", texto.strip())[:LIMITE_TEXTO]
        trechos = _para_utf16(cortado, [t for t in marcar_trechos(cortado, ind_t, ind_a) if t[1] <= len(cortado)])
        reviews.append({
            "id": str(linha.id_review),
            "jogo": str(getattr(linha, "jogo", "") or ""),
            "cat": linha.categoria,
            "regra": getattr(linha, "regra_acionada", ""),
            "conf": float(getattr(linha, "confianca", 0) or 0),
            "et": int(getattr(linha, "escore_tecnico", 0) or 0),
            "ea": int(getattr(linha, "escore_afetivo", 0) or 0),
            "it": ind_t,
            "ia": ind_a,
            "texto": cortado,
            "cortado": len(texto) > LIMITE_TEXTO,
            "marcas": trechos,
            "rec": _texto(getattr(linha, "recomendado", "")),
            "data": _texto(getattr(linha, "data_criacao", "")),
            "util": _numero(getattr(linha, "votos_util", None), int),
            "horas": _numero(getattr(linha, "horas_na_review", None)),
            "man": rotulos.get(str(linha.id_review), ""),
        })

    por_jogo = {}
    for jogo, grupo in classificados.groupby("jogo", sort=True):
        contagem = grupo["categoria"].value_counts()
        por_jogo[str(jogo)] = {cat: int(contagem.get(cat, 0)) for cat in CATEGORIAS}

    def ordenar(grupo):
        return sorted(contagem_ind[grupo].items(), key=lambda kv: (-kv[1], kv[0]))

    versoes = sorted({str(v) for v in classificados.get("versao_base", pd.Series(dtype=str)).dropna()})
    geral = {cat: int((classificados["categoria"] == cat).sum()) for cat in CATEGORIAS}
    return {
        "titulo": TITULO,
        "gerado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "versao_base": ", ".join(versoes),
        "com_indicador": len(classificados) - geral["Indefinido"],
        "periodo": periodo_das_reviews(classificados),
        "idiomas": idiomas_das_reviews(classificados),
        "fonte": "Steam" if "votos_util" in classificados.columns else "",
        "total": len(classificados),
        "categorias": CATEGORIAS,
        "geral": geral,
        "por_jogo": por_jogo,
        "indicadores": {"t": ordenar("t"), "a": ordenar("a")},
        "recomendacao": recomendacao_por_categoria(reviews),
        "rec_por_jogo": recomendacao_por_jogo(reviews),
        "avaliacao": avaliacao,
        "clicavel": bool(rotulos),
        "reviews": reviews,
    }


def recomendacao_por_categoria(reviews: list) -> dict:
    """{categoria: {"sim": n, "nao": n}}, ou None se nenhum review informar a recomendacao."""
    if not any(r["rec"] in ("sim", "nao") for r in reviews):
        return None
    saida = {cat: {"sim": 0, "nao": 0} for cat in CATEGORIAS}
    for r in reviews:
        if r["rec"] in ("sim", "nao") and r["cat"] in saida:
            saida[r["cat"]][r["rec"]] += 1
    return saida


def recomendacao_por_jogo(reviews: list) -> dict:
    """{jogo: [quantos recomendam, quantos informam a recomendacao]}."""
    saida = {}
    for r in reviews:
        if r["rec"] in ("sim", "nao"):
            par = saida.setdefault(r["jogo"], [0, 0])
            par[0] += r["rec"] == "sim"
            par[1] += 1
    return saida


def periodo_das_reviews(classificados: pd.DataFrame) -> list:
    """[primeira, ultima] data_criacao (AAAA-MM-DD), ou None se a coluna nao existir/estiver vazia."""
    if "data_criacao" not in classificados.columns:
        return None
    datas = pd.to_datetime(classificados["data_criacao"], format="%Y-%m-%d", errors="coerce").dropna()
    if datas.empty:
        return None
    return [datas.min().strftime("%Y-%m-%d"), datas.max().strftime("%Y-%m-%d")]


def idiomas_das_reviews(classificados: pd.DataFrame) -> list:
    """Idiomas das reviews com nome legivel (a Steam usa 'brazilian' para pt-BR)."""
    if "idioma" not in classificados.columns:
        return []
    codigos = sorted({str(i) for i in classificados["idioma"].dropna() if str(i).strip()})
    return [NOMES_IDIOMA.get(c, c) for c in codigos]


def ler_avaliacao(pasta: Path) -> dict:
    """Le reports/avaliacao/ (gerada por src/avaliacao.py), se existir."""
    metricas_csv, matriz_csv = pasta / "metricas.csv", pasta / "matriz_confusao.csv"
    if not (metricas_csv.exists() and matriz_csv.exists()):
        return None
    metricas = pd.read_csv(metricas_csv, encoding="utf-8-sig")
    matriz = pd.read_csv(matriz_csv, encoding="utf-8-sig", index_col=0)
    valores = matriz.values.tolist()
    total = int(matriz.values.sum())
    acertos = int(sum(valores[i][i] for i in range(min(len(valores), len(valores[0]) if valores else 0))))
    presentes = metricas[metricas["suporte"] > 0]
    rotulos = {}
    comparacao = pasta / "comparacao.csv"
    if comparacao.exists():
        pares = pd.read_csv(comparacao, encoding="utf-8-sig", dtype={"id_review": str})
        rotulos = dict(zip(pares["id_review"].astype(str), pares["categoria_manual"].astype(str)))
    kappa = None
    resumo = pasta / "resumo.txt"
    if resumo.exists():
        achado = re.search(r"Kappa de Cohen entre anotadores: ([0-9.,-]+)", resumo.read_text(encoding="utf-8"))
        kappa = float(achado.group(1).replace(",", ".")) if achado else None
    return {
        "n": total,
        "acuracia": round(acertos / total, 4) if total else 0.0,
        "f1_macro": round(float(presentes["f1"].mean()), 4) if len(presentes) else 0.0,
        "kappa": kappa,
        "metricas": metricas.to_dict(orient="records"),
        "matriz": valores,
        "rotulos": rotulos,
    }


def _json_seguro(dados: dict) -> str:
    # impede que um texto com "</script>" feche a tag de dados
    return json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")


def _string_css(texto: str) -> str:
    """Texto como string CSS entre aspas (para o cabecalho das paginas impressas)."""
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def montar_html(dados: dict) -> str:
    cabecalho = dados["titulo"] + (", base de conhecimento v" + dados["versao_base"] if dados["versao_base"] else "") + \
        ", gerado em " + dados["gerado"]
    html = (MODELO.replace("__TOKENS_CLARO__", TOKENS_CLARO)
            .replace("__TOKENS_ESCURO__", TOKENS_ESCURO)
            .replace("__CABECALHO_IMPRESSAO__", _string_css(cabecalho)))
    # os dados vao por ultimo: um review que contenha "__TOKENS_CLARO__" nao e substituido
    return html.replace("__DADOS__", _json_seguro(dados))


def gerar_painel(pasta: Path, destino: Path = None) -> Path:
    pasta = Path(pasta)
    classificados = pd.read_csv(pasta / "reviews_classificados.csv", encoding="utf-8-sig", dtype={"id_review": str})
    dados = montar_dados(classificados, ler_avaliacao(pasta / "avaliacao"))
    destino = Path(destino) if destino else pasta / "painel.html"
    destino.write_text(montar_html(dados), encoding="utf-8")
    return destino


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Gera o painel HTML a partir de uma pasta de relatorios.")
    parser.add_argument("--pasta", type=Path, default=Path("reports"))
    parser.add_argument("--saida", type=Path, default=None, help="Arquivo HTML (padrao: <pasta>/painel.html)")
    args = parser.parse_args(argv)
    print(f"Painel gravado em {gerar_painel(args.pasta, args.saida)}")


MODELO = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Triagem de reviews</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<script>
  // tema escolhido antes (claro/escuro), aplicado já no carregamento para não piscar
  try { var t = localStorage.getItem("painel-tema"); if (t === "claro" || t === "escuro") document.documentElement.setAttribute("data-tema", t); } catch (e) {}
  // o tema do sistema também vira atributo: na impressão o navegador sempre diz "claro"
  try { if (window.matchMedia("(prefers-color-scheme: dark)").matches) document.documentElement.setAttribute("data-sistema", "escuro"); } catch (e) {}
</script>
<style id="estilo-folha"></style>
<style>
:root {
  __TOKENS_CLARO__
  --sans: "IBM Plex Sans", system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "Cascadia Code", Consolas, monospace;
  --t-p: .875rem; --t-0: 1rem; --t-1: 1.375rem; --t-2: 1.625rem; --t-3: 2rem;
  --t-leitura: 1rem;
  --r-pequeno: 6px; --r-medio: 12px; --r-grande: 16px; --r-pilula: 999px;
  --e1: 4px; --e2: 8px; --e3: 12px; --e4: 16px; --e5: 24px; --e6: 32px; --e7: 48px; --e8: 72px;
  --largura: 1200px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-tema="claro"]) { __TOKENS_ESCURO__ }
}
:root[data-tema="escuro"], :root[data-sistema="escuro"]:not([data-tema="claro"]) { __TOKENS_ESCURO__ }
* { box-sizing: border-box; }
/* barras de rolagem finas, arredondadas, nas cores do tema */
html, .rolagem, .dd-lista, #sec-rev > .margem { scrollbar-width: thin; scrollbar-color: var(--rolagem) transparent; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--rolagem); border-radius: 999px; border: 3px solid transparent; background-clip: padding-box; }
::-webkit-scrollbar-thumb:hover { background-color: var(--rolagem-forte); }
::-webkit-scrollbar-corner { background: transparent; }
html { font-size: 100%; }
body { margin: 0; background: var(--fundo); color: var(--tinta); font: var(--t-0)/1.55 var(--sans); }
.envolve, main { max-width: var(--largura); margin: 0 auto; padding-left: var(--e6); padding-right: var(--e6); }
main { padding-bottom: var(--e8); display: flex; flex-direction: column; gap: var(--e6); margin-top: calc(-1 * var(--e6)); position: relative; }
h1 { font: 700 clamp(2rem, 4.6vw, 3.25rem)/1.07 var(--sans); letter-spacing: -.02em; margin: 0; max-width: 22ch; }
h2 { font: 600 var(--t-1)/1.25 var(--sans); margin: 0; letter-spacing: -.005em; }
h3 { font: 600 var(--t-0)/1.3 var(--sans); margin: 0 0 var(--e3); }
p { margin: 0; }
.sub { color: var(--tinta-suave); font-size: .9375rem; max-width: 72ch; }
.num { font-variant-numeric: tabular-nums; }
.mono, .kicker, .rotulo { font-family: var(--mono); }
:focus-visible { outline: 3px solid var(--foco); outline-offset: 2px; }

/* cabeçalho em faixa escura */
.cabeca-pagina { background: var(--cabeca); color: var(--cabeca-tinta); padding: var(--e6) 0 var(--e8); }
.cabeca-pagina .envolve { display: flex; flex-direction: column; gap: var(--e5); }
.barra-topo { display: flex; flex-wrap: wrap; gap: var(--e3); justify-content: space-between; align-items: center; }
.kicker { font-size: .8125rem; font-weight: 500; letter-spacing: .05em; text-transform: uppercase; color: var(--cabeca-suave); }
.contexto { color: var(--cabeca-suave); font-size: 1.0625rem; line-height: 1.55; max-width: 70ch; }
.ferramentas { display: flex; flex-wrap: wrap; gap: var(--e2); align-items: center; }
.ferramentas button, .ferramentas select { font: inherit; font-size: var(--t-p); color: var(--cabeca-tinta); background-color: transparent;
  border: 1px solid var(--cabeca-linha); border-radius: var(--r-pilula); padding: var(--e2) var(--e4); min-height: 44px; cursor: pointer; }
/* lista do dropdown do cabeçalho: escura, como a faixa */
.ferramentas select { color-scheme: dark; }
.ferramentas select option { color: var(--cabeca-tinta); background: var(--cabeca); }
.ferramentas button:hover, .ferramentas select:hover { border-color: var(--cabeca-suave); }
.ferramentas select { padding-right: 2.5rem; }
.ferramentas label { display: inline-flex; gap: var(--e2); align-items: center; font-size: var(--t-p); color: var(--cabeca-suave); }
.ferramentas button[aria-pressed="true"] { background: var(--cabeca-tinta); color: var(--cabeca); border-color: var(--cabeca-tinta); }
.indice ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--e2); }
.indice a { display: inline-flex; align-items: center; min-height: 40px; padding: 0 var(--e4); border: 1px solid var(--cabeca-linha);
  border-radius: var(--r-pilula); color: var(--cabeca-tinta); font-size: var(--t-p); text-decoration: none; }
.indice a:hover { border-color: var(--cabeca-suave); }

/* ações dentro dos cartões */
.mais, .comando button { font: inherit; font-size: var(--t-p); color: var(--tinta); background: var(--papel);
  border: 1px solid var(--linha); border-radius: var(--r-pequeno); padding: var(--e2) var(--e4); min-height: 44px; cursor: pointer; }
.mais:hover, .comando button:hover { border-color: var(--tinta-suave); }
.mais { margin-top: var(--e4); justify-self: start; }

/* seções: cartões brancos, título em cima do conteúdo */
section { background: var(--papel); border: 1px solid var(--linha); border-radius: var(--r-grande); padding: var(--e6);
  display: flex; flex-direction: column; gap: var(--e5); scroll-margin-top: var(--e4); min-width: 0; }
.margem { display: flex; flex-direction: column; gap: var(--e2); }
.margem .troca { align-self: flex-start; }
.corpo { min-width: 0; }

/* modo apresentação */
html.apresentacao { font-size: 125%; }
html.apresentacao { --largura: 1440px; }
html.apresentacao .so-tela, html.apresentacao footer { display: none; }
.so-impressao { display: none; }
html.apresentacao #tempo svg { height: 300px; }
html.apresentacao #tempo .eixo text { font-size: 15px; }

/* achado: a frase-resumo no topo do primeiro cartão */
.achado { font: 500 var(--t-2)/1.3 var(--sans); letter-spacing: -.01em; max-width: 44ch; }

/* números por categoria */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--e4); }
.kpi { display: flex; flex-direction: column; gap: 6px; padding: var(--e5); border-radius: var(--r-medio); background: var(--ind-marca); }
.kpi .rotulo-cat { font-size: var(--t-p); font-weight: 600; color: var(--tinta-suave); }
.kpi b { font: 700 2.5rem/1 var(--sans); font-variant-numeric: tabular-nums; }
.kpi small { font-size: .8125rem; color: var(--tinta-suave); }
.kpi.k-Tecnico { background: var(--tec-marca); } .kpi.k-Tecnico .rotulo-cat { color: var(--tec); }
.kpi.k-Afetivo-visual { background: var(--afe-marca); } .kpi.k-Afetivo-visual .rotulo-cat { color: var(--afe); }
.kpi.k-Misto { background: var(--mis-marca); } .kpi.k-Misto .rotulo-cat { color: var(--mis); }
.kpi.k-total { background: var(--fundo); }

/* barras empilhadas */
.barra { display: flex; gap: 3px; height: 18px; border-radius: var(--r-pilula); overflow: hidden; background: var(--papel); }
.barra.grande { height: 22px; }
.fatia { min-width: 3px; }
.f-Tecnico { background: var(--tec); }
.f-Afetivo-visual { background: var(--afe); }
.f-Misto { background: var(--mis); }
.f-Indefinido { background: var(--ind); }
.funil { display: block; width: 100%; height: 36px; }
.funil polygon { fill: var(--linha); opacity: .8; }
.zoom-titulo { font-size: var(--t-p); color: var(--tinta-suave); }
.zoom-titulo b { color: var(--tinta); }

/* tabelas */
table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { padding: var(--e3) var(--e4); text-align: right; border-bottom: 1px solid var(--linha); }
th:first-child, td:first-child { text-align: left; padding-left: 0; }
thead th { font: 600 .75rem/1.2 var(--mono); text-transform: uppercase; letter-spacing: .06em; color: var(--tinta-suave); vertical-align: bottom; }
tbody tr:last-child th, tbody tr:last-child td { border-bottom: 0; }
.rolagem { overflow-x: auto; }
.tab-legenda { width: 100%; margin-top: var(--e5); }
.tab-legenda tbody th { font-weight: 400; }
.tab-legenda .nome { display: grid; grid-template-columns: 12px 1fr; column-gap: var(--e3); align-items: baseline; }
.tab-legenda .cor { width: 12px; height: 12px; border-radius: 3px; align-self: center; }
.tab-legenda b { font-weight: 600; }
.tab-legenda .desc { grid-column: 2; color: var(--tinta-suave); font-size: var(--t-p); }
.tab-legenda td { vertical-align: top; white-space: nowrap; font-family: var(--mono); font-size: .9375rem; }

/* ao longo do tempo */
/* interruptor: checkbox de verdade, desenhado como trilho + bolinha */
.troca { display: inline-flex; gap: var(--e3); align-items: center; min-height: 44px; cursor: pointer; font-size: var(--t-p);
  padding: 0 var(--e4) 0 var(--e1); border-radius: var(--r-pilula); user-select: none; }
.troca input { -webkit-appearance: none; appearance: none; flex: none; position: relative; margin: 0; cursor: pointer;
  width: 40px; height: 24px; border-radius: var(--r-pilula); background: var(--ind-marca); border: 1px solid var(--linha);
  transition: background-color .18s ease, border-color .18s ease; }
.troca input::after { content: ""; position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%;
  background: var(--bolinha); box-shadow: 0 1px 3px rgba(15, 17, 20, .3); transition: transform .18s ease; }
.troca:hover input { border-color: var(--tinta-suave); }
.troca input:checked { background: var(--tec); border-color: var(--tec); }
.troca input:checked::after { transform: translateX(16px); background: var(--sobre-cor); }
.troca input:focus-visible { outline: 2px solid var(--foco); outline-offset: 3px; }
.troca:has(input:checked) { color: var(--tinta); font-weight: 600; }
@media (prefers-reduced-motion: reduce) { .troca input, .troca input::after { transition: none; } }
#tempo svg { display: block; width: 100%; height: 240px; overflow: visible; }
#tempo .eixo text { fill: var(--tinta-suave); font: 12px var(--mono); font-variant-numeric: tabular-nums; }
#tempo .eixo line { stroke: var(--linha); }
#tempo .col { cursor: pointer; outline: none; }
#tempo .col .alvo { fill: transparent; }
#tempo .col:hover .alvo, #tempo .col:focus-visible .alvo { fill: var(--linha); opacity: .45; }
#tempo .col:focus-visible .alvo { stroke: var(--foco); stroke-width: 3px; opacity: 1; fill-opacity: .25; }
#tempo.escolhido .col:not([aria-pressed="true"]) rect:not(.alvo) { opacity: .3; }
.s-Tecnico { fill: var(--tec); } .s-Afetivo-visual { fill: var(--afe); } .s-Misto { fill: var(--mis); } .s-Indefinido { fill: var(--ind); }

/* por jogo */
.tab-jogos { width: 100%; min-width: 720px; }
.tab-jogos th, .tab-jogos td { vertical-align: middle; }
.tab-jogos thead th { padding: 0; }
.ordenar { font: 600 .75rem/1.2 var(--mono); text-transform: uppercase; letter-spacing: .06em; color: var(--tinta-suave); background: none; border: 0; cursor: pointer;
  width: 100%; min-height: 44px; padding: var(--e2) var(--e4); text-align: inherit; white-space: nowrap; }
thead th:first-child .ordenar { padding-left: 0; }
.ordenar::after { content: ""; display: inline-block; width: 1em; }
th[aria-sort="descending"] .ordenar::after { content: " \2193"; }
th[aria-sort="ascending"] .ordenar::after { content: " \2191"; }
th[aria-sort] .ordenar { color: var(--tinta); }
.jogo-btn { font: inherit; font-weight: 600; color: var(--tinta); background: none; border: 1px solid transparent; border-radius: var(--r-pequeno);
  padding: var(--e2); margin-left: calc(-1 * var(--e2)); min-height: 44px; cursor: pointer; text-align: left; }
.jogo-btn:hover { border-color: var(--linha); }
.jogo-btn[aria-pressed="true"] { border-color: var(--tec); background: var(--tec-marca); }
.celula { display: grid; gap: 4px; justify-items: end; }
.celula small { color: var(--tinta-suave); font-size: var(--t-p); }
.mini { width: 72px; height: 6px; background: var(--linha); border-radius: 3px; overflow: hidden; }
.mini span { display: block; height: 100%; }

/* recomendação */
.rec-lista { display: grid; gap: var(--e4); }
.rec-linha { display: grid; grid-template-columns: minmax(130px, 200px) 1fr minmax(150px, auto); gap: var(--e4); align-items: center; }
.rec-linha .barra { height: 12px; gap: 0; background: var(--ind-marca); }
.r-sim { background: var(--tinta); border-radius: var(--r-pilula); } .r-nao { background: transparent; }
.rec-linha .conta { font-size: var(--t-p); font-family: var(--mono); }
.rec-linha small { color: var(--tinta-suave); font-size: var(--t-p); margin-left: var(--e2); }

/* indicadores */
.duas { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); gap: var(--e6); }
.ind-lista { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e3); }
.ind-lista li { display: grid; grid-template-columns: minmax(120px, 42%) 1fr 3ch; gap: var(--e3); align-items: center; }
.ind-lista .trilho { height: 10px; background: var(--ind-marca); border-radius: 5px; overflow: hidden; }
.ind-lista .enchimento { height: 100%; }
.vazio { color: var(--tinta-suave); background: var(--papel-2); border: 1px dashed var(--linha); border-radius: var(--r-medio); padding: var(--e5); }
.vazio ol { margin: var(--e3) 0 0; padding-left: 1.4em; display: grid; gap: var(--e3); }
.comando { display: flex; flex-wrap: wrap; gap: var(--e2); align-items: center; margin-top: var(--e1); }
.comando code { font: var(--t-p)/1.5 var(--mono); color: var(--tinta); background: var(--fundo);
  border: 1px solid var(--linha); border-radius: var(--r-pequeno); padding: var(--e2) var(--e3); overflow-wrap: anywhere; }
.comando button { min-width: 88px; }

/* avaliação */
.placar { display: flex; flex-wrap: wrap; gap: var(--e4); margin-bottom: var(--e5); }
.placar div { padding: var(--e4) var(--e5); background: var(--fundo); border-radius: var(--r-medio); min-width: 140px; }
.placar div b { display: block; font-size: var(--t-2); line-height: 1.1; font-variant-numeric: tabular-nums; }
.placar div span { color: var(--tinta-suave); font-size: var(--t-p); }
.matriz td { min-width: 64px; text-align: center; }
.matriz td.diag { font-weight: 700; }
.matriz td small { display: block; font-size: var(--t-p); color: var(--tinta-suave); font-weight: 400; }
.celula-btn { font: inherit; color: inherit; background: none; border: 1px solid transparent; border-radius: var(--r-pequeno);
  width: 100%; min-height: 44px; cursor: pointer; padding: var(--e1); }
.celula-btn:hover { border-color: var(--tinta-suave); }
.celula-btn[aria-pressed="true"] { border-color: var(--tec); box-shadow: inset 0 0 0 1px var(--tec); }

/* reviews: filtros num cartão ao lado da lista */
#sec-rev { background: transparent; border: 0; padding: 0; }
#sec-rev > .margem { background: var(--papel); border: 1px solid var(--linha); border-radius: var(--r-grande); padding: var(--e5); gap: var(--e3); }
@media (min-width: 960px) {
  #sec-rev { display: grid; grid-template-columns: 19rem minmax(0, 1fr); gap: var(--e5); align-items: start; }
  #sec-rev > .margem { position: sticky; top: var(--e4); max-height: calc(100vh - 2 * var(--e4)); overflow-y: auto; overflow-x: hidden;
    scrollbar-gutter: stable; }
}
.filtros { display: grid; gap: var(--e3); }
.filtros label { display: grid; gap: var(--e1); font-size: var(--t-p); color: var(--tinta-suave); }
select, input[type=search] { font: inherit; font-size: var(--t-p); color: var(--tinta); background-color: var(--papel); border: 1px solid var(--linha);
  border-radius: var(--r-pequeno); padding: var(--e2) var(--e3); min-height: 44px; }
input[type=search]:hover, select:hover { border-color: var(--tinta-suave); }
/* todos os dropdowns: sem a seta do sistema; seta desenhada na cor do texto, lista nas cores do tema */
select { -webkit-appearance: none; appearance: none; cursor: pointer; padding-right: 2.5rem;
  background-image: linear-gradient(45deg, transparent 50%, currentColor 50%), linear-gradient(135deg, currentColor 50%, transparent 50%);
  background-position: calc(100% - 1.15rem) 52%, calc(100% - .8rem) 52%; background-size: .36rem .36rem; background-repeat: no-repeat; }
select option { color: var(--tinta); background-color: var(--papel); }
select:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.filtros select, .filtros input { width: 100%; min-width: 0; }
/* dropdown próprio: o <select> fica escondido por baixo e continua sendo a fonte do valor */
.dd-nativo, .filtros .dd-nativo { position: absolute !important; width: 1px !important; min-width: 0 !important; height: 1px !important; min-height: 0 !important;
  padding: 0 !important; margin: 0 !important; border: 0 !important; opacity: 0; pointer-events: none; overflow: hidden; clip-path: inset(50%); }
.dd { position: relative; display: inline-block; }
.filtros .dd { display: block; }
.dd-botao { font: inherit; font-size: var(--t-p); display: inline-flex; align-items: center; justify-content: space-between; gap: var(--e3);
  min-height: 44px; padding: var(--e2) var(--e3) var(--e2) var(--e4); cursor: pointer; text-align: left;
  color: var(--tinta); background: var(--papel); border: 1px solid var(--linha); border-radius: var(--r-pequeno); }
.filtros .dd-botao { width: 100%; }
.dd-botao:hover { border-color: var(--tinta-suave); }
.dd-botao[aria-expanded="true"] { border-color: var(--tec); box-shadow: 0 0 0 3px var(--tec-marca); }
.dd-botao:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.dd-seta { flex: none; transition: transform .15s ease; opacity: .8; }
.dd-botao[aria-expanded="true"] .dd-seta { transform: rotate(180deg); }
.dd-valor { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dd-lista { position: absolute; z-index: 30; top: calc(100% + 6px); left: 0; min-width: 100%; max-height: 320px; overflow-y: auto;
  margin: 0; padding: 6px; list-style: none; background: var(--papel); color: var(--tinta);
  border: 1px solid var(--linha); border-radius: var(--r-medio); box-shadow: 0 16px 40px rgba(15, 17, 20, .16), 0 2px 6px rgba(15, 17, 20, .08); }
.dd-lista[hidden] { display: none; }
.dd-lista:focus { outline: none; }
.dd-opcao { display: flex; align-items: center; gap: 10px; min-height: 40px; padding: var(--e2) var(--e3) var(--e2) 10px;
  border-radius: 8px; cursor: pointer; font-size: var(--t-p); white-space: nowrap; }
.dd-opcao.ativa { background: var(--fundo); }
.dd-opcao[aria-selected="true"] { font-weight: 600; }
.dd-check { flex: none; visibility: hidden; color: var(--tec); }
.dd-opcao[aria-selected="true"] .dd-check { visibility: visible; }
/* no cabeçalho: pílula transparente e menu escuro */
.ferramentas .dd-botao { color: var(--cabeca-tinta); background: transparent; border-color: var(--cabeca-linha); border-radius: var(--r-pilula); }
.ferramentas .dd-botao:hover { border-color: var(--cabeca-suave); }
.ferramentas .dd-botao[aria-expanded="true"] { border-color: var(--cabeca-suave); box-shadow: 0 0 0 3px rgba(255, 255, 255, .08); }
.filtros .dd-lista { right: 0; }
.filtros .dd-opcao { white-space: normal; }
.ferramentas .dd-lista { left: auto; right: 0; min-width: 190px; background: #1e2126; color: var(--cabeca-tinta); border-color: var(--cabeca-linha);
  box-shadow: 0 18px 44px rgba(0, 0, 0, .45); }
.ferramentas .dd-opcao.ativa { background: rgba(255, 255, 255, .08); }
.ferramentas .dd-check { color: var(--cabeca-tinta); }
@media (prefers-reduced-motion: reduce) { .dd-seta { transition: none; } }
.cats { display: flex; flex-wrap: wrap; gap: var(--e1); }
.cats button { font: inherit; font-size: var(--t-p); color: var(--tinta); background: var(--papel); border: 1px solid var(--linha);
  border-radius: var(--r-pilula); padding: var(--e2) var(--e3); min-height: 44px; cursor: pointer; }
.cats button[aria-pressed="true"] { background: var(--tinta); color: var(--papel); border-color: var(--tinta); }
.chip { display: grid; gap: var(--e1); font-size: var(--t-p); }
.chip[hidden] { display: none; }
.chip b { font-weight: 600; }
.chip .mais { margin-top: 0; justify-self: start; }
.estado { color: var(--tinta-suave); font-size: var(--t-p); }
.lista { display: grid; gap: var(--e3); }
.review { background: var(--papel); border: 1px solid var(--linha); border-radius: var(--r-medio); padding: var(--e5); }
.cabeca { display: flex; flex-wrap: wrap; gap: var(--e2) var(--e4); align-items: center; font-size: var(--t-p); color: var(--tinta-suave); }
.cabeca .jogo-nome { font-weight: 600; color: var(--tinta); }
.etiqueta { display: inline-flex; align-items: center; font-weight: 600; font-size: .8125rem; color: var(--tinta-suave); padding: 3px 10px;
  border-radius: var(--r-pequeno); border: 1px solid var(--ind); background: transparent; }
.etiqueta.c-Tecnico { color: var(--sobre-cor); border-color: var(--tec); background: var(--tec); }
.etiqueta.c-Afetivo-visual { color: var(--sobre-cor); border-color: var(--afe); background: var(--afe); }
.etiqueta.c-Misto { color: var(--sobre-cor); border-color: var(--mis); background: var(--mis); }
.etiqueta.gabarito { color: var(--tinta); font-weight: 500; background: none; border-style: dashed; }
.etiqueta.gabarito.c-Tecnico { border-color: var(--tec); } .etiqueta.gabarito.c-Afetivo-visual { border-color: var(--afe); }
.etiqueta.gabarito.c-Misto { border-color: var(--mis); }
.meta { display: inline-flex; gap: var(--e1); align-items: center; font-family: var(--mono); font-size: .8125rem; }
.texto { font: var(--t-leitura)/1.65 var(--sans); margin: var(--e3) 0; max-width: 72ch; white-space: pre-wrap; overflow-wrap: anywhere; }
mark { color: inherit; background: transparent; padding: 0 2px; border-radius: 3px; font-weight: 600; }
mark.t { color: var(--tec); box-shadow: inset 0 -2px 0 var(--tec); }
mark.a { color: var(--afe); box-shadow: inset 0 -2px 0 var(--afe); }
mark.m { color: var(--mis); box-shadow: inset 0 -2px 0 var(--mis); }
mark.i { color: var(--tinta-suave); box-shadow: inset 0 -2px 0 var(--ind); font-weight: 500; }
mark.radical { box-shadow: none; text-decoration: underline dotted 2px; text-underline-offset: 4px; }
.reticencias { color: var(--tinta-suave); }
.ler { font: inherit; font-size: var(--t-p); color: var(--tec); background: none; border: 0; padding: var(--e2) 0; min-height: 44px; cursor: pointer; text-decoration: underline; }
.porque { font-size: var(--t-p); color: var(--tinta-suave); display: grid; gap: var(--e1); padding-top: var(--e3); border-top: 1px solid var(--linha); }
.porque b { color: var(--tinta); font-weight: 600; }
footer { color: var(--tinta-suave); font-size: var(--t-p); }

@media (max-width: 640px) {
  .envolve, main { padding-left: var(--e4); padding-right: var(--e4); }
  section { padding: var(--e5) var(--e4); }
  .achado { font-size: 1.3rem; }
  .kpi b { font-size: 2rem; }
  .rec-linha { grid-template-columns: 1fr; gap: var(--e1); }
  .review { padding: var(--e4); }
  .tab-legenda td { white-space: normal; }
}
@media print {
  /* o PDF segue o tema que está na tela (claro, escuro ou o do sistema),
     com tipografia e espaçamento próprios para papel A4 */
  @page {
    size: A4;
    margin: 15mm 14mm 16mm;
    @top-left { content: __CABECALHO_IMPRESSAO__; font: 7pt "IBM Plex Sans", system-ui, sans-serif; color: var(--tinta-suave); }
    @bottom-right { content: counter(page) " / " counter(pages); font: 7pt "IBM Plex Mono", ui-monospace, monospace; color: var(--tinta-suave); }
  }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  html, html.apresentacao { font-size: 9pt; background: var(--papel); }
  body { background: var(--papel); line-height: 1.45; }
  .envolve, main, html.apresentacao main { max-width: none; padding: 0; margin: 0; }
  main { display: block; }

  /* cabeçalho: bloco compacto, sem a faixa escura */
  .cabeca-pagina { background: none; color: var(--tinta); padding: 0 0 8pt; margin-bottom: 10pt; border-bottom: 1.5pt solid var(--tinta); }
  .cabeca-pagina .envolve { gap: 5pt; }
  .kicker { font-size: 6.5pt; color: var(--tinta-suave); }
  h1 { font-size: 19pt; line-height: 1.1; max-width: none; }
  .contexto { color: var(--tinta-suave); font-size: 8pt; max-width: none; }

  /* seções: fluxo contínuo separado por fios, sem cartões */
  section, #sec-rev, #sec-rev > .margem { display: block; background: none; border: 0; border-radius: 0; padding: 0; box-shadow: none; position: static; max-height: none; overflow: visible; }
  section { margin: 0 0 12pt; padding-top: 9pt; border-top: .75pt solid var(--linha); }
  #sec-geral { border-top: 0; padding-top: 0; }
  section > * + *, .margem > * + * { margin-top: 5pt; }
  h2 { font-size: 11.5pt; break-after: avoid; }
  h3 { font-size: 9.5pt; margin-bottom: 4pt; }
  .sub { font-size: 7.5pt; max-width: none; }
  .instrucao, .dd, .ferramentas, .filtros, .cats, .mais, .ler, .troca, #limpar-periodo, #limpar-celula, .so-tela, #estado, .indice, .comando button { display: none !important; }
  .so-impressao { display: block; color: var(--tinta-suave); font-size: 7.5pt; margin-bottom: 5pt; }

  /* visão geral */
  .achado { font-size: 12pt; line-height: 1.3; max-width: none; }
  .kpis { grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 5pt; margin-top: 8pt; }
  .kpi { padding: 6pt 8pt; gap: 2pt; border-radius: 5pt; }
  .kpi .rotulo-cat { font-size: 7pt; }
  .kpi b { font-size: 16pt; }
  .kpi small { font-size: 6.5pt; }
  .barra { height: 8pt; gap: 1.5pt; }
  .barra.grande { height: 10pt; }
  .funil { height: 14pt; }
  .zoom-titulo { font-size: 7.5pt; margin-top: 3pt !important; }

  /* tabelas densas */
  th, td { padding: 3pt 6pt; }
  thead th, .ordenar { font-size: 6.5pt; }
  .tab-legenda { margin-top: 6pt; }
  .tab-legenda td { font-size: 8pt; white-space: nowrap; }
  .tab-legenda .desc { font-size: 7pt; }
  .tab-legenda .cor { width: 8pt; height: 8pt; }
  .tab-jogos { min-width: 0; font-size: 8pt; }
  .tab-jogos td { padding-top: 4pt; padding-bottom: 4pt; }
  .celula small { font-size: 6.5pt; }
  .mini { width: 44pt; height: 3pt; }
  .jogo-btn, .ordenar, .celula-btn { border: 0; padding: 0; margin: 0; min-height: 0; background: none; box-shadow: none; }
  .ordenar::after { content: none !important; }
  .rolagem { overflow: visible; }

  /* gráficos */
  #tempo svg { height: 130px; }
  #tempo .eixo text { font-size: 9px; }
  .rec-lista { gap: 4pt; }
  .rec-linha { grid-template-columns: 34mm 1fr 32mm; gap: 6pt; }
  .rec-linha .barra { height: 6pt; }
  .rec-linha .conta, .rec-linha small { font-size: 7.5pt; }
  .duas { gap: 12pt; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ind-lista { gap: 3pt; }
  .ind-lista li { font-size: 8pt; gap: 6pt; }
  .ind-lista .trilho { height: 5pt; }
  .placar { gap: 6pt; margin-bottom: 6pt; }
  .placar div { padding: 5pt 8pt; min-width: 0; background: var(--papel-2); }
  .placar div b { font-size: 13pt; }
  .vazio { padding: 8pt; font-size: 8pt; border-radius: 5pt; }
  .comando code { font-size: 7pt; padding: 2pt 4pt; }

  /* reviews: cartões finos, dois por linha não; um embaixo do outro, densos */
  .lista { gap: 5pt; }
  .review { padding: 6pt 9pt; border: .75pt solid var(--linha); border-radius: 5pt; background: var(--papel-2); }
  .cabeca { font-size: 7pt; gap: 2pt 8pt; }
  .meta { font-size: 6.5pt; }
  .etiqueta { font-size: 6.5pt; padding: 1pt 5pt; border-radius: 3pt; }
  .texto { font-size: 8.5pt; line-height: 1.45; margin: 4pt 0; max-width: none; }
  .porque { font-size: 7pt; gap: 1pt; padding-top: 4pt; }
  footer { font-size: 7pt; margin-top: 8pt; }

  /* quebras: só os blocos pequenos ficam inteiros; as seções podem continuar na página seguinte */
  .kpis, .barra, #zoom, .tab-legenda tr, #tempo, .tab-jogos tr, .rec-linha, .ind-lista li, .matriz, .placar, .review, .vazio { break-inside: avoid; }
  .margem, h2, h3 { break-after: avoid; }
}
</style>
</head>
<body>
<header class="cabeca-pagina">
  <div class="envolve">
    <div class="barra-topo">
      <span class="kicker" id="kicker"></span>
      <div class="ferramentas" role="toolbar" aria-label="Opções de exibição">
        <button type="button" id="b-apresentacao" aria-pressed="false" aria-keyshortcuts="P" title="Atalho: tecla P">Modo apresentação</button>
        <label>Tema <select id="f-tema">
          <option value="">Do sistema</option><option value="claro">Claro</option><option value="escuro">Escuro</option>
        </select></label>
        <button type="button" id="b-imprimir">Imprimir ou salvar em PDF</button>
      </div>
    </div>
    <h1 id="titulo"></h1>
    <p class="contexto" id="resumo"></p>
    <nav class="indice" aria-label="Nesta página">
      <ul>
        <li><a href="#sec-geral">Visão geral</a></li>
        <li><a href="#sec-tempo">Ao longo do tempo</a></li>
        <li><a href="#sec-jogos">Por jogo</a></li>
        <li><a href="#sec-rec">Recomendação</a></li>
        <li><a href="#sec-ind">Indicadores</a></li>
        <li><a href="#sec-aval">Gabarito</a></li>
        <li><a href="#sec-rev">Reviews</a></li>
      </ul>
    </nav>
  </div>
</header>
<main>

  <section aria-labelledby="t-geral" id="sec-geral">
    <p class="achado" id="achado"></p>
    <div class="kpis" id="kpis"></div>
    <div class="margem">
      <h2 id="t-geral">Como os reviews se dividem</h2>
      <p class="sub">A barra de baixo amplia a parte colorida da de cima: só os reviews em que o sistema achou algum indicador.</p>
    </div>
    <div class="corpo">
      <div class="barra grande" id="barra-geral" role="img"></div>
      <div id="zoom"></div>
      <div class="rolagem"><table class="tab-legenda" id="legenda"></table></div>
    </div>
  </section>

  <section aria-labelledby="t-tempo" id="sec-tempo">
    <div class="margem">
      <h2 id="t-tempo">Ao longo do tempo</h2>
      <p class="sub" id="tempo-sub"></p>
      <label class="troca"><input type="checkbox" role="switch" id="so-indicador"> Só reviews com indicador</label>
      <p class="sub">Conta só as reviews coletadas, não todas as dos jogos: a altura das colunas depende de como a coleta foi feita
        (coletar as mais recentes enche os últimos meses).</p>
    </div>
    <div class="corpo"><div id="tempo"></div></div>
  </section>

  <section aria-labelledby="t-jogos" id="sec-jogos">
    <div class="margem">
      <h2 id="t-jogos">Por jogo</h2>
      <p class="sub instrucao">Clique no nome de um jogo para filtrar a linha do tempo e a lista de reviews. Clique no título de uma coluna para ordenar.</p>
    </div>
    <div class="corpo"><div class="rolagem"><table class="tab-jogos" id="tab-jogos"></table></div></div>
  </section>

  <section aria-labelledby="t-rec" id="sec-rec">
    <div class="margem">
      <h2 id="t-rec">Recomendação por categoria</h2>
      <p class="sub">Parte dos reviews de cada categoria que recomenda o jogo, segundo a própria Steam.</p>
    </div>
    <div class="corpo"><div class="rec-lista" id="rec"></div></div>
  </section>

  <section aria-labelledby="t-ind" id="sec-ind">
    <div class="margem">
      <h2 id="t-ind">Indicadores mais acionados</h2>
      <p class="sub">Em quantos reviews cada expressão da base de conhecimento foi encontrada.</p>
    </div>
    <div class="corpo"><div class="duas" id="indicadores"></div></div>
  </section>

  <section aria-labelledby="t-aval" id="sec-aval">
    <div class="margem"><h2 id="t-aval">Sistema comparado ao gabarito manual</h2></div>
    <div class="corpo" id="avaliacao"></div>
  </section>

  <section aria-labelledby="t-rev" id="sec-rev">
    <div class="margem">
      <h2 id="t-rev">Reviews e o porquê de cada classificação</h2>
      <p class="sub">Indicadores marcados no texto: <mark class="t">técnicos</mark> e <mark class="a">afetivo-visuais</mark>.
        Pontilhado é <mark class="t radical">casamento pelo radical</mark> (“lagar” com “lag”). Reviews longos mostram só o trecho em volta.</p>
      <div class="filtros">
        <label>Jogo <select id="f-jogo"><option value="">Todos os jogos</option></select></label>
        <label class="so-tela">Buscar no texto <input type="search" id="f-busca" placeholder="ex.: travando, rosto"></label>
        <label class="so-tela">Ordenar por <select id="f-ordem">
          <option value="indicadores">Mais indicadores primeiro</option>
          <option value="recentes">Mais recentes primeiro</option>
          <option value="uteis">Mais votados como úteis</option>
        </select></label>
      </div>
      <div class="cats" id="f-cats" role="group" aria-label="Filtrar por categoria"></div>
      <div class="chip" id="chip-periodo" hidden><span>Período: <b id="chip-texto"></b></span>
        <button class="mais" type="button" id="limpar-periodo">Limpar período</button></div>
      <div class="chip" id="chip-celula" hidden><span>Matriz: <b id="chip-celula-texto"></b></span>
        <button class="mais" type="button" id="limpar-celula">Limpar filtro da matriz</button></div>
      <p class="estado" id="estado" aria-live="polite"></p>
    </div>
    <div class="corpo">
      <p class="so-impressao" id="nota-impressao"></p>
      <div class="lista" id="lista"></div>
      <button class="mais" id="mais" type="button">Mostrar mais 30</button>
    </div>
  </section>

  <footer id="rodape"></footer>
</main>

<script type="application/json" id="dados">__DADOS__</script>
<script>
(function () {
  "use strict";
  var D = JSON.parse(document.getElementById("dados").textContent);
  var NOMES = { "Tecnico": "Técnico", "Afetivo-visual": "Afetivo-visual", "Misto": "Misto", "Indefinido": "Indefinido" };
  var DESC = {
    "Tecnico": "Só indicadores de falha técnica (regra R1).",
    "Afetivo-visual": "Só indicadores de rejeição à aparência de personagens (R2).",
    "Misto": "Indicadores dos dois grupos no mesmo review (R3).",
    "Indefinido": "Nenhum indicador da base encontrado (R4)."
  };
  var fmt = new Intl.NumberFormat("pt-BR");
  var pct = function (n, t) { return t ? (100 * n / t).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + "%" : "0%"; };
  var el = function (tag, attrs, filhos) {
    var e = document.createElement(tag);
    for (var k in (attrs || {})) {
      if (k === "texto") e.textContent = attrs[k];
      else if (k === "classe") e.className = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    (filhos || []).forEach(function (f) { if (f) e.appendChild(typeof f === "string" ? document.createTextNode(f) : f); });
    return e;
  };

  function barra(contagem, total, alvo) {
    var partes = [];
    D.categorias.forEach(function (c) {
      var n = contagem[c] || 0;
      if (!n) return;
      alvo.appendChild(el("div", { classe: "fatia f-" + c, style: "flex:" + n }));
      partes.push(NOMES[c] + " " + fmt.format(n) + " (" + pct(n, total) + ")");
    });
    alvo.setAttribute("aria-label", partes.join(", "));
    return partes;
  }

  // cabeçalho: título, o achado em uma frase e o contexto da coleta
  var MARCA = { "Tecnico": "t", "Afetivo-visual": "a", "Misto": "m", "Indefinido": "i" };
  var SINGULAR = { "Tecnico": "técnico", "Afetivo-visual": "afetivo-visual", "Misto": "misto" };
  var PLURAL = { "Tecnico": "técnicos", "Afetivo-visual": "afetivo-visuais", "Misto": "mistos" };
  var PLURAL_I = { "Tecnico": "técnicos", "Afetivo-visual": "afetivo-visuais", "Misto": "mistos", "Indefinido": "indefinidos" };
  var SINGULAR_I = { "Tecnico": "técnico", "Afetivo-visual": "afetivo-visual", "Misto": "misto", "Indefinido": "indefinido" };
  var nCat = function (n, c) { return fmt.format(n) + " " + (n === 1 ? SINGULAR_I[c] : PLURAL_I[c]); };
  var nReviews = function (n) { return fmt.format(n) + (n === 1 ? " review" : " reviews"); };
  var dataBr = function (iso) { return iso.split("-").reverse().join("/"); };
  var lista_e = function (itens) {   // ["a","b","c"] -> a, b e c (como nós DOM)
    var out = [];
    itens.forEach(function (it, i) { if (i) out.push(i === itens.length - 1 ? " e " : ", "); out.push(it); });
    return out;
  };
  document.getElementById("titulo").textContent = D.titulo;
  document.getElementById("kicker").textContent = "Sistema especialista" + (D.versao_base ? " · base de conhecimento v" + D.versao_base : "") +
    " · " + fmt.format(D.total) + (D.total === 1 ? " review" : " reviews");
  document.title = D.titulo;

  var achado = document.getElementById("achado");
  if (!D.total) {
    achado.textContent = "Nenhum review para mostrar.";
  } else if (!D.com_indicador) {
    achado.appendChild(document.createTextNode("Nenhum dos " + fmt.format(D.total) + " reviews tem indicador da base de conhecimento: todos ficaram "));
    achado.appendChild(el("mark", { classe: "i", texto: "indefinidos" }));
    achado.appendChild(document.createTextNode("."));
  } else {
    var partes = [];
    ["Tecnico", "Afetivo-visual", "Misto"].forEach(function (c) {
      var n = D.geral[c];
      if (!n) return;
      partes.push(el("span", {}, [fmt.format(n) + " ", el("mark", { classe: MARCA[c], texto: n === 1 ? SINGULAR[c] : PLURAL[c] })]));
    });
    var filhos = ["De " + fmt.format(D.total) + " reviews, " + fmt.format(D.com_indicador) + " (" + pct(D.com_indicador, D.total) + ") " +
      (D.com_indicador === 1 ? "tem" : "têm") + " algum indicador da base: "].concat(lista_e(partes)).concat(["."]);
    filhos.forEach(function (f) { achado.appendChild(typeof f === "string" ? document.createTextNode(f) : f); });
    var resto = D.geral["Indefinido"];
    if (resto) {
      achado.appendChild(document.createTextNode(" Os outros " + fmt.format(resto) + " ficaram "));
      achado.appendChild(el("mark", { classe: "i", texto: "indefinidos" }));
      achado.appendChild(document.createTextNode("."));
    }
  }

  var nJogos = Object.keys(D.por_jogo).length;
  var ctx = "Reviews" + (D.idiomas.length ? " em " + D.idiomas.join(", ") : "") + (D.fonte ? " da " + D.fonte : "") +
    " de " + nJogos + (nJogos === 1 ? " jogo" : " jogos") +
    (D.periodo ? (D.periodo[0] === D.periodo[1] ? ", escritos em " + dataBr(D.periodo[0]) : ", escritos entre " + dataBr(D.periodo[0]) + " e " + dataBr(D.periodo[1])) : "") +
    ". Classificados pelo sistema especialista" + (D.versao_base ? " com a base de conhecimento v" + D.versao_base : "") +
    ". Painel gerado em " + D.gerado + ".";
  document.getElementById("resumo").textContent = ctx;

  // visão geral + ampliação dos que têm indicador
  barra(D.geral, D.total, document.getElementById("barra-geral"));
  // números por categoria, em cartões
  var REGRA = { "Tecnico": "R1", "Afetivo-visual": "R2", "Misto": "R3", "Indefinido": "R4" };
  var kp = document.getElementById("kpis");
  kp.appendChild(el("div", { classe: "kpi k-total" }, [el("span", { classe: "rotulo-cat", texto: "Reviews analisados" }),
    el("b", { texto: fmt.format(D.total) }), el("small", { texto: nJogos + (nJogos === 1 ? " jogo" : " jogos") })]));
  D.categorias.forEach(function (c) {
    var n = D.geral[c] || 0;
    kp.appendChild(el("div", { classe: "kpi k-" + c }, [el("span", { classe: "rotulo-cat", texto: NOMES[c] }),
      el("b", { texto: fmt.format(n) }), el("small", { texto: pct(n, D.total) + " · regra " + REGRA[c] })]));
  });
  var zoom = document.getElementById("zoom");
  if (D.com_indicador && D.geral["Indefinido"]) {
    var SVG = "http://www.w3.org/2000/svg";
    var fun = document.createElementNS(SVG, "svg");
    fun.setAttribute("class", "funil"); fun.setAttribute("viewBox", "0 0 100 36");
    fun.setAttribute("preserveAspectRatio", "none"); fun.setAttribute("aria-hidden", "true");
    var poli = document.createElementNS(SVG, "polygon");
    var fr = (100 * D.com_indicador / D.total).toFixed(3);
    poli.setAttribute("points", "0,0 " + fr + ",0 100,36 0,36");
    fun.appendChild(poli);
    zoom.appendChild(fun);
    var so = {}; D.categorias.forEach(function (c) { so[c] = c === "Indefinido" ? 0 : D.geral[c]; });
    var b2 = el("div", { classe: "barra grande" });
    var partes2 = barra(so, D.com_indicador, b2);
    b2.setAttribute("role", "img");
    b2.setAttribute("aria-label", "Entre os " + D.com_indicador + " reviews com indicador: " + partes2.join(", "));
    zoom.appendChild(b2);
    zoom.appendChild(el("p", { classe: "zoom-titulo", style: "margin-top:var(--e2)" }, [
      el("b", { classe: "num", texto: fmt.format(D.com_indicador) + " reviews com algum indicador" }), ", ampliados."
    ]));
  }
  // legenda como tabela: nome e regra de cada categoria, com os números alinhados
  var leg = document.getElementById("legenda");
  leg.appendChild(el("thead", {}, [el("tr", {}, ["Categoria", "Reviews", "Do total", "Dos com indicador"].map(function (t) {
    return el("th", { scope: "col", texto: t });
  }))]));
  var legCorpo = el("tbody");
  D.categorias.forEach(function (c) {
    var n = D.geral[c];
    legCorpo.appendChild(el("tr", {}, [
      el("th", { scope: "row" }, [el("span", { classe: "nome" }, [
        el("span", { classe: "cor f-" + c, "aria-hidden": "true" }), el("b", { texto: NOMES[c] }), el("span", { classe: "desc", texto: DESC[c] })])]),
      el("td", { texto: fmt.format(n) }),
      el("td", { texto: pct(n, D.total) }),
      el("td", { texto: c !== "Indefinido" && D.com_indicador ? pct(n, D.com_indicador) : "" })
    ]));
  });
  leg.appendChild(legCorpo);

  // filtros
  var estado = { jogo: "", cat: "", busca: "", limite: 30, periodo: null, soIndicador: false, celula: null };
  var selJogo = document.getElementById("f-jogo");
  var botoesJogo = [];
  var escolherJogo = function (j) { estado.jogo = estado.jogo === j ? "" : j; selJogo.value = estado.jogo; estado.periodo = null; estado.limite = 30; render(); };

  // tabela comparativa por jogo
  var COLUNAS = [
    { chave: "jogo", titulo: "Jogo", texto: true },
    { chave: "total", titulo: "Reviews" },
    { chave: "com", titulo: "Com indicador", cor: "var(--tinta-suave)" },
    { chave: "Tecnico", titulo: "Técnico", cor: "var(--tec)" },
    { chave: "Afetivo-visual", titulo: "Afetivo-visual", cor: "var(--afe)" },
    { chave: "Misto", titulo: "Misto", cor: "color-mix(in srgb, var(--tec) 50%, var(--afe))" },
    { chave: "rec", titulo: "Recomendam", cor: "var(--tinta)" }
  ];
  var linhasJogo = Object.keys(D.por_jogo).map(function (j) {
    var c = D.por_jogo[j], tot = 0;
    D.categorias.forEach(function (k) { tot += c[k]; });
    var rp = D.rec_por_jogo[j];
    return { jogo: j, total: tot, com: tot - c["Indefinido"], "Tecnico": c["Tecnico"], "Afetivo-visual": c["Afetivo-visual"],
      "Misto": c["Misto"], rec: rp ? rp[0] : null, recBase: rp ? rp[1] : 0 };
  });
  var temRec = linhasJogo.some(function (l) { return l.rec !== null; });
  var colunas = COLUNAS.filter(function (c) { return c.chave !== "rec" || temRec; });
  var ordem = { chave: "jogo", desc: false };
  var valor = function (l, k) {   // valor usado para ordenar (percentual, exceto jogo e total)
    if (k === "jogo") return l.jogo.toLowerCase();
    if (k === "total") return l.total;
    if (k === "rec") return l.recBase ? l.rec / l.recBase : -1;
    return l.total ? l[k] / l.total : 0;
  };
  var tab = document.getElementById("tab-jogos");
  function desenharTabela() {
    tab.textContent = "";
    var linhas = linhasJogo.slice().sort(function (a, b) {
      var x = valor(a, ordem.chave), y = valor(b, ordem.chave);
      var r = x < y ? -1 : x > y ? 1 : 0;
      return ordem.desc ? -r : r;
    });
    var cab = el("tr");
    colunas.forEach(function (c) {
      var th = el("th", { scope: "col" });
      if (ordem.chave === c.chave) th.setAttribute("aria-sort", ordem.desc ? "descending" : "ascending");
      var bt = el("button", { classe: "ordenar", type: "button", texto: c.titulo, "aria-label": "Ordenar por " + c.titulo.toLowerCase() });
      bt.addEventListener("click", function () {
        if (ordem.chave === c.chave) ordem.desc = !ordem.desc; else { ordem.chave = c.chave; ordem.desc = !c.texto; }
        desenharTabela();
      });
      th.appendChild(bt); cab.appendChild(th);
    });
    tab.appendChild(el("thead", {}, [cab]));
    var tb = el("tbody");
    botoesJogo = [];
    linhas.forEach(function (l) {
      var tr = el("tr");
      colunas.forEach(function (c) {
        if (c.chave === "jogo") {
          var b = el("button", { classe: "jogo-btn", type: "button", "aria-pressed": estado.jogo === l.jogo ? "true" : "false", texto: l.jogo });
          b.addEventListener("click", function () { escolherJogo(l.jogo); });
          botoesJogo.push([l.jogo, b]);
          tr.appendChild(el("th", { scope: "row" }, [b]));
        } else if (c.chave === "total") {
          tr.appendChild(el("td", { classe: "num", texto: fmt.format(l.total) }));
        } else {
          var n = l[c.chave], base = c.chave === "rec" ? l.recBase : l.total;
          if (n === null || !base) { tr.appendChild(el("td", { texto: "sem dado" })); return; }
          var frac = n / base;
          tr.appendChild(el("td", {}, [el("div", { classe: "celula" }, [
            el("span", { classe: "num", texto: pct(n, base) }),
            el("span", { classe: "mini", "aria-hidden": "true" }, [el("span", { style: "width:" + (100 * frac) + "%;background:" + c.cor })]),
            el("small", { classe: "num", texto: fmt.format(n) + " de " + fmt.format(base) })
          ])]));
        }
      });
      tb.appendChild(tr);
    });
    tab.appendChild(tb);
  }
  desenharTabela();
  Object.keys(D.por_jogo).forEach(function (j) { selJogo.appendChild(el("option", { value: j, texto: j })); });
  selJogo.addEventListener("change", function () { estado.jogo = selJogo.value; estado.periodo = null; estado.limite = 30; render(); });

  // recomendação por categoria
  var recBox = document.getElementById("rec");
  if (!D.recomendacao) {
    document.getElementById("sec-rec").hidden = true;
  } else {
    D.categorias.forEach(function (c) {
      var r = D.recomendacao[c], tot = r.sim + r.nao;
      if (!tot) return;
      var b = el("div", { classe: "barra", role: "img",
        "aria-label": NOMES[c] + ": " + pct(r.sim, tot) + " recomendam, " + pct(r.nao, tot) + " não recomendam" });
      if (r.sim) b.appendChild(el("div", { classe: "fatia r-sim", style: "flex:" + r.sim }));
      if (r.nao) b.appendChild(el("div", { classe: "fatia r-nao", style: "flex:" + r.nao }));
      recBox.appendChild(el("div", { classe: "rec-linha" }, [
        el("span", {}, [el("mark", { classe: MARCA[c], texto: NOMES[c] }), el("small", { classe: "num", texto: nReviews(tot) })]),
        b,
        el("span", { classe: "conta num", texto: pct(r.sim, tot) + " recomendam" })
      ]));
    });
  }

  // ao longo do tempo
  var tempoBox = document.getElementById("tempo"), tempoSub = document.getElementById("tempo-sub");
  var MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  var paraDia = function (iso) { var p = iso.split("-"); return Date.UTC(+p[0], +p[1] - 1, +p[2]); };
  var isoDe = function (ms) { return new Date(ms).toISOString().slice(0, 10); };
  var comData = D.reviews.filter(function (r) { return /^\d{4}-\d{2}-\d{2}$/.test(r.data); });
  var porMes = D.periodo && (paraDia(D.periodo[1]) - paraDia(D.periodo[0])) / 864e5 > 120;
  function baldes() {
    if (!D.periodo) return [];
    var out = [], ini = paraDia(D.periodo[0]), fim = paraDia(D.periodo[1]);
    if (porMes) {
      var d = new Date(ini); d.setUTCDate(1);
      while (d.getTime() <= fim) {
        var a = d.getTime(); d.setUTCMonth(d.getUTCMonth() + 1);
        var m = new Date(a);
        out.push({ ini: isoDe(a), fim: isoDe(d.getTime()), curto: MESES[m.getUTCMonth()] + "/" + String(m.getUTCFullYear()).slice(2),
          longo: MESES[m.getUTCMonth()] + "/" + m.getUTCFullYear() });
      }
    } else {
      var dia = new Date(ini).getUTCDay(), seg = ini - ((dia + 6) % 7) * 864e5;   // começa na segunda-feira
      for (var t = seg; t <= fim; t += 7 * 864e5) {
        var dd = new Date(t), rot = String(dd.getUTCDate()).padStart(2, "0") + "/" + String(dd.getUTCMonth() + 1).padStart(2, "0");
        out.push({ ini: isoDe(t), fim: isoDe(t + 7 * 864e5), curto: rot, longo: "semana de " + rot + "/" + dd.getUTCFullYear() });
      }
    }
    return out;
  }
  var BALDES = baldes();
  var SVGNS = "http://www.w3.org/2000/svg";
  var svgEl = function (tag, attrs) { var e = document.createElementNS(SVGNS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); return e; };
  var ORDEM_PILHA = ["Tecnico", "Afetivo-visual", "Misto", "Indefinido"];
  document.getElementById("so-indicador").addEventListener("change", function (ev) { estado.soIndicador = ev.target.checked; desenharTempo(); });
  function desenharTempo() {
    if (!BALDES.length || !comData.length) {
      document.getElementById("sec-tempo").hidden = true; return;
    }
    var fonte = comData.filter(function (r) { return (!estado.jogo || r.jogo === estado.jogo) && (!estado.soIndicador || r.cat !== "Indefinido"); });
    var cont = BALDES.map(function (b) {
      var c = { total: 0 }; ORDEM_PILHA.forEach(function (k) { c[k] = 0; });
      fonte.forEach(function (r) { if (r.data >= b.ini && r.data < b.fim) { c[r.cat]++; c.total++; } });
      return c;
    });
    var maior = Math.max.apply(null, cont.map(function (c) { return c.total; }).concat([1]));
    var max = (function (v) {   // teto "redondo" do eixo: 115 -> 120, 7 -> 8
      var pot = Math.pow(10, Math.floor(Math.log10(v)));
      var m = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find(function (k) { return k * pot >= v; });
      return Math.max(2, Math.round(m * pot));
    })(maior);
    var descTempo = (porMes ? "Reviews por mês" : "Reviews por semana") + (estado.jogo ? " de " + estado.jogo : ", todos os jogos") + ".";
    tempoSub.textContent = descTempo + " ";
    tempoSub.appendChild(el("span", { classe: "instrucao", texto: "Clique numa coluna para ver só os reviews daquele período." }));
    var H = document.documentElement.classList.contains("apresentacao") ? 300 : 240;
    var W = Math.max(280, tempoBox.clientWidth || 800), esq = 36, base = H - 28, topo = 8;
    var largura = (W - esq) / BALDES.length, barraW = Math.max(2, Math.min(56, largura * 0.72));
    var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "group", "aria-label": descTempo });
    var eixo = svgEl("g", { "class": "eixo", "aria-hidden": "true" });
    [0, Math.round(max / 2), max].forEach(function (v, i, arr) {
      if (i === 1 && (v === 0 || v === max)) return;
      var y = base - (base - topo) * v / max;
      eixo.appendChild(svgEl("line", { x1: esq, x2: W, y1: y, y2: y }));
      var t = svgEl("text", { x: esq - 6, y: y + 4, "text-anchor": "end" }); t.textContent = fmt.format(v); eixo.appendChild(t);
    });
    var passo = Math.ceil(BALDES.length / Math.max(1, Math.floor((W - esq) / 56)));
    BALDES.forEach(function (b, i) {
      if (i % passo) return;
      var t = svgEl("text", { x: esq + largura * (i + 0.5), y: H - 8, "text-anchor": "middle" }); t.textContent = b.curto; eixo.appendChild(t);
    });
    svg.appendChild(eixo);
    tempoBox.classList.toggle("escolhido", !!estado.periodo);
    BALDES.forEach(function (b, i) {
      var c = cont[i], x = esq + largura * i;
      var partes = ORDEM_PILHA.filter(function (k) { return c[k]; }).map(function (k) { return nCat(c[k], k); });
      var ativo = estado.periodo && estado.periodo.ini === b.ini;
      var g = svgEl("g", { "class": "col", tabindex: "0", role: "button", "aria-pressed": ativo ? "true" : "false",
        "aria-label": b.longo + ": " + nReviews(c.total) + (partes.length ? " (" + partes.join(", ") + ")" : "") + ". " + (ativo ? "Clique para limpar o período." : "Clique para filtrar a lista.") });
      g.appendChild(svgEl("rect", { "class": "alvo", x: x + 1, y: topo, width: largura - 2, height: base - topo, rx: 3 }));
      var y = base;
      ORDEM_PILHA.forEach(function (k) {
        if (!c[k]) return;
        var h = (base - topo) * c[k] / max;
        y -= h;
        var x0 = x + (largura - barraW) / 2, hh = Math.max(h, 1);
        g.appendChild(svgEl("rect", { "class": "s-" + k, x: x0, y: y, width: barraW, height: hh }));
      });
      var titulo = svgEl("title", {}); titulo.textContent = b.longo + ": " + nReviews(c.total) + (partes.length ? " (" + partes.join(", ") + ")" : ""); g.appendChild(titulo);
      var escolher = function () {
        estado.periodo = ativo ? null : { ini: b.ini, fim: b.fim, rotulo: b.longo };
        estado.limite = 30; render();
        var foco = tempoBox.querySelectorAll(".col")[i]; if (foco) foco.focus();
      };
      g.addEventListener("click", escolher);
      g.addEventListener("keydown", function (ev) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); escolher(); } });
      svg.appendChild(g);
    });
    tempoBox.textContent = ""; tempoBox.appendChild(svg);
  }
  var redesenho = null;
  window.addEventListener("resize", function () { clearTimeout(redesenho); redesenho = setTimeout(desenharTempo, 150); });
  document.getElementById("limpar-periodo").addEventListener("click", function () { estado.periodo = null; estado.limite = 30; render(); });
  var busca = document.getElementById("f-busca");
  busca.addEventListener("input", function () { estado.busca = busca.value.trim().toLowerCase(); estado.limite = 30; render(); });
  var cats = document.getElementById("f-cats");
  var botoesCat = [];
  [""].concat(D.categorias).forEach(function (c) {
    var b = el("button", { type: "button", "aria-pressed": c === "" ? "true" : "false" });
    b.addEventListener("click", function () { estado.cat = c; estado.limite = 30; render(); });
    botoesCat.push([c, b]); cats.appendChild(b);
  });

  // indicadores
  var indBox = document.getElementById("indicadores");
  [["t", "Técnicos", "var(--tec)"], ["a", "Afetivo-visuais", "var(--afe)"]].forEach(function (g) {
    var lista = D.indicadores[g[0]];
    var bloco = el("div", {}, [el("h3", { texto: g[1] })]);
    if (!lista.length) {
      bloco.appendChild(el("p", { classe: "vazio", texto: "Nenhum indicador " + g[1].toLowerCase().replace(/s$/, "") + " foi encontrado nestes reviews." }));
    } else {
      var max = lista[0][1], VISIVEIS = 8, aberto = false;
      var ul = el("ul", { classe: "ind-lista" });
      var resto = el("p", { classe: "estado", style: "margin:var(--e3) 0 0" });
      var bt = el("button", { classe: "mais", type: "button", "aria-expanded": "false", style: "margin-top:var(--e2)" });
      var pintar = function () {
        ul.textContent = "";
        (aberto ? lista : lista.slice(0, VISIVEIS)).forEach(function (par) {
          ul.appendChild(el("li", {}, [
            el("span", { texto: par[0] }),
            el("span", { classe: "trilho", "aria-hidden": "true" }, [el("span", { classe: "enchimento", style: "display:block;width:" + (100 * par[1] / max) + "%;background:" + g[2] })]),
            el("span", { classe: "num", texto: fmt.format(par[1]) })
          ]));
        });
        var escondidos = lista.slice(VISIVEIS), uma = escondidos.filter(function (p) { return p[1] === 1; }).length;
        resto.hidden = aberto || !escondidos.length;
        resto.textContent = escondidos.length ? "Mais " + escondidos.length + (escondidos.length === 1 ? " indicador" : " indicadores") +
          (uma ? ", " + (uma === escondidos.length ? (uma === 1 ? "com" : "todos com") : uma + " deles com") + " uma ocorrência só." : ".") : "";
        bt.hidden = !escondidos.length;
        bt.textContent = aberto ? "Mostrar só os " + VISIVEIS + " primeiros" : "Ver todos os " + lista.length;
        bt.setAttribute("aria-expanded", aberto ? "true" : "false");
      };
      bt.addEventListener("click", function () { aberto = !aberto; pintar(); });
      pintar();
      bloco.appendChild(ul); bloco.appendChild(resto); bloco.appendChild(bt);
    }
    indBox.appendChild(bloco);
  });

  // avaliação
  var av = D.avaliacao, avBox = document.getElementById("avaliacao"), botoesCelula = [];
  function comando(texto) {   // bloco de comando com botão de copiar
    var cod = el("code", { texto: texto });
    var bt = el("button", { type: "button", texto: "Copiar", "aria-label": "Copiar o comando " + texto });
    bt.addEventListener("click", function () {
      var feito = function () { bt.textContent = "Copiado"; setTimeout(function () { bt.textContent = "Copiar"; }, 2000); };
      var selecionar = function () {   // sem acesso à área de transferência (ex.: arquivo local): deixa o texto selecionado
        var r = document.createRange(); r.selectNodeContents(cod);
        var sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); bt.textContent = "Selecionado: Ctrl+C";
      };
      try { navigator.clipboard.writeText(texto).then(feito, selecionar); } catch (e) { selecionar(); }
    });
    return el("div", { classe: "comando" }, [cod, bt]);
  }
  if (!av) {
    avBox.appendChild(el("div", { classe: "vazio" }, [
      el("p", { texto: "Ainda não há gabarito manual, então não dá para medir acertos e erros do sistema." }),
      el("ol", {}, [
        el("li", {}, ["Gere a amostra cega e preencha a coluna categoria_manual:", comando("python -m src.amostragem --tamanho 200")]),
        el("li", {}, ["Salve como data/gabarito_rotulado.csv e avalie:", comando("python -m src.avaliacao --gabarito data/gabarito_rotulado.csv")])
      ]),
      el("p", { style: "margin-top:var(--e3)", texto: "Este painel é refeito com a matriz de confusão." })
    ]));
  } else {
    var placar = el("div", { classe: "placar" });
    [["Acurácia", pct(av.acuracia, 1)], ["F1 macro", av.f1_macro.toLocaleString("pt-BR", { maximumFractionDigits: 2 })],
     ["Reviews no gabarito", fmt.format(av.n)]].concat(av.kappa === null ? [] : [["Kappa entre anotadores", av.kappa.toLocaleString("pt-BR", { maximumFractionDigits: 2 })]])
      .forEach(function (p) { placar.appendChild(el("div", {}, [el("b", { classe: "num", texto: p[1] }), el("span", { texto: p[0] })])); });
    avBox.appendChild(placar);
    var max = 0; av.matriz.forEach(function (l) { l.forEach(function (v) { if (v > max) max = v; }); });
    var tm = el("table", { classe: "matriz" });
    var cab = el("tr", {}, [el("th", { scope: "col", texto: "Gabarito ↓  Sistema →" })]);
    D.categorias.forEach(function (c) { cab.appendChild(el("th", { scope: "col", texto: NOMES[c] })); });
    tm.appendChild(el("thead", {}, [cab]));
    var tb = el("tbody");
    av.matriz.forEach(function (linha, i) {
      var tr = el("tr", {}, [el("th", { scope: "row", texto: NOMES[D.categorias[i]] })]);
      var totalLinha = linha.reduce(function (a, b) { return a + b; }, 0);
      linha.forEach(function (v, j) {
        var a = (max && v) ? 0.1 + 0.5 * v / max : 0;
        var conteudo = [fmt.format(v), el("small", { texto: totalLinha ? pct(v, totalLinha) + " da linha" : "" })];
        var td = el("td", { classe: i === j ? "diag" : "",
          style: "background:color-mix(in srgb, " + (i === j ? "var(--tec)" : "var(--afe)") + " " + Math.round(a * 100) + "%, transparent)" });
        if (D.clicavel && v) {
          var man = D.categorias[i], sis = D.categorias[j];
          var b = el("button", { classe: "celula-btn num", type: "button", "aria-pressed": "false",
            "aria-label": "Gabarito " + NOMES[man] + ", sistema " + NOMES[sis] + ": " + nReviews(v) + ". Mostrar na lista." }, conteudo);
          b.addEventListener("click", function () {
            estado.celula = (estado.celula && estado.celula.man === man && estado.celula.sis === sis) ? null : { man: man, sis: sis };
            estado.limite = 30; render();
            if (estado.celula) document.getElementById("t-rev").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
          });
          botoesCelula.push([man, sis, b]);
          td.appendChild(b);
        } else {
          conteudo.forEach(function (c) { td.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
        }
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    tm.appendChild(tb);
    var tmet = el("table", {});
    tmet.appendChild(el("thead", {}, [el("tr", {}, ["Categoria", "Precisão", "Revocação", "F1", "Suporte"].map(function (t) { return el("th", { scope: "col", texto: t }); }))]));
    var tb2 = el("tbody");
    av.metricas.forEach(function (m) {
      tb2.appendChild(el("tr", {}, [el("th", { scope: "row", texto: NOMES[m.categoria] || m.categoria }),
        el("td", { texto: m.precisao.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) }),
        el("td", { texto: m.revocacao.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) }),
        el("td", { texto: m.f1.toLocaleString("pt-BR", { maximumFractionDigits: 2 }) }),
        el("td", { texto: fmt.format(m.suporte) })]));
    });
    tmet.appendChild(tb2);
    avBox.appendChild(el("div", { classe: "duas" }, [el("div", { classe: "rolagem" }, [tm]), el("div", { classe: "rolagem" }, [tmet])]));
    if (D.clicavel) avBox.appendChild(el("p", { classe: "estado instrucao", style: "margin-top:var(--e3)", texto: "Clique numa célula da matriz para ver na lista os reviews daquele par gabarito × sistema." }));
  }

  // reviews
  var ORDENS = {
    indicadores: { rotulo: "os com mais indicadores primeiro", f: function (x, y) { return (y.et + y.ea) - (x.et + x.ea); } },
    recentes: { rotulo: "os mais recentes primeiro", f: function (x, y) { return x.data < y.data ? 1 : x.data > y.data ? -1 : 0; } },
    uteis: { rotulo: "os mais votados como úteis primeiro", f: function (x, y) { return (y.util || 0) - (x.util || 0); } }
  };
  var selOrdem = document.getElementById("f-ordem");
  var temData = D.reviews.some(function (r) { return r.data; }), temUtil = D.reviews.some(function (r) { return r.util !== null; });
  [].slice.call(selOrdem.options).forEach(function (o) {
    if ((o.value === "recentes" && !temData) || (o.value === "uteis" && !temUtil)) o.remove();
  });
  var ordenados = [];
  var ordenar = function () { ordenados = D.reviews.slice().sort(ORDENS[selOrdem.value].f); };
  ordenar();
  selOrdem.addEventListener("change", function () { ordenar(); estado.limite = 30; render(); });
  document.getElementById("limpar-celula").addEventListener("click", function () { estado.celula = null; estado.limite = 30; render(); });
  var lista = document.getElementById("lista"), info = document.getElementById("estado"), mais = document.getElementById("mais");
  mais.addEventListener("click", function () { estado.limite += 30; render(); });

  var CURTO = 420, MARGEM = 140;
  // janelas [inicio, fim) do texto a mostrar: tudo, ou o entorno dos indicadores
  function janelas(r, inteiro) {
    if (inteiro || r.texto.length <= CURTO) return [[0, r.texto.length]];
    if (!r.marcas.length) return [[0, 300]];
    var js = [];
    r.marcas.forEach(function (m) {
      var a = Math.max(0, m[0] - MARGEM), b = Math.min(r.texto.length, m[1] + MARGEM);
      var ult = js[js.length - 1];
      if (ult && a <= ult[1]) ult[1] = Math.max(ult[1], b); else js.push([a, b]);
    });
    return js;
  }
  function escrever(p, r, a, b) {
    var pos = a;
    r.marcas.forEach(function (m) {
      if (m[1] <= a || m[0] >= b) return;
      if (m[0] > pos) p.appendChild(document.createTextNode(r.texto.slice(pos, m[0])));
      var mk = el("mark", { classe: m[2] + (m[3] ? " radical" : ""), texto: r.texto.slice(m[0], m[1]) });
      if (m[3]) mk.title = "Encontrado pelo radical da palavra";
      p.appendChild(mk);
      pos = m[1];
    });
    if (pos < b) p.appendChild(document.createTextNode(r.texto.slice(pos, b)));
  }
  function textoMarcado(r, inteiro) {
    var p = el("p", { classe: "texto" });
    var js = janelas(r, inteiro);
    js.forEach(function (j, i) {
      if (j[0] > 0) p.appendChild(el("span", { classe: "reticencias", texto: i ? " … " : "… " }));
      escrever(p, r, j[0], j[1]);
    });
    var fimMostrado = js[js.length - 1][1];
    if (fimMostrado < r.texto.length || r.cortado) p.appendChild(el("span", { classe: "reticencias", texto: " …" }));
    return p;
  }

  function cartao(r) {
    var rec = r.rec === "sim" ? "Recomenda o jogo" : r.rec === "nao" ? "Não recomenda o jogo" : "";
    var porque = el("div", { classe: "porque" }, [
      el("span", {}, [el("b", { texto: "Regra " + r.regra + ": " }),
        "escore técnico " + r.et + ", afetivo-visual " + r.ea + ", confiança " + r.conf.toLocaleString("pt-BR", { maximumFractionDigits: 2 })])
    ]);
    if (r.it.length) porque.appendChild(el("span", {}, [el("b", { texto: "Indicadores técnicos: " }), r.it.join("; ")]));
    if (r.ia.length) porque.appendChild(el("span", {}, [el("b", { texto: "Indicadores afetivo-visuais: " }), r.ia.join("; ")]));
    var texto = textoMarcado(r, false);
    var horas = r.horas === null ? null : r.horas.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " h jogadas ao escrever";
    var util = !r.util ? null : fmt.format(r.util) + (r.util === 1 ? " pessoa achou útil" : " pessoas acharam útil");
    var artigo = el("article", { classe: "review c-" + r.cat }, [
      el("div", { classe: "cabeca" }, [
        el("span", { classe: "etiqueta c-" + r.cat, texto: NOMES[r.cat] }),
        r.man ? el("span", { classe: "etiqueta gabarito c-" + r.man, texto: "Gabarito: " + (NOMES[r.man] || r.man) }) : null,
        el("span", { classe: "jogo-nome", texto: r.jogo }),
        r.data ? el("span", { classe: "num", texto: r.data.split("-").reverse().join("/") }) : null,
        rec ? el("span", { texto: rec }) : null,
        horas ? el("span", { classe: "meta num", texto: horas }) : null,
        util ? el("span", { classe: "meta num", texto: util }) : null]),
      texto
    ]);
    if (r.texto.length > CURTO) {
      var aberto = false;
      var botao = el("button", { classe: "ler", type: "button", "aria-expanded": "false", texto: "Ler o review inteiro" });
      botao.addEventListener("click", function () {
        aberto = !aberto;
        var novo = textoMarcado(r, aberto);
        artigo.replaceChild(novo, texto); texto = novo;
        botao.setAttribute("aria-expanded", aberto ? "true" : "false");
        botao.textContent = aberto ? "Mostrar só o trecho" : "Ler o review inteiro";
      });
      artigo.appendChild(botao);
    }
    artigo.appendChild(porque);
    return artigo;
  }

  function render() {
    botoesJogo.forEach(function (p) { p[1].setAttribute("aria-pressed", p[0] === estado.jogo ? "true" : "false"); });
    desenharTempo();
    var chip = document.getElementById("chip-periodo");
    chip.hidden = !estado.periodo;
    if (estado.periodo) document.getElementById("chip-texto").textContent = estado.periodo.rotulo;
    var chipC = document.getElementById("chip-celula");
    chipC.hidden = !estado.celula;
    if (estado.celula) document.getElementById("chip-celula-texto").textContent =
      "gabarito " + NOMES[estado.celula.man] + ", sistema " + NOMES[estado.celula.sis];
    botoesCelula.forEach(function (p) {
      p[2].setAttribute("aria-pressed", estado.celula && estado.celula.man === p[0] && estado.celula.sis === p[1] ? "true" : "false");
    });
    var base = ordenados.filter(function (r) {
      return (!estado.jogo || r.jogo === estado.jogo) && (!estado.busca || r.texto.toLowerCase().indexOf(estado.busca) >= 0) &&
        (!estado.periodo || (r.data >= estado.periodo.ini && r.data < estado.periodo.fim)) &&
        (!estado.celula || (r.man === estado.celula.man && r.cat === estado.celula.sis));
    });
    botoesCat.forEach(function (p) {
      var n = p[0] ? base.filter(function (r) { return r.cat === p[0]; }).length : base.length;
      p[1].textContent = (p[0] ? NOMES[p[0]] : "Todas") + " (" + fmt.format(n) + ")";
      p[1].setAttribute("aria-pressed", p[0] === estado.cat ? "true" : "false");
    });
    var filtrados = estado.cat ? base.filter(function (r) { return r.cat === estado.cat; }) : base;
    lista.textContent = "";
    filtrados.slice(0, estado.limite).forEach(function (r) { lista.appendChild(cartao(r)); });
    info.textContent = filtrados.length
      ? "Mostrando " + fmt.format(Math.min(estado.limite, filtrados.length)) + " de " + fmt.format(filtrados.length) + " reviews, " + ORDENS[selOrdem.value].rotulo + "."
      : "Nenhum review com esses filtros. Tente outra categoria, limpe a busca, o período ou o filtro da matriz.";
    mais.hidden = filtrados.length <= estado.limite;
    var filtros = [];
    if (estado.jogo) filtros.push("jogo " + estado.jogo);
    if (estado.cat) filtros.push("categoria " + NOMES[estado.cat]);
    if (estado.periodo) filtros.push("período " + estado.periodo.rotulo);
    if (estado.celula) filtros.push("matriz: gabarito " + NOMES[estado.celula.man] + ", sistema " + NOMES[estado.celula.sis]);
    if (estado.busca) filtros.push("busca \u201c" + estado.busca + "\u201d");
    document.getElementById("nota-impressao").textContent = "Lista impressa: " + nReviews(filtrados.length) +
      (filtros.length ? " (" + filtros.join("; ") + ")" : ", sem filtros") + ", " + ORDENS[selOrdem.value].rotulo + ".";
  }
  // filtro guardado na URL (#jogo=...&cat=...): dá para compartilhar um recorte
  var semMovimento = matchMedia("(prefers-reduced-motion: reduce)").matches;
  function lerDaUrl() {
    var h = location.hash.slice(1);
    if (h.indexOf("=") < 0) return;
    var p = new URLSearchParams(h);
    if (p.get("jogo") && D.por_jogo[p.get("jogo")]) { estado.jogo = p.get("jogo"); selJogo.value = estado.jogo; }
    if (p.get("cat") && D.categorias.indexOf(p.get("cat")) >= 0) estado.cat = p.get("cat");
    var bal = BALDES.filter(function (b) { return b.ini === p.get("periodo"); })[0];
    if (bal) estado.periodo = { ini: bal.ini, fim: bal.fim, rotulo: bal.longo };
    if (p.get("busca")) { estado.busca = p.get("busca").toLowerCase(); busca.value = p.get("busca"); }
    if (p.get("ordem") && selOrdem.querySelector('option[value="' + p.get("ordem").replace(/[^a-z]/g, "") + '"]')) { selOrdem.value = p.get("ordem"); ordenar(); }
    if (p.get("so") === "1") { estado.soIndicador = true; document.getElementById("so-indicador").checked = true; }
    var cel = (p.get("celula") || "").split("|");
    if (D.clicavel && cel.length === 2 && D.categorias.indexOf(cel[0]) >= 0 && D.categorias.indexOf(cel[1]) >= 0) estado.celula = { man: cel[0], sis: cel[1] };
  }
  function salvarNaUrl() {
    var p = new URLSearchParams();
    if (estado.jogo) p.set("jogo", estado.jogo);
    if (estado.cat) p.set("cat", estado.cat);
    if (estado.periodo) p.set("periodo", estado.periodo.ini);
    if (estado.busca) p.set("busca", estado.busca);
    if (selOrdem.value !== "indicadores") p.set("ordem", selOrdem.value);
    if (estado.soIndicador) p.set("so", "1");
    if (estado.celula) p.set("celula", estado.celula.man + "|" + estado.celula.sis);
    var novo = p.toString();
    try { history.replaceState(null, "", novo ? "#" + novo : location.pathname + location.search); } catch (e) {}
  }
  var renderBase = render;
  render = function () { renderBase(); salvarNaUrl(); };
  document.getElementById("so-indicador").addEventListener("change", salvarNaUrl);
  // os links do índice rolam até a seção sem trocar o endereço (que guarda o filtro)
  [].slice.call(document.querySelectorAll(".indice a")).forEach(function (a) {
    a.addEventListener("click", function (ev) {
      var alvo = document.getElementById(a.getAttribute("href").slice(1));
      if (!alvo || alvo.hidden) return;
      ev.preventDefault();
      alvo.scrollIntoView({ behavior: semMovimento ? "auto" : "smooth" });
      var titulo = alvo.querySelector("h2");
      if (titulo) { titulo.setAttribute("tabindex", "-1"); titulo.focus({ preventScroll: true }); }
    });
  });
  // seções escondidas (sem dados) somem do índice
  [].slice.call(document.querySelectorAll(".indice li")).forEach(function (li) {
    var alvo = document.getElementById(li.firstChild.getAttribute("href").slice(1));
    if (!alvo || alvo.hidden) li.hidden = true;
  });
  lerDaUrl();
  render();

  // barra de ferramentas: modo apresentação, tema e impressão
  var raizHtml = document.documentElement, bApr = document.getElementById("b-apresentacao");
  function apresentacao(ligar) {
    raizHtml.classList.toggle("apresentacao", ligar);
    bApr.setAttribute("aria-pressed", ligar ? "true" : "false");
    bApr.textContent = ligar ? "Sair do modo apresentação" : "Modo apresentação";
    desenharTempo();
  }
  bApr.addEventListener("click", function () { apresentacao(!raizHtml.classList.contains("apresentacao")); });
  document.addEventListener("keydown", function (ev) {
    var alvo = ev.target && ev.target.tagName;
    if (ev.ctrlKey || ev.metaKey || ev.altKey || alvo === "INPUT" || alvo === "SELECT" || alvo === "TEXTAREA") return;
    if (ev.target.closest && ev.target.closest(".dd")) return;
    if (ev.key === "p" || ev.key === "P") { ev.preventDefault(); apresentacao(!raizHtml.classList.contains("apresentacao")); }
    else if (ev.key === "Escape" && raizHtml.classList.contains("apresentacao")) apresentacao(false);
  });
  var selTema = document.getElementById("f-tema");
  selTema.value = raizHtml.getAttribute("data-tema") || "";
  selTema.addEventListener("change", function () {
    if (selTema.value) raizHtml.setAttribute("data-tema", selTema.value); else raizHtml.removeAttribute("data-tema");
    try { if (selTema.value) localStorage.setItem("painel-tema", selTema.value); else localStorage.removeItem("painel-tema"); } catch (e) {}
    if (typeof pintarFolha === "function") pintarFolha();
  });
  // dropdowns próprios (a lista nativa do <select> não aceita estilo). O <select> continua
  // no lugar, escondido: os filtros leem e mudam o valor dele como antes, e o dropdown espelha.
  var SETA = '<svg class="dd-seta" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
  var CHECK = '<svg class="dd-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';
  var abertos = [];
  function fecharTodos() { abertos.slice().forEach(function (f) { f(false); }); }
  function dropdown(sel) {
    var id = sel.id, caixa = el("div", { classe: "dd" });
    var botao = el("button", { type: "button", classe: "dd-botao", id: id + "-botao", "aria-haspopup": "listbox", "aria-expanded": "false", "aria-controls": id + "-lista" });
    var valor = el("span", { classe: "dd-valor" });
    botao.appendChild(valor); botao.insertAdjacentHTML("beforeend", SETA);
    var lista = el("ul", { classe: "dd-lista", id: id + "-lista", role: "listbox", tabindex: "-1", hidden: "" });
    var rotulo = sel.closest("label"), nome = "";
    if (rotulo) {   // nome acessível: o texto do rótulo ("Tema", "Jogo", "Ordenar por")
      nome = [].slice.call(rotulo.childNodes).filter(function (n) { return n.nodeType === 3; })
        .map(function (n) { return n.textContent.trim(); }).join(" ").trim();
      lista.setAttribute("aria-label", nome);
    }
    caixa.appendChild(botao); caixa.appendChild(lista);
    sel.parentNode.insertBefore(caixa, sel);   // antes do select: o clique no rótulo vai para o botão
    sel.classList.add("dd-nativo"); sel.setAttribute("tabindex", "-1"); sel.setAttribute("aria-hidden", "true");
    var ativo = -1;
    function opcoes() { return [].slice.call(lista.children); }
    function atualizar() {
      var o = sel.options[sel.selectedIndex];
      valor.textContent = o ? o.textContent : "";
      if (nome) botao.setAttribute("aria-label", nome + ": " + valor.textContent);
    }
    function marcar(i) {
      var ops = opcoes(); if (!ops.length) return;
      ativo = Math.max(0, Math.min(ops.length - 1, i));
      ops.forEach(function (li, k) { li.classList.toggle("ativa", k === ativo); });
      lista.setAttribute("aria-activedescendant", ops[ativo].id);
      ops[ativo].scrollIntoView({ block: "nearest" });
    }
    function montar() {
      lista.textContent = "";
      [].slice.call(sel.options).forEach(function (o, k) {
        var li = el("li", { classe: "dd-opcao", role: "option", id: id + "-op-" + k, "aria-selected": String(k === sel.selectedIndex) });
        li.insertAdjacentHTML("afterbegin", CHECK);
        li.appendChild(el("span", { texto: o.textContent }));
        li.addEventListener("mousemove", function () { if (ativo !== k) marcar(k); });
        li.addEventListener("click", function (ev) { ev.preventDefault(); escolher(k); });   // sem isso o <label> reabre a lista
        lista.appendChild(li);
      });
    }
    function fechar(devolverFoco) {
      if (lista.hidden) return;
      lista.hidden = true; botao.setAttribute("aria-expanded", "false"); lista.removeAttribute("aria-activedescendant");
      abertos = abertos.filter(function (f) { return f !== fechar; });
      if (devolverFoco) botao.focus();
    }
    function abrir() {
      fecharTodos();
      montar(); lista.hidden = false; botao.setAttribute("aria-expanded", "true");
      abertos.push(fechar); marcar(sel.selectedIndex); lista.focus();
    }
    function escolher(k) {
      var mudou = k !== sel.selectedIndex;
      sel.selectedIndex = k; atualizar(); fechar(true);
      if (mudou) sel.dispatchEvent(new Event("change", { bubbles: true }));
    }
    lista.addEventListener("click", function (ev) { ev.preventDefault(); });
    botao.addEventListener("click", function () { if (lista.hidden) abrir(); else fechar(true); });
    botao.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") { ev.preventDefault(); abrir(); }
    });
    lista.addEventListener("keydown", function (ev) {
      var n = opcoes().length;
      if (ev.key === "ArrowDown") { ev.preventDefault(); marcar(ativo + 1); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); marcar(ativo - 1); }
      else if (ev.key === "Home") { ev.preventDefault(); marcar(0); }
      else if (ev.key === "End") { ev.preventDefault(); marcar(n - 1); }
      else if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); if (ativo >= 0) escolher(ativo); }
      else if (ev.key === "Escape") { ev.preventDefault(); fechar(true); }
      else if (ev.key === "Tab") { fechar(false); }
      else if (ev.key.length === 1) {   // pula para a opção que começa com a letra
        var ops = opcoes(), letra = ev.key.toLowerCase();
        for (var d = 1; d <= n; d++) {
          var k = (ativo + d) % n;
          if (ops[k].textContent.trim().toLowerCase().indexOf(letra) === 0) { marcar(k); break; }
        }
      }
    });
    // valor mudado por código (clique num jogo, filtro vindo da URL) também aparece no botão
    var desc = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value");
    Object.defineProperty(sel, "value", { configurable: true,
      get: function () { return desc.get.call(sel); },
      set: function (v) { desc.set.call(sel, v); atualizar(); } });
    sel.addEventListener("change", atualizar);
    atualizar();
  }
  document.addEventListener("mousedown", function (ev) { if (!ev.target.closest || !ev.target.closest(".dd")) fecharTodos(); });
  [selTema, selJogo, selOrdem].forEach(dropdown);
  document.getElementById("b-imprimir").addEventListener("click", function () { window.print(); });
  // na impressão sai a lista filtrada inteira, não só os 30 primeiros
  var limiteAntes = null;
  // folha do PDF na cor do tema atual (inclusive as margens): @page não lê variáveis CSS
  var folha = document.getElementById("estilo-folha");
  function pintarFolha() {
    var cs = getComputedStyle(document.documentElement);
    var papel = cs.getPropertyValue("--papel").trim() || "#ffffff", suave = cs.getPropertyValue("--tinta-suave").trim() || "#4b5159";
    folha.textContent = "@page { background-color: " + papel + "; @top-left { color: " + suave + "; } @bottom-right { color: " + suave + "; } }";
  }
  pintarFolha();
  // Na impressão o navegador reavalia as media queries como papel, e para papel
  // prefers-color-scheme é sempre "claro": isso dispara "change" no meio da impressão.
  // Por isso o tema do sistema só é lido na tela; durante a impressão fica o da tela.
  var imprimindo = false;
  var mqImpressao = window.matchMedia ? window.matchMedia("print") : null;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  function lerSistema() {
    if (!mq || imprimindo || (mqImpressao && mqImpressao.matches)) return;
    if (mq.matches) document.documentElement.setAttribute("data-sistema", "escuro"); else document.documentElement.removeAttribute("data-sistema");
    pintarFolha();
  }
  if (mq) { if (mq.addEventListener) mq.addEventListener("change", lerSistema); else if (mq.addListener) mq.addListener(lerSistema); }
  window.addEventListener("beforeprint", function () { imprimindo = true; pintarFolha(); });
  window.addEventListener("afterprint", function () { imprimindo = false; setTimeout(lerSistema, 0); });
  window.addEventListener("beforeprint", function () { limiteAntes = estado.limite; estado.limite = Infinity; render(); });
  window.addEventListener("afterprint", function () { if (limiteAntes !== null) { estado.limite = limiteAntes; limiteAntes = null; render(); } });

  document.getElementById("rodape").textContent =
    "Painel gerado pelo projeto tcc-triagem-reviews (src/painel.py). Textos de reviews longos foram cortados em " + fmt.format(""" + str(LIMITE_TEXTO) + r""") + " caracteres.";
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

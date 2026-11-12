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


def _lista(valor) -> list:
    if not isinstance(valor, str) or not valor.strip():
        return []
    return [parte.strip() for parte in valor.split(";") if parte.strip()]


def montar_dados(classificados: pd.DataFrame, avaliacao: dict = None) -> dict:
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
        trechos = [t for t in marcar_trechos(cortado, ind_t, ind_a) if t[1] <= len(cortado)]
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
            "rec": str(getattr(linha, "recomendado", "") or ""),
            "data": str(getattr(linha, "data_criacao", "") or "") if "data_criacao" in classificados.columns else "",
        })

    por_jogo = {}
    for jogo, grupo in classificados.groupby("jogo", sort=True):
        contagem = grupo["categoria"].value_counts()
        por_jogo[str(jogo)] = {cat: int(contagem.get(cat, 0)) for cat in CATEGORIAS}

    def top(grupo):
        return sorted(contagem_ind[grupo].items(), key=lambda kv: (-kv[1], kv[0]))[:12]

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
        "indicadores": {"t": top("t"), "a": top("a")},
        "avaliacao": avaliacao,
        "reviews": reviews,
    }


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
    }


def _json_seguro(dados: dict) -> str:
    # impede que um texto com "</script>" feche a tag de dados
    return json.dumps(dados, ensure_ascii=False).replace("</", "<\\/")


def gerar_painel(pasta: Path, destino: Path = None) -> Path:
    pasta = Path(pasta)
    classificados = pd.read_csv(pasta / "reviews_classificados.csv", encoding="utf-8-sig", dtype={"id_review": str})
    dados = montar_dados(classificados, ler_avaliacao(pasta / "avaliacao"))
    destino = Path(destino) if destino else pasta / "painel.html"
    destino.write_text(MODELO.replace("__DADOS__", _json_seguro(dados)), encoding="utf-8")
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
<style>
:root {
  --fundo: #eef3f7; --papel: #ffffff; --tinta: #14212b; --tinta-suave: #4b5b67; --linha: #d3dde5;
  --tec: #0b6f78; --tec-marca: #a6eef2; --afe: #a3205f; --afe-marca: #ffc9e2;
  --ind: #77838d; --foco: #1b5fd6;
  --serifa: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --sans: system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --r-pequeno: 4px; --r-medio: 10px;
  --e1: 4px; --e2: 8px; --e3: 12px; --e4: 16px; --e5: 24px; --e6: 32px; --e7: 48px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fundo: #0e1920; --papel: #15232c; --tinta: #e4edf2; --tinta-suave: #a2b3bf; --linha: #2b3c48;
    --tec: #5fd3db; --tec-marca: #1d5a60; --afe: #ff86bf; --afe-marca: #6a2348;
    --ind: #7f909c; --foco: #8ab4ff;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fundo); color: var(--tinta); font: 16px/1.5 var(--sans); }
main { max-width: 1080px; margin: 0 auto; padding: var(--e6) var(--e4) var(--e7); }
h1 { font: 700 2rem/1.15 var(--sans); margin: 0 0 var(--e2); letter-spacing: -0.01em; }
h2 { font: 650 1.25rem/1.3 var(--sans); margin: 0 0 var(--e3); }
p { margin: 0; }
.sub { color: var(--tinta-suave); max-width: 70ch; }
section { margin-top: var(--e7); }
.num { font-variant-numeric: tabular-nums; }
:focus-visible { outline: 3px solid var(--foco); outline-offset: 2px; }

/* barras empilhadas */
.barra { display: flex; height: 28px; border-radius: var(--r-pequeno); overflow: hidden; background: var(--linha); }
.barra.grande { height: 44px; border-radius: var(--r-medio); }
.fatia { min-width: 2px; }
.f-Tecnico { background: var(--tec); }
.f-Afetivo-visual { background: var(--afe); }
.f-Misto { background: repeating-linear-gradient(135deg, var(--tec) 0 7px, var(--afe) 7px 14px); }
.f-Indefinido { background: var(--ind); }
/* achado em uma frase */
.achado { font: 600 1.5rem/1.4 var(--sans); max-width: 40ch; margin: var(--e5) 0 var(--e3); letter-spacing: -0.005em; }
.achado mark { padding: 0 .15em; }
.contexto { color: var(--tinta-suave); max-width: 75ch; }

/* funil: a fatia com indicador ampliada na segunda barra */
.funil { display: block; width: 100%; height: 36px; }
.funil polygon { fill: var(--linha); opacity: .7; }
.zoom-titulo { font-size: .95rem; color: var(--tinta-suave); margin-bottom: var(--e2); }
.zoom-titulo b { color: var(--tinta); }
.legenda { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: var(--e4); margin-top: var(--e4); }
.legenda div { display: grid; grid-template-columns: 14px 1fr; column-gap: var(--e2); }
.legenda .cor { width: 14px; height: 14px; border-radius: 3px; margin-top: 4px; }
.legenda b { font-weight: 650; }
.legenda span.desc { grid-column: 2; color: var(--tinta-suave); font-size: .9rem; }

/* por jogo */
.jogos { display: grid; gap: var(--e2); }
.jogo { display: grid; grid-template-columns: 220px 1fr 300px; gap: var(--e4); align-items: center;
  width: 100%; padding: var(--e3) var(--e3); border: 1px solid transparent; border-radius: var(--r-medio);
  background: none; color: inherit; font: inherit; text-align: left; cursor: pointer; min-height: 44px; }
.jogo:hover { border-color: var(--linha); background: var(--papel); }
.jogo[aria-pressed="true"] { border-color: var(--tinta-suave); background: var(--papel); }
.jogo .nome { font-weight: 600; }
.jogo .nome small { display: block; color: var(--tinta-suave); font-weight: 400; }
.jogo .conta { color: var(--tinta-suave); font-size: .9rem; }

/* indicadores */
.duas { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr)); gap: var(--e6); }
.ind-lista { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e2); }
.ind-lista li { display: grid; grid-template-columns: minmax(120px, 42%) 1fr 3ch; gap: var(--e3); align-items: center; }
.ind-lista .trilho { height: 10px; background: var(--linha); border-radius: 5px; overflow: hidden; }
.ind-lista .enchimento { height: 100%; }
.vazio { color: var(--tinta-suave); background: var(--papel); border: 1px dashed var(--linha); border-radius: var(--r-medio); padding: var(--e4); }
.vazio code { font-size: .9em; }

/* avaliacao */
.placar { display: flex; flex-wrap: wrap; gap: var(--e6); margin-bottom: var(--e5); }
.placar div b { display: block; font-size: 1.75rem; line-height: 1.1; }
.placar div span { color: var(--tinta-suave); font-size: .9rem; }
table { border-collapse: collapse; font-variant-numeric: tabular-nums; }
th, td { padding: var(--e2) var(--e3); text-align: right; border-bottom: 1px solid var(--linha); }
th:first-child, td:first-child { text-align: left; }
thead th { font-weight: 600; color: var(--tinta-suave); font-size: .9rem; }
.matriz td { min-width: 64px; text-align: center; }
.matriz td.diag { font-weight: 700; }
.rolagem { overflow-x: auto; }

/* reviews */
.filtros { display: flex; flex-wrap: wrap; gap: var(--e3); align-items: end; margin-bottom: var(--e4); }
.filtros label { display: grid; gap: var(--e1); font-size: .9rem; color: var(--tinta-suave); }
select, input[type=search] { font: inherit; color: var(--tinta); background: var(--papel); border: 1px solid var(--linha);
  border-radius: var(--r-pequeno); padding: var(--e2) var(--e3); min-height: 44px; }
input[type=search] { min-width: min(320px, 100%); }
.cats { display: flex; flex-wrap: wrap; gap: var(--e1); }
.cats button, .mais { font: inherit; color: var(--tinta); background: var(--papel); border: 1px solid var(--linha);
  border-radius: 999px; padding: var(--e2) var(--e4); min-height: 44px; cursor: pointer; }
.cats button[aria-pressed="true"] { background: var(--tinta); color: var(--papel); border-color: var(--tinta); }
.estado { color: var(--tinta-suave); margin-bottom: var(--e3); }
.lista { display: grid; gap: var(--e3); }
.review { background: var(--papel); border: 1px solid var(--linha); border-left: 6px solid var(--ind); border-radius: var(--r-pequeno);
  padding: var(--e4) var(--e5); }
.review.c-Tecnico { border-left-color: var(--tec); }
.review.c-Afetivo-visual { border-left-color: var(--afe); }
.review.c-Misto { border-image: linear-gradient(var(--tec) 50%, var(--afe) 50%) 0 0 0 1; border-left-width: 6px; }
.cabeca { display: flex; flex-wrap: wrap; gap: var(--e2) var(--e4); align-items: baseline; font-size: .9rem; color: var(--tinta-suave); }
.cabeca .cat { font-weight: 700; color: var(--tinta); }
.texto { font: 1.06rem/1.65 var(--serifa); margin: var(--e3) 0; max-width: 75ch; white-space: pre-wrap; overflow-wrap: anywhere; }
mark { color: inherit; padding: 0 .12em; border-radius: 2px; }
mark.t { background: linear-gradient(transparent 30%, var(--tec-marca) 30%); box-shadow: inset 0 -2px 0 var(--tec); }
mark.a { background: linear-gradient(transparent 30%, var(--afe-marca) 30%); box-shadow: inset 0 -2px 0 var(--afe); }
mark.m { background: linear-gradient(transparent 30%, var(--tec-marca) 30%, var(--tec-marca) 65%, var(--afe-marca) 65%);
  box-shadow: inset 0 -2px 0 var(--afe); }
mark.i { background: linear-gradient(transparent 30%, var(--linha) 30%); box-shadow: inset 0 -2px 0 var(--ind); }
mark.radical { box-shadow: none; text-decoration: underline dotted 2px; text-underline-offset: 4px; }
.reticencias { color: var(--tinta-suave); }
.ler { font: inherit; font-size: .9rem; color: var(--foco); background: none; border: 0; padding: var(--e2) 0; min-height: 44px; cursor: pointer; text-decoration: underline; }
.porque { font-size: .9rem; color: var(--tinta-suave); display: grid; gap: var(--e1); }
.porque b { color: var(--tinta); font-weight: 600; }
.mais { margin-top: var(--e4); }
footer { margin-top: var(--e7); color: var(--tinta-suave); font-size: .9rem; }

@media (max-width: 640px) {
  h1 { font-size: 1.6rem; }
  .achado { font-size: 1.25rem; }
  .jogo { grid-template-columns: 1fr; gap: var(--e2); }
  .review { padding: var(--e3) var(--e4); }
}
@media print {
  .filtros, .mais, .cats { display: none; }
  .review { break-inside: avoid; }
}
</style>
</head>
<body>
<main>
  <header>
    <h1 id="titulo"></h1>
    <p class="achado" id="achado"></p>
    <p class="contexto" id="resumo"></p>
  </header>

  <section aria-labelledby="t-geral">
    <h2 id="t-geral">Como os reviews se dividem</h2>
    <div class="barra grande" id="barra-geral" role="img"></div>
    <div id="zoom"></div>
    <div class="legenda" id="legenda"></div>
  </section>

  <section aria-labelledby="t-jogos">
    <h2 id="t-jogos">Por jogo</h2>
    <p class="sub" style="margin-bottom: var(--e3)">Escolha um jogo para ver só os reviews dele na lista abaixo.</p>
    <div class="jogos" id="jogos"></div>
  </section>

  <section aria-labelledby="t-ind">
    <h2 id="t-ind">Indicadores mais acionados</h2>
    <div class="duas" id="indicadores"></div>
  </section>

  <section aria-labelledby="t-aval">
    <h2 id="t-aval">Sistema comparado ao gabarito manual</h2>
    <div id="avaliacao"></div>
  </section>

  <section aria-labelledby="t-rev">
    <h2 id="t-rev">Reviews e o porquê de cada classificação</h2>
    <p class="sub" style="margin-bottom: var(--e4)">Os indicadores encontrados aparecem marcados no texto:
      <mark class="t">técnicos</mark> e <mark class="a">afetivo-visuais</mark>. O sublinhado pontilhado indica
      <mark class="t radical">casamento pelo radical</mark> (ex.: "lagar" casando com "lag"). Reviews longos mostram só o trecho em volta dos indicadores.</p>
    <div class="filtros">
      <label>Jogo <select id="f-jogo"><option value="">Todos os jogos</option></select></label>
      <label>Buscar no texto <input type="search" id="f-busca" placeholder="ex.: travando, rosto"></label>
    </div>
    <div class="cats" id="f-cats" role="group" aria-label="Filtrar por categoria"></div>
    <p class="estado" id="estado" aria-live="polite" style="margin-top: var(--e4)"></p>
    <div class="lista" id="lista"></div>
    <button class="mais" id="mais" type="button">Mostrar mais 30</button>
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
  var dataBr = function (iso) { return iso.split("-").reverse().join("/"); };
  var lista_e = function (itens) {   // ["a","b","c"] -> a, b e c (como nós DOM)
    var out = [];
    itens.forEach(function (it, i) { if (i) out.push(i === itens.length - 1 ? " e " : ", "); out.push(it); });
    return out;
  };
  document.getElementById("titulo").textContent = D.titulo;
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
      "Ampliação dos ", el("b", { classe: "num", texto: fmt.format(D.com_indicador) + " reviews com algum indicador" }),
      " (a parte colorida da barra de cima)."
    ]));
  }
  var leg = document.getElementById("legenda");
  D.categorias.forEach(function (c) {
    var n = D.geral[c];
    var detalhe = fmt.format(n) + " (" + pct(n, D.total) + " do total" +
      (c !== "Indefinido" && D.com_indicador ? ", " + pct(n, D.com_indicador) + " dos com indicador" : "") + ")";
    leg.appendChild(el("div", {}, [
      el("span", { classe: "cor f-" + c, "aria-hidden": "true" }),
      el("span", {}, [el("b", { texto: NOMES[c] }), " ", el("span", { classe: "num", texto: detalhe })]),
      el("span", { classe: "desc", texto: DESC[c] })
    ]));
  });

  // filtros
  var estado = { jogo: "", cat: "", busca: "", limite: 30 };
  var selJogo = document.getElementById("f-jogo");
  var jogosBox = document.getElementById("jogos");
  var botoesJogo = [];
  Object.keys(D.por_jogo).forEach(function (j) {
    var cont = D.por_jogo[j], tot = 0;
    D.categorias.forEach(function (c) { tot += cont[c]; });
    var trilha = el("div", { classe: "barra" });
    barra(cont, tot, trilha);
    var b = el("button", { classe: "jogo", type: "button", "aria-pressed": "false" }, [
      el("span", { classe: "nome" }, [j, el("small", { classe: "num", texto: fmt.format(tot) + " reviews" })]),
      trilha,
      el("span", { classe: "conta num", texto: "Técnico " + pct(cont["Tecnico"], tot) + ", afetivo-visual " + pct(cont["Afetivo-visual"], tot) + ", misto " + pct(cont["Misto"], tot) })
    ]);
    b.addEventListener("click", function () {
      estado.jogo = estado.jogo === j ? "" : j;
      selJogo.value = estado.jogo; estado.limite = 30; render();
      document.getElementById("t-rev").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    });
    botoesJogo.push([j, b]);
    jogosBox.appendChild(b);
    selJogo.appendChild(el("option", { value: j, texto: j }));
  });
  selJogo.addEventListener("change", function () { estado.jogo = selJogo.value; estado.limite = 30; render(); });
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
    var bloco = el("div", {}, [el("h3", { texto: g[1], style: "font-size:1rem;margin:0 0 var(--e3)" })]);
    if (!lista.length) {
      bloco.appendChild(el("p", { classe: "vazio", texto: "Nenhum indicador " + g[1].toLowerCase().replace(/s$/, "") + " foi encontrado nestes reviews." }));
    } else {
      var max = lista[0][1];
      var ul = el("ul", { classe: "ind-lista" });
      lista.forEach(function (par) {
        ul.appendChild(el("li", {}, [
          el("span", { texto: par[0] }),
          el("span", { classe: "trilho", "aria-hidden": "true" }, [el("span", { classe: "enchimento", style: "display:block;width:" + (100 * par[1] / max) + "%;background:" + g[2] })]),
          el("span", { classe: "num", texto: fmt.format(par[1]) })
        ]));
      });
      bloco.appendChild(ul);
    }
    indBox.appendChild(bloco);
  });

  // avaliação
  var av = D.avaliacao, avBox = document.getElementById("avaliacao");
  if (!av) {
    avBox.appendChild(el("div", { classe: "vazio" }, [
      el("p", { texto: "Ainda não há gabarito manual, então não dá para medir acertos e erros do sistema." }),
      el("p", { style: "margin-top:var(--e2)" }, ["Para gerar: rotule a amostra de ", el("code", { texto: "python -m src.amostragem" }),
        " e rode ", el("code", { texto: "python -m src.avaliacao --gabarito data/gabarito_rotulado.csv" }), ". Este painel é refeito com a matriz de confusão."])
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
      linha.forEach(function (v, j) {
        var a = (max && v) ? 0.1 + 0.5 * v / max : 0;
        tr.appendChild(el("td", { classe: i === j ? "diag" : "", texto: fmt.format(v),
          style: "background:color-mix(in srgb, " + (i === j ? "var(--tec)" : "var(--afe)") + " " + Math.round(a * 100) + "%, transparent)" }));
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
  }

  // reviews
  var ordenados = D.reviews.slice().sort(function (x, y) { return (y.et + y.ea) - (x.et + x.ea); });
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
    var artigo = el("article", { classe: "review c-" + r.cat }, [
      el("div", { classe: "cabeca" }, [el("span", { classe: "cat", texto: NOMES[r.cat] }), el("span", { texto: r.jogo }),
        r.data ? el("span", { classe: "num", texto: r.data.split("-").reverse().join("/") }) : null, rec ? el("span", { texto: rec }) : null]),
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
    var base = ordenados.filter(function (r) {
      return (!estado.jogo || r.jogo === estado.jogo) && (!estado.busca || r.texto.toLowerCase().indexOf(estado.busca) >= 0);
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
      ? "Mostrando " + fmt.format(Math.min(estado.limite, filtrados.length)) + " de " + fmt.format(filtrados.length) + " reviews, os com mais indicadores primeiro."
      : "Nenhum review com esses filtros. Tente outra categoria ou limpe a busca.";
    mais.hidden = filtrados.length <= estado.limite;
  }
  render();

  document.getElementById("rodape").textContent =
    "Painel gerado pelo projeto tcc-triagem-reviews (src/painel.py). Textos de reviews longos foram cortados em " + fmt.format(""" + str(LIMITE_TEXTO) + r""") + " caracteres.";
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

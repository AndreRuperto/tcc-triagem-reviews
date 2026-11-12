"""
Compara a classificacao automatica com o gabarito manual (secao 4.8 do
TCC): matriz de confusao, precisao, revocacao, F1 por categoria,
acuracia, e concordancia entre anotadores (kappa de Cohen) quando
houver um segundo rotulador.

Uso, na raiz do projeto:

    python -m src.avaliacao --gabarito data/gabarito_rotulado.csv
    python -m src.avaliacao --gabarito data/gabarito_a.csv --segundo data/gabarito_b.csv

Saidas em reports/avaliacao/:
    metricas.csv             precisao, revocacao, F1 e suporte por categoria
    matriz_confusao.csv/png  linhas = gabarito manual, colunas = sistema
    divergencias.csv         reviews em que sistema e gabarito discordam,
                             com os indicadores acionados (analise de erros)
    comparacao.csv           gabarito e sistema de cada review rotulado
                             (usado pelo painel para filtrar pela matriz)
    resumo.txt               acuracia, F1 macro e kappa
"""

import argparse
import unicodedata
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import (
    accuracy_score, cohen_kappa_score, confusion_matrix, precision_recall_fscore_support,
)

CATEGORIAS = ["Tecnico", "Afetivo-visual", "Misto", "Indefinido"]
_APELIDOS = {
    "tecnico": "Tecnico", "t": "Tecnico",
    "afetivo-visual": "Afetivo-visual", "afetivo visual": "Afetivo-visual", "afetivo": "Afetivo-visual", "a": "Afetivo-visual",
    "misto": "Misto", "m": "Misto",
    "indefinido": "Indefinido", "i": "Indefinido",
}


def padronizar_categoria(valor) -> str:
    """Aceita 'Técnico', 'tecnico', 'T', 'afetivo visual' etc. Vazio vira ''."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor).strip().lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    if not texto:
        return ""
    if texto not in _APELIDOS:
        raise ValueError(f"Categoria manual desconhecida: {valor!r}. Use uma de {CATEGORIAS}.")
    return _APELIDOS[texto]


def ler_gabarito(caminho: Path) -> pd.DataFrame:
    gabarito = pd.read_csv(caminho, encoding="utf-8-sig", dtype={"id_review": str})
    if "categoria_manual" not in gabarito.columns:
        raise ValueError(f"{caminho} nao tem a coluna 'categoria_manual'.")
    gabarito["categoria_manual"] = gabarito["categoria_manual"].map(padronizar_categoria)
    rotulados = gabarito[gabarito["categoria_manual"] != ""]
    if rotulados.empty:
        raise ValueError(f"{caminho}: nenhuma linha com 'categoria_manual' preenchida ainda.")
    return rotulados[["id_review", "categoria_manual"] + (["observacao"] if "observacao" in gabarito else [])]


def juntar(classificados: pd.DataFrame, gabarito: pd.DataFrame) -> pd.DataFrame:
    base = classificados.copy()
    base["id_review"] = base["id_review"].astype(str)
    juntos = gabarito.merge(base, on="id_review", how="left", validate="one_to_one")
    sem_par = juntos["categoria"].isna().sum()
    if sem_par:
        raise ValueError(f"{sem_par} id(s) do gabarito nao existem nos reviews classificados.")
    return juntos


def calcular_metricas(manual, automatico) -> dict:
    precisao, revocacao, f1, suporte = precision_recall_fscore_support(
        manual, automatico, labels=CATEGORIAS, zero_division=0
    )
    por_categoria = pd.DataFrame({
        "categoria": CATEGORIAS,
        "precisao": precisao.round(4),
        "revocacao": revocacao.round(4),
        "f1": f1.round(4),
        "suporte": suporte,
    })
    presentes = por_categoria[por_categoria["suporte"] > 0]
    return {
        "por_categoria": por_categoria,
        "matriz": pd.DataFrame(
            confusion_matrix(manual, automatico, labels=CATEGORIAS),
            index=[f"manual:{c}" for c in CATEGORIAS],
            columns=[f"sistema:{c}" for c in CATEGORIAS],
        ),
        "acuracia": round(accuracy_score(manual, automatico), 4),
        "f1_macro": round(presentes["f1"].mean(), 4) if len(presentes) else 0.0,
        "n": len(manual),
    }


def desenhar_matriz(matriz: pd.DataFrame, destino: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(matriz.values, cmap="Blues")
    ax.set_xticks(range(len(CATEGORIAS)), CATEGORIAS, rotation=20)
    ax.set_yticks(range(len(CATEGORIAS)), CATEGORIAS)
    ax.set_xlabel("Classificacao do sistema")
    ax.set_ylabel("Gabarito manual")
    ax.set_title("Matriz de confusao")
    limite = matriz.values.max() / 2 if matriz.values.max() else 0
    for i in range(len(CATEGORIAS)):
        for j in range(len(CATEGORIAS)):
            v = matriz.values[i, j]
            ax.text(j, i, str(v), ha="center", va="center", color="white" if v > limite else "black")
    fig.tight_layout()
    fig.savefig(destino, dpi=300)
    plt.close(fig)


def avaliar(classificados: pd.DataFrame, gabarito: pd.DataFrame, segundo: pd.DataFrame = None,
            destino: Path = None) -> dict:
    juntos = juntar(classificados, gabarito)
    resultado = calcular_metricas(juntos["categoria_manual"], juntos["categoria"])

    if segundo is not None:
        pares = gabarito.merge(segundo, on="id_review", suffixes=("_a", "_b"))
        resultado["kappa"] = round(cohen_kappa_score(pares["categoria_manual_a"], pares["categoria_manual_b"]), 4)
        resultado["n_kappa"] = len(pares)

    colunas_erro = [c for c in ["id_review", "jogo", "texto_original", "categoria_manual", "categoria",
                                "indicadores_tecnicos", "indicadores_afetivos", "regra_acionada", "observacao"]
                    if c in juntos.columns]
    resultado["divergencias"] = juntos[juntos["categoria_manual"] != juntos["categoria"]][colunas_erro]

    if destino is not None:
        destino.mkdir(parents=True, exist_ok=True)
        resultado["por_categoria"].to_csv(destino / "metricas.csv", index=False, encoding="utf-8-sig")
        resultado["matriz"].to_csv(destino / "matriz_confusao.csv", encoding="utf-8-sig")
        resultado["divergencias"].to_csv(destino / "divergencias.csv", index=False, encoding="utf-8-sig")
        # par gabarito x sistema de cada review rotulado: deixa a matriz do painel clicavel
        juntos[["id_review", "categoria_manual", "categoria"]].to_csv(
            destino / "comparacao.csv", index=False, encoding="utf-8-sig")
        desenhar_matriz(resultado["matriz"], destino / "matriz_confusao.png")
        (destino / "resumo.txt").write_text(texto_resumo(resultado), encoding="utf-8")

    return resultado


def texto_resumo(r: dict) -> str:
    linhas = [
        f"Reviews avaliados: {r['n']}",
        f"Acuracia: {r['acuracia']:.4f}",
        f"F1 macro (categorias presentes no gabarito): {r['f1_macro']:.4f}",
    ]
    if "kappa" in r:
        linhas.append(f"Kappa de Cohen entre anotadores: {r['kappa']:.4f} (n={r['n_kappa']})")
    linhas += ["", r["por_categoria"].to_string(index=False), "", r["matriz"].to_string()]
    return "\n".join(linhas) + "\n"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Avalia o sistema contra o gabarito manual.")
    parser.add_argument("--classificados", type=Path, default=Path("reports/reviews_classificados.csv"))
    parser.add_argument("--gabarito", type=Path, required=True)
    parser.add_argument("--segundo", type=Path, default=None, help="Gabarito de um segundo anotador (kappa)")
    parser.add_argument("--saida", type=Path, default=Path("reports/avaliacao"))
    args = parser.parse_args(argv)

    classificados = pd.read_csv(args.classificados, encoding="utf-8-sig", dtype={"id_review": str})
    segundo = ler_gabarito(args.segundo) if args.segundo else None
    resultado = avaliar(classificados, ler_gabarito(args.gabarito), segundo, args.saida)
    print(texto_resumo(resultado))
    print(f"Arquivos em {args.saida}")
    # se a avaliacao ficou ao lado dos classificados (padrao reports/avaliacao), refaz o painel com a matriz
    if args.saida.resolve().parent == args.classificados.resolve().parent:
        from src.painel import gerar_painel
        print(f"Painel atualizado: {gerar_painel(args.classificados.parent)}")


if __name__ == "__main__":
    main()

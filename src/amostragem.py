"""
Gera a planilha de rotulagem manual (gabarito) a partir dos reviews
ja classificados pelo sistema.

Uso, na raiz do projeto:

    python -m src.amostragem --entrada reports/reviews_classificados.csv --tamanho 200

A amostra e estratificada pela categoria automatica, para que as
classes raras (Misto, Afetivo-visual) tenham exemplos suficientes na
avaliacao, e e sorteada com semente fixa (reprodutivel).

IMPORTANTE (cegamento): a planilha gerada NAO mostra a categoria, os
escores nem os indicadores do sistema. Quem rotula ve apenas o texto
original, para nao ser influenciado pela resposta automatica. A ligacao
com o resultado automatico e feita depois, pelo id_review, em
src/avaliacao.py. Ver docs/protocolo_rotulagem.md.
"""

import argparse
from pathlib import Path

import pandas as pd

SEMENTE = 2026
COLUNAS_ROTULAGEM = ["id_review", "jogo", "texto_original", "categoria_manual", "observacao"]


def sortear_amostra(classificados: pd.DataFrame, tamanho: int, minimo_por_categoria: int = 15,
                    semente: int = SEMENTE) -> pd.DataFrame:
    """
    Sorteia `tamanho` reviews. Cada categoria automatica recebe pelo
    menos `minimo_por_categoria` (ou todas, se tiver menos); o restante
    e distribuido proporcionalmente ao tamanho de cada categoria.
    """
    if tamanho >= len(classificados):
        return classificados.sample(frac=1, random_state=semente).reset_index(drop=True)

    grupos = {cat: df for cat, df in classificados.groupby("categoria")}
    cotas = {cat: min(len(df), minimo_por_categoria) for cat, df in grupos.items()}
    # se os minimos nao cabem no tamanho pedido, corta das maiores cotas
    # (as categorias raras ficam com o que tinham)
    while sum(cotas.values()) > tamanho:
        maior = max(cotas, key=lambda c: (cotas[c], c))
        cotas[maior] -= 1
    restante = tamanho - sum(cotas.values())

    if restante > 0:
        sobras = {cat: len(df) - cotas[cat] for cat, df in grupos.items()}
        total_sobras = sum(sobras.values())
        extras = {cat: int(restante * s / total_sobras) for cat, s in sobras.items()} if total_sobras else {}
        # distribui o arredondamento para as maiores sobras
        faltam = restante - sum(extras.values())
        for cat in sorted(sobras, key=lambda c: sobras[c] - extras.get(c, 0), reverse=True):
            if faltam <= 0:
                break
            if extras[cat] < sobras[cat]:
                extras[cat] += 1
                faltam -= 1
        for cat, extra in extras.items():
            cotas[cat] += min(extra, sobras[cat])

    partes = [grupos[cat].sample(n=cota, random_state=semente) for cat, cota in cotas.items() if cota]
    amostra = pd.concat(partes)
    # embaralha para quem rotula nao ver os reviews agrupados por categoria
    return amostra.sample(frac=1, random_state=semente).reset_index(drop=True)


def planilha_cega(amostra: pd.DataFrame) -> pd.DataFrame:
    planilha = amostra[["id_review", "jogo", "texto_original"]].copy()
    planilha["categoria_manual"] = ""
    planilha["observacao"] = ""
    return planilha[COLUNAS_ROTULAGEM]


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Gera a planilha cega de rotulagem manual.")
    parser.add_argument("--entrada", type=Path, default=Path("reports/reviews_classificados.csv"))
    parser.add_argument("--tamanho", type=int, default=200)
    parser.add_argument("--minimo", type=int, default=15, help="Minimo por categoria automatica")
    parser.add_argument("--saida", type=Path, default=Path("data/gabarito_para_rotular.csv"))
    args = parser.parse_args(argv)

    if args.saida.exists():
        raise SystemExit(f"{args.saida} ja existe: renomeie ou apague antes, para nao perder rotulos ja feitos.")

    classificados = pd.read_csv(args.entrada, encoding="utf-8-sig", dtype={"id_review": str})
    amostra = sortear_amostra(classificados, args.tamanho, args.minimo)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    planilha_cega(amostra).to_csv(args.saida, index=False, encoding="utf-8-sig")

    print(f"{len(amostra)} reviews em {args.saida}")
    print(amostra["categoria"].value_counts().to_string())


if __name__ == "__main__":
    main()

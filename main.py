"""
Ponto de entrada do sistema especialista de triagem de reviews.

Fluxo (Capitulo 3.7 do TCC):
Entrada dos reviews -> preparacao dos dados -> consulta a base de
conhecimento -> calculo dos escores -> aplicacao das regras ->
classificacao -> relatorios.
"""

import argparse
import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from src.classificador import classify_review
from src.painel import gerar_painel

def load_knowledge_base(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    required_groups = {"tecnico", "afetivo_visual"}
    if not required_groups.issubset(data.keys()):
        raise ValueError("A base deve possuir os grupos 'tecnico' e 'afetivo_visual'.")
    if "versao" not in data:
        raise ValueError("A base deve informar sua 'versao' para rastreabilidade dos resultados.")

    return data


def prepare_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"id_review", "jogo", "texto_original"}
    missing = required_columns.difference(dataframe.columns)
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes: {', '.join(sorted(missing))}")

    prepared = dataframe.drop_duplicates(subset=["id_review"], keep="first").copy()
    prepared["texto_original"] = prepared["texto_original"].fillna("").astype(str)
    prepared = prepared[prepared["texto_original"].str.strip() != ""]

    return prepared.reset_index(drop=True)


def classify_dataframe(dataframe: pd.DataFrame, knowledge_base: dict) -> pd.DataFrame:
    prepared = prepare_dataframe(dataframe)

    results = prepared["texto_original"].apply(
        lambda text: classify_review(text, knowledge_base)
    )
    results_df = pd.DataFrame(results.tolist())
    results_df["versao_base"] = knowledge_base["versao"]

    return pd.concat([prepared, results_df], axis=1)


def generate_category_chart(dataframe: pd.DataFrame, output_path: Path) -> None:
    counts = dataframe["categoria"].value_counts()

    plt.figure(figsize=(9, 5))
    counts.plot(kind="bar")
    plt.title("Distribuicao das categorias")
    plt.xlabel("Categoria")
    plt.ylabel("Quantidade de reviews")
    plt.xticks(rotation=0)
    plt.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()


def export_reports(dataframe: pd.DataFrame, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)

    dataframe.to_csv(
        output_directory / "reviews_classificados.csv", index=False, encoding="utf-8-sig"
    )

    technical = dataframe[dataframe["categoria"].isin(["Tecnico", "Misto"])]
    technical.to_csv(
        output_directory / "reviews_tecnicos.csv", index=False, encoding="utf-8-sig"
    )

    summary = (
        dataframe["categoria"].value_counts().rename_axis("categoria").reset_index(name="quantidade")
    )
    summary["percentual"] = (summary["quantidade"] / len(dataframe) * 100).round(2)
    summary.to_csv(output_directory / "resumo_categorias.csv", index=False, encoding="utf-8-sig")

    generate_category_chart(dataframe, output_directory / "distribuicao_categorias.png")
    gerar_painel(output_directory)


def main(argv=None) -> None:
    project_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Classifica reviews com o sistema especialista.")
    parser.add_argument("--entrada", type=Path, nargs="+", default=[project_dir / "data" / "reviews_entrada.csv"],
                        help="Um ou mais CSVs de entrada, juntados antes da classificacao (padrao: data/reviews_entrada.csv)")
    parser.add_argument("--saida", type=Path, default=project_dir / "reports",
                        help="Pasta dos relatorios (padrao: reports/)")
    args = parser.parse_args(argv)

    knowledge_base_path = project_dir / "config" / "base_conhecimento.json"
    output_dir = args.saida

    for input_path in args.entrada:
        if not input_path.exists():
            raise FileNotFoundError(f"Arquivo de entrada nao encontrado: {input_path}")

    knowledge_base = load_knowledge_base(knowledge_base_path)
    input_df = pd.concat(
        [pd.read_csv(caminho, encoding="utf-8-sig", dtype={"id_review": str}) for caminho in args.entrada],
        ignore_index=True,
    )

    classified_df = classify_dataframe(input_df, knowledge_base)
    export_reports(classified_df, output_dir)

    print("Classificacao concluida.")
    print(classified_df["categoria"].value_counts())


if __name__ == "__main__":
    main()

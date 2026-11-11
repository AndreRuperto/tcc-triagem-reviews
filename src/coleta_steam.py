"""
Coleta de reviews reais da Steam (endpoint publico appreviews).

Uso, na raiz do projeto:

    python -m src.coleta_steam --appid 1234 --jogo "Nome do Jogo" --max 500
    python -m src.coleta_steam --lote config/jogos.json --max 100

Nao precisa de chave de API: o endpoint de reviews da Steam e publico.

Gera data/steam_<appid>.csv no formato de entrada do classificador
(id_review, jogo, nota, recomendado, texto_original) mais metadados
uteis para a analise (data, votos de utilidade, horas jogadas).

Privacidade/etica: o identificador do autor (steamid) NAO e gravado.
So entram o texto e dados agregados da review, suficientes para a
classificacao e para a analise temporal de review bombing.

Endpoint documentado em:
https://partner.steamgames.com/doc/store/getreviews
"""

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

URL = "https://store.steampowered.com/appreviews/{appid}"
USER_AGENT = "tcc-triagem-reviews/1.0 (pesquisa academica)"
POR_PAGINA = 100  # maximo aceito pela API
COLUNAS = [
    "id_review", "jogo", "nota", "recomendado", "texto_original",
    "data_criacao", "votos_util", "votos_engracado", "horas_jogadas",
    "compra_steam", "recebido_gratis", "idioma",
]


def montar_parametros(cursor: str, idioma: str, filtro: str) -> dict:
    return {
        "json": 1,
        "language": idioma,
        "filter": filtro,
        "review_type": "all",
        "purchase_type": "all",
        "num_per_page": POR_PAGINA,
        "cursor": cursor,
    }


def converter_review(bruta: dict, jogo: str) -> dict:
    """Converte uma review da API para uma linha do CSV de entrada."""
    autor = bruta.get("author") or {}
    criada = bruta.get("timestamp_created")
    return {
        "id_review": str(bruta["recommendationid"]),
        "jogo": jogo,
        "nota": "",  # a Steam nao tem nota numerica, so recomendado sim/nao
        "recomendado": "sim" if bruta.get("voted_up") else "nao",
        "texto_original": bruta.get("review", ""),
        "data_criacao": (
            datetime.fromtimestamp(criada, tz=timezone.utc).strftime("%Y-%m-%d")
            if criada else ""
        ),
        "votos_util": bruta.get("votes_up", 0),
        "votos_engracado": bruta.get("votes_funny", 0),
        "horas_jogadas": round((autor.get("playtime_forever") or 0) / 60, 1),
        "compra_steam": "sim" if bruta.get("steam_purchase") else "nao",
        "recebido_gratis": "sim" if bruta.get("received_for_free") else "nao",
        "idioma": bruta.get("language", ""),
    }


def coletar(appid: int, jogo: str, maximo: int, idioma: str = "brazilian",
            filtro: str = "recent", pausa: float = 1.5, sessao=None, info: dict = None) -> list:
    """
    Percorre as paginas da API pelo cursor ate juntar `maximo` reviews,
    a API parar de devolver novas ou repetir o cursor. Respeita uma
    pausa entre requisicoes para nao sobrecarregar o servico.

    Se `info` for passado, recebe o total de reviews disponiveis no
    idioma ("total_disponivel"), informado pela Steam na primeira pagina.
    """
    sessao = sessao or requests.Session()
    sessao.headers.setdefault("User-Agent", USER_AGENT)
    linhas, vistos, cursor = [], set(), "*"

    while len(linhas) < maximo:
        resposta = sessao.get(
            URL.format(appid=appid),
            params=montar_parametros(cursor, idioma, filtro),
            timeout=30,
        )
        resposta.raise_for_status()
        try:
            dados = resposta.json()
        except ValueError:
            raise RuntimeError(
                f"A Steam nao devolveu JSON para o app {appid} (provavelmente uma pagina HTML). "
                "Confira o appid na URL da loja; se estiver certo, tente de novo mais tarde."
            ) from None
        if dados.get("success") != 1:
            raise RuntimeError(f"A Steam recusou a consulta do app {appid}: {dados}")
        if info is not None and cursor == "*":
            info["total_disponivel"] = (dados.get("query_summary") or {}).get("total_reviews")

        novas = 0
        for bruta in dados.get("reviews", []):
            rid = str(bruta.get("recommendationid"))
            if rid in vistos:
                continue
            vistos.add(rid)
            linhas.append(converter_review(bruta, jogo))
            novas += 1
            if len(linhas) >= maximo:
                break

        proximo = dados.get("cursor")
        if not novas or not proximo or proximo == cursor:
            break
        cursor = proximo
        time.sleep(pausa)

    return linhas


def salvar(linhas: list, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)


def coletar_lote(jogos: list, maximo: int, idioma: str, filtro: str, pasta: Path,
                 pausa: float = 1.5, sessao=None) -> list:
    """
    Coleta varios jogos em sequencia. Um jogo que falhar nao interrompe
    os outros: o erro fica registrado no resumo devolvido.
    """
    resumo = []
    for jogo in jogos:
        appid, nome = int(jogo["appid"]), jogo["jogo"]
        destino = pasta / f"steam_{appid}.csv"
        info = {}
        try:
            linhas = coletar(appid, nome, maximo, idioma, filtro, pausa, sessao, info)
            salvar(linhas, destino)
            resumo.append({"appid": appid, "jogo": nome, "coletadas": len(linhas),
                           "disponiveis": info.get("total_disponivel"), "arquivo": str(destino), "erro": ""})
        except Exception as erro:  # registra e segue para o proximo jogo
            resumo.append({"appid": appid, "jogo": nome, "coletadas": 0,
                           "disponiveis": None, "arquivo": "", "erro": str(erro)})
    return resumo


def imprimir_resumo(resumo: list) -> None:
    print(f"{'appid':>9}  {'coletadas':>9}  {'disponiveis':>11}  jogo")
    for r in resumo:
        disp = "?" if r["disponiveis"] is None else r["disponiveis"]
        print(f"{r['appid']:>9}  {r['coletadas']:>9}  {disp:>11}  {r['jogo']}")
        if r["erro"]:
            print(f"{'':>9}  ERRO: {r['erro']}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Coleta reviews de um jogo (ou de uma lista de jogos) na Steam.")
    parser.add_argument("--lote", type=Path, default=None,
                        help="JSON com a lista de jogos (ex: config/jogos.json); dispensa --appid e --jogo")
    parser.add_argument("--appid", type=int, help="ID do jogo na Steam (numero na URL da loja)")
    parser.add_argument("--jogo", help="Nome do jogo, gravado na coluna 'jogo'")
    parser.add_argument("--max", type=int, default=500, help="Quantidade maxima de reviews (padrao 500)")
    parser.add_argument("--idioma", default="brazilian", help="Idioma da Steam (padrao: brazilian = pt-BR)")
    parser.add_argument("--filtro", default="recent", choices=["recent", "updated", "all"],
                        help="Ordenacao da API (padrao: recent)")
    parser.add_argument("--saida", type=Path, default=None, help="CSV de saida (com --lote: pasta de saida; padrao: data/)")
    args = parser.parse_args(argv)

    if args.lote:
        with args.lote.open(encoding="utf-8") as arquivo:
            jogos = json.load(arquivo)["jogos"]
        pasta = args.saida or Path("data")
        resumo = coletar_lote(jogos, args.max, args.idioma, args.filtro, pasta)
        imprimir_resumo(resumo)
        if any(r["erro"] for r in resumo):
            raise SystemExit(1)
        return

    if args.appid is None or not args.jogo:
        parser.error("informe --lote, ou --appid e --jogo")
    destino = args.saida or Path("data") / f"steam_{args.appid}.csv"
    linhas = coletar(args.appid, args.jogo, args.max, args.idioma, args.filtro)
    salvar(linhas, destino)
    print(f"{len(linhas)} reviews de '{args.jogo}' salvas em {destino}")


if __name__ == "__main__":
    main()

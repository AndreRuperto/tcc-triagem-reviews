"""
Coleta de reviews reais da Steam (Web API IUserReviewsService/GetAppReviews).

Uso, na raiz do projeto:

    python -m src.coleta_steam --appid 1234 --jogo "Nome do Jogo" --max 500
    python -m src.coleta_steam --lote config/jogos.json --max 100

Nao precisa de chave de API (a chave so aumenta o limite de requisicoes).

Review bombing: por padrao a Steam ESCONDE as reviews que ela marcou
como atividade fora do assunto ("off-topic review activity"), que e
justamente como ela classifica ondas de review bombing. Para este
trabalho elas precisam entrar, entao o coletor pede
filter_offtopic_activity=false. Use --excluir-fora-do-assunto para
reproduzir a visao filtrada da loja.

Gera data/steam_<appid>.csv no formato de entrada do classificador
(id_review, jogo, nota, recomendado, texto_original) mais metadados
uteis para a analise (data, votos de utilidade, horas jogadas).

Privacidade/etica: o identificador do autor (steamid) NAO e gravado.
So entram o texto e dados agregados da review, suficientes para a
classificacao e para a analise temporal de review bombing.

Endpoint documentado em:
https://partner.steamgames.com/doc/webapi/IUserReviewsService
(substitui store.steampowered.com/appreviews/<appid>?json=1, que a
Valve desligou em outubro de 2026 e hoje redireciona para a loja).
"""

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
USER_AGENT = "tcc-triagem-reviews/1.0 (pesquisa academica)"
POR_PAGINA = 100  # maximo aceito pela API
# A API so aceita numeros nos enums: um texto como "recent" e ignorado em
# silencio e a resposta volta na ordem padrao (Helpful, ultimos 30 dias).
ORDENACAO = {"helpful": 0, "recent": 1, "updated": 2}
TIPO_REVIEW_TODAS = 0     # positivas e negativas
TIPO_COMPRA_TODAS = 1     # compras na Steam e fora dela (chaves etc.)
COLUNAS = [
    "id_review", "jogo", "nota", "recomendado", "texto_original",
    "data_criacao", "votos_util", "votos_engracado", "horas_jogadas",
    "horas_na_review", "compra_steam", "recebido_gratis", "idioma",
]


def para_timestamp(data: str, fim_do_dia: bool = False) -> int:
    """'2025-01-30' -> timestamp Unix UTC (inicio ou fim do dia)."""
    dia = datetime.strptime(data, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dia.timestamp()) + (86399 if fim_do_dia else 0)


def montar_parametros(cursor: str, idioma: str, filtro: str, appid: int,
                      incluir_fora_do_assunto: bool = True, periodo: tuple = None) -> dict:
    """Parametros da GetAppReviews: tudo vai dentro de input_json."""
    if filtro not in ORDENACAO:
        raise ValueError(f"Filtro desconhecido: {filtro!r}. Use um de {sorted(ORDENACAO)}.")
    entrada = {
        "appid": appid,
        "filter": ORDENACAO[filtro],
        "languages": [idioma],
        "review_type": TIPO_REVIEW_TODAS,
        "purchase_type": TIPO_COMPRA_TODAS,
        "num_per_page": POR_PAGINA,
        "cursor": cursor,
        "filter_offtopic_activity": not incluir_fora_do_assunto,
    }
    if filtro == "helpful":
        entrada["day_range"] = 0  # sem limite de datas (o padrao e 30 dias)
    if periodo:
        # a API ignora um lado do periodo se o outro nao vier junto
        entrada["date_range_start"] = para_timestamp(periodo[0])
        entrada["date_range_end"] = para_timestamp(periodo[1], fim_do_dia=True)
    return {"input_json": json.dumps(entrada)}


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
        # horas no momento da review: pouco tempo de jogo e um sinal comum de review bombing
        "horas_na_review": round((autor.get("playtime_at_review") or 0) / 60, 1),
        "compra_steam": "sim" if bruta.get("steam_purchase") else "nao",
        "recebido_gratis": "sim" if bruta.get("received_for_free") else "nao",
        "idioma": bruta.get("language", ""),
    }


def coletar(appid: int, jogo: str, maximo: int, idioma: str = "brazilian",
            filtro: str = "recent", pausa: float = 1.5, sessao=None, info: dict = None,
            incluir_fora_do_assunto: bool = True, periodo: tuple = None) -> list:
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
            URL,
            params=montar_parametros(cursor, idioma, filtro, appid, incluir_fora_do_assunto, periodo),
            timeout=30,
        )
        if resposta.status_code == 429:
            raise RuntimeError("A Steam limitou as requisicoes (HTTP 429). Espere alguns minutos e rode de novo.")
        resposta.raise_for_status()
        try:
            corpo = resposta.json()
        except ValueError:
            raise RuntimeError(
                f"A Steam nao devolveu JSON para o app {appid} (provavelmente uma pagina HTML). "
                "Confira o appid na URL da loja; se estiver certo, tente de novo mais tarde."
            ) from None
        # a GetAppReviews embrulha tudo em "response" e nao tem campo "success"
        dados = corpo.get("response") if isinstance(corpo, dict) else None
        if not isinstance(dados, dict):
            raise RuntimeError(f"Resposta inesperada da Steam para o app {appid}: {str(corpo)[:200]}")
        if info is not None and cursor == "*":
            resumo = dados.get("query_summary") or {}
            info["total_disponivel"] = resumo.get("total_reviews", dados.get("total_matching"))

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
                 pausa: float = 1.5, sessao=None, incluir_fora_do_assunto: bool = True) -> list:
    """
    Coleta varios jogos em sequencia. Cada jogo pode ter "periodo":
    ["AAAA-MM-DD", "AAAA-MM-DD"] no JSON (ex: as semanas do lancamento).
    Um jogo que falhar nao interrompe os outros: o erro fica no resumo.
    """
    resumo = []
    for jogo in jogos:
        appid, nome = int(jogo["appid"]), jogo["jogo"]
        destino = pasta / f"steam_{appid}.csv"
        info = {}
        try:
            periodo = tuple(jogo["periodo"]) if jogo.get("periodo") else None
            linhas = coletar(appid, nome, maximo, idioma, filtro, pausa, sessao, info,
                             incluir_fora_do_assunto, periodo)
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
    parser.add_argument("--filtro", default="recent", choices=sorted(ORDENACAO),
                        help="Ordenacao: recent (mais novas), updated, helpful (mais uteis, sem limite de data). Padrao: recent")
    parser.add_argument("--excluir-fora-do-assunto", action="store_true",
                        help="Esconde as reviews que a Steam marcou como fora do assunto (review bombing), como a loja faz")
    parser.add_argument("--periodo", nargs=2, metavar=("DE", "ATE"), default=None,
                        help="So reviews criadas entre DE e ATE (AAAA-MM-DD), ex: semanas do lancamento")
    parser.add_argument("--saida", type=Path, default=None, help="CSV de saida (com --lote: pasta de saida; padrao: data/)")
    args = parser.parse_args(argv)

    if args.lote:
        with args.lote.open(encoding="utf-8") as arquivo:
            jogos = json.load(arquivo)["jogos"]
        pasta = args.saida or Path("data")
        resumo = coletar_lote(jogos, args.max, args.idioma, args.filtro, pasta,
                              incluir_fora_do_assunto=not args.excluir_fora_do_assunto)
        imprimir_resumo(resumo)
        if any(r["erro"] for r in resumo):
            raise SystemExit(1)
        return

    if args.appid is None or not args.jogo:
        parser.error("informe --lote, ou --appid e --jogo")
    destino = args.saida or Path("data") / f"steam_{args.appid}.csv"
    linhas = coletar(args.appid, args.jogo, args.max, args.idioma, args.filtro,
                     incluir_fora_do_assunto=not args.excluir_fora_do_assunto,
                     periodo=tuple(args.periodo) if args.periodo else None)
    salvar(linhas, destino)
    print(f"{len(linhas)} reviews de '{args.jogo}' salvas em {destino}")


if __name__ == "__main__":
    main()

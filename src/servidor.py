"""
Serve os paineis de reports/ numa porta local.

    python -m src.servidor                 # http://localhost:8090
    python -m src.servidor --porta 9000

Pelo Docker (ver docker-compose.yml):

    docker compose up -d painel

Rotas: a pagina inicial (/) lista os paineis; cada reports/<pasta>/painel.html
fica em /<pasta> (ex.: /steam) e o reports/painel.html de exemplo em /exemplo.
Os enderecos antigos (/steam/painel.html, /painel.html) redirecionam (301)
para a rota limpa; pastas nao sao listadas. As
respostas vao com Cache-Control: no-store, para o navegador nunca
mostrar um painel antigo depois de uma nova classificacao.

No Railway: a porta vem da variavel PORT e o start command passa
--endereco 0.0.0.0 (o painel fica publico no dominio do servico).

Por padrao escuta so em 127.0.0.1 (nada fica exposto na rede). Dentro
do container ele escuta em 0.0.0.0, e quem limita a 127.0.0.1 e o
mapeamento de porta do docker-compose.
"""

import argparse
import html
import posixpath
import json
import os
import re
from functools import partial
from urllib.parse import unquote
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from src.estilo import FAVICON, LOGO_SIMBOLO, TOKENS_CLARO, TOKENS_ESCURO


def listar_paineis(raiz: Path) -> list:
    return sorted(p.relative_to(raiz).as_posix() for p in raiz.rglob("painel.html"))


ROTA_RAIZ = "/exemplo"   # o painel solto em reports/ (os 7 reviews de exemplo)


def rota_do_painel(relativo: str) -> str:
    """'steam/painel.html' -> '/steam'; 'painel.html' (raiz) -> '/exemplo'."""
    pasta = relativo.rsplit("/", 1)[0] if "/" in relativo else ""
    return "/" + pasta if pasta else ROTA_RAIZ


def rotas(raiz: Path) -> dict:
    """Rota limpa -> arquivo do painel. Uma pasta chamada 'exemplo' ganha da raiz."""
    mapa = {}
    for rel in listar_paineis(raiz):
        rota = rota_do_painel(rel)
        if rota not in mapa or "/" in rel:
            mapa[rota] = rel
    return mapa


def resumo_do_painel(arquivo: Path) -> dict:
    """Le os dados embutidos num painel.html (o JSON entre as tags de dados)."""
    try:
        texto = arquivo.read_text(encoding="utf-8")
        achado = re.search(r'<script type="application/json" id="dados">(.*?)</script>', texto, re.S)
        dados = json.loads(achado.group(1).replace("<\\/", "</")) if achado else {}
    except (OSError, ValueError):
        dados = {}
    return {
        "total": dados.get("total"),
        "com_indicador": dados.get("com_indicador"),
        "jogos": len(dados.get("por_jogo") or {}),
        "gerado": dados.get("gerado", ""),
        "versao": dados.get("versao_base", ""),
        "periodo": dados.get("periodo"),
    }


def _data_br(iso: str) -> str:
    return "/".join(reversed(iso.split("-")))


def pagina_inicial(raiz: Path) -> str:
    paineis = listar_paineis(raiz)
    if paineis:
        itens = []
        for p in paineis:
            r = resumo_do_painel(raiz / p)
            nome = p.rsplit("/", 1)[0] if "/" in p else "reports (exemplo)"
            linhas = []
            if r["total"] is not None:
                pct = f'{100 * r["com_indicador"] / r["total"]:.1f}'.replace(".", ",") if r["total"] else "0"
                linhas.append(f'{r["total"]} reviews de {r["jogos"]} jogo{"s" if r["jogos"] != 1 else ""}, {pct}% com algum indicador')
            if r["periodo"]:
                linhas.append(f'escritos entre {_data_br(r["periodo"][0])} e {_data_br(r["periodo"][1])}')
            if r["gerado"]:
                linhas.append(f'gerado em {r["gerado"]}' + (f', base de conhecimento v{r["versao"]}' if r["versao"] else ""))
            detalhes = "".join(f"<span>{html.escape(l)}</span>" for l in linhas)
            itens.append(f'<li><a href="{html.escape(rota_do_painel(p))}"><b>{html.escape(nome)}</b>{detalhes}</a></li>')
        corpo = f'<p class="sub">Escolha um painel:</p><ul class="paineis">{"".join(itens)}</ul>'
    else:
        corpo = ('<p class="vazio">Nenhum painel encontrado em reports/. Gere um classificando reviews, por exemplo: '
                 "<code>python main.py --entrada data/steam_*.csv --saida reports/steam</code></p>")
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Painéis de triagem</title>
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans:wght@400;600;700&display=swap">
<script>try {{ var t = localStorage.getItem("painel-tema"); if (t === "claro" || t === "escuro") document.documentElement.setAttribute("data-tema", t); }} catch (e) {{}}</script>
<style>
:root {{ {TOKENS_CLARO} }}
@media (prefers-color-scheme: dark) {{ :root:not([data-tema="claro"]) {{ {TOKENS_ESCURO} }} }}
:root[data-tema="escuro"] {{ {TOKENS_ESCURO} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--fundo); color: var(--tinta); font: 1rem/1.55 "IBM Plex Sans", system-ui, "Segoe UI", Roboto, Arial, sans-serif; }}
header {{ background: var(--cabeca); color: var(--cabeca-tinta); padding: 48px 16px 64px; }}
header div {{ max-width: 760px; margin: 0 auto; }}
.marca {{ display: flex; align-items: center; gap: 12px; margin: 0; }}
.marca-simbolo {{ flex: none; color: var(--cabeca-tinta); }}
.marca-t {{ stroke: #5b93ea; }} .marca-a {{ stroke: #f08a52; }}
header span {{ font: 500 .8125rem/1.4 "IBM Plex Mono", ui-monospace, Consolas, monospace; letter-spacing: .05em; text-transform: uppercase; color: var(--cabeca-suave); }}
main {{ max-width: 760px; margin: -32px auto 0; padding: 0 16px 64px; }}
h1 {{ font-size: clamp(1.9rem, 5vw, 2.6rem); line-height: 1.1; font-weight: 700; letter-spacing: -.02em; margin: 12px 0 0; }}
.sub {{ color: var(--tinta-suave); margin: 0 0 16px; background: var(--papel); border: 1px solid var(--linha); border-radius: 12px; padding: 12px 16px; }}
.paineis {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }}
.paineis a {{ display: grid; gap: 4px; padding: 20px 24px; border: 1px solid var(--linha);
  border-radius: 12px; background: var(--papel); color: var(--tinta); text-decoration: none; }}
.paineis a:hover {{ border-color: var(--tec); }}
.paineis a:focus-visible {{ outline: 3px solid var(--foco); outline-offset: 2px; }}
.paineis b {{ font-size: 1.15rem; }}
.paineis span {{ color: var(--tinta-suave); font-size: .9rem; font-variant-numeric: tabular-nums; }}
.paineis b {{ color: var(--tec); }}
.vazio {{ color: var(--tinta-suave); background: var(--papel); border: 1px dashed var(--linha); border-radius: 10px; padding: 16px; }}
</style></head>
<body><header><div><p class="marca">{LOGO_SIMBOLO}<span>TCC · Ciência da Computação · UDF · 2026/2</span></p><h1>Painéis de triagem de reviews</h1></div></header>
<main>{corpo}</main></body></html>"""


class Manipulador(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _rotear(self):
        """
        Rotas limpas: /steam serve reports/steam/painel.html e /exemplo serve
        reports/painel.html. Os endereços antigos (.../painel.html) e a barra
        no fim (/steam/) redirecionam (301) para a rota limpa, mantendo ?busca.
        Devolve True se já respondeu (página inicial ou redirecionamento).
        """
        bruto, _, consulta = self.path.partition("?")
        resto = ("?" + consulta) if consulta else ""
        barra_final = bruto.endswith("/")
        caminho = posixpath.normpath(unquote(bruto.split("#", 1)[0]))
        if not caminho.startswith("/") or caminho.startswith("//") or "/.." in caminho or caminho.startswith(".."):
            self.send_error(404)
            return True
        if barra_final and caminho != "/":
            caminho += "/"
        raiz = Path(self.directory)
        if caminho in ("/", "/index.html"):
            if self.command == "GET" or self.command == "HEAD":
                conteudo = pagina_inicial(raiz).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(conteudo)))
                self.end_headers()
                if self.command == "GET":
                    self.wfile.write(conteudo)
            return True
        mapa = rotas(raiz)
        por_arquivo = {"/" + rel: rota for rota, rel in mapa.items()}
        if caminho in por_arquivo:                        # endereço antigo
            return self._redirecionar(por_arquivo[caminho] + resto)
        if len(caminho) > 1 and caminho.endswith("/") and caminho.rstrip("/") in mapa:
            return self._redirecionar(caminho.rstrip("/") + resto)
        if caminho in mapa:                               # rota limpa: serve o arquivo do painel
            self.path = "/" + mapa[caminho] + resto
        return False

    def _redirecionar(self, destino: str) -> bool:
        self.send_response(301)
        self.send_header("Location", destino)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def list_directory(self, path):
        """Sem listagem de pastas: só os painéis e os arquivos pedidos pelo nome."""
        self.send_error(404)
        return None

    def do_GET(self):
        if not self._rotear():
            super().do_GET()

    def do_HEAD(self):
        if not self._rotear():
            super().do_HEAD()


def criar_servidor(raiz: Path, porta: int, endereco: str = "127.0.0.1") -> ThreadingHTTPServer:
    return ThreadingHTTPServer((endereco, porta), partial(Manipulador, directory=str(raiz)))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Serve os paineis de reports/ numa porta local.")
    parser.add_argument("--pasta", type=Path, default=Path("reports"))
    parser.add_argument("--porta", type=int, default=int(os.environ.get("PORT", 8090)),
                        help="Padrao: variavel PORT (Railway) ou 8090")
    parser.add_argument("--endereco", default="127.0.0.1", help="Use 0.0.0.0 so dentro de container")
    args = parser.parse_args(argv)

    servidor = criar_servidor(args.pasta, args.porta, args.endereco)
    print(f"Painel em http://localhost:{args.porta}/  (Ctrl+C para parar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()

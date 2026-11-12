"""
Serve os paineis de reports/ numa porta local.

    python -m src.servidor                 # http://localhost:8090
    python -m src.servidor --porta 9000

Pelo Docker (ver docker-compose.yml):

    docker compose up -d painel

A pagina inicial lista os painel.html encontrados em reports/. As
respostas vao com Cache-Control: no-store, para o navegador nunca
mostrar um painel antigo depois de uma nova classificacao.

Por padrao escuta so em 127.0.0.1 (nada fica exposto na rede). Dentro
do container ele escuta em 0.0.0.0, e quem limita a 127.0.0.1 e o
mapeamento de porta do docker-compose.
"""

import argparse
import html
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def listar_paineis(raiz: Path) -> list:
    return sorted(p.relative_to(raiz).as_posix() for p in raiz.rglob("painel.html"))


def pagina_inicial(raiz: Path) -> str:
    paineis = listar_paineis(raiz)
    if paineis:
        itens = "".join(
            f'<li><a href="{html.escape(p)}">{html.escape(p.rsplit("/", 1)[0] if "/" in p else "reports (exemplo)")}</a></li>'
            for p in paineis
        )
        corpo = f"<p>Escolha um painel:</p><ul>{itens}</ul>"
    else:
        corpo = ("<p>Nenhum painel encontrado em reports/. Gere um classificando reviews, "
                 "por exemplo: <code>python main.py --entrada data/steam_*.csv --saida reports/steam</code>.</p>")
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Painéis de triagem</title>
<style>:root{{color-scheme:light dark}}body{{font:16px/1.5 system-ui,"Segoe UI",sans-serif;max-width:640px;margin:48px auto;padding:0 16px}}
li{{margin:8px 0}}a{{font-size:1.1rem}}</style></head>
<body><h1>Painéis de triagem de reviews</h1>{corpo}</body></html>"""


class Manipulador(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            conteudo = pagina_inicial(Path(self.directory)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(conteudo)))
            self.end_headers()
            self.wfile.write(conteudo)
            return
        super().do_GET()


def criar_servidor(raiz: Path, porta: int, endereco: str = "127.0.0.1") -> ThreadingHTTPServer:
    return ThreadingHTTPServer((endereco, porta), partial(Manipulador, directory=str(raiz)))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Serve os paineis de reports/ numa porta local.")
    parser.add_argument("--pasta", type=Path, default=Path("reports"))
    parser.add_argument("--porta", type=int, default=8090)
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

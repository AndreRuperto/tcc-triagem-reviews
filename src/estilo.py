"""
Tokens de cor do painel, num modulo sem dependencias: usados por
src/painel.py e pela pagina inicial de src/servidor.py.

Visual: o do redesign aprovado (canvas "Redesign da pagina"): fundo cinza
quente, cartoes brancos, cabecalho escuro em faixa, IBM Plex, azul para
tecnico, laranja para afetivo-visual e roxo para misto.
"""

# Cores dos dois temas. Ficam aqui (e nao soltas no CSS) porque cada tema e
# usado em mais de um lugar: tema do sistema, tema escolhido no painel, a
# impressao (que segue o tema da tela) e a pagina inicial do servidor.
TOKENS_CLARO = """--fundo: #f4f5f3; --papel: #ffffff; --papel-2: #fafaf9; --tinta: #15171a; --tinta-suave: #4b5159; --linha: #dde0dc;
  --tec: #1f5fbf; --tec-marca: #e4ecf8; --afe: #b4410c; --afe-marca: #fbece4;
  --mis: #6a3fa0; --mis-marca: #f1ebf8; --ind: #9aa0a8; --ind-marca: #eceeea; --sobre-cor: #ffffff; --bolinha: #ffffff; --rolagem: #c9cdc8; --rolagem-forte: #9aa0a8;
  --cabeca: #15171a; --cabeca-tinta: #f4f5f3; --cabeca-suave: #c2c7cd; --cabeca-linha: #3a3f46;
  --foco: #1f5fbf; color-scheme: light;"""
TOKENS_ESCURO = """--fundo: #0f1114; --papel: #181b1f; --papel-2: #1d2126; --tinta: #e8eaed; --tinta-suave: #a9afb7; --linha: #2c3137;
  --tec: #79a8f0; --tec-marca: #1c2d48; --afe: #f2925f; --afe-marca: #3d2216;
  --mis: #b89be3; --mis-marca: #2e2442; --ind: #7d848d; --ind-marca: #23272c; --sobre-cor: #0f1114; --bolinha: #b4bac2; --rolagem: #3a4047; --rolagem-forte: #59616b;
  --cabeca: #08090b; --cabeca-tinta: #f4f5f3; --cabeca-suave: #b8bdc4; --cabeca-linha: #2c3137;
  --foco: #8ab4ff; color-scheme: dark;"""


# Logo: balao de review com uma linha de texto e o "grifo" dividido em tecnico
# (azul) e afetivo-visual (laranja), a mesma divisao da barra do painel.
# Versao inline (no cabecalho escuro): o balao usa currentColor.
LOGO_SIMBOLO = (
    '<svg class="marca-simbolo" viewBox="6 8 36 33" width="30" height="28" aria-hidden="true" focusable="false">'
    '<path d="M14 10h20a6 6 0 0 1 6 6v11a6 6 0 0 1-6 6H20l-7 6v-6.3A6 6 0 0 1 8 27V16a6 6 0 0 1 6-6Z" fill="none" '
    'stroke="currentColor" stroke-width="3" stroke-linejoin="round"/>'
    '<path d="M15 18.5h18" stroke="currentColor" stroke-opacity=".45" stroke-width="3" stroke-linecap="round"/>'
    '<path class="marca-t" d="M15 25h9" stroke-width="3.5" stroke-linecap="round"/>'
    '<path class="marca-a" d="M28 25h5" stroke-width="3.5" stroke-linecap="round"/></svg>'
)
# Favicon: o mesmo simbolo sobre um quadrado tinta (data URI, o painel funciona offline).
FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E"
    "%3Crect width='48' height='48' rx='12' fill='%2315171a'/%3E"
    "%3Cpath d='M14 10h20a6 6 0 0 1 6 6v11a6 6 0 0 1-6 6H20l-7 6v-6.3A6 6 0 0 1 8 27V16a6 6 0 0 1 6-6Z' fill='none' "
    "stroke='%23f4f5f3' stroke-width='3' stroke-linejoin='round'/%3E"
    "%3Cpath d='M15 18.5h18' stroke='%23f4f5f3' stroke-opacity='.45' stroke-width='3' stroke-linecap='round'/%3E"
    "%3Cpath d='M15 25h9' stroke='%235b93ea' stroke-width='3.5' stroke-linecap='round'/%3E"
    "%3Cpath d='M28 25h5' stroke='%23f08a52' stroke-width='3.5' stroke-linecap='round'/%3E%3C/svg%3E"
)

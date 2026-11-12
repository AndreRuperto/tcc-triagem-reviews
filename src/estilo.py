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

"""
Tokens de cor do painel, num modulo sem dependencias: usados por
src/painel.py e pela pagina inicial de src/servidor.py.
"""

# Cores dos dois temas. Ficam aqui (e nao soltas no CSS) porque cada tema e
# usado em mais de um lugar: tema do sistema, tema escolhido no painel e a
# impressao, que sempre sai no tema claro.
TOKENS_CLARO = """--fundo: #eef3f7; --papel: #ffffff; --tinta: #14212b; --tinta-suave: #4b5b67; --linha: #d3dde5;
  --tec: #0b6f78; --tec-marca: #a6eef2; --afe: #a3205f; --afe-marca: #ffc9e2;
  --ind: #77838d; --foco: #1b5fd6; color-scheme: light;"""
TOKENS_ESCURO = """--fundo: #0e1920; --papel: #15232c; --tinta: #e4edf2; --tinta-suave: #a2b3bf; --linha: #2b3c48;
  --tec: #5fd3db; --tec-marca: #1d5a60; --afe: #ff86bf; --afe-marca: #6a2348;
  --ind: #7f909c; --foco: #8ab4ff; color-scheme: dark;"""

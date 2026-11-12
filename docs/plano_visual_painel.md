# Plano: melhorar o visual do painel

Escrito em 12/11/2026, a partir das telas atuais de
`reports/steam/painel.html` (399 reviews, 4 jogos) no tema claro, no
escuro e em 375 px.

**Andamento:** fase 1 implementada em 12/11/2026 (frase-achado, segunda
barra ampliada ligada por um funil à barra geral, título do TCC e
contexto da coleta). Fase 2 implementada em 12/11/2026 (linha do tempo
clicável, categoria × recomendação, tabela comparativa por jogo
ordenável, indicadores com "ver todos"). Fase 3 implementada em
12/11/2026 (etiqueta de categoria, Misto em duas faixas sólidas em todo
o painel, ordenação escolhível, horas e votos da Steam no cartão,
matriz de confusão clicável com % por linha). Fase 4 implementada em
12/11/2026 (modo apresentação com atalho P, seletor de tema lembrado no
navegador, impressão/PDF com cabeçalho e número de página, seções
inteiras por página e nota dos filtros). Fase 5 implementada em
12/11/2026 (página inicial do servidor com o estilo e o resumo de cada
painel, índice no topo, filtro guardado na URL, estado vazio da
avaliação com comandos copiáveis). **Plano concluído.**

## Para que serve a tela

- **Trabalho principal:** a banca entender, em poucos segundos, o que o
  sistema encontrou e conseguir conferir por que cada review recebeu a
  categoria que recebeu.
- **Quem usa:** a autora, apresentando num projetor ou compartilhando a
  tela; depois, avaliadores lendo sozinhos no notebook.
- **Identidade:** o marca-texto sobre o texto do review (ciano =
  técnico, magenta = afetivo-visual). É o único elemento ousado; o
  resto deve ficar quieto. As melhorias abaixo reforçam isso, não
  competem com isso.

## Diagnóstico (o que as telas mostram hoje)

1. **A barra geral esconde o que interessa.** 87,7% é Indefinido
   (cinza). Afetivo-visual e Misto, o tema do TCC, viram um risco de
   1 px. O olho vai para o cinza.
2. **Não há conclusão escrita.** O cabeçalho diz quantos reviews e a
   versão da base, mas não o achado ("quase 9 em 10 reviews não têm
   nenhum indicador; 12% são técnicos").
3. **Falta o tempo.** Review bombing é um fenômeno temporal, e o painel
   não tem nenhuma linha do tempo, embora o CSV tenha `data_criacao`.
4. **Falta o cruzamento com a recomendação.** "Recomenda / não
   recomenda" aparece só em letra pequena em cada review; não há
   gráfico de categoria × recomendação.
5. **"Por jogo" são quatro barras quase iguais**, com o percentual
   repetido em texto corrido à direita. Difícil comparar jogos.
6. **Lista de indicadores com cauda longa:** muitos itens com valor 1,
   todos com a mesma barrinha mínima.
7. **Reviews:** o cabeçalho de cada cartão é pequeno e uniforme; a
   categoria não se destaca; o hachurado do Misto fica ilegível em
   tamanhos pequenos (legenda, borda do cartão).
8. **Matriz de confusão:** só números absolutos; não dá para clicar e
   ver quais reviews estão em cada célula.
9. **Sem modo de apresentação.** No projetor a fonte é pequena, e a
   impressão em PDF (para anexar ao TCC) só esconde os filtros.
10. **Página inicial do servidor** (`src/servidor.py`) é uma lista
    crua, sem o estilo do painel.
11. **Tema** segue só o sistema; num projetor claro com notebook em
    tema escuro, não há como trocar.

## O que fazer, em ordem de impacto

### Fase 1: a mensagem em 5 segundos (feita)
- **1.1 Frase-achado no topo.** Gerada dos dados em `montar_dados`:
  "De 399 reviews, 49 (12,3%) têm algum indicador: 47 técnicos,
  1 afetivo-visual e 1 misto." Em texto grande, com os nomes das
  categorias marcados com o próprio marca-texto.
- **1.2 Segunda barra, só dos reviews com indicador.** Abaixo da barra
  geral, uma barra "entre os 49 com indicador" (Técnico / Afetivo-visual
  / Misto), ligada visualmente à fatia não cinza da primeira. Assim as
  categorias raras ficam visíveis sem distorcer a escala da primeira.
- **1.3 Contexto da coleta no cabeçalho:** período das reviews (menor e
  maior `data_criacao`), idioma e nome do trabalho. Título passa a ser
  o do TCC, não "Triagem de reviews".

### Fase 2: os gráficos que faltam (feita)
- **2.1 Linha do tempo.** Reviews por semana (ou mês, conforme o
  intervalo), empilhadas por categoria, com filtro por jogo. Clicar numa
  coluna filtra a lista de reviews por aquele período. SVG gerado no
  JavaScript do próprio arquivo, sem biblioteca.
- **2.2 Categoria × recomendação.** Para cada categoria, uma barra
  dividida em "recomenda / não recomenda". Só aparece se o CSV tiver a
  coluna `recomendado`.
- **2.3 "Por jogo" como tabela pequena comparável.** Uma linha por
  jogo, colunas alinhadas: total, % com indicador, técnico,
  afetivo-visual, misto, % que recomenda; barra fina em cada célula.
  Ordenável por coluna. Substitui o texto corrido à direita.
- **2.4 Indicadores:** mostrar os 8 primeiros e um botão "Ver todos
  (n)"; agrupar os de valor 1 numa linha "outros n indicadores com 1
  ocorrência".

### Fase 3: a lista de reviews (feita)
- **3.1 Categoria como etiqueta** no canto do cartão (texto + cor de
  fundo suave), em vez de só negrito no cabeçalho.
- **3.2 Misto sem hachura:** duas faixas sólidas lado a lado (ciano e
  magenta) na borda do cartão, na legenda e nas barras estreitas; a
  hachura fica só em barras largas. *Na implementação a hachura saiu de todo lugar,
  inclusive das barras largas e da linha do tempo, para o Misto ter uma
  aparência só.*
- **3.3 Ordenação escolhível:** mais indicadores primeiro (atual), mais
  recentes, mais votadas como úteis (`votos_util`).
- **3.4 Metadados da Steam no cartão**, quando existirem: horas jogadas
  na hora da review e votos de utilidade. Pouco tempo de jogo é sinal de
  review bombing e hoje não aparece.
- **3.5 Matriz clicável:** clicar numa célula da matriz de confusão
  filtra a lista pelos reviews daquela célula (precisa incluir
  `categoria_manual` nos dados do painel quando houver gabarito).
  Adicionar % por linha abaixo de cada número.

### Fase 4: modo apresentação e PDF (feita)
- **4.1 Botão "Modo apresentação":** aumenta a escala tipográfica
  (base 20 px), esconde filtros secundários e limita a largura para
  projetor. Atalho de teclado `P`.
- **4.2 Seletor de tema** (claro / escuro / sistema), lembrado no
  navegador. O tema escuro atual não muda; só passa a poder ser forçado.
- **4.3 Folha de impressão de verdade:** cabeçalho com data e versão da
  base em cada página, gráficos sem cortes, cores com contraste em
  impressora P&B (rótulos escritos, que já existem), lista limitada aos
  reviews filtrados.

### Fase 5: acabamento (feita)
- **5.1 Página inicial do servidor** com os mesmos tokens do painel e,
  para cada painel, o total de reviews e a data de geração.
- **5.2 Âncoras e índice:** links no topo para cada seção; a URL guarda
  o filtro (`#jogo=...&cat=...`), para dar para compartilhar um recorte.
- **5.3 Estado vazio da avaliação** mais curto, com os dois comandos em
  blocos copiáveis.

## O que não muda
- Um arquivo HTML só, offline, sem CDN, sem framework e sem biblioteca
  de gráficos. A banca pode não ter internet.
- Texto dos reviews inserido só com `textContent`.
- Tokens em `:root`, tema escuro por variáveis, nenhum hex solto.
- Sem animações decorativas; movimento só em resposta a clique, e
  respeitando `prefers-reduced-motion`.
- Fora do escopo: editar a base de conhecimento pelo painel, login,
  banco de dados.

## Como verificar cada fase
- Screenshots em 1280 px, 375 px, tema claro e escuro, servidos por
  `docker compose up -d painel` (o arquivo local sempre abre claro).
- Contraste calculado para cada cor nova: texto ≥ 4,5:1, gráficos e
  componentes ≥ 3:1. Os valores atuais (6,3:1 a 16,4:1 no claro) são o
  piso a manter.
- Alvos de toque ≥ 44 px, tudo operável por teclado, sem rolagem
  horizontal em 375 px, zoom de 200%.
- Testes em `tests/test_painel.py` para cada dado novo que
  `montar_dados` passar a calcular (frase-achado, série temporal,
  cruzamento com recomendação, células da matriz).
- Teste do genérico: se trocar o assunto e a tela servir para outro
  produto sem mudar nada, a fase não está pronta.

## Arquivos envolvidos
- `src/painel.py`: `montar_dados` (dados novos) e `MODELO` (HTML, CSS e
  JavaScript).
- `src/servidor.py`: página inicial (5.1).
- `tests/test_painel.py`, `tests/test_servidor.py`.
- `README.md`: seção "Painel de resultados" ao final de cada fase.

## Ordem sugerida e tamanho
| Fase | O que entrega | Tamanho |
|---|---|---|
| 1 | A conclusão legível de longe | pequeno |
| 2 | Tempo e recomendação, o que o TCC discute | médio |
| 3 | Conferência dos reviews mais rápida | médio |
| 4 | Apresentação e anexo em PDF | médio |
| 5 | Acabamento | pequeno |

As fases 1 e 2 são as que mais mudam o que a banca vê. A fase 3.5
depende de existir o gabarito manual.

## Segunda rodada: regras de design (12/11/2026, feita)

Crítica da tela pronta em 1280 px, depois das cinco fases:

- O título do TCC competia com a frase-achado, que é a mensagem.
- Treze "pílulas" na primeira tela (ferramentas, índice, botões).
- Todas as seções com o mesmo peso, e metade direita vazia em várias.
- Legenda de cores repetida embaixo da linha do tempo.
- A recomendação trouxe duas cores (verde e salmão) fora da paleta.
- Tamanhos de letra soltos (.75, .8, .85, .9, .95 rem).

O que foi aplicado:

- **Estrutura de margem.** A partir de 960 px, cada seção tem o título e
  a explicação numa coluna de margem (14,5 rem) e os dados ao lado, como
  anotação de margem num texto marcado. Na lista de reviews, os filtros
  ficam na margem e acompanham a rolagem. Abaixo de 960 px e na
  impressão, tudo empilha.
- **Hierarquia do topo.** O título do TCC virou um rótulo pequeno na
  margem; a frase-achado é o maior texto da página, na mesma serifa dos
  reviews (é um texto lido e marcado, como eles).
- **Escala tipográfica única**, razão 1,25 (`--t-p` .875, `--t-0` 1,
  `--t-1` 1,25, `--t-2` 1,5625, `--t-3` 1,953 rem), mais `--t-leitura`
  para a serifa dos reviews. Nenhum tamanho solto no CSS (o script de
  mudança verificava isso).
- **Forma com significado.** Pílula só no que liga e desliga (filtros de
  categoria, etiquetas). Ações são retângulos discretos de 4 px; o
  índice virou links de texto sublinhados.
- **Paleta só das categorias.** A recomendação passou a ser uma barra
  única na cor do texto; saíram os tokens `--sim` e `--nao` e a legenda
  deles.
- **Legenda como tabela**, com os números alinhados (reviews, % do
  total, % dos com indicador) e a regra de cada categoria.
- **Um acessório a menos:** a legenda repetida da linha do tempo saiu.
- Correção encontrada na crítica: marcas deslocadas em reviews com
  emoji (o Python contava 1 caractere, o navegador 2).

O que não mudou: paleta das categorias, marca-texto, arquivo único
offline, textContent, impressão no tema claro.

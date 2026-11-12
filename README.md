# Triagem de Reviews de Jogos Digitais com IA Simbólica

TCC — Ciência da Computação — UDF — Melissa Aragão Leite (2026_2)

## Objetivo
Sistema especialista baseado em regras para classificar reviews de jogos
digitais em quatro categorias: técnico, afetivo-visual, misto ou indefinido,
separando críticas de falhas técnicas de comentários motivados por rejeição
à representação de personagens femininas (review bombing).

## Ambiente de execução
- VM Oracle Cloud (Ampere A1 / ARM aarch64)
- 2 vCPUs, 11GB RAM, 195GB disco
- Docker instalado (v29.6.0) para garantir reprodutibilidade (RNF6 do TCC)
- Todo o código roda dentro de container — não depende de instalação
  local de Python/pip no host

## Estrutura do projeto
projeto_reviews/
├── data/       # CSVs de entrada e saída
├── config/     # base_conhecimento.json (indicadores e pesos)
├── reports/    # gráficos e relatórios gerados
├── src/        # código-fonte do sistema especialista
├── docs/       # documentação de decisões técnicas
├── tests/      # testes automatizados do classificador
└── main.py     # ponto de entrada

## Como rodar os testes
Na raiz do projeto (dentro do container ou com as dependências instaladas):

    python -m unittest discover -s tests

Pelo Docker, sem instalar nada no host (o `COPY . .` do Dockerfile já
inclui a pasta tests/):

    docker compose build
    docker compose run --rm classificador python -m unittest discover -s tests

## Fluxo de validação (reviews reais → gabarito → métricas)
Protocolo completo, com as regras de rotulagem e de cegamento, em
docs/protocolo_rotulagem.md. Pelo Docker, prefixe cada comando com
`docker compose run --rm classificador`.

    # 1. coletar reviews em português (não precisa de chave de API)
    #    todos os jogos de config/jogos.json; o resumo mostra quantas existem em pt-BR
    python -m src.coleta_steam --lote config/jogos.json --max 100
    #    ou um jogo só (appid = número na URL da loja), opcionalmente num período
    python -m src.coleta_steam --appid <id> --jogo "<nome>" --max 500 --periodo 2025-01-30 2025-02-28
    #    --filtro helpful = mais úteis de todo o histórico; por padrão as reviews
    #    que a Steam marca como "fora do assunto" (review bombing) ENTRAM na coleta
    # 2. classificar (aceita vários CSVs, que são juntados)
    python main.py --entrada data/steam_*.csv --saida reports/steam
    # 3. sortear a amostra cega para rotulagem manual
    python -m src.amostragem --tamanho 200
    # 4. preencher categoria_manual e salvar como data/gabarito_rotulado.csv
    # 5. matriz de confusão, precisão, revocação, F1 (e kappa, com --segundo)
    python -m src.avaliacao --gabarito data/gabarito_rotulado.csv

## Painel de resultados
Cada classificação gera também `painel.html` na pasta de relatórios
(ex.: `reports/steam/painel.html`): um arquivo só, que abre offline em
qualquer navegador, pensado para a apresentação à banca. Mostra a
divisão por categoria e por jogo, os indicadores mais acionados, a
matriz de confusão (depois da avaliação) e cada review com os
indicadores marcados no próprio texto, o que deixa a classificação
auditável a olho. Para gerar de novo sem reclassificar:

    python -m src.painel --pasta reports/steam

Na barra do topo do painel:
- **Modo apresentação** (ou tecla `P`; `Esc` sai): letra maior para
  projetor e só os filtros essenciais.
- **Tema**: do sistema, claro ou escuro (fica lembrado no navegador).
- **Imprimir ou salvar em PDF**: sai sempre no tema claro, com título,
  versão da base e data no topo de cada página e a lista de reviews
  inteira com os filtros escolhidos na tela (filtre antes para um anexo
  menor: sem filtro são cerca de 100 páginas para 399 reviews).

### Abrir numa porta local
Pelo Docker (fica rodando em segundo plano):

    docker compose up -d painel      # http://localhost:8090
    docker compose stop painel       # para

Sem Docker, com Python:

    python -m src.servidor           # http://localhost:8090 (Ctrl+C para parar)

A página inicial lista os painéis de `reports/`. O servidor desliga o
cache do navegador, então basta recarregar a página depois de uma nova
classificação. Para usar outra porta: `PAINEL_PORTA=9000 docker compose
up -d painel` ou `python -m src.servidor --porta 9000`.

A porta fica presa a 127.0.0.1, então na VM o painel não fica exposto
na internet. Para ver o painel da VM no seu computador, abra um túnel
SSH e acesse http://localhost:8090 no seu navegador:

    ssh -L 8090:localhost:8090 <usuario>@<ip-da-vm>

## Status atual
- [x] VM provisionada e configurada
- [x] Docker instalado e testado
- [x] Estrutura de pastas criada
- [x] Repositório Git inicializado
- [x] Dockerfile criado
- [x] Base de conhecimento inicial (v1.0)
- [x] Classificador implementado e testado (7 reviews de exemplo, via Docker/Portainer)
- [x] Classificador com stemming (RSLP) implementado e testado
- [x] Correção da dupla contagem e base de conhecimento v1.1 (classificador v1.3)
- [x] Testes automatizados (tests/)
- [x] Ferramentas de validação: coletor Steam, amostra cega, avaliação (matriz de confusão, F1, kappa)
- [ ] Dicionário de sinônimos curados (config/sinonimos.json)
- [ ] Escolher os jogos e coletar reviews reais (API Steam)
- [ ] Revisar docs/protocolo_rotulagem.md e rotular a amostra (gabarito)
- [ ] Comparação automático x manual / ajuste de pesos
- [ ] Relatórios finais gerados

## Log de decisões técnicas
- Escolhida abordagem de IA simbólica (sistema especialista) em vez de
  Machine Learning/Deep Learning: justificativa em docs/decisao_ia.md
  (transparência, auditabilidade, viabilidade em hardware sem GPU).
- Escolhido Docker em vez de venv: garante reprodutibilidade do ambiente
  completo, não só das bibliotecas Python.
- Adicionado stemming (RSLP/NLTK) como camada complementar à comparação
  literal, para tratar variações morfológicas não cadastradas na base
  de conhecimento: docs/decisao_stemming.md.
- Corrigida dupla contagem de indicadores que reduzem ao mesmo radical
  (bug identificado e corrigido na v1.2 do classificador):
  docs/observacoes_teste_v1.md.
- v1.3: a correção da v1.2 só valia quando o casamento literal vinha
  depois do casamento por radical; a ordem dos indicadores na base mudava
  o escore. Agora o casamento literal roda para todos os indicadores antes
  do casamento por radical, e cada radical conta uma única vez.
- v1.3: radicais de uma palavra só com menos de 3 letras não casam
  sozinhos (o RSLP reduz "trava" e "trem" a "tr").
- Base v1.1: o RSLP não aproxima "cai" de "caiu", então o caso do
  review 3 não era resolvido pelo stemming. Cadastrados "servidor cai"
  e "trava". A versão da base agora fica no próprio JSON (campo "versao")
  e é gravada em cada linha do resultado.
- Versões das bibliotecas fixadas em requirements.txt (RNF6).
- Coleta migrada para a Web API IUserReviewsService/GetAppReviews: a
  Valve desligou o endpoint store.steampowered.com/appreviews em
  outubro de 2026. A API nova esconde por padrão as reviews que a Steam
  marca como fora do assunto (como ela trata review bombing); o coletor
  pede filter_offtopic_activity=false para elas entrarem.
- Coleta: o identificador do autor (steamid) não é gravado; só o texto
  e metadados agregados (data, votos, horas jogadas).
- Gabarito cego: a planilha de rotulagem não mostra a resposta do
  sistema; a amostra é estratificada pela categoria automática, com
  semente fixa, para as classes raras terem exemplos suficientes.

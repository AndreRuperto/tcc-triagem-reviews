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
- [x] Testes automatizados (tests/test_classificador.py)
- [ ] Dicionário de sinônimos curados (config/sinonimos.json)
- [ ] Coleta de reviews reais (API Steam)
- [ ] Classificação manual de amostra (gabarito)
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

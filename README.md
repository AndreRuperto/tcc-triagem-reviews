# Triagem de reviews de jogos digitais com IA simbólica

**TCC — Ciência da Computação — UDF — 2026/2**
Autora: Melissa Aragão Leite

Sistema especialista baseado em regras que classifica reviews de jogos digitais em
**Técnico**, **Afetivo-visual**, **Misto** ou **Indefinido**. O objetivo é separar críticas
a falhas técnicas de comentários motivados pela rejeição à aparência de personagens
femininas (*review bombing*).

Toda classificação é rastreável: o sistema registra quais indicadores encontrou, os
escores de cada grupo, a regra aplicada e a confiança. Não há aprendizado de máquina
envolvido (justificativa em [docs/decisao_ia.md](docs/decisao_ia.md)).

**Painel online:** https://triagem-reviews.up.railway.app (Railway, deploy automático a cada push na `main`)

**Sumário:** [Como funciona](#como-funciona) · [Executar](#como-executar) ·
[Validação](#fluxo-de-validação) · [Painel](#painel-de-resultados) ·
[Resultados](#primeira-coleta-real) · [Estrutura](#estrutura) ·
[Andamento](#andamento) · [Decisões](#decisões-técnicas)

---

## Como funciona

```
reviews (CSV) → preparação → base de conhecimento → escores → regras → relatórios + painel
```

1. **Entrada** — um ou vários CSVs com `id_review`, `jogo` e `texto_original` (mais
   `nota`, `recomendado` e metadados da Steam quando houver).
2. **Preparação** — remove duplicados e textos vazios e padroniza o texto (minúsculas,
   sem acentos, links e pontuação). O texto original nunca é alterado (RNF5).
3. **Base de conhecimento** — [config/base_conhecimento.json](config/base_conhecimento.json)
   (v1.1): indicadores técnicos e afetivo-visuais com peso de 1 a 3. A versão fica no
   próprio JSON e é gravada em cada linha do resultado.
4. **Escores** — primeiro o casamento literal de todos os indicadores, depois o casamento
   pelo radical (stemmer RSLP do NLTK). Cada radical conta uma vez só, seja qual for a
   ordem da base.
5. **Regras** — a matriz abaixo define a categoria.
6. **Relatórios** — CSVs, gráfico e um painel HTML na pasta de saída.

### Matriz de classificação

|                  | Afetivo = 0       | Afetivo > 0             |
|------------------|-------------------|-------------------------|
| **Técnico = 0**  | R4 — Indefinido   | R2 — Afetivo-visual     |
| **Técnico > 0**  | R1 — Técnico      | R3 — Misto              |

### Confiança

```
confiança = max(T, A) / (T + A)
```

Vale 1,00 quando só um grupo pontua e cai para 0,50 quando os dois empatam. Sem nenhum
indicador, a confiança é 0.

---

## Como executar

Tudo roda em Docker, sem instalar Python no host. Para rodar direto no Python, use os
mesmos comandos sem o prefixo `docker compose run --rm classificador`.

```bash
docker compose build
```

```bash
docker compose run --rm classificador python main.py
```

Sem argumentos, `main.py` classifica `data/reviews_entrada.csv` (7 reviews de exemplo)
e grava em `reports/`. Para outros arquivos:

```bash
docker compose run --rm classificador python main.py --entrada data/steam_*.csv --saida reports/steam
```

### Testes

```bash
docker compose run --rm classificador python -m unittest discover -s tests
```

São 60 testes em `tests/`: classificador, validação, painel e servidor.

### Saídas

| Arquivo | Conteúdo |
|---|---|
| `reviews_classificados.csv` | Cada review com escores, indicadores, categoria, regra, confiança e versão da base |
| `reviews_tecnicos.csv` | Só os reviews Técnico e Misto |
| `resumo_categorias.csv` | Quantidade e percentual por categoria |
| `distribuicao_categorias.png` | Gráfico da distribuição |
| `painel.html` | Painel interativo, offline, para a banca |

---

## Fluxo de validação

Reviews reais → gabarito manual → métricas. As regras de rotulagem e de cegamento
estão em [docs/protocolo_rotulagem.md](docs/protocolo_rotulagem.md). Pelo Docker,
prefixe cada comando com `docker compose run --rm classificador`.

**1. Coletar** reviews em pt-BR (não precisa de chave de API):

```bash
python -m src.coleta_steam --lote config/jogos.json --max 100
```

Ou um jogo só (o `appid` é o número na URL da loja), opcionalmente num período:

```bash
python -m src.coleta_steam --appid <id> --jogo "<nome>" --max 500 --periodo 2025-01-30 2025-02-28
```

`--filtro helpful` pega as mais úteis de todo o histórico. Por padrão, as reviews que a
Steam marca como "fora do assunto" (o jeito dela de tratar review bombing) entram na
coleta. O steamid do autor não é gravado.

**2. Classificar** (aceita vários CSVs, que são juntados):

```bash
python main.py --entrada data/steam_*.csv --saida reports/steam
```

**3. Sortear a amostra cega** para rotulagem manual (estratificada pela categoria
automática, com semente fixa):

```bash
python -m src.amostragem --tamanho 200
```

**4. Rotular:** preencher `categoria_manual` e salvar como `data/gabarito_rotulado.csv`.

**5. Avaliar:** matriz de confusão, precisão, revocação e F1 (e kappa, com `--segundo`):

```bash
python -m src.avaliacao --gabarito data/gabarito_rotulado.csv
```

---

## Painel de resultados

Cada classificação gera um `painel.html` na pasta de relatórios (por exemplo
`reports/steam/painel.html`). É um arquivo só, que abre offline em qualquer navegador.
Ele mostra a divisão por categoria e por jogo, os indicadores mais acionados, a matriz de
confusão (depois da avaliação) e cada review com os indicadores marcados no próprio
texto, para auditar a classificação a olho. No fim de cada cartão fica a conta: cada indicador com o
seu peso na base (`trava +2`, `bug +1`), a soma de cada grupo, a barra técnico × afetivo-visual (a
confiança) e o veredito com a regra aplicada. Passar o mouse num indicador acende o trecho dele no texto.

- **Modo apresentação** (tecla `P`, `Esc` sai): letra maior para projetor.
- **Tema**: do sistema, claro ou escuro.
- **Imprimir ou salvar em PDF**: no tema que estiver na tela (claro, escuro ou o do sistema), em A4 com
  tipografia compacta, com os filtros aplicados na tela e a lista de reviews inteira.
- **Link do recorte**: jogo, categoria, período, busca e ordenação ficam na URL.

Para gerar o painel de novo sem reclassificar:

```bash
python -m src.painel --pasta reports/steam
```

### Online (Railway)

O serviço `painel` do projeto `tcc-triagem-reviews` no Railway faz o build pelo
`Dockerfile` a cada push na `main` e roda `python -m src.servidor --endereco 0.0.0.0`.
A porta vem da variável `PORT`. O painel lá é público: qualquer pessoa com o link vê os
reviews coletados (textos públicos da Steam, sem o steamid).

### Abrir numa porta local

```bash
docker compose up -d painel
```

Abre em http://localhost:8090. Para parar, use `docker compose stop painel`. Sem Docker, o
equivalente é `python -m src.servidor`. A página inicial lista os painéis de `reports/`.
Para usar outra porta: `PAINEL_PORTA=9000` no Docker ou `--porta 9000` no Python.

A porta fica presa a 127.0.0.1, então na VM o painel não fica exposto na internet. Para
vê-lo do seu computador, abra um túnel SSH e acesse http://localhost:8090:

```bash
ssh -L 8090:localhost:8090 <usuario>@<ip-da-vm>
```

---

## Primeira coleta real

Coleta de 11/11/2026: as 100 reviews pt-BR mais recentes de cada jogo candidato de
[config/jogos.json](config/jogos.json). Resultado em `reports/steam/`.

| Jogo | appid | Reviews pt-BR disponíveis |
|---|---|---|
| Marvel's Spider-Man 2 | 2651280 | 3.235 |
| Dragon Age: The Veilguard | 1845910 | 1.191 |
| Horizon Forbidden West | 2420110 | 1.596 |
| Star Wars Outlaws | 2842040 | 272 |

| Categoria | Reviews | % |
|---|---|---|
| Indefinido | 350 | 87,7 |
| Técnico | 47 | 11,8 |
| Afetivo-visual | 1 | 0,3 |
| Misto | 1 | 0,3 |

**O que isso indica:**
- Só 57,4% dos reviews Técnicos recomendam o jogo, contra 88,6% dos Indefinidos. É um
  indício de que o grupo técnico capta reclamação real.
- As 100 mais recentes são todas de 2026, longe dos lançamentos. Para pegar o review
  bombing é preciso coletar por período, nas semanas de lançamento.
- Em pt-BR, a crítica de representação aparece com outro vocabulário ("lacração", "woke"),
  mais ideológico do que sobre aparência, e a base atual não cobre isso. A definição da
  categoria afetivo-visual está em discussão com a orientação.

---

## Estrutura

```
tcc-triagem-reviews/
├── config/
│   ├── base_conhecimento.json   # indicadores e pesos (v1.1)
│   └── jogos.json               # jogos candidatos da coleta
├── data/                        # exemplo e CSVs coletados da Steam
├── docs/                        # decisões técnicas, protocolo e plano do painel
├── reports/                     # relatórios do exemplo; reports/steam/ da coleta real
├── src/
│   ├── classificador.py         # normalização, escores, regras e confiança
│   ├── coleta_steam.py          # coleta pela Web API GetAppReviews
│   ├── amostragem.py            # amostra cega para o gabarito
│   ├── avaliacao.py             # matriz de confusão, F1, kappa
│   ├── painel.py                # painel HTML
│   └── servidor.py              # servidor local do painel
├── tests/                       # testes automatizados
├── main.py                      # ponto de entrada
├── Dockerfile
└── docker-compose.yml
```

## Ambiente

- VM Oracle Cloud (Ampere A1, ARM aarch64), 2 vCPUs, 11 GB de RAM
- Docker para reproduzir o ambiente completo (RNF6), com versões fixadas em `requirements.txt`
- Python 3.11, pandas, matplotlib e NLTK (RSLP)

---

## Andamento

- [x] VM, Docker, estrutura do projeto e Dockerfile
- [x] Base de conhecimento v1.1 e classificador v1.3 (stemming e correção da dupla contagem)
- [x] Testes automatizados
- [x] Ferramentas de validação: coleta Steam, amostra cega, avaliação
- [x] Primeira coleta real (100 reviews por jogo candidato)
- [x] Painel de resultados para a banca
- [ ] Escolher os jogos e fazer a coleta definitiva por período
- [ ] Dicionário de sinônimos curados (`config/sinonimos.json`)
- [ ] Revisar o protocolo de rotulagem e rotular a amostra (gabarito)
- [ ] Comparação automático × manual e ajuste de pesos
- [ ] Relatórios finais

O passo a passo detalhado está em [PROXIMOS_PASSOS.md](PROXIMOS_PASSOS.md).

## Decisões técnicas

- **IA simbólica em vez de ML/DL** — transparência, auditabilidade e execução sem GPU.
  [docs/decisao_ia.md](docs/decisao_ia.md)
- **Docker em vez de venv** — reproduz o ambiente inteiro, não só as bibliotecas.
- **Stemming RSLP como complemento** — cobre flexões regulares ("fechou sozinho" casa com
  "fecha sozinho"). Ele não une formas curtas como "cai" e "caiu", por isso "servidor cai"
  e "trava" foram cadastrados na base v1.1. Radicais de uma palavra só com menos de 3
  letras não casam sozinhos, porque o RSLP reduz "trava" e "trem" a "tr".
  [docs/decisao_stemming.md](docs/decisao_stemming.md)
- **Dupla contagem (v1.2 e v1.3)** — indicadores com o mesmo radical somam uma vez só, seja
  qual for a ordem da base. [docs/observacoes_teste_v1.md](docs/observacoes_teste_v1.md)
- **Coleta pela Web API GetAppReviews** — o endpoint antigo da loja foi desligado em
  outubro de 2026. O coletor pede `filter_offtopic_activity=false` para incluir as reviews
  que a Steam esconde como fora do assunto.
- **Privacidade** — o identificador do autor não é gravado, só o texto e metadados
  agregados (data, votos, horas jogadas).
- **Gabarito cego** — a planilha de rotulagem não mostra a resposta do sistema.
- Critérios para incluir indicadores na base:
  [docs/criterios_base_conhecimento.md](docs/criterios_base_conhecimento.md)

### Limitações conhecidas

- Negação não é tratada ("não tem bug nenhum" vira Técnico).
- Termos curtos podem casar pelo radical ("lag" com "lagado").

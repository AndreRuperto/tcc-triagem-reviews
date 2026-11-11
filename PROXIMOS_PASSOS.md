# Próximos passos: TCC Triagem de Reviews

**Atualizado em:** 11/11/2026 · **branch:** `claude/project-analysis-6682a0` · **remoto:** `fork` → https://github.com/AndreRuperto/tcc-triagem-reviews

## O que foi feito
- Classificador v1.3: dupla contagem corrigida de verdade (não depende da ordem da base), radicais curtos demais não casam sozinhos.
- Base de conhecimento v1.1 ("servidor cai", "trava"; versão gravada no JSON e em cada resultado).
- Ferramentas de validação:
  - `src/coleta_steam.py`: reviews pt-BR pela Web API GetAppReviews (sem chave; inclui as reviews "fora do assunto"; filtro por período), sem gravar o steamid; modo `--lote` com resumo do volume disponível;
  - `src/amostragem.py`: amostra estratificada e cega para o gabarito;
  - `src/avaliacao.py`: matriz de confusão, precisão/revocação/F1, kappa entre anotadores, lista de divergências.
- `main.py --entrada/--saida` para classificar qualquer CSV.
- Protocolo de rotulagem (rascunho): `docs/protocolo_rotulagem.md`.
- 38 testes (`python -m unittest discover -s tests`).

## Primeira coleta real (11/11/2026, 100 reviews pt-BR por jogo, mais recentes)
| Jogo | appid | reviews pt-BR disponíveis |
|---|---|---|
| Marvel's Spider-Man 2 | 2651280 | 3235 |
| Dragon Age: The Veilguard | 1845910 | 1191 |
| Horizon Forbidden West | 2420110 | 1596 |
| Star Wars Outlaws | 2842040 | 272 |

Achados (importantes para a metodologia):
- As 100 "mais recentes" são todas de 2026, longe dos lançamentos. Para pegar o review bombing é preciso coletar por período (`--periodo DE ATE`) nas semanas de lançamento.
- Classificando as 400: Indefinido 350, Técnico 47, Afetivo-visual 1, Misto 1.
- A crítica de representação em pt-BR aparece com outro vocabulário ("lacração", "woke", "forçaram a barra com a MJ"), mais ideológico/narrativo do que sobre aparência. A base de conhecimento não cobre isso. Decisão da autora com a orientação: ampliar a categoria afetivo-visual (e a base) ou manter a definição restrita à aparência e registrar a raridade como resultado.
- Spider-Man 2 no mês do lançamento no PC (fev/2025): 12 de 100 reviews citam MJ/woke/aparência, quase sempre o papel dela na história, não o rosto.
- Os CSVs coletados estão versionados em `data/steam_*.csv` (textos públicos da Steam, sem o steamid).

## Estado atual
- **Funciona e foi testado:** os 38 testes no Python local (a imagem Docker x86 passou nos 33 da versão anterior); coleta real pela API nova da Steam; fluxo completo pela linha de comando com dados de exemplo.
- **Não testado:**
  - build da imagem em ARM64 (a VM Oracle). As versões fixadas têm pacote para Python 3.11 aarch64, mas o build não foi rodado lá.

## Próximos passos (em ordem)
- [ ] Na VM: `docker compose build` e `docker compose run --rm classificador python -m unittest discover -s tests`.
- [ ] Na VM, checar o volume em pt-BR dos 4 candidatos de `config/jogos.json` (não precisa de chave de API):
      `docker compose run --rm classificador python -m src.coleta_steam --lote config/jogos.json --max 100`
- [ ] Ler uma amostra de cada CSV: a crítica à aparência aparece mesmo nas reviews da Steam? Fechar a lista e justificar no TCC.
- [ ] Decidir a definição da categoria afetivo-visual diante do vocabulário real ("lacração", "woke").
- [ ] Coleta definitiva por período, nas semanas de lançamento de cada jogo (`--periodo DE ATE`, ou "periodo" no `config/jogos.json`), e/ou `--filtro helpful` para as mais úteis de todo o histórico.
- [ ] Classificar: `python main.py --entrada data/steam_<id>.csv` (para vários jogos, juntar os CSVs antes).
- [ ] Revisar `docs/protocolo_rotulagem.md` (definições das categorias e casos difíceis) com a orientação.
- [ ] Gerar a amostra cega: `python -m src.amostragem --tamanho 200`.
- [ ] Rotular a amostra (idealmente duas pessoas, para o kappa).
- [ ] Avaliar: `python -m src.avaliacao --gabarito data/gabarito_rotulado.csv`.
- [ ] Analisar `reports/avaliacao/divergencias.csv` e ajustar a base só com uma parte do gabarito; medir de novo na parte intocada.
- [ ] Dicionário de sinônimos (`config/sinonimos.json`) e `docs/decisao_sinonimos.md`.

## Decisões e problemas conhecidos
- Negação não é tratada ("não tem bug nenhum" → Técnico): limitação registrada em teste.
- Termos curtos casam via radical ("lag" com "lagado").
- Não ajustar pesos olhando o mesmo gabarito usado para medir (sobreajuste).

## Comandos úteis
    python -m unittest discover -s tests
    python main.py
    git push fork claude/project-analysis-6682a0

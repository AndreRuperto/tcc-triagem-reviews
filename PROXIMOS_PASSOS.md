# Próximos passos: TCC Triagem de Reviews

**Atualizado em:** 11/11/2026 · **branch:** `claude/project-analysis-6682a0` · **remoto:** `fork` → https://github.com/AndreRuperto/tcc-triagem-reviews

## O que foi feito
- Classificador v1.3: dupla contagem corrigida de verdade (não depende da ordem da base), radicais curtos demais não casam sozinhos.
- Base de conhecimento v1.1 ("servidor cai", "trava"; versão gravada no JSON e em cada resultado).
- Ferramentas de validação:
  - `src/coleta_steam.py`: reviews pt-BR da API pública da Steam (sem chave), sem gravar o steamid; modo `--lote` com resumo do volume disponível;
  - `src/amostragem.py`: amostra estratificada e cega para o gabarito;
  - `src/avaliacao.py`: matriz de confusão, precisão/revocação/F1, kappa entre anotadores, lista de divergências.
- `main.py --entrada/--saida` para classificar qualquer CSV.
- Protocolo de rotulagem (rascunho): `docs/protocolo_rotulagem.md`.
- 33 testes (`python -m unittest discover -s tests`).

## Estado atual
- **Funciona e foi testado:** os testes, no Python local (33) e dentro da imagem Docker x86 (29, antes da coleta em lote); fluxo completo pela linha de comando com dados de exemplo.
- **Não testado:**
  - coleta contra a API real da Steam (não deu para acessar daqui; o código segue o formato documentado e foi testado com respostas simuladas);
  - build da imagem em ARM64 (a VM Oracle). As versões fixadas têm pacote para Python 3.11 aarch64, mas o build não foi rodado lá.

## Próximos passos (em ordem)
- [ ] Na VM: `docker compose build` e `docker compose run --rm classificador python -m unittest discover -s tests`.
- [ ] Na VM, checar o volume em pt-BR dos 4 candidatos de `config/jogos.json` (não precisa de chave de API):
      `docker compose run --rm classificador python -m src.coleta_steam --lote config/jogos.json --max 100`
- [ ] Ler uma amostra de cada CSV: a crítica à aparência aparece mesmo nas reviews da Steam? Fechar a lista e justificar no TCC.
- [ ] Coleta definitiva com `--max` maior (e `--filtro all` para pegar as mais úteis, onde costuma estar o pico do review bombing).
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

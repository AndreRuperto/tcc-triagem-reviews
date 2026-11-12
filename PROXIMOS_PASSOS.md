# Próximos passos

**Data:** 2026-11-12 · **Branch:** `claude/page-visual-improvements-8049cd`

## Feito nesta sessão
- Redesign visual do relatório do projeto (canvas de design no claude.ai, privado).
- Descoberto que o RSLP não une "cai" e "caiu" (cai → cai, caiu → caiu): o stemming
  nunca resolveu o review 3. Cadastrado "servidor cai" (peso 3) na base.
- Corrigido o comentário em `src/classificador.py` que dizia o contrário e registrada a
  correção em `docs/decisao_stemming.md`.
- Relatórios em `reports/` regenerados via Docker: Técnico 2, Afetivo-visual 2, Misto 1,
  Indefinido 2. Review 3 agora é Misto (R3, confiança 0,50).

## Estado atual
- Classificador v1.2 + base com "servidor cai": funcionando e testado nos 7 reviews de exemplo.
- `versao_base` no CSV continua "1.0" (constante `BASE_VERSION` em `main.py`), embora a base
  tenha mudado — decidir se sobe para 1.1.

## Próximos passos
- [ ] Decidir versão da base (1.0 → 1.1) e atualizar `BASE_VERSION`
- [ ] Dicionário de sinônimos/variações curadas (`config/sinonimos.json`) — incluir formas
      verbais curtas que o RSLP não une (cai/caiu, sai/saiu, etc.)
- [ ] Coleta de reviews reais (API Steam)
- [ ] Classificação manual de amostra (gabarito)
- [ ] Comparação automático x manual / ajuste de pesos
- [ ] Relatórios finais

## Comandos úteis
```bash
docker compose up --build
```

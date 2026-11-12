# Observacoes do primeiro teste (base de conhecimento v1.0)

## Resultado do teste com 7 reviews de exemplo
- Tecnico: 2
- Afetivo-visual: 3
- Indefinido: 2
- Misto: 0

## Limitacao identificada
Review 3 ("O servidor cai e a protagonista parece um homem.") deveria
ser classificado como "Misto" (contem critica tecnica e afetivo-visual),
mas foi classificado como "Afetivo-visual" (escore_tecnico=0).

Causa raiz: a base de conhecimento possui os indicadores "erro no
servidor" e "servidor caiu", mas nao "servidor cai" (variacao verbal
no presente do indicativo). O comparador de indicadores e literal
(secao 2.5 do TCC), entao variacoes morfologicas nao cadastradas nao
sao reconhecidas.

## Acao futura
Documentado como exemplo real de limitacao do sistema (capitulo 6.3
do TCC). Sera avaliado se a base de conhecimento devera incluir mais
variacoes verbais/morfologicas dos indicadores tecnicos, ou se este
tipo de caso sera tratado apenas na revisao manual (Requisito RF5).

## Atualizacao (classificador v1.3, base v1.1)
O stemming (v1.1) nao resolveu este caso: o RSLP gera radicais
diferentes para "cai" e "caiu" (ver docs/decisao_stemming.md). A base
v1.1 passou a cadastrar "servidor cai", e o review 3 agora e
classificado como Misto (R3).

A correcao da dupla contagem da v1.2 so funcionava quando o indicador
casado literalmente vinha antes, na base, do indicador casado via
radical. No caso inverso o escore era somado duas vezes (ex: "fechando
sozinho" dava escore 6, "muitos bugs" dava 2, "travamento" dava 4). A
v1.3 roda o casamento literal para todos os indicadores antes do
casamento por radical e conta cada radical uma unica vez.

Resultado com os 7 reviews de exemplo (base v1.1):
- Tecnico: 2
- Afetivo-visual: 2
- Misto: 1
- Indefinido: 2

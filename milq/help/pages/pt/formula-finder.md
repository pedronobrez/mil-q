---
title: Localizador de fórmulas
---
A aba **Formula finder** (localizador de fórmulas) responde ao inverso da
[[mass-calculator]]: dado um m/z medido, que composições elementares
poderiam produzi-lo? Ela é aberta clicando com o botão direito em um pico do
espectro e escolhendo **Find formula for this peak**, por **Send m/z to
formula finder** na calculadora de massas, ou digitando um m/z.

## Entradas

| Campo | Significado |
|---|---|
| m/z e aduto | o íon medido e como foi formado; a massa neutra é o que a busca usa |
| tolerância, ppm ou Da | quão longe um candidato pode estar da medida; 10 ppm para começar |
| faixa de RDBE | equivalentes de anéis e duplas ligações permitidos, −0.5 a 40 por padrão |
| **Even-electron only** | manter as composições cujo RDBE é um número inteiro mais meio — os íons de camada fechada que a eletronebulização produz; íons radicalares têm RDBE inteiro |
| **Apply element-ratio rules** | as faixas heurísticas de H/C, O/C, N/C e assim por diante dentro das quais moléculas reais se mantêm — as "sete regras de ouro" |
| **Rank by isotope pattern** | pontuar cada candidato contra os satélites isotópicos do espectro em tela |
| Faixas de elementos | a contagem mínima e máxima de cada elemento considerado |

## Resultados

Uma linha por composição: fórmula, m/z, erro em mDa e em ppm, RDBE e a
pontuação isotópica. A massa exata sozinha raramente separa candidatos acima
de algumas centenas de daltons; as alturas relativas de M+1 e M+2
normalmente separam, e é por isso que a pontuação isotópica existe e por que
a tabela é ordenada por ela quando está ligada.

## A pontuação isotópica precisa de uma varredura de survey

A pontuação compara os picos satélites do espectro com o padrão que cada
fórmula prevê. Uma varredura de íons produto não tem satélites a comparar —
o Q1 isolou o precursor monoisotópico antes da fragmentação — portanto rode
o localizador sobre um pico do canal de survey TOF MS. O painel verifica de
que canal veio o espectro e diz isso em vez de reportar pontuações sem
sentido.

## Quando o localizador é a ferramenta errada

Para lipídios, um banco de dados é uma primeira pergunta melhor do que uma
busca sobre composições: a aba [[lipid-maps]] responde "qual lipídio
conhecido tem esta massa" com estruturas anexadas, e a página
[[accurate-precursor]] explica como a massa sobre a qual perguntar é medida
a partir da varredura de survey em vez de lida do método.

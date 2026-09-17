---
title: Princípios de projeto
---
Algumas poucas regras decidiram o que este programa faz quando duas coisas boas
não podiam ser ambas obtidas. Elas saíram do trabalho — a maioria delas de um
erro — e conhecê-las explica as escolhas que um leitor vai encontrar.

## Medir antes de afirmar

Cada número de desempenho e de fidelidade neste manual foi produzido executando
algo, não lendo código. Foram feitas duas tentativas de engenharia reversa de um
algoritmo do fornecedor e ambas estavam erradas; a segunda parecia certa até ser
testada em dados aos quais não havia sido ajustada. Veja [[measured-facts]].

## Uma diferença declarada é melhor que uma regra inventada

Onde o comportamento não pôde ser reproduzido fielmente, a versão simples é
distribuída com a lacuna medida escrita — a regra de extração em [[formats]] é o
exemplo. Um número que é 0.58% mais baixo e o diz vale mais que um que às vezes
está certo por razões que ninguém consegue enunciar.

## Nunca substituir a aritmética do instrumento pela deste programa

Totais, tempos de retenção e áreas vêm do fornecedor onde o fornecedor os
reporta. Somar os pontos armazenados em vez disso moveu cada área em 2%.

## Dizer o que não pôde ser feito

Um critério que não pôde ser avaliado não é um critério que passou. Um ruído que
não pôde ser medido não é uma contagem. Um ajuste que não pôde ser feito não é
um trapézio sob o nome do ajuste. Um carryover sem um branco no lugar certo não
é um número tirado do branco mais próximo. Em todos os casos a linha o diz —
[[signal-to-noise]], [[integration-algorithms]],
[[detection-limits-and-carryover]] — e o [[report]] imprime a razão onde de
outro modo uma tabela ficaria vazia.

## Uma sinalização que dispara em todo lote não é lida em nenhum

As regras de QC carregam duas condições cada uma — estatisticamente incomum
**e** praticamente diferente — porque cada uma isoladamente sinalizava injeções
ordinárias em corridas reais. Veja [[batch-qc]].

## A confiança é medida, não afirmada

Uma proposta feita a partir dos dados carrega a exatidão que o mesmo estimador
alcançou nas partes do lote em que a resposta já era conhecida. Quando ele não
se provou, nada vem pré-marcado. Veja [[suggest-from-data]].

## Uma política que ninguém consegue revisar não é uma política

Quando o programa decide algo que um leitor poderia ter decidido de outro modo —
proximidade em vez de tamanho, um ajuste em vez de um trapézio, uma exclusão — a
linha diz o que ele fez e o que preteriu.

## Nada muda os números de um projeto salvo por surpresa

Cada configuração nova assume por padrão o que o programa fazia antes de ela
existir: pico *largest*, integração *valley*. Um lote reaberto em uma versão mais
nova reporta o que reportava, e o [[version-history]] diz qual versão trouxe
cada uma delas.

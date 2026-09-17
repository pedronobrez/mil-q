---
title: Comparar infusões
---
A bandeja de padrões é infundida de novo — um frasco novo, um solvente novo,
o instrumento de volta da manutenção — e a pergunta é se os espectros são os
da última vez. **Compare infusions…** na aba Infusions do
[[analytics-workspace]] a responde: um projeto de referência contra as
infusões que estão abertas, composto a composto e condição a condição.

É o [[compare-batches]] para o outro tipo de lote. Onde aquele põe duas
corridas cromatográficas de um método lado a lado, este põe dois dias de
[[direct-infusion]] lado a lado, e faz as perguntas que o
[[standard-history]] faz de uma biblioteca — com as mesmas regras, para que
*moved* signifique uma coisa neste programa e não duas.

## A referência

Um arquivo de projeto, `.oqproj`. Ele é lido pelo resumo de infusões que
salvou e nenhum arquivo bruto é aberto, de modo que uma referência cujas
aquisições foram para outro disco continua sendo uma referência.

Para isso o projeto de referência precisa *conter* um resumo. Pressione
**Measure** na aba Infusions antes de salvá-lo e o projeto leva o que a
tabela mostrou — e, para cada linha, a lista de picos média e centroidada,
no piso e no teto com que um registro seu é escrito ([[spectral-library]]:
picos acima de um por cento do pico base, no máximo duzentos deles, com a
altura do pico base em contagens ao lado). Um projeto salvo sem medir não
tem nada com que comparar e diz isso, em vez de mostrar uma tabela vazia.

Os picos são o que o arquivo paga. Medido em três infusões reais de ácido
cólico-d4 — 12, 41 e 179 picos guardados — o projeto passou de 1.965 para
8.645 bytes: 19,4 bytes por pico, de modo que uma linha com os duzentos
completos custa cerca de 4 kB. Ler um de volta leva 3 ms.

## A correspondência

Uma linha é emparelhada com a linha da referência do **mesmo composto e das
mesmas condições**: a mesma ativação, e uma energia de colisão dentro de
meio elétron-volt. Uma infusão a 22 eV EAD é comparada com a de 22 eV EAD da
referência e nunca com a de 12 eV, pela razão que leva o
[[standard-history]] a cortar um histórico em séries — um espectro medido em
outra energia tem outros fragmentos, e pontuar entre energias mede o método
e não o padrão. O que o outro dia não tem é listado como presente apenas
aqui ou apenas lá.

O composto, e a ativação onde só o nome do arquivo a declara, são lidos do
**nome do arquivo em disco** e não do nome abreviado da amostra nas tabelas.
O nome abreviado é o que todas as amostras abertas têm em comum retirado da
frente, o que significa que ele muda conforme o que mais está aberto: a
mesma aquisição lida como *EAD…* ao lado de outras duas infusões de ácido
cólico e como *12CE…* ao lado de uma, e nada correspondia a nada até que o
nome do arquivo fosse usado.

## O que é comparado

| Coluna | Significado |
|---|---|
| Score, Reverse | o cosseno dos picos deste dia contra os picos guardados da referência, e o cosseno apenas sobre os picos da referência — um reverso alto com um escore baixo é tudo o que havia mais alguma coisa nova |
| Matched | quantos dos picos da referência foram encontrados |
| Base m/z ref., now, Base Δ ppm | onde está o pico base, e quanto ele se moveu. É o mais forte dos picos *guardados*, que é um centroide: pode ficar alguns milésimos do pico base que a aba Infusions lê do traço em perfil, e é o único contra o qual uma referência lida de volta de um arquivo ainda poderia ser conferida |
| Height ref., now, Δ height % | o pico base em contagens, e a mudança — o número que um registro de biblioteca não consegue guardar e o que diz se o padrão ainda dá o que dava |
| Ions ref., now | os íons que uma fórmula encontrou dos que previu, em cada dia; veja [[infusion-report]] |
| Δ precursor ppm | a mudança no erro do precursor contra o que o método escreveu ([[accurate-precursor]]) |
| Δ record score | a mudança no escore do melhor registro da sua própria biblioteca |

## A marca

Uma linha é marcada como *moved* por duas regras, ambas emprestadas:

- **o pico base está a mais de 50 ppm do da referência.** Isso não é um erro
  de massa, é um íon diferente — o número do `standard_history`, e a
  distinção para a qual ele existe.
- **sua altura está a mais de 20% da da referência.** O que um gráfico de
  controle daquele padrão apontaria; veja [[batch-qc]] para a origem do
  número.

O escore é relatado e deliberadamente *não* é uma regra. Um histórico julga
um cosseno contra a dispersão da sua própria série, e dois dias são dois
pontos, o que não é uma dispersão.

## Medido

Duas das aquisições reais contra três do dia anterior, todas de ácido
cólico-d4: duas linhas corresponderam a 12 e 22 eV EAD, e a terceira
infusão — 45 eV, sem ativação declarada no nome — ficou apenas na
referência. As duas linhas correspondidas se moveram.
O pico base tinha passado de 430,3488 e 377,3015 para 839,2316 e 839,2343 —
950.000 e 1.224.000 ppm de distância, o que é um precursor diferente e não
uma deriva — a 0,9% e 2,4% da altura da referência, e os cossenos foram 0 de
12 e 7 de 41 picos correspondidos, pontuando 0,0 e 8,6. Os mesmos arquivos
reabertos contra si mesmos pontuam 100,0, 0,0000 ppm e uma razão de 1,0000
em cada linha, que é o piso da medida, e a comparação em si leva 6 ms.

**Export CSV…** escreve cada linha e as duas listas de sobras, e enquanto a
comparação se sustenta o [[report]] a carrega como uma seção *Infusion
comparison*.

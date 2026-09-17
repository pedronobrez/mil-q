---
title: Comparar lotes
---
No dia em que o agendamento de [[acquisition-schedule]] é executado, a pergunta
é se ele ajudou. **Compare batches…** na barra de ferramentas da
[[analytics-workspace]] a responde: um projeto de referência contra o lote que
está aberto, componente a componente, nas coisas que a mudança deveria mover.

## A referência

Um arquivo de projeto, `.oqproj`. Ele é lido pelo que salvou — o método, as
amostras, os resultados — e nenhum arquivo bruto é aberto, de modo que uma
referência cujas aquisições foram para outro disco continua sendo uma
referência. O lote aberto é o lado atual.

Os componentes são correspondidos por nome entre os dois métodos. Um componente
presente em um método e não no outro é listado como existente apenas ali, e um
padrão acrescentado desde então é comparado como um analito no lado que não o
tinha.

## O que é comparado

| Coluna | Significado |
|---|---|
| Found ref., Found now | linhas com um pico, de cada lado |
| Points ref., Points now | o número mediano de pontos no pico — iguais ou acima de um por cento de sua altura — que é o que um novo agendamento deve elevar; veja a aba *Sampling* do [[batch-qc]] |
| %CV ref., %CV now | a dispersão sobre as linhas que deveriam concordar — cada injeção fortificada para um padrão interno, os controles de qualidade para um analito — que é o que mais pontos devem baixar |
| Area ref., Area now, Δ area % | a área mediana de cada lado, e a mudança; um componente acima de 20% é marcado, já que um novo agendamento que muda o *nível* de uma resposta e não apenas sua precisão é algo que vale a pena saber |
| RT ref., RT now, ΔRT | o tempo de retenção mediano de cada lado, e o deslocamento — uma coluna que envelheceu, ou um gradiente que mudou |

Os totais acima da tabela dão os mesmos quatro números sobre o método inteiro,
lado a lado. **Export CSV…** escreve cada linha, e enquanto a comparação se
sustenta o [[report]] a carrega como uma seção *Batch comparison* — o documento
para levar à reunião depois da corrida agendada.

## Lendo a comparação

A comparação diz o que se moveu; não diz por quê. Um lote que encontrou mais
linhas pode ter tido uma janela mais larga ou uma aquisição melhor; um %CV que
caiu pode ser mais pontos no pico ou um preparo melhor. O que ela de fato
resolve é se a mudança fez alguma diferença, e em quais componentes — que é a
pergunta que um agendamento, uma edição de método ou uma coluna nova coloca, e
aquela que um único lote não consegue responder sobre si mesmo.

O mesmo formato de [[compare-algorithms]], que põe três algoritmos lado a lado
em um lote; esta põe dois lotes lado a lado em um método. Uma bandeja de
padrões infundidos é um lote de outro tipo, e o [[compare-infusions]] põe dois
dias desses lado a lado — correspondidos por composto e por energia de colisão,
e pontuados sobre os espectros em vez das áreas.

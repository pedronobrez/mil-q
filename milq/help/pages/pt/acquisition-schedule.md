---
title: Agendamento de aquisição
---
A aba *Sampling* (Amostragem) do [[batch-qc]] pode dizer que um lote colocou um
ponto em cada pico e de que tempo de ciclo os picos precisariam. Dizê-lo não é o
mesmo que corrigi-lo. A correção é uma **aquisição agendada** — cada transição
adquirida apenas em torno de seu tempo de retenção, de modo que o ciclo do
instrumento seja repartido entre menos transições a cada momento e cada uma
receba mais dele — e o software do instrumento recebe isso como uma tabela.
**Export schedule…** no [[method-workspace]] constrói a tabela a partir do
método e diz, antes de ela ser salva, o que um ciclo alvo deixaria para cada
transição.

## O que há nela

Cada componente com tempo de retenção, adquirido ao longo de sua janela
(RT ± meia-largura) — a mesma janela que a integração usa, e aquela que
[[suggest-from-data]] alarga até o que a amostragem consegue resolver.
Componentes sem tempo de retenção não podem ser agendados e são listados como
deixados de fora.

| Coluna | Significado |
|---|---|
| ID, Group | o componente e seu grupo |
| Q1 (Da), Q3 (Da) | precursor e fragmento; um componente sem fragmento é escrito com seu precursor em ambos |
| RT (min) | o tempo de retenção esperado |
| Window start, Window end (min) | quando a transição é adquirida |
| Dwell (ms) | o que o ciclo alvo deixa a cada transição no momento mais ocupado |
| Internal standard | `yes` nos padrões |

## A aritmética

A cada momento o instrumento percorre em ciclo as transições cujas janelas
contêm aquele momento, gastando um **dwell time** em cada uma e uma **pausa**
ao mover-se entre elas, de modo que o tempo de ciclo é a contagem do momento
mais ocupado × (dwell + pausa). Dado um **ciclo alvo**, o dwell decorre daí;
dado um **piso de dwell** — o menor dwell que vale a pena adquirir, já que
abaixo dele a estatística de contagem de uma transição é pior que o pico que
ela mede — decorre também o menor ciclo que o momento mais ocupado permite.

O diálogo mostra o momento mais ocupado (quantas ao mesmo tempo, e quando), o
dwell que o alvo deixa e, quando este está abaixo do piso, o ciclo que
efetivamente pode ser alcançado e o que o mudaria: estreitar as janelas onde
elas se sobrepõem, ou descartar transições. O dwell escrito é o do momento mais
ocupado, igual para todas as linhas — uma transição adquirida sozinha poderia
ter mais, mas um agendamento que varia o dwell por momento não é aceito pelo
software do instrumento.

## O ciclo alvo

Pré-preenchido a partir do que o lote mediu: três pontos nos flancos do pico —
o mínimo de que um ajuste gaussiano precisa, em qualquer fase dos scans — para
picos da largura mediana que o relatório de amostragem encontrou. Quando a
maior parte dos picos do lote era mais estreita que um ciclo, essa largura é um
limite superior sobre os mais largos e o ciclo que dela decorre é um **limite
superior**; o diálogo o diz, porque o número vai ser digitado em um
instrumento. Digite um menor, ou o correspondente a dez pontos ao longo da
base, conforme o método exigir.

## Depois

Quando o lote agendado tiver corrido, [[compare-batches]] o coloca contra
aquele que ele deveria melhorar: pontos no pico, %CV das réplicas, linhas
encontradas, e para onde os picos se moveram.

## O que o arquivo não é

Um CSV simples cujas colunas são nomeadas de modo que uma planilha mapeie na
tabela do fornecedor. Não se afirma que ele importe diretamente no Analyst ou
no SCIEX OS, e nenhuma sobrecarga específica do instrumento é modelada além da
pausa. No Analyst a janela de detecção é uma única configuração válida para
todo o método, em vez de uma coluna: a janela mais larga aqui é a que se deve
digitar. Os [[design-principles]] dizem por que uma diferença declarada é
melhor que um formato de importação inventado.

As figuras — transições com tempo, o momento mais cheio, o dwell que o ciclo
alvo deixa — são também uma seção do [[method-report]], ao lado de tudo o
mais que se pode ler do método antes de ele ser executado.

## A outra metade da aquisição

Esta página decide *quando* cada transição é adquirida. Em *que* ela é
adquirida — em qual energia de colisão, e sob qual ativação — é a mesma
pergunta feita às infusões em vez de à separação, e a [[collision-energy]]
a responde a partir dos padrões que foram de fato borrifados.

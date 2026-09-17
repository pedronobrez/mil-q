---
title: Comparar algoritmos
---
Uma área de pico é uma medição e uma decisão: onde o pico começa e termina, e o
que se faz com os pontos entre esses limites. Se o número se move com a decisão,
o tamanho desse movimento é parte do resultado. **Compare algorithms…** na barra
de ferramentas da [[analytics-workspace]] o mede.

## O que faz

O lote é integrado uma vez com cada um dos três [[integration-algorithms]], cada
execução automática — uma linha que o operador integrou à mão não é a resposta
de algoritmo nenhum — e cada execução calibrada sobre seus próprios resultados,
de modo que o r² de uma curva seja daquele algoritmo. A referência é o algoritmo
que os padrões do método nomeiam, que é aquele com que o lote está atualmente
sendo reportado. Um diálogo de progresso percorre os três; no lote para o qual
isto foi escrito, 3,666 linhas de três maneiras levaram menos de quatro
segundos.

A comparação das execuções, depois, é indexada e não pesquisada. As linhas de
cada componente eram filtradas do conjunto inteiro de resultados, e a linha
correspondente em outra execução era encontrada percorrendo aquela execução
desde o início — por linha, por componente, por algoritmo. Em 3.666 linhas
essas duas buscas medem **0,010 s e 0,106 s** percorrendo contra **0,0002 s e
0,0031 s** indexadas, e crescem com o quadrado do lote: dobrar para 7.332
linhas leva o percurso a 0,032 s e 0,518 s enquanto o índice não se move. Os
números reportados são os mesmos de um jeito ou de outro; o que muda é quanto
um lote grande espera por eles.

## O diálogo

**Summary.** Um parágrafo: linhas encontradas por cada algoritmo, quantas
recaíram sobre a área do vale e por quê, o %CV mediano de cada um sobre os
componentes com réplicas, e quantos componentes se moveram mais de 20%.

**Component table.** Uma linha por componente:

| Coluna | Significado |
|---|---|
| Found | linhas com um pico, por algoritmo; para o ajuste, quantas recaíram |
| Δ median % | a mediana, sobre as linhas que ambos os algoritmos encontraram, de \|área − área de referência\| / área de referência; um componente acima de **20%** é marcado, já que seu número depende tanto da decisão quanto da amostra |
| Δ max % | a maior diferença desse tipo |
| %CV | o coeficiente de variação das áreas de cada algoritmo sobre as linhas que deveriam concordar |
| Note | linhas encontradas apenas pela referência, ou apenas pelo outro algoritmo |

**%CV** é o único número que pode chamar um algoritmo de *melhor* em vez de
meramente *diferente*: mesmos arquivos, mesmo ruído, mesmo instrumento, apenas a
aritmética mudou. As linhas que deveriam concordar são cada injeção fortificada
para um padrão interno — fortificado em cada frasco numa única quantidade — e os
controles de qualidade para um analito; desconhecidos diferem por projeto e
padrões por construção, de modo que nenhum dos dois diz nada sobre precisão. Um
componente com menos de três réplicas não mostra %CV.

**One sample, every way.** Selecione um componente, depois uma amostra: o traço
é desenhado com a integração de cada algoritmo sobre ele — os limites e a linha
de base de cada um em sua própria cor, a área sombreada de cada um, a curva
ajustada onde houve uma, com sua área e *exact through 3 points* ou seu r² na
legenda. Um número que diz que dois algoritmos discordam em setenta por cento é
apenas o começo; isto é o que mostra qual deles está olhando para o pico.

**Adopt and reprocess.** Coloca o lote sobre o algoritmo escolhido — tanto os
padrões do método quanto cada sobreposição de componente, de modo que um
componente que carrega suas próprias configurações não guarde o algoritmo antigo
em silêncio — e integra o lote novamente com ele. Linhas integradas à mão são
mantidas.

## O que a comparação disse em um lote real

| Algoritmo | Linhas encontradas | Recaíram | Moveram > 20% | %CV mediano |
|---|---|---|---|---|
| Valley to valley | 2,638 | — | — | 87.7 |
| Summation over the window | 857 | — | 8 | 92.6 |
| Gaussian fit | 2,638 | 2,238 (2,169 com pontos insuficientes) | 0 | 88.2 |

Onde o ajuste pôde ser feito, ele concordou com o trapézio — mediana de 0.977
dele — e nenhum componente se moveu mais de 20%; onde não pôde, o pico tinha um
ou dois pontos de largura. A somatória perdeu linhas, porque 85 componentes não
tinham janela e porque uma janela cujas extremidades caem nos flancos de um pico
não tem nada acima da reta entre elas. O algoritmo não moveu os números daquele
lote; a amostragem moveu — e a comparação é o que diz isso com números. Veja
[[measured-facts]].

## No relatório

Quando uma comparação foi executada, o [[report]] carrega uma seção *Integration
algorithms* com a tabela de totais e os componentes que mais se moveram. A
comparação não é salva no projeto — são três integrações do lote inteiro e é
reconstruída sob demanda.

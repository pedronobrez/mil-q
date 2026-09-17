---
title: A área de trabalho Analytics
---
A área de trabalho Analytics (Ctrl+2) é o lote, quantitativamente: cada
componente em cada amostra, a integração de cada um, as curvas, as estatísticas
e a qualidade da corrida. É construída do modo como o MultiQuant é — um
componente escolhido à esquerda, um cromatograma por amostra para ele no meio, e
a tabela por baixo.

## Disposição

**Esquerda.** A árvore de componentes, agrupada pelos grupos do método, com
**All components** no topo; uma caixa de filtro acima dela; e dois painéis
dobráveis abaixo: **Integration** ([[integration-parameters]]) e **Acceptance**
([[acceptance-criteria]]). Os painéis começam dobrados, porque abertos deixam a
árvore com poucas linhas de altura, e se estavam abertos é lembrado.

**Centro.** A grade de [[peak-review]]: um painel por amostra para o componente
selecionado, com a área integrada sombreada.

**Base.** Oito abas: [[results-table|Results]],
[[calibration|Calibration]], [[statistics|Statistics]],
[[metric-plot|Metric plot]], [[batch-qc|Batch QC]], [[mass-drift|Mass drift]],
[[infusion-report|Infusions]] e [[audit-trail|Audit trail]]. As duas últimas
não medem nada antes de serem pedidas — *Infusions* passa a trazer a contagem
de linhas no nome da aba depois que mede, e fica vazia num lote que não tenha
nenhum padrão infundido.

## A barra de ferramentas

| Botão | Efeito |
|---|---|
| **Process batch** | extrai e integra cada componente válido em cada amostra aberta, depois ajusta as curvas, lê as concentrações e pontua os critérios de aceitação. Com resultados já em mãos, lê apenas o que mudou — veja *Processando só o que mudou* abaixo |
| **Reprocess all…** (a seta ao lado de **Process batch**) | cada linha de novo a partir dos arquivos, sem manter nada, inclusive as linhas integradas à mão. Pergunta antes, quando existe alguma |
| **Recalibrate** | reajusta cada curva a partir das amostras marcadas como Standard e lê os desconhecidos de volta a partir delas, sem reintegrar |
| **Compare algorithms…** | integra o lote com todos os algoritmos e coloca as respostas lado a lado — veja [[compare-algorithms]] |
| **Compare batches…** | um projeto de referência contra este lote, componente a componente — veja [[compare-batches]] |
| **Magnify peak** | um painel preenchendo o painel principal; um duplo clique num painel faz o mesmo |

A linha de status à direita relata o que foi feito por último: quantas linhas em
quantas amostras, quantas integradas, qual padrão e qual qualificador o
componente selecionado tem.

## O que o "processamento" faz, em ordem

1. Para cada amostra e componente, o canal é correspondido e o XIC extraído e
   condicionado (suavização, linha de base) com as configurações de integração
   daquele componente.
2. O pico é encontrado e integrado pelo algoritmo do componente — veja
   [[integration-parameters]] e [[integration-algorithms]].
3. As razões de padrão interno e as razões iônicas de qualificador são
   calculadas — depois do lote inteiro, já que o próprio pico de um padrão tem
   de existir antes que algo possa ser dividido por ele.
4. As curvas são ajustadas a partir dos padrões, as concentrações lidas nelas e
   multiplicadas pela diluição de cada amostra, e as exatidões calculadas.
5. Cada linha é pontuada contra seus critérios de aceitação.

Uma mudança nas configurações de integração de um componente reprocessa apenas
aquele componente (ou seu grupo); tudo a jusante — razões, curvas,
concentrações, status — é recalculado a cada vez.

## Processando só o que mudou

Acrescentar uma injeção a um lote de vinte e seis deveria ler uma injeção, e
lê. Cada linha integrada registra uma **impressão digital**: um resumo curto
de tudo o que decide seus números — o precursor, o fragmento, a tolerância, o
tempo de retenção e a janela do componente, os parâmetros de integração de
fato em vigor para ele, e a correção de massa daquela injeção. Quando
**Process batch** é pressionado com resultados já em mãos, a impressão digital
de cada linha é comparada ao que o método diz agora:

| A linha | O que acontece |
|---|---|
| impressão digital inalterada | **mantida**, exatamente como está; o arquivo não é aberto |
| uma injeção nova, ou um componente novo | **integrada** |
| a impressão digital do componente mudou | **integrada** de novo |
| a injeção ou o componente sumiu | **descartada** |

Uma linha mantida não é um palpite. Sua impressão digital diz que ela foi
produzida pela mesma aritmética que uma execução completa produziria agora, e
é por isso que o conjunto inteiro volta idêntico, linha por linha e campo por
campo, ao que processar o lote do zero dá. O que *não* entra na impressão
digital é tudo o que não muda um número: renomear uma injeção ou reagrupar um
componente é escrito nas linhas mantidas em vez de comprado com uma segunda
leitura.

**Linhas integradas à mão são mantidas como estão** enquanto a impressão
digital do componente delas vale — é para isso que se desenha uma fronteira.
Quando os parâmetros do componente mudam, elas são integradas de novo, e tanto
a linha de status quanto a [[audit-trail]] dizem quantas: uma fronteira
desenhada sobre um traço não é uma decisão sobre uma janela de massa
diferente, e deixá-la ali relataria um pico que ninguém escolheu.

Medido no lote real de 26 injeções e 141 componentes — 3.666 linhas:

| | |
|---|---|
| processar o lote inteiro | **2,4 s** com os arquivos no cache do sistema operacional; 12 s na primeira vez, a frio |
| uma injeção acrescentada: 3.525 mantidas, 141 integradas | **0,06 s** — 39 vezes mais rápido |
| a janela de um componente alargada: 3.640 mantidas, 26 integradas | **0,03 s** |
| nada mudou: 3.666 mantidas, 0 integradas | **0,02 s** |
| decidir tudo isso, antes de ler qualquer coisa | **menos de 10 ms**, sem abrir arquivo nenhum |

Tudo o que é derivado continua a ser recalculado sobre o conjunto inteiro a
cada vez — razões de padrão interno, razões iônicas, curvas, concentrações,
aceitação e os gráficos de qualidade. Isso é aritmética sobre linhas, e não
leitura de arquivos, e custa cerca de 50 ms ao todo neste lote.

Três coisas que ele deliberadamente não faz. Uma mudança em um **padrão do
método** alcança todo componente que o herda, de modo que quase nada pode ser
mantido e a execução volta a processar o lote inteiro — a linha do registro
então diz *Batch processed* e não *Batch reprocessed*. Uma linha escrita por
uma versão anterior às impressões digitais não registra nada, então é
integrada de novo; uma execução completa dá ao projeto inteiro suas impressões
digitais e toda execução depois dela é incremental. E uma impressão digital
diz que o **método** não mudou — ela não tem como saber se a aquisição por
trás de um caminho foi substituída, que é para isso que existe **Reprocess
all…**.

Uma execução cancelada deixa como estavam as linhas que não alcançou. As
impressões digitais delas já não conferem, então pressionar **Process batch**
de novo termina exatamente o que ficou.

## Vinculação nos dois sentidos

Clicar em um painel da grade seleciona sua linha na tabela de resultados;
selecionar uma linha traz aquele componente na árvore e destaca seu painel;
clicar em um ponto do gráfico de métricas ou em uma linha do Batch QC faz o
mesmo. A tabela de resultados acompanha a árvore: com um componente selecionado
ela mostra as linhas daquele componente, com **All components** mostra tudo.

## Revisando um lote inteiro

**All components** na árvore coloca cada pico de cada componente na grade, uma
página por vez. Extrair todos eles — 141 componentes em 26 amostras — são cerca
de cem segundos de trabalho para pôr nove na tela, de modo que as páginas são
construídas conforme são viradas, em vez de todas de uma vez.

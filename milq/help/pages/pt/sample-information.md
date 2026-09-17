---
title: Informações da amostra
---
A aba **Sample** dos painéis laterais do Explorer lista o que o arquivo de
aquisição registra sobre a amostra selecionada e sobre o canal ativo. É
somente leitura; **Copy all** coloca a árvore inteira na área de transferência
como texto.

## Sample

O que o arquivo declara: o nome da amostra no lote, a posição do frasco, o
volume de injeção, o nome do método de aquisição, a data e hora do lote e da
aquisição e — onde o método os registra — o potencial de desagregação
(declustering potential) e a energia de colisão em uso. O que ele **não**
declara é o papel da amostra: toda injeção em um `.wiff` volta como
`kUnknown`, e é por isso que o tipo de amostra, a concentração e a diluição
ficam guardados na [[samples-workspace]] e são salvos com o projeto.

O tempo de aquisição é o que a página [[batch-qc]] e o eixo de ordem de injeção
do [[metric-plot]] usam para colocar as injeções na ordem em que o instrumento
as executou.

## Active channel

Para o canal selecionado no alto da janela: o índice e o nome, o tipo de
experimento (`TOF MS`, `TOF PI` — uma varredura de íons produto — ou uma
transição MRM), a polaridade, o precursor, a faixa de massa, o número de scans
e a energia de colisão.

Para um mzML, esses campos são os que o conversor conseguiu carregar, e o
próprio canal pode ter sido inferido a partir do ciclo de aquisição em vez de
declarado — ver [[formats]].

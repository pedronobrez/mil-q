---
title: Cromatogramas de íon extraído
---
Um cromatograma de íon extraído (XIC) é a intensidade de uma massa ao longo
da corrida: para cada scan de um canal, a soma dos pontos dentro de uma
janela de massa. Há quatro maneiras de pedir um.

## A aba Manual XIC

Digite uma ou mais massas, separadas por vírgula (`183.1391, 313.2384`), uma
tolerância e a sua unidade — Da ou ppm — e **Extract XIC**. Cada massa vira
um traço no cromatograma, extraído do canal ativo, ou de todos os canais
marcados com **Extract from every checked channel** assinalado. A lista
**Active XICs** os nomeia; selecione um e pressione Delete para removê-lo, ou
**Clear XICs** para remover todos.

## A partir do espectro

Shift+arrastar sobre uma faixa de m/z no painel do espectro, depois clique
direito e **Extract XIC from selection**: a janela é exatamente a faixa
selecionada.

## A partir da lista de picos

Duplo clique em uma linha da aba **Spectrum peaks** para extrair a massa
daquele pico com a tolerância definida na aba Manual XIC.

## A partir de um componente

Duplo clique em uma linha da aba **Components** para desenhar o XIC daquele
componente em todas as amostras marcadas, no seu próprio canal, com a sua
própria janela de massa. Ver [[explorer-components-and-results]].

## A janela de massa

A janela é `m/z ± tolerance`. Em ppm, a meia largura é `m/z × ppm / 10⁶`,
de modo que 20 ppm em 313.24 são ±6.3 mDa. A janela soma os pontos **dentro**
dela; a extração da própria SCIEX também conta parte de um pico cujos pontos
caem logo fora, o que é a única diferença medida entre este programa e o do
fabricante — uma mediana de 0.58% da altura do pico, no máximo 12%, sempre
menor aqui. Ver [[formats]] e [[measured-facts]].

## Qual canal

Um XIC vive em um só canal. A partir da aba Manual XIC esse é o canal ativo;
a partir de um componente é o canal que [[method-workspace|the method]] (o
método) associa ao componente — pelo precursor, por o canal ter sido
adquirido no tempo de retenção esperado, e por a sua faixa de massas conter
o alvo. Um método agendado pode carregar o mesmo precursor em dois períodos,
e é por isso que o tempo faz parte da associação.

## Por onde o traço passa

A suavização e a remoção de linha de base da barra de ferramentas Processing
se aplicam a um XIC como a qualquer outro traço, e o mesmo vale para
*Normalise*, *Mirror*, *Stack* e *Cascade*. **Detect peaks** o integra como a
qualquer outro traço.

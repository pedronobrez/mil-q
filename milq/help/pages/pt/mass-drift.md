---
title: Deriva de massa
---
A aba **Mass drift** da [[analytics-workspace]] pergunta se o eixo de massas
se moveu durante a corrida. Nada é medido até que **Measure** seja
pressionado: ler o espectro de survey de cada padrão interno em cada injeção
é um minuto de trabalho em um lote real, e uma aba que fizesse isso a cada
alteração dos resultados seria uma aba que ninguém deixaria aberta.

## O que é medido

Para cada padrão interno — ele está em todo frasco em uma única quantidade,
de modo que o seu íon está lá para ser medido em cada injeção — a massa do
precursor é lida da varredura de survey no tempo em que a transição do
próprio padrão atinge o ápice, exatamente como a página
[[accurate-precursor]] descreve, uma vez por injeção em vez de uma vez por
lote. As injeções ficam na ordem em que o instrumento as rodou, a partir dos
seus tempos de aquisição.

A referência é **a mediana do próprio lote**, não o precursor escrito: um
valor de método digitado com duas casas decimais é bom até ±14 ppm em m/z
350 e não diz nada sobre deriva, ao passo que uma mudança ao longo da
corrida é medida contra si mesma com folga abaixo de um ppm. Onde o
componente carrega uma fórmula e um aduto, a massa exata também é conhecida,
e o **erro** da mediana contra ela é reportado — um deslocamento, que é um
achado diferente de uma deriva.

## O que a tabela diz

| Coluna | Significado |
|---|---|
| n | injeções em que o survey encontrou o íon |
| Median m/z | a massa medida, mediana ao longo da corrida |
| Exact m/z, Error ppm | a partir da fórmula e do aduto, quando o componente os tem, e quão longe a mediana está dela |
| Spread ppm | a maior diferença entre injeções |
| Change ppm | a mudança ao longo de toda a corrida, a partir de uma reta ajustada às medidas |
| ρ | a correlação de Spearman da medida com a ordem de injeção: quão monotônica foi a mudança |
| Verdict | *drift +12.3 ppm*, *steady*, ou por que não pôde ser julgada |

Antes de qualquer disso, as injeções têm de ter medido **o mesmo íon**. Em
um lote real, os padrões internos cujo sinal de survey era fraco voltaram com
dispersões de 100 a 500 ppm entre injeções, e um deles com uma "deriva"
ajustada de −351 ppm — a janela de busca pegando o que estivesse mais perto
em cada injeção, não um eixo se movendo. Uma dispersão acima de 25 ppm, o
limite que o consenso de [[accurate-precursor]] já usa para dizer que as
amostras discordam, torna o componente *not measurable* e o veredito diz por
quê. Só os padrões que passam por isso entram no índice.

Um componente é chamado de **drifting** quando a mudança ajustada é de pelo
menos 10 ppm **e** vai num só sentido (ρ além de 0.5) — as duas condições,
como para uma resposta na página [[batch-qc]]: uma grande mudança ajustada
através de dispersão é uma reta ajustada ao ruído, e uma correlação forte
sobre dois ppm é uma tendência para a qual ninguém recalibra. Menos de seis
injeções não conseguem mostrar uma tendência, e o veredito diz isso.

## O índice de massa do instrumento

Um componente andando é um composto; todos os componentes andando juntos são
o eixo. O índice toma, por injeção, a mediana sobre os padrões do desvio de
cada um em relação à sua própria mediana, e traça a carta sob as mesmas
regras. Ele precisa de pelo menos três padrões medidos em uma injeção para
que aquela injeção conte. É listado primeiro, porque é nele que uma deriva
do instrumento aparece.

## A carta

O desvio do componente selecionado em ppm contra a ordem de injeção, a
mediana como linha cheia e ±10 ppm tracejados, a mudança ajustada como uma
tendência tracejada. Um ponto além de ±10 ppm é desenhado na cor de aviso;
clicar em um seleciona aquela amostra na grade de [[peak-review]].

## Medido, e corrigido só a pedido

Esta página reporta; por si só ela não muda massa nenhuma. O que fazer com
o que ela mostra é [[mass-recalibration]], cujo interruptor fica nesta mesma
aba: ela reutiliza exatamente estas medidas, de modo que um padrão que
falhou o teste de mesmo íon aqui também não é lock mass lá. E o caminho
inverso também vale: um padrão cujas medidas ficam a mais de 50 ppm da sua
própria fórmula na maioria das injeções não é o íon que a fórmula nomeia, e a
coluna Verdict aqui diz isso — uma verificação que o teste de mesmo íon não
consegue fazer, já que ele só pergunta às injeções se elas concordam entre
si. Uma medida que a
varredura de íons produto não confirmou é mantida e contada — uma deriva é
uma deriva quer o scan confirmatório fosse forte o bastante quer não — e a
contagem está na linha.

A medida não é salva com o projeto; é um minuto para repetir. Enquanto ela
vale, o [[report]] carrega uma seção *Mass drift* com a mesma tabela.

---
title: Batch QC
---
A revisão amostra por amostra não consegue ver uma resposta que se desfaz ao
longo de noventa injeções: cada ponto está dentro de seus limites e o lote
continua não sendo o lote com que começou. A aba **Batch QC** da
[[analytics-workspace]] olha a corrida como corrida — os padrões internos contra
a ordem em que o instrumento injetou, as injeções tomadas em conjunto, e a
precisão dos controles de qualidade.

## Ordem de injeção

A ordem vem dos tempos de aquisição que os arquivos carregam; onde alguns não
carregam nenhum, a aba o diz e recai sobre a ordem em que os arquivos foram
abertos, que costuma ser a mesma ordem. Um lote com menos de seis injeções não
consegue dizer como é o normal, e a aba também diz isso.

## Cartas de controle

Uma carta por padrão interno: sua área em cada injeção fortificada — Unknowns,
Standards, Quality Controls e Blanks; não brancos duplos nem injeções de
solvente, que nunca viram o padrão e colocariam dois zeros no meio da corrida —
contra a ordem de injeção, no padrão de uma carta de Levey–Jennings.

**O centro é a mediana e a dispersão é o desvio absoluto mediano**, escalado
para um desvio padrão, de modo que uma injeção ruim não possa alargar os limites
destinados a apanhá-la. Então:

| Veredito | Condição |
|---|---|
| warned | além de 2σ **e** ao menos 10% do centro |
| out | além de 3σ **e** ao menos 20% do centro — ou ao menos 50% dele por menor que seja a dispersão |
| drifted | a mudança ajustada ao longo de toda a corrida é ao menos 20% do centro **e** vai num só sentido: ρ de Spearman além de 0.5 |
| unusable | um terço ou mais da carta está out |

As duas condições de cada veredito foram aprendidas em lotes reais. Um lote que
se repete bem tem uma dispersão tão pequena que três dela é uma diferença sobre
a qual ninguém agiria: medido em uma corrida, um desvio absoluto mediano de 0.8%
transformou um padrão 2.4% abaixo — uma injeção ordinária — em um outlier de
quatro sigma, e teria feito o mesmo em quase todo lote. A regra dos 50% é o
espelho: um lote cuja própria dispersão é ampla engole uma falha real, e uma
injeção em que todos os padrões voltaram a um quinto do normal ficou em 2.6σ. E
quando dezessete de vinte e seis injeções estão out, listar dezessete outliers
perde o que elas dizem em conjunto, que é que nada pode ser normalizado contra
esse padrão — de modo que a carta é reportada como inutilizável, em vez das
injeções.

Um padrão cujo sinal/ruído mediano está abaixo de 10 é plotado mas não
sinalizado: abaixo do limite de quantificação uma pequena mudança absoluta é uma
grande mudança relativa, e cada sinalização contra ele seria aritmética sobre
ruído. No lote para o qual isto foi escrito, oito de onze padrões tinham uma
resposta mediana entre 4 e 52 contagens e produziram quase todas as
sinalizações da corrida. Se essa comporta faz o que diz depende de o ruído ser
mensurável — veja [[signal-to-noise]] — razão pela qual um **piso de resposta
declarado no método** a substitui: um padrão com uma **Min. response** é
utilizável quando sua mediana supera o piso, e não de outro modo; o veredito diz
*below its floor of 100*, e em uma carta utilizável as injeções que ficaram
abaixo do piso são listadas. Veja [[internal-standards-and-qualifiers]].

## O índice de resposta da injeção

A carta de um padrão não consegue distinguir uma injeção que falhou de um
composto que se comportou mal: ambos são um ponto longe do centro. O índice
divide cada padrão interno por sua própria mediana e toma a mediana dessas por
injeção, de modo que todos-os-padrões-caídos-juntos é separável de
um-padrão-caído-sozinho. Ele precisa de ao menos três padrões para ser uma
mediana, e é plotado sob seu próprio nome com as mesmas regras.

No lote para o qual foi escrito, os padrões tomados separadamente dispersavam
entre 32% e 228% e pareciam sem esperança; tomados em conjunto as injeções
ficaram dentro de ±18% com três exceções, uma delas em 0.08, onde todos os
padrões haviam caído de uma vez.

## Controles

| Controle | Efeito |
|---|---|
| **Component** | qual carta é desenhada; a tabela abaixo lista cada carta com seu centro, dispersão, deriva e veredito, e clicar numa linha a desenha |
| **Recheck** | recalcular a partir dos resultados atuais |
| **Exclude failed injections** | desmarca cada linha de cada injeção que o índice aponta, marcando cada uma com a razão; habilitado apenas quando há alguma, confirmado antes, e linhas integradas à mão são deixadas em paz — alguém olhou para aquelas |
| clicar num ponto | seleciona aquela amostra na grade de [[peak-review]] |

## Precisão

A segunda aba: para cada componente, o %CV de sua resposta sobre os controles de
qualidade — apenas controles de qualidade, já que desconhecidos diferem por
projeto e padrões por construção — contra um limite de 15%, a partir de ao menos
três réplicas. Um componente com menos o diz.

## Sampling

A terceira aba mede a única coisa em que três outros achados não paravam de
esbarrar: quantos pontos a aquisição pôs em cada pico. Para cada componente, o
tempo de ciclo de seu canal (a partir do próprio eixo de tempo do canal), a
largura mediana de seus picos a meia altura, e o número mediano de **pontos no
pico** — pontos iguais ou acima de um por cento de sua altura, os que são o pico
e não seus pés, contados na integração e carregados em cada linha da
[[results-table]]. Um ajuste gaussiano precisa de três deles
([[integration-algorithms]]); os livros de quantitação pedem cerca de dez ao
longo da base.

As últimas colunas são os tempos de ciclo que dariam cada um, para picos daquela
largura: um ajuste em qualquer fase dos scans precisa que o ciclo não seja maior
que 0.85 da largura a meia altura, e dez pontos ao longo de uma base de quatro
sigma precisam de 0.17 dela. Um pico com apenas um ponto acima da meia altura
não tem largura mensurável — é mais estreito que um ciclo — e é contado na
última coluna; as larguras são então apenas dos picos mais largos, e os tempos
de ciclo que decorrem são limites superiores.

No lote para o qual isto foi escrito: um scan a cada 14.6 s, **uma mediana de um
ponto no pico**, 129 de 139 componentes tipicamente abaixo dos três de que um
ajuste precisa. Isso é uma propriedade do agendamento de aquisição, e nada no
processamento substitui isso — o [[report]] carrega a mesma tabela sob
*Sampling*, e **Export schedule…** na área de trabalho Method transforma o
método na tabela de que o instrumento precisa, com o ciclo daqui como ponto de
partida: [[acquisition-schedule]].

## Sugerindo os pisos

**Suggest floors…** propõe uma **Min. response** para cada padrão interno a
partir do que ele deu neste lote: a mediana de sua área sobre as injeções
fortificadas, com as injeções em que todos os padrões caíram de uma vez deixadas
de fora — são essas que o piso existe para apanhar, e uma mediana que as
incluísse seria mais baixa por causa delas — e metade dessa mediana como
proposta, arredondada a três algarismos. Cada linha mostra a base: a mediana,
quantas injeções a sustentaram, quais foram deixadas de fora. Linhas com menos
de seis injeções vêm desmarcadas. É uma proposta: o piso é o que o padrão dá
quando a corrida está certa, e quem conhece o método pode colocá-lo mais alto ou
mais baixo. Veja [[internal-standards-and-qualifiers]].

## Deriva de massa

A aba vizinha, [[mass-drift]], faz ao eixo de massa a mesma pergunta que as
cartas de controle fazem à resposta: ele se manteve da primeira à última
injeção?

## No relatório

A seção *Batch quality* do [[report]] carrega os vereditos das cartas, o índice,
a deriva e a tabela de precisão, com as regras enunciadas nas palavras da própria
seção.

A mesma aritmética responde a uma pergunta mais lenta em outro lugar. Um
padrão infundido para verificar um frasco deixa um registro na sua própria
biblioteca a cada vez, e o [[standard-history]] traça esses registros ao
longo dos dias em que foram adquiridos — o mesmo centro, as mesmas duas
condições antes de um ponto estar fora, e a mesma regra de tendência, sobre
registros em vez de injeções.

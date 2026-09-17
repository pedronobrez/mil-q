---
title: Quantificação por infusão direta
---
**Quantify…** na aba *Infusions* mede cada analito contra o padrão interno
que o método lhe dá, no espectro médio de cada [[direct-infusion]] aberta.
Não há coluna, então não há pico, nem tempo de retenção, nem largura: a
resposta é uma altura em um espectro, e o número que significa alguma coisa é
a razão entre duas delas.

Essa razão vai então para a [[results-table]] e para a [[calibration]] como
qualquer outra linha. Uma série de diluições de infusões ajusta uma curva
exatamente como uma série de injeções, e as linhas dizem o que são — a coluna
*Algorithm* mostra `infusion`, o tempo de retenção é zero e a *Note* diz qual
base produziu o número.

## As três bases

O diálogo pergunta sobre o que tomar a razão, e as três respondem perguntas
diferentes:

- **Precursor** — o íon intacto que o aduto declara. O número mais específico
  que existe, e a primeira coisa a desaparecer conforme a energia de colisão
  sobe.
- **Fragment** — o m/z do fragmento escrito na tabela de componentes ou, onde
  nenhum está escrito, o íon mais intenso que aquele composto está previsto a
  dar *neste* espectro. O segundo não é um íon fixo, e a página explica
  abaixo por que isso importa.
- **Water-loss ladder** (o padrão) — cada degrau que a previsão do
  [[lipid-maps]] oferece para esta fórmula e este aduto, somados: o aduto
  intacto, a forma que os fragmentos carregam, e cada desidratação dela,
  inclusive os degraus que perderam um deutério junto com uma água.

Medido nas nove infusões de ácidos biliares no ZenoTOF, todas aquisições de
íons produto dos próprios padrões deuterados:

| aquisição | CE | precursor | fragmento | escada | degraus achados |
|---|---|---|---|---|---|
| CA-d4, EAD | 12 | 12.271 | 12.271 | 12.982 | 11 de 11 |
| CA-d4, EAD | 22 | 9.415 | 9.618 | 27.754 | 11 de 11 |
| CA-d4, CID | 45 | 0 | 5.673 | 6.569 | 4 de 11 |
| DCA-d4, EAD | 22 | 5.582 | 5.582 | 15.677 | 9 de 11 |
| DCA-d4, CID | 40 | 7 | 3.109 | 3.839 | 7 de 11 |
| TDCA-d4, EAD | 22 | 5.235 | 5.235 | 15.338 | 6 de 10 |
| TDCA-d4, CID | 30 | 124 | 9.044 | 10.403 | 6 de 10 |

O padrão é a razão de a escada ser o valor por omissão. Sob uma ativação
suave o precursor sobrevive e as três concordam dentro de um fator de dois;
sob CID ele acabou — **0, 7 e 124 contagens** nas três aquisições duras —
enquanto a escada ainda carrega de cinco a dez mil. Uma base que lê zero em
uma energia de colisão e doze mil em outra não é uma base.

Os dois arquivos chamados `…TESTEARTIGO` estão do outro lado da tabela: eles
isolam **839,56**, que não é aduto nenhum do ácido cólico-d4, então as três
bases recusam com essa frase em vez de informar um número. O mesmo achado que
o [[infusion-report]] fez sobre essas duas aquisições.

## A interferência isotópica, e para que lado ela vai

Um padrão d4 fica 4·(D−H) = **4,0251 Da** acima do seu analito não marcado. O
isotopólogo M+4 do próprio analito — quatro carbonos-13 — fica 4·(13C−12C) =
**4,0134 Da** acima dele. Os dois estão a **0,0117 Da** um do outro, o que
são 27 ppm em m/z 430: um instrumento de alta resolução os separa e um de
resolução unitária não, de modo que se o analito alcança o canal do padrão é
decidido pela tolerância e por mais nada.

Então a correção é calculada a partir da fórmula, íon a íon, e somada sobre o
que a tolerância de fato admite. Dos três padrões em mãos, como fração do
pico monoisotópico do *analito*:

| par | 10 ppm | 20 ppm | 25 ppm | 30 ppm | 50 ppm | janela unitária |
|---|---|---|---|---|---|---|
| ácido cólico → CA-d4, `[M+NH4]+` | 0 | 0,00004% | 0,0014% | 0,018% | 0,058% | 0,058% |
| desoxicólico → DCA-d4, `[M+NH4]+` | 0 | 0,00004% | 0,0014% | 0,017% | 0,049% | 0,049% |
| taurodesoxicólico → TDCA-d4, `[M+H]+` | 0 | 0,0019% | 0,025% | 0,073% | 0,322% | 0,337% |

**O sentido inverso é zero, e é zero porque foi calculado.** O padrão é o
composto mais pesado, então o seu envelope isotópico sobe *para longe* dos
íons do analito e não alcança nenhum deles — 0,00000% em toda tolerância até
uma unidade inteira. O sentido que importa é sempre o composto leve entrando
no pesado, o que para um padrão deuterado quer dizer o analito entrando no
padrão, e cresce com o analito: 0,058% não é nada numa razão de um para um e
é 5,8% numa de cem para um.

A única coisa que a aritmética não enxerga é o **frasco**. Um padrão d4 tem
algum d3 e algum d2, e esses caem 1,006 e 2,012 Da *abaixo* do íon d4 — do
lado do analito. Nenhuma fórmula prevê quanto: é uma propriedade do material,
não do composto. Um ombro de d3 é portanto medido como analito, e isso é dito
em vez de corrigido.

## Quando a correção é zero porque o instrumento chegou antes

Uma aquisição de íons produto isola o seu precursor, e a janela de isolamento
é mais estreita que um dálton — então os satélites nunca entraram na célula
de colisão e não há nada de um composto nos íons do outro para tirar.

Isso é medido, não suposto. Para cada composto o M+1 previsto é comparado com
o medido, no íon mais intenso que não tenha *outro* íon previsto onde o seu
M+1 estaria. Nas sete infusões legíveis de ácidos biliares o M+1 previsto é
**26,4 – 29,6%** do pico monoisotópico e o medido é **0,000 – 0,426%** — uma
transmissão de **0,00 – 1,44%**. Abaixo de dez por cento da previsão o
envelope é tratado como ausente, a correção é informada como zero, e a razão
disso está na dica da coluna *Cross-talk* e na nota da linha. A mesma
leitura recusa a solução da pureza isotópica e a verificação de satélite em
cada fragmento casado; o [[lipid-maps]] a traz por aquisição, com a única
injeção com survey que diz que uma janela de isolamento de fato mantém o
M+1 do lado de fora.

Onde ela se aplica é numa infusão de **varredura de survey**, ou em qualquer
aquisição
cuja janela de isolamento abranja os dois compostos. Ali cada isotopólogo é
transmitido e a tabela acima é toda a resposta.

Há uma segunda sobreposição, mais próxima, que só um par marcado tem. O
degrau totalmente desidratado de um padrão d4, tendo perdido três marcas com
três águas, guarda um deutério e fica **1,00628 Da** acima do degrau
equivalente do analito — enquanto o satélite de carbono-13 desse mesmo degrau
do analito fica 1,00335 acima dele. Estão a **2,9 mDa** um do outro, oito ppm
em m/z 356, e em qualquer tolerância mais frouxa que isso são uma medida só.
É contabilizado como qualquer outra interferência, e a dica nomeia o degrau
de onde veio.

## O que a curva faz com isso

Ajustada sobre uma série sintética de cinco níveis com as razões conhecidas —
1, 2, 5, 10 e 20 — o precursor e a escada recuperam **todos os níveis a
100,000% com r² = 1,0000000**. A base do fragmento, deixada escolher o íon
mais intenso de cada espectro, dá r² = 0,895 e exatidões de −199% a +150%: é
um íon diferente em níveis diferentes, porque o pico mais alto mudou conforme
o analito cresceu contra o padrão. **Escreva um m/z de fragmento na tabela de
componentes** e ele volta a ser um íon fixo; as linhas dizem quando não é, e
o *Measure* nomeia as amostras entre as quais ele se moveu.

A medida em si não é salva com o projeto — apertar **Write into results** é o
que põe as linhas lá, e isso é uma linha na [[audit-trail]] nomeando os
pares, a base e a tolerância. Ler e promediar sete infusões reais e medir
dois pares em cada uma levou 36 segundos, quase tudo lendo os arquivos.

## O que ela não faz

**Não separa isômeros.** Ácido desoxicólico e ácido quenodesoxicólico têm a
mesma fórmula, o mesmo precursor e a mesma escada. Um cromatograma os
distingue; um spray não. Toda razão medida aqui é a razão de tudo o que
estiver no frasco com aquela composição, e onde a tabela de componentes do
método nomeia dois isômeros as linhas dos dois serão o mesmo número. Essa é a
maior razão isolada para um método cromatográfico existir.

**A supressão iônica é compartilhada, não removida.** O analito e o seu
padrão são pulverizados juntos, que é exatamente o que torna a razão útil —
uma matriz que corta um pela metade corta o outro e a razão sobrevive.
Também quer dizer que o par não consegue informar que aquilo aconteceu: as
respostas caem juntas e a razão diz que nada estava errado. As respostas
absolutas na tabela são o que mostra isso, e é por isso que estão na tabela
ao lado da razão e não embaixo dela. Veja
[[internal-standards-and-qualifiers]] para o piso de resposta que transforma
"o padrão estava lá" em algo que uma linha pode reprovar.

**Não há confirmação por qualificador nem razão de íons.** Isso precisa de
duas transições de um composto adquiridas juntas; uma infusão tem um espectro
só, e os degraus da escada não são independentes entre si.

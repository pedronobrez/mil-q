---
title: Histórico do padrão
---
Um registro escrito na sua própria biblioteca é uma verificação que já
aconteceu. Toda vez que o padrão é infundido para conferir o frasco, mais um
registro do mesmo composto entra no mesmo MSP — e depois de alguns meses
esse arquivo guarda a única medida daquele padrão ao longo do tempo que
existe.

**History…**, ao lado da contagem de registros na aba
[[spectral-library]], lê tudo de volta. É o [[batch-qc]] perguntado a uma
biblioteca em vez de a um lote: o mesmo centro robusto, as mesmas duas
condições que um ponto precisa cumprir antes de ser chamado de fora do
limite, a mesma tendência que exige tamanho e direção — com os registros na
ordem em que foram **adquiridos**, e não na ordem em que foram digitados.

## O que é agrupado com o quê

Os registros de um composto são cortados em **séries** por energia de
colisão e ativação, e nada é comparado através dessa fronteira. Um espectro
medido em outra energia tem outros fragmentos e muitas vezes outro pico
base, de modo que um cosseno contra ele mede o método e não o padrão; e uma
intensidade absoluta só é comparável dentro de um mesmo método. Medido em um
padrão infundido real, o ácido cólico-d4, o mesmo composto no mesmo frasco
obteve **67 em EAD 12 eV contra EAD 22 eV, 29 em EAD 22 eV contra CID 45 eV
e 6 em EAD 12 eV contra CID 45 eV** — três números que não dizem nada sobre
o frasco e tudo sobre a cela de colisão.

O composto é a parte do nome do registro antes do primeiro separador, como
no [[infusion-report]]. A ativação é lida de um campo `Activation` onde
algum exportador escreveu um, e do nome do registro caso contrário —
`..._EAD_22CE_...` — porque nenhum campo que este programa lê de um `.wiff`
a carrega: as nove infusões do ZenoTOF disponíveis dizem todas `TOF PI` e
`Product`, e a energia dos elétrons aparece apenas no nome do arquivo. Um
registro cujo nome não diz é agrupado como *não declarado*, nunca como CID.

### E pelo eixo de massa do qual foi escrito

Um registro escrito enquanto a [[mass-recalibration]] estava ligada carrega
picos que o instrumento nunca reportou: eles foram movidos por algumas
partes por milhão antes, e o comentário do registro diz isso. Pontuar um
registro desses contra um escrito do eixo do próprio instrumento mede a
correção e a reporta como o padrão tendo mudado, de modo que o eixo é um
atributo da série exatamente como a energia é. A coluna **Mass axis** da
tabela diz de qual cada registro veio, e uma série corrigida carrega `axis
corrected −5.2 ppm` no nome.

Duas regras impedem que isso parta histórias que deveriam estar inteiras:

- **Dois registros corrigidos são um só eixo, por mais distantes que as
  correções tenham sido.** Cada um está onde as lock masses da própria
  aquisição dele o põem. Só uma correção que um registro carrega e outro não
  pode separá-los — veja a medição de quatro modos em [[spectral-library]],
  onde o par cujas correções eram as mais distantes foi o que melhor
  concordou.
- **E só quando ela é maior que os 20 ppm dentro dos quais uma busca pareia
  picos.** Abaixo disso os dois põem cada pico na mesma janela um do outro,
  e duas séries seriam uma história partida ao meio por um cinquentavo de
  largura de pico; a diferença ainda aparece no gráfico de massa, que avisa
  a 10 ppm e marca a 20.

Onde um composto de fato sai como duas séries por essa razão, a linha sob os
gráficos diz quais séries são, quanta correção uma carrega e a outra não, e
que o reparo é **Rewrite from files…** — que lê de novo cada registro cuja
aquisição ainda está em disco e escreve todos a partir do eixo em vigor
agora. O botão é oferecido nesta janela quando é isso que está errado, e faz
a escrita de volta na aba [[spectral-library]], que é dona do arquivo.

Nas infusões reais nada se parte: toda correção que as próprias escadas de
precursor dão está dentro dos 20 ppm — as cifras por aquisição estão em
[[mass-recalibration|Uma infusão recalibra no próprio precursor]] —, de modo
que um registro corrigido e um não corrigido do mesmo padrão continuam sendo
uma série e dizem isso no nome da série — *axis corrected +6.6 ppm for 1 of
2, the rest on the instrument's own*. Esse é o resultado pretendido. A
divisão em si só é exercitada em registros inventados, e o manual diz isso
em vez de sugerir uma medição que não foi feita.

### A fronteira da série não é o fim da história

Esses três números — 67, 29 e 6 — são a razão de uma série nunca cruzar uma
energia, e são também três medidas desperdiçadas. Os mesmos registros que não
podem ser postos em gráfico uns contra os outros *podem* ser lidos como uma
curva: como a fração de intensidade de cada fragmento se move conforme a
energia sobe. Isso é o perfil de energia, é calculado a partir dos registros de
um composto sem cruzar série alguma, e é o que permite à aba
[[spectral-library]] dizer **compatible with CA-d4 EAD at ~18 eV** em vez de
listar três registros que parecem todos errados.

O perfil do ácido cólico-d4, degrau por degrau, está impresso em
[[spectral-library|Fragmentação ao longo das energias]], nas mesmas nove
infusões de onde vêm os números desta página. A única linha dele que decide
como esta página é traçada: **o pico base é um íon diferente em cada um dos
três arquivos** — o precursor amoniado a 12 eV, `[M+H-2H2O]+` a 22,
`[M+H-3H2O]+` a 45 — que é por que um perfil é mantido em frações do próprio
total, e não em relação a um pico base que se muda, e por que o gráfico de
*intensidade do pico base* abaixo é traçado dentro de uma série e nunca
através de uma.

O perfil é calculado a partir dos registros presentes e nunca é escrito neles,
de modo que acrescentar mais uma verificação o altera sem deixar nada
desatualizado. Veja [[spectral-library]] para a interpolação, as duas recusas —
nada extrapolado além da faixa medida, nenhuma ativação cruzada com outra — e o
que duas energias por ativação permitem e não permitem.

## Os três gráficos

O primeiro registro de uma série é a **referência**, e tudo é medido contra
ele.

| Gráfico | O que pergunta | Sinalizado além de |
|---|---|---|
| Escore contra o primeiro registro | ainda se parece consigo mesmo | 20% do centro e 3σ, ou 50% de imediato |
| Pico base, ppm do primeiro registro | o pico base ainda é o mesmo íon, no mesmo lugar | 20 ppm e 3σ, ou 40 ppm de imediato |
| Intensidade do pico base | ainda está dando o que dava | 20% e 3σ, ou 50% de imediato |

O escore é o mesmo cosseno que a busca em biblioteca usa, para que "quão
parecidos são estes dois espectros" tenha uma resposta só neste programa; o
cosseno reverso fica ao lado dele, porque um padrão que ganhou uma impureza
manteve tudo o que tinha e ganhou algo. A tabela traz também o escore contra
o registro **anterior**, que é o que diz se a mudança aconteceu em uma
verificação ou foi se acumulando.

O gráfico de massa é a única métrica que não pode ser uma porcentagem do
próprio centro — uma mediana de zero ppm não tem porcentagem de si mesma —
então seus limites são escritos em ppm e sua tendência é uma diferença
simples. Um pico base a mais de 50 ppm do da referência não é traçado: isso
é outro íon, não um erro de massa, e a linha diz `not the same ion` com as
duas massas ao lado. É a lição do [[mass-drift]] em outro lugar — uma medida
que não pode ser mostrada como sendo do mesmo íon não é julgada.

## Três registros, não dois

Nenhum limite é traçado com menos de três registros. Abaixo disso todos os
gráficos dizem **too few to chart** e os registros continuam listados,
porque uma mediana e uma dispersão tiradas de dois pontos são uma reta por
dois pontos, e quem vê limites desenhados vai lê-los. Um lote ganha seis, e
pode: ele é adquirido em uma tarde. Um histórico acumula um registro por
verificação, e seis deles são um ano.

## O que um registro precisa carregar

Dois campos são escritos em todo registro feito a partir desta versão, e
nenhum dos dois pode ser recuperado depois:

- **Acquired** — o dia em que o instrumento mediu, lido do arquivo, e não o
  dia em que o registro foi digitado. Uma pasta adquirida ao longo de três
  meses e escrita em uma biblioteca numa tarde é três meses de histórico, e
  `added 2026-09-10` não diz nada sobre o padrão. Ele aparece, somente para
  leitura, no diálogo *Add spectrum to library*.
- **Base peak intensity** — a altura do pico base em contagens. Todo formato
  de biblioteca guarda os picos como fração do pico base, então o tamanho do
  espectro se perde no instante em que o registro é escrito, a menos que
  seja escrito junto.

Um registro feito antes desses campos existirem continua sendo lido: ele é
ordenado pela ordem em que o arquivo o guarda, sua intensidade fica fora
daquele gráfico, e as duas coisas são ditas no gráfico em vez de passarem em
silêncio.

Um terceiro campo é escrito pelo [[new-standard]] e por mais nada: o **lote**,
no comentário do registro. Ele não é uma medida e nenhuma aquisição o contém,
e é justamente por isso que precisa ser digitado quando o padrão é
cadastrado — um histórico que atravessa uma troca de frasco são dois
históricos desenhados como um só, e o lote é a única coisa que diz onde está
a emenda.

Um padrão cadastrado por aquele diálogo tem a sua primeira entrada de
histórico no instante em que é criado, porque a entrada *é* o registro: esta
página é a biblioteca relida, e nada escreve um histórico à parte.

## O que foi medido

Nove infusões de ácidos biliares no ZenoTOF, escritas em uma biblioteca
própria e lidas de volta: nove registros, sete séries, todas adquiridas em um
único dia. **Dois registros em uma energia é o que a pasta tem** — esperava-se
que as aquisições `_TESTEARTIGO` fossem repetições das `_mix1` nas mesmas
energias, e não são. Elas isolaram m/z 839,56 numa faixa de 100–1000, onde as
infusões `_mix1` isolaram 430,34 em 50–500, e o histórico diz isso sem que
ninguém o avise: em EAD 22 eV o segundo registro obteve escore **8** com pico
base em 839,2343 contra 377,3015 — *não é o mesmo íon* — a 2,4% da altura do
primeiro registro; em 12 eV obteve **0**, a 0,9% dela.

Como nenhuma série real chega a três registros, os limites foram exercitados
cortando seis das infusões em três terços consecutivos cada — dezoito
registros, seis séries, um padrão em uma energia por série, nada mudando
entre eles. Esse é o piso da medida: o escore contra o primeiro terço ficou
entre **98,7 e 100,0**, o pico base se manteve em **0,4 ppm**, e a altura do
pico base variou **até 4,5%**, o que deixou um dos seis gráficos de
intensidade com um ponto além de dois sigmas. Um dos terços da infusão de
ácido cólico-d4 em EAD 22 eV teve o pico base trocado do fragmento em
377,3014 para o precursor em 430,3489 — dois picos de altura quase igual, e
qual deles é o maior muda ao longo da corrida. Esse registro saiu do gráfico
de massa como *not the same ion*, que é a resposta pretendida.

Ler uma biblioteca de nove registros como histórico completo leva cerca de
3 ms.

## O que ele não é

É uma carta de controle de um padrão contra si mesmo, e tem o mesmo limite
que o [[batch-qc]] declara: não distingue um instrumento que mudou de um
frasco que mudou. Vários padrões caindo juntos em uma verificação é o que
diz qual dos dois, e esse julgamento é do analista — isto desenha os
gráficos que o tornam possível. **Export CSV…** escreve todos os registros
com o que cada gráfico disse acima das linhas.

Ele também precisa de registros, o que significa que alguém tem de os ter
escrito. As mesmas duas regras — cinquenta ppm para *o mesmo íon*, vinte por
cento para *a mesma resposta* — são aplicadas a uma bandeja inteira de uma
vez pelo [[compare-infusions]], que lê um dia de referência do arquivo de
projeto em vez de uma biblioteca, e não precisa que nada tenha sido
acrescentado a uma.

Ele também compara uma série apenas consigo mesma. Qual das séries de um
padrão vale a pena manter — qual energia de colisão e ativação o identifica,
qual o quantifica e qual pertence a um registro — é uma pergunta diferente
de se uma delas se deslocou, e a [[collision-energy]] é onde ela é feita,
das infusões e não dos registros.

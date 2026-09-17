---
title: Recalibração de massa
---
A [[mass-drift|Mass drift]] pergunta se o eixo de massa do instrumento *se
moveu* durante a corrida, e responde contra a mediana do próprio lote porque
essa é a única referência que uma corrida pode fornecer a si mesma. A
recalibração pergunta a outra metade da questão — **o eixo está no lugar
certo, afinal** — e o corrige se não estiver.

O interruptor é *Recalibrate m/z from the internal standards*, na aba **Mass
drift** da área de trabalho Analytics. Ele vem desligado e é salvo com o
projeto.

## O que conta como lock mass

Uma lock mass aqui é um padrão interno que satisfaz quatro condições:

1. ele carrega uma **fórmula e um aduto** no [[method-workspace|method]], de
   modo que a sua massa verdadeira é conhecida. O *Fill formulas from names*
   preenche as células Formula vazias a partir da notação abreviada de
   lipídios dos próprios nomes — `SM(d18:1/12:0)`, `C16:0-Ceramide`,
   `PC 34:1` — e guarda cada uma somente onde ela concorda com o precursor já
   escrito;
2. o seu precursor fica dentro da faixa de massas da varredura de survey, de
   modo que pode ser medido — o [[check-method|Check method]] lista os que
   não ficam;
3. o íon medido se manteve o mesmo ao longo da corrida, que é o mesmo teste
   `same_ion` que a medida de [[mass-drift|drift]] aplica: injeções que
   discordam por mais de 25 ppm não estavam medindo um único íon, e
   promediá-las recalibraria o instrumento sobre o que por acaso estivesse
   mais perto;
4. ele mediu esse íon **perto de onde a fórmula o coloca** — dentro de
   **50 ppm**, na maioria das suas injeções. A condição 3 pergunta às injeções
   se elas concordam *entre si*; ela não consegue perguntar se elas concordam
   com o composto, e um padrão cuja janela de ±0.25 Da contém o mesmo íon
   *errado* em toda injeção concorda consigo mesmo perfeitamente. Um padrão
   além do limite é nomeado na tabela — *measures 237 ppm from its formula:
   not the ion the formula names* — e não é usado, por mais firme que tenha
   sido a medida. Onde um padrão está dentro do limite na maioria das injeções
   e além dele em uma, apenas aquela injeção o perde, e a linha daquela
   injeção diz isso.

**De onde vêm os 50 ppm.** Medido sobre as 1,439 medidas de survey que o lote
real fornece — todos os 60 componentes com fórmula dentro do survey, em cada
injeção — a distância até a fórmula é bimodal: 19.5% delas abaixo de 20 ppm,
53.5% além de 200 ppm, e o fundo do vale entre os dois lóbulos em 30–50 ppm,
onde um intervalo de 10 ppm contém 1.0–1.4%. Cinquenta é a borda distante
desse vale, e é o dobro dos 25 ppm que a condição 3 já tolera: um íon ao qual
se permite vagar o equivalente a uma dispersão pode ficar o equivalente a uma
dispersão longe da verdade, e não mais. As margens de cada lado são ambas de
cerca de um fator de cinco — 11.7 ppm na pior injeção da lock mass honesta,
237 ppm no impostor.

O **precursor escrito é deliberadamente recusado**. Um método que diz `647.5`
é bom até cerca de 800 ppm naquela massa; corrigir um eixo de massa em
direção ao arredondamento de alguém é pior do que não corrigi-lo. Digite a
fórmula.

## O que é ajustado

Uma correção por injeção:

- um **offset** em ppm — a mediana dos erros das lock masses daquela injeção,
  com o sinal invertido;
- um **termo linear** em ppm por dalton, mas apenas onde **quatro ou mais**
  lock masses cobrem pelo menos 100 Da *e* um teste de deixar-uma-de-fora diz
  que a reta prevê uma lock mass retida melhor do que o offset simples
  prevê. Uma reta traçada pelos pontos sobre os quais ela é então pontuada é
  exata e não diz nada, que é o mesmo aviso que o
  [[integration-algorithms|Gaussian fit]] carrega; quatro em vez de três,
  porque reter uma de três deixa uma reta por dois pontos, o que é exato de
  novo.

Uma correção a partir de **uma** lock mass é um offset e a tabela diz isso:
não sobra uma segunda medida contra a qual conferi-la, e o seu resíduo vai a
zero por construção e não por concordância.

## Onde ela se aplica

Enquanto o interruptor está ligado:

- o eixo de m/z dos espectros no [[explorer|Explorer]], cujo título passa a
  dizer `· recalibrated +3.2 ppm`;
- a medida do [[accurate-precursor|accurate precursor]], que reporta a massa
  crua e a corrigida lado a lado — o valor medido nunca é sobrescrito, porque
  a correção foi ajustada a partir dele;
- a janela de extração de todo [[manual-xic|XIC]] e de todo pico integrado. A
  janela se move; a aritmética do leitor, não. As linhas carregam a correção
  que lhes foi aplicada.

Com o interruptor desligado nada muda em absoluto, e um projeto salvo antes
de isto existir reabre com ele desligado.

## O que o lote real disse

Medido no lote de esfingolipídios de 26 injeções contra o qual isto foi
escrito (TripleTOF 5600, uma única varredura de survey de 50–700, um scan a
cada 14.6 s).

**Fórmulas.** O método não carregava nenhuma. O *Fill formulas from names*
leu 125 dos seus 141 nomes de componente e 10 dos seus 11 padrões internos,
em milissegundos e sem abrir um arquivo:

| | |
|---|---|
| preenchidas a partir do nome | **125** de 141 |
| recusadas — a fórmula do nome não é o precursor escrito | 16 |
| nomes que não são notação abreviada de lipídios | 0 |
| padrões internos que ganharam uma fórmula | **10** de 11 |

As dezesseis recusas são todas o *precursor* estar errado, e não o nome:
`dHCer(d18:0/12:0)` está escrito 484.465 contra os 484.4724 da sua fórmula
(15 ppm), `LacCER(d18:1/18:1(9Z))` exatamente 2.0000 Da abaixo, e as treze
linhas de `HexCer_2OH` e de ceramidas de cadeia longa cerca de 0.13 Da. Cada
uma é listada com os dois números, e a célula fica vazia — veja o
[[check-method]].

**Lock masses.** Uma fórmula era a metade que faltava da questão, e não é a
metade que limita. Dos 60 componentes que agora carregam uma fórmula *e*
ficam dentro do survey, exatamente **um** mede o mesmo íon injeção após
injeção:

| | |
|---|---|
| injeções corrigidas | 25 de 26 |
| lock masses em cada uma | **1** (somente offset) |
| offset mediano | **+4.8 ppm** (−4.4 a +11.7) |
| dispersão dos offsets | 16.1 ppm |

**O que a barreira da fórmula recusa.** Cinco dos dez padrões que carregam
uma fórmula são nomeados como medindo um íon que a fórmula deles não nomeia:
`Sphingosine C17:0` a 383 ppm dela, `C17:0_Ceramide` a 237, `C12:0 _Ceramide`
a 204, `Cer1P (12:0)` a 91 e `Sphingosine-1-P C17:0` a 82 — este último
montado a cavalo sobre a sua fórmula, com um erro mediano de apenas −43 ppm e
a maioria das suas injeções além do limite de um lado ou do outro. Cada um
deles já havia falhado na condição 3 ou estava aquém das injeções que uma
tendência exige, de modo que o ajuste abaixo permanece inalterado até a última
casa decimal e nenhuma injeção perdeu uma medida: neste lote a barreira é uma
guarda e não um achado. O quase-acerto diz por que vale a pena tê-la. O
`Sphingosine C14:0`, um analito e não um padrão, mantém a sua medida dentro de
**52 ppm ao longo de 25 injeções** — o dobro do limite de mesmo-íon, e nada
mais — a uma mediana de **156 ppm** da sua fórmula. Isso é um íon, medido
firmemente, e não é o composto; nada além da fórmula consegue dizer isso.

Os outros dez padrões falham por um motivo que fórmula nenhuma resolve: o
sinal deles no survey é fraco demais, de modo que a janela de busca de
±0.25 Da pega um vizinho diferente em cada injeção e eles se dispersam entre
98 e 534 ppm ao longo da corrida — e um fica fora do survey por completo. O
`C17:0_Ceramide` foi encontrado em apenas cinco injeções e a sua mediana fica
237 ppm da sua própria fórmula, o que é um íon diferente e não um íon mal
medido. **Várias lock masses não estão disponíveis neste lote com nenhuma
cobertura de fórmulas**, de modo que o termo linear continua nunca tendo
disparado em dados reais.

O número que importa é o que acontece com *outros* componentes. Cinquenta e
um analitos dentro do survey carregam agora uma fórmula — contra quinze
quando isto foi medido pela primeira vez — e foram medidos em cada injeção:
1,228 medidas ao todo. Sobre todas elas o erro mediano é −247 ppm antes e
−241 ppm depois, porque a maioria é interferência e não o composto, e nada na
escala de ppm as toca. Sobre as 197 medidas que já estavam dentro de 25 ppm
para começar:

| | antes | depois |
|---|---|---|
| erro mediano | −7.0 ppm | **−1.4 ppm** |
| magnitude mediana | 8.6 ppm | **6.8 ppm** |
| menor depois | | 122 de 197 |

Ou seja, isso move o centro na direção certa, e não pode ser melhor que a
única lock mass de que veio — cuja própria dispersão de 16 ppm ao longo da
corrida é maior que os 4.8 ppm pelos quais ela corrige.

## Isso muda os números

Reprocessando o lote inteiro dos dois modos, sobre janelas de extração de
±20 ppm, um deslocamento mediano de 5 ppm moveu **1,769 das 2,593 áreas
integradas**: uma mudança absoluta mediana de 1.3%, 830 linhas além de 5%, e
dez linhas que deixaram de encontrar um pico. Um instrumento de tempo de voo
guarda poucos pontos ao longo de uma janela tão estreita, de modo que mover a
borda da janela leva pontos inteiros para dentro ou para fora.

Ligar isto é uma decisão quantitativa, não uma preferência de exibição.
Ajuste, leia a tabela por injeção, e ligue apenas quando as lock masses o
justificarem — e então processe o lote de novo para que os resultados
acompanhem.

## Uma infusão se recalibra sobre o próprio precursor

Tudo acima precisa de um **lote**: um composto de composição conhecida medido
injeção após injeção, para que o erro de uma injeção possa ser distinguido do
de outra. Uma [[direct-infusion|infusão direta]] é uma única aquisição de um
único frasco, e não existe segunda injeção alguma.

Ela não precisa de uma. Uma infusão pulveriza o composto por um ou dois
minutos e a média da corrida inteira traz o precursor **junto com os seus
próprios fragmentos**, e a aritmética já sabe onde cada um deles pertence: o
aduto intacto, o `[M+H]+` que um amônio deixa para trás ao entregar o seu
próton, a escada de perdas cumulativas de água e — para um padrão marcado — o
degrau ao lado de cada um deles que perdeu um deutério junto com a água. São
os mesmos íons que a aba [[lipid-maps|LIPID MAPS]] prevê para uma fórmula.
Cada um deles que de fato esteja lá é uma medida independente de uma massa
que a fórmula já conhece, na mesma aquisição, em uma massa diferente.

Assim, uma infusão é recalibrada contra **si mesma**. Nada precisa ser
digitado: o composto é a parte do nome do arquivo antes do primeiro `_`, a
sua fórmula vem da tabela de padrões, do LIPID MAPS ou da notação abreviada
de lipídios, e o aduto é lido do precursor que o canal recebeu. O ajuste
acontece quando o Explorer promedia a corrida inteira, e o título do painel
passa a dizer `· recalibrated −5.6 ppm from 8 rungs`.

### As regras

- um degrau é casado com o **pico mais forte dentro de 20 ppm** de onde a
  fórmula o coloca, e apenas acima de 100 contagens — o piso fixo a que o
  [[accurate-precursor|precursor acurado]] submete uma varredura de survey,
  porque abaixo dele uma janela é um trecho de eixo cujo ponto mais alto é
  ruído. É o único lugar, numa infusão, em que as cem fixas ainda valem em
  vez do piso medido na aquisição ([[signal-to-noise]]), e a página o diz em
  vez de deixar dois pisos para serem confundidos;
- a correção é a **mediana ponderada pela intensidade** dos erros dos
  degraus, com o sinal invertido. Ponderada, porque um pico de doze mil
  contagens localiza o seu centroide melhor do que um de cem; mediana, porque
  um degrau apanhado sobre um vizinho não deve arrastar o eixo parte do
  caminho até ele;
- é um **deslocamento e mais nada**. Os degraus de um precursor abrangem as
  águas que ele pode perder — 72 Da no caso mais amplo medido — contra os
  100 Da de que uma inclinação precisa antes de ser extrapolação, e a linha
  diz isso com a abrangência do próprio arquivo;
- um degrau que discorda dos demais por mais de **25 ppm** é um íon diferente
  dentro da janela: ele é descartado e nomeado;
- abaixo de **dois** degraus, nada é corrigido e a linha diz por quê. Dois, e
  não um: um único degrau é o precursor medido contra a sua própria fórmula
  sem nada que o verifique, e uma infusão não tem outra injeção contra a qual
  ser lida.

### A que isso se aplica

Enquanto o interruptor está ligado, e atrás do mesmo interruptor de tudo o que
está acima: o espectro promediado no [[explorer|Explorer]] e o seu título, a
[[lipid-maps|explicação]] — cuja linha de base passa a imprimir o erro do
degrau mais forte cru *e* corrigido — o [[spectral-library|registro escrito
na sua própria biblioteca]], cujo comentário diz que o eixo foi movido e por
quanto, o parágrafo *Mass axis* do [[infusion-report|relatório de infusão]]
por composto, a coluna *Mass axis* da aba Infusions, e uma linha própria na
tabela por injeção da aba **Mass drift**, com *from the precursor ladder*
como fonte.

### O que as nove infusões reais disseram

Nove infusões de ácidos biliares em um ZenoTOF 7600, modo positivo, um único
canal de íons produto cada e **nenhuma varredura de survey**. As quatro
últimas colunas são a explicação do LIPID MAPS rodada no seu próprio padrão
de 5 ppm, no eixo como medido e no eixo corrigido:

| infusão | degraus | deslocamento | dispersão | abrangência | íons antes | depois | intensidade antes | depois |
|---|---|---|---|---|---|---|---|---|
| CA-d4, EAD 12 eV | 3 | −5.3 ppm | 7.5 ppm | 54 Da | 2 de 56 | 2 de 56 | 2.8% | **83.7%** |
| CA-d4, EAD 22 eV | 8 | −5.6 | 6.3 | 72 | 5 de 56 | **8 de 56** | 14.0% | **63.6%** |
| CA-d4, CID 45 eV | 3 | +3.8 | 1.3 | 19 | 2 de 56 | 2 de 56 | 24.2% | 24.2% |
| DCA-d4, EAD 22 eV | 8 | −8.6 | 19.9 | 72 | 2 de 41 | **5 de 41** | 16.2% | **53.0%** |
| DCA-d4, CID 40 eV | 3 | +6.6 | 2.8 | 18 | 1 de 41 | **3 de 41** | 1.6% | **17.1%** |
| TDCA-d4, EAD 22 eV | 5 | −7.5 | 3.3 | 37 | 0 de 104 | **5 de 104** | 0.0% | **78.4%** |
| TDCA-d4, CID 30 eV | 4 | +2.0 | 2.2 | 37 | 4 de 104 | 4 de 104 | 72.1% | 72.1% |
| CA-d4, EAD 12 eV, `_TESTEARTIGO` | — | — | — | — | — | — | — | — |
| CA-d4, EAD 22 eV, `_TESTEARTIGO` | — | — | — | — | — | — | — | — |

Sete das nove são corrigidas, com três a oito degraus cada, por −8.6 a
+6.6 ppm. Os três desvios CID liam +3.6, +6.2 e +1.8 ppm quando esta tabela
foi escrita; medidos de novo para [[integration]], leem como acima, nos
mesmos números que [[spectral-library]] cita, com os mesmos degraus. As duas
que não são constituem a recusa correta: o par
`_TESTEARTIGO` tem o nome do ácido cólico-d4 e isola **839.56**, que não é
nenhum dos adutos daquela fórmula, de modo que não há escada a procurar e a
linha diz *no lock mass* com esse motivo. O sinal não é o mesmo para as sete
— as aquisições EAD leem alto, as CID leem baixo — e é por isso que isto é
ajustado por aquisição e nunca uma vez só para o instrumento.

O número que diz que valeu a pena é o último par de colunas. O CA-d4 a EAD
22 eV chegando a **8 de 56 íons e 63.6% da intensidade a 5 ppm** é exatamente
o que aquele arquivo dava a *10 ppm* no eixo não corrigido: a correção
devolve a tolerância que havia sido alargada para absorvê-la, e uma
tolerância que absorve um erro de eixo é uma tolerância que não testa nada.
Nada piorou: os dois arquivos que não se movem já estavam dentro de 5 ppm nos
seus degraus mais fortes e voltam idênticos até o décimo de por cento.

### E um registro seu viaja entre ativações

Um registro escrito a partir de uma infusão e procurado com outra do mesmo
composto — a ida e volta da [[spectral-library|biblioteca própria]] — antes e
depois, na tolerância de pico padrão da busca, 20 ppm, e a 5 ppm:

| registro / consulta | tolerância | eixo | pontuação | reversa | casados | mediana &#124;Δ ppm&#124; |
|---|---|---|---|---|---|---|
| CA-d4 EAD 22 / EAD 12 | 20 ppm | como medido | 67.4 | 67.4 | 12 de 42 | 0.6 |
| | | recalibrado | 67.4 | 67.4 | 12 de 42 | 0.6 |
| DCA-d4 EAD 22 / CID 40 | 20 ppm | como medido | 33.4 | 70.0 | 21 de 39 | 12.3 |
| | | recalibrado | **34.5** | **71.3** | **23 de 39** | **2.6** |
| TDCA-d4 EAD 22 / CID 30 | 20 ppm | como medido | 61.5 | 69.4 | 8 de 32 | 8.6 |
| | | recalibrado | 61.5 | 69.4 | 8 de 32 | **2.1** |
| CA-d4 EAD 22 / EAD 12 | 5 ppm | como medido | 65.9 | 66.3 | 11 de 42 | 0.4 |
| | | recalibrado | 65.9 | 66.3 | 11 de 42 | 0.5 |
| DCA-d4 EAD 22 / CID 40 | 5 ppm | como medido | **sem acerto** | | | |
| | | recalibrado | **31.8** | **69.6** | **19 de 39** | 2.5 |
| TDCA-d4 EAD 22 / CID 30 | 5 ppm | como medido | **sem acerto** | | | |
| | | recalibrado | **61.0** | **69.1** | **7 de 32** | 1.9 |

A 20 ppm as pontuações quase não se movem — um casamento que já vinha dando
certo continua dando — mas as *massas* concordam muito melhor: a distância
mediana entre um pico do registro e o pico medido sobre o qual ele caiu vai
de 12.3 para 2.6 ppm e de 8.6 para 2.1. A **5 ppm** esse é o resultado
inteiro. Dois dos três pares não casam de modo algum nos eixos do próprio
instrumento, porque as duas aquisições estavam a 14.8 e 9.3 ppm uma da outra;
ambos casam depois que cada uma é corrigida contra o seu próprio precursor. O
par do CA-d4 já estava a 0.3 ppm de distância e não se move, o que é o
controle: a correção não fabrica concordância onde já havia alguma.

### E o registro diz de qual eixo foi escrito

Aquela tabela compara dois espectros tratados do mesmo jeito. Uma biblioteca
não é tratada de uma vez só: ela é acrescentada ao longo de meses, parte dela
com isto ligado e parte com isto desligado. Então um registro seu **carrega a
correção que estava em vigor quando ele foi escrito**, no próprio comentário
— `recalibrated −5.2 ppm`, com aquilo em que a correção se apoiou —, tenha
ele sido escrito pelo painel do espectro, por uma pasta inteira de infusões
de uma vez, ou por *Rewrite from files…*. Um registro que nada diz foi
escrito a partir dos números que o instrumento deu, e todo registro feito
antes disto existir é exatamente isso.

Daí em diante ele é lido de volta em vez de suposto:

- uma **busca** diz de qual eixo cada lado foi escrito e como os dois se
  combinam, e avisa quando uma correção que um lado carrega e o outro não é
  maior que a tolerância dentro da qual os picos dela foram pareados.
  *Re-search with the axis matched* refaz a pergunta com os dois num só
  eixo;
- uma **[[standard-history]]** mantém tais registros em séries separadas, de
  modo que uma correção nunca é traçada como o padrão tendo mudado;
- **Rewrite from files…** escreve cada registro cuja aquisição ainda está em
  disco a partir do eixo em vigor agora, que é o que põe de volta num só
  eixo uma biblioteca preenchida nos dois estados.

As quatro combinações do eixo de um registro com o de uma consulta — os dois
corrigidos, nenhum, e cada uma das duas misturas — estão medidas nestas
mesmas aquisições em [[spectral-library]]. A versão curta é que os dois
corrigidos é o melhor dos quatro todas as vezes, que nenhum é o pior, e que
**dois espectros corrigidos por valores diferentes não são dois eixos**: o
par cujas correções estavam a 9.5 ppm uma da outra concordou a 2.0 ppm por
pico, melhor que qualquer outra combinação daquele composto.

## Ver também

- [[direct-infusion]] — o que faz de uma amostra uma infusão
- [[infusion-report]] — onde o parágrafo *Mass axis* é impresso
- [[mass-drift]] — a medida a partir da qual isto é ajustado
- [[accurate-precursor]] — a medida da massa de um componente na varredura de
  survey
- [[check-method]] — quais precursores a varredura de survey consegue ver
- [[report]] — a tabela de correções é impressa sob a seção de massa

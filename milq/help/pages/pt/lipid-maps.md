---
title: LIPID MAPS
---
A aba **LIPID MAPS** do [[explorer]] trabalha contra uma cópia local do LIPID
MAPS Structure Database (LMSD), de modo que uma massa possa ser transformada
em lipídios candidatos, um nome de lipídio nos seus íons, e uma estrutura
nos fragmentos que ela poderia produzir — nada disso precisando de rede uma
vez construído o índice.

## O banco de dados

O primeiro uso oferece **Download the database**. Um arquivo de 21 MB de
lipidmaps.org vira um índice de 45 MB com 49,969 estruturas curadas — a
anotação delas e as suas tabelas de conexão — guardado como
`~/.milq/lipidmaps/lmsd-index.sqlite`. O LMSD é redistribuído pelo
LIPID MAPS sob CC BY 4.0 e é baixado sob demanda, não distribuído junto.

O índice é um banco de dados e é lido uma linha de cada vez, não mantido em
memória. Medido nesta máquina sobre os 49,969 registros: abri-lo leva
0,1 ms e nenhuma memória mensurável, um LM_ID 0,012 ms, uma fórmula
0,058 ms, uma janela de massa 0,083 ms e um nome procurado inteiro 0,03 ms
— um nome procurado como trecho de todos os outros é a única pergunta ainda
respondida lendo todos os nomes, a 5 ms. Antes disso o índice era um
único documento comprimido que precisava ser decodificado inteiro antes de
responder qualquer coisa: 0,74 segundo e 591 MB, que a janela pagava ao
abrir apenas para escrever quantas estruturas estavam indexadas. Um índice
instalado por uma versão anterior é reescrito no lugar na primeira vez que
é aberto, uma só vez, e nada é baixado de novo.

As buscas são restritas a estruturas construídas a partir de C, H, N, O, P, S
e Se. O LMSD contém lipídios organoarsênicos e fluorados; são registros
válidos e candidatos absurdos para um painel de plasma, e uma massa de
precursor arredondada casa com um deles com toda a boa vontade.

## Massa → lipídio

Digite um m/z, escolha o aduto, defina uma tolerância em ppm ou Da e
**Search LIPID MAPS**. Os resultados são agrupados **por espécie, depois por
estrutura**: uma espécie — `PC 34:1`, digamos — com os isômeros que
compartilham a sua fórmula listados abaixo, porque uma massa não consegue
separá-los e uma lista que fingisse o contrário estaria afirmando mais do
que foi medido. Cada linha carrega a fórmula, o erro em mDa e em ppm, o
LM_ID e o **aduto** em que foi encontrada; a dica de contexto sobre a espécie
dá o nome sistemático, e a que fica sobre o aduto diz o que aquele aduto faz
quando o íon se quebra.

A caixa Adduct começa em **every adduct**, a sua primeira entrada: a massa
é então buscada em cada aduto que a polaridade do canal permite. É o padrão honesto
para uma massa medida, porque qual íon o número *é* é justamente a pergunta —
876,8015 de uma corrida DIA de fígado responde uma espécie, `TG 52:2`,
C55H102O6, como `[M+NH4]+` a +0,0 ppm e 51 estruturas, e o mesmo número
buscado como `[M+H]+` não responde nada. Um espectro de produtos então
ordena o que a massa sozinha não separa: ver *Explain*, abaixo.

Clicar com o botão direito em um pico do espectro e escolher **Find formula
for this peak** manda a sua massa para cá tanto quanto para o
[[formula-finder]].

## Lipídio → massa

Digite um nome (`SM(d18:1/16:0)`, `Cer(d18:1/16:0)`) ou um LM_ID
(`LMSP03010003`) e **Find the precursor**: os registros correspondentes são
listados com fórmula e massa neutra, e selecionar um lista os seus íons —
cada aduto, o seu m/z e a sua carga. Duplo clique em um íon para usar o seu
m/z como precursor em outra parte do painel.

## Fragmentos

Dado um lipídio e uma polaridade, **Predict fragments** enumera o que a
clivagem das suas ligações deixaria. A estrutura vem do molfile do banco de
dados — uma simples tabela de conexões com coordenadas 2D, que é tudo o que
é preciso para enumerar clivagens e para desenhar uma, de modo que nenhum
toolkit de química está envolvido. Os hidrogênios, implícitos no arquivo,
são contados a partir da valência que resta em cada átomo e conferidos
contra a fórmula publicada: uma estrutura cujos hidrogênios não fecham a
conta é marcada como não confiável em vez de deixada produzir massas de
fragmento que parecem exatas e estão erradas.

Até duas ligações são cortadas de uma vez — o que um anel precisa para se
desfazer; três é uma explosão combinatória que ninguém procuraria — e cada
pedaço pode perder os pequenos neutros que a opção **losses** lista (água,
amônia e assim por diante). A tabela dá o m/z de cada fragmento, o pedaço, a
rota que o produziu, quantos cortes foram precisos e quantas outras rotas
chegam à mesma massa (**Rivals**). Um m/z **target** filtra para as rotas
que caem sobre ele.

O que isto *não* faz é dizer que clivagens de fato acontecem. Enumerar
ligações é aritmética; prever um espectro não é. A lista é o conjunto de
massas que vale a pena procurar.

## Explain

### Explicar, de uma vez

**Explain**, no topo da aba, não pergunta qual rota tentar. Ele roda todas —
o nome do composto, o LIPID MAPS neste precursor, a fórmula, e um desenho se
houver um carregado — e mostra aquela que explica a maior parte do espectro,
com todas as outras rotas listadas abaixo. As três rotas abaixo dele
continuam ali para quem quiser escolher à mão.

Ele se preenche sozinho. O precursor, a polaridade e o survey vêm do canal de
onde o espectro veio; o nome e a fórmula vêm do componente cujo precursor
este canal isola, de modo que o espectro de um padrão que o método declara
não precisa de nada digitado. O que estiver digitado nas caixas abaixo
prevalece, já que quem digitou quis dizer aquilo. Um `-d4` no nome é lido
como quatro marcações que o nome não posiciona, e cada rota recebe a
contagem que se aplica a *ela*: o ácido cólico-d4 do PubChem posiciona as
suas quatro no desenho e não precisa de nenhuma adicionada, enquanto o
`C24H40O5` ao lado dele na tabela de componentes precisa das quatro, e uma
contagem única para o espectro inteiro pula a rota da fórmula com a
afirmação verdadeira e inútil de que 430.35 não é aduto nenhum da molécula
não marcada.

A **tabela de rotas** abaixo dos candidatos é a resposta:

| Coluna | |
|---|---|
| Route | nome, LIPID MAPS, fórmula, desenho |
| Adduct | o íon que aquela rota leu no precursor |
| Explains | a parcela da intensidade do espectro que ela explica |
| Ions | quantos dos íons que ela previu foram encontrados, de quantos ofereceu |
| ppm | a que distância o precursor escrito fica dela através daquele aduto |

Clique em uma linha e a tabela de candidatos acima passa a mostrar a
resposta daquela rota. Uma rota sem nada com que trabalhar também é uma
linha, acinzentada, com o motivo na dica de contexto — *o banco LIPID MAPS
não está instalado* e *nenhuma estrutura curada fica a ±0,7 Da daquela
massa* são respostas diferentes, e uma rota simplesmente ausente da tabela
não diz nenhuma das duas.

A linha abaixo dos candidatos nomeia a rota de onde ele veio:

> from the name CA-d4 → LMST04010001 as [M+NH4]+; 430.35 is [M+NH4]+ of
> C24H36D4O5 (430.3465, +8.1 ppm); [M+H]+ would be 413.3200

**O melhor é a maior parcela, e os desempates estão declarados.** Com a mesma
parcela, um desenho ganha de uma fórmula, porque uma fórmula não tem ligações
para cortar e chegou àquela parcela com uma lista menor de previsões; depois,
um candidato cujo precursor fica dentro da precisão com que o precursor foi
escrito ganha de um que fica fora; depois, a ordem em que as rotas são
perguntadas. Nada mais decide, e nada é calculado duas vezes — a
identificação do aduto, que é onde o survey é lido e o padrão isotópico
pontuado, é feita uma vez por composição e entregue a toda rota que a pedir.

Toda rota estrutural é enumerada com os mesmos limites, até duas ligações
cortadas e até três perdas neutras, e toda rota é pontuada a 20 ppm. Ambos
são deliberados: a parcela é uma fração do mesmo espectro de qualquer modo,
então uma rota com mais cortes, ou com uma janela mais larga, ganharia uma
comparação que lhe foi dada em vez de uma que ela conquistou. Os 5 ppm na
caixa abaixo são para outra pergunta — posicionar marcações, onde um deutério
está a 1,55 mDa do hidrogênio que ele substituiu — e continuam valendo para
*Onde estão as marcações*.

#### O que ele fez em quatro infusões reais

Quatro infusões em ZenoTOF de padrões de ácidos biliares deuterados, cada
corrida inteira promediada e centroidada, o nome e a fórmula como uma tabela
de componentes os carregaria (`CA-d4`, `C24H40O5`), e um desenho só onde
havia um: o ácido cólico-d4 do PubChem, CID 16217616. Um **Explain** levou
2,6–4,7 s, contados a partir do botão.

| | Rota | Aduto | Explica | Íons | ppm |
|---|---|---|---|---|---|
| **CA-d4, CID** | **name → LMST04010001** | [M+NH4]+ | **92,0%** | 53 de 3.837 | +8,1 |
| | LIPID MAPS | [M+NH4]+ | 78,1% | 41 de 3.274 | −32,4 |
| | drawing | [M+NH4]+ | 69,7% | 35 de 1.081 | +8,1 |
| | formula | [M+NH4]+ | 24,2% | 2 de 56 | +8,1 |
| **CA-d4, EAD 22 eV** | **LIPID MAPS → LMGL03013010** | [M+2H]2+ | **95,0%** | 34 de 4.030 | −9,6 |
| | name → LMST04010001 | [M+NH4]+ | 87,3% | 33 de 3.837 | −15,1 |
| | drawing | [M+NH4]+ | 82,4% | 23 de 1.081 | −15,1 |
| | formula | [M+NH4]+ | 63,6% | 8 de 56 | −15,1 |
| **DCA-d4, CID** | **name → LMST04010040** | [M+NH4]+ | **90,6%** | 54 de 3.282 | −28,0 |
| | LIPID MAPS | [M+Na]+ | 64,3% | 35 de 2.330 | +13,9 |
| | formula | [M+NH4]+ | 17,0% | 3 de 41 | −28,0 |
| | drawing | *nenhuma estrutura carregada* | | | |
| **TDCA-d4, CID** | **name → LMST05040013** | [M+H]+ | **92,2%** | 18 de 8.463 | −18,1 |
| | LIPID MAPS | [M+Na]+ | 79,9% | 12 de 7.244 | +27,6 |
| | formula | [M+H]+ | 72,7% | 5 de 104 | −18,1 |
| | drawing | *nenhuma estrutura carregada* | | | |

A rota do nome acerta o composto nas quatro e vence em três delas: ácido
cólico, ácido desoxicólico e ácido taurodesoxicólico, cada um alcançado pela
tabela de padrões a partir da abreviação do frasco e depois desenhado a
partir do LIPID MAPS.

**A que ela perde é para o que serve a coluna Ions.** No CA-d4 sob EAD a
primeira linha é um triacilglicerol lido como um íon duplamente carregado, e
ele explica 95,0% do espectro com **4.030** massas previstas contra as 3.837
do composto certo — uma lista suficientemente longa de massas possíveis cobre
um espectro por acidente, que é a mesma coisa que esta página diz sobre
isômeros e sobre picos não explicados. Leia a parcela ao lado da contagem que
a produziu. Uma rota que ofereceu cinquenta massas e explicou a maior parte
do espectro disse alguma coisa; uma que ofereceu quatro mil não
necessariamente.

Dois dos ajustes foram escolhidos contra estes arquivos, e não argumentados.
Pontuar a 5 ppm em vez de 20 leva a rota que nomeia o composto certo de três
de quatro para uma de quatro: estes eixos ficam 4–7 ppm altos, então apertar
a janela derruba os íons do composto verdadeiro enquanto o candidato de
quatro mil íons continua cobrindo o espectro. E com uma ligação cortada em
vez de duas — o limite que a busca manual no banco usa — o composto certo
vence duas das quatro em vez de três, com a pontuação levando 0,2–0,9 s em
vez de 2,6–3,9. O segundo corte compra uma destas quatro respostas e custa
cerca de três segundos.

### Uma rota de cada vez

**Explain this spectrum** toma o espectro em tela e o precursor (preenchido
a partir do canal ativo, ou digitado), procura o precursor no LIPID MAPS,
prevê os fragmentos de cada estrutura candidata e pontua cada uma por **a
parcela da intensidade do espectro que ela explica**. Contar picos
correspondidos em vez disso premiaria um candidato que explica quarenta
pontinhos de ruído em detrimento de um que explica o pico base, o que é o
contrário do certo: um espectro de produtos é, na maior parte, um punhado de
íons que importam.

Picos abaixo de 1% do pico base não contam contra um candidato — a linha de
base de um espectro de produtos está cheia deles e nada os explica — e uma
massa prevista corresponde a uma medida dentro de 20 ppm. Os candidatos são
listados com o que cada um explica; selecionar um lista os picos
correspondidos com a sua massa medida, o erro, a rota e, onde várias perdas
formam uma escada, a escada. Os picos não explicados também são reportados:
vários candidatos costumam explicar os mesmos picos, porque isômeros
fragmentam de modo parecido, e os não explicados são a parte honesta da
resposta.

No painel eles são uma contagem. No [[infusion-report]] eles são uma tabela,
e cada linha carrega o melhor de três palpites sobre o que o pico pode ser —
um contaminante conhecido ou um agregado de solvente, um satélite de um íon
que *foi* correspondido, ou uma composição montada com nada além dos
próprios átomos do íon precursor, já que um fragmento não pode carregar um
átomo que o precursor não tem. O último é o motivo de a tabela valer a pena:
restringir as faixas de elementos a este precursor transforma uma busca de
fórmula de "que massa poderia ser esta" em "o que este precursor poderia ter
deixado aqui", e uma massa sem resposta passa a ser uma afirmação — não é um
pedaço deste composto. Nas infusões reais de ácidos biliares ela nomeou a
taurina protonada no conjugado de taurina e o cátion radical do benzeno num
espectro EAD, os dois listados pelo painel como massas nuas; os números
estão naquela página.

A caixa **Adduct** ao lado do precursor diz qual íon o precursor é, e é usada
duas vezes: para procurar a massa no banco de dados, e para dizer qual é o
íon precursor de cada candidato e o que os seus fragmentos carregam.

Deixada em **from the precursor**, como ela começa, o banco de dados é
buscado em cada aduto que a polaridade do canal permite e cada candidato
carrega aquele que o encontrou — a coluna **Adduct**, com o comportamento
daquele aduto na sua dica de contexto, e **ppm**, a que distância o precursor
escrito fica daquele candidato através daquele aduto. A linha abaixo da
tabela diz isso em palavras, a mesma frase que o caminho da estrutura
própria escreve, vinda do mesmo código:

> 703.6 is [M+H]+ of C39H79N2O6P (703.5749, +35.7 ppm); [M+NH4]+ would be
> 720.6014

Selecionar outro candidato reescreve a linha, porque neste caminho cada
linha pode ter sido encontrada em um aduto diferente. Escolher um aduto à
mão busca apenas aquele. Ver *Adutos*, abaixo: não é um detalhe, já que um
precursor amoniado pontuado como protonado prevê cada fragmento a 17 Da de
qualquer coisa no espectro.

**Explain spectrum** na barra de ferramentas Processing faz o mesmo a partir
do cromatograma: toma o espectro do scan atual e o precursor do seu canal.

### Os satélites de um fragmento encontrado

Um valor em ppm não consegue dizer que um pico encontrado é a composição
alegada. Um isóbaro está dentro da tolerância por definição, e a 20 ppm um
espectro de produtos oferece vários deles. O **satélite isotópico** do
próprio pico consegue: um fragmento com vinte carbonos deve um M+1 de cerca
de 22% de si mesmo, e um pico que mostra esse satélite em proporção é um
pico com aproximadamente esse número de carbonos.

Essa é a verificação que o survey já faz sobre o *precursor* — ver *O survey
confirma*, abaixo — feita agora a cada **fragmento** encontrado, no próprio
espectro de produtos. A coluna **Isotopes** da tabela de candidatos carrega a
contagem, e a sua dica de contexto, a frase:

> 2 of 2 agree
>
> 2 of 2 matched ion(s) have a satellite that agrees, 0 disagree, 0
> unmeasurable.

São quatro veredictos, e o último é o que mais importa:

- **agrees** — o M+1, e o M+2 quando existe, estão em proporção.
- **disagrees** — não estão. O achado é **mantido e impresso**: um satélite
  inesperado tem causas inocentes (um vizinho coeluindo a um milidalton de
  distância, um detector no topo da sua faixa) além das culpadas, e a
  classificação não é o lugar de decidir entre elas.
- **no satellite measurable** — o M+1 previsto do próprio íon seria menor do
  que este espectro consegue mostrar, ou outro íon previsto está dentro da
  janela onde o M+1 dele deveria estar. Nenhum dos dois é uma discordância, e
  dizer isso é justamente o ponto.
- **none expected: precursor isolated monoisotopically** — o quadrupolo
  passou o precursor monoisotópico e mais nada, então nenhum fragmento deste
  espectro veio de uma molécula com um 13C dentro. Não há satélite a
  procurar, e uma coluna de discordâncias seria um retrato da seleção do
  próprio instrumento, não uma evidência sobre a estrutura.

Qual deles vale é medido antes de qualquer fragmento ser lido, sobre o
**próprio M+1 do precursor** no mesmo espectro — do mesmo jeito que a
solução da pureza isotópica e o termo de cross-talk da infusão já se recusam
a si mesmos. Quando a energia de colisão consumiu o precursor, o **fragmento
encontrado mais intenso** responde à mesma pergunta, e a frase diz qual dos
dois foi lido.

#### O que os dados dizem

A medição que motivou tudo isto. Nas sete infusões de ácidos biliares no
ZenoTOF 7600 — aquisições de produtos, sem survey nenhum — o M+1 transmitido
do precursor é **0,00 a 0,26% do que a composição dele exige**, que é 26,4 a
30,0%:

| Infusão | CE | lido em | altura | M+1 medido | previsto | transmitido |
|---|---|---|---|---|---|---|
| CA-d4 | 45 | fragmento mais intenso | 5.638 | 0,068% | 26,4% | 0,26% |
| CA-d4 | 22 | precursor | 9.415 | 0,000% | 27,0% | 0,00% |
| CA-d4 | 12 | precursor | 12.271 | 0,000% | 27,0% | 0,00% |
| DCA-d4 | 40 | fragmento mais intenso | 3.019 | 0,060% | 26,4% | 0,23% |
| DCA-d4 | 22 | precursor | 5.582 | 0,000% | 26,9% | 0,00% |
| TDCA-d4 | 30 | precursor | 123 | 0,000% | 30,0% | 0,00% |
| TDCA-d4 | 22 | precursor | 5.235 | 0,000% | 30,0% | 0,00% |

Por isso os **34 íons encontrados nas sete** leem *none expected*, e nenhum
deles é chamado de discordância. Todos os 34 tiveram uma composição que pôde
ser resolvida, e **12 dos 34** têm outro íon previsto dentro da janela onde
o M+1 deles deveria estar — a mesma peça carregando mais uma marcação. Um
deutério está a 1,00628 Da do hidrogênio que substituiu, contra 1,00336 do
nêutron, então o "M+1" de um degrau `+3D` é o vizinho `+4D` dele, a 2,9 mDa:
lidos como satélite, esses doze dão M+1 de 0,96, 1,12, 2,20, 2,63, 4,51,
7,99, 8,61, 11,27, 12,44, 12,57, 19,98 e 40,54 vezes o próprio pico. São
imensuráveis, e dizem isso.

A pergunta que uma aquisição de produtos não responde sozinha é se alguma
janela de isolamento chega a passar o M+1. Uma injeção de esfingolipídios em
TripleTOF 5600 responde, porque adquire um survey de 50–700 ao lado dos
canais de produtos. Sobre os mesmos dois scans no ápice de SM(d18:1/12:0):

| | precursor | altura | M+1 medido | previsto | transmitido |
|---|---|---|---|---|---|
| o canal de produtos 647.5 | 647,5121 | 1.064 | 0,31% | 39,6% | **0,8%** |
| o survey, os mesmos scans | 647,5103 | 58.462 | 29,23% | 39,6% | **73,7%** |

A janela não passa: duas ordens de grandeza entre as duas leituras do mesmo
íon na mesma aquisição. No survey a mesma regra encontra então para que
serve — os dois íons encontrados **concordam**, a 0,70 e 0,99 — e no canal de
produtos os dois leem *none expected*. O canal da ceramida da mesma injeção
mostra o terceiro veredicto: um pico base de 163 contagens, cujo precursor
teria um M+1 de 4 contagens contra as 10 que aquele espectro consegue
mostrar, então nada é afirmado em nenhuma direção.

Uma composição é o que um satélite precisa para ser previsto, e um íon
previsto não carrega uma simplesmente: uma clivagem guarda a fórmula da peça
com os hidrogênios que ela moveu e os neutros que ela depois perdeu anotados
ao lado, enquanto uma forma do precursor guarda a composição que ela já é,
com os átomos do aduto por fora. Então cada leitura é proposta e convertida
de volta em m/z, e só é aceita quando reproduz a massa do próprio íon. Nos
mesmos dois espectros de CA-d4 pontuados contra o desenho do PubChem em vez
de contra uma fórmula — 882 íons previstos, 20 encontrados — todos os 20
voltaram com uma composição, e o isolamento foi lido no precursor a 22 eV e
no fragmento mais intenso a 45, onde o precursor já se foi.

Uma coisa que um satélite concordante não faz é confirmar a rota. Naquele
survey o segundo íon concordante é `[M+H-2CO-CO2]+` em 547,5229, que pontua
0,99 porque é *algum* íon com aproximadamente aquele número de carbonos — e
é, seja lá o que o produziu. O satélite limita a composição; a escada e os
picos não explicados são o que argumenta pela rota.

### Uma estrutura ou fórmula de sua autoria

O banco de dados não contém tudo — não um ácido biliar deuterado comprado
como padrão interno, não um composto desenhado na semana passada. O grupo
sob o botão Explain aceita uma de duas coisas:

- **Uma estrutura**, de um arquivo `.mol` ou `.sdf` (o download do PubChem, o
  arquivo salvo de um programa de desenho; MDL V2000). Ela recebe o
  tratamento completo: as clivagens e as perdas do desenho, pontuadas contra
  o espectro exatamente como um registro do banco de dados é. Um desenho que
  posiciona as suas marcações — um bloco `M  ISO`, ou átomos D explícitos,
  que é como a estrutura de um padrão d4 fornecida por um fabricante é
  escrita — não precisa de mais nada; os seus fragmentos saem nas massas
  certas por si sós. Hidrogênios escritos como átomos próprios são
  incorporados aos átomos que os carregam: o PubChem escreve todos os
  quarenta de um ácido biliar, e cortar quarenta ligações C–H só produz
  quarenta pedaços que diferem da molécula inteira por um hidrogênio — o que
  um deslocamento de hidrogênio já cobre. A fórmula não muda com isso, e o
  deutério que o desenho posiciona permanece no átomo em que foi desenhado.
- **Uma fórmula**, quando não há desenho. Uma fórmula não tem ligações a
  cortar, de modo que o que se pode dizer é o íon precursor e a escada de
  pequenas perdas neutras que ele poderia sofrer — água, amônia, monóxido e
  dióxido de carbono, ácido fórmico, até três de uma vez, cada uma apenas
  onde a fórmula tem os átomos para ela. Menos do que uma estrutura dá, e
  dito que é.
- **Um nome**, quando não há nem uma nem outra. Ele é procurado em uma
  tabela de padrões, depois no LIPID MAPS, depois na notação abreviada de
  lipídios, e traz de volta uma fórmula, o desenho do banco de dados quando
  há um, e a contagem de marcações que um `-d4` no fim declara. Ver *Um nome
  de sua autoria*, abaixo.

Seja qual for das três, a caixa **Adduct** diz como o precursor foi
ionizado, e no automático lê isso do próprio precursor escrito do canal. Não
é um detalhe: um precursor amoniado pontuado como um protonado prevê cada
fragmento a 17 Da de qualquer coisa que esteja no espectro. Ver *Adutos*,
abaixo.

**Deuterium, unplaced** (deutério, não posicionado) serve para um desenho ou
fórmula do composto *não marcado* e um padrão cujas marcações estão em algum
lugar desconhecido. Cada fragmento é então oferecido carregando de nenhuma a
todas as marcações, e o espectro diz quantas ele reteve: uma correspondência
em +2.0126 é um pedaço que reteve duas, escrito `+2D` na sua rota. Enumerar
cada posicionamento seria honesto e inútil; enumerar a contagem é o que o
espectro pode confirmar. Um pedaço nunca recebe mais marcações do que
hidrogênios que tem.

**Limits** define até onde a enumeração vai e quão perto uma massa precisa
estar. Dois cortes, porque um esteroide cortado uma vez continua em uma só
peça; três perdas, porque um ácido biliar tri-hidroxilado perde três águas e
o íon de três águas é o seu pico base. A tolerância é de **± 5 ppm** em vez
dos 20 ppm com que um candidato do banco de dados é pontuado, e isso não é
questão de gosto — ver abaixo.

O resultado cai nas mesmas duas tabelas que um candidato do banco de dados —
a parcela do espectro explicada, os picos correspondidos com as suas rotas e
escadas — e os picos não explicados continuam sendo a metade honesta disso.

### Onde estão as marcações

Um pedaço que reteve duas de quatro marcações contém duas delas; um pedaço
que não reteve nenhuma não contém nenhuma. Todo íon correspondido é portanto
uma afirmação sobre *quais* hidrogênios são pesados, e não apenas sobre
quantos, e o bloco sob as tabelas reúne essas afirmações. Um posicionamento
é um conjunto de posições, uma por marcação; um posicionamento sobrevive a
um íon quando as marcações que ele coloca dentro daquele pedaço são o número
que o pedaço reteve. O que volta é quantos posicionamentos sobrevivem, em
quais posições todos os sobreviventes concordam, e quais posições nada
separa.

Posições que as observações não conseguem distinguir são agrupadas, porque
um empate entre dois hidrogênios que estão dentro exatamente dos mesmos
fragmentos não é um resultado. O ácido cólico oferece 21 posições ligadas a
carbono e **8.391** maneiras de colocar quatro marcações sobre elas.

Três regras decidem o que conta, e as três foram medidas, não supostas:

- **Um hidrogênio ligado a oxigênio ou nitrogênio não é oferecido.** Ele
  troca com o solvente muito antes de o espectro ser registrado. A caixa de
  seleção devolve essas posições para quem quiser ver o que o espectro diria
  se não trocasse.
- **Uma perda neutra pode levar uma marcação consigo.** Uma desidratação sai
  com o hidrogênio da própria hidroxila e mais um do carbono ao lado, de
  modo que um íon que perdeu água limita a contagem em vez de fixá-la; uma
  descarboxilação não leva hidrogênio ligado a carbono e por isso diz
  exatamente. Isso é medido: no espectro CID abaixo, o pico base em
  m/z 359,2870 é a perda de três águas retendo todas as quatro marcações, e
  358,2808 ao lado dele, a 12,5%, é o mesmo íon retendo três. Os dois estão a
  1,0062 de distância, que é o 1,00628 de um deutério contra um hidrogênio e
  não o 1,00783 de um hidrogênio contra nada.
- **Um hidrogênio que o pedaço perdeu na clivagem também pode ter sido uma
  marcação.** Supor o contrário é mais arrumado e é errado: com essa
  suposição, um íon escrito `-2H` não pode ter perdido uma marcação, e no
  espectro abaixo o posicionamento verdadeiro passava a satisfazer 43% das
  evidências em vez de 78% e era superado por 96% das possibilidades em vez
  de 79% — e o bloco apontava uma metila sem marcação alguma como posição em
  que todos os sobreviventes concordavam.

**Um pico só conta quando diz um número.** Um deutério é 1,55 mDa mais
pesado do que o hidrogênio que substituiu, de modo que o mesmo pedaço com
uma marcação a mais e um hidrogênio a menos fica a 1,55 mDa dali — em
m/z 359 isso são 4,3 ppm. Uma janela mais larga do que essa diferença contém
os dois, e a correspondência passa a ser decidida por qual está mais perto,
o que é cara ou coroa; esses íons são contados e deixados de fora. No
espectro do ácido cólico-d4, dos íons correspondidos deixados de fora por
esse motivo: 48 de 53 a 20 ppm, 24 de 47 a 10 ppm, 4 de 26 a 5 ppm, nenhum
de 19 a 3 ppm. É por isso que a tolerância aqui é de 5 ppm por padrão.

### O que ele fez com um padrão real

Ácido cólico-d4 infundido em um ZenoTOF 7600 — o canal de íons-produto do
aduto de amônio em m/z 430,35, CE 45, com toda a corrida de 1,98 min
promediada (473 scans, plana do início ao fim, uma infusão pelo teste em
[[direct-infusion]]) e centroidada: 811 centroides, 60 picos acima de 1% do
pico base. A estrutura é o ácido cólico do PubChem (CID 221493) com quatro
marcações não posicionadas; a resposta é conhecida, porque o PubChem também
tem o padrão marcado (CID 16217616), cujo bloco `M  ISO` coloca as quatro em
C2 e C4 — de cada lado da hidroxila em C3, no anel A.

| | CID, CE 45 | EAD, 22 eV |
|---|---|---|
| picos explicados | 59,0% | 60,7% |
| íons correspondidos | 26 | 24 |
| destes, dizendo uma contagem | 22 | 15 |
| deixados de fora como indecisos | 4 | 9 |
| posicionamentos empatados no topo | 580 | 2.625 |
| de 8.391, com | 93% das evidências | 100% |
| posições em que todos concordam | nenhuma | nenhuma |
| o posicionamento do fabricante | 78% das evidências | 92% |
| posicionamentos que o superam | 6.589 (79%) | 6.224 (74%) |

A coluna EAD é uma segunda infusão do mesmo padrão, a 22 eV, lida do mesmo
modo: 146 scans em 0,61 min, 424 centroides, 42 picos.

**Ele não recupera a resposta.** Sob CID os melhores posicionamentos colocam
duas marcações em uma metila e uma em um carbono ao lado de outra hidroxila;
sob EAD elas se espalham por quatro posições no meio do sistema de anéis.
Nenhum dos dois é o anel A, e o 2,2,4,4 do fabricante é superado por três
quartos das possibilidades nas duas ativações. Leia o empate — 580 e 2.625 posicionamentos — como o
espectro limitando as marcações em vez de posicioná-las, que é o que o bloco
diz quando reporta que nenhuma posição está em todos eles. A razão é que uma
massa correspondida não é uma atribuição resolvida: um pedaço alcançado por
dois cortes e três perdas é uma entre milhares de possibilidades
aritméticas, e o posicionamento que melhor se ajusta é aquele que
racionaliza as que o correspondedor escolheu.

Recebendo em vez disso o desenho marcado, sem nada a inferir, os mesmos
espectros concordam com ele: todo íon que o posicionamento prevê está onde
deveria estar, 100% das evidências nos dois arquivos. O que isso custa é
alcance — o desenho marcado explica 35,5% do espectro CID contra os 59,0% da
versão não posicionada, porque a versão não posicionada recebe cinco vezes
mais massas para corresponder. E a discordância é reportada em vez de
escondida: três picos no espectro CID e dois no de EAD correspondem a um
pedaço que o posicionamento prevê *carregando um número diferente de
marcações*, um deles o 358,2836 já citado acima.

O que o espectro diz com clareza é que uma desidratação leva uma marcação.
Sob EAD a escada está completa, e a parcela de cada degrau que perdeu uma
cresce à medida que as hidroxilas saem: 5,2% no precursor, 5,0% após uma
água, 8,0% após duas e 104% após três — o íon que perdeu uma marcação é
então maior do que o que reteve todas. Qual hidroxila saiu em qual degrau
posicionaria as marcações; a enumeração ainda não acompanha isso.

## A margem

Uma parcela sozinha não se lê. "Explica 63,6%" não diz nada enquanto outra
coisa não tiver sido pontuada sobre os mesmos picos: uma lista de massas
previstas suficientemente longa cobre um espectro por acaso, e o tamanho
dessa lista depende do composto, não da evidência. Por isso toda explicação
passa a trazer a sua **margem** — o que o composto escolhido explica, menos
o que explica o melhor dos seus impostores mais próximos — na linha sob as
tabelas, na seção por composto do [[infusion-report]] e como uma coluna da
aba Infusions:

> explains 63.6%; the best of 17 neighbour(s) (TG 17:1/18:4/18:4 as
> [M+2H]2+) explains 21.7%: a margin of 41.9 points

Os impostores são os registros do LIPID MAPS que cabem no precursor
**escrito** em qualquer aduto que a polaridade do canal permita — o mesmo
conjunto de onde sai a tabela ranqueada, com a mesma comporta — com dois
tipos de fora:

- **O próprio composto**, em qualquer aduto.
- **Qualquer coisa com a mesma fórmula.** Mesma fórmula, mesmo precursor,
  mesmas perdas neutras: a mesma aritmética, e contraste nenhum. Pontuá-la
  colocaria o número do próprio composto escolhido na coluna do impostor e
  reportaria margem zero para um espectro que nunca esteve em dúvida. Em
  lipidômica esse é o caso ordinário e não a exceção — cada um dos quatro
  esfingolipídios nomeados abaixo tem um ou dois — de modo que a frase diz
  quantos ficaram de fora, e uma margem medida sobre dezesseis vizinhos
  quando dezoito foram encontrados não se apresenta como medida sobre
  dezoito.

Cada impostor é pontuado **do mesmo modo que o composto foi**: uma fórmula
contra fórmulas, um desenho contra desenhos. Isso não é asseio. Pontuado ao
contrário — as 56 massas previstas de um ácido biliar contra estruturas do
LIPID MAPS oferecendo de 700 a 2.900 cada — o impostor venceu em cinco das
seis infusões reais de ácidos biliares, por até 33 pontos, em espectros nos
quais nada estava errado. Uma lista de duas mil massas cobre por acaso um
espectro de sessenta picos. Enumerados do mesmo jeito, o composto verdadeiro
venceu nas seis.

Abaixo de **10 pontos** a margem é chamada de *thin* (estreita), e a frase
diz que o espectro não distingue os dois compostos. Dez é onde está a lacuna
nos onze espectros reais em que isso foi medido.

### O que ela diz em dados reais

Seis infusões de ácidos biliares deuterados, cada uma explicada a partir da
sua fórmula pelo aduto que o precursor escrito do canal nomeia:

| Infusão | Escrito | Explica | Melhor impostor | Ele explica | Margem |
|---|---|---|---|---|---|
| CA-d4, CID 45 eV | 430,35 | 24,2% | TG 17:1/18:4/18:4 `[M+2H]2+` | 0,0% | **+24,2** |
| CA-d4, EAD 22 eV | 430,34 | 63,6% | TG 17:1/18:4/18:4 `[M+2H]2+` | 21,7% | **+41,9** |
| DCA-d4, CID 40 eV | 414,34 | 17,0% | 3-hidroxipalmitoleoilcarnitina `[M+H]+` | 1,6% | **+15,3** |
| DCA-d4, EAD 22 eV | 414,34 | 70,4% | ácido wuhânico `[M+NH4]+` | 56,5% | **+13,9** |
| TDCA-d4, CID 30 eV | 504,32 | 72,7% | uma espirostenona `[M+NH4]+` | 1,5% | **+71,2** |
| TDCA-d4, EAD 22 eV | 504,32 | 78,4% | PC O-16:0/0:0 `[M+Na]+` | 72,3% | **+6,1** *thin* |

E os quatro esfingolipídios nomeados de uma injeção de um lote de 26,
explicados a partir dos seus desenhos do LIPID MAPS, onde os precursores
escritos ficam de 36 a 264 ppm dos próprios compostos:

| Canal | Composto | Explica | Melhor impostor | Ele explica | Margem |
|---|---|---|---|---|---|
| 703,60 | SM(d18:1/16:0) | 31,9% | PG 13:0/18:3 `[M+H]+` | 15,7% | **+16,2** |
| 731,70 | SM(d18:1/18:0) | 19,4% | PA 16:0/22:1 `[M+H]+` | 17,3% | **+2,1** *thin* |
| 538,60 | Cer(d18:1/16:0) | 9,5% | PE 22:0/0:0 `[M+H]+` | 12,4% | **−3,0** *thin* |
| 648,80 | Cer(d18:1/24:1) | 9,2% | calixosídeo `[M+H]+` | 7,1% | **+2,1** *thin* |

Essas quatro linhas devem ser lidas como foram pensadas. A ceramida em 538,6
está naquele frasco — é um componente do método, com tempo de retenção, e o
lote foi quantificado sobre ela — mas *este espectro* não a identifica: três
lisofosfolipídios de outra fórmula explicam mais dos mesmos picos. A margem
não diz que o composto está errado. Ela diz que o composto não foi
distinguido aqui, e que o que sustenta a atribuição tem de vir de outro
lugar: o tempo de retenção, a massa exata da varredura de survey, um
registro de [[spectral-library]].

O mesmo vale para o TDCA-d4 com 6,1 pontos. Aquilo é um padrão puro
pulverizado de um frasco, e a sinalização continua certa: ele é conhecido
pelo rótulo, não pelo espectro, e antes de a margem ser medida nada na
página dizia isso.

Uma margem é medida sobre 16 a 29 vizinhos nesses espectros e custa menos de
meio segundo — um décimo disso pela rota da fórmula.

## Adutos

Um precursor é uma molécula mais o que quer que a tenha carregado, e qual
deles decide todas as massas abaixo. A infusão em ZenoTOF contra a qual isto
foi construído escreve o seu canal de íons-produto em **430,35**, e o ácido
cólico-d4 pesa 412,31: o número é o aduto de *amônio*, `[M+NH4]+`, e a sua
forma protonada é 413,32 — dezessete daltons abaixo. Pontuado como
`[M+H]+`, um desenho prevê um precursor que não está no espectro e uma
escada de águas deslocada de todos os degraus que estão; pontuado como
`[M+NH4]+` por uma aritmética que simplesmente soma 18,03 a tudo, ele prevê
`[M+NH4-H2O]+`, que não é espécie alguma. Ambos falham, e nenhum diz por
quê.

Por isso um aduto aqui carrega o que faz quando o íon se quebra, e os três
tipos se comportam de modos diferentes:

- **Um aduto de próton** — `[M+H]+`, `[M-H]-`, `[M+2H]2+` — mantém a sua
  carga sobre o pedaço que a segurar. Os fragmentos são os pedaços
  protonados, ou desprotonados.
- **Um aduto lábil** — `[M+NH4]+`, e em modo negativo `[M+HCOO]-`,
  `[M+CH3COO]-`, `[M+Cl]-` — é seguro por ligações de hidrogênio e por nada
  mais forte. Ele sai como um neutro (amônia, ácido fórmico, ácido acético,
  cloreto de hidrogênio) e entrega um próton no caminho, de modo que o íon
  que fragmenta é `[M+H]+` ou `[M-H]-`. O precursor é visto intacto, depois
  como a forma protonada, e a escada de perdas pende *dessa*: `[M+NH4]+`,
  `[M+H]+ (-NH3)`, `[M+H-H2O]+`, `[M+H-2H2O]+`, `[M+H-3H2O]+`. Nada retém o
  amônio enquanto perde uma hidroxila, porque a amônia já foi embora havia
  muito.
- **Um aduto metálico** — `[M+Na]+`, `[M+K]+` — é uma ligação de
  coordenação, e o metal fica no pedaço que retém o sítio coordenante, o que
  a aritmética não tem como saber. Os dois são oferecidos, `[pedaço+Na]+` e
  `[pedaço+H]+`, e cada íon diz qual foi assumido.

Os íons do precursor são escritos como a forma que são — `[M+NH4]+`,
`[M+H]+ (-NH3)`, `[M+H-3H2O]+`, com `+3D` depois quando o pedaço reteve três
de quatro marcações. Um *pedaço* continua escrito como o que sobrou e como
chegou lá, `C23H37O3 -H2O`, porque essa é a única descrição que uma clivagem
tem.

### Qual aduto o precursor é

Deixada em **from the precursor**, a caixa Adduct sob *Explain with this*
descobre sozinha: cada aduto da fórmula é medido contra o precursor escrito
do canal, a polaridade do canal descarta o outro sinal, e a linha sob o
botão diz qual é e a que distância —

> 430.35 is [M+NH4]+ of C24H36D4O5 (430.3465, +8.1 ppm); [M+H]+ would be
> 413.3200

Um aduto tem de cair dentro de **0,05 Da**, alargado para a precisão com que
o precursor foi escrito quando esta for mais grosseira. 0,05 é medido e não
escolhido: nas nove infusões de ácidos biliares, a pior distância entre um
precursor escrito e a massa verdadeira do seu aduto é 0,0117 Da — DCA-d4,
escrito `414.34` para um aduto de amônio de 414,3516 — porque um método de
instrumento carrega duas casas decimais e nem sempre as arredonda do mesmo
jeito; o mesmo composto está escrito `430.35` em um destes arquivos e
`430.34` em outro. 0,05 cobre isso com folga, e ainda é um cinquenta avos da
menor distância entre dois adutos de uma mesma molécula que poderiam ser
confundidos (amônio e sódio, 4,955 Da).

Onde **nada** cai dentro dela, nada é explicado. A linha nomeia os erros mais
próximos e os seus Δ, e as tabelas ficam vazias:

> Nothing explained: 430.35 is none of the adducts of C24H40O5 within
> ±0.05 Da — closest [M+Na]+ at 431.2768 (-0.9268 Da), [M+NH4]+ at 426.3214
> (+4.0286 Da).

Essa é a resposta certa, e não uma falha. A fórmula ali é o ácido cólico sem
as suas quatro marcações, e explicá-la assim mesmo preveria cada fragmento a
partir de uma molécula que o quadrupolo nunca isolou — uma tabela de rotas
erradas e confiantes, mais difícil de duvidar do que uma tabela vazia.
Digite as marcações, ou escolha o aduto à mão na mesma caixa, que então diz
*chosen by hand* em vez de fingir que foi derivado.

A polaridade vem do canal e não é digitada em lugar nenhum: um canal
positivo nunca recebe a oferta de um aduto negativo. Sem nenhum precursor
escrito não há de onde lê-lo, e a caixa Adduct no topo da aba — a que a
busca do banco de dados usa — entra no lugar, dito em voz alta.

### O survey confirma

Tudo acima é aritmética sobre um número que alguém digitou. Onde a aquisição
tem uma **varredura de survey** — um canal TOF MS de varredura completa
cobrindo o precursor — o aduto deixa de ser uma dedução e vira uma medida, e
o painel diz qual das duas você está olhando.

O survey da mesma aquisição, promediado sobre os mesmos scans que o
espectro na tela, é perguntado sobre cada candidato: a massa exata do íon,
dentro de 25 ppm e acima de 100 contagens, e o padrão isotópico da composição
do próprio íon — átomos do aduto incluídos, já que `[M+NH4]+` carrega um
nitrogênio que a molécula não tem. A linha abaixo do botão então diz

> 647.5 is [M+H]+ of C35H71N2O6P (647.5123, −18.9 ppm); [M+NH4]+ would be
> 664.5388; confirmed by the survey: 647.5112, −1.6 ppm, isotopes agree, and
> the survey also shows [M+Na]+ 13%, [M+K]+ 0%

ou, quando não confirma,

> …; the survey does not show it (the nearest peak is +69.9 ppm away, past
> ±25), so it is chosen from the written mass alone

A segunda cláusula é o ponto. Uma varredura de íons produto não pode
verificar isto de jeito nenhum: o Q1 deixou passar uma massa e jogou fora os
satélites isotópicos junto com todo o resto, de modo que o espectro na tela
não tem padrão para ler. As nove infusões de ácidos biliares em mãos foram
adquiridas só como varreduras de íons produto, e nelas esta frase diz *no
survey scan covering 430.35, so nothing independent says which ion it is* —
que é o que o aduto sempre foi ali, agora escrito.

**O mapa vale tanto quanto a resposta.** Um survey costuma mostrar um
composto como vários íons ao mesmo tempo, e cada um é reportado com sua
altura como fração do mais forte: no lote de esfingolipídios tanto a
esfingomielina quanto a ceramida C16 ficam em cerca de `[M+H]+` 100%,
`[M+Na]+` 13%. Um oitavo do sinal está num canal que ninguém adquiriu, e um
composto cujo aduto de sódio seja o maior será quantificado mal por quem
assumir o contrário.

**O padrão decide o que a massa não decide.** Duas coisas podem ficar numa
mesma massa: um íon, e o M+1 de algo um dalton mais leve. O `[M+NH4]+` da
ceramida acima está a 21.5 ppm — dentro dos 25 ppm que dizem "o mesmo íon" —
e tem 170 contagens, acima das 100 que dizem "mensurável"; seu M+1 e seu M+2
voltam a 1.00 e 1.00 do seu M, que é ruído plano e não um padrão isotópico, e
ele fica em último. Um padrão d4 e sua impureza d3, a 1.0063 Da um do outro,
são o mesmo problema ao contrário: os dois estão na massa dentro de 1 ppm, e
só o padrão — 0.97 contra 0.06 — diz de qual deles o pico é.

Os números, os dois compostos reais e o que o M+2 de um lipídio de fato
contém estão em [[accurate-precursor]].

### Um registro do banco diz qual aduto o encontrou

O mesmo modelo roda no caminho do banco de dados, de modo que um
triacilglicerol anotado como `[M+NH4]+` é pontuado com o amônio intacto, o
`[M+H]+` que ele entrega e a escada pendurada n*esse*, com os seus íons de
diacilglicerol carregando um próton; um candidato `[M+Na]+` oferece os dois
carregadores. É o caminho da estrutura própria com o desenho tirado do LMSD
em vez do disco — uma enumeração, uma pontuação, uma frase.

O que o caminho do registro precisa e o da estrutura própria não é um
**portão**. Um canal de íons-produto é procurado sobre a janela de
isolamento, meio dalton, porque um método escreve o seu precursor
arredondado — 538,6 para uma ceramida cujo precursor é 538,52. A 700 Da meio
dalton são 700 ppm e cabem centenas de espécies, então rodar cinco adutos
sobre ela multiplica os candidatos que explicam um espectro ruidoso por
acaso. Um aduto que não seja o do próton precisa portanto *nomear* o
precursor — os mesmos ±0,05 Da acima — enquanto o aduto do próton fica com a
janela inteira, porque é a leitura que o método escreveu e não precisa ser
identificada.

Medido nos quatro compostos nomeados do lote de esfingolipídios, corrida
inteira média e centroidada, e na janela DIA do ZenoTOF que contém o
TG 52:2:

| canal | composto | como [M+H]+ | todo aduto, com portão |
|---|---|---|---|
| 703,6 | SM(d18:1/16:0) | posição 1, 31,9%, 6 de 885 | posição 1, 31,9%, 6 de 885 |
| 538,6 | Cer(d18:1/16:0) | posição 4, 9,5%, 6 de 779 | posição 4, 9,5%, 6 de 779 |
| 648,8 | Cer(d18:1/24:1) | posição 1, 9,2%, 6 de 1.153 | posição 1, 9,2%, 6 de 1.153 |
| 731,7 | SM(d18:1/18:0) | posição 1, 19,4%, 4 de 968 | posição 1, 19,4%, 4 de 968 |
| 876,80 | TG 52:2 | não listado | posição 2, 24,0%, 9 de 1.123 |

Os quatro esfingolipídios não se movem, e é para isso que o portão serve: os
seus precursores escritos ficam de 36 a 264 ppm dos próprios compostos, de
modo que nenhuma regra de massa consegue promovê-los — e nenhuma deveria
rebaixá-los. Sem portão eles foram para as posições 1, 5, 5 e 3, com as
novas primeiras linhas sendo um glicoesfingolipídio de carga dupla a
−171 ppm e uma ceramida potassiada a +356 ppm, cada uma oferecendo de duas a
três vezes mais íons previstos.

O triacilglicerol é a razão do portão existir. Uma janela DIA em 876,80
buscada como `[M+H]+` não lista o `TG 52:2` de jeito nenhum — ele não é um
lipídio naquele aduto, e o melhor candidato é uma fosfatidilserina que
explica 7,7%. Buscada em todos os adutos, ele volta a −1,7 ppm explicando
24,0% do espectro, com o `[M+NH4]+` intacto em 876,8051 (+4,2 ppm) e os íons
de diacilglicerol carregando prótons: 577,5219 (+4,9), 603,5363 (+2,6),
605,5520 (+2,8). Acima dele fica uma ceramida potassiada com 3.291 íons
previstos explicando 43,2% a +25,0 ppm — a ressalva da lista-longa-por-acaso
que esta página não para de fazer, e a coluna ppm é o que separa as duas por
um fator de quinze. Uma busca leva de 0,2 a 0,8 s de qualquer modo.

### O que fez nas infusões reais

Três padrões de ácidos biliares infundidos em um ZenoTOF 7600 em modo
**positivo**, a corrida inteira promediada e centroidada, pontuados a
±10 ppm. *Antes* são os mesmos arquivos pelo mesmo botão com o aduto que o
canal declara, que era tudo o que se podia pedir dele:

| infusão | escrito | lido como | antes | agora |
|---|---|---|---|---|
| CA-d4, CID 45 eV | 430,35 | [M+NH4]+, +8,1 ppm | 0 de 31, 0,0% | 2 de 56, 24,2% |
| CA-d4, EAD 22 eV | 430,34 | [M+NH4]+, −15,1 ppm | 1 de 31, 21,7% | 8 de 56, 63,6% |
| CA-d4, EAD 12 eV | 430,34 | [M+NH4]+, −15,1 ppm | 1 de 31, 82,3% | 3 de 56, 85,0% |
| DCA-d4, CID 40 eV | 414,34 | [M+NH4]+, −28,0 ppm | 0 de 25, 0,0% | 3 de 41, 17,1% |
| DCA-d4, EAD 22 eV | 414,34 | [M+NH4]+, −28,0 ppm | 1 de 25, 15,8% | 7 de 41, 44,4% |
| TDCA-d4, CID 30 eV | 504,32 | [M+H]+, −18,1 ppm | 3 de 50, 66,5% | 4 de 104, 72,1% |
| TDCA-d4, EAD 22 eV | 504,32 | [M+H]+, −18,1 ppm | 3 de 50, 71,3% | 5 de 104, 78,4% |

Acertar no palpite também não salvava: o mesmo espectro EAD de CA-d4
pontuado como `[M+H]+` dava 4 de 31 e 34,2%, porque a escada era então
prevista e o precursor — 98% do pico base — não. O TDCA-d4 *é* uma molécula
protonada, e melhora pelo outro motivo desta página: marcações escritas
dentro da fórmula agora saem junto com a água, como as não posicionadas
sempre saíram.

No CA-d4 sob EAD a 22 eV a escada inteira é explicada, cada degrau duas
vezes:

| | medido | rota |
|---|---|---|
| precursor | 430,3489 | `[M+NH4]+ +4D` |
| perde a amônia | 413,3217 | `[M+H]+ (-NH3) +4D` |
| uma água | 395,3118 | `[M+H-H2O]+ +4D` |
| duas águas | 377,3015 | `[M+H-2H2O]+ +4D` |
| três águas | 359,2897 | `[M+H-3H2O]+ +4D` |
| uma água, com uma marcação junto | 394,3035 | `[M+H-H2O]+ +3D` |
| duas águas, uma marcação a menos | 376,2935 | `[M+H-2H2O]+ +3D` |
| três águas, uma marcação a menos | 358,2836 | `[M+H-3H2O]+ +3D` |

Sob CID a 45 eV a escada já correu até o fim: só 359,2870 e 358,2808 estão
lá acima de 1% do pico base, e ambos são explicados.

**Uma estrutura ganha exatamente um íon, e ele pode ser o pico base.** A
enumeração de clivagens já constrói pedaços protonados, que é o que os
fragmentos de um aduto lábil são, de modo que a única coisa que ela não
alcançava era o amônio intacto — e esse íon é 98% do pico base a 22 eV e o
próprio pico base a 12 eV. O ácido cólico-d4 do PubChem (CID 16217616, cujo
bloco `M  ISO` posiciona as quatro marcações), dois cortes, três perdas:

| | antes | agora |
|---|---|---|
| CID, 45 eV | 25 de 1080, 56,5% | 25 de 1081, 56,5% |
| EAD, 22 eV | 21 de 1080, 60,3% | 22 de 1081, 82,0% |
| EAD, 12 eV | 8 de 1080, 9,7% | 9 de 1081, 92,0% |

**A tolerância é a outra metade disso.** Estes espectros estão de 4,1 a
7,1 ppm altos no seu próprio eixo de massa — o erro do precursor
correspondido na tabela acima diz isso — e nos ±5 ppm em que esta caixa vem
por padrão, a maior parte da escada cai fora da janela: o CA-d4 sob EAD
22 eV dá 5 de 56 e 14,0% a 5 ppm contra 8 de 56 e 63,6% a 10. O padrão é 5
porque uma marcação está a apenas 1,55 mDa do hidrogênio que substituiu —
*Onde estão as marcações*, acima —, de modo que as duas perguntas puxam para
lados opostos: alargue para ler a escada, aperte para contar marcações, e
leia os ppm que o painel imprime no precursor para saber de que lado você
está.

## Um nome de sua autoria

A caixa **Name** resolve um composto quando não há desenho nem fórmula
digitada. Três lugares são consultados, nesta ordem:

1. **Uma tabela de padrões** comprados pelos seus nomes triviais: os ácidos
   biliares e os seus conjugados com glicina e taurina — ácidos cólico,
   desoxicólico, quenodesoxicólico, ursodesoxicólico, hiodesoxicólico e
   litocólico, e as formas glico- e tauro- de cada um — por nome ou pela
   abreviação do frasco (`TDCA`, `GCDCA`), porque nada no LIPID MAPS atende
   por `TDCA` e um `.wiff` é nomeado a partir do frasco. A tabela dá a
   grafia do LIPID MAPS, de modo que o *desenho* continua vindo do banco de
   dados; a fórmula que ela também carrega é o recurso para uma máquina sem
   banco de dados instalado. Ela para nos ácidos biliares de propósito —
   cada entrada foi conferida contra o LMSD, e uma tabela que crescesse por
   suposição seria uma lista de fórmulas que ninguém mediu.
2. **O próprio LIPID MAPS**, por nome ou LM_ID.
3. **A notação abreviada de lipídios**, que dá uma fórmula e nenhuma
   estrutura.

Um `-d4`, `_d5` ou `(d4)` no fim é lido como esse número de marcações que o
nome não posiciona — o mesmo número que a caixa *Deuterium, unplaced*
recebe — e é retirado antes de qualquer um dos três ser consultado. O `d`
dentro de `SM(d18:1/16:0)` e o `d` de `DCA` não são contagens de marcação,
porque o sufixo está ancorado no fim do nome. Um nome que nenhum dos três
conhece é declarado desconhecido, e não adivinhado.

Assim, `cholic acid-d4` digitado sobre uma infusão de CA-d4 vira ácido
cólico, C24H40O5, desenhado como `LMST04010001`, com quatro marcações não
posicionadas, ionizado como `[M+NH4]+` porque é isso que 430,35 é. Nos três
compostos, a ±10 ppm:

| | CID | EAD, 22 eV |
|---|---|---|
| `cholic acid-d4` | 48 de 3.837, 85,7% | 33 de 3.837, 87,3% |
| `DCA-d4` | 48 de 3.282, 82,2% | 29 de 3.282, 88,6% |
| `TDCA-d4` | 17 de 8.463, 91,6% | 21 de 8.463, 91,2% |

Essas parcelas são as mais altas desta página e são as que menos significam,
pelo motivo que *Onde estão as marcações* dá acima: quatro marcações não
posicionadas multiplicam por cinco as massas oferecidas, e uma lista
suficientemente longa de massas possíveis cobre um espectro por acidente.
Leia-as ao lado das do desenho com marcações posicionadas, não no lugar
delas.

## Pureza isotópica

Um frasco de ácido cólico-d4 vem com um certificado dizendo `98 átomo % D`, e
ninguém nunca mede isso. Quando o composto carrega marcações — declaradas em
*Deuterium, unplaced*, escritas na fórmula, posicionadas por um desenho, ou
lidas de um `-d4` no fim de um nome — e um aduto foi identificado, uma linha
aparece abaixo da inferência de posições:

    Isotopic purity: d4 96.2%, ≥d3 99.1% (from the precursor at 430.35; ±0.8%)

O número importa por uma razão que nada tem a ver com identidade. Um padrão
interno que é quatro por cento d3 coloca quatro por cento da sua resposta um
dálton abaixo de onde o método procura, e nenhuma outra verificação de um lote
enxerga isso.

**É uma deconvolução e não um conjunto de razões.** O íon d4 e o íon d3 estão
a 1,00628 um do outro, a massa que um deutério acrescenta sobre o hidrogênio
que substituiu. O **satélite de carbono-13 do íon d3** fica 1,00335 acima dele
— 2,9 mDa abaixo do íon d4 — e nestas aquisições o pico do precursor tem
10,2 mDa de largura a meia altura (R = 42.000 em *m/z* 430). Esses dois são um
pico só, e nenhum instrumento de laboratório comum os separa. Num esqueleto de
24 carbonos aquele satélite é 27% do que quer que a espécie de baixo tenha, de
modo que cada degrau da escada vaza para o degrau acima. O envelope é portanto
resolvido — o padrão natural de cada espécie, vindo da fórmula, ajustado como
mínimos quadrados não negativos — em vez de lido.

Ler os picos, em vez disso, não erra do jeito que se espera. Medido em
envelopes sintéticos exatos de um material d4 com 95% de pureza: as alturas
normalizadas sobre d0 – d4 dão d4 = 94,81% onde ele é 95,00%, porque o
vazamento para o d4 também infla o denominador e os dois quase se cancelam.
**O que não se cancela é a impureza**, que é o número pelo qual se compra uma
pureza: d3 contra d4 lê 4,44% onde é 4,21%, cinco por cento alto, e num
esfingolipídio d7 com 45 carbonos lê 4,63% contra 4,21%, dez por cento alto.

**Dois números, e não são o mesmo número.** `d4 96,2%` é a fração de moléculas
que carregam as quatro marcações. `98 átomo % D` é a fração das *posições
marcadas* que têm um deutério, o que conta as três que uma molécula d3 de fato
carrega — de modo que um material 96% d4 e 4% d3 é 99,0 átomo % D. A linha dá
o par de espécies; o bloco do relatório embaixo dá também o átomo por cento,
porque é isso que o certificado declara.

### Quando ela diz que não pode

A verificação é de graça, porque o padrão natural já está em mãos: **o
satélite M+1 do próprio íon totalmente marcado tem de estar lá**, mais ou
menos na fração que a fórmula exige. Quando não está, a linha diz isso em vez
de dar um número:

    Isotopic purity: not measured — the d4 ion's own M+1 satellite is 0.006%
    of it where the formula says 26.6% …

Não é um caso raro. É a cara de um **espectro de íons produto**: o quadrupolo
isolou o precursor antes da cela de colisão, e uma janela estreita o bastante
para escolher uma espécie da escada de d já jogou fora os satélites de que a
solução precisa. Medido nas nove infusões de ácidos biliares, todas espectros
de íons produto sem nenhuma varredura de survey:

| infusão | CE | M+1 medido | a fórmula diz | razão |
|---|---|---|---|---|
| CA-d4 EAD | 12 eV | 0,006% | 26,6% | 0,0002 |
| CA-d4 EAD | 22 eV | 0,028% | 26,6% | 0,0010 |
| CA-d4 CID | 45 eV | 0,095% | 26,6% | 0,0036 |
| DCA-d4 EAD | 22 eV | 0,015% | 26,5% | 0,0006 |
| DCA-d4 CID | 40 eV | 0,150% | 26,5% | 0,0057 |
| TDCA-d4 EAD | 22 eV | 0,020% | 30,0% | 0,0007 |
| TDCA-d4 CID | 30 eV | 0,206% | 30,0% | 0,0069 |

Três ordens de grandeza, em todos os arquivos, sob as duas ativações. O mesmo
limiar pega o outro caso que deveria pegar: um precursor fraco demais para que
o seu próprio satélite de 27% saia do ruído é um precursor cujo envelope seria
lido do ruído.

A recusa também é o que os próprios arquivos defendem. Na corrida de ácido
cólico-d4 a 12 eV, a transmissão um dálton *acima* do precursor é 0,0002 da
transmissão nele; uma janela de quadrupolo simétrica em torno do seu centro
passaria o degrau d3 um dálton abaixo mais ou menos na mesma fração, e os
0,763% de fato medidos ali significariam então uma fração d3 de 3.300%. Ou a
janela é assimétrica por três ordens de grandeza — caso em que os degraus
abaixo do d4 estão escalados por uma transmissão que ninguém conhece — ou o
que está naquela posição não é d3. E a segunda hipótese é o que a energia diz:
aquele resíduo é 0,763% do precursor a 12 eV, 0,328% a 22 eV e 0,067% a 45 eV,
de modo que o mesmo frasco teria 98,32%, 98,77% e 98,98% de pureza conforme a
força com que o íon foi golpeado. Uma composição isotópica não faz isso. O que
está ali é um canal de fragmentação — um átomo de hidrogênio perdido da
molécula amoniada, que a EAD produz à vontade, e a 1,5 mDa de onde o d3
estaria.

**O que isto precisa é de uma varredura MS1 de survey**, ou de uma infusão em
varredura completa sem isolamento no quadrupolo à frente. Adquira um minuto de
TOF MS ao lado do canal de íons produto e a mesma linha responde.

### A escada, e por que ela é só um piso

Quando o precursor não sobreviveu à sua energia de colisão, a mesma aritmética
é oferecida no degrau totalmente marcado mais forte da escada de perdas de
água — `[M+H-3H2O]+` e o seu degrau −1D — e a linha diz *a lower bound*. Ela
responde a outra pergunta: uma desidratação pode sair com uma marcação, de
modo que uma molécula d4 que perdeu um hidrogênio hidroxílico marcado chega à
posição d3 e é contada como uma impureza que nunca esteve no frasco. Medido
nos mesmos arquivos com a verificação do satélite desligada, a escada dá
frações d4 de 36,7%, 90,1% e 85,0% para o ácido cólico-d4 a 12, 22 e 45 eV,
contra 98,3 – 99,0% dos precursores dessas mesmas aquisições — até um quinto
das moléculas totalmente marcadas deixa uma marcação para trás com a água.
Nestes arquivos a escada não consegue nem isso, porque os fragmentos herdam o
filtro de massa que os fez: o satélite M+1 do próprio degrau da escada é
0,015 – 0,63% onde a fórmula diz 26 – 30%.

### Para onde vai

A linha fica no painel; o **relatório de infusão** carrega o envelope inteiro
— cada degrau com a sua *m/z*, a sua intensidade, a sua fração do íon
totalmente marcado e a fração ajustada — com o átomo por cento embaixo, ou a
razão de não haver nenhum. Veja [[infusion-report]]. E *Add spectrum to
library…* escreve isso no registro como `Isotopic_purity`, porque um registro
guarda os seus picos acima de um por cento do pico base e um envelope
isotópico vive em décimos de um por cento: nada consegue recuperar a pureza de
um registro depois, então ela é escrita enquanto ainda é conhecida. Veja
[[spectral-library]].

## Contra uma biblioteca

A aba **Library** ao lado desta faz a outra pergunta — o que alguém
registrou a partir do composto, em vez do que a sua estrutura poderia
produzir — e vale a pena ler as duas juntas: [[spectral-library]].

## Anotar um método inteiro

**Annotate from LIPID MAPS…** na área de trabalho Method propõe uma espécie
para todo componente ainda nomeado a partir do seu precursor, usando a massa
medida na varredura de survey onde puder. Ver [[annotate-from-lipid-maps]] e
[[accurate-precursor]].

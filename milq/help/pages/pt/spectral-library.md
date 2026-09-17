---
title: Biblioteca espectral
---
A aba **Library** do [[explorer]] busca o espectro na tela contra uma
biblioteca espectral — registros do MassBank, do MoNA, do GNPS ou do NIST, ou a
biblioteca própria de um laboratório — e lista os registros que correspondem.

Ela fica ao lado de [[lipid-maps]] em vez de substituí-la. A aba *Explain* de
lá pergunta o que uma estrutura *poderia* produzir; uma biblioteca pergunta o
que alguém *registrou* do composto em um instrumento. As duas respondem
perguntas diferentes e discordam de maneiras úteis: uma estrutura explica um
espectro para cujo composto nunca se fez uma medida, e uma biblioteca carrega o
padrão de intensidades que nenhuma enumeração de ligações prevê.

## Carregar uma biblioteca

**Load library…** aceita um arquivo MSP — o formato que o NIST define e que
MassBank, MoNA e GNPS todos exportam — ou um MGF. O arquivo é lido uma vez, a
contagem de registros e quantos trazem um precursor é mostrada, e o caminho
fica guardado para que a biblioteca esteja lá na próxima inicialização. Os
nomes dos campos variam conforme o exportador (`PrecursorMZ`, `PRECURSORMZ`,
`Precursor_type`, `Formula`) e são lidos sem distinção de maiúsculas e
minúsculas; campos que o programa não conhece são mantidos e mostrados ao
passar o cursor.

## Buscar

**Search the spectrum on screen** toma o espectro que o Explorer está
mostrando — centroidado, se era perfil — e o precursor do canal ativo, e
pontua cada registro cujo precursor esteja dentro de **Precursor ±** dele. A
tolerância é no mínimo a precisão com que o precursor do canal foi escrito: um
valor de método `647.5` é conhecido a ±0.05, e um filtro de ±0.02 em torno dele
estaria pedindo dígitos que ele não tem.

Um registro declara o seu precursor duas vezes — como `PrecursorMZ`, e de novo
como a massa que a sua `Formula` e o seu `Precursor_type` dão — e **qualquer
uma** das duas declarações o coloca na janela, de modo que nenhum registro se
perde porque os seus próprios dois números discordam. Um registro que não
declara nenhuma das duas fica de fora a menos que **Also records with no
precursor** esteja marcado — medido no MassBank, 24,000 de 139,000 registros
não trazem precursor escrito, e um filtro que os admitisse todos tinha cada
busca dominada por eles; marcados, eles são pontuados com o Δ ppm mostrado
como `—`, para que o leitor saiba que o filtro não pôde se aplicar a eles.
Picos medidos abaixo de um por cento do pico base não entram na
correspondência; a linha de base de um espectro de íons produto está cheia
deles.

Um aduto também declara um sinal de carga, de modo que se pode perguntar a um
registro se ele pertence à polaridade em que o scan foi medido — e se
pergunta. Registros cujo aduto é do sinal oposto ficam de fora a menos que
**Also the other polarity** esteja marcado. A polaridade é a do canal ativo,
lida do arquivo: ela não é digitada em lugar nenhum, porque a polaridade de
um scan é um fato sobre a aquisição e a única escolha que se tem é
honrá-la ou não. Um registro que nada diz sobre a sua própria polaridade é
mantido de todo modo — o portão recusa o que contradiz a consulta, nunca o que
é silencioso.

Um registro tem de alcançar pelo menos **Matched peaks ≥** dos seus picos para
ser listado, dois por padrão. Um pico em comum é uma coincidência: no mesmo
lote, um espectro que era quase todo o íon fosfocolina em 184.07 pontuou 83
contra um laxante cujo fragmento fica a 13 ppm de distância, e um registro de um
único pico correspondido nele era uma pontuação perfeita por nada.

Cada pico da biblioteca, do mais forte para o mais fraco, é emparelhado ao pico
medido livre mais próximo dentro de **Peaks ±** ppm, de modo que um íon forte da
biblioteca nunca é roubado da sua correspondência por um fraco listado antes.

## As duas pontuações

| Pontuação | O que ela pergunta |
|---|---|
| **Score** | o cosseno entre os dois espectros, sobre tudo o que ambos contêm, com as intensidades sob raiz quadrada para que um único pico base não decida tudo |
| **Reverse** | o mesmo cosseno, mas apenas sobre os picos da biblioteca: se eles estão no espectro medido, ignorados os demais picos do espectro medido |

Um reverse alto com um score baixo é um composto presente acompanhado — uma
impureza coeluente, ou uma varredura de survey (survey scan) com mais de um íon
na janela de isolamento. Um score alto com tudo correspondido é o próprio
registro. Ambos são mostrados como porcentagens; **Matched** é quantos dos picos
do registro encontraram um par.

## Δ ppm, e contra qual precursor ele é medido

`PrecursorMZ` é o que quer que o autor do registro tenha digitado — muitas
vezes duas casas decimais, às vezes truncadas em vez de arredondadas.
`Formula` e `Precursor_type` juntos dão a massa que o íon de fato tem, com
tantas casas quantas os elementos têm. Onde um registro traz os dois, o Δ ppm
é medido contra **essa** massa e a coluna **Δ from** diz `formula`; onde não
traz, o Δ recai sobre o valor escrito e a coluna diz `written`, para que um
número nunca seja lido como mais do que ele é.

Isso muda o que o número significa. Medido numa infusão real: o registro do
ácido cólico-d4 diz `430.35` e o canal que o buscou diz `430.34` — duas casas
decimais do mesmo íon, e um contra o outro eles dão **−23.2 ppm**, um
digitador contra outro. Contra 430.3465, que é o que `C24H36D4O5` como
`[M+NH4]+` pesa, a mesma busca dá **−15.1 ppm**, e isso é o truncamento da
própria consulta e nada mais.

Um registro cujas duas versões de si mesmo discordam por mais do que o valor
escrito é capaz de precisar diz isso na sua linha: a célula Precursor mostra
os dois, como `414.3400 ≠ 414.3516`, e o cursor por cima explica. Qual dos
três — a fórmula, o aduto ou a massa digitada — está errado não se pode saber
daqui, então isto é relatado e nunca consertado. "Capaz de precisar" é uma
unidade inteira na última casa escrita, já que um método escreve `286.2` para
286.2741 com a mesma facilidade com que arredonda, e nunca mais apertado do
que 25 ppm.

Esse piso foi medido. Numa biblioteca lipídica in silico de 449,627 registros
em que cada registro escreve cinco casas decimais — alegando ±0.000005 Da —
96.8% dos registros ficam dentro de 0.5 ppm da sua própria fórmula, 3.1%
dentro de 1 ppm e 309 dentro de 2 ppm, que é o arredondamento do exportador, e
depois disso não há **nada** até **um** registro a 116,411 ppm. Cobrado a meia
unidade na última casa, 30% daquela biblioteca se lê como quebrada; cobrado a
25 ppm, um registro se lê assim — `TG d5 17:0/17:1/17:0`, cujo registro
`[M+NH4]+` diz 768.57491 onde `C54H97D5O6` dá 869.8329, e cujo registro
`[M+H]+` no mesmo arquivo está certo. A marca encontrou um registro
genuinamente errado numa biblioteca pública e mais nada.

## Os picos correspondidos, e a sobreposição

Selecionar um registro lista os picos dele contra os medidos — massa, massa,
ppm e a fração do pico base de cada espectro — e **Overlay on spectrum**
desenha os picos do registro sobre o painel do espectro, escalados ao pico base
dele, do mesmo modo que a [[mass-calculator]] sobrepõe um padrão isotópico.
**Clear overlay** remove a sobreposição.

## Dois eixos de massa numa mesma comparação

Um registro escrito enquanto a [[mass-recalibration]] estava ligada carrega
picos que o instrumento nunca reportou: cada um deles foi deslocado por
algumas partes por milhão antes de o registro ser escrito, e o comentário
dele diz isso — `recalibrated −5.2 ppm`. Um registro que nada diz foi
escrito a partir dos números que o instrumento deu. Os dois são legítimos;
não são a mesma medição, e uma busca entre eles precisa dizer qual é qual.

Por isso a coluna **Axis** de cada acerto diz de qual eixo o registro foi
escrito e — quando o espectro na tela está ele próprio num eixo corrigido, o
que o Explorer informa junto com ele — como os dois se combinam:

| Os dois eixos | O que o acerto diz |
|---|---|
| nenhum corrigido | *record and query both on the instrument's axis* |
| os dois corrigidos | *record corrected −5.2 ppm, query corrected −6.1 ppm: each on the axis its own lock masses define* |
| um dos dois | *record on the instrument's axis, query corrected −5.6 ppm: 5.6 ppm apart by construction* |

**Dois espectros corrigidos estão num só eixo, por mais distantes que as
correções tenham sido.** Cada um foi levado às massas que as próprias lock
masses da sua aquisição definem, de modo que a diferença entre as duas
correções é o quanto as duas corridas haviam derivado uma da outra — que é
justamente o que corrigi-las removeu. O que está *apartado por construção* é
uma correção que um lado carrega e o outro não: essa está em cada Δ ppm da
comparação e em cada pico que o pareamento teve de decidir. Onde ela é maior
que a tolerância **Peaks ±** da busca, a linha é marcada e a frase sob os
acertos diz isso, nestas palavras: a pontuação está então medindo os eixos e
não o composto.

**Re-search with the axis matched** refaz a pergunta com o espectro movido
para o eixo do registro — uma consulta corrigida devolvida a onde o
instrumento a leu, para encontrar um registro não corrigido, ou uma consulta
não corrigida movida ao encontro de um registro corrigido. Nada muda na
tela; as massas são movidas só para aquela busca, e a linha diz qual eixo
foi usado.

É um diagnóstico, não um reparo. Tira a diferença que as correções puseram
ali; não põe nenhum dos dois lados no eixo *certo*, e onde o registro é o não
corrigido ele afasta a consulta das próprias lock masses dela. Medido
abaixo: um acerto de 61.0 virou nenhum acerto desse jeito. O que põe uma
biblioteca inteira num só eixo é **Rewrite from files…**.

### Medido: o eixo de um registro contra o de uma consulta, de quatro modos

Os três padrões de ácido biliar, com as infusões CID escritas numa
biblioteca própria duas vezes — uma a partir do eixo que o instrumento
reportou e outra com a recalibração ligada — e cada infusão EAD do mesmo
composto buscada contra as duas bibliotecas, ela própria dos dois modos. As
correções são a escada de precursor de cada aquisição
([[mass-recalibration]]): os registros CID **+3.8, +6.6 e +2.0 ppm**, as
consultas EAD **−5.3, −5.6, −8.6 e −7.5 ppm**. Cada célula é *pontuação /
mediana de |Δ ppm| sobre os picos pareados*.

Na tolerância de pico padrão da busca, **20 ppm**:

| consulta | ambos como medidos | registro cru, consulta corrigida | registro corrigido, consulta crua | **ambos corrigidos** |
|---|---|---|---|---|
| CA-d4 EAD 12 eV | 6.5 / 11.5 | 6.5 / 7.7 | 6.5 / 9.2 | **6.5 / 4.3** |
| CA-d4 EAD 22 eV | 29.3 / 10.8 | 29.3 / 5.2 | 29.3 / 7.0 | **29.6 / 3.5** |
| DCA-d4 EAD 22 eV | 34.3 / 13.0 | 35.3 / 4.6 | 35.3 / 6.4 | **35.5 / 2.4** |
| TDCA-d4 EAD 22 eV | 61.4 / 9.8 | 61.4 / 3.1 | 61.4 / 7.8 | **61.4 / 2.1** |

A **5 ppm**:

| consulta | ambos como medidos | registro cru, consulta corrigida | registro corrigido, consulta crua | **ambos corrigidos** |
|---|---|---|---|---|
| CA-d4 EAD 12 eV | **nenhum acerto** | 1.8 / 0.9 | 1.8 / 2.4 | **5.1 / 3.4** |
| CA-d4 EAD 22 eV | 1.0 / 3.4 | 16.5 / 2.1 | 15.9 / 2.5 | **26.6 / 2.5** |
| DCA-d4 EAD 22 eV | **nenhum acerto** | 13.8 / 4.1 | 2.7 / 4.3 | **33.5 / 2.2** |
| TDCA-d4 EAD 22 eV | **nenhum acerto** | 61.0 / 3.0 | 2.4 / 4.4 | **61.0 / 2.0** |

Três coisas saem daí, e uma delas mudou o programa.

**Ambos corrigidos é o melhor dos quatro, todas as vezes.** A 20 ppm as
pontuações quase não se mexem — um pareamento que já vinha dando certo
continua dando —, mas as massas concordam muito melhor: a mediana da
distância por pico pareado cai de 9.8–13.0 ppm para 2.1–4.3. A 5 ppm esse é
o resultado inteiro: três das quatro consultas **não acertam nada** quando
nenhum dos lados está corrigido, e as quatro acertam quando os dois estão.

**E isso vale embora as duas correções sejam ali as mais distantes entre
si.** O registro de TDCA-d4 foi corrigido em +2.0 ppm e a consulta dele em
−7.5 — 9.5 ppm entre as duas — e deu a melhor concordância da linha, 2.0 ppm
por pico. A primeira versão disto avisava sobre esse par, pela aritmética de
que duas correções diferentes teriam de significar dois eixos diferentes. A
medição diz o contrário, e a regra agora é a de cima: o que conta é uma
correção que um lado carrega e o outro não.

**Igualar o eixo não é o mesmo que corrigi-lo.** TDCA-d4 a 5 ppm contra o
registro não corrigido pontua 61.0 com a consulta corrigida, e **nenhum
acerto** assim que a consulta é devolvida ao eixo não corrigido do registro
— porque o próprio registro estava 2.0 ppm fora. Igualar os eixos remove a
diferença que as correções puseram ali e deixa o erro que cada lado tinha de
seu. Diz quanto da concordância era a correção; não fabrica concordância, e
não é o reparo.

## Medido no MassBank

A exportação completa do MassBank em formato NIST — 139,006 registros, 137 MB —
é lida em cinco segundos e ocupa cerca de 1.3 GB de memória, já que os picos de
cada registro ficam guardados como arrays prontos para corresponder. Uma busca
filtrada responde em milissegundos; uma sem filtro de precursor, que tem de
considerar todo registro que compartilhe dois picos com a consulta, em dois a
sete segundos.

Contra os espectros de íons produto de um lote real, a busca filtrada retornou
o composto onde a biblioteca o tinha — uma esfingomielina C16 com score 46 e
reverse 79, uma ceramida C16 com 32 e 94, uma ceramida C24:1 com 11 e 90, uma
esfingomielina C18 com 48 e 96 — e nada para os padrões internos C17, que não
estão no MassBank. As pontuações são baixas e as reversas altas porque uma
varredura de íons produto num TOF carrega o precursor, os isótopos dele e toda a
região de baixa massa, além dos fragmentos que o registro lista: em espectros
assim, o reverse é o que se deve ler, e o score simples diz quanta outra coisa
havia ali.

## Medido numa biblioteca lipídica grande

A outra biblioteca medida aqui é um MSP lipídico in silico de **449,627
registros**, 224 MB, todos eles em modo positivo: 6.1 segundos para ler, 2.2
GB ocupados, e mais 5.9 segundos na primeira vez em que uma busca pergunta o
quanto as fórmulas pesam — calculado uma vez, sob demanda, de modo que uma
biblioteca carregada e nunca buscada não paga nada.

**449,525 dos 449,627 registros (100.0%) trazem uma fórmula e um aduto que
ambos são lidos.** Os 102 que não trazem são todos `[M]+`, um cátion radical
que este programa não modela; eles mantêm o seu precursor escrito e a sua
polaridade, e o seu Δ diz `written`.

Em seguida, os 143 canais de íons produto de uma injeção real — um TripleTOF
5600, positivo, um composto por canal — foram cada um promediados,
centroidados e buscados contra ela numa janela de ±0.5 Da. 132 canais
devolveram resultados e 11 não devolveram nenhum. **2,414 dos 2,415
resultados listados tiveram o seu Δ medido contra a fórmula** e um contra o
valor escrito: o caso `[M]+`. A busca levou uma mediana de 6 ms, e 5.8 s no
único canal cuja janela contém a maior parte da biblioteca.

O portão de polaridade naquele lote não removeu **nada** — cada lista dos 20
melhores idêntica com ele e sem ele, nos 132 canais — porque uma biblioteca em
modo positivo consultada por varreduras em modo positivo não tem o que
recusar, e essa é a metade do portão que não pode disparar por engano. A outra
metade foi medida pedindo aos mesmos 143 canais registros em modo negativo:
**zero resultados**, todos os 449,627 registros recusados. O meio interessante
— uma biblioteca com as duas polaridades, onde o portão tem o que escolher —
não foi mensurável aqui: os números do MassBank acima foram tomados quando
aquela exportação estava na máquina, e ela não está mais.

## Sua própria biblioteca

Um padrão interno deuterado infundido de propósito não está em biblioteca
pública nenhuma. O espectro na tela é o único registro dele que algum dia
existirá, de modo que **Add spectrum to library…** o escreve numa biblioteca
sua: um arquivo MSP que você escolhe uma vez, ao qual se acrescenta, e que é
legível por qualquer coisa que leia MSP — inclusive este programa, o MS-DIAL
e o MSPepSearch.

Na primeira vez, um arquivo é pedido; depois disso o painel diz quantos
registros ele contém. O diálogo pergunta apenas o que a aquisição não pode
fornecer e preenche de antemão tudo o que pode:

| Campo | De onde vem |
|---|---|
| **Name** | seu. É o que uma busca mostrará, e um registro sem ele não é sequer lido de volta |
| **Precursor m/z** | o canal ativo, ou o que estiver digitado em **Precursor** acima |
| **Adduct** | oferecido a partir da polaridade que foi executada — `[M-H]-` para um método negativo, `[M+H]+` para um positivo — e qualquer outro aduto pode ser digitado. Mude-o se o íon não foi o oferecido |
| **Formula** | sua, se for conhecida; um registro não precisa de uma, mas um registro que tem uma vale mais |
| **Collision energy** | a informação do canal, onde o instrumento registrou alguma |
| **Comment** | o próprio título do painel do espectro — amostra, canal e os scans sobre os quais a média foi tomada — com o arquivo e a data de hoje |

O espectro é escrito como **centroides**: bastões, um por íon, não os pontos
de perfil. Se o painel de [[chromatograms-and-spectra]] estiver mostrando um
espectro de perfil, ele é centroidado na saída, do mesmo modo que para uma
busca. Picos abaixo de um por cento do pico base são descartados — a linha de
base de uma varredura de íons produto são milhares deles, e um registro que
os carregasse corresponderia a qualquer coisa — e no máximo duzentos do que
sobra são mantidos, do mais forte para o mais fraco. As intensidades são
guardadas em relação ao pico base, como porcentagem, que é como todo formato
de biblioteca as contém.

O registro entra no arquivo como MSP no estilo NIST: `Name`, `PrecursorMZ`,
`Precursor_type`, `Formula`, `Collision_energy`, `Comment`, `Num Peaks`, e
então a lista de picos. O `PrecursorMZ` é escrito com a precisão que lhe foi
dada e nada além dela — `430.35` continua `430.35`, e não é preenchido até
`430.3500`, o que alegaria quatro casas decimais que um valor de método não
tem e faria a própria fórmula do registro chamá-lo de errado. Se a biblioteca
carregada for o arquivo que acabou de ser escrito, ela é lida de novo em
seguida, de modo que o registro novo pode ser buscado imediatamente — o que é
também a verificação de que ele foi escrito numa forma que o analisador lê de
volta.

**Dê ao registro a sua fórmula e o seu aduto.** Eles não são rótulos: a busca
calcula a massa real do íon a partir deles, mede o Δ ppm contra ela, e recusa
o registro a uma varredura da polaridade oposta. Um registro seu é o único
registro de biblioteca do qual se pode ter certeza de que os traz.

**E o registro sabe de qual eixo de massa foi escrito.** Com a
[[mass-recalibration]] ligada, o espectro na tela não é o que o instrumento
reportou — cada pico foi movido por algumas partes por milhão —, de modo que
o comentário carrega `recalibrated −5.2 ppm` e aquilo em que a correção se
apoiou, seja o registro escrito pelo Explorer, pela pasta inteira de uma vez
ou por uma reescrita. Um registro que nada diz foi escrito a partir dos
números do próprio instrumento, que é o que todo registro feito antes disto
existir é. Daí em diante o eixo é lido de volta onde importa: uma busca
declara a combinação dos dois eixos e avisa quando estão mais distantes que
a própria tolerância de pico dela, e a [[standard-history]] mantém um
registro corrigido e um não corrigido em séries separadas quando a correção
entre eles é grande o bastante para quebrar o pareamento.

### Um padrão, a partir do frasco

Uma terceira porta de entrada, e a que parte do frasco em vez de partir de um
espectro já na tela: o [[new-standard]] pede o nome, o lote e o arquivo de
infusão e escreve o registro e o componente do método juntos, de modo que um
padrão cadastrado uma vez fique pesquisável, quantificável e com histórico a
partir do mesmo instante. O registro que ele escreve carrega um campo que
estes dois não carregam — o **lote**, no comentário — que é o que diz que dois
registros com meses de diferença são do mesmo material.

### Uma pasta inteira de uma vez

Uma pasta de infusões são nove espectros, e acrescentá-los um a um pelo
Explorer significa nove diálogos. A aba **Infusions** já tirou a média,
centroidou e identificou cada um deles, de modo que **Add all to library**
naquela aba ([[infusion-report]]) escreve um registro por linha no mesmo MSP
— o arquivo escolhido uma vez, ao qual se acrescenta, pedido na primeira vez
se ainda não estiver definido.

Cada registro toma o nome do composto que a linha propõe, o aduto e a
fórmula do que a linha identificou, a energia de colisão e a ativação do
canal, o `Acquired` do arquivo, e os picos exatamente dos números sobre os
quais a tabela foi medida. Nada é lido de novo e nada é centroidado duas
vezes.

Dois tipos de linha não produzem registro, e ambos dizem isso na linha
abaixo da tabela em vez de serem contados em silêncio:

- **uma linha cujo composto não pôde ser proposto.** O composto é a parte do
  nome do arquivo antes do primeiro separador, e um registro que ninguém
  consegue encontrar pelo nome outra vez não é um registro.
- **uma linha que já está no arquivo.** A chave é a **procedência no
  comentário do registro: o arquivo de aquisição e o canal dentro dele**.
  Não o composto e não o nome — o mesmo frasco infundido duas vezes são duas
  medições e pertence ao arquivo duas vezes, ao passo que o mesmo canal do
  mesmo arquivo escrito duas vezes é uma medição anotada duas vezes, o que
  transforma um histórico num gráfico de nada. Assim, apertar o botão de
  novo depois de acrescentar mais dois arquivos acrescenta esses dois
  arquivos e nada mais.

A linha diz *7 record(s) written, 2 skipped: …* com cada linha ignorada
nomeada e a razão ao lado.

### Reescrever a partir dos arquivos

Uma biblioteca sua é escrita um registro por vez ao longo de meses, e um
registro escrito em março carrega o que a versão de março escrevia: sem
`Acquired`, sem `Base_peak_intensity`, sem fórmula, um precursor digitado
com duas casas. As aquisições em geral ainda estão em disco, de modo que o
registro não precisa continuar assim. **Rewrite from files…**, ao lado de
**History…**, lê todo registro cujo comentário nomeia um arquivo que ele
consegue encontrar, tira de novo a média dos mesmos scans do mesmo canal,
centroida com o mesmo piso e o mesmo teto, e reescreve o registro no lugar
com tudo o que esta versão escreve — inclusive um `PrecursorMZ` que
concorda com a própria fórmula do registro em vez de com o que foi digitado.

Onde os arquivos são procurados: nas pastas de onde as aquisições abertas
foram abertas, na última pasta de onde algo foi lido, e na pasta da própria
biblioteca. Um comentário nomeia um arquivo e nunca um caminho, porque um
caminho deixa de ser verdadeiro no instante em que a aquisição é copiada
para qualquer lugar.

**Um registro cujo arquivo sumiu é mantido exatamente como está**, listado
pelo nome com a razão, e o mesmo vale para um cujo comentário não nomeia
aquisição nenhuma — registros de outra pessoa no mesmo arquivo, por
exemplo. O espectro de um registro assim é a última cópia daquela medição, e
perdê-la numa arrumação é a única coisa aqui que não se pode desfazer.

**A biblioteca como estava é copiada para `<nome>.msp.bak` antes**, antes de
qualquer coisa ser sobrescrita, e a linha de resumo diz isso. Nada é escrito
quando não havia nada a reescrever.

Onde a [[mass-recalibration]] está ligada e a aquisição é uma das abertas, o
registro é reescrito no eixo de massa **corrigido** e seu comentário passa a
dizer `recalibrated −5.2 ppm`: um eixo de massa que foi movido e não admite
isso é pior do que um que está errado.

### Medido numa pasta de nove infusões

As nove infusões de ácidos biliares no ZenoTOF — três compostos, modo
positivo, um canal de íons-produto cada — medidas na aba Infusions e depois
escritas num único aperto:

| | |
|---|---|
| linhas medidas | 9, em 35 s |
| **Add all to library** | **9 registros escritos, nenhum ignorado, em 0,01 s** |
| apertado de novo | 0 escritos, 9 ignorados, cada um *already in the file from …* |
| o arquivo | 19 KB, 9 registros |
| **Rewrite from files…** | **9 de 9 reescritos em 39 s** |
| picos depois da reescrita | **idênticos, cada valor de cada registro** |
| demais campos depois da reescrita | inalterados, 9 de 9 |

O Add all não custa nada porque a tabela já havia feito o trabalho; a
reescrita custa 39 segundos porque tira de novo a média de nove corridas
inteiras, que são os mesmos 35 segundos que a medição levou da primeira vez.
Os picos serem idênticos é o objetivo da comparação: o registro é escrito a
partir dos picos que a aba escolheu, e a reescrita os escolhe do mesmo modo
a partir dos mesmos scans, de forma que uma diferença significaria que um
dos dois não estava lendo o que dizia ler.

Com os três compostos na tabela de componentes, sete dos nove registros
carregam fórmula e aduto — `C24H36D4O5` como `[M+NH4]+` para o ácido
cólico-d4, com as quatro marcações recolocadas a partir do nome — e o
`PrecursorMZ` deles é escrito como **430,34651**, o que aquele íon pesa, e
não como o `430,35` que o método digitou. Nenhum dos nove discorda de si
mesmo.

Os outros dois são o par chamado `CA-d4_…TESTEARTIGO`, cujo canal isola
**839,56** e não 430,35 (veja [[infusion-report]]). Nenhum aduto da fórmula
alcança essa massa, de modo que esses dois registros são escritos **sem
fórmula e sem aduto nenhum** — apenas a medição, o precursor que o
instrumento recebeu e a procedência dizendo de que arquivo e de que canal
vieram. Esse é o resultado pretendido: o nome do arquivo diz ácido
cólico-d4 e a aquisição diz outra coisa, e um registro que carregasse a
fórmula assim mesmo poria o nome do composto num espectro de outro íon. O
pico base deles é de 109 contagens, o que o `Base_peak_intensity` do
registro diz em voz alta.

Depois uma aquisição foi posta fora de alcance — a mesma pasta com aquele
`.wiff` de fora — e a biblioteca reescrita de novo: **8 reescritos, 1
mantido**, listado como *CA-d4 (CA-d4_TOFMSMS_EAD_12CE_44DP_13KE_TESTEARTIGO.wiff
is not on disk)*, e esse registro voltou com seus picos e cada um de seus
campos idênticos ao que eram.

### Medido em três padrões infundidos

As aquisições para as quais isto foi escrito: ácido cólico-d4, ácido
desoxicólico-d4 e ácido taurodesoxicólico-d4, infundidos um de cada vez num
ZenoTOF 7600 em modo **positivo**, varreduras de íons produto, um canal cada e
sem coluna. O veredito de [[direct-infusion]] chama todos eles de infusões,
de modo que cada registro é a média de **todos os scans da corrida** — 473,
473 e 257 deles, ao longo de 1.98, 1.98 e 1.07 minutos — centroidada:

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| pontos de perfil na média | 255,113 | 242,308 | 192,688 |
| centroides | 811 | 1,059 | 455 |
| em ou acima de 1% do pico base | 204 | 226 | 25 |
| picos no registro | 200 | 200 | 25 |
| o que limitou | o teto de 200 | o teto de 200 | o piso de 1% |
| pico base | 359.2870 | 361.3017 | 468.3072 |

Buscar um espectro contra um registro do mesmo composto é uma das três
verificações que um [[infusion-report]] soma, e a sua pontuação, a pontuação
reversa e a procedência do registro são impressas ali ao lado da figura
cabeça contra cauda.

Três registros, 8,144 bytes, escritos em menos de um segundo. Lidos de volta,
todos os três voltaram com cada campo com que foram escritos, as massas
dentro de 5·10⁻⁶ Da e as intensidades relativas dentro de 5·10⁻⁷ — o
arredondamento do texto, e nada mais.

Depois, cada composto foi **readquirido com dissociação ativada por elétrons
a 22 eV** e essa média buscada contra os três registros, que foram escritos a
partir de dissociação induzida por colisão a 45, 40 e 30 eV. Essa é uma
pergunta mais difícil que o mesmo canal de uma injeção diferente: o registro
e a consulta não são apenas duas medições, são duas maneiras de quebrar a
molécula.

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| o próprio registro veio primeiro | sim | sim | sim |
| o score dele | 29.2 | 33.3 | 61.5 |
| o reverse dele | 38.8 | 43.8 | 68.7 |
| picos correspondidos | 22 de 200 | 19 de 200 | 8 de 25 |
| o melhor registro *errado* | 14.1 | 14.0 | 10.3 |
| Δ ppm contra a fórmula do registro | −15.1 | −28.0 | −18.1 |
| Δ ppm contra o precursor escrito dele | −23.2 | +0.0 | +0.0 |

**Um composto diferente não corresponde.** Buscados contra os outros dois
registros sem filtro de precursor, o melhor score errado em qualquer lugar é
14.1 com um reverse de 31.2 — da metade a um sexto do que o registro do
próprio composto dá — e o espectro do CA-d4 não retorna **correspondência
alguma** contra o registro do TDCA-d4, menos de dois picos em comum. Com o
filtro de precursor que o painel aplica por padrão havia exatamente um
registro na janela de ±0.02 Da a cada vez e era o certo; o filtro não muda
nenhum score nem a ordem aqui, apenas quais registros foram pontuados. Uma
busca leva de 0.1 a 1.6 ms.

### O que a fórmula e o aduto mudaram aqui

Os três registros foram então escritos de novo **com as suas fórmulas e os
seus adutos** — `C24H36D4O5` `[M+NH4]+`, `C24H36D4O4` `[M+NH4]+`,
`C26H41D4NO6S` `[M+H]+` — e nada da correspondência se moveu: os mesmos
scores, os mesmos reverses, os mesmos picos correspondidos, o registro certo
em primeiro lugar todas as vezes. O que se moveu foi a coluna Δ, e um registro
ganhou uma marca.

| | CA-d4 | DCA-d4 | TDCA-d4 |
|---|---|---|---|
| precursor escrito | 430.35 | 414.34 | 504.32 |
| o que a fórmula e o aduto pesam | 430.3465 | 414.3516 | 504.3291 |
| distantes por | 3.5 mDa, +8.1 ppm | 11.6 mDa, −28.0 ppm | 9.1 mDa, −18.1 ppm |
| o que um número de duas casas precisa | ±10.8 mDa | ±10.4 mDa | ±12.6 mDa |
| marcado | não | **sim** | não |

O Δ do CA-d4 lia −23.2 ppm — o registro diz `430.35` e o canal que o consultou
diz `430.34`, duas casas decimais do mesmo íon, um digitador contra outro.
Contra 430.3465, que é o que o íon pesa, ele lê −15.1 ppm, que é o truncamento
da própria consulta.

O DCA-d4 é o que vale a pena ler. O seu registro e a sua consulta trazem o
*mesmo* número digitado, `414.34`, de modo que o Δ antigo era **+0.0 ppm** —
concordância perfeita entre duas cópias do mesmo erro. Contra a fórmula, os
dois estão 28 ppm fora, além dos ±10.4 mDa que um número de duas casas
precisa, de modo que o registro é marcado. E a aquisição decide qual dos três
está errado: o precursor sobrevivente na própria varredura EAD do DCA-d4 mede
**414.3525**, a 2.2 ppm de `C24H36D4O4` `[M+NH4]+` e a 28 ppm do `414.34` do
método (o do CA-d4 mede 430.3489, a 5.6 ppm da sua fórmula). A fórmula está
certa e a massa digitada não está — mas é o instrumento que diz isso, não a
marca, que apenas relata que os dois discordam.

O TDCA-d4, a 9.1 mDa, não é marcado e não deve ser: `504.3291` truncado em
duas casas é `504.32`, que é como métodos escrevem massas.

**Um aduto errado é apanhado de imediato.** O mesmo registro do CA-d4 escrito
`[M-H]-` em vez de `[M+NH4]+` — o íon que estas infusões foram a princípio
supostas ser — põe a sua fórmula a 19.0446 Da do seu próprio precursor
escrito, e por isso é marcado; e o portão de polaridade então o recusa à
varredura positiva que de outro modo o teria correspondido, um resultado
virando nenhum até que **Also the other polarity** seja marcado.

**Um registro é uma energia, e uma maneira de quebrar a molécula.** O mesmo
espectro do CA-d4 readquirido a 12 eV em vez de 22, contra o mesmo registro
de CID, pontua **6.4 com um reverse de 21.3 sobre 8 picos correspondidos** —
contra 29.2, 38.8 e 22 a 22 eV. Separando as duas causas: um registro escrito
a partir da própria média de EAD a 22 eV do CA-d4 pontua 100.0 contra si
mesmo (que é a ida e volta, exata), **67.4** contra a média dele a 12 eV, e
29.1 com um reverse de 55.7 contra a média de CID a 45 eV. Ou seja, a mudança
de energia custa cerca de um terço do score e a mudança de ativação custa
quase todo o resto. A ordenação sobrevive a tudo isso — o registro certo veio
primeiro todas as vezes — mas o número ao lado dele não viaja entre métodos,
e um limiar escolhido num não é um limiar noutro.

### Medido num lote de esfingolipídios

Num lote real de aquisições de íons produto — 26 injeções de um método cujos
144 canais são um composto cada, na sua própria energia de colisão, que é o
mesmo formato de uma infusão de um padrão:

Catorze registros foram escritos a partir da primeira injeção, cada um a
média de todos os 61 scans de um canal, centroidada. De onze mil a vinte e um
mil pontos de perfil viraram de 84 a 3,650 centroides e de 7 a 82 picos no
registro; o arquivo são catorze registros em 13.9 kB, construído em menos de
dois segundos. Lidos de volta, todos os catorze voltaram com cada campo com
que foram escritos, as massas dentro de 5·10⁻⁶ Da e as intensidades relativas
dentro de 5·10⁻⁷ — o arredondamento do texto, e nada mais.

Depois, os **mesmos canais de uma injeção diferente** foram buscados contra
aquela biblioteca, sem filtro de precursor, de modo que a correspondência é
espectral apenas:

| | Injeção 02 | Injeção 13 |
|---|---|---|
| o registro certo veio primeiro | 14 de 14 | 14 de 14 |
| o score dele | 13–95, mediana 60 | 33–95, mediana 63 |
| o reverse dele | 45–96, mediana 87 | 61–99, mediana 83 |
| o melhor registro *errado* | 42 | 42 |

Um composto diferente não corresponde. O registro feito a partir do padrão em
354.3 foi buscado contra cada um dos outros treze canais da segunda injeção:
nove deles não retornaram **correspondência alguma** — menos de dois picos em
comum — e o melhor dos demais pontuou 19 com um reverse de 67, contra 95 e 96
para o seu próprio canal. Com o filtro de precursor que o painel aplica por
padrão, cada busca teve exatamente um registro na janela e o encontrou.

As pontuações se leem baixas pelo mesmo motivo que os números do MassBank
acima: uma varredura de íons produto num TOF carrega o precursor, os isótopos
dele e toda a região de baixa massa, além dos fragmentos, e nada disso está
num registro construído a partir de uma média mais limpa. O reverse é o que
se deve ler.

## Fragmentação ao longo das energias

Um registro é um espectro em uma energia de colisão, e um registro não viaja
entre energias: nas nove infusões de ácidos biliares, um registro de ácido
cólico-d4 medido sob CID a 45 eV pontua **6** contra o mesmo frasco sob EAD a
12 eV e **29** contra ele a 22 eV. Lido como uma lista de resultados, isso diz
que o composto não está ali, o que é falso.

Quando um composto tem registros em duas ou mais energias da mesma ativação,
o painel acrescenta uma linha sob a lista de resultados, uma por composto e
ativação:

> compatible with CA-d4 EAD at ~18 eV (score 0.71; measured at 12 and 22)

A linha responde à outra pergunta. A lista de resultados pergunta *com qual
registro isto se parece*; esta pergunta *que condições produziriam isto*. Ela
é acrescentada, nunca substitui: a lista de resultados não muda.

### Como a linha é obtida

Cada registro do composto é reduzido à fração da intensidade que os degraus da
sua própria escada carregam — a escada de perdas de água que a `Formula` e o
`Precursor_type` do registro preveem pela enumeração de [[lipid-maps]], mais os
fragmentos mais intensos em que os registros concordam. **Frações do total do
próprio perfil, nunca do pico base do registro**, porque o próprio pico base
desce a escada conforme a energia sobe (veja a tabela abaixo), e um número cujo
denominador troca de degrau não pode ser interpolado.

A fração de cada degrau é então linear na energia entre as duas energias
medidas que a cercam, e o painel varre a faixa a meio elétron-volt em busca do
melhor ajuste. Três recusas são tão importantes quanto a resposta:

* **Nada é extrapolado.** Acima da energia mais alta em arquivo a escada
  continua descendo e nenhum registro diz a que velocidade. Um espectro medido
  além da faixa só pode ser reportado no extremo dela.
* **Duas ativações nunca são interpoladas entre si.** Registros de EAD e
  registros de cela de colisão são perfis separados, e um registro cuja
  ativação não é declarada é um terceiro — a mesma regra pela qual
  [[standard-history]] corta suas séries.
* **Um registro é um registro.** Com uma única energia em arquivo a linha diz
  *one energy on file (22 eV): no profile*.

A pontuação é o cosseno sobre os íons do próprio perfil, com as intensidades
sob raiz quadrada como nas pontuações da lista de resultados. Não é o cosseno
simples: um perfil tem uma dúzia de íons e um espectro de íons-produto tem
centenas, de modo que o cosseno simples mediria tudo o mais que havia no
frasco. Um `~` antes da energia significa que ela foi interpolada, e não
medida.

### Medido nas nove infusões de ácidos biliares

O ácido cólico-d4 foi infundido a EAD 12 eV, EAD 22 eV e a 45 eV num arquivo
cujo nome não declara ativação alguma. Seu perfil, em frações do total do
próprio perfil:

| Íon | m/z | EAD 12 eV | EAD 22 eV | 45 eV, não declarada |
|---|---|---|---|---|
| `[M+NH4]+ +4D` | 430,3465 | 83,5% | 24,6% | 0,0% |
| `[M+H]+ (-NH3) +4D` | 413,3200 | 0,0% | 0,9% | 0,0% |
| `[M+H-H2O]+ +4D` | 395,3094 | 0,0% | 6,5% | 0,0% |
| `[M+H-H2O]+ +3D` | 394,3031 | 0,0% | 0,3% | 0,0% |
| `[M+H-2H2O]+ +4D` | 377,2988 | 1,5% | 25,2% | 1,7% |
| `[M+H-2H2O]+ +3D` | 376,2926 | 1,3% | 2,0% | 0,0% |
| `[M+H-3H2O]+ +4D` | 359,2883 | 0,0% | 6,2% | 54,2% |
| `[M+H-3H2O]+ +3D` | 358,2820 | 0,0% | 6,5% | 6,8% |
| doze fragmentos compartilhados abaixo de m/z 150, juntos | | 13,7% | 27,8% | 37,2% |

É a escada descendo. A 12 eV o precursor amoniado é 83,5% de tudo; a 22 eV ele
já entregou um quarto da intensidade a `[M+H-2H2O]+`; a 45 eV o precursor
desapareceu e `[M+H-3H2O]+` é 54,2%, com os fragmentos pequenos ficando com
quase todo o resto. **O pico base é um íon diferente nos três arquivos**, que é
exatamente por que o perfil é mantido em frações do próprio total.

Dois dos nove arquivos se chamam `CA-d4` e isolam 839,56 em vez de 430,34.
Eles ficam de fora do perfil do CA-d4 com o motivo na linha — *holds fewer
than 2 of the ladder's ions* — e nada precisou ler um nome de arquivo para
saber disso.

### O que duas energias por ativação permitem, e o que não permitem

Honestamente: ainda não muito, nesses arquivos. Tire o EAD 12 eV da biblioteca
e busque-o de volta: o perfil fica com um único registro EAD e diz *one energy
on file (22 eV): no profile*; o registro de 45 eV não ajuda, porque sua
ativação não é declarada e nenhuma ativação é interpolada com outra. Tire o
EAD 22 eV e acontece o mesmo com o de 12 eV. **Dois registros de uma ativação
é o mínimo, e tirar qualquer um deles fica abaixo do mínimo.**

Com os dois registros EAD presentes, a varredura faz o que deve: o espectro de
12 eV volta a 12 eV e o de 22 eV volta a 22 eV, ambos com pontuação 1,00, e os
dois arquivos de 839,56 pontuam 0,10 e 0,11. O espectro de 45 eV volta a 22 eV
— o topo da faixa EAD, já que nada é extrapolado — a 0,56, que é o mesmo 0,56
que seu reverse contra o registro de 22 eV sozinho já era. Esse é o resultado
honesto de dois pontos: o melhor ajuste cai sobre um dos dois registros, de
modo que a linha acrescenta a *energia*, que uma lista de resultados não pode
declarar, e não uma pontuação melhor. Uma terceira energia sob uma ativação é o
que faria a interpolação valer o próprio número, e ninguém adquiriu uma ainda.

O que a aritmética faz quando um espectro de fato fica entre dois registros foi
verificado nesses degraus pedindo as frações do meio do caminho: a varredura
responde 16,5 a 17 eV, e tudo entre 15 e 20 eV pontua dentro de um por cento do
melhor. **Ou seja, uma proposta é boa a alguns elétron-volts, não ao passo de
meio volt**, e é por isso que ela vem escrita com um `~`.

Construir um perfil e varrê-lo leva cerca de 3 ms numa biblioteca de nove
registros.

## O que a biblioteca não sabe

Um registro é o espectro de um instrumento em uma energia de colisão. Uma
correspondência é evidência de que o espectro medido se parece com aquele
registro; quanta semelhança basta é decisão do analista, e o
[[accurate-precursor]] e o [[formula-finder]] são as verificações independentes
sobre o precursor que uma correspondência de biblioteca não faz.

Um perfil de energia não muda isso. Ele diz com quais das condições
*registradas* um espectro se parece e em que energia entre elas; não diz que o
composto é o certo, e não pode propor uma ativação que ninguém registrou.

## Ler de volta a sua própria biblioteca

Uma biblioteca própria acumula um registro por verificação do mesmo padrão.
**History…**, ao lado da contagem de registros, lê esses registros de volta
como uma carta de controle do padrão ao longo do tempo — veja
[[standard-history]].

## A partir de um script

`api.Library.open(msp)`, `.search(spectrum)` e `.add(spectrum, name)` fazem
tudo isso sem a janela, tomando o precursor e a polaridade do próprio
espectro e centroidizando-o antes de escrever um registro — veja a
[[python-api]].

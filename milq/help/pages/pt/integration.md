---
title: Todo o caminho da infusão, medido como uma coisa só
---
Cada outra página aqui descreve uma coisa que o programa faz. Esta roda
todas elas, em ordem, sobre as mesmas nove aquisições, e relata quanto
custa o caminho inteiro e onde as suas partes discordam umas das outras.

Essa segunda metade é a razão de a página existir. O caminho da infusão são
trinta e tantos módulos escritos em paralelo, e módulos escritos em paralelo
respondem à mesma pergunta duas vezes. Dois deles medem o piso de ruído.
Três dizem quantas varreduras foram promediadas. Dois dizem quantos íons
previstos foram encontrados. Onde as duas respostas diferem, uma delas está
errada na tela de alguém — e nada percebe isso a não ser rodá-las lado a
lado e comparar os números, que é o que esta página é.

As medições são sobre as nove infusões de ácidos biliares do ZenoTOF 7600
contra as quais o resto do manual foi escrito: um canal de íons-produto cada,
nenhuma varredura de varredura completa em lugar nenhum, de 146 a 473
varreduras ao longo de 0,6 a 2,0 minutos. Veja [[direct-infusion]] para o que
elas são e [[measured-facts]] para os números que o resto do manual tira
delas.

## O caminho

De uma pasta no disco até um documento, um registro e um componente:

[[checking-files]] → abrir → o veredicto de [[direct-infusion]] → a máscara
do spray → a média → o piso de ruído → o que o método isola → o aduto → o
eixo de massas ([[mass-recalibration]]) → a explicação ([[lipid-maps]]) → a
margem → os picos não explicados → a evidência isotópica → a pureza → um
registro próprio ([[spectral-library]], [[standard-history]]) → um componente
([[new-standard]]) → a energia de colisão ([[collision-energy]]) →
[[infusion-quantitation]] → o [[infusion-report]] e a capa da sua pasta →
[[compare-infusions]] → [[python-api]].

## Quanto custa

Nove arquivos, um processo, a partir do código-fonte no macOS. **Frio** é a
primeira chamada e **quente** é a mesma chamada de novo sobre os mesmos
arquivos já abertos.

| etapa | frio | quente |
|---|---|---|
| importar `milq` | 0,24 s | — |
| `folder.check_files` | 0,001 s | 0,001 s |
| abrir as nove | 0,258 s | 0,014 s |
| `is_infusion` ×9 | 0,009 s | 0,000 s |
| `strongest_channel` ×9 | 0,000 s | 0,000 s |
| `mask_for` ×9 | 0,014 s | 0,014 s |
| **`average_stable` ×9** | **10,94 s** | **11,10 s** |
| a corrida inteira promediada, ×9 | 13,09 s | 13,54 s |
| **`noise_floor` ×9, sozinho** | **14,58 s** | **13,99 s** |
| **`summarise` ×9, com biblioteca** | **21,44 s** | **20,51 s** |
| o veredicto de isolamento ×9 | 0,174 s | 0,174 s |
| `margin.cross_validate` ×9 | 1,64 s | 1,75 s |
| `unexplained.annotate` ×9 | 0,160 s | 0,071 s |
| `library.search` ×9 | 1,59 s | 1,59 s |
| `search_energy` ×9 | 1,59 s | 1,59 s |
| `records_from_summary`, `write_msp` | 0,001 s | 0,001 s |
| `standard_history.history_of` | 0,002 s | 0,001 s |
| `component_from_infusion` ×9 | 0,042 s | 0,041 s |
| `energy.recommend` | 0,001 s | 0,001 s |
| o parágrafo da capa | 0,000 s | 0,000 s |
| o CSV do resumo | 0,002 s | 0,002 s |
| salvar o projeto | 0,001 s | 0,001 s |
| `compare_infusions` | 0,003 s | 0,003 s |
| `quantify_infusions` | 0,000 s | 0,000 s |

Memória residente de pico para tudo isso em um processo: **0,73 GB**. A rota
de pasta da [[command-line]], que faz o mesmo trabalho e ainda diagrama um
PDF de 58 páginas, segura **1,15 e 1,21 GB** em duas execuções e leva **52 s
e 42 s** — os segundos sendo o único número aqui que é da máquina e não do
programa, como aquela página diz.

Três coisas seguem da tabela, e só a terceira era esperada.

**Ler e promediar é o custo inteiro.** `average_stable` e o piso de ruído são
25 dos 27 segundos; cada medição feita *sobre* o espectro promediado — a
explicação, a margem, a busca na biblioteca, o perfil de energia, a anotação,
a comparação, as exportações — dá menos de 5 s para as nove juntas, e treze
das vinte e três etapas ficam abaixo de um centésimo de segundo. Qualquer
coisa que valha otimizar neste caminho está em `spectrum_rt_range`, e nada
mais vale otimizar.

**Quente não compra nada.** Só abrir os arquivos sai mais barato da segunda
vez (0,258 s → 0,014 s), porque os identificadores do `.wiff` continuam
abertos. Toda etapa que lê espectros custa o mesmo na segunda passagem que na
primeira: 10,94 → 11,10 s, 21,44 → 20,51 s. O leitor não guarda um espectro
promediado, então *Measure* na aba Infusions paga o preço cheio toda vez que
é apertado, e um script que promedia uma corrida duas vezes lê o arquivo duas
vezes.

**Deixar de fora as varreduras instáveis é mais rápido do que mantê-las.**
10,94 s contra 13,09 s, porque os trechos da máscara têm menos varreduras do
que a corrida. A máscara em si custa 1,6 ms por arquivo — um cromatograma,
nenhum espectro.

## Onde dois módulos discordaram

Nove destes foram achados rodando o caminho de ponta a ponta e comparando os
números que cada etapa relatou para o mesmo arquivo. Seis eram pequenos o
bastante para consertar e estão consertados; três estão registrados abaixo
com os seus números.

### A contagem de marcações, dobrada duas vezes

`infusion_report.labelled_formula` devolve uma fórmula com as marcações que o
nome declara **já incorporadas**, junto com quantas incorporou —
`("C24H36D4O5", 4)` para um componente chamado `CA-d4` que carrega
`C24H40O5`. `axis_subject`, que escolhe a fórmula de onde a escada de massas
de travamento é construída, tomava as duas e incorporava as quatro marcações
uma segunda vez, então todo padrão d4 virava um d8: `C24H32D8O5`, do qual
nenhum aduto fica a menos de 4 Da dos 430,35 que o canal isola.

A consequência era silenciosa e total. **Todas as nove infusões recusavam o
seu próprio eixo de massas** com *nenhuma massa de travamento … 430,34 não é
nenhum dos adutos de C24H32D8O5*, enquanto o veredicto de isolamento duas
linhas acima na mesma página dizia *430,34 = [M+NH4]+ de CA-d4* — as duas
rotas lendo uma única tabela de componentes e discordando sobre o que o
composto é. Com as marcações incorporadas uma vez só, **sete das nove ajustam
uma correção** de 3 a 8 degraus, entre −8,6 e +6,6 ppm; as duas aquisições
`_TESTEARTIGO` continuam recusando, o que está correto, e agora nomeiam a
fórmula certa ao fazê-lo.

### O comentário do registro contava varreduras que não estavam nele

O título do painel, o cabeçalho do relatório e a coluna *Scans* da aba
Infusions todos dizem `464 of 473` na corrida CID de DCA-d4. O comentário de
um registro escrito a partir daquela linha dizia `average of 473 scans`:
`records_from_summary` escrevia `report.scans`, que é quantas a *corrida*
tem, onde os outros três escrevem quantas foram promediadas. Quatro relatos
de uma única média, um deles contando nove varreduras em que o spray havia
falhado. Agora escreve `scans_averaged()`, que é o número com que os outros
três já concordam.

### A verificação de pasta relatava os metadados do próprio macOS como uma varredura órfã

Ler as nove de um disco externo criou
`._CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1.wiff.scan` — o arquivo AppleDouble
que o Finder escreve ao lado de todo arquivo em um volume que não é APFS, que
é por onde dados de instrumento de fato viajam. Ele termina em `.scan` e o seu
radical não está em pasta nenhuma, então [[checking-files]] o relatava como
*uma varredura órfã que não pertence a nenhum .wiff nesta pasta*: um achado
sobre um arquivo que a pessoa nunca fez e sobre o qual não pode agir. Um
`._X.wiff` seria pior — `raw.is_supported` diz que sim, e ele teria entrado na
lista de arquivos a abrir. Nomes que começam com ponto agora ficam de fora
quando uma pasta é listada. Um arquivo com ponto nomeado explicitamente na
linha de comando ainda passa, porque um caminho que foi dado foi querido.

### A capa parou de dizer o que havia de errado com os dois arquivos estranhos

A capa do relatório de pasta soma a sua tabela uma frase por vez, e a frase
dos precursores existe para separar um erro de massa de um íon diferente:
*2 cujo método isola 839,56* é um achado diferente de *1 a +30,3 ppm*. Ela
perguntava pelo erro primeiro e pelo isolamento depois, então uma linha com
qualquer erro mensurável nunca chegava ao balde do isolamento. Isso era
inofensivo até o piso de ruído passar a ser medido a partir da aquisição em
vez de fixado em cem contagens — depois disso **todas as cinco linhas não
confirmadas tinham um erro a relatar** e `isolated_precursors`, que existe
inteiramente por causa destes dois arquivos, virou código morto. A capa dizia:

> 4 of 9 precursor(s) confirmed within 25 ppm; 5 not: 5 between −70.7 and
> +30.3 ppm.

o que relata as duas aquisições `_TESTEARTIGO` como um instrumento
ligeiramente descalibrado, quando o que aconteceu é que o método delas isola
uma massa que não é aduto nenhum do composto que o nome afirma. Agora o
isolamento é perguntado primeiro, e ela diz:

> 4 of 9 precursor(s) confirmed within 25 ppm; 5 not: 2 whose method
> isolates 839.56, 3 at −70.7 and −30.1 and +30.3 ppm.

`isolated_precursors` só responde onde o composto tem outro agrupamento que
*de fato* confirmou, então perguntar primeiro não pode engolir uma falha
comum.

### A API promediava um espectro diferente do da aplicação

`api.Acquisition.infusion_average` dizia na sua própria documentação que era
"a vista com que o Explorer abre uma infusão" e promediava a corrida inteira,
rajadas de spray incluídas. Nas três das nove cujo spray falhou ela discordava
do Explorer, do [[infusion-report]] e de `api.infusion_report` em 0,62%, 1,99%
e 2,90% do pico base, e relatava 473, 473 e 257 varreduras onde a aplicação
relatava 472, 464 e 256.

Pior, discordava de si mesma: `api.infusion_report` explicava *aquele*
espectro e buscava a biblioteca com ele, depois chamava `report_for`, que
promedia de novo com a máscara, e **imprimia o espectro mascarado ao lado dos
números medidos sobre o não mascarado**. Ambos agora usam a máscara, então a
figura do documento e os seus números saem de um único arranjo.

### A quantitação por infusão media respostas sobre as rajadas

`infusion_quant.centroids_of` também promediava a corrida inteira, então uma
resposta lida para uma razão e a altura do mesmo íon na página ao lado saíam
de dois espectros diferentes — em 2,90% na corrida CID de DCA-d4. Uma razão
entre duas respostas existe para dividir esse tipo de coisa e não divide,
porque a rajada está na corrida de um frasco e não na do outro. Agora ela
toma a amostra também e aplica a máscara onde a amostra lê como infusão.
Medido nas nove, o pico base se move −0,62%, −1,99% e −2,90% nos três
arquivos que perdem varreduras e fica inalterado, no dígito, nos outros seis.

## Ainda em aberto

### Há dois pisos de ruído, e os dois estão certos

`infusion.noise_floor_for(channel)` mede o piso a partir da **corrida
inteira**, em cache por canal; é isso que o piso de rótulos e a linha de
estado do [[explorer]] usam. `report_for` mede de novo a partir da **média
mascarada, com a contagem de varreduras que entraram nela**, e é isso que o
[[infusion-report]], a sua tabela de picos e o seu portão de precursor usam.
Nas nove:

| | corrida inteira | o do relatório |
|---|---|---|
| menor | 0,068 | 0,068 |
| maior | 3,53 | 4,27 |
| CA-d4 CID | 0,962 | 1,429 |
| DCA-d4 CID | 0,583 | 0,753 |
| TDCA-d4 CID | 2,447 | 4,272 |

Os dois são defensáveis — o segundo é medido sobre o espectro efetivamente
impresso, que é a coisa certa para uma página usar como portão dos seus picos
— e o manual vinha citando as duas faixas em lugares diferentes sem dizer
qual era qual. Esta página é onde elas são nomeadas. Nada é decidido de forma
diferente pelos dois nestes arquivos, porque um pico ou é oitenta vezes o
fundo ou é um décimo dele, e nunca fica no meio. O que decidiria algo de
forma diferente é um pico a menos de um fator de dois do piso, e nenhuma das
nove tem um.

### Um registro não bate com a sua própria corrida em 100

O manual vinha dizendo que um registro próprio pontua 100 contra o espectro do
qual foi feito, "o que prova que o arquivo foi escrito e lido de volta".
Medido agora: **97, 96 e 100** para as três corridas CID. A pontuação reversa
é 100 nas três e cada um dos picos do registro é encontrado — *179 of its 179
peak(s) matched* — de modo que a ida e volta é exata e é a pontuação direta
que não é 100.

A causa é que o registro e a consulta são escolhidos do mesmo espectro por
duas regras diferentes. Um registro é escrito a partir de `row.peaks`, que é
`pick_peaks` a um por cento do pico base, limitado a 200, fundindo máximos
mais próximos que `OWN_MIN_DISTANCE`. A busca lê `_sticks`, que é cada
centroide do perfil. Na corrida CID de CA-d4 são 179 picos contra 819
centroides, **204 dos quais estão em ou acima de um por cento** — então a
consulta tem 25 picos em altura pontuável que o registro nunca recebeu, e um
cosseno direto sobre tudo o que os dois espectros têm não pode chegar a 1.

| | picos do registro | centroides | destes, ≥1% | pontuação | reversa |
|---|---|---|---|---|---|
| CA-d4 CID | 179 | 819 | 204 | 97 | 100 |
| DCA-d4 CID | 191 | 1.100 | 226 | 96 | 100 |
| TDCA-d4 CID | 25 | 470 | 25 | 100 | 100 |

Nenhum dos dois lados está obviamente errado: uma busca de biblioteca deve
ver o espectro inteiro, e um registro não deve carregar trezentos picos. Então
nada é mudado aqui, e o que o manual deve citar como prova da ida e volta é a
pontuação **reversa** e a contagem *N de N*, ambas exatas.

### Os dois documentos de infusão não relatam os mesmos íons

`python3 -m milq.app --infusion-report` e
`milq.api.infusion_report` ambos escrevem "o relatório de infusão" e
ambos recebem os mesmos nove arquivos, e não concordam sobre quanto foi
explicado:

| | a CLI, e a aba Infusions | `api.infusion_report` |
|---|---|---|
| CA-d4 EAD 12 eV | 3 de 56, 85,0% | 4 de 882, 85,9% |
| CA-d4 EAD 22 eV | 8 de 56, 63,6% | 15 de 882, 71,2% |
| CA-d4 CID 45 eV | 2 de 56, 24,2% | 8 de 882, 32,5% |
| DCA-d4 CID 40 eV | 3 de 41, 17,0% | 7 de 882, 21,7% |
| TDCA-d4 CID 30 eV | 5 de 104, 72,7% | 12 de 2.241, 86,4% |

Os dois estão corretos e estão respondendo a perguntas diferentes. A CLI passa
por `summarise`, que explica a partir da **fórmula da tabela de componentes** e
enumera o precursor com até três perdas neutras — 56 íons para o ácido cólico-d4.
A API resolve o *nome* pela tabela de padrões até um registro do LIPID MAPS com
um desenho e enumera **clivagens de ligação** — 882 íons. Cada um diz o que fez,
na sua própria linha de base (*predicted from the formula alone* contra
*predicted from its structure*), então nenhum mente; mas os denominadores não
são comparáveis e as frações também não, e nada fora desta página dizia isso.
Quem comparar dois documentos do mesmo frasco deve checar a linha de base
antes da fração. `explain_any` é uma terceira resposta ainda — ele roda todas
as rotas e as ordena, e na corrida EAD 22 eV de CA-d4 ele coloca um
triacilglicerol como [M+2H]2+ em *primeiro*, com 95,0%, acima dos 63,6% do
próprio CA-d4, enquanto a margem na mesma página relata CA-d4 à frente desse
mesmo triacilglicerol por 41,9 pontos. A margem pontua os seus rivais nas
configurações com que o composto escolhido foi pontuado; `explain_any` dá a
cada rota as suas próprias melhores configurações. Mesmo espectro, mesmo
rival, duas ordenações.

### As nove não conseguem exercitar a quantitação por infusão

Cada uma das nove isola um precursor, então um analito e o seu padrão interno
nunca estão na mesma aquisição. Pareá-los mesmo assim — CA-d4 e DCA-d4 contra
TDCA-d4 — dá 18 pares em 9 infusões com 6 razões, e as razões são formadas
contra 0,24 contagens de um padrão que não está no frasco.
`quantify_infusions` é exercitado sobre os dados sintéticos de
`tests/test_infusion_quant.py` e sobre nada real; veja
[[infusion-quantitation]] para o que ele precisa, que é uma aquisição
carregando os dois.

## O que ainda reproduz

Rodados de novo contra o código atual, estes voltaram inalterados, no dígito:

- os números de achatamento, 0,9936 a 1,0000 nas duas medidas para todas as
  nove;
- a máscara do spray: 1, 1 e 9 varreduras deixadas de fora nas três corridas
  CID e nenhuma nas outras seis, valendo 0,61%, 1,66% e 2,78% da corrente
  iônica da corrida;
- cada pico base, cada massa de precursor e cada erro em ppm que o
  [[infusion-report]] tabula — 430,3196 a −70,7 ppm e 84 contagens, 430,3489
  a +20,7, 414,3275 a −30,1 e 33 contagens, 504,3273 a +14,4 e 123 contagens;
- os íons encontrados: 2, 8 e 3 de 56 para CA-d4, 3 e 8 de 41 para DCA-d4,
  5 e 5 de 104 para TDCA-d4;
- a frase da margem, palavra por palavra: *explains 63.6%; the best of 17
  neighbour(s) (TG 17:1(9Z)/18:4(6Z,9Z,12Z,15Z)/18:4(6Z,9Z,12Z,15Z) [iso3]
  as [M+2H]2+) explains 21.7%: a margin of 41.9 points*;
- os pisos do relatório que a página cita, 1,43 e 0,75 contagens nas duas
  corridas CID, a 59 e 45 vezes a altura na janela do precursor;
- a linha de resumo, no dígito: *3 compound(s) in 9 infusion(s); 4 of 9
  precursor(s) confirmed within 25 ppm; 34 of 458 predicted ion(s) found
  across 7; 4 with an own record above 60*;
- o documento da pasta com **58 páginas**, nove arquivos lidos e nenhum
  pulado;
- a ida e volta do projeto: nove infusões salvas como números, lidas de volta
  sem abrir arquivo nenhum, e comparadas contra si mesmas a uma mediana de
  100 direta e 100 reversa, o mesmo íon em 9 de 9, nada movido.

Três números mudaram e o manual foi corrigido: as pontuações de um registro
contra a sua própria corrida (100 e 99 → 97 e 96, acima), a frase de
precursores da capa, e a contagem de varreduras do registro.

## Fazendo de novo

O caminho é exercitado de ponta a ponta, sobre os dados sintéticos em vez de
qualquer coisa real, por `tests/test_integration_path.py`. Ele afirma as
concordâncias de que esta página trata em vez dos valores: que o comentário
do registro diz o que o cabeçalho do relatório diz, que o eixo de massas e o
veredicto de isolamento nomeiam uma só fórmula, que a média da API é a média
da aplicação, e que o piso de ruído contra o qual um relatório faz o seu
portão é o que ele imprimiu. Um número mudar é uma medição; esses quatro
mudarem é uma contradição, e o teste está lá para tornar a diferença visível.

---
title: Um padrão novo, a partir do frasco
---
**File ▸ New standard…**, e **New standard…** na aba Infusions, é todo o
caminho de um frasco até um padrão interno em funcionamento, num só lugar: o
componente no método, o registro na sua própria biblioteca e, com ele, o
primeiro ponto do histórico desse padrão.

Cada etapa disso já existia e nenhuma delas estava ligada às outras. O frasco
era infundido; a [[direct-infusion|infusão]] era promediada; o
[[infusion-report|relatório de infusão]] dizia o que ela era; *Use in method…*
escrevia o componente; *Add spectrum to library…* escrevia o registro; e o
número do lote ficava escrito no tubo e em mais lugar nenhum. Nada levava um
nome digitado uma única vez por todo esse percurso, e nada dizia depois que o
componente, o registro e a entrada do histórico são o mesmo material.

## O que você dá, e o que é lido

Quatro coisas são suas para dar, porque nenhuma aquisição as contém:

| Você dá | O que isso faz |
|---|---|
| **Name** | resolvido enquanto você digita — os padrões de ácidos biliares pela abreviação do frasco, depois LIPID MAPS, depois a nomenclatura abreviada de lipídios — para uma fórmula, o identificador LIPID MAPS quando existe, e as marcações que um `-d4` no fim declara |
| **Bottle / lot** | vai para a procedência do componente e para o comentário do registro. O único fato sobre um padrão que nenhum arquivo carrega e que nada recupera depois: é ele que diz que dois registros com seis meses de diferença são o mesmo material |
| **Infusion** | a aquisição. Ela precisa ser lida como uma infusão — as duas medidas de planura de uma [[direct-infusion|infusão direta]] — porque tudo aqui é a média de uma corrida inteira |
| **Expected adducts** | quais íons se espera que este composto dê |

Todo o resto é lido do arquivo: a polaridade, o canal e o precursor escrito
nele, a energia de colisão, a ativação, quantos scans existem e a média de
todos eles.

A **fórmula** é preenchida a partir do nome e continua editável — uma
resolução é uma proposta e uma fórmula digitada é uma decisão. **Unplaced
labels** é um campo próprio, em vez de algo lido do nome, porque as marcações
são entregues à previsão como uma *contagem*: cada fragmento previsto é
oferecido carregando de 0 a n delas e o espectro diz quantas ele manteve. Veja
[[lipid-maps]] para saber por que essa é a única forma honesta de pontuar um
padrão marcado.

## Os aductos esperados

Escolhido o arquivo, todos os aductos daquela polaridade são listados com
quanto pesariam para esta fórmula e a que distância isso fica do precursor que
o canal realmente recebeu — e os que o alcançam ficam marcados. A lista
inteira é mostrada, e não apenas os que servem, porque um erro informa tanto
quanto um acerto: um precursor que não é nenhum deles significa que a fórmula,
as marcações ou o arquivo não são deste composto.

O aducto marcado que melhor se ajusta é aquele com o qual o componente é
escrito. Marcar um que não serve para nada não é ignorado em silêncio: ele é
levado adiante como declarado, e, quando algum outro aducto alcança o
precursor escrito, é esse que é tomado, e a linha de base sob a prévia diz
qual marcação foi deixada de lado — o canal é uma medida e uma marcação é uma
expectativa. Quando nenhum deles o alcança, nada é identificado e nada é
escrito.

## O que a prévia mostra

Nada nela é digitado. O aducto com a frase que o identificou — confirmado
contra a varredura de survey quando a aquisição tem uma, e lido apenas do
precursor escrito quando não tem; a massa exata desse aducto ao lado do número
com que o canal foi escrito, em ppm (veja [[accurate-precursor]]); o pico base
do espectro promediado e os mais intensos seguintes, cada um rotulado com o
íon a que a explicação o associou; quantos dos íons previstos foram
encontrados e que fração da intensidade medida eles explicam; e a pureza
isotópica quando o envelope pôde ser resolvido — e a recusa dela, no mesmo
lugar, quando não pôde.

Abaixo disso está o que **Create** escreveria, para que possa ser lido antes
de ser escrito.

## O que Create escreve

Duas coisas, e nada mais:

1. **O componente**, na tabela de componentes do
   [[method-workspace|Method]]: a fórmula marcada, o aducto, a massa **exata**
   desse aducto como precursor — nunca o valor arredondado com que o canal foi
   digitado — o pico base como fragmento, nenhum tempo de retenção (uma
   infusão não é uma separação e não tem nenhum a dar), o grupo `standards`, a
   caixa de padrão interno marcada a menos que você a desmarque, e a
   procedência por extenso com o lote nela. Um composto que o método já
   carrega tem as células **vazias** preenchidas e nada mais; veja
   [[internal-standards-and-qualifiers]].
2. **O registro**, acrescentado à sua própria biblioteca — o mesmo MSP em
   que a aba [[spectral-library|Library]] e a aba Infusions escrevem: o
   espectro promediado e centroidado com a fórmula, o aducto, a energia de
   colisão, o dia em que o instrumento mediu, a altura absoluta do pico base e
   a procedência com o lote no comentário.

Um composto que o método já carrega por inteiro não deixa componente algum
para escrever, e o registro é escrito mesmo assim: uma segunda infusão de um
padrão é uma segunda verificação dele, e uma verificação é uma entrada de
histórico. A linha de estado diz qual dos dois vai acontecer antes de
**Create** ser pressionado, e a entrada de auditoria diz qual aconteceu
depois.

**O histórico não é escrito, porque o histórico é a biblioteca relida.** É só
isso que o [[standard-history|histórico do padrão]] é: os registros de um
composto ordenados pelo dia em que foram adquiridos. O registro
recém-acrescentado *é* a entrada mais nova desse padrão, e a linha de
auditoria diz quantas o arquivo agora tem dele. Uma única entrada na
[[audit-trail]] nomeia as três coisas.

## Onde ele recusa

Três recusas, e cada uma desabilita **Create** e diz por quê no lugar a que
ela pertence, em vez de escrever um componente com uma massa inventada:

- **o arquivo não é uma infusão** — com as duas medidas que dizem isso, por
  amostra;
- **o nome não resolve para fórmula alguma e nenhuma foi digitada** — não há
  do que um aducto ser aducto;
- **o precursor escrito não é aducto nenhum da fórmula** — os mais próximos
  são nomeados, com a distância de cada um.

## Medido

`cholic acid-d4`, lote `CDN-D-2452`, numa infusão real de ZenoTOF
(`CA-d4_TOFMSMS_Mix1.wiff`, 473 scans, CE 45 eV, sem varredura de survey). O
nome resolveu para `C24H40O5` pela tabela de padrões, com 4 marcações não
posicionadas e `LMST04010001`; um dos cinco aductos positivos de `C24H36D4O5`
alcança o `430.35` escrito, e é `[M+NH4]+`, em 430.3465 — **+8,1 ppm** do
número que o canal recebeu, que é a diferença entre a massa que foi dita ao
instrumento e a massa que o composto tem. O pico base é 359.2869 com 5.638
contagens, associado a `[M+H-3H2O]+ +4D`; 2 dos 56 íons previstos foram
encontrados, explicando 24,2% da intensidade naquela energia de colisão; a
pureza recusou a si mesma, porque o quadrupolo levou os satélites de que o
envelope teria sido lido. O componente saiu `430.3465 → 359.2869`, `C24H36D4O5
[M+NH4]+`, sem tempo de retenção; o registro carrega 179 picos.

Abrir o arquivo, promediar a corrida e identificar o composto levou **2,6 s**
numa execução fria e 1,6 s numa segunda, com o cache de arquivos quente;
depois disso, editar o nome, a fórmula ou um aducto reidentifica em **0,05 a
0,08 s**, porque a média é guardada e só a aritmética é refeita. Escrever o
componente, o registro e a entrada de auditoria levou **menos de 0,01 s**.

A recusa, em `CA-d4_TOFMSMS_EAD_12CE_44DP_13KE_TESTEARTIGO.wiff` — um arquivo
com nome de CA-d4 cujo método isola 839.56: **0 de 5** aductos de `C24H36D4O5`
o alcançam, sendo o mais próximo `[M+K]+` em 451.2758, a 388.2842 Da de
distância. **Create** fica desabilitado, a prévia diz que não haverá
componente, nem registro, nem entrada de histórico, e nada é escrito.
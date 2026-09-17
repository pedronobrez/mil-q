---
title: Infusão direta
---
Numa infusão direta não há coluna. A amostra é pulverizada na fonte por um
minuto ou dois e cada scan é o mesmo espectro mais ruído, de modo que o
cromatograma não carrega informação e o que vale olhar é a média da corrida
inteira. Aberta como se fosse uma corrida cromatográfica, uma infusão pede ao
leitor que escolha o canal de íons produto na árvore, arraste com Shift uma
faixa sobre uma linha plana e só então obtenha um espectro que valha mandar
para o [[lipid-maps]] ou para a [[spectral-library]].

O [[explorer]] reconhece uma infusão quando uma amostra é aberta e começa
pela média em vez disso.

## Como ela é detectada

Duas medidas, ambas de cromatogramas — nenhum espectro é lido, de modo que o
veredito não custa nada a mais e vale tanto num `.wiff` cujo `.wiff.scan`
está faltando quanto na mesma aquisição convertida para mzML:

- a fração do **cromatograma de íons totais da amostra** que fica em ou acima
  da metade do seu próprio máximo;
- a mesma medida sobre **o canal mais forte** — o canal de íons produto que
  carrega mais sinal, ou o survey se o método não tiver varredura de íons
  produto.

Esse máximo é o **scan do percentil 99, não o maior deles**, tomado sobre os
scans que sobram depois do **primeiro segundo de aquisição**. O maior é um
único scan, e um transiente de pulverização também é: três das nove infusões
reais medidas carregam um logo no início da aquisição, de duas a quatro vezes
a mediana da corrida, e metade desse pico fica acima de todos os outros scans
de uma corrida perfeitamente plana. Pôr de lado o um por cento mais alto dos
scans não custa nada numa corrida que tenha um pico de verdade — um pico são
muitos scans — e é a diferença entre ler essas três infusões em 0.002 e
lê-las em 1.00. O primeiro segundo sai porque um por cento de uma corrida
*curta* volta a ser um único scan; veja adiante. As medidas mostradas ao
pairar sobre a amostra dizem qual referência foi usada.

Ambas têm de ser de pelo menos **75%**. Um pico é, por definição, estreito
contra a corrida em que está, de modo que uma corrida com qualquer pico
dentro dela passa a maior parte dos seus scans bem abaixo da metade do ápice;
uma pulverização que apenas deriva fica acima dela do primeiro ao último
scan. As duas medidas são necessárias em vez de uma: um método agendado
adquire cada transição sobre a sua própria janela, e a soma de muitos picos
em tempos diferentes é mais plana que qualquer um deles, ao passo que uma
transição única de um branco é plana por estar vazia.

E uma corrida plana com menos de **120 scans** não é chamada de infusão de
jeito nenhum. Ela é relatada como **too short to tell** (curta demais para
dizer), com as duas medidas, e tratada como não sendo infusão. Por quê, e por
que 120, está na última seção desta página.

## Os números por trás dos limiares

Medido em todas as aquisições disponíveis — quarenta e oito delas, as duas
populações, corridas inteiras, **nenhuma das quarenta e oito classificada
errado**:

| conjunto de aquisições | n | TIC da amostra | canal mais forte |
|---|---|---|---|
| ZenoTOF 7600, 0.6 – 2.0 min, 146 – 473 scans, infusões de íons produto de padrões de ácidos biliares | 9 | 0.9936 – 1.0000 | 0.9936 – 1.0000 |
| TripleTOF 5600, 21.4 min, 577 scans, 81 canais, MRM-HR | 5 | 0.019 – 0.057 | 0.030 – 0.097 |
| TripleTOF 5600, 14.6 min, 61 scans, 144 canais | 26 | 0.033 – 0.433 | 0.017 – 0.383 |
| ZenoTOF 7600, 24.0 min, 482 – 490 scans, 25 canais, DIA | 8 | 0.031 – 0.364 | 0.015 – 0.060 |

Os casos cromatográficos mais difíceis são ambos apanhados pela segunda
medida. Uma equilibração de coluna sem injeção nenhuma — solvente
pulverizando por 24 minutos, o mais próximo de uma infusão em todo o conjunto
— mede 0.364 no total da amostra contra 0.060 no seu canal mais forte. Um
branco que mede 0.383 no seu canal mais forte mede 0.050 no total da amostra.
Nas trinta e nove corridas cromatográficas, a menor das duas medidas nunca
passa de **0.1167**, e nas nove infusões nunca cai abaixo de **0.9936**. O
limiar de 0.75 fica, portanto, 0.633 acima da pior corrida cromatográfica e
0.244 abaixo da pior infusão, dentro de uma folga de 0.877.

Essa folga não existia antes de a referência mudar. Lidas contra o maior
scan, três das nove infusões mediram 0.0021, 0.0039 e 0.0063 — **abaixo de
todas as trinta e nove corridas cromatográficas**. As duas populações não
estavam apenas sobrepostas, estavam invertidas, e nenhum limiar as teria
separado. Um único scan fez isso: um transiente em 0.008 min, de 2.8 a 4.4
vezes a mediana da corrida, e num dos arquivos mais duas rajadas no meio
dela. A estatística estava errada, não o limiar — e é por isso que a
referência agora é o scan do percentil 99.

O percentil 99 está onde está porque foi medido. O 99.5 não basta — os três
scans com pico de um dos arquivos são 0.63% dos seus 473, de modo que
sobrevivem a ele, que lê 0.639 — enquanto o 95 e o 90 levantam as medidas
cromatográficas para 0.262 e 0.410 ao pôr de lado ápices de picos reais. A
maior margem medida é 0.895 no percentil 99.2 e 0.879 no 99.

## Corridas curtas, e a resposta "too short to tell"

Um percentil põe de lado uma *fração* dos scans, e um por cento de uma
corrida curta é um scan. Cada uma das quarenta e oito aquisições foi truncada
aos seus primeiros 20, 30, 50, 75 e 100 scans e lida de novo. Só com o
percentil, a pior das nove infusões lê:

| primeiros N scans | pior infusão | pior corrida cromatográfica |
|---|---|---|
| 20 | **0.0500** | 0.9500 |
| 30 | **0.0333** | 0.9667 |
| 50 | **0.0200** | 0.6735 |
| 75 | **0.3333** | 0.8919 |
| 100 | 0.9900 | 0.9394 |
| a corrida inteira | 0.9937 | 0.1148 |

As três infusões com transiente ficam invertidas outra vez, até oitenta scans
e não até os cem que se supunha. Deixar o **primeiro segundo de aquisição**
fora tanto da referência quanto da contagem resolve isso por completo, porque
é ali que está o transiente — scan 1, meio segundo depois do início — e
depois disso o lado das infusões deixa de se mexer com o comprimento:
**1.0000 em cada uma dessas truncagens**, e 0.9936 na corrida inteira. Outras
duas regras foram medidas e são piores. Deixar o primeiro segundo fora e
voltar ao maior scan como referência falha na corrida inteira, onde um
arquivo tem mais duas rajadas um minuto adentro e lê 0.0043. Fazer a
referência ser a mediana dos poucos scans mais altos, com esse "poucos"
amarrado ao comprimento da corrida, sobrevive a um pico mas não a três, e lê
0.0100 nesse mesmo arquivo.

A coluna da direita da tabela acima é a parte que nenhuma referência conserta,
e é por isso que corridas curtas e planas são recusadas. Um gradiente cortado
antes de qualquer coisa eluir é plano, e "plano" é tudo o que essas duas
medidas medem. Uma corrida real do conjunto não carrega nada até 8.9 minutos:
**os seus primeiros cem scans leem 1.0000 no total da amostra e 0.9388 no seu
canal mais forte**, que é exatamente a assinatura de uma infusão. Nada num
cromatograma distingue as duas, porque não há nada ali para distinguir — as
duas são uma linha plana.

Assim, o limiar de 0.75 não separa as duas populações em comprimento nenhum
abaixo de 240 scans, que é mais do que tem a infusão real mais curta. O piso
vai para onde o resto da medição o sustenta: fora esse único arquivo, nenhuma
das trinta e nove corridas cromatográficas lê como plana depois de **35**
scans, e a infusão mais curta medida tem **146** — de modo que o piso é
**120**, entre os dois. Abaixo dele uma corrida plana é relatada como *too
short to tell* e tratada como não sendo infusão.

O piso vale só para a resposta "plana". Uma corrida que mostra estrutura é
cromatográfica em qualquer comprimento, e é por isso que as vinte e seis
corridas de 61 scans continuam lendo "chromatographic" com as suas medidas em
vez de "too short to tell". E a perda é real e está declarada: uma infusão
genuína com menos de 120 scans seria recusada, assim como aquele gradiente no
trecho entre 154 e 234 scans em que ele ainda é plano. Errar o veredito é
barato de propósito — ele só decide o que é mostrado primeiro.

Três outras regras foram tentadas e rejeitadas, com números, em
`milq/infusion.py`: a correlação espectral de scan a scan (0.85 – 0.99
nos canais de íons produto de corridas em gradiente comuns, que é o canal que
importa), o coeficiente de variação do cromatograma de íons totais (sem
margem contra um branco, e que pune a deriva da pulverização) e a ausência de
um pico detectado (um traço plano com 3% de ruído ainda rende três).

## Scans que a pulverização perdeu

Uma eletronebulização não fica estável pela corrida inteira. Ela arqueia, uma
gotícula alcança o cone, a agulha molha: a corrente iônica total deixa o nível
que vinha mantendo por um scan ou alguns e volta. Esses scans não são o que o
composto parece, e incluí-los na média com o resto levanta a resposta.

Por isso a média da corrida inteira os deixa de fora, e diz quantos e onde. Um
scan é **instável** quando a sua corrente iônica total se afasta da mediana
móvel dos seus **21 scans vizinhos** em mais de **50%**, e os scans seguintes
continuam instáveis até a corrente voltar para dentro de **25%**. Todo o resto
entra na média. O título do painel, o cabeçalho do [[infusion-report]], a
coluna *Scans* da aba Infusions e o comentário de um registro escrito numa
biblioteca sua carregam todos a mesma linha:

> 473 scans, 464 averaged; 9 left out: 0.008 min; 1.069–1.099 min, 8 scans

Um único scan é nomeado pelo seu tempo e um trecho é dado pelos seus extremos.
Onde nada foi deixado de fora, o título continua sendo *average of N scans*,
exatamente como antes.

**Process ▸ Include unstable scans** faz a média da corrida como ela saiu do
instrumento. Vem desligado e é lembrado entre sessões; com ele ligado, o
relatório diz quantos scans instáveis foram mantidos e onde estavam, de modo
que um documento feito de qualquer um dos dois jeitos diz qual dos dois é.

### Os números por trás disso

Medido nas nove infusões reais. O afastamento de cada scan em relação à sua
própria mediana móvel foi lido, e as duas populações não se sobrepõem: o maior
afastamento de uma pulverização que nunca falhou é **0.316** (uma corrida CID
cuja pulverização vagueia), e o menor afastamento dentro de uma rajada de
verdade é **0.870**. A contagem de scans excluídos é a mesma em todo limiar de
0.35 a 0.85, de modo que 50% é o meio de um platô e não um valor ajustado. A
janela é de 21 scans porque uma mediana móvel sobrevive a uma perturbação de
até metade da sua largura e a mais longa medida tem oito scans: com 11 scans a
rajada decide a sua própria linha de base e seis scans são encontrados, com 15
oito, e de 21 em diante nove — e aí a contagem para de se mexer.

O pico base foi medido ao lado do total e não é usado. Ele é de quatro a oito
vezes mais ruidoso — nas seis infusões sem rajada nenhuma ele se afasta da sua
própria mediana móvel em até 0.585, onde o total nunca passa de 0.164 — de modo
que qualquer limiar sobre ele que pegue uma rajada também pega scans comuns de
uma pulverização estável, e todo scan que ele marca nos arquivos que de fato
têm rajada o total também marca.

A faixa de recuperação é o que pega os scans no meio de uma rajada que não são
nem o pico nem a pulverização: uma rajada real vai a 0.01, 0.03, 0.64, 2.57,
0.63, 0.13, 0.74, 4.68 do seu nível ao longo de oito scans, e três desses nunca
passam de 50% por conta própria. O que ela *não* compra é uma cauda — em toda
rajada e todo transiente medidos, o scan seguinte ao último excluído já está
dentro de 13% do nível, de modo que uma pulverização aqui volta em um scan.

O primeiro segundo de aquisição **não** é descartado. A janela de acomodação
descrita acima existe porque um percentil põe de lado uma *fração* dos scans;
isto mede cada scan contra os seus vizinhos, e o transiente do scan 1 sai a
4.5, 5.1 e 5.0 vezes a sua própria linha de base nos três arquivos que o
carregam — treze vezes o maior afastamento comum. Descartar quatro scans de
toda corrida para pegar o que já está pego seria jogar fora dados contra os
quais nenhuma medida tem objeção.

### O que isso faz com a resposta

Três dos nove arquivos perdem alguma coisa; seis voltam **byte a byte a média
do próprio leitor**, porque uma máscara que não exclui nada pede ao leitor a
corrida inteira numa chamada só e não toca no que volta.

| | scans deixados de fora | da corrente iônica da corrida | pico base |
|---|---|---|---|
| CA-d4 CID | 1 | 0,61% | −0,62% |
| TDCA-d4 CID | 1 | 1,66% | −1,99% |
| DCA-d4 CID | 9 | 2,78% | **−2,90%** |
| as outras seis | 0 | — | 0,00% |

O que muda é a altura, não a forma: pontuada como um registro seu contra a
mesma média tomada do jeito antigo, a pior das três volta com **99.999**. É
esse o ponto. Um espectro é o mesmo composto de qualquer jeito, e o gráfico do
[[standard-history]] segura o pico base do mesmo padrão dentro de 4,5% entre
terços de uma corrida — de modo que uma rajada que vale 2,9% dele é mais da
metade disso, e é uma rajada e não o composto.

A máscara lê um cromatograma, o que dá 1,6 ms por arquivo. Fazer a média dos
trechos sobreviventes não é mais lento do que fazer a média da corrida
inteira: nessas nove, **10,9 s contra 13,1 s**, porque há menos scans nela.
Esse par, e o que cada outra etapa do caminho custa ao lado dele, está em
[[integration]].

### Numa corrida que não é uma infusão

A regra só é aplicada onde a amostra é lida como uma infusão. Um pico
cromatográfico se afasta dos seus vizinhos muito mais do que qualquer
pulverização — é isso que um pico é — de modo que num gradiente de vinte
minutos a mesma aritmética deixa de fora justamente os únicos scans que valem
a pena. O **Average whole run** é oferecido em qualquer canal, então o veredito
acima é a comporta: em qualquer coisa não lida como infusão, todo scan entra na
média.

## O que muda

Para uma amostra lida como infusão:

- a árvore escreve **infusion** ao lado do nome do instrumento, e passar o
  cursor sobre a amostra dá as medidas que a decidiram;
- o seu canal de íons produto mais forte vem marcado e torna-se o **active
  channel** (canal ativo), em vez do survey em que o Explorer aterrissaria;
- o painel do espectro abre na média de todos os scans em que a
  pulverização esteve estável, intitulado *average of N scans (infusion)*
  — ou, onde scans foram deixados de fora, *N scans, M averaged; K left
  out: …* — e **infusion** aparece ao lado do tempo de retenção;
- tudo a jusante vê essa média, porque ela é o espectro ao vivo: a subtração
  de fundo, o *Explain spectrum*, a busca na biblioteca, a tabela de picos, o
  *Pin spectrum* e a exportação CSV.

Nada mais muda. O painel do cromatograma continua desenhando a corrente
iônica total ao longo do tempo, os controles de scan continuam avançando scan
a scan, e o [[contour-view]] continua sendo construído — como um filme, com a
corrente iônica total da corrida ao lado e um Play que percorre os scans. Veja
adiante.

## Vendo a corrida scan a scan

A média é a coisa certa para ler uma infusão e a coisa errada para conferi-la:
um transiente no primeiro scan, uma rajada no meio do caminho e um fragmento
que só aparece depois que a pulverização estabiliza desaparecem todos dentro
dela. Duas coisas devolvem a corrida.

**O filme.** Mude *View* para *Contour* numa infusão e a superfície vem com a
corrente iônica total da corrida como uma faixa no mesmo eixo de tempo, os
scans deixados de fora da média marcados com ✕, e **Play**, que percorre o
painel de espectro por todos os scans da corrida. Um fragmento é uma crista
percorrendo toda a corrida; um transiente de pulverização é uma coluna da
largura de um scan. Veja [[contour-view]] para o que ele mostrou nas
aquisições reais.

**Δ from average** (Δ em relação à média). *Process ▸ Δ from average*,
desligado por padrão e oferecido apenas numa infusão, desenha o scan atual
**menos** a média da corrida inteira, com a média espelhada por baixo — pelo
mesmo interruptor *Mirror* que um espectro fixado usa, que ele liga e depois
devolve como estava. Todo scan de uma pulverização deveria ser o mesmo
espectro, de modo que o que sobra é o que mudou.

A média é interpolada primeiro sobre o próprio eixo de m/z do scan, do jeito
que um fundo é, porque as duas grades não coincidem: no
`DCA-d4_TOFMSMS_Mix1` um único scan carrega de 8,815 a 21,960 pontos contra os
242,308 da média, que é a união das grades de todos os scans. Nada é cortado
em zero — um scan *abaixo* da média é exatamente para isso que isto serve.

Enquanto está ligado, a diferença **é** o espectro ao vivo: a tabela de picos,
a comparação e um pin leem-na. Desligue-o antes do *Explain spectrum*, de uma
busca na biblioteca ou de um relatório, que querem o espectro e não o resíduo.

### O que ele mostrou

Lido por massa nominal no `DCA-d4_TOFMSMS_Mix1`, contra um canal cujo total
fica em 373,000 contagens:

| o scan | o que a diferença diz |
|---|---|
| **scan 1**, 0.0042 min, 0.67× o total mediano | toda a escada abaixo da média — −1,997 em 153, −1,897 em 247, −1,843 em 167. A pulverização não havia estabilizado |
| **scan 262**, 1.0988 min, 4.36× | toda a escada subindo junta — **+118,209 em 361**, +25,520 em 219, +24,949 em 95, e uma diferença de pico de +21,674 contagens. Um evento de pulverização, não uma espécie nova: uma espécie nova seria uma única massa |
| **scan 237**, 0.9938 min, 0.91× | quase nada: o maior ponto isolado difere em −523 contagens contra um pico médio de 2,795 |

**Leia por massa, não por ponto.** A grade de perfil se desloca por uma fração
de ponto entre scans, de modo que o resíduo de um pico sai como um dipolo de
cada lado dele: no arquivo CA-d4 EAD as três maiores diferenças no scan 1 são
+2,457, −2,052 e +1,978 contagens dentro de 0.010 Da de 377.30, que é o mesmo
pico chegando ligeiramente adiantado e não três achados. Somado sobre uma
massa nominal inteira isso se cancela, e o que sobra é a mudança.

## Uma infusão de outro instrumento

Tudo nesta página é lido de cromatogramas, de modo que nada disso depende de
onde o arquivo veio. Uma infusão convertida para mzML — um `.raw` da Thermo,
um `.d` da Agilent, um `.tdf` da Bruker pelo `msconvert` — passa pela mesma
detecção, pela mesma média, pela mesma explicação do [[lipid-maps]], pela
mesma busca na [[spectral-library]] e pelo mesmo [[infusion-report]]. Ver
[[formats]] para o que um arquivo convertido declara sobre cada scan e o que
ele não pode declarar.

Isso foi verificado, não suposto. Uma infusão real de ácido cólico-d4 num
ZenoTOF 7600 foi lida de três maneiras — do `.wiff`, do mzML exportado dele,
e desse mzML reescrito como o ProteoWizard escreve um arquivo Thermo, com
identificadores de scan Thermo, tempos em segundos, uma janela de
isolamento, um estado de carga, HCD nomeado em `activation`, e nada dizendo
a que experimento um scan pertence. As três leram **um canal de íons
produto**, precursor 430,34 a 22 eV, 146 scans ao longo de 0,61 minuto,
**1,0000 nas duas figuras**, e o mesmo espectro médio: pico base 377,3018 a
9.618,10 contagens, 424 centroides, 42 picos acima da fração de ruído, o
precursor sobrevivendo a 430,3489 com 9.415 contagens, e a fórmula
explicando 8 de 56 íons previstos e 63,63% do espectro. O arquivo no formato
Thermo nomeia além disso o seu instrumento, a sua carga e a sua ativação,
que um `.wiff` não carrega.

Duas infusões reais de Orbitrap da Thermo, de um repositório público, também
foram lidas, e nenhuma das duas é chamada de infusão. As duas recusas são a
aquisição e não o formato, e as duas vale conhecer:

- **Uma corrida curta demais para que a planura signifique algo.** Um LTQ
  Orbitrap Elite pulverizando por três minutos dá 108 scans de cerca de 1,7
  segundo cada, o que fica abaixo do piso de 120 scans acima. Ela também lê
  **0,5943** em vez de 1,0000, porque o spray decai ao longo dos primeiros
  dez segundos e só um segundo é posto de lado: a 1,7 segundo por scan, essa
  rampa são seis scans e a janela de acomodação alcança dois deles. Lida a
  mesma corrida com dez segundos postos de lado, dá 0,8812. A janela de
  acomodação é de um segundo porque foi medida em um ciclo de um quarto de
  segundo, onde o transiente é um único scan meio segundo adentro; num
  instrumento mais lento ela é curta.
- **Uma corrida que varre de propósito.** Uma infusão de precursor em passos
  — a janela de isolamento caminhada sobre o precursor em incrementos de
  0,02 Da enquanto a amostra é pulverizada — tem uma corrente iônica que
  sobe e desce com onde a janela está, e não com a eluição. Ela lê
  **0,0123** contra os 0,75 necessários, em toda janela de acomodação
  tentada, e as duas figuras não podem dizer outra coisa: elas perguntam se
  o sinal se mantém, e este não se mantém. Os seus 164 espectros também são
  inferidos como 82 canais de um ou dois scans cada, de modo que nenhum
  canal isolado tem cromatograma suficiente para julgar.

Nos dois casos **Average whole run** dá exatamente a visão que o caminho
automático teria dado, em qualquer canal que se queira; nada fica fora de
alcance.

## Fazer à mão, e sobrepor a escolha

**Average whole run** (promediar a corrida inteira), na barra de ferramentas
Processing, faz o mesmo em qualquer amostra e em qualquer canal, infusão ou
não — útil para um canal que não seja o escolhido, e para uma corrida que a
regra não chamou de infusão.

Para sobrepor a escolha, trabalhe como de costume: escolha outro canal na
árvore ou no seletor **Active channel**, e avance scans ou arraste com Shift
uma faixa no cromatograma, como em [[chromatograms-and-spectra]]. Qualquer
uma dessas coisas substitui a média pelo que foi pedido; nada fica travado.

## O precursor acurado

O [[accurate-precursor]] ancora a sua medida na varredura de survey sobre um
pico no canal de íons produto, ou sobre o tempo de retenção de um componente.
Uma infusão não tem nem um nem outro: não há pico, e um tempo de retenção
copiado de um método cromatográfico aponta para fora de uma corrida que dura
um minuto. Numa infusão a medida toma o meio da corrida como âncora e
promedia a corrida inteira tanto para o survey quanto para o espectro de íons
produto, que é o máximo de sinal que a aquisição pode lhe dar.

## O que o arquivo diz que é, e o que o seu método faz

Uma infusão costuma ser adquirida à mão, e uma aquisição manual anota quase
nada. Lidos por reflexão, os nove arquivos ZenoTOF reais chamam a sua amostra
de `sample`, nomeiam o seu método de `Untitled 1.msm` e deixam
`TargetedCompoundInfo` — o campo em que um método direcionado põe o nome de
um composto — vazio. O que o experimento carrega é uma polaridade, uma faixa
de massas, uma massa fixa, e DP, CE, DPS e CES. **Nenhum composto, em lugar
nenhum do arquivo.** O único lugar em que um composto está escrito é o nome
do arquivo, e é por isso que a coluna *Compound* em toda parte no MIL-Q
se chama uma proposta.

O precursor isolado pelo método é uma segunda resposta à mesma pergunta, e é
a do instrumento e não a de quem digitou. Quando uma infusão é aberta, o
composto com que o seu nome começa é resolvido a uma fórmula e cada aduto
dessa fórmula é medido contra o precursor que o método isola. Onde discordam,
a janela avisa uma vez, ao abrir o arquivo, ao lado do aviso para um `.wiff`
sem o seu `.wiff.scan`:

> CA-d4_TOFMSMS_EAD_12CE_44DP_13KE_TESTEARTIGO: The file is named CA-d4 but
> the method isolates 839.56 over 100–1000, which is no adduct of
> C24H36D4O5 within ±0.05 Da; it fits nothing in the component table or the
> library.

Esse aviso não lê espectro nenhum e levou 32 ms, então chega antes de
qualquer coisa ter sido medida — e nos dois arquivos para os quais foi
escrito, é o achado inteiro: ver *Quando o nome e o método discordam* em
[[infusion-report]] para o que eles acabaram sendo e para a regra que impede
um nome de amostra comum de resolver a um lipídio com que ele apenas se
parece.

A verificação de pasta antes de uma abertura não pode fazer esta verificação
e não é chamada a fazê-la: ela lê nomes e nunca abre um arquivo, por
princípio — ver [[checking-files]]. Nem o [[check-method]], que olha o método
de processamento e nunca uma aquisição. A discordância é entre o nome de um
arquivo e um arquivo, então o lugar de encontrá-la é onde arquivos são
abertos.

## O piso de ruído da média

O espectro de uma infusão é a média de todos os scans da corrida, e
quanto disso é fundo é uma propriedade daquela aquisição e não uma constante.
Ele é medido, do arquivo, assim que uma infusão é aberta: as regiões vazias do
eixo de massa da média de um lado, e a dispersão entre scans de uma janela
silenciosa de meio dalton escalada para o número de scans promediados do
outro, adotando-se o maior dos dois. Nas nove infusões de ácidos biliares ele
sai entre **0,068 e 3,53 contagens**, onde o piso fixo que ele substitui era de
cem; numa delas cem contagens eram quase o espectro inteiro, cujo pico base é
109. O [[signal-to-noise]] traz os dois métodos e o que eles mediram.

Esses são os números do piso que o **Explorer** segura: medido uma vez por
canal a partir da corrida inteira, que é o que o piso de rótulos e a linha de
estado leem. O [[infusion-report]] o mede de novo a partir do espectro que
está prestes a imprimir — a média mascarada, com a contagem de varreduras que
entraram nela — e esse vai de 0,068 a **4,27** contagens nas mesmas nove.
Dois pisos, ambos honestos, nenhum decidindo nada de forma diferente aqui;
[[integration]] os põe lado a lado e diz qual lê qual.

Duas coisas o acompanham no Explorer. O **piso de rótulos** do painel de uma
infusão começa no maior entre os 2% do pico mais alto em vista, que é a regra
do desenho, e o piso de ruído como fração do pico base, e a linha de status diz
qual dos dois foi e quanto o piso mediu — nas nove infusões reais o piso de
ruído fica entre 0,017% e 0,063% do pico base, então os dois por cento vencem
sempre e a regra é uma proteção e não uma mudança. E um registro escrito na sua
própria biblioteca a partir de uma infusão passa a obedecer ao piso além do seu
um por cento do pico base, de modo que o registro não pode carregar picos que
eram fundo.

## Colocando uma no papel

**Process ▸ Report this infusion…** escreve o espectro promediado, os seus
picos, o precursor acurado e o que quer que tenha sido rodado contra ele como
um documento de duas a quatro páginas — ver [[infusion-report]]. Só é
oferecido numa infusão, porque tudo nele é a média de uma corrida inteira. O
seu cabeçalho carrega o par *Named* e *Isolated*, de modo que as duas
afirmações sobre o que o frasco contém são impressas lado a lado.

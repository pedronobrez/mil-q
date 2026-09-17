---
title: O relatório de infusão
---
**Process ▸ Report this infusion…** escreve um composto em duas a quatro
páginas: o documento que vai para o caderno quando um padrão é validado. Um
[[report]] responde o que um lote mediu; este responde algo menor e mais
antigo — *este frasco é o que o rótulo diz?* — e responde listando o que foi
verificado, não aprovando nem reprovando coisa alguma.

A ação só é oferecida enquanto a amostra ativa for uma [[direct-infusion]],
porque tudo o que está na página é a média de uma corrida inteira, o que é
uma mentira sobre uma amostra cromatográfica. **Process ▸ Report every
infusion…** faz o mesmo para todas as infusões abertas, uma seção por
composto num único documento, cada composto começando numa página nova.

## O que cada bloco carrega

**O cabeçalho** vem do arquivo e não do nome dele: a aquisição, a amostra, o
instrumento, a polaridade, o canal de íons produto com o precursor como o
método o escreveu, a energia de colisão, quantos scans foram promediados e
sobre que faixa de tempo — e o precursor acurado, com o seu erro em ppm e
onde ele foi medido. Quando a aquisição tem uma varredura de survey, a medida
é a do [[accurate-precursor]], com o espectro de íons produto como
verificação de que é o mesmo íon. Quando não tem nenhuma — o que é o caso de
todas as nove infusões reais contra as quais isto foi construído; cada uma
tem um único canal de íons produto e mais nada — o precursor é lido do
próprio espectro de íons produto promediado, e o relatório diz isso com todas
as letras.

*Scans averaged* é a linha que a [[direct-infusion]] descreve: quantos scans a
aquisição tem, quantos entraram na média e para onde foi o resto — *473 scans,
464 averaged; 9 left out: 0.008 min; 1.069–1.099 min, 8 scans*. Esses são os
scans em que a pulverização falhou, e um relatório que os deixou de fora diz
isso no cabeçalho e outra vez numa frase do veredito. Com o **Process ▸
Include unstable scans** ligado, os mesmos dois lugares dizem, em vez disso,
que eles foram mantidos a pedido, de modo que um documento diz de qual média
ele é.

**O espectro promediado**, desenhado para o papel no piso de rótulos em que o
painel foi deixado, de modo que as massas impressas são as massas que
estavam na tela — veja [[chromatograms-and-spectra]] para o piso e para como
os rótulos são posicionados. Abaixo dele, os vinte e cinco picos mais
intensos acima desse piso, com as suas intensidades e a sua fração do pico
base, e uma frase dizendo qual foi o **piso de ruído** medido desta aquisição
— as duas estimativas, a que foi adotada e o que promediar a corrida comprou.
Veja [[signal-to-noise]]; é a esse piso que o portão do precursor, os picos
não explicados e um registro seu são todos submetidos, então o número a que
foram submetidos é impresso junto e não deixado para ser adivinhado.

**O aduto**, do qual pende tudo o que vem abaixo. Qual íon o precursor
escrito do canal *é* — protonado, amoniado, sodiado — decide toda massa
prevista, então a linha de base o nomeia, dá a massa exata daquele aduto e
quanto o valor escrito dista dela em ppm, e diz se ele foi lido só do
precursor escrito ou confirmado contra uma varredura de survey. Onde nenhum
aduto da fórmula alcança o precursor escrito, nada é explicado e a linha diz
quais foram as aproximações mais próximas. Veja *Adutos* em [[lipid-maps]] e
o [[accurate-precursor]].

**A explicação estrutural**, quando alguma foi rodada na aba [[lipid-maps]] —
um registro curado, um desenho próprio, ou uma fórmula e as suas perdas. Cada
íon casado com a sua massa teórica, a massa medida, o erro em ppm e, para uma
marcação não posicionada, quantos deutérios o fragmento reteve. Depois, numa
tabela própria, **os picos que ela não explica**: a metade honesta da
resposta, e onde uma impureza co-infundida ou o composto errado aparece.
Cada um deles carrega o que pode ser — um contaminante conhecido, um
satélite de um íon que *foi* correspondido, ou uma composição montada com os
próprios átomos do íon precursor — com o erro desse palpite em ppm, e a
frase embaixo da tabela diz quantos foram explicados de um jeito ou de
outro. Veja *O que os picos não explicados podem ser*, mais abaixo.

Sob os íons casados a seção traz **a margem** — o que este composto explica
contra o que explica o melhor dos seus impostores mais próximos, sobre os
mesmos picos e pela mesma aritmética:

> Margin — CA-d4 explains 63.6%; the best of 17 neighbour(s)
> (TG 17:1/18:4/18:4 as [M+2H]2+) explains 21.7%: a margin of 41.9 points

Uma parcela não é evidência enquanto não houver algo pontuado ao lado dela, e
abaixo de dez pontos a frase diz isso: o espectro não distinguiu os dois
compostos, qualquer que tenha sido a parcela. A aba Infusions traz o mesmo
número como uma coluna **Margin**, com a lista inteira de rivais na dica de
ferramenta. [[lipid-maps]] expõe quais registros contam como impostores, por
que um isômero de mesma fórmula não conta, e os onze espectros reais em que a
linha de dez pontos foi medida.

**A pureza isotópica**, quando o composto carrega marcações e um aduto foi
identificado — o número do certificado que ninguém mede. O bloco é o próprio
envelope: cada degrau de d0 a dn com a sua *m/z*, a sua intensidade, a sua
fração do íon totalmente marcado e a fração ajustada, depois o par de
espécies (`d4 96,2%, ≥d3 99,1%`) e o átomo por cento, que é a grandeza que o
certificado declara e é outro número. Quando o envelope não pode ser
resolvido, os degraus são impressos do mesmo jeito com a razão embaixo,
porque uma recusa é uma afirmação sobre aqueles números e quem não os vê não
pode conferi-la. Esse é o desfecho em todas as nove infusões reais, por uma
razão que o [[lipid-maps]] expõe: o precursor de um espectro de íons produto
passou pelo quadrupolo, e os satélites de carbono-13 de que a solução precisa
foram junto.

**O resultado da biblioteca**, quando uma busca foi feita na aba
[[spectral-library]]: o melhor registro, a sua pontuação e a pontuação
reversa, quantos dos seus picos casaram, a diferença de precursor em ppm, os
dois espectros cabeça contra cauda, e os campos do próprio registro como
foram escritos — o arquivo de onde ele veio, a energia de colisão e a data.
Um registro cuja procedência não está na página não pode ser conferido contra
a aquisição de onde saiu.

**O eixo de massa**, sempre — tenha ele sido corrigido ou não. Uma infusão
direta não tem uma segunda injeção contra a qual ser lida, de modo que ela é
recalibrada contra **si mesma**: o precursor está na média junto com os seus
próprios fragmentos, e a aritmética já sabe onde cada um deles pertence. O
parágrafo nomeia cada degrau encontrado, a sua massa teórica e medida, o seu
erro antes e depois da correção e a sua altura; o deslocamento e sobre
quantos degraus ele se apoiou; e, quando a mesma explicação foi rodada dos
dois modos, quantos íons previstos caíram sobre um pico no eixo como medido e
no eixo corrigido. Quando nada foi corrigido o parágrafo diz isso, com o
motivo — um frasco que foi olhado e deixado em paz é um achado, e uma página
que omitisse o parágrafo deixaria o leitor sem como distinguir um eixo
corrigido de um não corrigido. As regras e o que as nove infusões reais deram
estão em [[mass-recalibration|Uma infusão se recalibra sobre o próprio
precursor]].

**Outras infusões do mesmo composto**, quando houver alguma aberta: cada uma
promediada sobre a sua própria corrida inteira e desenhada cabeça contra
cauda contra esta, com o mesmo cosseno que uma busca em biblioteca usa. O
diálogo marca aquelas cujo nome de arquivo começa com o mesmo composto e
deixa marcar ou desmarcar qualquer uma, porque uma convenção de nomes não é
uma medida.

## O que o veredito afirma e o que não afirma

*What was measured* é uma frase por verificação, e uma verificação que não
foi feita não ganha frase nenhuma:

- **"Precursor confirmed at +20.7 ppm…"**, ou **"Precursor not confirmed:
  …"** com o motivo. Uma janela que contém menos do que o piso de ruído medido
  da própria aquisição não é uma massa: é reportada como pouco demais para
  medir, com a altura que foi encontrada, em vez de virar um centroide tirado
  sobre ruído. O piso era de cem contagens, fizesse o instrumento o que
  fizesse; agora é medido da média — de 0,068 a 4,27 contagens nas nove
  infusões daqui, medido sobre a média mascarada que esta página imprime, que
  não é bem o piso da corrida inteira que o [[explorer]] mostra: veja
  [[integration]] para os dois lado a lado — e a frase diz contra qual dos
  dois recusou. O que supera o
  piso é um pico que está realmente ali; se ele é o composto, quem diz é o ppm
  ao lado, que é outra pergunta e ganha outro número.
- **"8 of the 56 ions predicted for … were found"** — o denominador é quantos
  íons a previsão ofereceu, para que o leitor veja do que a contagem é uma
  fração, e o pico não explicado mais intenso é nomeado ao lado.
- **"Best library record … at score 29, reverse 39"**, com a diferença entre
  os precursores em ppm.
- **"Collision energy differs from the record's (22 against 45 eV)"** — um
  espectro tirado em outra energia tem outros fragmentos, de modo que uma
  pontuação baixa ali é a energia e não necessariamente o composto.
- **"9 scan(s) of 473 were left out of the average: …"**, com os tempos, por
  que cada um saiu e o quanto o resto da corrida se repete. Ela vem por
  último porque não é uma verificação sobre o composto: é um fato sobre o
  espectro em que as verificações acima foram feitas. Uma corrida cuja
  pulverização nunca falhou não ganha frase nenhuma.

Não há aprovação, não há reprovação e não há selo. Se o frasco contém o que
deveria conter é um juízo feito a partir de evidências por alguém que sabe o
que foi pesado nele, e um visto verde não convida ninguém a ler o resto da
página. Quando nada foi rodado, o veredito diz exatamente isso, e o documento
é um espectro e uma tabela de picos — o que é uma descrição justa dele.

Cada relatório escrito fica registrado no [[audit-trail]]: o que foi
relatado, em qual arquivo, e quais das três verificações estavam por trás.

## Medido

Ácido cólico-d4 infundido num ZenoTOF 7600, o mesmo frasco sob duas
ativações, explicado a partir do `C24H40O5` da tabela de componentes — lido
como `C24H36D4O5` a partir das quatro marcações que o nome declara, e como
`[M+NH4]+` porque é isso que o 430,35 do canal é — e buscado contra um
registro feito da corrida CID:

| | CID, 45 eV, 473 scans | EAD, 22 eV, 146 scans |
|---|---|---|
| pico base | 359,2870 | 377,3015 |
| precursor 430,35 no espectro de íons produto | 430,3196 a 84 contagens, 1,49%, **−70,7 ppm** (piso 1,43) | 430,3489 a 9.415 contagens, **+20,7 ppm** |
| íons encontrados, de 56 previstos | 2 — 24,2% da intensidade | 8 — 63,6% |
| contra o registro CID | 97 / 100, o seu próprio registro — veja abaixo | **29 / 39**, 20 de 179 picos |
| energia de colisão contra a do registro | igual | **22 contra 45 eV** |
| contra o mesmo composto a 12 eV | 7 / 29 | 67 / 81 |

Medido sobre a corrida EAD, acrescentando um bloco de cada vez: só o
espectro e os seus picos, **duas páginas**; com o precursor, duas; com a
explicação estrutural e os seus picos não explicados, duas; com o registro da
biblioteca e a sua figura cabeça contra cauda, **três**; com mais uma infusão
comparada, **quatro**. Cada um levou entre 0,3 e 1,0 s para diagramar e
imprimir. Dois compostos num só documento deram oito páginas em dois
segundos.

As duas linhas que vale reler são as duas últimas da coluna CID. A pontuação
na biblioteca — 97, com cada um dos picos do registro encontrado — é um
registro casado contra o espectro do qual ele foi feito, o que prova que o
arquivo foi escrito e lido de volta e mais nada; e
2 de 56 íons é o que uma fórmula com três perdas neutras consegue dizer sobre
um espectro CID cuja escada já correu até o fim — os dois que ela acha são a
perda de três águas e o mesmo íon com uma marcação a menos. Nenhuma das duas
é uma falha do composto, e o relatório é construído de modo que a página diga
qual é qual.

### Pureza isotópica, nos mesmos nove arquivos

O bloco de pureza foi rodado nas nove infusões de ácidos biliares, e todas
elas voltaram como *não medida* — com os seus próprios números na página. O satélite de carbono-13 do íon totalmente marcado, que a
fórmula coloca em 26,5 – 30,0% dele, mede 0,006 – 0,206%:

| infusão | degrau d4 | M+1 medido | razão para a fórmula | leitura |
|---|---|---|---|---|
| CA-d4 EAD 12 eV | 83.712 | 0,006% | 0,0002 | não medida |
| CA-d4 EAD 22 eV | 66.655 | 0,028% | 0,0010 | não medida |
| CA-d4 CID 45 eV | 607 | 0,095% | 0,0036 | não medida |
| DCA-d4 EAD 22 eV | 38.178 | 0,015% | 0,0006 | não medida |
| DCA-d4 CID 40 eV | 296 | 0,150% | 0,0057 | não medida |
| TDCA-d4 EAD 22 eV | 36.447 | 0,020% | 0,0007 | não medida |
| TDCA-d4 CID 30 eV | 2.272 | 0,206% | 0,0069 | não medida |

As duas linhas `TESTEARTIGO` não têm bloco nenhum: nada identificou um íon
para elas — o método delas isola 839,56, que não é aduto nenhum da fórmula
que o nome declara, e *Quando o nome e o método discordam*, abaixo, é o que
elas vieram a ser —, de modo que não há envelope para imprimir.

O número que o envelope *teria* dado, com a verificação desligada, é
98,3 – 99,0% de d4 nos sete precursores — o que ficaria confortavelmente acima
de um `≥98 átomo % D` de certificado e não significaria nada, porque se move
com a energia de colisão: 98,32%, 98,77% e 98,98% em três aquisições do mesmo
frasco de ácido cólico-d4 a 12, 22 e 45 eV. A escada, tentada do mesmo modo,
dá 36,7%, 90,1% e 85,0% para essas mesmas três. **O que os dados dizem é que
estes arquivos não conseguem responder à pergunta**, e um relato honesto da
pureza de um padrão d4 neste instrumento precisa de um minuto de TOF MS ao
lado do canal de íons produto. O [[lipid-maps]] tem a aritmética e o resto das
evidências.

### O que os picos não explicados podem ser

Listar um pico que ninguém explicou como uma massa nua é honesto e não é
útil: o leitor recebe `217,1880` e fica com a tarefa de digitá-lo em outro
lugar. Então cada um dos picos listados recebe a melhor de três hipóteses,
com o seu erro em ppm ao lado — um **contaminante conhecido ou um agregado
de solvente**, um **satélite de um íon que foi correspondido** (o seu pico
de carbono-13, a sua forma sodiada ou potassiada, uma perda de água ou de
amônia a partir dele, outro aduto ou um dímero do precursor), ou uma
**composição montada com os próprios átomos do íon precursor**.

A terceira é a que vale explicar. Uma busca geral de fórmula para uma massa
de 300 volta com uma lista que ninguém lê, mas um espectro de íons produto
não é uma busca geral: um fragmento não pode carregar átomos que o precursor
não tem. As faixas de elementos são, portanto, a própria composição do íon
precursor — os átomos da molécula mais o que o aduto trouxe, com a folga de
dois hidrogênios para cima para um rearranjo — de modo que a pergunta passa
a ser *o que este precursor poderia ter deixado nesta massa*, e um pico sem
resposta nenhuma é um achado: seja o que for, não é um pedaço deste
composto.

Medido em quatro das infusões de ácidos biliares no ZenoTOF, tomando os
vinte e cinco picos não explicados mais intensos de cada uma:

| | não explicados acima do piso | anotados | satélite | contaminante | composição | nada | composição, mediana \|ppm\| |
|---|---|---|---|---|---|---|---|
| CA-d4, CID 45 eV | 126 | 25 | 1 | 0 | 24 | 0 | 8,9 |
| CA-d4, EAD 22 eV | 20 | 20 | 0 | 0 | 20 | 0 | 3,8 |
| DCA-d4, CID | 141 | 25 | 0 | 0 | 25 | 0 | 11,5 |
| TDCA-d4, CID | 9 | 9 | 0 | 0 | 9 | 0 | 5,5 |

Setenta e nove picos, um satélite, nenhum contaminante e nenhuma recusa; as
composições foram de 0,2 a 16,6 ppm e cada arquivo inteiro levou entre 0,02
e 0,07 s. Os mais intensos, um por arquivo, são
`217,1879 → [C16H17D4]+` a −4,6 ppm (14,8% do pico base, CA-d4 CID),
`78,0465 → [C6H6]+` a +0,8 ppm (22,5%, CA-d4 EAD), `95,0842 → [C7H11]+`
a −13,5 ppm (21,2%, DCA-d4), `343,2915 → [C24H31D4O]+` a −5,5 ppm (6,8%,
TDCA-d4) e, no mesmo arquivo, `126,0211 → [C2H8NO3S]+` a −6,3 ppm — que é a
taurina protonada, o fragmento que dá nome a um conjugado de taurina.

Leia o resto da tabela com a mesma desconfiança. Cada linha diz quantas
*outras* composições do mesmo precursor chegam à mesma massa, e no 343,2915
do TDCA-d4 são onze: a restrição estreita a pergunta, não a responde. Os
erros grandes dos arquivos CID são dos próprios arquivos — aqueles espectros
estão vários ppm fora do seu próprio eixo, que é para o que serve a
[[mass-recalibration]], e corrigir o eixo antes aperta todos os números da
última coluna.

Duas coisas dessa tabela foram decididas rodando-a, e não lendo-a:

- **As Sete Regras de Ouro não são aplicadas abaixo de 150 Da.** Elas limitam
  as razões entre elementos de uma *molécula*, e a que atrapalha limita H/C
  a 3,1. A taurina protonada tem H/C = 4,0, então as regras recusaram o
  fragmento real mais intenso do arquivo TDCA-d4 e a tabela dizia "nenhuma
  fórmula dentro da composição do precursor" a respeito de um pedaço que dá
  nome ao composto.
- **Uma composição de elétron ímpar é oferecida, marcada, e fica em último
  lugar.** `78,0465` é o pico não explicado mais intenso da corrida CA-d4
  EAD, a 22,5% do pico base, e é o cátion do benzeno a +0,8 ppm e mais nada.
  A dissociação ativada por elétrons faz radicais; um filtro escrito para
  espectros de dissociação induzida por colisão jogava a resposta fora. Fica
  em último lugar porque num espectro CID costuma ser a resposta errada.

Os contaminantes ganharam o seu lugar por serem raros, não por serem comuns.
Nos quatro arquivos, até um centésimo de por cento do pico base — 3.187
picos — a tabela nomeou cinco: um ftalato em 149,0233, um agregado de
metanol duas vezes, um agregado de ácido fórmico e um de acetonitrila. Nove
eram satélites de íons correspondidos e 710, pouco mais de um quinto, não
tinham nenhuma subfórmula do precursor. Um frasco limpo deve mesmo parecer
com isso; a tabela existe para o frasco que não parece.

As mesmas anotações não estão na lista da própria aba [[lipid-maps]], que
continua mostrando os picos não explicados como massas. Não havia um ponto
de encaixe no painel para pendurá-las e o painel está sendo mexido em outro
lugar; o relatório é onde elas estão.

## Todas as infusões de uma vez: a aba Infusions

Um relatório de um frasco responde uma pergunta. Uma pasta com nove faz outra
— quais delas mediram o seu precursor, quais acharam os seus fragmentos, quais
bateram com o registro feito do mesmo composto no mês passado — e essa é uma
tabela. A aba **Infusions** do [[analytics-workspace]] é ela: uma linha por
amostra infundida, agrupadas pelo composto com que o nome do arquivo começa.

Nada é medido antes de **Measure** ser pressionado: promediar uma corrida
inteira, centroidar um quarto de milhão de pontos, buscar numa biblioteca e
pontuar cada infusão de um composto contra as outras leva alguns segundos por
composto, e uma aba que fizesse isso a cada mudança nos resultados seria uma
aba que ninguém deixa aberta. A contagem de linhas aparece no próprio nome da
aba depois que ela mede.

As colunas, na ordem em que são desenhadas: **Compound** e **Sample**;
**Isolated**, a massa que o método de fato isola, lida contra o nome — veja
*Quando o nome e o método discordam*, abaixo; **Mode** e **CE (eV)**;
**Scans**, quantos foram promediados — *464 of 473* onde a pulverização
perdeu alguns, com a linha inteira ao pairar o cursor; **Base peak m/z**;
depois o precursor de três modos — **Precursor written** como o método o
escreveu, **Found m/z** como foi medido de volta, **Δ ppm** entre os dois e
**Height**, o que havia na janela; **Adduct**, o íon que aquele precursor foi
lido como sendo; **Ions found** dentre os previstos; **Margin**, a fração
deste composto menos a do seu impostor mais próximo, com a lista inteira de
rivais na dica; depois o melhor registro da sua própria biblioteca —
**Library record**, **Score**, **Reverse**, **Matched** e **Record Δ ppm**,
com **Record CE** contra a energia desta aquisição; **Other infusions**, o
mesmo composto pontuado nos dois sentidos; **Mass axis**, a correção ajustada
a partir da escada de precursor do próprio frasco, se ela foi aplicada, ou o
motivo de não haver nenhuma ([[mass-recalibration]]); e **File**. A tabela do
próprio relatório é mais estreita — A4 não comporta vinte e três colunas —,
então ela escreve o precursor e o registro como uma célula cada e deixa as
partes para o painel e para o CSV.

### Enquanto o Measure roda

**A janela continua viva.** A medição roda numa thread própria, de modo que a
janela redesenha, rola e responde enquanto ela trabalha — medido nas nove
infusões de ácidos biliares no ZenoTOF contando as voltas do laço de eventos
durante a corrida: **0,4 por segundo** quando rodava na própria thread da
janela, **89 por segundo** com ela movida para fora. Essa é a diferença entre
uma bola de praia girando e uma janela.

Um diálogo de progresso nomeia o arquivo que está sendo lido — *Reading
CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1 — 4 of 9 done* — e **Cancel** o
interrompe. O cancelamento é atendido **entre arquivos, nunca dentro de um**:
um arquivo sendo lido está dentro do leitor e nada aqui pode interrompê-lo,
então aquele que se espera termina e o próximo não é iniciado. O que já foi
medido **fica na tabela**, e a linha abaixo dela diz isso — *Cancelled: 4
infusion(s) measured before you stopped, kept as they stand.* Pressione
**Measure** de novo para fazer o resto; os arquivos já feitos voltam do cache.

**As linhas aparecem conforme os seus arquivos terminam**, uma de cada vez e
na ordem em que foram medidas, de modo que o primeiro resultado está na tela
em um ou dois segundos em vez de tudo chegar no fim. A ordenação fica
desligada enquanto a tabela se preenche — uma tabela que se reordena sob os
seus olhos entre um arquivo e o seguinte é mais difícil de ler — e volta com o
resumo terminado, junto com a coluna **Other infusions**, que não pode ser
preenchida antes de a última infusão de um composto terminar.

**Um arquivo que falha é uma linha dizendo isso**, não uma corrida parada.
Nove infusões em que a quarta perdeu o seu `.wiff.scan` são oito medições e um
motivo: a linha que falhou mantém o seu composto, a sua amostra e o seu canal
e carrega o erro nas células que de outro modo teriam as medições.

Os botões que leem os mesmos arquivos — *Measure*, *New standard…*,
*Quantify…* — ficam desabilitados enquanto ela roda, e os que agem sobre a
tabela só voltam se houver uma tabela sobre a qual agir.

### O cache de espectros promediados

Promediar todos os scans de uma infusão é a metade cara disto, e nada nessa
média depende da sessão: ela é uma função do arquivo, do canal, de quais scans
a pulverização manteve estável e de se *Include unstable scans* de
[[direct-infusion]] foi pedido. Então ela é anotada. **Um arquivo que não
mudou é lido uma vez**, e todo *Measure* posterior — e o *Average whole run*
do próprio Explorer, e a rota de pastas de [[command-line]] — lê a média de
volta do disco.

As entradas ficam **ao lado do projeto**, em `<projeto>.oqcache/`: as médias
pertencem àquele lote de arquivos, então são achadas onde o lote é achado e
podem ser apagadas com ele. Sem projeto aberto não há lugar que lhes pertença
e o diretório de cache do próprio sistema é usado
(`~/Library/Caches/MIL-Q` no macOS) — o diretório que o sistema
operacional tem o direito de esvaziar. Veja [[projects-and-files]].

O que é guardado é a média **crua**, antes de qualquer correção de massa: uma
correção pertence à chave da sessão e é aplicada na saída, de modo que ligar e
desligar a [[mass-recalibration]] não custa nada e não pode envenenar o que
foi guardado. Uma entrada é aposentada pela mudança do arquivo — a chave
guarda o tamanho e a data de modificação da aquisição e **os do seu
`.wiff.scan`**, que é onde os scans de fato estão — e também pelo canal, pela
faixa, pela máscara de pulverização e pela chave dos scans instáveis, de modo
que duas médias diferentes de um arquivo são duas entradas.

**File ▸ Clear cached spectra…** o esvazia e diz o que se foi. Nada se perde
que não possa ser medido de novo; o que custa é o próximo *Measure* ser um
frio. O diretório é limitado — 512 MB, cerca de cento e vinte infusões — e
acima do limite as entradas *usadas* há mais tempo saem primeiro.

Medido nas nove infusões de ácidos biliares no ZenoTOF, cada *Measure* num
processo novo:

| | *Measure* | cache |
|---|---|---|
| frio — nada em cache | 11,8 s | 9 lidos do arquivo |
| morno — as mesmas nove de novo | **1,6 – 1,7 s** | 9 do cache |
| um `.wiff.scan` tocado | 2,4 s | 8 do cache, 1 relido |
| vinte e sete infusões, frio | 32,5 s | 27 lidos do arquivo |
| vinte e sete infusões, morno | **3,5 s** | 27 do cache |

Um *Measure* morno é um sétimo de um frio, e o frio é o que o disco e o
leitor custam: o número morno se repete dentro de um décimo de segundo, o
frio se move segundos de um disco para outro. As nove médias ocupam
**39,1 MB** em disco, 4,3 MB cada — contra os 47 MB de `.wiff.scan` que
elas poupam de ler. Quando o cache passou a existir, um *Measure* morno ainda
levava 7,7 – 8,5 s, e a maior parte disso era uma linha: o detector de picos
perguntava a cada máximo candidato sobre cada pico que já tinha guardado, e
centroidar um quarto de milhão de pontos guarda sete mil. Agora pergunta aos
dois mais próximos, e cada média é centroidada e pontuada uma vez por
relatório em vez de cinco e três — os mesmos picos, conferidos até o último
dígito nestes nove arquivos. O que sobra é aritmética, e a thread é o que
impede que ela congele a janela.

Cada linha traz o composto e a amostra, o modo e a energia de colisão, quantos
scans foram promediados — *464 of 473* onde a pulverização perdeu alguns, com
a linha inteira ao pairar o cursor — o pico base, o precursor como o método o escreveu e
como foi medido de volta com o seu erro em ppm e a sua altura, os íons
encontrados dentre os previstos, o melhor registro da sua própria biblioteca
com as duas pontuações e a energia de colisão do registro contra a desta
aquisição, as outras infusões do mesmo composto com o cosseno nos dois
sentidos, e a coluna **Mass axis** — a correção ajustada a partir da escada
de precursor do próprio frasco, se ela foi aplicada, ou o motivo de não haver
nenhuma. Veja [[mass-recalibration]].

Dois desses vêm de onde o relatório de um frasco os recebe de uma pessoa:

- **a explicação.** Quando a aba [[lipid-maps]] já explicou o espectro na
  tela, é essa explicação que é usada. Caso contrário o composto é procurado
  na tabela de componentes pelo nome e explicado a partir da sua fórmula — o
  caminho da fórmula do [[annotate-from-lipid-maps]], executado sem ninguém
  na aba. Duas coisas são lidas em vez de tomadas como escritas, pelo mesmo
  motivo: uma tabela de componentes não tem coluna para nenhuma das duas. As
  **marcações**: um componente chamado `CA-d4` cuja fórmula é a não marcada
  `C24H40O5` é explicado como `C24H36D4O5`, porque o nome diz quatro e a
  aritmética estaria fora por 4,025 Da. E o **aduto**: o do próprio
  componente é usado quando concorda com o precursor escrito do canal, e
  quando não concorda, o precursor vence e a linha de base diz isso — ver
  *Adutos* em [[lipid-maps]]. Um composto que o método não tem não é
  adivinhado, e um precursor que nenhum aduto da fórmula alcança não é
  explicado de modo algum: a célula diz qual dos dois.
- **a biblioteca.** A biblioteca própria — o MSP a que *Add spectrum to
  library…* acrescenta, veja [[spectral-library]] — buscada na precisão do
  próprio precursor escrito. Um registro feito de uma destas mesmas infusões
  vai bater consigo mesmo com cada um dos seus picos encontrado, o que diz
  que o arquivo foi escrito e lido de volta e mais nada; a linha que vale ler
  é a do mesmo composto sob outra ativação.

**Uma célula que não pôde ser preenchida diz por quê em vez de ficar em
branco.** *only 84 counts survive* não é a mesma resposta que *nothing within
±0.25 Da*, e nenhuma das duas é *CA-d4 is not a component of the method* —
uma tabela de travessões não distingue as três, e qual delas é decide o que
fazer em seguida. A frase inteira por trás de uma abreviada está na dica da
célula.

Os cabeçalhos ordenam pelos números onde os têm, então o precursor mais fraco
ou a pior pontuação está a um clique.

**Report…** escreve o documento por composto — o mesmo que *Process ▸ Report
this infusion…* escreve — para as linhas selecionadas, ou para todas quando
nenhuma está selecionada, uma seção por composto. Linhas do mesmo composto
escolhidas juntas são desenhadas cabeça-cauda umas contra as outras nele; uma
linha deixada de fora fica de fora também da comparação. **A tabela inteira
recebe a capa** descrita adiante e uma seleção não, porque cada contagem
dessa capa é uma contagem da tabela inteira; a linha do [[audit-trail]] diz
qual dos dois foi escrito. **Export CSV…**
escreve a tabela inteira, todas as colunas, com ou sem seleção: um resumo com
linhas faltando não é a coisa que ele diz ser.

**Add all to library** escreve um registro por linha na sua própria
biblioteca — o MSP ao qual *Add spectrum to library…* acrescenta, veja
[[spectral-library]]. A tabela já tirou a média, centroidou e identificou
cada linha, de modo que um registro é exatamente esses números com um nome e
uma procedência: o composto que a linha propõe, o aduto e a fórmula que ela
identificou, a energia de colisão e a ativação do canal, o dia em que o
arquivo diz que foi adquirido, e um comentário nomeando a aquisição, o canal
e os scans sobre os quais a média foi tomada. Uma linha cujo composto não
pôde ser proposto é ignorada e nomeada; o mesmo vale para uma linha que já
está no arquivo com a mesma aquisição e o mesmo canal, que é a chave que
impede a mesma medição de ser escrita duas vezes — aperte de novo depois de
abrir mais duas infusões e só essas duas são acrescentadas. A linha abaixo
da tabela diz o que foi escrito e o que não foi: *7 record(s) written, 2
skipped: …*.

A linha de resumo sob a tabela é a única frase que a tabela soma — *3
compound(s) in 9 infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm; 34
of 458 predicted ion(s) found across 7; 4 with an own record above 60 in
own-bileomics.msp* — apenas contagens, cada uma com aquilo contra o que foi
contada. O relatório do lote imprime a tabela e essa linha como a sua seção
*Infusions*, enquanto a medida valer: veja [[report]].

### Medido: a aba, nos mesmos nove arquivos

Os nove abertos de uma vez — três compostos, cinco deles chamados `CA-d4` —
com as três corridas CID escritas numa biblioteca própria e as três fórmulas
na tabela de componentes. **Measure** levou **14,1 s**, 1,6 s por infusão; o
documento das nove deu 61 páginas em 18 s, a maior parte disso as vinte
figuras cabeça-cauda que cinco infusões de um composto produzem.

| | precursor encontrado | íons dentre os previstos | registro próprio |
|---|---|---|---|
| CA-d4 CID 45 eV | 430,3196, −70,7 ppm, 84 contagens | 2 de 56 | 97, o dele mesmo |
| CA-d4 EAD 22 eV | 430,3489, **+20,7 ppm** | 8 de 56 | **29** a 45 eV |
| CA-d4 EAD 12 eV | 430,3488, +20,4 ppm | 3 de 56 | **6** a 45 eV |
| DCA-d4 CID 40 eV | 414,3275, −30,1 ppm, 33 contagens | 3 de 41 | 96, o dele mesmo |
| DCA-d4 EAD 22 eV | 414,3525, +30,3 ppm | 8 de 41 | **33** a 40 eV |
| TDCA-d4 CID 30 eV | 504,3273, +14,4 ppm, 123 contagens | 5 de 104 | 100, o dele |
| TDCA-d4 EAD 22 eV | 504,3325, +24,9 ppm | 5 de 104 | **61** a 30 eV |

*3 compound(s) in 9 infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm;
34 of 458 predicted ion(s) found across 7; 4 with an own record above 60.*

Quatro coisas nessa tabela merecem ser lidas em vez de puladas:

- **as duas linhas que não estão nela.**
  `CA-d4_TOFMSMS_EAD_12CE_…_TESTEARTIGO` e a sua gêmea de 22 eV carregam o
  nome CA-d4 e não são aquisições de CA-d4: o método delas mira **839,56**
  sobre 100–1000, o pico base é 839,23, nove e dezessete contagens ficam na
  janela do precursor — cento e trinta vezes os seus pisos de ruído medidos de
  0,068 e 0,13 contagens, de modo que ambas agora são medidas, a **−43 ppm** —
  e nenhum registro da biblioteca chega a ±0,02 Da de 839,56. Esses dois
  arquivos são também onde o limite do próprio piso aparece: as regiões vazias
  deles são a ponta de massa alta de um eixo que não contém nada, então o piso
  fica em um quinze avos de contagem enquanto o fundo químico tem picos de uma
  centena, e um pico acima do piso é um pico acima do fundo e não o
  composto. A célula de explicação delas agora diz a coisa abertamente —
  *839.56 is none of the adducts of C24H36D4O5 within ±0.05 Da — closest
  [M+K]+ at 451.2758* — em vez de reportar zero íons de trinta e um, o que
  era verdade e deixava o leitor descobrir por quê. O *across 7* na linha
  acima são essas duas linhas: uma infusão para a qual nada foi explicado não
  é contada como uma que não achou nada. Elas pontuam **73** uma
  contra a outra e **5 a 10** contra os três arquivos de CA-d4 de verdade. O
  prefixo do nome dizia um composto e o método dizia outro, e a linha é onde
  isso aparece — que é toda a razão de o composto nunca ser mais do que uma
  proposta. A coluna *Isolated* agora diz isso antes de qualquer coisa ser
  medida, e o que os dois arquivos de fato são está na seção *Quando o nome e
  o método discordam*, abaixo.
- **o precursor sobrevive às ativações suaves, e o que sobra dele sob as duras
  não é o precursor.** Toda corrida EAD de um composto mediu o seu precursor,
  de +20,4 a +30,3 ppm. As três corridas CID também têm algo na janela — 84,
  33 e 123 contagens — e contra um piso fixo de cem as duas primeiras eram
  recusadas como *pouco demais para medir*. Contra o piso que a aquisição de
  fato tem, 1,43 e 0,75 contagens, elas são 59 e 45 vezes o fundo e estão
  claramente ali; então são medidas, e saem em **−70,7 e −30,1 ppm**, ou seja
  a 0,030 e 0,012 Da da massa escrita. A altura diz que há um pico e o ppm diz
  que ele não é o precursor, e a frase nessas linhas agora diz **"Precursor
  found but not confirmed at −70,7 ppm, past the 25 ppm that says the same
  ion"** — *confirmado* é uma afirmação sobre identidade e a linha de resumo
  sempre a reservou para 25 ppm, então a frase teve de parar onde a contagem
  para. Medir quatro precursores a mais desse jeito portanto não acrescentou
  **nenhum** aos quatro dentro de 25 ppm: a contagem da linha de resumo não
  mudou, e o que mudou é que a página agora diz o que há na janela em vez de
  se recusar a olhar.
- **os erros confirmados têm todos o mesmo sinal**, de +14,4 a +24,9 ppm — e
  os dois que o piso medido passou a deixar entrar nesta tabela têm o outro,
  −30,1 e −70,7 (e as duas linhas que não estão nela, −43), o que é uma
  segunda razão para lê-los como algo na janela e não como o precursor. Um dos positivos, o DCA-d4 a +30,3, passa dos 25 ppm que a
  linha conta e está na página do mesmo jeito: a contagem é uma frase, não um
  veredito.
- **uma fórmula acha de dois a oito íons, e quais depende da ativação.** Uma
  fórmula oferece o precursor, a forma que os seus fragmentos carregam e as
  perdas neutras dela, e mais nada; o resto destes espectros são clivagens de
  anel. É para isso que serve o denominador. Nas sete aquisições reais:
  **34 de 458** íons previstos encontrados, 2 de 56 no CA-d4 sob CID contra 8
  de 56 sob EAD a 22 eV, 3 de 41 e 8 de 41 no DCA-d4, 5 de 104 dos dois lados
  no TDCA-d4 — as ativações suaves guardam a escada e as duras já a
  terminaram. A linha com que comparar é a da aba [[lipid-maps]], onde o
  mesmo composto como *desenho* é pontuado contra milhares de massas em vez
  de dezenas.

A coluna da biblioteca é a que diz algo que o resto não diz. Um registro feito
de uma corrida bate com essa corrida com **cada um dos seus picos encontrado**
— *179 of its 179 peak(s) matched*, uma pontuação reversa de 100 — o que prova
que o arquivo foi escrito e lido de volta. A pontuação *direta* é 97, 96 e 100
nas três, e não 100 em todas: o registro é escrito a um por cento do pico base
e a busca lê cada centroide, então a consulta tem picos que o registro nunca
recebeu. [[integration]] traz as três contagens de picos e por que nenhum dos
lados está errado. Os números que significam alguma coisa aqui são 6, 29, 33
e 61 — o mesmo composto, o mesmo frasco, sob outra ativação, e um registro não
viaja entre elas.

## Quando o nome e o método discordam

Um `.wiff` escrito por uma aquisição manual chama a própria amostra de
`sample` e o próprio método de `Untitled 1.msm`. Lido por reflexão, o seu
experimento oferece uma polaridade, uma faixa de massas, uma massa fixa, DP,
CE, DPS e CES — e um `TargetedCompoundInfo` vazio, que é o campo onde o SCIEX
OS escreve o nome de um composto quando o método tem um. **Nas nove infusões
reais nada no arquivo diz o que foi borrifado.** O composto está no nome do
arquivo e em nenhum outro lugar.

Então o nome é uma proposta, e o precursor que o método isola é a única
medida da mesma pergunta que o arquivo de fato carrega. O MIL-Q compara
os dois. O composto com que o nome começa é resolvido a uma fórmula — a
tabela de padrões de ácidos biliares e seus conjugados, depois o LIPID MAPS,
depois a taquigrafia de lipídios, as mesmas três que o [[lipid-maps]] usa,
com um `-d4` final lido como quatro marcações que a fórmula não carrega — e
cada aduto dessa fórmula é medido contra o precursor escrito, na precisão com
que o precursor foi digitado. Onde o nome fecha, a coluna **Isolated** da aba
Infusions e o cabeçalho do relatório leem *430.35 = [M+NH4]+ of CA-d4*. Onde
não fecha, o mesmo precursor é oferecido à tabela de componentes e à sua
própria biblioteca, e a resposta é uma de duas frases:

> The file is named CA-d4 but the method isolates 839.56 over 100–1000,
> which is no adduct of C24H36D4O5 within ±0.05 Da; it fits nothing in the
> component table or the library.

> …it fits DCA-d4 [M+NH4]+ (414.3516, +2.0 ppm) from the component table.

A célula **Compound** da linha então para de repetir o nome: lê *not CA-d4*,
ou *DCA-d4, not CA-d4* onde algo fecha, com a frase inteira na dica. O
agrupamento não muda — dois arquivos nomeados pelo mesmo composto valem ser
pontuados um contra o outro seja qual for o que os seus métodos isolam, e o
par abaixo só é visível *como* par porque continuaram a ser.

A mesma verificação roda quando um arquivo é aberto, e avisa uma vez por
arquivo, ao lado do aviso para um `.wiff` sem o seu `.wiff.scan`. **Não lê
espectro nenhum**, então chega antes de qualquer coisa ter sido medida: nas
nove infusões reais leva **32 ms por arquivo**, quase tudo procurando o nome
no LIPID MAPS, contra os segundos que o próprio arquivo leva para abrir. A
tabela de componentes não custa nada mensurável em cima disso — 125 fórmulas
por todos os adutos deram os mesmos 32 ms.

**Um nome só é aceito quando é o composto exatamente.** O LIPID MAPS é
buscado por subcadeia, o que está certo para alguém digitando numa caixa e
errado para uma verificação que dispara sozinha: contra a base instalada,
`PC` responde *PCTR3*, `CE` responde *cedrol*, `Cer` responde *Cerasin* e
`TESTOL` responde *testolactone*. Quatro nomes de amostra do tipo mais
comum, cada um resolvido a um composto que ninguém estava infundindo, e cada
um teria então contradito o que quer que o seu método isolasse. Então um nome
de base de dados só conta quando o nome, a abreviação ou o LM_ID do próprio
registro *é* o nome; a tabela de padrões é uma busca exata e a taquigrafia é
analisada em vez de buscada. Um nome que nada reconhece é reportado como *not
checked* — que é um achado diferente de *o nome está errado*, e os dois nunca
são confundidos.

### O que são os dois arquivos `TESTEARTIGO`

São as aquisições para as quais esta verificação foi escrita, e não são ácido
cólico-d4.

| | os dois `_TESTEARTIGO` | `CA-d4_TOFMSMS_EAD_12CE_…_mix1` |
|---|---|---|
| precursor isolado | **839,56** | 430,34 |
| faixa de massas | 100 – 1000 | 50 – 500 |
| potencial de declusterização | 80 e 44 | 44 |
| pico base | 839,2316 / 839,2343 | 430,3490 |
| altura do pico base | **109 / 234 contagens** | **12.271 contagens** |
| centroides no espectro promediado | 7.101 / 5.281 | 234 |
| corrente iônica total da média | 18.537 / 40.453 | 156.716 |

Milhares de centroides de dezenas de contagens cada é a cara de uma aquisição
vazia: um espectro de ruído, centroidado. A infusão real ao lado tem 234
centroides e um deles é cinquenta vezes mais alto do que tudo o que há nos
outros dois arquivos somado.

**Nada em lugar nenhum fecha com 839,56 e nada no arquivo sustenta o que
fecha.** Todo aduto positivo dos ácidos cólico, desoxicólico e
taurodesoxicólico, dos seus conjugados de glicina e taurina, marcados e não
marcados, como monômero e como dímero — setenta e duas massas — dá
exatamente um acerto a ±0,05 Da: **[2M+Na]+ do ácido cólico *não marcado*,
839,5644, −5,2 ppm**. O LIPID MAPS a ±0,01 Da acrescenta dezessete registros
sobre duas fórmulas, `C43H83O13P` como `[M+H]+` e `C45H76NO10P` como
`[M+NH4]+` — fosfatidilinositóis e fosfatidilserinas, que ninguém estava
infundindo. E o próprio arquivo recusa todos eles: dentro de ±0,05 Da de
839,56 o centroide mais alto tem **9 contagens** num arquivo e **17** no
outro, 8% e 7% de um pico base que já é 109 e 234. O único íon na janela de
isolamento que está realmente lá fica em 839,23, um terço de dalton — uns
quatrocentos partes por milhão — abaixo do que o método pediu, então é um
vizinho que a janela de ±0,5 Da apanhou e não o alvo.

A conclusão que a aba tira é a que a aritmética sustenta: **o método isolou
uma massa digitada para outra coisa, e não pegou nada.** Os dois pontuam 73
um contra o outro — dois espectros de ruído da mesma fonte, tomados com dois
minutos de diferença — e 5 a 10 contra os três arquivos de CA-d4 de verdade.
O nome do arquivo é a única coisa em qualquer um dos dois que diz CA-d4, e
está errado.

Uma discordância menor do mesmo tipo, visível na tabela acima: o arquivo de
12 eV se chama `…_44DP_…` e o seu método carrega um potencial de
declusterização de **80**. O nome é uma nota que alguém digitou, nos dois
casos, e o método é o que o instrumento fez.

## Uma pasta de uma vez

**File ▸ Report infusions in a folder…** faz a mesma pergunta a uma pasta que
saiu do instrumento hoje de manhã, sem nada aberto no [[explorer]] e sem lote
na tela. Aponte para a pasta, diga para onde vai o documento e — se os tiver —
um MSP seu e uma tabela de componentes, seja um projeto ou um CSV de
componentes; ele escreve o mesmo documento por composto, e a mesma
tabela-resumo como CSV se isso estiver marcado.

Nada é acrescentado ao que está aberto. Cada arquivo é aberto em uma sessão
própria, medido, e fechado de novo antes de o próximo ser aberto, de modo que
uma pasta de trinta infusões nunca mantém trinta leitores; e um projeto já
aberto fica exatamente como estava, com uma linha em seu [[audit-trail]]
dizendo que uma pasta foi relatada. Sem projeto aberto não há trilha em que
escrever, e nenhuma é criada.

A pasta é examinada por [[checking-files]] antes de qualquer abertura. Um
`.wiff` cujo `.wiff.scan` não está ao lado é **excluído**, porque seus
espectros não podem ser lidos e o relatório é um espectro; um `.wiff2` é
relatado como ignorado; uma corrida que não lê como [[direct-infusion]] fica
de fora com os números de planura que dizem por quê. Cada exclusão é listada
com o seu motivo: uma pasta de nove relatada como oito só é honesta se a outra
voltar com a razão.

A mesma execução está na linha de comando, para uma pasta que chega toda
semana — veja [[command-line]]:

```
MIL-Q --infusion-report ~/dados/acidos --out ~/relatorios/acidos.pdf \
          --library ~/biblioteca/own-bileomics.msp --csv ~/relatorios/acidos.csv
```

### Medido: a pasta, nos mesmos nove arquivos

A pasta inteira pela linha de comando, com as três corridas CID como
biblioteca própria e as três fórmulas como CSV de componentes: **9 arquivos
lidos, nada excluído, um PDF de 58 páginas** — duas de capa e 56 de seções —
em **31 s**, com 1,2 GB de pico de memória; `--per-compound` dá quatro
documentos, a capa e um por composto, as mesmas 58 páginas. Escritas sem
capa, as mesmas nove seções dão 56, de modo que a capa custa exatamente as
duas que ela é. Os segundos são o único número aqui que não é do programa —
a mesma execução já levou de 27 s numa máquina ociosa a 255 s numa ocupada.
O que é estável é o que ela fez.
Cada linha é
a que a aba Infusions mediu com os nove arquivos abertos — 2 de 56 íons sob
CID e 8 de 56 sob EAD para o CA-d4, 29 e 6 e 61 contra os registros próprios,
+14,4 a +30,3 ppm onde o precursor sobreviveu — que é justamente o ponto: o
caminho da pasta e o caminho do lote aberto são a mesma medida, e concordam
dígito por dígito.

As duas aquisições `_TESTEARTIGO` **não** são excluídas, e essa é a resposta à
pergunta óbvia sobre elas. Elas leem como infusões, porque são: 294 e 311
scans de um spray estável. O que há de errado com elas não é visível no
cromatograma — seu método isola 839,56, seu pico base é 839,23, nove e
dezessete contagens estão na janela do precursor, e sua célula de explicação
diz *839.56 is none of the adducts of C24H36D4O5 within ±0.05 Da — closest
[M+K]+ at 451.2758*. Uma regra que as descartasse teria de saber disso de
antemão; o relatório é onde isso se descobre.

## A capa de um relatório de pasta

Um relatório de pasta abre na pasta, e não no seu primeiro composto. Diante
das páginas por composto, no mesmo PDF, há uma capa de cinco blocos — e ela
está no mesmo PDF porque uma capa em arquivo próprio é um arquivo que se
separa daquilo que apresenta.

**O que isto é.** A pasta, o dia, a versão que escreveu, quantos arquivos
foram lidos e quantos ficaram de fora, quantas infusões em quantos compostos,
a biblioteca própria quando alguma foi pesquisada, e a linha-resumo que a aba
Infusions mostra, dígito por dígito. Um documento é lido de volta uma semana
depois, separado de tudo o que o produziu.

**As infusões.** Cada infusão em uma linha, nas colunas que a aba e a seção
*Infusions* do [[report]] do lote usam — uma definição só, para que as três
não possam discordar — com as aquisições de um composto juntas mesmo quando a
pasta saiu do instrumento com elas intercaladas. Uma célula que não pôde ser
preenchida continua dizendo por quê em vez de ficar em branco, cortada numa
palavra quando a razão é uma frase inteira; ela está por extenso na página do
próprio composto, que é para onde o sumário aponta.

**No que elas dão.** A tabela acima somada, uma frase por coluna que pode ser
somada, cada uma delas uma contagem e aquilo contra o que foi contada. Não há
uma frase final que as reúna nem aprovação ou reprovação da pasta, pela mesma
razão que não há para um composto: o que um espectro vale depende do que o
frasco deveria conter.

**O que ficou de fora.** Os arquivos excluídos com as suas razões, impressos
haja ou não algum — *nada ficou de fora* também é uma medida — e depois o que
[[checking-files]] achou nos nomes da própria pasta antes de qualquer
abertura.

**As páginas que vêm a seguir.** Cada seção com a página em que caiu. O
título carrega a amostra além do composto, porque uma pasta é onde um
composto é infundido cinco vezes e um sumário de cinco linhas idênticas manda
o leitor à página 3 para descobrir se a página 3 é a que ele queria. Os
números são as páginas em que as seções realmente caíram: o documento é
paginado uma vez para descobri-los e outra para imprimi-los, que é a
maquinaria que o [[report]] já usa.

Com `--per-compound` a capa é escrita como arquivo próprio, chamado
`-cover`, já que as páginas que ela apresenta estão nos outros; ali ela não
lista número de página nenhum, porque não os tem.

### Medido, nos nove

O parágrafo que as nove infusões reais produzem, por inteiro:

> 4 of 9 precursor(s) confirmed within 25 ppm; 5 not: 2 whose method isolates
> 839.56, 3 at -70.7 and -30.1 and +30.3 ppm. Own records: 4 above 60, 3
> below — all across a collision-energy change; 2 matched no record at all. Predicted ions: 34 of 458 found across 7
> spectrum(s); 2 had nothing to predict from — no formula in the component
> table for that compound.

Cada número dele está na página acima dele, e três valem a leitura. As **2
whose method isolates 839.56** são as aquisições `_TESTEARTIGO`: uma massa
que nenhuma outra corrida de CA-d4 da pasta isola, de modo que elas não são
duas falhas de um íon e sim duas medidas de outro, e a frase diz isso com a
massa em vez de chamá-las de não medidas. As **4 above 60** são os três
registros comparados com as corridas de que foram feitos, mais um; é por isso
que a frase as conta em vez de concluir a partir delas. E **2 had nothing to
predict from** é o denominador mantido honesto: uma infusão para a qual nada
foi previsto não é contada como uma que não achou nada.

A capa deu **duas páginas** das 58 da pasta — a tabela de nove linhas ocupa a
primeira e um pouco da segunda — e leva **0,2 s** sozinha: ela é escrita a
partir das linhas que a execução já fez, e não lê arquivo nenhum.

## Da infusão para o método

Um frasco verificado só vale alguma coisa se o que se aprendeu sobre ele
chegar ao método. **Use in method…**, na aba Infusions, escreve as linhas
selecionadas — todas, quando nenhuma está selecionada — na tabela de
componentes do [[method-workspace]], um componente por infusão, e diz de
onde veio cada coisa.

O que o componente recebe:

| Campo | De onde |
|---|---|
| Name | o composto com que o nome do arquivo começa — o mesmo prefixo pelo qual a tabela agrupa |
| Formula | aquilo com que a infusão foi de fato explicada, carregando os deutérios que o nome declara: `CA-d4` é `C24H36D4O5`, não `C24H40O5` |
| Adduct | lido do precursor escrito no próprio canal, com a polaridade como filtro — veja [[lipid-maps]] sobre por que um aduto não é um deslocamento |
| Precursor | a massa **exata** desse aduto e dessa fórmula |
| Fragment | o pico base do espectro de produtos médio, ou um pico que você escolhe entre os mais altos |
| IS | marcado, a não ser que você desmarque na linha |
| Group | `standards` |
| RT | **nada.** Uma infusão não é uma separação e não tem tempo de retenção para dar |
| Provenance | a amostra, o canal, a energia de colisão, o arquivo, a hora de aquisição e o registro da sua própria biblioteca com que o espectro bateu |

O precursor é o ponto em que é preciso ter cuidado. O canal diz `430.35` e o
componente recebe `430.3465`, e as duas coisas são afirmações diferentes. O
valor escrito é o que o instrumento recebeu: foi ele que escolheu o canal, a
aquisição está sobre ele, e ele só é bom até as casas decimais que alguém
digitou — ±0,005 aqui, o que dá 12 ppm. A massa exata é quanto o composto
pesa como aquele aduto, e é dela que uma janela de massa, uma massa de
travamento ([[mass-recalibration]]) e uma verificação de exatidão de massa
têm de ser feitas. Escrever a arredondada no método colocaria 12 ppm de erro
nas três de propósito. Então o que é escrito é a massa exata e **as duas são
mostradas** — na coluna Note do diálogo, na dica de tela e na
[[audit-trail]] — porque nada deve substituir em silêncio um número que você
já não pode ver.

Nada digitado é sobrescrito. Um composto que o método já carrega é
*completado*: só as células vazias são preenchidas, e onde um valor que já
está lá discorda da infusão, a Note diz isso e o valor digitado fica —
`Precursor 430.3500 written, 430.3465 from the infusion — kept as written`.
Cada linha marcada é uma entrada na [[audit-trail]] sob *Component from
infusion*, com a procedência na nota.

Esse caminho parte de uma tabela que já foi medida. O caminho inverso — um
frasco na mão, nada medido ainda, e nenhum componente, registro ou histórico
para ele — é o [[new-standard]], que pede o nome, o lote e o arquivo e
escreve os três de uma vez.

Duas coisas que o diálogo recusa fazer, ambas dignas de nota:

- **um precursor em que nenhum aduto encaixa não é escrito.** A linha diz o
  porquê no lugar: *839.56 is none of the adducts of C24H36D4O5 within
  ±0.05 Da — closest [M+K]+ at 451.2758*. Um componente com uma massa
  inventada é pior do que nenhum componente.
- **uma segunda infusão do mesmo composto não tem mais o que escrever.** Duas
  energias de colisão de um frasco são um componente, e a primeira delas
  preenche as células que a segunda preencheria. A linha de estado diz quais
  compostos foram esses, em vez de acrescentar uma segunda linha com o mesmo
  nome.

### Medido, nas nove infusões de ácidos biliares

As mesmas nove aquisições no ZenoTOF do resto desta página, com as três
corridas em CID escritas antes numa biblioteca própria, para que toda linha
tivesse um registro a nomear.

| Composto | Fórmula | Aduto | Escrito | Exato | Δ |
|---|---|---|---|---|---|
| CA-d4 | C24H36D4O5 | [M+NH4]+ | 430,35 (CID), 430,34 (EAD) | 430,3465 | +8,1 e −15,1 ppm |
| DCA-d4 | C24H36D4O4 | [M+NH4]+ | 414,34 | 414,3516 | −28,0 ppm |
| TDCA-d4 | C26H41D4NO6S | [M+H]+ | 504,32 | 504,3291 | −18,1 ppm |

Toda fórmula veio da tabela de padrões através do nome, com os quatro rótulos
que o `-d4` declara colocados — sem eles nada pesa 430 e nenhum aduto encaixa.
Dois dos três adutos são amônio e o terceiro não é, que é exatamente o tipo
de coisa que não se pode supor.

Os fragmentos são os picos base, e não são o mesmo pico em toda energia: o
CA-d4 dá **359,2870** em CID 45 eV e **377,3015** em EAD 22 eV; o TDCA-d4 dá
**468,3072** em CID 30 eV. Em EAD 12 eV o pico mais alto do CA-d4 é
**430,3488** — o precursor que sobreviveu — e a linha diz isso: *the base peak
is the precursor that survived, not a fragment*. É uma transição legítima e
ruim, e a caixa de fragmento é onde se escolhe outro.

**Sete das nove foram oferecidas.** As duas aquisições `_TESTEARTIGO` foram
recusadas, e pelo motivo que esta página já dá: elas se chamam CA-d4 e miram
839,56, que não é nenhum dos adutos daquela fórmula. Marcar as sete escreveu
**três** componentes, um por composto, porque a segunda e a terceira infusão
de cada composto não tinham mais nada a preencher.

Depois, *Check method* sobre esses três: **um achado** — `3 of 3 components
have no retention time`, que é a resposta esperada e correta para padrões que
só foram infundidos, e o motivo para passar um deles pela coluna em seguida.
A verificação do scan de varredura foi pulada, já que estas aquisições não têm
varredura nenhuma. Escrito do outro jeito — as sete infusões como sete linhas
separadas, o que isto se recusa a fazer — o `check_method` ainda chamou as
duas linhas de DCA-d4 de transição compartilhada: as duas são 414,3516 →
361,30 dentro da tolerância, uma a 22 eV e outra a 40, e nada além de um tempo
de retenção poderia distingui-las.

## Qual energia manter

Uma bandeja costuma ser o mesmo frasco borrifado em várias energias de
colisão e, onde o instrumento tem as duas, sob mais de uma ativação. O
**Recommend energies…** agrupa estas linhas por composto, ativação e energia
e diz qual condição usar para identificação, qual para quantificação e qual
para um registro de biblioteca — três perguntas diferentes, cada uma com os
números em que foi decidida, e nunca uma energia que não foi adquirida. Veja
a [[collision-energy]].

## De uma verificação para uma medida

Este relatório pergunta se um frasco é o que o rótulo diz. O **Quantify…** na
mesma aba faz outra pergunta — quanto há de um composto contra outro no mesmo
spray — e a responde com as duas respostas, a interferência isotópica entre
elas e a razão. Veja a [[infusion-quantitation]].

## O mesmo padrão, no mês que vem

Este relatório é uma verificação. O registro que ele nomeia é escrito na sua
própria biblioteca, e o [[standard-history]] lê os registros acumulados de
um composto como uma carta de controle: o cosseno contra o primeiro
registro, o pico base em ppm a partir dele, e a altura do pico base, ao
longo dos dias em que foram adquiridos.

A bandeja inteira é a outra metade dessa pergunta, e o
[[compare-infusions]] é onde ela é feita: esta tabela contra a que um
projeto de referência salvou, correspondida por composto e por condições.
Pressione **Measure** antes de salvar um projeto e o projeto guarda estes
números e a lista de picos média de cada linha, que é contra o que um dia
posterior é comparado.

## A pasta inteira a partir de um script

`api.infusion_report(folder, "infusions.pdf")` escreve este documento para
cada infusão de um arquivo ou de uma pasta sem abrir a aplicação, e devolve
uma linha por seção para que os números possam ser lidos sem abrir o PDF —
veja a [[python-api]].

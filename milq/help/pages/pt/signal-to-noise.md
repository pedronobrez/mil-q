---
title: Sinal/ruído
---
O sinal/ruído aparece em quatro lugares — o portão do detector, os
[[acceptance-criteria]], as cartas de [[batch-qc]] e a [[results-table]] — e em
todos eles é a altura do pico dividida por uma medida do ruído. O que é o
ruído, e quando ele não pode ser medido, é o assunto inteiro desta página.

## Onde o ruído é medido

**Sobre o cromatograma inteiro**, quando nenhuma região de ruído está
definida. Ele deliberadamente *não* é medido dentro da janela de tempo de
retenção: aquele trecho é quase todo pico, de modo que a sua dispersão de
ponto a ponto reporta a própria inclinação do pico. Em dados reais isso leu
16,944 onde o ruído verdadeiro do traço era 505, e o mesmo pico saiu em S/N 19
automaticamente contra 531 à mão.

**Sobre uma região de ruído**, quando há uma definida a partir da grade de
[[peak-review]]: clique com o botão direito em um painel com um trecho de linha
de base sombreado e escolha *Set noise region from the shaded range*. **Noise
as** no painel Integration escolhe a medida: *peak-to-peak* toma a excursão
completa da região e é a leitura mais estrita e conservadora; *standard
deviation* é a mais branda. Ambas estão em uso em laboratórios, de modo que de
qual delas veio um número tem de ser declarado ao lado dele, e o painel o faz.

## Como funciona a estimativa automática

O ruído é o desvio absoluto mediano das diferenças de ponto a ponto, escalado
para um desvio padrão — um estimador robusto que um pico não consegue inflar.
Em um XIC de baixa contagem, mais da metade das diferenças é exatamente zero, o
que zera a mediana; o recurso alternativo é o desvio padrão da metade inferior
dos pontos, que raramente contém um pico.

## Quando não pode ser medido

**A estimativa fica "não medida" quando não há nada a medir**, e esse é o caso
ordinário em uma aquisição agendada, não a exceção. Ao longo de 846 traços
reais, o traço mediano tinha três pontos não nulos em sessenta e um, e apenas
9% tinham uma linha de base que variasse de algum modo. Um traço que o
instrumento reporta como zeros exatos tem uma linha de base abaixo do seu
limiar de reporte; não há ruído ali para medir, e um número inventado para isso
não seria razão com coisa alguma.

Assim, o sinal/ruído de uma linha fica vazio, mostrado como `—`, quando a linha
de base não pôde ser medida. No lote em que isso foi medido, ele pôde sê-lo
para 23% dos picos encontrados.

## O que os portões fazem sem ele

O detector ainda precisa de um piso para rejeitar os menores picos, de modo que
onde o ruído não pode ser medido ele usa uma contagem como ruído. Isso mantém o
portão — um pico de uma única contagem em um traço de outro modo nulo continua
rejeitado — mas significa que **Min. S/N** passa a ser um limiar de intensidade
absoluta vestindo um nome de sinal/ruído: um pico de 30 contagens em um traço
de zeros passa por S/N 3 com "S/N 30". Medido em um lote real, um padrão
interno de 30 contagens e outro de 42,400 contagens teriam reportado S/N 30 e
42,400 sob essa regra. O portão é mantido; o número sobre o qual ele rejeita
não é reportado como uma razão.

O mesmo vale para o S/N mínimo dos critérios de aceitação e para o limiar de
quantificável das cartas de QC: ambos ficam condicionados à altura absoluta com
uma constante arbitrária quando a linha de base é zero. O que essa questão de
fato exige é um piso sobre a resposta absoluta do padrão interno, e um lote do
tipo em que isto foi desenvolvido não fornece um — a precisão dele não acompanha
a sua resposta. Por isso o método o declara: **Min. response** no padrão, lido
pelas cartas, pela aceitação e pela verificação do método. Ver
[[internal-standards-and-qualifiers]] e [[batch-qc]].

## O piso de ruído de uma infusão

Tudo acima trata de um cromatograma. Uma [[direct-infusion]] não tem nenhum: o
que se olha é a média de todos os scans da corrida, e *ruído* ali quer
dizer a altura abaixo da qual um pico dessa média é fundo e não medida. Esse
piso era de cem contagens, fixo, porque foi escrito para um único scan de
survey de um TripleTOF. Uma média de quatrocentos scans de um ZenoTOF não
é aquele scan, e nas nove infusões de ácidos biliares em mãos o **pico
base do espectro promediado inteiro é de 109 contagens em uma delas** — ou
seja, o piso fixo era quase o topo do espectro.

Agora ele é medido da própria aquisição, de duas maneiras, e as duas são
impressas.

**(a) As regiões vazias do eixo de massa da média.** Todo centroide igual ou
acima de um décimo de por cento do pico base é encontrado e meio dalton de cada
lado dele é deixado de fora; o que sobra fica entre os agrupamentos isotópicos
e longe de todo pico. A mediana, o desvio absoluto mediano e o percentil 99 dos
pontos medidos ali descrevem o fundo, e o percentil 99 dos *máximos locais*
entre eles é a altura que um **pico** de ruído alcança. É desse último número
que o piso é tirado, porque o que o piso barra é o ponto mais alto de uma
janela e não um ponto sorteado ao acaso: um percentil de pontos isolados
deixaria passar quase todo o fundo. Pontos exatamente iguais a zero ficam de
fora, de modo que um arquivo cujos zeros suprimidos foram restaurados e outro
cujos zeros não foram dão a mesma resposta.

**(b) A dispersão entre scans de uma janela silenciosa.** A janela de meio
dalton mais silenciosa que não contém pico algum — meio dalton porque é o que a
busca do precursor alcança de cada lado de um alvo — é extraída ao longo da
corrida inteira, a mesma janela em cada scan, e toma-se o desvio padrão da
sua intensidade somada entre scans. Promediar n scans divide o ruído
pela raiz de n, então esse desvio padrão é dividido por ela, e os dois números
são reportados: o que um scan faz e o que a promediação comprou.

O piso é o maior dos dois. Onde nenhum dos dois pode ser medido, as cem
contagens fixas ficam de pé e o registro diz isso; onde a medida sai **abaixo**
das cem fixas — que é toda aquisição medida até aqui — a medida é usada e o
relatório também diz isso, porque uma constante maior do que o espectro que ela
barra não é margem de segurança.

### O que ele mede

Nove infusões de íons produto de padrões de ácidos biliares num ZenoTOF 7600,
modo positivo, sem varredura de survey, de 146 a 473 scans cada,
promediadas inteiras:

| | |
|---|---|
| pico base da média | 109 – 12.271 contagens |
| (a), as regiões vazias | 0,068 – 3,53 contagens |
| (b), a dispersão, escalada para a média | 0,026 – 0,36 contagens |
| o piso adotado | **0,068 – 3,53 contagens**, (a) em nove de nove |
| quanto um scan dispersava, antes da média | 0,45 – 5,05 contagens |
| o piso fixo que ele substitui | 100 contagens |

A promediação é onde as duas estimativas se separam. Em
`CA-d4_TOFMSMS_Mix1`, 473 scans, a janela de meio dalton de um scan
se move em 5,05 contagens e a média de 473 delas em 5,05 / √473 = 0,23; as
regiões vazias dessa mesma média alcançam 0,96. A estimativa (a) só enxerga o
que sobrou depois da promediação, e a (b) lê a promediação em si — que é por
que as duas ficam no registro e a maior é adotada.

Doze aquisições cromatográficas como contraste, em outro instrumento e num
gradiente real: um TripleTOF 5600, o canal de íons produto mais forte de cada
uma promediado sobre os limites do seu próprio pico maior. Onze das doze são
medidas, com (a) de 0,69 a 20,1 contagens contra (b) de 0,23 a 3,25 — (a) o
maior em onze de onze, como era nas infusões. A mais alta delas promedia as
treze scans de um pico de 567.000 contagens e sai em **20,1 contagens**:
trezentas vezes o piso da infusão mais silenciosa, pela razão simples de que
uma média de treze scans não é uma média de quatrocentos. As cem fixas
ainda eram cinco vezes rigorosas demais ali.

A décima segunda é onde o recurso de reserva aparece, num arquivo real e não
num teste. O canal de íons produto mais forte dela tem um pico de 352 contagens
sobre três scans; a média desses três tem 167 pontos medidos em 412 e
nenhuma região vazia larga o bastante para medir, então nenhuma das duas
estimativas pode ser feita e **as cem contagens fixas ficam de pé**, com o
motivo impresso ao lado. Uma aquisição silenciosa e uma aquisição que não
contém nada não são a mesma coisa, e só uma das duas ganha uma medida.

### Onde o piso se aplica

- o precursor lido de um espectro promediado de íons produto, no
  [[infusion-report]] e no [[accurate-precursor]] — uma janela que contém menos
  que o piso é reportada como pouco demais para medir, com a altura que foi
  encontrada;
- a lista de **picos não explicados** do relatório: um pico abaixo do piso é
  fundo, e não algo que a explicação deixou de dar conta;
- um registro escrito na sua própria biblioteca a partir de uma infusão, que
  passa a obedecer ao piso além do seu um por cento do pico base — ver
  [[spectral-library]];
- o piso de rótulos do painel de uma infusão, que começa no maior entre os 2% do
  desenho e o piso de ruído, com a linha de status dizendo qual dos dois foi.

O piso é medido sobre **a mesma média que quem pergunta está olhando**, e é
por isso que dois deles podem divergir num mesmo arquivo. O painel do Explorer
promedia a corrida inteira; o [[infusion-report]] promedia o trecho estável do
spray (*Scans que a pulverização perdeu*, em [[direct-infusion]]), então as
scans que um spray instável contribuiu ficam fora da média dele e também
fora do piso dele. Nas nove
infusões os pisos da corrida inteira vão de 0,068 a 3,53 contagens e os do
relatório de 0,068 a 4,27 — iguais nas seis corridas que a máscara não mexeu,
e maiores nas três que ela aparou, porque jogar scans fora é jogar fora
parte da promediação. Isso é a resposta estar certa e não os números
discordarem: um piso que descrevesse um espectro diferente do que foi impresso
seria o piso errado.

### O que ele não diz

O piso é um número só para um espectro inteiro, e um fundo não é o mesmo em
toda massa: nas duas aquisições das nove que não contêm nada, as regiões vazias
são a ponta de massa alta onde o detector não viu nada, então o piso sai em
0,07 e 0,13 contagens e os picos do fundo químico — uma centena de contagens
dele — ficam muito acima. **Um pico acima do piso é um pico acima do fundo, não
o composto.** O que diz se ele é o composto é a sua massa: nesses dois arquivos
o íon na janela do precursor supera o piso em duas ordens de grandeza e fica a
43 ppm do precursor escrito, e são as partes por milhão que respondem à
pergunta.

## Aceitação

Um critério de aceitação sobre S/N que não pode ser avaliado marca a linha com
**S/N not measured** em vez de aprová-la em silêncio: um critério que não pôde
ser verificado não é um critério que passou, e não dizer nada permitiria que
fosse lido como tal.

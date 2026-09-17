---
title: Cromatogramas e espectros
---
## O painel do cromatograma

Cada canal marcado é um traço. O nó *Sample TIC* desenha o cromatograma de íons
totais (TIC) da corrida, que é somado **por ciclo, não por tempo**: os
experimentos de um ciclo são medidos um após o outro, de modo que a união de
seus tempos é um ponto por espectro — 23,722 onde o instrumento reporta 577 — e
o programa reporta os 577 do instrumento. Um canal desenhado como **TIC** é a
soma de cada um de seus scans; como **BPC**, o pico mais alto de cada scan.

| Gesto | Efeito |
|---|---|
| clique simples | espectro do scan sob o cursor |
| arrastar | zoom por faixa elástica |
| duplo clique | ajustar o traço |
| Shift + arrastar, ou arrastar com *Select range* ligado | selecionar um intervalo: o painel de espectro mostra a média sobre ele, ao vivo, enquanto a seleção é arrastada ou redimensionada, e a barra de status relata a integração do intervalo — área, altura, ápice e S/N |
| ← → | scan anterior e seguinte |
| clique com o botão direito | o menu do gráfico: exportar como imagem, eixos, grade |

**Stack** dá a cada traço um painel próprio, com os eixos de tempo travados, de
modo que um zoom em um é um zoom em todos. **Overview** acrescenta um navegador
ao longo da base: a faixa completa, com o zoom atual desenhado como uma janela
que pode ser arrastada. **Mirror** desenha um traço a cada dois para baixo, que
é como uma amostra é comparada contra seu branco. **Cascade** desloca traços
sobrepostos em x (minutos) e em y (por cento da altura) de modo que oito corridas
quase idênticas possam ser distinguidas.

**RT labels** põe o tempo do ápice em cada pico. Com um marcador presente,
**Relative labels** rotula novamente os picos pela distância até ele.

## O painel do espectro

O espectro de um scan do canal ativo, ou a média sobre um intervalo selecionado.
Canais de íons produto mostram o que sobreviveu à fragmentação de seu precursor;
o canal de survey (TOF MS) mostra tudo o que elui naquele momento. Onde nada
elui — uma infusão pulverizada por um minuto, cada scan igual ao anterior — a
corrida inteira é promediada num único espectro em vez disso, e é com ele que
o painel abre: ver [[direct-infusion]].

| Gesto | Efeito |
|---|---|
| Shift + arrastar | selecionar um intervalo de m/z |
| clique com o botão direito | *Extract XIC from selection*, *Find formula for this peak*, *Add marker here*, *Clear markers*, *Clear theoretical overlay*, *Reset label floor* |
| arrastar / duplo clique | zoom / ajustar |

**m/z labels** escreve a massa ao lado dos picos que valem ser nomeados, e
quais são eles é decidido de novo cada vez que a vista se move. O eixo de massas
na tela é dividido em oito janelas iguais, cada uma pode reivindicar três
rótulos começando pelo seu mais alto, e o pico mais alto de cada janela pede
espaço antes que qualquer janela peça um segundo — de modo que um trecho
congestionado não pode gastar toda a cota consigo mesmo. Um rótulo que seria
impresso em cima de outro já colocado continua sendo descartado em vez de
sobreposto, o que significa que o número desenhado é o que cabe e não o que foi
oferecido.

Escolher só por altura é o que isto substituiu, e lia-se mal num scan de survey:
no survey TOF MS de uma aquisição real os doze picos mais altos caíam todos
dentro de um trecho de 118 Da perto do início de um eixo de 100–2000, onze dos
doze colidiam entre si, e o espectro inteiro era desenhado com um único rótulo.
Por região, seis são desenhados e percorrem todo o eixo. Como as janelas seguem
a vista, dar zoom nomeia mais: no mesmo scan, sete rótulos entre m/z 150–350
contra quatro antes. *Compare spectra…* imprime com a mesma regra — vinte
rótulos naquele par de espectros contra doze.

**O piso dos rótulos**, e o triângulo que o define. Um pico precisa alcançar uma
fração do pico mais alto *em vista* para valer um rótulo; ele começa em 2%, que
é o que deixa um scan de survey legível. Quando o pico que interessa é pequeno —
um padrão a um por cento do pico base — é esse piso que está escondendo a massa
dele. O pequeno triângulo preenchido ao lado do eixo Y, na margem à esquerda
dele, é onde o piso está: arraste-o para baixo e mais picos são nomeados, para
cima e menos são. Uma linha pontilhada atravessa o gráfico mostrando o nível
enquanto o botão do mouse está pressionado. Duplo clique no triângulo, ou botão
direito ▸ *Reset label floor*, devolve o piso aos 2%. **Label floor (%)** na
barra View é o mesmo número digitado em vez de arrastado, e um move o outro; ele
é lembrado entre sessões, e a figura que *Compare spectra…* imprime é rotulada
com o que o painel estava mostrando.

É uma fração do pico mais alto em vista e não uma intensidade, então sobrevive a
um zoom, a *Normalise* e ao espectro seguinte: com zoom num trecho silencioso o
piso é medido contra o que está na tela, não contra um pico base que está fora
dela.

Quanto isso vale, medido. No scan de íons-produto de um ácido biliar deuterado
infundido para esse fim, com a média de toda a corrida, o próprio precursor —
m/z 430.3197, a 1,49% do pico base — **não** é nomeado a 2% e **é** nomeado a
0,5%: sete rótulos contra oito no eixo inteiro de 50–450, e dois contra três com
zoom em 350–440. No survey TOF MS de uma aquisição real o eixo inteiro de
100–1960 é desenhado com os mesmos seis rótulos a 2%, a 0,5% e a 0,1% — ali quem
decide é o congestionamento e não o piso — enquanto ao longo do eixo, em dezoito
janelas de 100 Da, são 57 rótulos a 2%, 57 a 0,5% e 70 a 0,1%, e em dezenove
janelas de 20 Da entre m/z 100–500, 67, 95 e 95. O ganho está nos trechos
silenciosos, que é onde um pico pequeno vale ser nomeado; num trecho
congestionado os três rótulos que uma janela pode reivindicar são o que acaba
primeiro, e baixar o piso não muda nada.

**Marcadores.** Solte um marcador sobre um pico e os demais picos são rotulados
com sua distância até ele em daltons, que é como perdas neutras (18.011 para
água, 44.026 para CO₂, 87.032 para uma serina) e espaçamentos isotópicos são
lidos em um espectro. Vários marcadores podem ser colocados; *Clear markers* os
remove.

Aba **Spectrum peaks**. Os picos do espectro na tela — m/z, intensidade e por
cento do pico base — encontrados por máximo local, centroidizados em dados de
perfil, e fundidos quando mais próximos que 0.03 Da, de modo que o topo ondulado
de um perfil não apareça como cinco massas. Dê duplo clique numa linha para
extrair aquela massa como um XIC.

## Comparando espectros entre amostras

O painel do cromatograma sobrepõe tantos traços quantos estiverem marcados; o
painel do espectro mostra um espectro por vez, porque um espectro pertence a um
scan de um canal de uma amostra. **Pin spectrum** (a barra de ferramentas
Processing, ou o menu de contexto do espectro) mantém o espectro na tela de modo
que o próximo desenhe sobre ele: mude para outra amostra na árvore, outro scan
ou outro canal, e o novo espectro é desenhado em azul sobre os fixados, cada um
em sua própria cor e nomeado na legenda pela amostra, pelo canal e pelo scan de
onde veio. Vários podem ser fixados; **Unpin spectra** os limpa.

Dois interruptores tornam a comparação legível. **Normalise** põe cada espectro
sobre seu próprio pico base, que é o que duas amostras em concentrações
diferentes precisam. **Mirror** desenha um espectro a cada dois para baixo, de
modo que um espectro fixado e o ao vivo tornam-se um gráfico cabeça-cauda — o
modo como uma correspondência de biblioteca é usualmente mostrada, e a maneira
mais rápida de ver um pico presente em um e ausente no outro. Com mais de um
fixado, as cores fazem a separação e o Mirror alterna.

Todo o resto lê o espectro ao vivo: a tabela de picos, o [[formula-finder]], o
Explain do [[lipid-maps]], a [[spectral-library]]. As cópias fixadas são
perdidas quando os arquivos são fechados — e guardadas quando o projeto é
salvo.

### O que um salvamento guarda

Salvar o projeto salva o painel: cada espectro fixado, o piso dos rótulos,
Normalise, Mirror e Centroid, e o espectro que estava ao vivo. Abra o projeto
de novo e os fixados estão de volta, o piso está onde foi deixado e a
comparação está de pé — de modo que *Export comparison…* e a seção *Compared
spectra* do relatório funcionam sem fixar nada outra vez. É uma coisa só a
salvar, não duas: não há um comando separado para a vista.

O que é escrito no projeto é **como** cada espectro foi feito — qual amostra,
qual canal, qual scan ou trecho de tempo, e a janela de fundo se alguma foi
subtraída — e nunca os seus pontos, e é por isso que um projeto que guarda
duas médias de corrida inteira de uma infusão tem três kilobytes em vez de
vinte megabytes. Os espectros são lidos dos arquivos brutos de novo quando o
projeto abre, de modo que o que volta é o que os arquivos dizem agora: alguns
segundos a mais do que abrir apenas os arquivos. Um fixado cujo arquivo bruto
saiu do lugar não pode ser lido, e permanece na lista com o nome *not
available: file missing* — uma comparação que voltasse com um espectro a menos
sem dizê-lo seria lida como a comparação que foi salva. Passar o ponteiro
sobre o painel do espectro lista os fixados e como cada um foi feito.

### Levando a comparação embora

**File ▸ Export comparison (PNG/SVG)…** escreve o que o painel está mostrando
como uma única figura — habilitado assim que algo é fixado. O PNG sai com o
dobro do tamanho do próprio desenho, que é o que deixa a tipografia e os
bastões nítidos quando ela é impressa ou posta num slide; o SVG é o mesmo
desenho em vetores, para uma figura que será redimensionada. De um jeito ou
de outro a figura é desenhada de novo a partir dos dados em vez de capturada
da tela, de modo que ela é a mesma qualquer que seja o tamanho da janela, e é
desenhada para a página em que vai parar, e não para a janela de onde veio.

Que página é essa, o diálogo pergunta — um tema ao lado do nome do arquivo,
guardado para a figura seguinte:

| Tema | O que desenha | Medido |
|---|---|---|
| Paper | fundo branco, eixos escuros e cada traço na sua própria cor, escurecida onde uma cor de janela escura sairia como uma linha pálida | o azul do tema claro está em 8,6:1 sobre branco e não é tocado; #e08a1e é desenhado como #c97b1b, a 3,3:1 |
| Black and white | fundo branco e cor nenhuma: os traços se distinguem pelo tom e pelo estilo de linha — o primeiro preto sólido, o segundo cinza tracejado, o terceiro pontilhado — e os bastões de centroides por uma cabeça cheia ou vazada | o preto está em 21:1 sobre branco e o #666666 em 5,7:1; nos dois espectros médios de CA-d4 a tinta dos dois traços tem cinza mediano 0 e 102 em 255, e os tracejados sobrevivem à figura ser reduzida à metade |
| Dark | o próprio fundo escuro da aplicação, com todas as cores clareadas até se manterem legíveis sobre ele | sobre #1e2124: #234b8c desenhado como #336ecd, a 3,3:1; #e08a1e intacto, a 6,0:1; o próprio #6f9be0 do tema escuro, a 5,7:1 |

Três para um é o que a WCAG pede de uma linha que carrega significado, e é o
que se exige de toda cor de traço sobre o fundo em que ela é desenhada — uma
medida, não uma opinião sobre uma cor. O matiz nunca muda, só a sua
luminosidade, de modo que um traço conhecido pela sua cor na tela é o mesmo
traço na página. O preto e branco é o que abre mão do matiz, porque uma cor
que a impressão em escala de cinza está prestes a achatar não é uma
distinção; o que ele gasta no lugar é estilo de linha, que sobrevive a
qualquer coisa.

Só as cores e os estilos de linha mudam: os eixos, os picos e quais deles são
nomeados são o mesmo desenho nos três, de modo que uma figura reexportada em
outro tema é a mesma figura. A única coisa que se move é um rótulo cujo pico
ganhou uma cabeça — o preto e branco marca um bastão de centroide com uma, e
um rótulo se afasta dela como se afasta de qualquer outra tinta, ficando uma
fileira mais para fora com um fio até o seu ápice. Nos dois espectros médios
de CA-d4 desenhados como centroides, são as mesmas trinta e duas massas
nomeadas nos dois temas, quatorze delas elevadas no papel e vinte e oito no
preto e branco.

As massas impressas ao lado dos picos são as que o painel nomeia — o mesmo
orçamento de alguns rótulos por região do eixo de massas —, mas a figura
impressa as posiciona de outro jeito, porque numa página não se dá zoom. Um
rótulo fica acima do pico que ele nomeia e nunca sobre ele: onde esse espaço
já está tomado, por outro rótulo ou por qualquer traço, o rótulo sobe uma
linha inteira e um fio fino o liga ao seu ápice, de modo que um trecho
apinhado se lê como fileiras de massas em vez de números empilhados sobre os
bastões. O espaço para as fileiras é reservado acima do traço mais alto, e
abaixo do mais baixo com o Mirror ligado. Um rótulo que não tem para onde ir
dentro de seis linhas — um isótopo ao lado de um pico base que alcança o topo
do gráfico é o caso comum — fica de fora em vez de ser desenhado sobre o que
descreve, e é por isso que uma comparação impressa pode nomear menos picos
que o painel, e por isso que os que ela nomeia podem ser lidos.

A mesma figura entra no [[report]], sob *Compared spectra*, com uma tabela
dos traços e uma tabela das massas que eles têm em comum. O que o relatório
imprime é o que o painel mostra: fixar um espectro inicia a comparação, mudar
o espectro ao vivo ou qualquer um dos dois interruptores a atualiza, e
**Unpin spectra** a descarta. Não há nada a manter em dia à mão e nada que
possa ficar desatualizado — se o painel contém dois espectros que valham ser
reportados, o relatório também os contém; se não, o relatório deixa a seção
de fora. A comparação em si não é escrita no projeto — ela é uma cópia dos
traços, e uma cópia de uma cópia —, mas os fixados que a produzem são, de
modo que ela está de pé assim que o projeto abre.

## Espectros de perfil e seus zeros

Um espectro de perfil de um `.wiff` e o mesmo espectro de um mzML não têm o
mesmo número de pontos. A SCIEX retira os pontos de intensidade zero ao
armazenar e os repõe ao desenhar; um mzML carrega o que foi armazenado.
Desenhado como vem, uma linha vai direto do último ponto de um pico ao primeiro
ponto do seguinte e o trecho vazio entre eles parece uma linha de base
inclinada — sinal onde não há nenhum. Pior, um rótulo de pico tomado através da
lacuna estava errado: um leu 184.8466 para um pico em 185.0077.

Então o programa restaura os zeros para qualquer formato que não os tenha,
medindo o intervalo de amostragem a partir do próprio arquivo: o menor quarto
das lacunas entre pontos são as que estão dentro dos picos, e interpolá-las ao
longo do eixo de massa dá o intervalo em qualquer massa — nenhuma física de
instrumento é presumida, o que cobre igualmente um tempo de voo e um Orbitrap.
Cada ponto acrescentado é um zero, em uma massa onde o instrumento não reportou
nada; nenhuma intensidade muda. Um espectro que já carrega seus zeros não tem
lacuna larga o bastante para acioná-lo e volta intocado.

## Centroide

*Centroid* na barra de ferramentas Processing converte um espectro de perfil em
bastões: um por pico, no centro de massa ponderado pela intensidade, tão alto
quanto o ápice do perfil. Um espectro centroidizado tem menos pontos que seu
perfil, razão pela qual a sobreposição de padrão isotópico teórico e o
localizador de fórmula trabalham sobre o que estiver sendo mostrado.

## Suavização e linha de base

**Smooth (σ, scans)** aplica um filtro gaussiano dessa largura a cada
cromatograma; 0 o desliga. Uma gaussiana é o filtro certo para cromatografia
porque, ao contrário de uma média móvel, preserva a posição e a área do pico.
**Baseline (min)** estima um envelope inferior sobre uma janela dessa largura —
mínimos por bloco, interpolados e suavizados — e o subtrai; a janela tem de ser
mais larga que o pico mais largo que valha a pena manter, ou o pico é tomado
como linha de base. Ambos se aplicam ao desenho, à integração e à exportação, de
modo que um número na aba Results é o número na tela.

## Subtração de fundo

Selecione um trecho de cromatograma que não contenha pico e use **Set
background**: o espectro médio sobre aquele intervalo é subtraído de cada
espectro mostrado até **Clear background**. O intervalo em uso é nomeado ao lado
dos controles de scan.

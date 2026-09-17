---
title: O que foi medido
---
Cada número neste manual foi produzido rodando algo sobre dados reais, e não
lendo código ou repetindo a afirmação de um fabricante. Esta página os
reúne, com aquilo em que foram medidos, para que quem lê possa decidir até
onde cada um alcança no seu próprio instrumento. Salvo indicação em
contrário, os dados são um de três conjuntos: cinco aquisições reais de um
TripleTOF 5600 em modo **negativo** — um método MRM-HR direcionado de 81
experimentos ao longo de dois períodos, cerca de 24,000 espectros cada; um
lote de 26 injeções no mesmo instrumento em modo **positivo**, um método
agendado para esfingolipídios com 141 componentes e 11 padrões internos,
amostrado a cada 14.6 s; e nove infusões diretas de padrões de ácidos
biliares num ZenoTOF 7600, **positivo**, varreduras de íons produto sem
varredura de survey nenhuma. De qual conjunto veio cada cifra está dito ao
lado dela.

## O leitor

- **As builds concordam.** A impressão digital `--digest` a partir do
  código-fonte no macOS, a partir da imagem de disco da CI e a partir do
  instalador do Windows sob o CrossOver é idêntica byte a byte: 405
  cromatogramas de canal, 25 espectros, 125 picos integrados com áreas até a
  nona casa decimal. Todos os 405 hashes de canal diferem entre si, portanto
  aquelas foram cinco aquisições diferentes e não uma lida cinco vezes.
- **Sem o `.wiff.scan`, o `.wiff` abre e parece inteiro.** Medido em um
  arquivo de infusão de um ZenoTOF 7600 cujo companheiro tinha sido
  renomeado à mão: a lista de amostras, os metadados, os parâmetros do método
  e o cromatograma de íons totais de cada canal foram lidos normalmente; o
  cromatograma de pico base, todo cromatograma de íon extraído e todo
  espectro falharam, com o Clearcore2 reportando um arquivo 'scan' ausente
  para os espectros e uma montagem ausente (`OFX.Core.Contracts`) para os
  cromatogramas. Nada no próprio arquivo diz que o companheiro está ausente;
  só ler um scan diz, e é por isso que um é lido quando o arquivo é aberto.
- **Um `.wiff2` não contém dados de scan, e isso foi medido antes de ele ser
  deixado de fora.** O Clearcore2 levanta `Invalid OLE structured storage
  file` em todos os nove `.wiff2` de uma pasta de um ZenoTOF 7600 — com os
  companheiros ao lado, com cada companheiro retirado por vez, e quando o
  arquivo é renomeado para `.wiff`, logo é o contêiner e não a extensão — e
  o seu próprio `CheckDataFileIntegrity` chama cada um deles de
  `NotWiffFile`. A montagem do Clearcore2 que escreve o formato declara o
  seu esquema inteiro: sete tabelas, nenhuma com coluna para um espectro, um
  pico, uma intensidade ou um cromatograma, e uma tabela `header` de
  `wiff_hash`, `scan_hash` e `scan_size`. Os tamanhos concordam — nesses
  nove o `.wiff.scan` vai de 1.67 a 9.88 MB (5.9×) e o `.wiff2` de 303 a
  406 kB (1.34×, cinco valores distintos), correlacionando 0.989 com o
  `.wiff` e 0.748 com os dados de scan. Ler o `.wiff` de uma aquisição com o
  `.wiff2` ao lado e com ele apagado deu a mesma amostra, o mesmo
  experimento, o mesmo TIC de 473 pontos e o mesmo primeiro espectro de
  13.705 pontos. Ver [[formats]].
- **Os formatos concordam, exceto em um ponto.** Exportado para mzML e lido
  de volta: espectros, cromatogramas de canal, o TIC da corrida (577 pontos)
  e as áreas integradas idênticos; os cromatogramas de íon extraído diferem
  em uma mediana de 0.58% da altura do pico, no máximo 12%, sempre menores
  aqui, porque a SCIEX conta parte de um pico cujos pontos caem logo fora da
  janela. De ponta a ponta, um componente quantificado a partir dos dois
  formatos: mesmo tempo de retenção, mesma largura, área com 0.54% de
  diferença. Duas tentativas de reproduzir a regra de borda do fabricante
  falharam; a segunda foi melhor em 41 canais e pior em 38.
- **O ProteoWizard concorda.** O msconvert lê o que este programa escreve, e
  o mzML que ele próprio escreve a partir disso é lido de volta aqui com
  espectros e cromatogramas idênticos.
- **Somar os pontos armazenados em vez de tomar o total do fabricante**
  deslocou toda área integrada em 2%. O número do fabricante é o usado.
- **Canais a partir das propriedades dos scans apenas** deram 69 onde a
  aquisição tinha 81; a partir do ciclo de aquisição, 81.
- **Os zeros de um perfil removido**, desenhado sem restaurá-los, puseram o
  rótulo de um pico em 184.8466 para um pico em 185.0077.

## Integração

- **Uma janela mais estreita que cinco pontos não retornou nada**, houvesse o
  que houvesse nela; um pico de 44,875 contagens foi lido como ruído. Dar ao
  detector três scans de cada lado levou as linhas com um pico de 1,771 a
  2,665 e os componentes com algum pico de 89 a 139 de 141.
- **A regra de escolha do pico não mudou nada naquele método**: das 896
  janelas com um tempo de retenção, nenhuma continha dois picos (uma janela
  de ±0.5 min a 14.6 s são quatro pontos); as 593 janelas que continham dois
  pertenciam a componentes sem tempo, onde *nearest* não tem de que estar
  perto.
- **Sensibilidade à fase a 14.6 s** em picos sintéticos: um trapézio varia
  com a fase dos scans em 16.8% a 11.3 s de largura à meia altura, 5.1% a
  14.1 s, 1.1% a 17 s; um ajuste gaussiano é exato onde quer que possa ser
  feito, e pode ser feito em 34 de 60 fases a 14.1 s e em todas as 60 a
  17 s. Com ruído de Poisson sobre mil contagens, a 14.1 s: trapézio 5.8%,
  ajuste 3.0%.
- **Um ajuste a dois pontos** é enviesado para baixo em sete por cento; um
  ajuste através de três com três parâmetros é exato quaisquer que sejam os
  pontos, e no lote real isso passou uma curva por um ápice de 52,000
  contagens e vizinhos de 44 e 98 e reportou uma área um terço menor. Daí a
  regra de que o ajuste precisa de três pontos em ou acima de 1% do ápice.
- **Os três algoritmos no lote real**: vale, 2,638 linhas encontradas;
  somatório, 857; gaussiano, 2,638 com 2,238 que recaíram no vale, 2,169
  delas porque o pico tinha menos de três pontos de largura. Onde ajustada, a
  área do ajuste foi uma mediana de 0.977 da do trapézio; nenhum componente
  se moveu mais que 20%. O %CV dos padrões internos foi o mesmo sob os três.
  O algoritmo não move os números daquele lote; a amostragem move.

## Amostragem

- No lote de 26 injeções, um scan a cada 14.6 s contra picos com **uma
  mediana de um ponto** sobre eles; 129 de 139 componentes tipicamente abaixo
  dos três de que um ajuste precisa, e 1 com cinco ou mais. As larguras só
  puderam ser medidas nos picos mais largos (dois pontos acima da meia
  altura), e essas deram uma mediana de 14.6 s — um ciclo — de modo que todo
  tempo de ciclo que o relatório de amostragem recomenda para aquele lote é
  um limite superior.

## O agendamento

- O método real agendado sobre as suas janelas: 59 transições com um tempo,
  no máximo 24 adquiridas ao mesmo tempo, e um ciclo de 3 s ainda deixando
  120 ms de dwell time — contra os 14.6 s a que o lote foi adquirido com
  todas as 144 rodando sem agendamento. 72 dos seus 141 precursores estão
  fora do survey de 50–700.

## A biblioteca espectral

- MassBank em formato NIST, 139,006 registros: lidos em 5 s, 1.3 GB em
  memória; uma busca filtrada em milissegundos, uma não filtrada em 2–7 s.
  Nos espectros de íons produto do lote ela nomeou uma esfingomielina C16
  (46 / 79), uma ceramida C16 (32 / 94), uma ceramida C24:1 (11 / 90) e uma
  esfingomielina C18 (48 / 96) — pontuações plana e reversa — e nada para os
  padrões C17 que a biblioteca não tem. Antes da regra dos dois picos, um
  espectro que era quase todo 184.07 pontuou 83 contra um laxante naquele
  único pico; antes da regra do precursor desconhecido, 24,000 registros sem
  precursor dominavam toda busca filtrada.

## Dois lotes

- As mesmas 26 injeções sob o método antes e depois de os tempos de retenção
  de dois padrões internos serem corrigidos: linhas encontradas de 2,607 para
  2,638, o %CV mediano dos padrões de 101.8 para 87.7, e os dois padrões
  corrigidos de 8 e 3 linhas para 23 cada — os pontos por pico inalterados em
  um, já que a aquisição era a mesma. Para o que serve [[compare-batches]].

## O eixo de massas

- No lote de 26 injeções, cuja varredura de survey cobre 50–700, o único
  padrão interno forte o bastante para ser medido — `SM(d18:1/12:0)` — ficou
  em −4.0 ppm ao longo da corrida com uma dispersão de 16 ppm entre injeções.
  Outros nove voltaram com dispersões de 98 a 534 ppm: não é o mesmo íon duas
  vezes. A primeira versão da medida chamou um deles de derivando por
  −351 ppm, e é por isso que uma dispersão acima de 25 ppm agora impede que
  uma tendência seja ajustada de todo.
- Pisos propostos a partir do mesmo lote: 5,240 para aquele padrão, 522 e 566
  para os dois em torno de mil contagens, e de 2 a 25 para os demais — que é
  o que as suas medianas são.

## Ruído

- Em 846 traços reais, a mediana tinha três pontos não nulos em sessenta e
  um, e 9% tinham uma linha de base que variava de todo. O ruído pôde ser
  medido para 23% dos picos encontrados.
- Com o piso de uma contagem no lugar de um ruído não mensurável, um padrão
  de 30 contagens reportou S/N 30 e um de 42,400 reportou 42,400.
- Ruído medido dentro da janela de tempo de retenção leu 16,944 onde o ruído
  do traço era 505: S/N 19 automático contra 531 à mão.

## Controle de qualidade

- Um desvio absoluto mediano de 0.8% fez de um padrão 2.4% baixo um outlier
  de quatro sigmas; daí os pisos percentuais.
- Uma injeção em que todo padrão voltou a um quinto do normal ficou em 2.6σ
  em um lote que variava um terço; daí a regra dos 50%.
- De onze padrões internos, oito tinham resposta mediana entre 4 e 52
  contagens e produziam quase todos os sinalizadores; daí o critério de
  S/N 10.
- Os padrões, tomados separadamente, dispersaram entre 32% e 228%; o índice
  de resposta da injeção pôs as injeções dentro de ±18% com três exceções.
- O lote não sustenta piso de resposta nenhum: a dispersão entre injeções
  sucessivas não acompanhou a resposta mediana.

## Estimativa de tempo de retenção

Verificada contra os 54 componentes que já declaravam um tempo, a estimativa
caiu dentro de um intervalo de amostragem para 45% dos componentes abaixo de
100 contagens, 54% entre 100 e 1,000, 54% entre 1,000 e 10,000, e 88% acima
de 10,000. Nada do que foi oferecido estava acima de 10,000, portanto nada
foi pré-marcado.

## O relatório

A primeira versão imprimia a um doze avos do seu tamanho. Um relatório de cem
páginas é diagramado três vezes e leva cerca de dezessete segundos.

## O que custa numa máquina

A rapidez é uma medição como outra qualquer, por isso é feita da mesma
maneira: o `tools/bench.py` da árvore de código corre cada peça de trabalho
real como um cenário com nome, num processo próprio, cronometrado no
relógio de parede e com o pico de memória residente do processo. Estas são
as cinco aquisições do TripleTOF num Apple M4 com 16 GB, Python 3.14,
contra os mesmos cenários corridos na versão 0.9.0.

| O quê | 0.9.0 | agora |
|---|---|---|
| centroidar 25 espectros de perfil | 0,568 s | 0,045 s |
| a grade de revisão remodelada de 1x1 a 8x8 e de volta | 1,185 s, 400 MB | 0,212 s, 187 MB |
| a corrida como grade de contorno | 0,182 s | 0,066 s |
| 25 espectros de um canal | 0,075 s | 0,034 s |
| média de 100 varrimentos | 0,287 s | 0,175 s |
| um cromatograma de íon extraído | 0,047 s | 0,036 s |
| abrir cinco aquisições na janela | 0,541 s | 0,444 s |
| 81 componentes integrados em cinco aquisições | 0,523 s | 0,496 s |
| todos os algoritmos comparados no lote | 0,665 s | 0,668 s |
| ler um mzML de ponta a ponta | 0,764 s | 0,699 s |
| seis extrações de um canal de mzML | 0,856 s | 0,707 s |
| cromatograma de pico base de cada canal, mzML | 1,738 s | 1,024 s |
| a impressão digital `--digest` de cinco aquisições | 0,965 s | 0,909 s |
| o manual impresso em PDF, 106 páginas | 1,466 s | 1,462 s |

Dois números não estão nessa tabela porque não são medidos nestes
ficheiros. A janela principal, com um índice LIPID MAPS instalado, levava
cerca de um segundo e **688 MB** de memória a construir, quase tudo o
índice a ser lido para escrever quantas estruturas tem; agora constrói-se
com **144 MB** sem o ler — ver [[lipid-maps]]. E as nove infusões de ácidos
biliares medidas juntas no separador Infusões, mornas, passaram de 7,7 –
8,5 segundos para 1,7 — ver [[infusion-report]].

As três últimas linhas da tabela são a parte honesta: a comparação, o
leitor de mzML e o manual impresso quase não se mexeram, porque o que
consomem é a paginação do Qt e a análise de 47 MB de XML, e nenhuma das
duas é nossa para acelerar.

## Estes números são testados

Um número escrito numa página não tem como falhar. Como as aquisições nunca
estão no repositório de código — pertencem a outras pessoas, e uma delas é
inédita —, cada número acima era prosa que nada verificava.

O repositório passou a levar `tests/real/`: um teste por número, executado
contra as mesmas aquisições, que falha quando um número sai da tolerância com
que foi escrito. Fica ignorado a menos que os dados sejam pedidos e estejam
presentes — `MILQ_REAL_DATA=1 pytest tests/real`, ou `pytest -m real` —,
de modo que nunca roda na integração contínua, onde não há o que ler. Cada
teste se ignora sozinho, dizendo qual caminho procurou, quando os seus
arquivos estão noutro lugar, e cada um diz com as próprias palavras qual
número desta página ou do `CLAUDE.md` está assegurando.

Onde um número já havia mudado quando passou a ser coberto, o teste assegura o
que o programa faz **hoje** e registra ao lado o número antigo com o que se
sabe da diferença. Seis deles, nesta página e no `CLAUDE.md`, estão nessa
situação; `tests/real/README.md` os lista.

## O caminho da infusão medido como uma coisa só

Cada número acima foi medido sobre uma etapa isolada. [[integration]] roda em
vez disso todo o caminho de infusão direta, de ponta a ponta, sobre as nove
aquisições do ZenoTOF — a verificação de pasta, o veredicto, a máscara, a
média, o piso de ruído, o isolamento, o eixo, a explicação, a margem, a
biblioteca, o relatório, as exportações e a comparação — e dá o que cada
etapa custa a frio e a quente, o que o todo segura em memória, e os lugares
onde dois módulos responderam à mesma pergunta de formas diferentes. Seis
dessas discordâncias estão consertadas e três continuam em aberto, com os
números de cada uma.

## Onde o resto está escrito

O `CLAUDE.md` do repositório de código registra os mesmos fatos para quem
altera o programa, com o commit de que cada um veio; os testes asseguram a
maior parte deles.

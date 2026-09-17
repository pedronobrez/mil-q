---
title: Formatos de arquivo
---
Dois formatos são lidos: `.wiff` da SCIEX e mzML. Um é escrito: mzML.

## .wiff

Uma aquisição SCIEX são dois arquivos, `name.wiff` e `name.wiff.scan`, e os
dois são necessários — o primeiro guarda o método e o índice, o segundo os
espectros. O `.wiff` sozinho abre: a lista de amostras, o método, o
cromatograma de íons totais de cada canal e os parâmetros de aquisição estão
nele, e a árvore se preenche como se nada estivesse errado. O que não está
nele são os dados de scan, de modo que o primeiro espectro pedido falha — e
com ele todo cromatograma de íon extraído, o cromatograma de pico base, o
contorno e a quantificação, que todos leem os scans. O MIL-Q tenta um
espectro quando o arquivo é aberto e, se falhar, diz isso de imediato: um
aviso quando o arquivo é acrescentado, um *⚠* diante da amostra na árvore,
com o motivo ao passar o cursor, o motivo no título do painel de espectro
onde estaria um espectro, e uma nota em qualquer linha de resultado que não
pôde ser extraída. A mensagem nomeia o arquivo que tem de estar ao lado do
`.wiff` e, quando a pasta contém um `.scan` que não pertence a nenhum
`.wiff` ali, nomeia também esse — um companheiro renomeado à mão
(`name.wiff_mix1.scan` ao lado de `name_mix1.wiff`) é a maneira habitual de
o par se desfazer, e renomeá-lo para `name_mix1.wiff.scan` é o reparo
inteiro — que [[checking-files]] encontra e oferece antes mesmo de o
arquivo ser aberto. Um `.wiff2` ao lado do par não é lido aqui, e nada se
perde com isso — veja a seção abaixo para o que foi medido.
Eles são lidos pelas próprias bibliotecas Clearcore2 da SCIEX, que
são o único software capaz de decodificar o formato e são redistribuídas
pelo pacote de código aberto alpharaw. Como elas são feitas funcionar fora
do Windows está descrito em [[how-wiff-is-read]].

Um `.wiff` pode conter várias amostras; cada uma é aberta como uma entrada
própria. Os arquivos são abertos em modo compartilhado somente leitura, de
modo que o Analyst ou uma segunda janela do MIL-Q podem abrir o mesmo
arquivo ao mesmo tempo.

Cada canal de aquisição — cada experimento do método — é listado com o seu
tipo, precursor, faixa de massas e energia de colisão, tal como o arquivo os
declara. Totais, tempos de retenção e áreas integradas que a biblioteca do
fabricante reporta são usados como reportados; nada é recalculado a partir
dos pontos armazenados onde existe o número do próprio instrumento, porque
somar os pontos armazenados em vez disso foi medido deslocando toda área
integrada em 2%.

## .wiff2

Um instrumento com SCIEX OS escreve um terceiro arquivo ao lado do par,
`name.wiff2`, e num ZenoTOF 7600 uma aquisição chega como um trio. Ele não
é aberto aqui, e o motivo é medido e não suposto.

Não é o mesmo tipo de arquivo. Um `.wiff` é um documento composto OLE; um
`.wiff2` é um banco de dados SQLite protegido por senha. Ao ser pedido para
abrir um, o Clearcore2 diz `Invalid OLE structured storage file`, e o seu
próprio `CheckDataFileIntegrity` chama-o de `NotWiffFile`. Isso valeu para
todos os nove `.wiff2` da pasta em que isto foi testado, com os
companheiros ao lado e com cada companheiro retirado por vez, e continuou
valendo quando o arquivo foi renomeado para `.wiff` — logo é o contêiner, e
não a extensão.

E, o que mais importa, não há nada nele para ler. A montagem do Clearcore2
que escreve um `.wiff2` declara o esquema inteiro, e são sete tabelas:
`header`, `sample`, `method`, `device_method`, `device_descriptor`,
`device_identifier` e `method_parameters_info`. Nenhuma coluna guarda um
espectro, um pico, uma intensidade ou um cromatograma. O que a tabela
`header` guarda é `wiff_hash`, `scan_hash` e `scan_size` — a identidade e o
tamanho dos dois arquivos ao lado dele. O `.wiff2` é o método da aquisição
e o seu registro dos companheiros, não os seus dados.

Os tamanhos dos arquivos dizem o mesmo. Nessas nove aquisições o
`.wiff.scan` — que realmente contém os espectros — vai de 1.67 a 9.88 MB,
um fator de 5.9, enquanto o `.wiff2` vai de 303 a 406 kB, um fator de 1.34,
em cinco valores distintos. O `.wiff2` acompanha o `.wiff` (correlação
0.989), não os dados de scan (0.748).

Portanto o `.wiff` de mesmo nome contém a aquisição, e abri-lo não perde
nada: lido com o `.wiff2` ao lado e com o `.wiff2` apagado, o mesmo arquivo
deu a mesma amostra, o mesmo experimento único, o mesmo cromatograma de
íons totais de 473 pontos e o mesmo primeiro espectro de 13.705 pontos. Um
`.wiff2` sem nenhum `.wiff` ao lado é uma aquisição que não pode ser aberta
aqui de modo algum, e nenhum leitor poderia ser escrito para ele a partir
deste contêiner — os espectros não estão nele. [[checking-files]] diz em
qual dos dois casos uma pasta está antes de qualquer coisa ser aberta.

## mzML

mzML é o formato aberto que o `msconvert` do ProteoWizard escreve a partir
dos arquivos de qualquer fabricante, de modo que um `.raw` da Thermo, um
`.d` da Agilent ou um `.tdf` da Bruker entram sendo convertidos primeiro.
Espectros em perfil e em centroide são ambos lidos, e os pontos de
intensidade zero que um fabricante removeu de um perfil são restaurados —
ver [[chromatograms-and-spectra]] para por que isso importa.

O que o arquivo declara sobre cada scan é lido e mostrado, e nada disso é
adivinhado: a polaridade a partir de `positive scan` ou `negative scan`, o
precursor a partir de `selected ion m/z` — ou, onde um conversor escreveu
apenas uma janela de isolamento, do centro dela — a carga a partir de
`charge state`, a energia de colisão, e **como o precursor foi quebrado** a
partir do elemento `activation`. Esta última é a coisa que um `.wiff` não
carrega: a biblioteca da SCIEX expõe a energia e nada que nomeie o método,
de modo que a ativação de um canal de `.wiff` fica vazia enquanto a de um
arquivo Thermo convertido diz *beam-type collision-induced dissociation*.
Vinte e dois elétron-volts disso e vinte e dois de transferência de elétrons
são experimentos diferentes sobre o mesmo precursor, então a ativação separa
dois canais que nada mais no scan distingue. Tudo isso aparece sob o canal
no [[explorer]].

O nome do instrumento é lido de três maneiras, porque os fabricantes o
escrevem de três maneiras: como termo próprio do vocabulário controlado com
valor vazio, como o termo genérico *instrument model* com o modelo no valor
e — que é como o ProteoWizard escreve todo arquivo Thermo — em um
`referenceableParamGroup` para o qual cada configuração de instrumento
apenas aponta. Dois arquivos Thermo reais, um LTQ Orbitrap Elite e o próprio
exemplo LTQ FT do ProteoWizard, diziam *unknown* até que essa referência
passasse a ser seguida.

Fazer a média de uma faixa de scans **soma cada scan nas massas em que ele
mediu**, e não põe nada em nenhum outro lugar. Vale dizê-lo porque a
alternativa óbvia está errada: dois scans de um tempo de voo não
compartilham um eixo de massas, então a média é sobre a união dos dois, e
interpolar cada scan sobre essa união traça uma reta através de todo trecho
em que um espectro de perfil sem os seus zeros não tem ponto nenhum — sinal
em massas onde o instrumento não reportou nada. Medido contra a própria
média da SCIEX dos mesmos 146 scans sobre as mesmas 221.847 massas, a
interpolação pôs 220.222 delas mais altas e totalizou **3,31 vezes** o
espectro do fabricante; centroidá-lo deu 670 picos onde a média do
fabricante dá 424. Somar os scans onde eles foram medidos reproduz o
espectro médio do fabricante exatamente — maior diferença em qualquer massa
0,0 — e está certo também para um arquivo centroidado, onde interpolar entre
dois bastões é ainda pior.

mzML não tem noção de *canal* de aquisição. Os canais são inferidos, e
inferidos a partir da ordem de aquisição em vez de apenas das propriedades
dos scans: um método pode ter dois experimentos que concordam em nível de
MS, precursor, energia de colisão e faixa de massas, e agrupar só pelas
propriedades deu 69 canais onde a aquisição tinha 81. Um método agendado
repete os seus experimentos em um ciclo fixo, de modo que a posição no ciclo
é o experimento. O arquivo contra o qual isto foi desenvolvido é um ciclo de
44 executado 339 vezes seguido de um ciclo de 37 executado 238 vezes —
44 + 37 = 81 canais, 44 × 339 + 37 × 238 = 23,722 espectros. Um ciclo tem de
se repetir pelo menos quatro vezes para ser acreditado; a aquisição
dependente de dados não tem ciclo e recai sobre as propriedades dos scans.

O cromatograma de íons totais **da corrida** segue a mesma resposta. Onde há
um ciclo, os experimentos de um período são somados ciclo a ciclo, porque é
isso que o instrumento reporta — 577 pontos para aqueles 23.722 espectros, e
não 23.722. Onde não há ciclo, é um ponto por espectro, que é o que o
próprio programa de uma corrida dependente de dados desenha. Nada mais
serve: uma infusão direta real da Thermo que caminha a janela de isolamento
sobre o precursor em incrementos de 0,02 Da tem 164 espectros e 82 canais
inferidos de um, dois e cinco scans, e agrupá-los por quantos scans cada um
tinha — a regra que valia antes — dava à corrida **oito pontos para 164
espectros**. O total estava certo e a forma era ficção, e a forma é
exatamente o que [[direct-infusion]] lê para decidir o que uma amostra é.

Um cromatograma de íon extraído precisa de todos os scans do seu canal, e
cada scan é decodificado direto dos bytes do arquivo — as posições e as
codificações dos vetores são localizadas na primeira vez que um scan é
pedido, e o analisador de XML não volta a correr para ele. Um canal já
decodificado fica guardado para o próximo componente que o pedir, sob um
orçamento de 256 MB para o processo inteiro, saindo primeiro o canal mais
antigo; o arquivo em si é mapeado em vez de lido para a memória, de modo
que um lote com muitos arquivos abertos custa o cache de arquivos do
sistema e não a aplicação. Medido em uma corrida sintética de 81 canais e
19.440 espectros no Windows 11: uma extração passou de 32 ms para 11 ms
onde o canal precisou ser decodificado e para 0,1 ms onde já tinha sido,
e integrar 80 componentes em seis dessas injeções de 15,5 s para 4,8 s.
Nada muda nos números: os mesmos pontos são somados. A mesma medição numa aquisição
real de 107 MB num Apple M4: os 23.722 espectros decodificam em 0,41 s
contra 1,09 s pelo caminho antigo, e os cromatogramas de íon extraído e de
pico base dos 81 canais em 0,21 s contra 1,03 s — com cada um dos 7.608.772
valores idêntico entre os dois caminhos.

## Infusões a partir de mzML

Uma infusão de outro instrumento passa por todo o [[direct-infusion]] —
detecção, a média da corrida, [[lipid-maps]], a [[spectral-library]], o
[[infusion-report]] — igual a um `.wiff`. O veredito lê cromatogramas e
nunca um espectro, de modo que não pode depender do formato.

Verificado ponta a ponta em uma infusão real de ácido cólico-d4 num ZenoTOF
7600, lida de três maneiras: do `.wiff`, do mzML que este programa exporta
dele, e desse mzML reescrito do jeito que o ProteoWizard escreve um `.raw`
da Thermo — identificadores de scan Thermo, tempos em segundos, uma janela
de isolamento, um estado de carga, `beam-type collision-induced
dissociation`, e nada dizendo a que experimento um scan pertence. As três
dão **um canal de íons produto**, precursor 430,34 a 22 eV, 146 scans ao
longo de 0,61 min, ambas as figuras de planura **1,0000**, um espectro médio
cujo pico base é 377,3018 a 9.618,10 contagens e cujo total é 360.596,6986,
**424** centroides, **42** picos acima da fração de ruído, o precursor
sobrevivendo a 430,3489 com 9.415 contagens, e a fórmula explicando **8 de
56 íons previstos e 63,63%** do espectro. Três diferenças, todas do arquivo
e não do leitor:

| | `.wiff` | o mzML dele | mzML no formato Thermo |
|---|---|---|---|
| nome do canal | `TOF PI` | `TOF PI` | `MS2` |
| ativação | *(não carregada)* | collision-induced dissociation | beam-type collision-induced dissociation |
| pontos no espectro médio | 289.103 | 221.847 | 221.847 |

O nome é o do método de aquisição, que o mzML não tem onde guardar — então a
exportação deste programa o mantém em um parâmetro próprio e o arquivo de
qualquer outra pessoa é descrito pelo seu nível de MS. A contagem de pontos
são os zeros removidos: as mesmas massas onde quer que algo tenha sido
medido, e os zeros repostos quando o espectro é desenhado.

Duas coisas pelas quais uma infusão convertida ainda pode ser recusada, e as
duas são a aquisição e não o formato. Uma corrida de menos de 120 scans é
*too short to tell* — uma infusão real de Orbitrap com 108 scans de um
segundo e meio fica abaixo disso. E as figuras de [[direct-infusion]]
perguntam se a corrente iônica se mantém, então uma aquisição que varre de
propósito — caminhando a janela de isolamento sobre o precursor — é lida
como cromatográfica, porque a sua corrente iônica de fato sobe e desce: a
real medida acima dá **0,0123** onde 0,75 seria preciso. **Average whole
run** dá a mesma visão à mão em qualquer amostra.

## Escrever mzML

`File ▸ Export sample as mzML…` no Explorer escreve a amostra selecionada
espectro por espectro, com a corrente iônica total que o instrumento
reportou em vez de uma recalculada aqui. O que sobrevive à viagem foi medido
em cinco aquisições reais de 81 canais lidas de volta por este programa, e
verificado contra o ProteoWizard nos dois sentidos:

| | |
|---|---|
| espectros | idênticos, em todos os canais, até o último dígito |
| cromatogramas de canal | idênticos, em todos os canais |
| o cromatograma de íons totais da corrida | idêntico, 577 pontos |
| áreas de pico integradas | idênticas |
| cromatogramas de íon extraído | **diferem**, ver abaixo |

## A única diferença: cromatogramas de íon extraído

A extração da própria SCIEX conta parte de um pico cujos pontos medidos caem
logo fora da janela de massas; este programa soma os pontos dentro dela.
Naquela aquisição a diferença é, na mediana, 0.58% da altura do pico, no
máximo 12%, e sempre menor aqui. De ponta a ponta, quantificar um componente
a partir do `.wiff` e a partir do seu mzML dá o mesmo tempo de retenção e a
mesma largura do pico e uma área com 0.54% de diferença.

Foram feitas duas tentativas de reproduzir a regra de borda do fabricante.
Ambas erradas: a segunda parecia certa nas janelas das quais foi derivada e,
em outras janelas, foi melhor em 41 canais e pior em 38 — cara ou coroa.
Portanto a regra simples é a que é distribuída e este parágrafo é o aviso.
**Quantifique uma série em um só formato.** Ver [[measured-facts]].

## Qual formato para quê

| Tarefa | Usar |
|---|---|
| revisar e quantificar dados SCIEX | `.wiff` diretamente |
| dados de outro fabricante | msconvert para mzML, depois abrir o mzML |
| uma série que precisa ser comparada ao longo do tempo | um só formato para a série inteira |
| entregar dados a software que não lê `.wiff` | exportar como mzML |

Os arquivos brutos nunca são modificados. Tudo o que o programa acrescenta —
tipos de amostra, concentrações, o método, os resultados — vive no arquivo
de projeto, ver [[projects-and-files]].

---
title: Como um arquivo .wiff é lido
---
O formato `.wiff` / `.wiff.scan` é proprietário e não tem especificação
pública. As únicas bibliotecas capazes de decodificá-lo são as próprias
montagens **Clearcore2** da SCIEX — as mesmas que o msconvert do
ProteoWizard usa. São montagens gerenciadas .NET, redistribuídas pelo pacote
de código aberto alpharaw (MIT), e o MIL-Q as carrega através do
pythonnet.

## Fora do Windows

Normalmente o Clearcore2 não funciona fora do Windows, porque
`Clearcore2.StructuredStorage` abre o arquivo pela API COM
`StgOpenStorageEx`, exclusiva do Windows. O bootstrap contorna isso em três
passos:

1. localiza um runtime .NET 8, ou instala um em `~/.dotnet`;
2. baixa do NuGet as montagens de compatibilidade que o .NET Core não
   distribui — `System.Configuration.ConfigurationManager` e suas
   dependências — e registra um resolvedor para elas;
3. por reflexão, inverte o campo estático privado `StgStorage.sWindows` para
   `False`, o que faz o Clearcore2 usar a sua implementação gerenciada de
   armazenamento estruturado (OpenMcdf) em vez do caminho COM.

Com isso, arquivos `.wiff` são lidos nativamente em Apple Silicon, sem
Docker, sem Wine e sem o Analyst instalado. A cultura é fixada em `en-US`
enquanto as montagens rodam, de modo que uma máquina cujo separador decimal
é a vírgula lê os mesmos números que uma cujo separador é o ponto.

## A travessia de .NET para numpy

O Clearcore2 devolve um `double[]` do .NET, e todo cromatograma, todo
espectro e todo cromatograma de íon extraído chega assim. O pythonnet expõe
esse arranjo como um buffer contíguo em C, de modo que o numpy pode levar
tudo em uma cópia só; percorrê-lo com `list()` empacota um `double` de cada
vez através da fronteira gerenciada. Medido em uma varredura TOF real de
1.143 pontos: **0,194 ms um elemento por vez contra 0,0009 ms pelo buffer**,
os mesmos `double` byte a byte. Essa travessia era 84% do custo de construir
um contorno e dois terços do de calcular a média de cem varreduras.

O arranjo é **copiado** para fora do buffer, e não visto através dele. Uma
vista seria um fio mais rápida, e sua memória pertence ao heap do .NET:
correta enquanto o arranjo existe, e uma leitura de memória liberada no
instante em que o coletor a recolhe — o que no macOS aparece como números
plausíveis, não como uma falha. O que o protocolo de buffer recusar recai
sobre o percurso elemento a elemento, de modo que um Clearcore2 futuro que
devolva outra coisa fica mais lento e nunca errado.

## Acesso compartilhado

Os arquivos são abertos com `OpenFileMode.ReadOnlyShared`. Qualquer outra
coisa toma um bloqueio exclusivo, e uma segunda janela — ou o próprio
Analyst — não consegue abrir o mesmo arquivo.

## IDA: o precursor é de cada scan

IDA é a aquisição dependente de dados da SCIEX: um scan de survey e depois
alguns experimentos *dependentes* (`IDAType` Dependent ou Confirmation) que
cada ciclo preenche com um dos íons mais intensos oferecidos pelo survey.
Cada experimento dependente ainda declara uma massa fixa (`FixedMasses`)
como qualquer scan de íons-produto, e ela é um marcador de posição — numa
corrida de TripleTOF 5600 os oito slots declaram 1.0, 2.0 … 8.0, o número do
slot; num método do ZenoTOF os 24 slots declaram 829.5. O precursor
realmente isolado está em cada espectro, `MassSpectrumInfo.ParentMZ`, e muda
quase a cada ciclo.

Por isso um experimento dependente é lido como um **slot IDA**: não tem
precursor próprio, o seu rótulo na árvore é `TOF PI IDA slot 3`, e cada scan
carrega o seu próprio precursor (e a carga e a energia de colisão, que no
IDA podem variar com o precursor). Um ciclo cujo `ParentMZ` não é positivo
não disparou o slot; também não tem pontos. Um slot nunca é associado a um
componente pelo seu marcador, um espectro mostrado a partir dele diz de que
precursor veio — `parent 627.8457` para um scan, ou *mixes 37 precursors*
para uma média de ciclos que isolaram coisas diferentes — e o Explain e a
busca em biblioteca recebem o precursor do scan, ou nenhum quando uma média
os mistura. Para ler os scans de produto de um precursor em todos os slots,
use uma fonte filtrada por precursor ([[manual-xic]]). *Export sample as
mzML* escreve o precursor de cada scan e deixa de fora os ciclos em que o
slot não disparou. Janelas SWATH, MRM e scans de íons-produto realmente
fixos mantêm a sua massa fixa. A regra é a que o MIL-X segue
(`docs/SCIEX-IDA.md` lá).

## O que vem do fabricante e o que não vem

Totais, tempos de retenção e áreas integradas que a biblioteca do fabricante
reporta são usados como reportados: somar os pontos armazenados em vez disso
foi medido deslocando toda área integrada em 2%. Espectros em perfil voltam
com os pontos de intensidade zero que a biblioteca restaura na saída. Os
cromatogramas de íon extraído são a única coisa calculada aqui em vez de
pedida à biblioteca, e o único ponto em que as duas discordam — ver
[[formats]]. Um espectro é centroidado por este programa para rótulos,
Explain e a biblioteca espectral; `MILQ_WIFF_CENTROID=sciex` passa isso ao
próprio localizador de picos da SCIEX — ver [[environment-variables]], que
diz por que esse não é o padrão.

## Verificado onde

A leitura de um `.wiff` foi feita, em aquisições reais, no macOS. Linux e
Windows rodam a suíte de testes e iniciam a aplicação em integração
contínua, e um job semanal pergunta se as montagens da SCIEX ainda carregam
em cada um — o que não depende de nada neste programa — mas o caminho de "as
montagens carregam" até "uma aquisição abre" é verificado apenas no macOS, e
a única leitura real da build do Windows foi sob o CrossOver. Ver
[[installation]].

## Licenciamento

O código do MIL-Q é MIT. As bibliotecas Clearcore2 pertencem à SCIEX e
não são de código aberto — são redistribuíveis, o mesmo arranjo em que o
ProteoWizard se apoia. Não existe hoje um leitor de `.wiff` inteiramente
livre de código do fabricante. Onde isso importa, converta os arquivos para
mzML com o msconvert e leia o mzML, o que este programa faz sem código
nenhum do fabricante.

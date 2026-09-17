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

## O que vem do fabricante e o que não vem

Totais, tempos de retenção e áreas integradas que a biblioteca do fabricante
reporta são usados como reportados: somar os pontos armazenados em vez disso
foi medido deslocando toda área integrada em 2%. Espectros em perfil voltam
com os pontos de intensidade zero que a biblioteca restaura na saída. Os
cromatogramas de íon extraído são a única coisa calculada aqui em vez de
pedida à biblioteca, e o único ponto em que as duas discordam — ver
[[formats]].

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

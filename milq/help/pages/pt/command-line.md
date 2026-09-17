---
title: Linha de comando
---
A aplicação instalada e a árvore de código respondem aos mesmos argumentos. A
partir da árvore de código o comando é `python3 run.py`; a partir de um
instalador é o executável dentro da aplicação — no macOS
`/Applications/MIL-Q.app/Contents/MacOS/MIL-Q`.

```
MIL-Q [files...] [--selftest] [--digest]
MIL-Q --infusion-report CAMINHO... --out ARQUIVO [--library ARQUIVO]
          [--components ARQUIVO] [--html] [--per-compound] [--csv ARQUIVO]
```

| Argumento | Efeito |
|---|---|
| `files` | arquivos de dados brutos a abrir — `.wiff`, `.mzML` — na janela, em lugar do prompt inicial |
| `--selftest` | abre os arquivos, relata o que foi lido, e sai sem janela |
| `--digest` | imprime uma impressão digital numérica de cada arquivo, para comparar uma build com outra, e sai |
| `--infusion-report` | relata todas as infusões diretas nos arquivos e pastas dados, e sai sem janela |
| `--out` | onde esse relatório é escrito; obrigatório com `--infusion-report` |
| `--library` | um MSP ou MGF seu, para buscar cada espectro médio contra ele |
| `--components` | um projeto (`.oqproj`) ou um CSV de componentes, para as fórmulas a partir das quais os compostos são explicados |
| `--html` | escreve o relatório como HTML em vez de PDF |
| `--per-compound` | um documento por composto, em vez de um com uma seção para cada |
| `--csv` | escreve também a tabela-resumo, uma linha por infusão |

## --selftest

Imprime a versão e a plataforma, se o índice do LIPID MAPS está instalado, se as
bibliotecas SCIEX estão prontas e onde o runtime .NET foi encontrado — ou por
que estão indisponíveis — e então, para cada arquivo, quantas amostras e canais
foram lidos, ou a exceção que o impediu. É o que os instaladores executam sobre
si mesmos antes de serem distribuídos, e a primeira coisa a executar quando um
arquivo não abre.

## --digest

Para cada arquivo, uma linha por canal com um hash curto de seu eixo de tempo e
de seu cromatograma total, uma por espectro amostrado, e uma por pico integrado
com sua área com nove casas decimais. Duas builds que leem o mesmo arquivo devem
imprimir uma saída idêntica byte a byte; o processo de lançamento compara a
build do macOS, a build do Windows e a árvore de código deste modo. A partir do
código no macOS, a partir da imagem de disco da CI e a partir do instalador do
Windows sob o CrossOver, cinco aquisições reais deram a mesma saída até o último
dígito. A build do Windows escreve terminações de linha CRLF, que é a única
diferença que o `diff` mostrará.

## --infusion-report

O [[infusion-report]] de uma pasta inteira, sem abrir nada no [[explorer]]:

```
MIL-Q --infusion-report ~/dados/acidos-biliares \
          --out ~/relatorios/acidos-biliares.pdf \
          --library ~/biblioteca/own-bileomics.msp \
          --components ~/metodos/acidos-biliares.csv \
          --csv ~/relatorios/acidos-biliares.csv
```

Um caminho pode ser uma pasta ou um único arquivo, e pode haver vários. A
pasta é examinada antes por [[checking-files]], de modo que um `.wiff` sem o
seu `.wiff.scan` é nomeado e **não é aberto** — seus espectros não podem ser
lidos e o relatório é um espectro — e um `.wiff2` ao lado dos dados é relatado
como ignorado em vez de lido. Cada arquivo restante é aberto sozinho e fechado
de novo antes do próximo, de modo que uma pasta de trinta infusões nunca
mantém trinta leitores. Uma corrida que não é uma infusão fica de fora com os
números que dizem por quê, nas palavras que [[direct-infusion]] usa.

Cada exclusão é impressa com o seu motivo, depois a mesma linha-resumo que a
aba Infusions mostra, depois o que foi escrito. O código de saída é 0 quando
ao menos um documento foi escrito e 1 caso contrário, de modo que um script
distingue uma pasta vazia de uma pasta relatada.

O documento **abre na pasta, e não no seu primeiro composto**: a capa diante
das páginas por composto nomeia a pasta, o dia e a versão, imprime cada
infusão em uma linha, soma essas linhas frase a frase, lista o que ficou de
fora e onde está cada composto — veja *A capa de um relatório de pasta* em
[[infusion-report]]. Ela está no mesmo PDF das páginas que apresenta.
`--per-compound` é a exceção: ali as páginas estão em um arquivo por
composto, então a capa é escrita sozinha como `<out>-cover`, e não lista
números de página porque não os tem.

Em uma máquina sem tela — um servidor de build, uma sessão por ssh — defina
`QT_QPA_PLATFORM=offscreen`: o documento é desenhado e paginado pelo Qt haja
ou não algo a mostrar. No Windows essa plataforma não encontra fonte
nenhuma por conta própria e desenhava cada glifo como um quadrado — um
relatório de 47 páginas sem texto algum — de modo que a aplicação a aponta
para a pasta de fontes do sistema (`QT_QPA_FONTDIR`), a menos que já
esteja definida.

Medido em nove infusões de ácidos biliares em um ZenoTOF, a partir do código
no macOS, com as três corridas CID como biblioteca própria e as três fórmulas
como CSV de componentes: **31 s** para a pasta inteira — nove arquivos lidos
e um PDF de 58 páginas escrito, duas de capa e 56 de seções — com **1,2 GB**
de pico de memória residente (duas execuções: 30,8 e 31,5 s, 1,42 e 1,40 GB;
medido de novo para [[integration]], 52 e 42 s a 1,15 e 1,21 GB),
e `--per-compound` quatro documentos das mesmas 58 páginas, duas
delas a capa e as outras 56 um documento por composto. Escritas sem capa, as
mesmas nove seções dão 56 páginas, de modo que a capa custa exatamente as
duas que ela é. Os segundos são o único número
aqui que não é do programa: a mesma execução sobre os mesmos arquivos já
levou de 27 s numa máquina ociosa a 255 s numa ocupada. O que é estável é o
que ela fez — nove arquivos lidos, nenhum excluído, 58 páginas — e o que ela
manteve na memória. Nada foi excluído:
todos os nove leem como infusões, inclusive as duas aquisições `_TESTEARTIGO`,
cujas linhas dizem o que há de errado com elas em vez de deixá-las de fora. A
linha-resumo é a da aba Infusions, dígito por dígito: *3 compound(s) in 9
infusion(s); 4 of 9 precursor(s) confirmed within 25 ppm; 34 of 458 predicted
ion(s) found across 7; 4 with an own record above 60*, e o parágrafo da capa
soma as mesmas linhas uma frase por vez — *4 of 9 precursor(s) confirmed
within 25 ppm; 5 not: 2 whose method isolates 839.56, 2 with too little
precursor surviving fragmentation, 1 at +30.3 ppm.* e mais duas como essa.

## O bootstrap

```
python3 -m milq.bootstrap --install
```

instala um runtime .NET 8 em `~/.dotnet` quando a máquina não tem nenhum, e
busca os assemblies de compatibilidade de que o Clearcore2 precisa. É necessário
uma vez, a partir do código; os instaladores carregam o que precisam. Veja
[[installation]] e [[how-wiff-is-read]].

## Programando a camada de dados

O leitor e a numérica funcionam sem a interface:

```
from milq import WiffFile

sample = WiffFile("run.wiff").sample(0)
channel = sample.channels[65]
rt, tic = channel.tic()
rt, xic = channel.xic(183.0137, tolerance=0.02)
mz, i = channel.spectrum(channel.scan_at_rt(13.14))
mz, i = channel.spectrum_rt_range(13.0, 13.3)
```

`milq.raw.open_raw(path)` devolve o leitor certo para qualquer um dos
formatos com a mesma superfície. `milq.quantify.process(entries, method)`
executa um método sobre um lote e devolve o conjunto de resultados;
`milq.report` escreve um relatório a partir de uma sessão;
`milq.compare.compare_algorithms` executa a comparação. A camada de química
— `milq.chemistry` — analisa fórmulas, calcula massas e padrões isotópicos
e busca composições, e não depende nem da interface nem das bibliotecas do
fornecedor.

Esses são os módulos em si, e eles podem mudar de lugar. Para uma superfície
que não muda — um lote reprocessado e exportado, um espectro explicado, uma
biblioteca buscada, um relatório escrito, em dez linhas e com uma promessa
de estabilidade — use a [[python-api]].

---
title: Linha de comando
---
O MIL-Q responde na linha de comando de duas maneiras. **`milq
<subcomando>`** é o contrato de linha de comando compartilhado da suíte —
os mesmos subcomandos, opções e saídas do `milx` do MIL-X, feito para
scripts e agentes, sem janela e sem Qt (roda por SSH e numa VM Linux
pequena). **`milq` sem subcomando** é a aplicação: abre a janela, ou roda um
dos seus próprios relatórios (`--selftest`, `--digest`,
`--infusion-report`). A partir da árvore de código o comando é `python3
run.py`; um `pip install .` coloca `milq` no caminho. No macOS e no Linux o
próprio executável da aplicação instalada também aceita os subcomandos
(`/Applications/MIL-Q.app/Contents/MacOS/MIL-Q info run.wiff`). No Windows
não os imprime: `MIL-Q.exe` é um programa com janela, a que o Windows não dá
saída de texto, e lá a linha de comando é `pip install` — ou `python run.py`
a partir do código.

## Os subcomandos do contrato

O contrato é `docs/CLI-CONTRACT.md` nos dois repositórios, idêntico byte a
byte; onde os dois programas diferem, vale o contrato. Em resumo:

```
milq selftest [FILES...]
milq info FILE [--sample N|NAME]
milq scans FILE [--source S] [--rt A:B] [--parent MZ[:TOL]] [--ms-level N] [--count]
milq xic FILE --mz LIST [--tol 0.01] [--unit Da|ppm] [--source S] [--rt A:B]
         [--smooth N] [--summary | --trace] [--reference MZ@SOURCE]
milq spectrum FILE [--source S] (--scan N | --rt A:B) [--subtract A:B]...
         [--centroid vendor|local|none] [--top N] [--min-rel 0.01] [--msp PATH]
milq isotopes FILE --mz MZ [--charge Z] --rt A:B [--formula F] [--adduct A]
milq batch-xic PATHS... --mz LIST [--tol] [--unit] [--source] [--rt-window C±W]
milq convert FILE [--out PATH] [--centroid vendor|local]
milq serve (--stdio | --inbox DIR) [--allow-root DIR]... [--idle-exit MIN]
```

`milq peptide …` — massas, fragmentos, anotação, digestão e uma
triagem alvo–isca de peptídeos — tem a sua própria página: [[peptides]].

Todo subcomando aceita também `--format json|tsv` (JSON por padrão; TSV é a
tabela principal do documento), `--quiet` (nada no stderr além de erros),
`--cache DIR` (onde fica o índice auxiliar) e `--require` (sai com 4 quando
nada é encontrado).

Uma **fonte** diz quais scans são lidos: `ms1` (o survey), `channel:N`,
`ms2-all` (todos os scans de íons-produto, unidos pelo tempo), ou
`gated:MZ[:TOL]` — só os scans de íons-produto cujo próprio precursor está a
até TOL (0.05 Da por padrão) de MZ, de todos os canais. O filtro é o que os
dados dependentes de dados precisam: ver [[how-wiff-is-read]] e
[[manual-xic]].

Todo documento JSON começa com `schema` (`mil-cli/1`), `tool`, `version`,
`command` e `input` (o caminho absoluto e a amostra). Massas vêm com 4
casas (6 para valores teóricos), tempos de retenção em minutos com 4,
intensidades como o leitor as informa, sempre com ponto decimal. A mesma
chamada dá os mesmos bytes. Um erro é um documento JSON no stderr,
`{"schema": "mil-cli/1", "error": "...", "message": "..."}`, e um código de
saída: **2** argumentos inválidos, **3** um arquivo que não pode ser lido ou
um `.wiff` sem o seu `.wiff.scan`, **4** nada encontrado (só com
`--require`; um resultado vazio não é, de outro modo, um erro), **5** um
erro interno.

### O que cada um responde

| Subcomando | Responde |
|---|---|
| `selftest` | a plataforma, se as bibliotecas da SCIEX carregam, e para cada arquivo se ele abre e se um espectro é lido |
| `info` | as amostras, e cada canal: índice, tipo (`ms1`, `ida-slot`, `dda-events`, `swath`, `mrm`, `product`), rótulo, scans, faixa de massas, precursor (nenhum para um slot IDA), largura de isolamento, energia de colisão, polaridade |
| `scans` | uma linha por scan: canal, scan, ciclo, TR, nível de MS, **o precursor que aquele scan isolou**, a sua janela de isolamento, CE, TIC, pontos; `--count` dá contagens por canal |
| `xic` | por m/z: o ápice (o ponto mais alto do traço) com o seu TR e altura, os limites (para fora até o primeiro ponto a 5% do ápice ou abaixo, ou até o vale antes de uma subida de um décimo dele), a área entre eles (trapézio, sem linha de base), FWHM, pontos no pico, e S/N com a convenção de ruído nomeada — as definições vão impressas no documento e são as do MIL-X; com `--reference`, o r de Pearson sobre a extensão do pico de referência, o ΔTR dos ápices e a razão de alturas |
| `spectrum` | a lista de picos (m/z, intensidade, % da base) e cada scan de que foi feita, com o seu precursor; `--subtract` retira a média de janelas de fundo; `--msp` escreve também um registro MSP |
| `isotopes` | M, M+1, M+2… medidos ao lado das massas esperadas, o erro de espaçamento, e as abundâncias esperadas quando `--formula` é dada |
| `batch-xic` | uma linha por arquivo, amostra e m/z — como se verificam brancos e a distribuição de um composto num lote; arquivos e pastas, com cada arquivo deixado de fora (um `.wiff` sem `.wiff.scan`, um `.scan` solto) listado em `skipped` |
| `convert` | um mzML que mantém o precursor de cada scan — `scans` nele dá os mesmos precursores |

### Exemplos, medidos

Numa corrida IDA HILIC de TripleTOF 5600 (um survey, oito slots
dependentes, 1.986 ciclos):

```
$ milq scans run.wiff --source gated:707.22 --format tsv | head -2
channel  scan  cycle  rt      ms_level  parent_mz  isolation          ce    tic       points
5        160   160    1.137   2         707.2197   706.7197;707.7197  35.0  656159.0  4447
```

Quinze scans em quatro slots diferentes isolaram 707.22 ao longo da corrida.

```
$ milq xic run.wiff --mz 707.22 --tol 0.02 --reference 365.104@gated:707.22
"summary": [{"mz": 707.22, "found": true, "apex_rt": 1.3425,
  "apex_height": 3946742.86, "fwhm": 0.1419, "points_across_peak": 7,
  "sn": 19915.11, "vs_reference": {"pearson_r": 0.8695,
  "apex_delta_rt": -0.0339, "height_ratio": 14.774225}}]
```

— o precursor no survey contra o seu fragmento mais forte lido dos scans que
o isolaram.

```
$ milq isotopes run.wiff --mz 707.22 --rt 0:20 --tol 0.02
M 707.2208 100 · M+1 708.2259 23.7 · M+2 709.2254 7.3 · M+3 710.2287 1.5
```

### Quanto custa uma chamada

A primeira chamada sobre um arquivo lê os seus cabeçalhos e, para `scans`,
o número de pontos de cada scan; os dois vão para um **índice auxiliar**
indexado pelo caminho, tamanho e data de modificação do arquivo (e do seu
`.wiff.scan`), de modo que um arquivo editado nunca é respondido com uma
entrada velha. Medido aqui: `scans` no `.wiff` IDA 3.8 s a frio, 1.3–1.8 s
a quente; `info` no seu mzML de 70 MB 1.4 s a frio, 0.5 s a quente. Cerca de
um segundo de cada chamada sobre `.wiff` é a partida do .NET, que é o que o
`serve` economiza. O índice fica em `index/` no cache da aplicação, ou onde
`--cache` ou `MILQ_INDEX_DIR` disserem; apagá-lo é seguro.

## serve: rodar comandos no Mac a partir de outro lugar

Um agente trabalhando numa VM Linux vê as pastas compartilhadas mas não
consegue digitar num terminal do macOS, e no Linux as bibliotecas da SCIEX
podem nem ler um `.wiff`. Então o Mac roda os trabalhos: inicie isto uma vez
num Terminal do Mac —

```
milq serve --inbox ~/Documents/mil-jobs --allow-root ~/Documents/MIL-data
```

— e ele vigia `~/Documents/mil-jobs/inbox/`. Um pedido é um arquivo,
`inbox/<id>.json`, escrito inteiro (como `<id>.json.tmp`, depois
renomeado):

```
{"schema": "mil-cli/1", "id": "0001", "command": "xic",
 "args": {"file": "/Users/me/Documents/MIL-data/run.wiff",
          "mz": [627.8457], "tol": 0.01, "source": "gated:627.8457"},
 "format": "json"}
```

A resposta é `outbox/0001.json`, byte a byte o que `milq xic …` imprimiria,
e o pedido vai para `outbox/0001.request.json`; um pedido que falhou vai
para `failed/` com o seu documento de erro. `"batch": [ … ]` roda vários em
ordem num só arquivo. Um `--trace`, um MSP ou um TSV é escrito em
`outbox/<id>/` e listado na resposta.

É uma lista de permissões, não um shell: só os subcomandos acima e
`peptide …` rodam, dentro do próprio processo do servidor — sem shell, sem
subprocesso. Todo caminho que um pedido nomeia precisa estar (links
seguidos) dentro de um `--allow-root` ou da pasta da caixa de entrada
(`path_outside_roots` caso contrário), e nada fora de `outbox/` é
sobrescrito. Um trabalho roda de cada vez; um trabalho que passa do seu
`timeout_s` (1.800 s por padrão) é respondido com `timeout` e abandonado.
`STATUS.json` diz o que está rodando e o tamanho da fila; `log.jsonl` tem
uma linha por trabalho (id, comando, argumentos, início, fim, resultado,
saídas, memória máxima) e nunca o conteúdo de arquivos. Crie `STOP` na
pasta, pressione Ctrl-C, ou inicie com `--idle-exit MIN` para encerrá-lo
depois do trabalho atual; um trabalho encontrado em `running/` ao iniciar
foi interrompido e vai para `failed/`. Os arquivos ficam abertos entre os
trabalhos (até quatro de uma vez), o que torna rápido o segundo pedido sobre
um arquivo.

`milq serve --stdio` faz o mesmo por um pipe: um pedido JSON por linha de
entrada, um documento por linha de saída.

### Iniciá-lo no login (opcional)

`packaging/macos/io.github.pedronobrez.milq-serve.plist` é um agente do
`launchd` que inicia o servidor no login. Edite nele as duas pastas e o
caminho para `milq` (`which milq` o imprime), depois:

```
cp packaging/macos/io.github.pedronobrez.milq-serve.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/io.github.pedronobrez.milq-serve.plist
```

`launchctl unload` com o mesmo caminho o para. Nada precisa disso: o
comando no Terminal acima é tudo o que se exige.

### No Linux

No Ubuntu 22.04 (arm64 ou x86-64), como usuário comum:

```
python3 -m pip install --user --upgrade pip setuptools
python3 -m pip install --user numpy pythonnet certifi
python3 -m pip install --user --no-deps alpharaw
python3 -m pip install --user --no-deps .
python3 -m milq.bootstrap --install
milq selftest run.wiff
```

A primeira linha importa: o pip e o setuptools do próprio Ubuntu instalam
este pacote como `UNKNOWN-0.0.0`. O `alpharaw` entra com `--no-deps` porque
carrega os assemblies da SCIEX e declara leitores que este programa nunca
importa; `pip install .[cli]` lista os mesmos quatro. O bootstrap coloca o
.NET 8 em `~/.dotnet` sem sudo. Medido no Ubuntu 22.04 arm64 com 3 GB: o
`.wiff` é lido, com os mesmos números do macOS — ver [[measured-facts]].
Onde o `selftest` disser que não, a rota do mzML é completa: `milq convert`
no Mac, e depois todos os subcomandos no mzML.

## Os argumentos da própria aplicação

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

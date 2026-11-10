---
title: Variáveis de ambiente
---
Algumas variáveis de ambiente mudam o que a aplicação faz sem um ajuste em
um diálogo. Elas são lidas quando o programa começa, então defina-as antes
de abri-lo — num terminal com `export NOME=valor`, ou, para a aplicação
instalada no macOS, com `launchctl setenv NOME valor` antes de abri-la pelo
Dock. Todo `OPENQUANT_X` do nome anterior do programa ainda é lido como
`MILQ_X` onde o novo não está definido.

| Variável | Valores | O que faz |
|---|---|---|
| `MILQ_WIFF_CENTROID` | `local` (padrão), `sciex`, `0` | Quem centroida um espectro de `.wiff` para rótulos, Explain, busca em biblioteca e registro de biblioteca: este programa, ou o próprio localizador de picos da SCIEX. `0` desliga o do fabricante como `local` — é o nome que o MIL-X usa para a mesma chave. Um mzML é sempre centroidado por este programa. |
| `MILQ_CACHE_DIR` | uma pasta | Onde ficam os espectros médios de arquivos inalterados quando não há projeto aberto. |
| `MILQ_HOME` | uma pasta | Onde ficam o runtime .NET e o índice do LIPID MAPS (padrão `~/.milq`, ou `~/.openquant` onde esta já existe). |
| `MILQ_SETTINGS` | um arquivo | Um arquivo INI usado para as preferências no lugar do armazenamento do sistema — o que a suíte de testes usa para nunca escrever nas preferências de uma pessoa. |
| `MILQ_REAL_DATA` | `1` | Roda os testes de `tests/real/`, que precisam de aquisições que nunca estão no repositório. |
| `MILQ_TEST_WIFF` | um `.wiff` | A aquisição IDA real que esses testes e o teste do contrato de linha de comando leem. |
| `MILQ_OPEN` | um `.oqproj` | Abre este projeto ao iniciar. |
| `MILQ_OPEN_RAW` | um arquivo bruto ou uma pasta | Abre este arquivo, ou todo `.wiff` e `.mzML` desta pasta, ao iniciar, e mostra o Explorer. |
| `MILQ_SNAPSHOT` | um `.png` | Grava a janela nesta imagem depois de `MILQ_SNAPSHOT_DELAY` segundos (padrão 10), no espaço de trabalho `MILQ_SNAPSHOT_TAB` (0–3, ou `explorer`, `analytics`, `method`, `samples`), e fecha — a menos que haja uma sonda rodando. |
| `MILQ_UI_PROBE` | um `.json` | Escreve o que a janela mostra neste arquivo sempre que muda, e executa os comandos encontrados em `<arquivo>.commands` (abaixo). |

## Comandando a janela por um script

Um agente — ou qualquer script — não deveria ter de comandar a janela
clicando em coordenadas lidas de uma captura de tela. Com
`MILQ_UI_PROBE=/tmp/probe.json` a janela escreve, sempre que algo muda, um
documento JSON do que está mostrando: o espaço de trabalho, o projeto e se
está salvo, cada amostra aberta (chave, nome, caminho, canais, algum
problema), o canal ativo (chave, rótulo, tipo e precursor), os canais
marcados, os cromatogramas de íon extraído, o intervalo de tempo do
cromatograma, o título do espectro, a linha de status e o resultado do
último comando.

Os comandos vão em `/tmp/probe.json.commands`: um objeto JSON, ou uma lista
deles, cada um com um `id` e uma `action`. A janela lê o arquivo em meio
segundo, apaga-o, executa cada comando pelo mesmo código que os seus menus e
botões usam, e escreve a resposta na sonda como `last_command`:
`{id, action, ok, message, completed_at}`. Um comando que não pode ser
feito é respondido com `ok: false` e o motivo; nunca para a janela. Escreva
o arquivo inteiro (um nome temporário, depois renomeie) para que nunca seja
lido pela metade.

| Ação | Campos | Faz |
|---|---|---|
| `select-workspace` | `name` (explorer, analytics, method, samples) ou índice | mostra esse espaço de trabalho |
| `open-file` | `path` | abre um arquivo bruto, ou um projeto |
| `select-channel` | `sample` (chave, nome ou índice), `channel` (índice; omita para o TIC da amostra) | marca-o e o torna ativo |
| `add-xic` | `mz` (uma lista ou `"a, b"`), `tol`, `unit` (Da, ppm), `source` (`channel`, `ms1`, `ms2-all`, `gated:MZ[:TOL]`) | extrai como a aba Manual XIC — ver [[manual-xic]] |
| `clear-xics` | | remove-os |
| `set-rt-range` | `start`, `end` (minutos) | o intervalo de tempo do cromatograma |
| `show-scan` | `scan` (a partir de 0) | esse scan do canal ativo |
| `average` | `start`, `end` | o canal ativo com a média nesse intervalo |
| `export-chart` | `path`, `chart` (chromatogram, spectrum, contour), `format`, `scale`, `theme`, `background`, `type_size` | grava o gráfico como **Export as a picture…** gravaria — ver [[export]] |
| `save-project` | `path` (opcional quando o projeto já tem um) | salva-o |

Por exemplo, para abrir uma corrida, ler os scans de produto de um
precursor em todos os slots IDA, e guardar a imagem:

```
[{"id": "1", "action": "open-file", "path": "/data/run.wiff"},
 {"id": "2", "action": "select-channel", "sample": 0, "channel": 1},
 {"id": "3", "action": "add-xic", "mz": [136.0757], "tol": 0.01,
  "unit": "Da", "source": "gated:627.8457:0.05"},
 {"id": "4", "action": "export-chart", "path": "/tmp/xic.svg",
  "chart": "chromatogram", "theme": "light"}]
```

São o `MILX_UI_PROBE`, `MILX_OPEN`, `MILX_OPEN_RAW` e `MILX_SNAPSHOT*` do
MIL-X, com o mesmo protocolo de arquivo de comandos. Para trabalho que não
precisa de janela nenhuma, a linha de comando custa menos — ver
[[command-line]].

## Quem centroida um espectro de `.wiff`

Um espectro de perfil precisa virar centroides — um traço por íon — antes
de se buscar uma biblioteca com ele, pontuar uma estrutura contra ele ou
escrever um registro a partir dele, e antes de um rótulo dizer uma massa.
Para um `.wiff` o software do instrumento sabe fazer isso: o localizador de
picos espectrais do Clearcore2 (`MSExperiment.GetPeakArray`) ajusta cada
pico de perfil e informa o seu ápice, para um scan ou para a média de um
intervalo de tempo. A regra do MIL-Q é usar a aritmética do instrumento
onde o instrumento a oferece, e a 1.1 foi escrita primeiro com o fabricante
como padrão. Depois foi medida, e perdeu (abaixo), por isso **o
centroidizador deste programa é o padrão** e o do fabricante é uma
escolha: com `MILQ_WIFF_CENTROID=sciex` o rótulo de um pico é o ápice do
fabricante para o pico em que está, **Centroid** desenha os traços do
fabricante, e o Explain, a biblioteca e um registro os usam. Na linha de
comando, `--centroid vendor` os pede para uma chamada.

O do fabricante é usado só quando o espectro na tela é o próprio do leitor: um espectro
com fundo subtraído, uma diferença da média da corrida ou a média de uma
infusão inteira com a máscara do spray é centroidada por este programa,
porque o fabricante nunca a viu.

O que foi medido que ele muda, nesta máquina:

- **Massas dos rótulos.** Em dezessete scans de survey de uma corrida de
  TripleTOF 5600, todos os rótulos mudaram, por uma mediana de 1.5 ppm
  (percentil 90 de 4.1, no máximo 11.8).
- **Número de picos.** Um scan de survey: 4.561 picos do fabricante contra
  13.764 máximos locais, nas mesmas alturas (razão mediana 1.00 nos 200 mais
  altos — o MIL-X mediu o fabricante 1.27 vez mais alto num ZenoTOF 7600, de
  modo que quem decide é o instrumento, não a regra).
- **A busca em biblioteca piorou num lote.** Num lote de íons-produto de
  esfingolipídios, os mesmos fragmentos medidos em duas injeções diferiram
  por uma mediana de 7.0 ppm centroidados aqui e 10.5 ppm pelo fabricante
  (83% e 73% dentro da tolerância de busca de 20 ppm), e um registro escrito
  a partir da injeção 01 foi encontrado em primeiro lugar para a injeção 02
  em 16 de 20 canais centroidados aqui contra 9 de 20 pelo fabricante — e
  é por isso que ele não é o padrão. A triagem de peptídeos
  ([[peptides]]) foi no sentido contrário numa aquisição IDA real: um pouco
  mais de peptídeos aceitos a 1% de FDR com os centroides do fabricante, o
  peptídeo de validação encontrado nos dois casos.
  `MILQ_WIFF_CENTROID=local` é o que roda quando nada está definido.

A quantificação lê cromatogramas de íon extraído e não é tocada por nada
disso. Ver [[spectral-library]] e [[how-wiff-is-read]].

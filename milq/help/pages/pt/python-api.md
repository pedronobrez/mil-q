---
title: API Python
---
Tudo o que a aplicação faz pode ser feito a partir de um script.
`milq.api` é uma superfície pequena sobre os módulos que estão abaixo
dela: abrir um arquivo, quantificar um lote, explicar um espectro, buscar em
uma biblioteca, escrever um relatório — sem janela, e sem precisar saber que
a sessão é um objeto Qt ou que os leitores são diferentes entre si.

```
from milq import api
```

É a única parte do pacote com uma promessa de estabilidade. **Os nomes em
`api.__all__`, seus métodos e os nomes de seus argumentos nomeados**
continuarão existindo e continuarão significando o que significam; as
dataclasses devolvidas mantêm os nomes de seus campos e ganham campos em vez
de perdê-los. `api.VERSION` é a versão dessa promessa — 1 — e só sobe quando
ela é quebrada. Tudo o que está abaixo (`milq.quantify`,
`milq.session`, `milq.report`, os leitores) é interno e pode
mudar de lugar. A saída de emergência é deliberada: `Batch.session`,
`Acquisition.sample` e `Acquisition.file` devolvem os objetos de baixo, e
usá-los é abrir mão da promessa acima.

Nada aqui recebe ou devolve um objeto Qt, exceto `headless()`. O que volta
são dataclasses simples e arrays numpy.

## O que há nela

| | |
|---|---|
| `api.open(path)` | uma amostra de um `.wiff` ou de um `.mzML`: `samples`, `channels`, `tic()`, `spectrum(scan)`, `average(rt0, rt1)`, `xic(mz)`, `is_infusion`, `infusion_average()` |
| `api.Batch` | `from_project(path)`, ou arquivos e uma tabela de componentes; depois `process()`, `results`, `calibrate()`, `statistics()`, `export_xlsx()`, `report()`, `save_project()` |
| `api.explain(spectrum, …)` | o que uma fórmula, um nome ou um molfile explica de um espectro |
| `api.Library` | `open(msp)`, `search(spectrum)`, `add(spectrum, name)` |
| `api.infusion_report(source, out)` | o documento de infusão direta de um arquivo, de uma pasta ou de uma amostra |
| `api.headless()` | a aplicação Qt fora da tela com que o relatório e o documento são desenhados |

Os resultados voltam de três formas: como linhas (`results.rows`, cada uma
uma dataclass `Result`), como dicionários (`results.dicts()`) e como uma
tabela de valores simples (`results.table()`) com `columns` e `rows` — que é
o que `pandas.DataFrame(table.rows, columns=table.columns)` recebe, sem que
este pacote dependa do pandas.

## Uma pasta de infusões, explicada e arquivada

Abrir cada aquisição de uma pasta, ficar com as que se leem como infusão
direta, explicar cada uma a partir do próprio nome e escrever um registro de
cada uma em uma biblioteca sua.

```python
from pathlib import Path
from milq import api

library = api.Library.open("bile-acids.msp", create=True)
for path in sorted(Path("/Volumes/NOBRE/Cyborg/Bileomics").glob("*.wiff")):
    with api.open(path) as run:
        if not run.is_infusion:
            continue
        spectrum = run.infusion_average()
        said = api.explain(spectrum, name=run.compound)
        library.add(spectrum, name=run.name, formula=said.formula,
                    adduct=said.adduct)
        print(f"{run.compound:8} {said.matched:3d}/{said.predicted:<4d} ions, "
              f"{said.share:.0%} of the spectrum — {said.basis or said.note}")
print(len(library), "records written to", library.path)
```

Medido em nove infusões de ácidos biliares em um ZenoTOF: **1 min 39 s**
lendo os arquivos de um disco externo pela primeira vez, **23 s** com os
mesmos arquivos em cache. Nove registros escritos. Duas das nove não
explicam nada, e dizem por quê — esses dois arquivos miram 839,56, que não é nenhum
aduto do composto que o nome deles afirma (veja [[measured-facts]]):

```
CA-d4      0/0    ions, 0% of the spectrum — 839.56 is none of the adducts of C24H36D4O5 within ±0.05 Da — closest [M+K]+ at 451.2758 (+388.2842 Da), [M+Na]+ at 435.3019 (+404.2581 Da)
CA-d4     15/882  ions, 71% of the spectrum — C24H36D4O5 as [M+NH4]+ (read off the precursor — 430.34 is [M+NH4]+ of C24H36D4O5 (430.3465, -15.1 ppm); [M+H]+ would be 413.3200), predicted from its structure, named from the standards table
TDCA-d4   12/2241 ions, 87% of the spectrum — C26H41D4NO6S as [M+H]+ (read off the precursor — 504.32 is [M+H]+ of C26H41D4NO6S (504.3291, -18.1 ppm); [M+NH4]+ would be 521.3557), predicted from its structure, named from the standards table
```

Três coisas que o script não precisa dizer. `run.compound` é a parte do nome
do arquivo antes do primeiro sublinhado, que é como esses arquivos são
nomeados e por onde o [[infusion-report]] agrupa; `explain` resolve esse nome
pela tabela de padrões, pelo LIPID MAPS e pela notação abreviada de
lipídios, lê `-d4` como quatro marcações que o nome não posiciona, e escolhe
o aduto a partir do precursor escrito no próprio canal. E o espectro é
centroidizado antes de virar um registro, porque um registro feito de pontos
de perfil descreve a forma de pico do instrumento e não o composto — veja
[[spectral-library]].

## Um projeto, reprocessado e exportado

```python
from milq import api

batch = api.Batch.from_project("Sphingolipids-reprocessado.oqproj")
rows = batch.process()
print(f"{len(batch.samples)} injections, {len(batch.components)} components, "
      f"{len(rows)} rows, {len(rows.found)} with a peak, "
      f"{len(batch.calibrate())} curves fitted")
rows.table().to_csv("sphingolipids.csv")
batch.export_xlsx("sphingolipids.xlsx")
batch.report("sphingolipids.pdf")
batch.close()
```

Medido no lote de esfingolipídios de 26 injeções — 141 componentes, com os
`.wiff` em disco local: **3 min 3 s** para o script inteiro com os arquivos
lidos a frio, **26 s** com eles em cache. Imprimiu

```
26 injections, 141 components, 3666 rows, 2638 with a peak, 0 curves fitted
```

e escreveu um CSV de 678 KB, uma pasta de trabalho de 408 KB e um PDF de 180
páginas.
Nenhuma curva porque nenhuma injeção desse lote está marcada como padrão:
`calibrate()` ajusta a partir das amostras que o projeto chama de padrões e
não relata nada quando não há nenhuma. `report()` desenha através do Qt e
cria a aplicação fora da tela sozinho, de modo que um script simples não
precisa de `headless()`; mantenha uma aberta à mão quando um script escrever
vários documentos, ou quiser o Qt para algo próprio. No Windows a
plataforma fora da tela recebe as fontes do sistema (`QT_QPA_FONTDIR`, a
menos que já esteja definida), porque sozinha não tem nenhuma e um
relatório saiu com quadrados onde deviam estar as palavras.

## Um espectro contra uma biblioteca

```python
from milq import api

library = api.Library.open("bile-acids.msp")
with api.open("/Volumes/NOBRE/Cyborg/Bileomics/CA-d4_TOFMSMS_Mix1.wiff") as run:
    spectrum = run.infusion_average()
print(f"{run.compound}, precursor {spectrum.precursor}, "
      f"{len(library)} records searched")
for hit in library.search(spectrum, top=5):
    print(f"  {hit.score:5.2f} {hit.reverse:5.2f} {hit.matched:3d} of "
          f"{hit.of_library:3d}  {hit.name}")
```

**12 s** a frio e **1,9 s** com cache contra os nove registros que o
primeiro script escreveu, dos quais o filtro de precursor admite três:

```
CA-d4, precursor 430.35, 9 records searched
   1.00  1.00 200 of 200  CA-d4_TOFMSMS_Mix1
   0.29  0.56  22 of  42  CA-d4_TOFMSMS_EAD_22CE_44DP_13KE_mix1
   0.06  0.29   8 of  12  CA-d4_TOFMSMS_EAD_12CE_44DP_13KE_mix1
```

O próprio registro pontua 1,00, como tem de ser. Os outros dois são o mesmo
frasco sob outras ativações, e pontuam 0,29 e 0,06: **um registro não viaja
entre energias de colisão**, que é a mesma constatação sobre a qual o
[[standard-history]] foi construído. A mesma chamada aceita um MSP de
qualquer tamanho: a exportação completa do MassBank, 139.006 registros, é
lida em cerca de cinco segundos e buscada em milissegundos assim que o filtro
de precursor se aplica — medido para a [[spectral-library]], que é o mesmo
código que esta chamada usa.

`search` toma o precursor e a polaridade do próprio espectro, e sua
tolerância assume por padrão a precisão com que o precursor foi escrito: um
canal que diz `647.5` não é conhecido com três casas decimais. Passe
`precursor`, `polarity` ou `precursor_tolerance` para sobrepor qualquer uma
dessas escolhas.

## O documento de infusão a partir de um script

```
doc = api.infusion_report("/Volumes/NOBRE/Cyborg/Bileomics", "infusions.pdf")
```

Cada amostra do arquivo ou da pasta que se lê como infusão direta vira uma
seção — o espectro médio, o precursor exato, a explicação e o melhor
registro de uma `library=` que você passe — e o que volta é uma
`InfusionLine` por seção, de modo que os números podem ser lidos sem abrir o
PDF. Medido: 13,7 s para uma infusão com biblioteca, 202 s para as nove.
Nada que se leia como cromatografia entra, e uma origem sem nenhuma infusão
levanta um erro em vez de escrever um documento vazio. Veja
[[infusion-report]] e [[direct-infusion]].

## De onde vêm os números

Nada aqui é uma segunda implementação. `process()` executa exatamente o que
o [[analytics-workspace]] executa, `report()` escreve exatamente o que
[[report|o relatório]] escreve, e os leitores são os descritos em
[[how-wiff-is-read]]. Tudo o que está em [[measured-facts]] é tão verdadeiro
por um script quanto pela janela — inclusive a única diferença entre
formatos, que é a razão de uma série ser quantificada em um só deles.

Veja também a [[command-line]] para o que a aplicação faz sem script nenhum.

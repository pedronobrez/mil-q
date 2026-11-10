---
title: Peptídeos na linha de comando
---
`milq peptide …` é um conjunto de ferramentas para peptídeos sem janela:
massas, fragmentos, a anotação de um espectro, uma digestão não específica,
e uma triagem de todos os scans MS2 dependentes de dados de um lote com taxa
de falsas descobertas por alvo–isca. Foi escrito para peptídeos endógenos em
dados IDA HILIC ESI+, e nada nele é específico de um tipo de amostra ou de
uma proteína. Toda saída segue o contrato de
[[command-line]]: um documento `mil-cli/1` em JSON, ou `--format tsv`. Toda
massa é monoisotópica.

## Escrevendo uma sequência

| Escrito | Significa |
|---|---|
| `QPLAPVHNPISV` | os resíduos; I e L são isobáricos (113.084064) e são informados assim |
| `pEPLAPVHNPISV`, `pE-PLAPVHNPISV` | `pE` é um resíduo de piroglutamato (111.032028, de Q ou E igualmente) |
| `[pyroGlu]QPLAPVHNPISV`, `pGlu-QPLAPVHNPISV` | pyroGlu no Q N-terminal (−17.026549) ou E (−18.010565) |
| `S[Phospho]` | em S, T ou Y, +79.966331 |
| `M[Oxidation]` | +15.994915 |
| `…V[Amidated]` | amida C-terminal, −0.984016 |
| `[Acetyl]-PEPTIDE` | acetil N-terminal, +42.010565 |

## Os subcomandos

| Subcomando | O que dá |
|---|---|
| `peptide mass SEQ` | a massa monoisotópica e o m/z nas cargas 1–4 (`--charges`) |
| `peptide fragments SEQ` | íons b, a e y, b−H2O e y−NH3, íons internos do tipo b e íons imônio, nas cargas 1–3, cada um nomeado (`b3`, `y5+` para 2+, `int-PLA`, `imm-H`) |
| `peptide annotate SPECTRUM --seq SEQ --charge Z --tol-ppm 20` | cada íon casado com o seu erro em ppm, um mapa de cobertura (`b`, `y` ou `|` para ambos, `.` para nenhum, entre cada par de resíduos), a fração da intensidade explicada, e os picos mais altos sem explicação. O espectro é um TSV de m/z e intensidade, um MSP, ou um JSON de `milq spectrum` — ou `--from FILE --source gated:MZ --rt A:B` o lê do próprio arquivo bruto |
| `peptide digest FASTA --proteins ACC,… --nonspecific --len 4:40 --mods pyroglu-q,phospho-st,ox-m --max-mods 3 --charges 1-4` | toda subsequência das proteínas com toda forma modificada que as opções permitem, com o m/z por carga |
| `peptide screen FILES… --fasta F --proteins ACC,… [opções da digestão] --ppm 15 --decoy reverse` | a triagem, abaixo |
| `peptide components SCREEN.tsv --out COMPONENTS.csv` | os peptídeos aceitos como tabela de componentes para [[method-workspace|o método]] |

As modificações da digestão são `pyroglu-q`, `pyroglu-e`, `phospho-st`,
`phospho-sty`, `ox-m`, `amidated` e `acetyl`.

## A triagem

Para cada scan MS2 de cada arquivo, o precursor que aquele scan isolou — o
seu, scan a scan, que é o que [[how-wiff-is-read|um slot IDA]] carrega — é
refinado a partir do scan de survey naquele tempo, e casado contra a
digestão dentro de `--ppm` na carga informada (ou 1–4 onde o arquivo não
informa nenhuma), com erros isotópicos de −1, 0 e +1 permitidos, porque o
instrumento às vezes escolhe o pico do 13C. Cada candidato é pontuado nos
centroides do scan (os deste programa, ou do localizador de picos da SCIEX com `MILQ_WIFF_CENTROID=sciex`, ver
[[environment-variables]]): íons b, y, a, b−H2O e y−NH3 dentro de
`--fragment-ppm` (20), a fração da intensidade que explicam, a maior
sequência de íons b ou y consecutivos, e um hyperscore à maneira do
X!Tandem (o log da intensidade b e y casada mais o log dos fatoriais das
suas contagens). Um candidato precisa de `--min-matched` (4) íons. O melhor
candidato de cada scan é mantido, alvo ou isca; as iscas são as proteínas
invertidas e digeridas do mesmo modo, e o valor q é a menor razão
isca/alvo no escore ou abaixo dele.

Ela escreve três arquivos junto a `--out PREFIXO`: `PREFIXO.tsv`, uma linha
por peptídeo e carga ordenada por valor q (peptídeo, modificações,
proteína, início–fim, carga, m/z, TR, ppm, erro isotópico, íons casados,
maior série, fração explicada, escore, valor q, número de scans, arquivos, e
o fragmento mais forte); `PREFIXO.json`, o resumo; e `PREFIXO.msp`, o melhor
espectro de cada peptídeo aceito — utilizável como biblioteca na
[[spectral-library]] do próprio MIL-Q, no MIL-X e no MS-DIAL. `peptide
components` transforma o TSV em componentes (o precursor na sua carga, o
fragmento mais forte, o tempo de retenção) para que um lote seja
quantificado pelo caminho comum.

## O que foi medido

Numa aquisição IDA HILIC ESI+ real de TripleTOF 5600, triando uma proteína de
forma não específica de 4 a 40 resíduos com pyroGlu-Q, fosfo-S/T e oxidação
de Met, até três por peptídeo: 2.364 scans MS2 contra 72.406 candidatos alvo
e as suas iscas em 11 s; em quatro aquisições assim, 10.180 scans em 44 s com
450 MB. O peptídeo que a triagem devia validar foi encontrado com q < 0,01 em
todas elas, com os centroides deste programa e com os da SCIEX (os do
fabricante levaram 75 s e aceitaram um pouco mais de peptídeos a 1%). O
escore não foi ajustado nele; o teste em `tests/real/` que o verifica lê o
peptídeo, a proteína e os arquivos de um arquivo local não versionado,
porque as aquisições são de outras pessoas.

O que significa uma busca de uma proteína só: a FDR é a taxa de falsas
descobertas entre os casamentos com os peptídeos daquela proteína, contra a
sua própria inversão — diz quais espectros são peptídeos daquela proteína e não
acaso, não que nada mais na amostra os explique melhor. Busque no proteoma,
ou nas proteínas que a amostra pode conter juntas, antes de afirmar que um
peptídeo é único.

---
title: Exportar para Excel e Skyline
---
Toda tabela da aplicação se exporta como CSV, um arquivo por vez. Duas
exportações vão além: o lote inteiro como uma pasta de trabalho Excel, e o
método como uma lista de transições que outro programa consegue importar.
Nenhuma das duas substitui [[report|the batch report]] (o relatório do lote)
— um relatório é o que se guarda, uma pasta de trabalho é aquilo em que se
continua a trabalhar.

## A pasta de trabalho

**File ▸ Export workbook (Excel)…** escreve um único `.xlsx` com uma planilha
por seção. Só são escritas as seções que têm algo dentro, de modo que um
projeto que é um método e nada mais dá duas planilhas em vez de seis, quatro
delas vazias.

| Planilha | Contém |
|---|---|
| Results | cada linha integrada: amostra, tipo e grupo, componente, canal, m/z, RT e RT esperado, área, altura, largura, S/N, pontos, algoritmo, padrão interno, razão, concentração, exatidão, status, se foi usada ou integrada à mão, as suas marcações e a sua nota — as colunas da [[results-table]], sem nada movido para uma nota de rodapé |
| Calibration | por componente: modelo, ponderação, equação, inclinação, intercepto, r², r, pontos usados de pontos — ver [[calibration]] |
| Statistics | as médias agrupadas, os desvios-padrão e os %CV da página [[statistics]], por tipo de amostra |
| Batch QC | uma linha por carta de controle: centro, dispersão, S/N, piso, deriva, ρ, quantas injeções ficaram fora dos seus limites, e os vereditos de [[batch-qc]] — o índice de resposta entre eles |
| Method | a tabela de componentes da [[method-workspace]], todas as colunas |
| Samples | a tabela do lote da [[samples-workspace]], e qualquer amostra cujos espectros não possam ser lidos |

Números são escritos como números, de modo que uma coluna soma, ordena e
plota. Nada é arredondado: uma coluna mostrada com três casas decimais contém
todos os dígitos que o resultado carrega, que é a diferença entre isto e uma
planilha construída colando um relatório dentro dela. Vazio significa não
medido — não zero. Os tempos de aquisição são texto, porque foi assim que o
instrumento os escreveu.

O escritor é o `milq/xlsx.py`: o formato é um zip de partes XML, e a
parte de que uma tabela precisa é pequena o bastante para ser escrita
diretamente em vez de assumir uma dependência que os instaladores teriam de
carregar. Escrever o mesmo lote duas vezes dá arquivos idênticos byte a byte.

**O que foi verificado.** Os testes descompactam cada arquivo que escrevem,
analisam cada parte e leem as células de volta — os tipos, os formatos
numéricos, a linha de cabeçalho em negrito, os cabeçalhos congelados e o
escape de `<`, `&` e `>` — em vez de confiar em que um zip de XML plausível
seja uma pasta de trabalho. Além da suíte, uma pasta de trabalho de um lote
foi lida por dois leitores que nada tiveram a ver com escrevê-la: o
`openpyxl`, que devolveu cada valor com o seu tipo e o seu formato intactos,
e o próprio Quick Look do macOS, que a renderizou. E depois o próprio
Excel: a pasta de trabalho do lote de 26 injeções (3.666 linhas de
resultados, 398 kB) foi aberta no Microsoft Excel para Mac, comandado por
AppleScript, que leu de volta as cinco planilhas que ela contém — Results,
Statistics, Batch QC, Method, Samples; o lote não tem calibração —, a linha
de cabeçalho, a primeira linha de resultados tal como escrita, e uma célula
de área como número e não como texto. O LibreOffice não foi experimentado.

## A lista de transições para o Skyline

**Export for Skyline…** na [[method-workspace]], ao lado de
[[acquisition-schedule|Export schedule…]], escreve o método como uma lista de
transições de moléculas pequenas — o CSV que o *Import Transition List* do
Skyline lê.

| Coluna | De onde vem |
|---|---|
| Molecule List Name | o grupo do componente, ou `Molecules` |
| Molecule Name | o nome do componente |
| Precursor m/z | o precursor |
| Precursor Charge | a carga do aduto do componente, com sinal: `[M-H]-` é −1 |
| Product m/z | o fragmento, ou de novo o precursor onde não há nenhum |
| Product Charge | a polaridade do precursor, com carga unitária |
| Explicit Retention Time | o tempo de retenção esperado |
| Explicit Retention Time Window | o dobro da meia-largura ± de RT, já que a janela do Skyline é a largura inteira |
| Note | `internal standard`, o quantificador de um qualificador, e contra o que um componente é reportado |

Três dessas coisas o método não carrega de saída. Um componente sem **aduto**
não tem carga a escrever, e a célula é deixada vazia em vez de preenchida com
um palpite: a linha de status diz quantos são, e dar um aduto a esses
componentes as preenche. A **carga de um fragmento** não está em lugar nenhum
de um método MRM, de modo que ela é escrita como carga unitária com a
polaridade do precursor — uma suposição, e declarada como tal. Um componente
sem **tempo de retenção** é escrito sem um, e o Skyline procurará por ele na
corrida inteira.

**O arquivo não foi importado no Skyline aqui.** Não há cópia do Skyline na
máquina em que isto foi escrito. Os nomes das colunas são os documentados,
lidos do leitor que as consome no código-fonte do ProteoWizard e dos próprios
tutoriais do Skyline, e os valores são os do método; se o Skyline aceita o
arquivo não foi testado, e dizer isso é melhor que dar a entender o
contrário. Os [[design-principles]] dizem por quê. A mesma ressalva se aplica
à [[acquisition-schedule]], pelo mesmo motivo.

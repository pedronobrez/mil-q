---
title: A área de trabalho Samples
---
A área de trabalho Samples (Ctrl+4) é a tabela do lote: uma linha por injeção,
com tudo o que o arquivo bruto não registra sobre ela. Um `.wiff` reporta toda
injeção como `kUnknown`, de modo que o papel de cada uma — padrão, controle,
branco, desconhecida —, a sua concentração e a sua diluição vivem aqui e são
salvos com o projeto.

## Colunas

| Coluna | Significado | Editável |
|---|---|---|
| File | o nome do arquivo bruto | não |
| Sample | o nome exibido; encurtado a partir do nome do arquivo removendo o prefixo comum a todos os arquivos | sim |
| Type | o papel da amostra, ver abaixo | sim |
| Group | o grupo do estudo — controle, tratado, dia 7; texto livre, porque nenhum vocabulário serve a todo estudo | sim |
| Actual conc. | a concentração esperada, para padrões e controles de qualidade; na unidade de concentração do método | sim |
| Dilution | o fator pelo qual a concentração reportada é multiplicada, porque a curva descreve o frasco que foi injetado e a resposta desejada é a da amostra original | sim |
| Vial | vindo do arquivo | não |
| Acquired | a data e hora da aquisição, vindas do arquivo — o que coloca as injeções na ordem em que o instrumento as executou | não |
| Comment | texto livre | sim |

Selecione linhas e use **Set type of selected rows**, **Set group** ou
**Apply concentration to selection** para editar várias de uma vez. **Add data
files…** e **Close all** são as mesmas ações do menu File.

As colunas que o arquivo *de fato* registra — o frasco, o volume de injeção, o
método de aquisição, o potencial de desagrupamento — são somente de leitura e
aparecem no Explorer: veja [[sample-information]].

## Tipos de amostra e o que os usa

| Tipo | Usado por |
|---|---|
| Unknown | reportada contra a curva; na carta de controle de um padrão interno |
| Standard | define a curva de [[calibration]], com a sua Actual conc.; o padrão mais baixo e o mais alto ancoram [[detection-limits-and-carryover]]; na carta de controle |
| Quality Control | o conjunto de réplicas para a precisão de [[batch-qc]] e para [[compare-algorithms]]; pontuada quanto à exatidão contra a sua Actual conc.; na carta de controle |
| Blank | contada como branco para carryover (arraste); na carta de controle, já que carrega o padrão interno |
| Double Blank | um branco extraído sem o padrão interno: um branco para carryover, **não** na carta de controle |
| Solvent | uma injeção de solvente: um branco para carryover, **não** na carta de controle |

A distinção nos dois últimos é deliberada. Plotar na carta de um padrão uma
injeção que nunca viu esse padrão interno coloca um zero no meio da corrida e
faz um lote íntegro parecer ter perdido o padrão duas vezes.

## Grupos

Um grupo é o que o estudo chamar de grupo. A página [[statistics]] pode agrupar
por ele, o [[metric-plot]] pode colorir por ele, e a seção de estatística do
relatório pode ser disposta por ele. Uma amostra sem grupo está em nenhum
grupo: ela cai fora de um resumo por grupo em vez de ser reunida em um grupo
fantasma "sem rótulo".

## Ordem

As linhas ficam na ordem em que os arquivos foram abertos. Quando as injeções
foram executadas em outra ordem, os tempos de aquisição decidem: a página
[[batch-qc]] e o eixo de ordem de injeção do gráfico de métricas ordenam por
eles e avisam quando alguns arquivos não trazem tempo algum.

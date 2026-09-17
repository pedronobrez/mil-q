---
title: Tabela de resultados
---
A aba **Results** da [[analytics-workspace]] é uma linha por amostra e
componente: o que foi medido, contra o que foi medido, e por que uma linha
está vazia quando está.

## Colunas

| Coluna | Significado |
|---|---|
| Sample, Type, Sample group | a injeção, vinda da [[samples-workspace]] |
| Component, Group | vindos da [[method-workspace]] |
| Channel | o canal de aquisição de onde o pico foi tirado |
| m/z | o centro da janela de massa extraída |
| RT, Exp. RT, ΔRT | o tempo do ápice, o tempo do método e a diferença com sinal |
| Area, Height, Width | o pico; a largura é a largura total à meia altura, em minutos |
| S/N | a altura sobre o ruído, ou `—` quando o ruído não pôde ser medido — ver [[signal-to-noise]] |
| Algorithm | qual [[integration-algorithms|algorithm]] produziu a área — *valley*, *summation*, *gaussian* ou *manual*; vazio nas linhas anteriores a este registro |
| Points | quantos pontos dentro das fronteiras estão em ou acima de um por cento da altura do pico — o pico e não os seus pés; o que a aba *Sampling* de [[batch-qc]] resume |
| IS, IS area | o padrão interno e a área dele nesta amostra; um padrão que não resolve é mostrado com o problema |
| Area ratio, Height ratio | o componente sobre o seu padrão |
| Response | o que a coluna Response do método pede: área, razão ou concentração |
| Ion ratio %, Exp. ratio %, Conf. | a razão medida e a esperada de um qualificador e o seu Pass / Marginal / Fail |
| Actual conc., Calc. conc., Accuracy % | a concentração esperada, a lida na curva (× diluição) e a segunda como porcentagem da primeira |
| Status, Flags | o veredito de [[acceptance-criteria]] e os seus motivos |
| Used | desmarque para deixar uma linha fora das estatísticas e da curva sem apagá-la |
| Note | por que uma linha está vazia, ou o que a integração decidiu — as notas estão listadas em [[integration-parameters]] |

Os nomes das colunas são os do ofício: o que cada um deles quer dizer, em uma
linha, está no [[glossary]].

## Controles

| Controle | Efeito |
|---|---|
| **Show** | All, Pass, Marginal, Fail ou Not integrated |
| **View** | *By sample* ou *By component* — por qual delas as linhas são ordenadas e agrupadas |
| a caixa de filtro | texto livre comparado com todas as colunas |
| **Columns…** | quais colunas são mostradas, e com quantas casas decimais |
| **Export CSV…** | as colunas visíveis das linhas visíveis; o lote inteiro de uma vez é [[export|the Excel workbook]] (a pasta de trabalho Excel) |
| um cabeçalho de coluna | ordenar |

## Edição na tabela

A célula **IS** é uma lista suspensa dos padrões internos do método. Escolher
outro reaponta o componente e recalcula de uma vez toda razão, resposta e
concentração calculada que vinham do antigo, em vez de deixá-las para o
analista lembrar de atualizar.

**Used** é uma caixa de seleção. Uma linha desmarcada é contada nos totais da
página [[statistics]] mas deixada fora da aritmética dela, de modo que excluir
uma injeção aparece como um *n* menor em vez de mudar a média silenciosamente e
sem deixar rastro; o [[report]] marca essas linhas com uma adaga.

## Vínculos

Selecionar uma linha destaca o painel dela na grade de [[peak-review]] e, se
outro componente estiver selecionado na árvore, muda para ele. A linha de
resumo sob a tabela conta as linhas mostradas e quantas estão integradas.

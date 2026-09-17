---
title: Critérios de aceitação
---
O painel **Acceptance** (Aceitação) da [[analytics-workspace]] contém o que uma
linha precisa satisfazer para passar na revisão. Todo limite igual a zero está
desligado, de modo que um método recém-criado não sinaliza nada enquanto os
critérios não forem efetivamente declarados.

| Critério | Sinaliza quando |
|---|---|
| **Max ΔRT** (min) | o ápice está mais distante do que isto do tempo de retenção esperado |
| **Accuracy ±** (%) | para uma amostra com concentração esperada, a exatidão está mais distante do que isto de 100%; ou nenhuma concentração pôde ser lida |
| **Min. S/N** | o sinal/ruído está abaixo disto — ou não pôde ser medido, o que é sinalizado como *S/N not measured* em vez de aprovado, veja [[signal-to-noise]] |

Mais uma verificação corre sem que um critério seja definido: uma linha
normalizada contra um padrão interno que declara uma **Min. response**
(resposta mínima) é sinalizada com *IS 40 below its floor of 100* e falha
quando o padrão deu menos do que seu piso naquela injeção — uma razão contra um
padrão que não está lá não é uma medição. Veja
[[internal-standards-and-qualifiers]].

**Apply to component** grava-os como próprios do componente selecionado;
**Apply to every component** grava-os como padrões do método e limpa todas as
sobreposições.

## Status

| Status | Quando |
|---|---|
| **Fail** | qualquer sinalização, uma razão iônica reprovada, ou uma linha que não integrou de forma alguma |
| **Marginal** | nenhuma sinalização, mas a razão iônica do qualificador está na faixa marginal |
| **Pass** | os critérios foram verificados e nada foi sinalizado |
| *(nenhum)* | nenhum critério se aplicou a esta linha |

Um método ao qual não foram dados critérios reporta **nenhum status, em vez de
um sinal verde**: um método ao qual não se disse o que verificar não verificou
nada, e dizer o contrário seria pior do que não dizer nada. A única exceção é
uma linha que falhou em integrar, a qual sempre falha. Um critério que não pode
ser avaliado em uma linha — uma exatidão em uma amostra sem concentração
esperada — também não conta como verificado.

A coluna **Flags** explicita as razões: `RT +0.312 min`, `S/N 4`,
`accuracy 71%`, `ion ratio 44.1%`, `not integrated`, `no concentration`,
`S/N not measured`, `IS 40 below its floor of 100`. As razões iônicas e suas
tolerâncias são explicadas em [[internal-standards-and-qualifiers]].

## Revisão por status

**Show** na [[results-table]] restringe a tabela a um status; o resumo do
[[report]] os contabiliza e sua seção de achados lista o que falhou. Os status
são recalculados sempre que algo a montante muda — um parâmetro, uma curva, um
padrão — de modo que um status nunca é mais antigo que o número que julga.

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

## Se uma concentração pode ser reportada

Quatro verificações correm em toda linha com curva, haja ou não critérios
definidos, porque não são critérios: dizem se o número em **Calculated** é
uma medição. Cada uma reprova a linha.

| Sinalização | Quando |
|---|---|
| `negative concentration` | a curva leu a resposta abaixo de zero |
| `< LLOQ (1.85 ng/mL)` | abaixo do padrão mais baixo que a curva usa — pela concentração no vial (com o fator de diluição desfeito), **ou** pela resposta, abaixo do que o padrão mais baixo de fato deu. A segunda pega um intercepto negativo que leva uma resposta menor que a do padrão mais baixo a uma concentração acima dele |
| `> ULOQ (400 ng/mL)` | acima do padrão mais alto que a curva usa |
| `the curve's intercept, not the sample's response` | a resposta é menor que um décimo do intercepto da curva, então a concentração é o intercepto lido de volta: todas as amostras dão o mesmo valor, que pode ser positivo e parecer plausível |
| `IS PGE2-d4 5,000 here against 3 in the curve` | o padrão interno nesta linha difere da sua mediana nos padrões da curva por mais de dez vezes, para cima ou para baixo — adicionado num conjunto e não no outro |
| `IS 5-oxo-ETE-d7 absent here, 107 in the curve` | o padrão não tem área nesta linha |
| `IS 12-epi-LTB4-d4 not above the solvents in the curve (5 against 1)` | a mediana do padrão nos padrões da curva é menor que dez vezes a sua mediana nos solventes e duplos brancos: não foi adicionado |

Os limites foram medidos num lote de eicosanoides: um padrão presente nos
dois conjuntos ficou dentro de 1,4× (TXB2-d4, ~460 contagens na curva e
~440 nas amostras), e os desencontrados estavam a 1.500×, 50× e presentes
de um lado só. Brancos, duplos brancos e solventes devem ler zero e não
recebem as sinalizações de concentração; solventes e duplos brancos não
levam padrão e não recebem as do padrão. As linhas do próprio padrão não
são sinalizadas pela sua concentração. Um projeto salvo antes destas
verificações passa a mostrá-las assim que algo é recalculado — basta
**Calibrate**.

## Revisão por status

**Show** na [[results-table]] restringe a tabela a um status; o resumo do
[[report]] os contabiliza e sua seção de achados lista o que falhou. Os status
são recalculados sempre que algo a montante muda — um parâmetro, uma curva, um
padrão — de modo que um status nunca é mais antigo que o número que julga.

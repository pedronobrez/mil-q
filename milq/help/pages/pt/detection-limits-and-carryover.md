---
title: Limites de detecção e carryover
---
Dois números que um laboratório é chamado a defender, calculados onde os dados
os sustentam e retidos onde não os sustentam.

## Limites de detecção e de quantificação

Para cada componente com uma curva de [[calibration]], o limite de detecção é
3.3σ/S e o limite de quantificação 10σ/S, como o ICH Q2 os define, onde S é a
inclinação da curva e σ o desvio padrão dos resíduos em torno da própria reta. O
ICH permite que σ venha de brancos, do intercepto ou dos resíduos; os resíduos
são usados porque são os únicos que toda curva carrega consigo.

| Situação | O que é reportado |
|---|---|
| uma curva linear ou pela origem com três ou mais padrões | LOD e LOQ, com σ e a inclinação |
| a mesma, com menos de três graus de liberdade | os limites, e uma nota dizendo quão poucos — três pontos numa reta de dois parâmetros deixam um, suficiente para calcular e insuficiente para confiar |
| um ajuste ponderado | os limites, notando que os resíduos foram tomados sem ponderação |
| uma quadrática | nenhum: ela não tem uma única inclinação |
| menos de três padrões, ou nenhuma curva, ou inclinação nula | nenhum, com a razão |
| um padrão interno | deixado de fora: sua curva é plana por construção |

**Extrapolado.** Um limite que cai abaixo do padrão mais baixo não foi
demonstrado por aquela curva, apenas extrapolado a partir dela, e é marcado como
tal. Uma curva nada diz sobre concentrações que ninguém colocou nela, e reportar
um limite abaixo do calibrador mais baixo sem dizê-lo é como um método passa a
alegar uma sensibilidade que nunca mostrou.

## Carryover

A medida que os órgãos reguladores pedem: o branco injetado **imediatamente após
o padrão mais alto**, sua resposta como porcentagem da resposta na **menor
concentração calibrada** — não contra o padrão que o causou, o que faria um
método sensível parecer pior quanto mais alto fosse seu calibrador de topo. O
limite é 20%. Blank, Double Blank e Solvent contam todos como brancos; padrões
internos não são verificados.

A ordem de injeção vem dos tempos de aquisição. Um branco em outro lugar da
corrida não é este teste e não é reportado como se fosse; e uma corrida sem
branco após o padrão mais alto volta com *no blank was injected after the
highest standard; inject one to measure carryover* em vez de um número tirado do
branco mais próximo. Um valor de carryover que ninguém mediu é pior que nenhum.

## Onde aparecem

Ambos são seções do [[report]] — *Detection and quantitation limits* e
*Carryover* — calculadas a partir da sessão quando o relatório é escrito, de
modo que refletem as curvas e os resultados tal como estão.

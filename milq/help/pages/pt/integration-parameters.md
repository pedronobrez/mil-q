---
title: Parâmetros de integração
---
O painel **Integration** da [[analytics-workspace]] contém os parâmetros com
que os picos do componente selecionado são encontrados e medidos. Um método
carrega um conjunto de padrões e um componente pode sobrepô-los, de modo que
um analito difícil pode ser ajustado sem perturbar o resto do lote. O título
do painel diz o que ele está mostrando: *method defaults* (padrões do
método) ou *component override* (sobreposição do componente).

## Os parâmetros

| Parâmetro | Significado |
|---|---|
| **Smooth σ** | suavização gaussiana do XIC, em scans; 0 desliga. Aplicada ao traço antes da detecção, da integração e do desenho igualmente |
| **Baseline (min)** | a janela sobre a qual um envelope inferior é estimado e subtraído; 0 desliga. Tem de ser mais larga que o pico mais largo que valha a pena manter |
| **Min. height** | o menor pico mantido, como fração do mais alto na faixa de detecção — 0.05 mantém picos com pelo menos 5% do maior |
| **Min. S/N** | picos cuja altura sobre o ruído fica abaixo disto são descartados; 3 para começar. O que "ruído" é aqui está em [[signal-to-noise]] |
| **Noise as** | como o ruído em uma região de ruído é medido: *peak-to-peak* (a excursão completa, a leitura mais estrita) ou *standard deviation* (desvio padrão) |
| **Peak** | qual pico da janela é o componente quando mais de um passa pelos critérios: *largest* (o maior), ou *nearest the expected RT* (o mais próximo do RT esperado) — ver abaixo |
| **Algorithm** | como se chega à área: vale, somatório ou ajuste gaussiano — ver [[integration-algorithms]] |
| **Noise region** | o trecho de linha de base sobre o qual o ruído é medido, definido a partir de um painel da grade de [[peak-review]]; *automatic* significa o traço inteiro |

**Update method for component** grava os parâmetros como a sobreposição
deste componente; **Update method for group** grava-os em todo componente do
mesmo grupo; **Back to method defaults** remove a sobreposição. **Copy** e
**Paste** levam parâmetros de um componente a outro. Alterar um valor o
pré-visualiza na grade; só Update o mantém.

Update também reintegra, e apenas o que precisa. Cada parâmetro da tabela
acima faz parte da *impressão digital* do componente — o resumo que cada
linha integrada carrega do que a produziu (veja
[[analytics-workspace|Processando só o que mudou]]) — de modo que aplicar um
parâmetro a um componente lê as linhas daquele componente em todas as amostras
e deixa o resto do lote intocado. Um componente com sobreposição própria
**não** se move quando os padrões do método mudam: o que é registrado na
impressão digital são os parâmetros em vigor, e uma sobreposição é o que está
em vigor. Linhas integradas à mão sob os parâmetros antigos são integradas de
novo junto com as demais, porque uma fronteira desenhada sobre um traço não é
uma decisão sobre outro; a linha da [[audit-trail]] diz quantas eram.

## Como um pico é encontrado

O detector trabalha sobre o trecho do XIC que lhe é dado, que é a janela de
tempo de retenção mais três scans de cada lado — ver *A margem* abaixo — e
faz o seguinte:

1. O traço é suavizado para a detecção (um scan por padrão; a integração em
   si usa o traço condicionado, não essa suavização) e todo máximo local com
   pelo menos **Min. height** do mais alto é um ápice candidato, do mais
   forte para o mais fraco.
2. A partir de cada ápice o limite é caminhado para fora, à esquerda e à
   direita, até que ou o sinal tenha descido à linha de base — a mediana do
   traço mais o maior entre o ruído e 5% da altura do pico acima dela — ou
   tenha subido de novo mais que o ruído, o que é um vale entre dois picos.
   Caminhar "enquanto não estiver subindo" foi tentado primeiro e deu picos
   de minutos de largura, porque um XIC é quase todo linha de base plana e
   plano conta como não estar subindo.
3. Uma linha de base reta é traçada entre os dois limites e a área acima dela
   é a área do pico; a altura é medida a partir dessa linha de base; a
   largura é a largura total à metade dessa altura.
4. Picos cuja altura fica abaixo de **Min. S/N** vezes o ruído são
   descartados.
5. Picos cujo ápice cai fora da janela declarada — na margem — são
   descartados: pertencem a outra coisa.
6. Do que sobrou, **Peak** decide qual é o componente.

## A janela e a margem

A janela de tempo de retenção diz onde o ápice pode estar. Ela **não** é uma
afirmação sobre onde o pico termina, e entregar ao detector exatamente essa
janela teve duas consequências, ambas encontradas ao reprocessar um lote
real: o pico era truncado no limite, enviesando a sua área, e — pior — o
detector recusa abaixo de cinco pontos, de modo que uma janela de ±0.5 min
em um método que amostra uma transição a cada 14.6 s continha quatro scans e
voltava vazia, houvesse o que houvesse nela. Um pico de 44,875 contagens foi
lido como "no peak above noise", e se um componente era integrado dependia de
a sua janela calhar de pegar quatro scans ou cinco, o que é definido pelo
deslocamento inicial do canal. Portanto o detector recebe três scans de cada
lado e exige-se, depois, que o ápice caia dentro da janela declarada. Naquele
lote isso levou as linhas com um pico de 1,771 a 2,665 e os componentes com
algum pico de 89 a 139 de 141. A margem é pequena de propósito: tudo dentro
dela compete em altura relativa com o pico real.

Uma janela mais estreita que cinco pontos ainda não retorna nada, e a linha
diz isso — *only 4 points to detect in; the window is narrower than the
sampling can resolve* — em vez de *no peak above noise*, o que manda alguém
procurar por sinal que está claramente ali. [[check-method]] avisa sobre
janelas com menos de oito pontos e [[suggest-from-data]] as alarga.

## Qual pico: o maior ou o mais próximo

*Largest* toma o maior pico da janela, que é o que um pico único com ruído
ao lado precisa e é o padrão, para que nenhum projeto salvo mude os seus
números. *Nearest the expected RT* usa o tempo de retenção do método para
decidir, e é o que duas espécies coeluentes precisam — um vizinho isobárico
ou isomérico dentro de uma janela de ±0.6 min é comum em lipidômica, e ali o
pico mais alto vence quer o método aponte para ele quer não.

A proximidade é decidida **entre os picos que já passaram pelos critérios de
altura e de S/N**, de modo que são esses critérios que impedem *nearest* de
escolher ruído que calhe de estar sobre o tempo esperado; um método cuja
janela está cheia de picos pequenos precisa de Min. height mais alto, não de
uma regra diferente. Quando a proximidade prevalece sobre o tamanho, a linha
diz o que foi preterido — *chosen by proximity; the largest peak in the
window is at 11.62 min and 2.3× the area* — porque uma política que toma
silenciosamente o pico menor não pode ser revisada. Sem um tempo esperado a
regra recai sobre o maior e diz isso.

## As notas que uma linha pode carregar

| Nota | Significado |
|---|---|
| no matching channel | nenhum canal da amostra carrega o precursor e o alvo do componente — ver [[method-workspace]] |
| no data | o canal não retornou nada |
| channel does not cover 5.10–6.10 min | o canal associado não foi adquirido ao longo da janela |
| only 4 points to detect in… | a janela é mais estreita do que a amostragem consegue resolver |
| no peak above noise | nada passou pelos critérios com o seu ápice dentro da janela |
| chosen by proximity… | *nearest* prevaleceu sobre *largest* |
| no expected retention time; took the largest peak | *nearest* não tinha de que estar perto |
| Gaussian fit not possible (…); valley area kept | o ajuste recaiu no vale — ver [[integration-algorithms]] |
| summation needs a retention-time window | o somatório não tem janela sobre a qual somar |
| S/N not measured | um critério de sinal/ruído não pôde ser avaliado — ver [[signal-to-noise]] |

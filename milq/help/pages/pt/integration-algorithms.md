---
title: Algoritmos de integração
---
Uma vez encontrado um pico, há mais de uma maneira de chegar à sua área.
Três são oferecidas, escolhidas por componente ou para o método inteiro em
**Algorithm** no painel de [[integration-parameters]], e cada linha da
[[results-table]] diz qual delas produziu o seu número — a que de fato
rodou, de modo que um ajuste que não pôde ser feito e deixou a área do vale
de pé é rotulado *valley* com o motivo na linha.

## Vale a vale

O padrão, e o que o programa sempre fez: caminhar do ápice até os vales de
cada lado, traçar uma linha de base reta entre eles e tomar a área do
trapézio do traço acima dela. Nada em um projeto salvo tem os seus números
alterados por isso ter ganhado um nome. É a resposta certa para um pico bem
amostrado e a única resposta para um pico de um ponto.

## Somatório sobre a janela

Nenhuma busca de picos. A janela de tempo de retenção do componente é o
limite, a linha de base é a reta entre as suas duas extremidades, e o que
estiver acima dela é a área. É a aritmética da integração manual aplicada à
janela declarada, e o que o algoritmo de mesmo nome do MultiQuant faz.

A sua virtude é que nenhum parâmetro de detecção pode movê-lo: o método
decidiu a janela e a janela é a resposta. O seu custo é que ele soma o que
quer que a janela contenha — em uma janela de ±0.5 min com quatro scans,
linha de base tanto quanto pico — e que, onde as extremidades da janela caem
sobre os flancos de um pico, a reta entre elas fica acima do pico e não há
nada a somar. Um componente sem tempo de retenção não tem janela, e a linha
diz *summation needs a retention-time window*. O critério de sinal/ruído é
respeitado, medido como o detector o mede, de modo que uma janela de linha
de base não seja reportada como um pico; um operador que queira a soma de
qualquer modo põe Min. S/N em zero.

## Ajuste gaussiano

O pico é encontrado como o vale a vale o encontra, e então uma gaussiana é
ajustada aos pontos dentro dos seus limites, acima da mesma linha de base
reta; a área do modelo — altura × σ × √2π — é reportada em vez da do
trapézio, e o seu centro como o tempo de retenção, a sua largura total à
meia altura como a largura. O ajuste é Levenberg–Marquardt com o jacobiano
analítico, partindo da parábola através dos logaritmos do ápice e dos seus
vizinhos.

### Por que ele existe

Em um traço amostrado a cada quinze segundos um pico tem dois ou três pontos
de largura, e um trapézio sobre eles depende de onde os scans calharam de
cair em relação ao ápice, o que é um acidente da aquisição. Medido em picos
sintéticos a 14.6 s de amostragem, sobre sessenta fases dos scans:

| Largura à meia altura | Dispersão do trapézio com a fase | Ajuste, onde pôde ser feito |
|---|---|---|
| 11.3 s | 16.8% | exato (34 de 60 fases) |
| 14.1 s | 5.1% | exato, dispersão de 0.00% (todas as 60) |
| 17.0 s | 1.1% | exato (todas as 60) |

Com ruído de Poisson sobre um pico de mil contagens, a 14.1 s de largura:
trapézio 5.8%, ajuste 3.0%. Acima de 17 s ambos são limitados pelo ruído de
contagem e o ajuste não acrescenta nada. Em um pico com cauda, o ajuste é
uma aproximação declarada: a área se mantém dentro de cerca de 2% até uma
cauda com o dobro da largura do núcleo, e o r² do ajuste diz quão longe de
gaussiano o pico estava.

### Quando ele não é feito

O ajuste precisa de **três pontos sobre o pico** — acima da linha de base e
com pelo menos 1% do ápice. Dois pontos e uma largura fazem uma gaussiana, e
os zeros ao lado deles não dizem mais do que que a largura é pequena, de
modo que um ajuste a dois se acomoda onde quer que tenha começado: medido a
14.6 s de amostragem, enviesado para baixo em sete por cento. E um terceiro
ponto a uma fração de por cento do ápice é o pé do pico, não o seu flanco.
No lote para o qual isto foi escrito, o único padrão interno com resposta
real — 52,000 contagens em um scan — tinha vizinhos de 44 e 98, do mesmo
tamanho que as flutuações da linha de base mais adiante no traço, e a
primeira versão do ajuste passou uma curva exatamente por esses três pontos,
r² = 1.000, e reportou uma área um terço menor. Uma largura tomada de três
pontos com três parâmetros é uma largura tomada do ruído.

Portanto um ajuste que não é determinado pelo pico não é feito. A linha
mantém a área do vale, é rotulada *valley* e diz por quê: *1 point(s) above
the baseline, 3 needed*, ou *narrower than the sampling resolves: 2 point(s)
above 1% of the apex*. E um ajuste através de exatamente três pontos é
reportado como **exact through 3 points** em vez de com um r² que não
significa nada. A 14.6 s entre scans, um pico de pelo menos cerca de 17 s de
largura à meia altura sempre pode ser ajustado, e um mais estreito só quando
os scans caem sobre os seus flancos.

## Qual usar

- Um método cujos picos têm vários pontos de largura: vale, ou o ajuste onde
  o diálogo [[compare-algorithms]] mostrar que ele se repete melhor.
- Picos de um ou dois pontos de largura: nada faz melhor que o vale, e a
  comparação dirá isso em números em vez de em opinião.
- Um revisor que queira todo o conteúdo da janela sem nenhuma decisão de
  detecção dentro: somatório.

O que a escolha fez em um lote real — 400 de 2,638 linhas ajustadas, 2,169
com pontos de menos para ajustar, e nenhum componente movido mais que 20% —
está em [[measured-facts]]. O algoritmo não moveu os números daquele lote; a
amostragem moveu.

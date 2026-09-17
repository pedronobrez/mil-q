---
title: Sugerir a partir dos dados
---
**Suggest from data…** na [[method-workspace]] propõe duas coisas que as
injeções abertas podem fornecer: tempos de retenção para componentes que não
têm nenhum, e meias larguras de janela que a amostragem consegue resolver. Nada
é escrito até que uma linha seja marcada e **Apply** pressionado, e nada vem
pré-marcado a menos que a estimativa tenha se provado neste lote.

## Tempos de retenção

Para cada componente sem um tempo, todos os picos de todas as injeções abertas
são encontrados — não apenas o mais alto — e a estimativa é o tempo em que o
maior número de injeções concorda dentro de um intervalo de amostragem. A
concordância entre injeções, e não a intensidade, é o que decide se um tempo
significa alguma coisa: uma transição amostrada a cada quinze segundos dá um
pico de um ou dois pontos, e a intensidade sozinha não distingue um pico de uma
espícula. Um tempo só é oferecido quando pelo menos metade das injeções o
sustenta.

### Calibrado, não afirmado

Antes de propor qualquer coisa, o estimador é rodado sobre os componentes que
**já declaram um tempo**, e registra-se com que frequência ele caiu dentro de
um intervalo de amostragem do tempo declarado — em faixas de altura de pico,
porque a altura é o que decide se um tempo pode ser estimado de todo:

| Altura do pico | No lote para o qual isto foi escrito |
|---|---|
| 0 – 100 contagens | 45% dentro de um intervalo (n = 20) |
| 100 – 1,000 | 54% (n = 13) |
| 1,000 – 10,000 | 54% (n = 13) |
| acima de 10,000 | 88% (n = 8) |

Cada proposta carrega então a exatidão que o estimador atingiu **na sua própria
faixa de altura neste lote**, e a primeira frase do diálogo enuncia a tabela
inteira. Uma linha só vem pré-marcada quando a sua faixa tem pelo menos 60%
dentro de um intervalo e componentes suficientes para tê-lo medido. Naquele
lote, nada do que foi oferecido estava acima de dez mil contagens, de modo que
**nada veio pré-marcado** — o que é o resultado pretendido: o estimador não se
provou nas alturas que precisavam dele, e dizer isso é o sentido de calibrar.

### Transições compartilhadas

Dois componentes que declaram a mesma transição recebem a mesma estimativa e
são marcados com uma nota: aceitar ambos escreve a mesma resposta sob dois
nomes, e não separa nada. Eles são oferecidos, para que o leitor possa escolher
um, e nunca vêm pré-marcados.

## Janelas

A segunda aba lista cada componente cuja janela ± contém menos de oito pontos
no intervalo de amostragem medido a partir dos arquivos, com a meia largura que
daria oito. Em um método que amostra uma transição a cada 14.6 s, ±0.50 min
contém quatro pontos e ±0.97 contém oito. Estas vêm marcadas: não há incerteza
nelas, apenas a aritmética do tempo de ciclo. Por que oito, e o que acontece
abaixo de cinco, está em [[integration-parameters]].

## Rumo a um agendamento

As janelas que este diálogo alarga são as janelas sobre as quais
[[acquisition-schedule]] adquire: uma janela mais larga é mais pontos sobre o
pico e, ao mesmo tempo, mais transições adquiridas ao mesmo tempo. O diálogo do
agendamento diz o que isso faz com o dwell time.

## Depois de aplicar

O método muda; o lote não é reprocessado até que **Process batch** seja
pressionado na [[analytics-workspace]]. **Check method**, rodado em seguida,
não deve mais listar os componentes que receberam tempos.

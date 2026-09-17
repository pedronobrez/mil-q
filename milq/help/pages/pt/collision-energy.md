---
title: Energia de colisão
---
O [[acquisition-schedule]] é a metade cromatográfica de *o que dizer ao
instrumento*: o método implica uma aquisição, e o programa diz quanto ela
custaria antes que alguém a digite. Esta é a metade de infusão. Uma bandeja
de infusões de um padrão costuma ser o mesmo frasco borrifado em várias
energias de colisão e, num instrumento que tem as duas, sob mais de uma
ativação — CID e EAD. Alguém então precisa escolher uma, e a escolha
normalmente é feita a olho, pelo espectro que pareceu mais movimentado.

**Recommend energies…** na aba [[infusion-report]] agrupa cada infusão
medida por composto, ativação e energia de colisão, e faz **três**
recomendações por composto, cada uma com os números em que se apoia. Três,
porque são três perguntas diferentes e elas não precisam concordar.

## As três perguntas

**Para identificação** — o maior número de íons previstos encontrados, *com
o precursor ainda de pé acima de 100 contagens*. As duas metades são
exigidas. Um espectro com quinze fragmentos e nenhum precursor restante não
pode dizer que os fragmentos vieram do íon que o método isolou — a janela de
isolamento pode ter pego um vizinho, que é o que o [[accurate-precursor]]
existe para pegar — e um espectro com um precursor alto e dois fragmentos
não identificou nada. Um empate na contagem é desfeito pela fração
explicada, e a justificativa diz isso.

**Para quantificação** — a energia cujo *fragmento mais forte* detém a maior
fração da intensidade medida, e devolve a mesma fração da próxima vez que o
frasco for borrifado. Uma transição é um único íon-produto: a energia que
põe 60% do espectro em uma massa dá uma transição seis vezes maior do que a
que espalha os mesmos íons por vinte massas. Onde o composto foi infundido
mais de uma vez naquela condição, a fração precisa repetir-se dentro de 20%
— o número em que uma carta de controle do mesmo padrão marca um ponto
fora, e em que a [[compare-infusions]] marca um pico base como deslocado.
Onde foi infundido uma vez só, a justificativa diz que a fração é uma
medida e não uma repetição, em vez de chamar uma medida de estável.

**Para um registro de biblioteca** — o meio das energias medidas, com a
maior fração explicada entre as do meio. Um registro feito na energia mais
branda guarda o precursor e pouco mais, e não casa com nada; um feito na
mais dura guarda fragmentos pequenos demais para outro instrumento
reproduzir. O meio é uma **posição entre as energias que foram
adquiridas**, nunca um número entre duas delas.

## O que nunca é oferecido

Uma energia que ninguém adquiriu. Não há interpolação nem "ótimo" entre dois
pontos medidos: o que um composto faz a 30 eV, tendo sido borrifado a 22 e a
45, é uma medida que ninguém tomou. Onde um composto foi borrifado em uma só
condição, a recomendação é *one energy measured; nothing to choose between*
— uma energia medida; nada a escolher —, que é a resposta verdadeira e não
uma falha.

## A tabela

Uma linha por composto, ativação e energia de colisão — uma *condição*, que
é como o [[standard-history]] corta a história de um padrão em séries e como
a [[compare-infusions]] casa dois dias, pelo mesmo motivo: 12 eV EAD e 45 eV
CID são duas medidas de duas coisas diferentes. Onde uma condição tem mais
de uma infusão, cada número é a mediana sobre elas.

| Coluna | Significado |
|---|---|
| Activation | como o nome do arquivo escreve; `unstated` onde ele não escreve nenhuma, o que não é o mesmo que CID |
| CE (eV) | a energia que a aquisição declara, ou a que o nome do arquivo escreve |
| Ions found | dos previstos para a fórmula do composto — veja [[lipid-maps]] |
| Explained | a fração da intensidade do espectro que a previsão explica |
| Precursor height, % of base | o que sobreviveu à fragmentação, contra o pico base |
| Base peak share, Fragment 1–3 | da intensidade somada da lista de picos medida |
| Against other energies | o cosseno mediano desta infusão contra as outras condições do mesmo composto |
| Considered | `no` numa linha que o veredicto de isolamento contradiz, com o que o método de fato isola |

As frações têm dois denominadores e cada um é nomeado onde é escrito. O do
precursor é o **pico base**, que é como qualquer um lê o traço. Todas as
outras frações são da **intensidade somada da lista de picos** em que a
tabela é medida — os picos em 1% do pico base ou acima, que é a lista de que
os escores e os registros próprios já são feitos.

## Linhas que aparecem e nunca são recomendadas

Uma linha cujo arquivo tem o nome de um composto enquanto seu método isola
algo que não é aduto dele fica na tabela, marcada, e nunca é recomendada.
Não é apagada porque um par delas é um achado sobre a bandeja, e não é
recomendada porque não é uma medida do composto do rótulo. Uma linha assim
também nunca divide uma condição com uma linha mantida: mediar dois
compostos sob um mesmo cabeçalho é exatamente o dano que o veredicto foi
escrito para pegar.

## O que sai dela

**Export CSV…** escreve a tabela e as recomendações num arquivo em dois
blocos — uma linha por condição, depois uma linha por recomendação com sua
justificativa, separados por uma linha em branco, que é o que uma planilha
lê como o fim de uma tabela.

O documento por composto (**Report…** na mesma aba) ganha um parágrafo
*Collision energy* sempre que as linhas escolhidas contêm mais de uma
condição daquele composto. O diálogo, o CSV e a página são a mesma
aritmética e não podem discordar.

## Uma advertência medida

Nos padrões de ácidos biliares contra os quais isto foi escrito, a **fração
explicada é maior na energia mais branda** — 85,0% a 12 eV EAD para um
deles, contra 63,6% a 22 eV — porque o precursor sobrevivente é 82% daquele
espectro e o precursor é um íon que a previsão explica. É por isso que a
regra da biblioteca toma primeiro a energia do meio e a fração explicada só
entre as candidatas do meio: a maior fração explicada, sozinha, recomendaria
a energia em que o composto mal se fragmentou.

---
title: Verificar o método
---
**Check method** no [[method-workspace]] lê o método contra si mesmo e contra os
arquivos abertos, e diz em que ele vai falhar antes que um lote seja processado.
Tudo o que ele reporta seria de outro modo aprendido a partir dos resultados, o
que é mais tarde e mais difícil.

## O que é verificado

| Achado | Severidade | Significado |
|---|---|---|
| shared transition | serious | dois componentes declaram o mesmo precursor e o mesmo fragmento e não têm nada — nenhum tempo de retenção, ou o mesmo — que os separe; a integração devolverá o mesmo pico sob os dois nomes |
| missing internal standard | serious | um componente nomeia um padrão que nenhum componente carrega, ou um que não está marcado como IS |
| internal standard without a time | serious | um padrão sem tempo de retenção é buscado ao longo de toda a corrida, e toma o maior pico em qualquer lugar dela; cada componente que ele normaliza herda isso. A contagem de componentes que ele carrega é dada |
| internal standard without a response floor | warning | um padrão que serve componentes não declara nenhuma **Min. response**, de modo que as cartas de qualidade e a aceitação recaem sobre um sinal/ruído de dez — o que, numa aquisição agendada, é uma altura absoluta contra uma constante arbitrária. Veja [[internal-standards-and-qualifiers]] |
| formula against precursor | serious | a **Formula** de um componente e o seu **Precursor** estão mais distantes do que a última casa decimal escrita desse precursor permite. Um dos dois está errado, e eles fazem trabalhos diferentes: o precursor escolhe o canal de aquisição e, onde nenhum fragmento está escrito, constrói a janela de extração; a fórmula é a massa verdadeira em direção à qual a [[mass-recalibration|recalibração]] corrige. O *Repair precursors…* da [[method-workspace]] lista esses casos com as duas massas e escreve a da fórmula onde uma linha for marcada. Uma linha a um dalton inteiro ou mais é o caso em que a massa é provavelmente a certa — é o que o instrumento foi posto a adquirir — e ali o *nome* é o erro, então o diálogo oferece os nomes cuja fórmula corresponde à massa escrita |
| internal standard without a formula | warning | o padrão não pode ser uma lock mass. Sem uma fórmula e um aduto nada diz onde a massa dele deveria estar, e o precursor escrito não pode substituí-la — um digitado com uma única casa decimal é bom até algumas centenas de partes por milhão, cem vezes o erro que está sendo corrigido. O *Fill formulas from names* no [[method-workspace]] deriva uma onde quer que o nome seja notação abreviada de lipídios |
| no retention time | warning | a janela do componente é a corrida inteira, de modo que o maior pico da corrida é o componente, seja ele qual for |
| precursor outside the survey scan | warning | com arquivos abertos: componentes cujo precursor nenhuma varredura de survey cobre, e as faixas que os surveys de fato cobrem. A massa exata, a anotação do LIPID MAPS e a [[mass-drift]] não podem ser medidas para eles; a transição em si não é afetada. Uma aquisição sem nenhuma varredura de survey é reportada sob as verificações puladas |
| window too narrow | warning | no intervalo de amostragem medido a partir dos arquivos abertos, a janela ± contém menos de oito pontos; abaixo de cinco o detector recusa de saída |

Severidades: um achado **serious** produzirá números errados; um **warning**
produzirá números mais difíceis de defender.

## O que é pulado, e dito

Verificações que precisam dos arquivos — o intervalo de amostragem, e portanto a
verificação de janela — são puladas quando nenhuma amostra está aberta, e o
diálogo lista o que não pôde verificar em vez de silenciar sobre isso. Um método
que "passa" com metade das verificações não executadas não passou.

## Agindo sobre os achados

- Uma transição compartilhada precisa de um tempo de retenção em cada
  componente, e de tempos diferentes.
- Um padrão sem tempo precisa de um: [[suggest-from-data]] estima tempos a
  partir das injeções abertas e diz o quanto cada estimativa pode ser confiada.
- Uma janela estreita demais para a amostragem pode ser alargada pelo mesmo
  diálogo, que calcula a meia-largura que dá oito pontos.
- Um padrão ausente é um erro de grafia ou uma marcação faltando, corrigido na
  tabela.
- Um padrão sem fórmula ganha uma do *Fill formulas from names* onde o nome
  dele diz do que ele é feito; os demais são digitados.
- Uma fórmula que discorda do seu precursor é uma pergunta que só quem
  escreveu o método pode responder — qual dos dois está certo. O *Repair
  precursors…* da [[method-workspace]] põe a pergunta linha por linha, com as
  duas massas, a diferença em mDa e em ppm e a janela de extração antes e
  depois, e escreve a massa da fórmula no precursor onde a linha for marcada.
  Ele marca por você as linhas abaixo de meio dalton e deixa as demais para
  você, porque abaixo de meio dalton é um mesmo composto escrito com menos
  casas e acima disso são dois compostos diferentes. No lote contra o qual
  isto foi desenvolvido a discordância foi relatada pelo *Fill formulas from
  names*, e não por esta verificação — a verificação lê uma fórmula que a
  tabela já carrega, e o preenchimento se recusa a escrever uma que não pode
  confirmar — e 13 dessas 16 recusas eram o precursor escrito com menos casas
  do que merecia: o `dHCer(d18:0/12:0)`
  carregava 484.465 contra os 484.4724 da sua própria fórmula, 15 ppm fora, e
  o `C25:0-Ceramide` carregava 664.4 contra 664.6602, 392 ppm fora. Reparar
  esses treze não mudou nenhum resultado do lote — toda linha carrega um
  fragmento, então nenhuma janela se moveu, e todo precursor reparado ficou
  dentro dos 0,7 Da que escolhem o canal de aquisição — e levou o método de 125
  fórmulas para 138 de 141, e de 10 dos seus 11 padrões internos com fórmula
  para os 11. Os outros três erravam
  por um dalton inteiro ou mais, e repará-los tirou dois deles de todo canal
  adquirido e os pôs sobre a varredura de survey; a [[method-workspace]] tem
  os números. Uma discordância de um dalton inteiro é uma pergunta sobre o
  *nome* tantas vezes quanto sobre a massa, e onde ela é, o achado diz isso e
  a coluna *Rename to* do diálogo a responde: os nomes cuja fórmula
  corresponde à massa que foi escrita, primeiro os da própria classe da linha
  e depois os do [[lipid-maps|LIPID MAPS]]. Nas três linhas de um dalton
  inteiro daquele método ela oferece o `LacCER(d18:1/18:2)` para o
  `LacCER(d18:1/18:1(9Z))` escrito 886,6407, a −17,7 ppm — e nada para as
  outras duas, que é a metade mais útil da resposta. O `LacCER(d18:0/18:1)`
  erra por um dalton ímpar, e uma cadeia é 14 Da, uma dupla ligação 2 e uma
  hidroxila 16: nenhum nome daquela classe pode ficar a um dalton, então o
  engano é o dígito e não o composto. O `C18:1 Cer` erra por cem, além do que
  uma cadeia mal nomeada pode ser. Uma renomeação não move número nenhum —
  mesmo precursor, mesmo fragmento, mesma janela, mesmo canal — e reprocessar
  o lote depois dela deixou 78 de 78 linhas idênticas; o que ela compra é uma
  linha cuja fórmula concorda com a sua própria massa.

A verificação corre sobre o método tal como está, de modo que pode ser executada
de novo após cada correção. Os mesmos achados aparecem no início da seção de
método do [[report]], de modo que um relatório carrega seus próprios avisos, e
tudo o que está aqui — agrupado por severidade, com cada linha marcada na
tabela de componentes — é a segunda seção do [[method-report]].

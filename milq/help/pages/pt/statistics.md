---
title: Estatística
---
A aba **Statistics** da [[analytics-workspace]] resume cada componente sobre
grupos de amostras: média, desvio padrão e coeficiente de variação, com os
valores individuais por trás deles.

| Controle | Efeito |
|---|---|
| **Group by** | *concentration* (amostras que compartilham uma concentração esperada — padrões em réplica, QCs em réplica), *sample name*, *sample type* ou *sample group* |
| **Quantity** | *response* (o que o método reporta para o componente), *area*, *height*, *calculated concentration*, *retention time*, *area ratio* |
| **Export CSV…** | a tabela como mostrada |

## A tabela

Uma linha por componente e grupo: o componente, o grupo, `n` usados de `n`
total, a média, o desvio padrão amostral, o **%CV** e — para grupos com uma
concentração esperada — a exatidão média. As colunas de valores à direita
listam cada membro do grupo, de modo que o número possa ser lido contra o que o
produziu.

O desvio padrão é o desvio padrão amostral (n − 1); um valor único não tem
dispersão a reportar. Uma linha desmarcada em **Used** é contada no total mas
deixada fora da aritmética, de modo que excluir uma injeção aparece como um *n*
menor em vez de uma média silenciosamente diferente.

Os grupos de um componente ficam juntos, para que controle, tratado e dia 7
possam ser lidos uns contra os outros; os resultados chegam amostra por
amostra, o que de outro modo espalharia cada grupo de cada componente pela
tabela.

## Agrupar por grupo de amostra

Uma amostra sem grupo está em nenhum grupo: ela cai fora do resumo em vez de
reunir toda injeção sem rótulo em um grupo fantasma. Os grupos são texto livre
definido na [[samples-workspace]].

## Precisão, corretamente

Para a pergunta "quão bem o lote se repetiu", a aba Precision da página
[[batch-qc]] é a ferramenta mais estrita: ela toma apenas os controles de
qualidade — as desconhecidas diferem entre si por projeto e os padrões por
construção — e aplica um limite. Esta página é o resumo geral.

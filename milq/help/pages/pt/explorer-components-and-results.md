---
title: Componentes e resultados no Explorer
---
O Explorer pode executar a lista de componentes do método sobre o que estiver
aberto, que é o modo rápido de ver um composto em alguns arquivos sem montar o
lote.

## A aba Components

A lista é a tabela de componentes do [[method-workspace|method]], somente
leitura aqui e compartilhada com todas as áreas de trabalho: precursor,
fragmento, tempo de retenção e janela, tal como o método os declara.

- **Duplo clique numa linha** para desenhar o XIC daquele componente em cada
  amostra marcada. O canal é escolhido pela mesma regra que a área de trabalho
  Analytics usa — precursor, cobertura de tempo e faixa de massa — e a janela de
  massa é a tolerância do componente.
- **Extract and integrate all** (extrair e integrar tudo) executa cada
  componente sobre cada amostra marcada e preenche a aba Results. A integração é
  o mesmo caminho de código de um lote em Analytics, com os padrões de
  integração do método.

## A aba Results

Uma linha por componente e amostra: componente, amostra, canal, m/z, tempo de
retenção, área, altura, largura, sinal/ruído e uma nota dizendo por que uma
linha está vazia quando está (nenhum canal correspondente, o canal não cobre o
tempo esperado, nenhum pico acima do ruído). Ordenável por qualquer coluna;
**Export CSV…** escreve o que está mostrado. Dar duplo clique numa linha desenha
o traço daquela linha.

Esses resultados são os próprios do Explorer. Os resultados do lote — os que a
[[results-table]], a calibração e o relatório usam — são produzidos na
[[analytics-workspace]] por **Process batch**, e as duas não são a mesma tabela.

## Detect peaks

**Detect peaks** na barra de ferramentas Processing integra cada traço
atualmente desenhado no cromatograma — TICs, BPCs e XICs igualmente — com o
detector automático em suas comportas padrão (um pico tem de ser ao menos 5% do
mais alto do traço e ao menos três vezes o ruído), marca cada pico no gráfico e
os lista na aba Results. É um levantamento, não uma quantitação: ele não sabe
que composto um pico é, e não usa nenhuma janela de tempo de retenção. Como o
detector encontra as bordas de um pico está descrito em
[[integration-parameters]].

## Um intervalo à mão

Shift+arrastar sobre um pico no cromatograma e a barra de status relata a
integração exatamente daquele intervalo — área acima de uma linha de base reta
traçada entre as extremidades, altura, tempo do ápice e S/N. Esta é a mesma
aritmética que a integração manual usa na grade de [[peak-review]].

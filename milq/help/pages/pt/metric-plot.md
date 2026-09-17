---
title: Gráfico de métricas
---
A aba **Metric plot** (gráfico de métricas) da [[analytics-workspace]]
desenha qualquer coluna numérica dos resultados contra a ordem das linhas, a
ordem de injeção ou outra coluna, para um componente ou para todos.

| Controle | Efeito |
|---|---|
| **X** | *injection order* — a ordem em que o instrumento executou as amostras, a partir dos tempos de aquisição; *row order* — a ordem da tabela de resultados; ou qualquer coluna numérica |
| **Y** | qualquer coluna numérica: área, altura, S/N, razão de áreas, tempo de retenção, ΔRT, concentração calculada, exatidão… |
| **Component** | um componente, ou todos os componentes sobrepostos |
| **Colour by** | *sample group*, *sample type* ou *nothing* — com legenda, e *no group* para as amostras que não têm nenhum |
| clicar em um ponto | seleciona a linha correspondente na [[results-table]] e o painel dela na grade de [[peak-review]] |

## Usos

- **Área ou razão contra a ordem de injeção**, para um padrão interno: o modo
  mais rápido de ver se a corrida se sustentou. A página [[batch-qc]] faz isso
  com limites e vereditos.
- **Tempo de retenção contra a ordem de injeção**: deriva da coluna, e um pico
  que salta entre dois vizinhos.
- **Concentração calculada contra a real**: a calibração vista do lado das
  amostras.
- **Exatidão contra S/N**: se as falhas são os picos fracos.
- **Colorido por grupo de amostra**: se tratado e controle se separam em um
  componente, antes de rodar qualquer estatística.

A ordem de injeção já foi a ordem em que os resultados por acaso foram
calculados, que era a ordem em que os arquivos foram abertos; hoje é o tempo
de aquisição, e os arquivos que não trazem nenhum ficam por último, na ordem
de abertura.

---
title: Calibração
---
Uma curva de calibração converte uma resposta em uma concentração. É construída
a partir das amostras tipificadas como **Standard** na [[samples-workspace]],
cada uma com sua **Actual conc.**, e aplica-se a todas as demais amostras do
mesmo componente.

## A aba Calibration

Para o componente selecionado na árvore: os pontos, a reta ajustada, a equação,
r e r², e uma tabela dos padrões com a concentração retrocalculada e a exatidão
de cada um. A linha de status diz quantas curvas foram ajustadas de quantos
componentes têm padrões.

| Controle | Efeito |
|---|---|
| **Regression** | *linear*, *linear through zero*, *quadratic*, *mean response factor* |
| **Weighting** | *1*, *1/x*, *1/x²*, *1/y*, *1/y²* |
| **Remove outliers** com sua tolerância | descarta padrões cuja exatidão está fora da tolerância, um de cada vez, do pior para o melhor, reajustando após cada um |
| clicar num ponto do gráfico, ou dar duplo clique numa linha | inclui ou exclui aquele padrão; a exclusão sobrevive a um reajuste |
| **Recalibrate** (barra de ferramentas) | reajusta cada curva a partir dos padrões e lê os desconhecidos de volta nelas, sem reintegrar |

A regressão e a ponderação são propriedades do componente e são salvas no
método.

## A partir de que a curva é construída

A **razão para o padrão interno** quando o componente tem um, e a **área** bruta
caso contrário. Essa é a grandeza medida, distinta da coluna *Response* do
método, que diz o que a tabela de resultados reporta.

## Pontos mínimos

| Regressão | Padrões necessários |
|---|---|
| linear | 2 |
| linear through zero | 1 |
| quadratic | 3 |
| mean response factor | 1 |

Uma curva com menos não é ajustada e o painel o diz. Com exatamente tantos
pontos quantos parâmetros, a curva passa por eles quaisquer que sejam; a página
[[detection-limits-and-carryover]] precisa de ao menos um grau de liberdade para
dizer algo sobre dispersão.

## Ponderação

Os mínimos quadrados dão a cada ponto o mesmo peso, e o resíduo absoluto do
padrão mais alto é em geral o maior, de modo que um ajuste não ponderado é um
ajuste ao topo da faixa que erra na base por uma margem ampla em relação à
concentração ali. *1/x* e *1/x²* ponderam pela concentração; *1/y* e *1/y²* pela
resposta. Um ajuste ponderado é a escolha usual para uma faixa de mais de duas
décadas; o relatório e a página de limites dizem que ponderação uma curva
carrega.

## Lendo concentrações

A resposta de cada amostra é lida na curva e multiplicada por seu fator de
**Dilution** — a curva descreve o frasco que foi injetado e a resposta desejada
é a da amostra original. Onde a curva não pode ser invertida (uma quadrática sem
raiz real na faixa, uma inclinação nula) a concentração é deixada vazia. Para
amostras com concentração esperada — padrões e controles de qualidade —
**Accuracy %** é a concentração calculada como porcentagem da real.

## A curva do próprio padrão interno

Um padrão interno é fortificado na mesma quantidade em cada padrão, de modo que
sua resposta contra a concentração é plana e uma curva através dela não
significa nada. O relatório rotula tal curva como sem significado, e a página de
limites deixa os padrões internos de fora.

## Uma curva a partir de infusões

Uma curva não precisa de cromatograma. Uma série de diluições pulverizada em
vez de injetada se ajusta aqui exatamente do mesmo jeito — a resposta é uma
altura num espectro médio e a razão para o padrão interno é tomada nesse
único espectro, que é o que a [[infusion-quantitation]] mede. As linhas
chegam sem tempo de retenção e com um *Algorithm* igual a `infusion`, e tudo
nesta página vale sem mudança.

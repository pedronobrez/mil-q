---
title: O relatório do lote
---
`File ▸ Export report…` escreve o lote inteiro como um documento: PDF para
entregar, HTML para guardar — o segundo abre em um navegador muito depois de
esta aplicação ter desaparecido, que é o sentido de um relatório em oposição a
uma exportação. Ele é construído a partir da sessão e não da tela, de modo que
contém o que foi medido e não o que por acaso estava à mostra.

## Seções

Numeradas na ordem em que são impressas; deixar uma de fora fecha a lacuna em
vez de deixar um buraco.

| Seção | Contém |
|---|---|
| Summary | linhas, amostras, componentes; quantas passaram, ficaram marginais, falharam; linhas excluídas; e os achados — cada linha reprovada com suas marcações |
| Samples | a tabela do lote: nome, tipo, grupo, concentração, diluição, tempo de aquisição |
| Method | a tabela de componentes, os padrões e os achados de [[check-method]] |
| Calibration | a regressão de cada curva, a ponderação, a equação, o r², e seus padrões com as exatidões; a curva de um padrão interno rotulada como sem significado |
| Detection and quantitation limits | LOD e LOQ por componente, com as notas de [[detection-limits-and-carryover]] |
| Carryover | o branco depois do padrão mais alto, ou por que não foi medido |
| Batch quality | os vereditos das cartas de controle, o índice de resposta da injeção, a deriva e a precisão dos QCs — [[batch-qc]] |
| Sampling | pontos por pico para cada componente, os tempos de ciclo de que os picos precisariam e quantos picos foram mais estreitos que um ciclo — a aba *Sampling* de [[batch-qc]] |
| Mass drift | apenas quando a aba [[mass-drift]] mediu: a massa de cada padrão ao longo da corrida e se o eixo se manteve, e as correções por injeção quando a [[mass-recalibration]] está ligada |
| Infusions | apenas enquanto a aba *Infusions* do [[analytics-workspace]] tiver medido: uma linha por amostra infundida — o precursor medido de volta na própria aquisição, os íons encontrados dentre os previstos, o melhor registro da sua própria biblioteca e cada infusão pontuada contra as outras do mesmo composto — [[infusion-report]] |
| Infusion comparison | apenas enquanto a [[compare-infusions]] tiver sido executada: a bandeja deste dia contra a de um projeto de referência, composto a composto e condição a condição |
| Compared spectra | apenas enquanto o Explorer estiver mantendo espectros juntos: a figura cabeça-cauda, uma tabela dos traços e as massas que eles compartilham dentro de 10 ppm — [[chromatograms-and-spectra]] |
| Integration algorithms | apenas quando [[compare-algorithms]] foi executado: os totais por algoritmo e os componentes que mais se moveram |
| Batch comparison | apenas quando [[compare-batches]] foi executado: os totais lado a lado e os componentes na ordem do quanto se moveram |
| Changes made by hand | apenas enquanto houver histórico a imprimir: cada edição feita à mão na ordem em que foi feita, com o valor antes e depois — a [[audit-trail]], e não uma assinatura eletrônica |
| Results | cada linha: amostra, componente, RT, área, razão, concentração, exatidão, status e marcações |
| Statistics | o resumo agrupado da página [[statistics]], por tipo de amostra |

Duas marcas sobre nomes de amostra são explicadas em uma legenda sob a tabela
que as usa: `†` para uma linha excluída das estatísticas, `‡` para uma linha
integrada à mão. Uma coluna de "sim / não / à mão" custa mais largura do que
rende.

Uma seção sem nada a mostrar diz isso — *no standards, so there is nothing to
carry over* — em vez de imprimir uma tabela vazia.

## A única figura

Todo o resto de um relatório é um número numa tabela. *Compared spectra* é a
exceção, porque dois espectros cabeça-cauda são lidos como uma forma e não
como uma lista, e ela só é impressa enquanto a comparação vale — fixe um
espectro no painel de [[chromatograms-and-spectra]] e a seção aparece,
desafixe e ela some. A figura é desenhada a partir dos dados no momento em
que o relatório é escrito, com o dobro do tamanho com que é impressa, e viaja
dentro do documento: um relatório em HTML continua sendo um único arquivo que
pode ser enviado por e-mail. Os seus rótulos de pico são posicionados para o
papel: cada um acima do pico que nomeia e nunca sobre um traço ou sobre outro
rótulo, subindo uma linha com um fio até o seu ápice onde o espaço está
tomado, e deixados de fora onde não há espaço dentro de seis linhas — veja
[[chromatograms-and-spectra]]. Sob ela estão os traços, cada um com o seu
pico base e quantos picos ele contém, e as massas que todos os espectros
carregam dentro de 10 ppm, com a altura de cada uma como fração do seu
próprio pico base — que é o único modo como dois espectros de tamanhos
diferentes se comparam numa tabela. Uma massa presente em um e ausente no
outro é uma diferença, e uma diferença se lê na figura.

## Temas

O diálogo de exportação pergunta em que tema o documento deve ser escrito, e
lembra a resposta para a próxima vez. Ele muda a aparência do relatório e
nunca o que ele diz: as mesmas seções, os mesmos números, as mesmas palavras.

| Tema | Para |
|---|---|
| Paper | o relatório como sempre foi — o azul do projeto nos títulos, linhas listradas, as figuras nas cores dos próprios traços |
| Black and white | uma revista que imprime em nenhuma outra cor, ou uma fotocopiadora |

**Black and white** é mais do que um relatório com a cor retirada. Nada leva
fundo tingido, porque um tom de 4% se reproduz como nada ou como uma
sujeira: as linhas listradas e as células de cabeçalho sombreadas viram
filetes, e uma linha reprovada fica em negrito onde estava em vermelho. As
figuras acompanham — um relatório em preto e branco com um espectro em quatro
cores não é um relatório em preto e branco —, de modo que os espectros
comparados são desenhados em dois tons e dois estilos de linha: o primeiro
traço em preto sólido (21:1 sobre branco), o segundo tracejado em #666666
(5,7:1) e, onde o desenho é de centroides, uma cabeça cheia nos bastões altos
do primeiro traço e uma vazada nos do segundo, já que um tracejado não
aparece num bastão de um ponto de largura. Medido nos dois espectros médios
de CA-d4 cabeça-com-cauda: com os rótulos de pico mascarados, a tinta do
traço de cima tem cinza mediano 0 e a do de baixo 102, numa página que é 255,
e o padrão tracejado continua sendo uma linha tracejada depois de a figura
ser reduzida à metade.

Há um terceiro tema, **dark**, e ele é só para a exportação em HTML. Um PDF é
uma coisa que alguém imprime, e uma impressora que recebe uma página escura
deposita uma folha inteira de toner com as letras vazadas nela, de modo que a
exportação impressa oferece dois temas e `report.write_pdf` recusa o terceiro.
Na tela ele é o próprio fundo escuro da aplicação, com todas as cores
clareadas até passarem de 3:1 sobre ele. Os mesmos três temas são oferecidos
para uma figura sozinha — ver [[chromatograms-and-spectra]], onde estão os
valores de contraste medidos.

## O layout impresso

A4 retrato; um bloco de título; um sumário com números de página; um cabeçalho
corrente nomeando o relatório a partir da página dois e um rodapé com a versão,
a data e *Page n of N* em todas as páginas, porque uma página que se solta tem
de dizer a que pertence. As linhas de cabeçalho das tabelas se repetem em cada
página que a tabela atravessa.

O documento é diagramado mais de uma vez. Um título deixado órfão no pé de uma
página, com seu conteúdo na página seguinte, é empurrado para a próxima página
e o documento é diagramado de novo — até três vezes, já que mover um título
pode deixar outro órfão — e o sumário precisa de uma passagem própria porque os
números de página não existem antes de as páginas existirem. Um relatório de
cem páginas é, portanto, diagramado três vezes e leva cerca de dezessete
segundos, e é por isso que a exportação mostra um cursor de espera em vez de
parecer travada.

## Uma nota sobre o que já esteve errado

A primeira versão do relatório imprimia a um doze avos do tamanho: oito seções
no canto superior de uma única página em tudo o mais em branco. O layout estava
sendo medido na resolução da tela e impresso na do escritor. Está corrigido, e
dois testes abrem cada PDF escrito — um conta páginas, outro procura tinta
abaixo da metade da altura — porque nada disso era visível no HTML.

A mesma maquinaria de impressão produz o PDF deste manual, a partir de
**Help ▸ Export manual as PDF…**.

Um relatório é o que se guarda. Aquilo em que se continua a trabalhar é a
pasta de trabalho Excel com as mesmas seções — ver [[export]], que cobre
também a lista de transições para o Skyline.

Este relatório é de um lote. Um composto pulverizado sozinho não tem lote do
qual fazer parte, e ganha um documento próprio: o [[infusion-report]],
escrito a partir do Explorer e impresso pela mesma maquinaria. E o método sob
o qual um lote foi executado, lido antes de qualquer coisa ser adquirida, é o
[[method-report]] — mesma impressora, mesma página, outra pergunta.

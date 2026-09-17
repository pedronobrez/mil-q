---
title: Bem-vindo
---
O MIL-Q é um software de código aberto para revisar e quantificar dados
de cromatografia líquida acoplada à espectrometria de massas. Ele lê
arquivos `.wiff` da SCIEX diretamente e **mzML** de qualquer instrumento, e
faz os dois trabalhos que a SCIEX distribui em dois programas: a revisão
qualitativa do jeito do PeakView — cromatogramas, espectros, íons extraídos,
química — e a quantificação em lote do jeito do MultiQuant — uma tabela de
componentes, um cromatograma por amostra para cada componente, curvas de
calibração, estatísticas e controle de qualidade.

Este manual descreve cada parte do aplicativo, o que cada controle faz, o
que cada número significa e, onde um número foi medido em vez de suposto, o
que foi medido e em quê. É o mesmo texto da janela **Help ▸ Manual** do
aplicativo e da cópia impressa que **Help ▸ Export manual as PDF…** gera.

## Como o manual está organizado

| Seção | O que cobre |
|---|---|
| Primeiros passos | [[installation]], [[formats]], [[starting-a-project]] e [[workspaces]] |
| Explorer | revisão qualitativa: [[chromatograms-and-spectra]], a [[contour-view]], [[manual-xic]], e um padrão infundido de ponta a ponta — [[direct-infusion]], o [[infusion-report]], [[new-standard]], a [[infusion-quantitation]] |
| Química e anotação | a [[mass-calculator]], o [[formula-finder]], o [[lipid-maps]], a [[spectral-library]], o [[standard-history]] e o [[accurate-precursor]] |
| Amostras | o lote: [[samples-workspace]] |
| Método | a tabela de componentes: [[method-workspace]], [[internal-standards-and-qualifiers]], [[check-method]], [[method-report]], [[suggest-from-data]], [[acquisition-schedule]], [[collision-energy]] |
| Análise | quantificação: [[peak-review]], [[integration-parameters]], [[integration-algorithms]], [[calibration]], [[batch-qc]], [[mass-drift]], [[audit-trail]], o [[report]] |
| Referência | [[projects-and-files]], a [[command-line]], os [[keyboard-shortcuts]], o [[troubleshooting]], o [[glossary]] e o [[version-history]] |

## Como chegar até ele

**F1** (⌘? no macOS) abre o manual na página correspondente a onde você
está: o painel que está com o foco — o painel Integration, a tabela de
resultados, a aba Batch QC, uma aba lateral do Explorer — ou, na falta
disso, a área de trabalho exibida. As caixas de diálogo trazem um botão
**Help** que faz o mesmo para a página delas. **Help ▸ Manual** abre o
manual pela mesma regra, e **Contents**, na barra de ferramentas do manual,
volta para esta página.

## Como lê-lo

As páginas se ligam umas às outras como as notas de um caderno. Um link é
desenhado na cor de destaque; clicar nele abre aquela página, e **Back**
retorna. Toda página termina com a lista das páginas que apontam para ela,
de modo que um assunto pode ser abordado a partir de qualquer ponta de
qualquer link.

A caixa de busca no alto da janela procura palavras por prefixo — digitar
`integr` encontra integration, integrated e integrator — e uma página só é
listada quando contém todas as palavras digitadas. O primeiro resultado é
aberto com Enter, e a página rola até a primeira ocorrência do termo
buscado.

## Em português

O manual também é escrito em português do Brasil. O seletor **English /
Português**, à direita da barra de ferramentas da janela do manual, muda o
idioma de tudo o que o manual é: a árvore do sumário, a página exibida, o
texto pelo qual a busca procura e a cópia que **Export as PDF…** gera. A
escolha é lembrada entre sessões. Uma página cuja tradução ainda não foi
escrita é mostrada em inglês com uma nota dizendo isso, para que o sumário
nunca tenha um buraco. O aplicativo em si — seus menus, botões, caixas de
diálogo e cabeçalhos de coluna — permanece em inglês, que é como o restante
deste manual o descreve.

## Convenções

- **Negrito** nomeia um controle como ele aparece na tela: um botão, uma
  entrada de menu, uma caixa de seleção. Os nomes dos controles ficam em
  inglês porque é assim que o aplicativo os exibe.
- `Código` é algo digitado, um nome de arquivo ou um valor exatamente como o
  aplicativo o mostra.
- Onde uma cifra é citada — uma porcentagem, uma contagem, um tempo — ela foi
  medida em dados reais, e a página diz em quais. Nada neste manual é a
  alegação de um fabricante repetida.
- Caminhos de menu são escritos assim: `File ▸ Export report…`.

## O que o MIL-Q não é

Não é um substituto certificado pelo fabricante para o MultiQuant em um
laboratório regulamentado. Existe uma [[audit-trail|trilha de auditoria]] —
cada edição feita à mão, com o valor antes e depois —, mas ela não carrega
assinatura eletrônica nem contas de usuário: registra o que foi feito e
quando, nunca quem o fez. E não reproduz exatamente a regra de extração da
própria SCIEX — veja [[measured-facts]] para o único ponto em que os dois
discordam, em quanto discordam e por que a regra simples é a que foi
distribuída. Todo o resto das listas de recursos dos dois programas do
fabricante está aqui, incluindo a [[spectral-library|busca em biblioteca
espectral]] e a [[mass-recalibration|recalibração de massa]], e os
[[design-principles]] dizem o que foi escolhido quando os dois não podiam
coexistir.

## Sem a janela

Tudo o que o aplicativo faz pode ser escrito em script: veja a [[python-api]]
para as versões de dez linhas de um lote reprocessado e exportado, de um
espectro explicado e de uma biblioteca buscada, e a [[command-line]] para o
que o próprio aplicativo responde na linha de comando.

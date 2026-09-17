---
title: Começar um projeto
---
## O aviso inicial

Quando a aplicação abre sem nenhum arquivo nomeado na linha de comando, ela
pergunta como começar: **New project…**, **Open project…**, ou explorar
arquivos brutos sem um projeto. O aviso não bloqueia a aplicação — dá para sair
por cima dele — e uma caixa de seleção faz com que ele não volte a aparecer; a
configuração fica guardada e só pode ser desfeita limpando as preferências.

## O assistente New project

`File ▸ New project…` (Ctrl+N) percorre o lote na ordem em que o trabalho
precisa dele.

**Project.** Um nome e uma pasta. O arquivo de projeto, `name.oqproj`, é
escrito quando o assistente termina, de modo que há um arquivo para salvar
desde a primeira alteração, em vez de um a lembrar de criar no fim.

**Samples.** Adicione os arquivos brutos. Cada um vira uma linha com o seu
arquivo, um nome de amostra encurtado, um tipo e um grupo; selecione linhas e
use **Set for selection** para lhes dar um tipo — Unknown, Standard, Quality
Control, Blank, Double Blank, Solvent — e um grupo de estudo em texto livre. Os
nomes são encurtados removendo o prefixo comum a todos os arquivos, de modo que
`demo_QC01` e `demo_STD_L1` viram `QC01` e `STD_L1`, e são diferenciados se
dois fossem colidir. Tudo isso pode ser mudado depois na [[samples-workspace]].

**Method.** De onde vem a tabela de componentes:

- **Import a component list (CSV)** — um arquivo no layout descrito em
  [[method-workspace]], com cabeçalhos em inglês ou em português.
- **Generate one component per product-ion channel of the samples** — o método
  de aquisição do primeiro arquivo é lido e cada experimento de íons produto
  vira um componente nomeado a partir do seu precursor. É assim que um método
  de oitenta transições entra sem ser digitado.
- **Start with an empty method** — e construí-lo na área de trabalho Method.

**Ready.** Um resumo do que será criado e quaisquer avisos — um arquivo que não
pôde ser aberto, um CSV sem nenhuma linha válida.

Quando o assistente termina, os arquivos são abertos, o projeto é escrito, e a
área de trabalho Analytics processa o lote se houver um método com que
processá-lo.

## Adicionar arquivos a um projeto aberto

`File ▸ Add data files…` (Ctrl+O) abre mais arquivos `.wiff` ou mzML na sessão
atual; `File ▸ Close all` fecha todos os arquivos e limpa os resultados. Os
arquivos adicionados assim aparecem na [[samples-workspace]] como Unknown até
que se diga outra coisa.

## Salvar

`File ▸ Save project` (Ctrl+S) escreve o `.oqproj`; `Save project as…` o
escreve em outro lugar. A barra de título traz um `•` enquanto houver algo não
salvo, e nada que descartaria a sessão — sair, fechar os arquivos, abrir outro
projeto — o faz sem antes oferecer salvar.

O que o projeto contém, e o que não contém, está em [[projects-and-files]].
Projetos salvos pelo programa sob o nome anterior, `.opvproj`, ainda abrem; os
novos são escritos como `.oqproj`.

## Abrir um projeto cujos arquivos mudaram de lugar

O projeto registra o caminho de cada arquivo bruto. Na abertura, um arquivo que
já não está lá é listado pelo nome e o projeto abre sem ele: as linhas dele
permanecem na tabela de amostras, marcadas como não carregadas, e os resultados
dele são mantidos. Devolva o arquivo ao lugar em que estava, ou adicione-o
novamente, e reprocesse.

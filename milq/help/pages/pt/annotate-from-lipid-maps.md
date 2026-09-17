---
title: Anotar a partir do LIPID MAPS
---
Uma tabela de componentes gerada a partir do método de aquisição nomeia cada
componente segundo seu precursor: `703.57`, `731.61`. **Annotate from LIPID
MAPS…** no [[method-workspace]] propõe um nome de espécie para cada componente
que ainda carrega um nome desses, e mostra as propostas para revisão antes que
algo seja gravado.

## Em que cada proposta se apoia

Para cada componente candidato, a massa do precursor é primeiro medida a partir
da varredura de survey (survey scan), como descreve [[accurate-precursor]] — no
momento em que a própria transição do componente atinge o pico, confirmada pelo
precursor sobrevivente na varredura de íons produto, e concordada entre as
amostras abertas. As colunas do diálogo dizem qual massa foi usada:

| Coluna | Significado |
|---|---|
| Use | marque para aceitar a proposta |
| Component | o componente como está nomeado agora |
| Mass used | a massa sobre a qual a busca foi feita |
| From | **survey** — medida a partir do scan TOF MS, buscada a ±10 ppm; ou **written** — o valor do próprio método, buscado na precisão com que foi escrito |
| ± window | a janela de busca que decorre disso |
| Species | a espécie proposta |
| Structures | quantas estruturas do LMSD compartilham essa espécie — uma massa não consegue separá-las |
| ppm | o erro entre a massa usada e o íon da espécie |

Um componente só é **oferecido para nomeação automática quando exatamente uma
espécie cabe na janela**. Onde duas cabem, a linha é marcada como ambígua e
deixada desmarcada; onde nenhuma cabe, isso é dito. Em uma tabela cujos
precursores carregam uma ou duas casas decimais, a maioria das linhas volta
marcada como *needs an accurate mass* em vez de adivinhada, porque naquela
precisão a janela contém várias espécies e a varredura de survey não conseguiu
medir o íon.

## O que é gravado

Aceitar uma proposta renomeia o componente para a espécie, preenche sua fórmula
e registra o LM_ID. O LM_ID viaja com o componente, para a exportação CSV e para
o projeto, de modo que a anotação possa ser rastreada até o registro do banco de
dados de onde veio.

Nada mais muda: o precursor permanece como escrito, porque a massa medida é uma
medição deste lote e o valor do método é o que foi dito ao instrumento para
isolar.

## Aduto

O diálogo assume [M−H]⁻ — modo negativo — a menos que se diga o contrário; a
mesma lista de adutos da [[mass-calculator]] está disponível.

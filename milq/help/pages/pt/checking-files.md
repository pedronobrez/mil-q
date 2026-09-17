---
title: Verificar os arquivos antes de abri-los
---
A maior parte do que dá errado numa pasta de aquisições é visível nos nomes
dos arquivos, antes de qualquer coisa ser lida. *File ▸ Check a folder…*
(verificar uma pasta) olha, e acrescentar arquivos também: quando a
verificação encontra algo, isso é mostrado primeiro e nada é aberto até que
você diga que sim.

Nada é aberto pela própria verificação. Ela lista a pasta, pergunta se cada
arquivo existe e pode ser lido, e diz o que encontrou — nenhum arquivo é
decodificado, de modo que uma pasta com cem aquisições é verificada no tempo
que leva para listá-la.

## O que ela procura

| Achado | O que significa | O que fazer |
|---|---|---|
| um `.wiff` sem um `.wiff.scan` ao lado | a aquisição abre e parece inteira — método, lista de amostras, o cromatograma de cada canal — e todo espectro, cromatograma de íon extraído e integração falha. Ver [[formats]] | reponha o companheiro; se a pasta contiver um avulso, a linha abaixo oferece a renomeação |
| um `.scan` que não pertence a nenhum `.wiff` da pasta | em geral o companheiro de um destes arquivos, renomeado à mão: `name.wiff_mix1.scan` ao lado de `name_mix1.wiff` | **Rename** para o nome que o `.wiff` procura |
| arquivos `.wiff2` | o método da aquisição e os hashes dos seus dois companheiros — medido como não contendo espectro, pico ou cromatograma algum, e não lido aqui. Ver [[formats]] | nada, quando o `.wiff` de mesmo nome está ao lado: ele contém a mesma aquisição e é o que é aberto. Sem nenhum `.wiff` ao lado, a aquisição não pode ser aberta, e o `.wiff2` não pode substituí-lo |
| arquivos no formato de outro fabricante | `.raw`, `.d`, `.tdf` e os demais não são lidos aqui | converta-os para mzML com o `msconvert` do ProteoWizard |
| um arquivo já aberto | acrescentá-lo de novo poria uma segunda cópia de cada amostra no lote | ele fica de fora; feche o lote primeiro para lê-lo outra vez |
| um arquivo que não pode ser lido, ou que não está lá | permissões, ou um arquivo que mudou de lugar depois de ter sido nomeado | corrija as permissões, ou acrescente-o de novo de onde ele está agora |

## A renomeação, e por que ela é um palpite

Qual `.scan` avulso pertence a qual `.wiff` não pode ser *sabido* de fora dos
arquivos. Os dois são grandes, o nome de nenhum contém o do outro, e nada em
nenhum dos nomes precisa coincidir. O emparelhamento oferecido aqui é aquele
cujo nome é mais parecido — a maior sequência de caracteres compartilhada no
começo e no fim, comparada contra o companheiro que falta a cada `.wiff` — e
ele é rotulado como palpite onde quer que apareça.

Por isso a renomeação nunca é executada por conta própria. Selecione a linha,
pressione **Rename…**, e uma pergunta nomeia por extenso o arquivo antigo e o
novo antes de qualquer coisa acontecer. Um arquivo que já carrega o nome novo
nunca é sobrescrito: a renomeação é recusada e diz isso, porque um
`.wiff.scan` que já está lá ou é o certo — caso em que o avulso pertence a
outra coisa — ou é o errado, e nenhum dos dois vale ser perdido para um
palpite. Depois de uma renomeação a pasta é verificada de novo, de modo que a
linha que dizia faltar um companheiro desaparece se era esse o reparo.

## Abrir mesmo assim

**Open anyway** (abrir mesmo assim) abre o que a verificação achou que pode
ser aberto: todo arquivo suportado que existe, pode ser lido e ainda não está
no lote. Um `.wiff` cujo companheiro continua faltando também é aberto — os
seus cromatogramas valem ser olhados, e a amostra carrega o motivo de os seus
espectros não poderem ser lidos onde um espectro estaria. **Cancel** não abre
nada.

A mesma verificação roda quando arquivos são acrescentados por *File ▸ Add
data files…*, e ela fica fora do caminho: uma pasta sem nada a relatar abre
direto. Ver [[projects-and-files]] para o que um projeto contém e
[[troubleshooting]] para sintomas depois de um arquivo estar aberto.

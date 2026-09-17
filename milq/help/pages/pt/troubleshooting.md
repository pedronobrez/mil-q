---
title: Solução de problemas
---
A barra de status costuma dizer por que algo não aconteceu. Quando não diz,
esta tabela é o próximo lugar a olhar; uma palavra dela que não lhe diga
nada está no [[glossary]].

## Abrir arquivos

| Sintoma | Olhar em |
|---|---|
| Um `.wiff` não abre; *SCIEX libraries: unavailable* | rode `MIL-Q --selftest file.wiff` para saber o motivo. A partir do código-fonte, `python3 -m milq.bootstrap --install` busca o runtime .NET e os assemblies. Ver [[how-wiff-is-read]] |
| O cromatograma abre mas o painel do espectro fica vazio — nada scan a scan, nada para um intervalo selecionado — e um XIC ou *Extract and integrate all* não dá nada | o `.wiff.scan` não está ao lado do `.wiff`, ou tem outro nome. A amostra é marcada com *⚠* na árvore, com o motivo ao passar o cursor, e o título do painel diz qual arquivo está faltando, nomeando qualquer `.scan` na pasta que não pertença a nenhum `.wiff` de lá; renomeie-o para `name.wiff.scan` e abra o arquivo de novo — *File ▸ Check a folder…* encontra isso antes de qualquer coisa ser aberta e oferece a renomeação, ver [[checking-files]] e [[formats]] |
| Uma pasta contém arquivos `.wiff2`, ou `.raw` ou `.d` de outro fabricante, e eles nunca aparecem | não são lidos aqui; o `.wiff` ao lado de um `.wiff2` contém a mesma aquisição, e os demais convertem-se para mzML. *File ▸ Check a folder…* diz quais arquivos de uma pasta serão ignorados. Ver [[checking-files]] |
| Windows: *DLL load failed while importing QtCore* | a máquina é anterior ao Windows 10 1703, ou a build está rodando sob o Wine — ver [[installation]] |
| macOS: *"MIL-Q" cannot be opened* | a marca de quarentena; clique com o botão direito e Abrir, ou `xattr -dr com.apple.quarantine /Applications/MIL-Q.app` |
| Um projeto abre com arquivos listados como faltando | eles mudaram de lugar; devolva-os ou adicione-os de novo do mesmo lugar, e reprocesse. Ver [[starting-a-project]] |
| Um mzML tem o número errado de canais | o arquivo não tem ciclo repetido e os canais foram inferidos apenas a partir das propriedades dos scans. Ver [[formats]] |
| Um espectro de mzML parece ter a linha de base elevada | o arquivo está centroidado, ou os zeros não puderam ser restaurados. Ver [[chromatograms-and-spectra]] |

## Integração

| Sintoma | Olhar em |
|---|---|
| *no matching channel* | nenhum canal carrega o precursor dentro de 0.7 Da com o alvo na faixa e, se houver um tempo definido, adquirido naquele tempo. Ver [[method-workspace]] |
| *channel does not cover 5.10–6.10 min* | o canal não foi adquirido sobre a janela; o tempo de retenção ou o canal está errado |
| *only 4 points to detect in* | a janela é mais estreita que a amostragem; alargue-a — [[suggest-from-data]] calcula a largura |
| *no peak above noise* em um painel que visivelmente mostra um pico | os portões: Min. height relativa ao mais alto do intervalo, ou Min. S/N. Ver [[integration-parameters]] |
| Foi tomado o pico errado entre dois | mude **Peak** para *nearest the expected RT*, e aumente Min. height se a janela estiver cheia de picos pequenos |
| S/N mostra `—` | a linha de base não pôde ser medida, o que é normal em uma aquisição agendada. Ver [[signal-to-noise]] |
| *Gaussian fit not possible* | o pico tem menos de três pontos nos flancos; a área do valley permanece. Ver [[integration-algorithms]] |
| As áreas diferem entre um `.wiff` e o seu mzML | esperado, cerca de meio por cento; verifique que não são cinquenta. Ver [[formats]] |
| Uma linha que integrei à mão fica voltando | ela é mantida de propósito; botão direito no painel → *Back to automatic integration* |

## Calibração e revisão

| Sintoma | Olhar em |
|---|---|
| *No curve yet* | nenhuma amostra tipada como Standard com uma concentração, ou menos do que a regressão precisa. Ver [[calibration]] |
| Todo status está vazio | nenhum critério de aceitação está definido; isso não é uma aprovação. Ver [[acceptance-criteria]] |
| Um padrão interno mostra um problema na coluna IS | o nome não corresponde a um componente, ou esse componente não está marcado como IS. Ver [[internal-standards-and-qualifiers]] |
| O Batch QC diz que a ordem é a ordem de abertura | alguns arquivos não trazem tempo de aquisição |
| Todo padrão interno está sinalizado | olhe a resposta mediana deles; padrões de umas poucas contagens não conseguem normalizar nada. Ver [[batch-qc]] |

## A aplicação

| Sintoma | Olhar em |
|---|---|
| A aplicação não fecha | há um diálogo modal aberto em algum lugar, possivelmente atrás da janela |
| *All components* na grade está lento | ele extrai cada traço de cada componente; pagina conforme avança, e um lote real leva cerca de cem segundos para a primeira página |
| O relatório sai em branco ou minúsculo | não deveria — esse bug está corrigido e testado; se voltar a ocorrer, o visualizador de PDF é o próximo suspeito. Ver [[report]] |
| O download do LIPID MAPS falha | a rede, ou um repositório de certificados que o `certifi` empacotado não conhece; o arquivo pode ser colocado à mão em `~/.milq/lipidmaps/` |
| Duas builds dão números diferentes | rode `--digest` nas duas e compare; a build de Windows escreve CRLF. Ver [[command-line]] |

## Relatar um problema

O repositório é `github.com/pedronobrez/mil-q`. A saída de `--selftest` no
arquivo em questão, a versão, a plataforma e o arquivo de projeto — nunca os
dados brutos, que são seus — são o que uma issue precisa.

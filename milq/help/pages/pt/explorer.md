---
title: A área de trabalho Explorer
---
O Explorer é onde os dados brutos são examinados antes de qualquer
quantificação: a corrida inteira, um canal por vez, um scan por vez. Foi
construído como o PeakView é — um cromatograma acima, um espectro abaixo, e
ao redor as coisas que se quer fazer com qualquer um dos dois.

## Disposição

**Samples and channels** (amostras e canais; doca à esquerda, Ctrl+Shift+S)
é uma árvore dos arquivos abertos. Cada amostra lista um nó *Sample TIC* —
o cromatograma de íons totais (TIC) da corrida — e todos os canais de
aquisição do seu método, rotulados com o nome do experimento, o precursor, a
faixa de massas e a energia de colisão. Marcar um canal o desenha; o seletor
**Active channel** (canal ativo) no alto da janela diz de que canal vêm o
painel de espectro e os cromatogramas de íon extraído.

Acima da árvore: uma caixa de **filter** (filtro; digitar `313.2` mantém
apenas os canais que mencionam essa massa), **Uncheck all** (desmarcar
tudo), **TOF MS only** (marcar as varreduras de survey e nada mais) e
**Collapse all** (fechar todas as amostras — um método TripleTOF tem oitenta
canais por amostra).

**Panels** (painéis; doca à direita, Ctrl+Shift+P) contém as abas laterais,
cada uma alcançável por Ctrl+Shift+1 em diante ou pelo menu **Panels**:

| Aba | O que faz | Página |
|---|---|---|
| Components | a lista de componentes do método, somente leitura, com *Extract and integrate all* | [[explorer-components-and-results]] |
| Results | o que foi integrado aqui, ordenável e exportável | [[explorer-components-and-results]] |
| Manual XIC | extrai qualquer massa com uma tolerância | [[manual-xic]] |
| Spectrum peaks | os picos do espectro em tela; duplo clique em um deles dá seu XIC | [[chromatograms-and-spectra]] |
| Mass calc | massas exatas, adutos, padrões isotópicos | [[mass-calculator]] |
| Formula finder | composições para uma massa medida | [[formula-finder]] |
| LIPID MAPS | lipídios para uma massa, massas para um lipídio, fragmentos e a explicação de um espectro | [[lipid-maps]] |
| Library | o espectro em tela pesquisado contra uma biblioteca espectral MSP ou MGF | [[spectral-library]] |
| Sample | os metadados da própria aquisição | [[sample-information]] |

O centro contém o painel do cromatograma e, sob ele, o painel do espectro;
**View** no alto alterna o painel superior entre o cromatograma e o
[[contour-view]]. **TIC / BPC** escolhe o que os canais marcados desenham: a
corrente iônica total de cada scan ou o seu pico base.

## Barras de ferramentas

**Main.** *Select range* faz o arraste selecionar em vez de ampliar (manter
Shift durante o arraste faz o mesmo sem a troca); *Fit* reescala os dois
painéis; *Add marker* e *Clear markers* colocam marcas de referência sobre o
espectro.

**View.** *Normalise* escala cada traço pelo seu próprio máximo; *Mirror*
inverte um traço sim, outro não, amostra contra branco; *Stack* dá a cada
traço o seu próprio painel com os eixos de tempo travados; *Overview*
acrescenta sob o cromatograma um navegador que mostra a faixa inteira e onde
está a ampliação atual; *Labels* anota os picos do espectro com o seu m/z;
*RT labels* anota os ápices do cromatograma; *Relative labels* rotula os
picos do espectro pela sua distância a um marcador; *Legend* nomeia os
traços. **Cascade x / y** deslocam os traços sobrepostos ao longo do tempo e
na vertical, em minutos e em por cento.

**Processing.** *Smooth (σ, scans)* e *Baseline (min)* condicionam cada
traço — para o desenho, para a integração e para a exportação igualmente, de
modo que uma área sempre corresponde ao que está na tela; *Centroid*
transforma um espectro em perfil em bastões; *Set background* toma a faixa
selecionada do cromatograma como branco e subtrai o seu espectro médio de
todo espectro mostrado; *Explain spectrum* pontua candidatos do LIPID MAPS
contra o espectro (ver [[lipid-maps]]); *Detect peaks* integra todos os
traços do cromatograma e preenche a aba Results; *Average whole run* promedia
todos os scans do canal ativo num único espectro, e *Δ from average* — apenas
numa infusão — desenha o scan em tela menos essa média, com a média espelhada
por baixo (ambos ver [[direct-infusion]]).

## Os controles de scan

**Scan** é o número do scan cujo espectro é mostrado, sendo 1 o primeiro
ciclo do canal ativo; as setas avançam por eles, e as teclas ← e → também; o
tempo de retenção do scan é mostrado ao lado. **Average selected range**
substitui o espectro de um único scan pela média sobre a faixa marcada no
cromatograma, e *Average whole run*, na barra de ferramentas Processing,
promedia todos os scans do canal ativo — que é como uma [[direct-infusion]]
é aberta.

## Convenções de mouse

Nos dois painéis: arrastar = ampliação por laço, duplo clique = ajustar,
clique direito = o menu do próprio gráfico (exportar como imagem, opções de
eixo), Shift+arrastar = selecionar uma faixa. Um clique simples no
cromatograma mostra o espectro daquele scan. O conjunto completo de gestos
está em [[chromatograms-and-spectra]].

## Exportações

No menu **File**: os cromatogramas em tela como CSV, o espectro em tela como
CSV e a amostra selecionada como mzML (ver [[formats]]).

## Abrir arquivos aqui

Arquivos abertos pelo Explorer, pela área de trabalho Samples ou pelo menu
File são os mesmos arquivos: a árvore aqui, a tabela do lote lá. Os arquivos
são lidos do disco uma única vez e todas as áreas de trabalho compartilham o
leitor.

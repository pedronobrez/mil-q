---
title: A área de trabalho Samples
---
A área de trabalho Samples (Ctrl+4) é a tabela do lote: uma linha por injeção,
com tudo o que o arquivo bruto não registra sobre ela. Um `.wiff` reporta toda
injeção como `kUnknown`, de modo que o papel de cada uma — padrão, controle,
branco, desconhecida —, a sua concentração e a sua diluição vivem aqui e são
salvos com o projeto.

## Colunas

| Coluna | Significado | Editável |
|---|---|---|
| Batch order | o lugar da injeção na corrida, 1 para o primeiro frasco que o instrumento tomou; vazio até alguém numerá-la. Onde está preenchido, decide a ordem de toda carta ao longo da corrida — veja *Ordem* abaixo | sim |
| File | o nome do arquivo bruto | não |
| Sample | o nome exibido; encurtado a partir do nome do arquivo removendo o prefixo comum a todos os arquivos | sim |
| Type | o papel da amostra, ver abaixo | sim |
| Group | o grupo do estudo — controle, tratado, dia 7; texto livre, porque nenhum vocabulário serve a todo estudo | sim |
| Actual conc. | a concentração esperada, para padrões e controles de qualidade; na unidade de concentração do método | sim |
| Dilution | o fator pelo qual a concentração reportada é multiplicada, porque a curva descreve o frasco que foi injetado e a resposta desejada é a da amostra original | sim |
| Vial | vindo do arquivo | não |
| Acquired | a data e hora da aquisição, vindas do arquivo — o que coloca as injeções na ordem em que o instrumento as executou | não |
| Comment | texto livre | sim |

**Add data files…** e **Close all** são as mesmas ações do menu File.

## Editar várias linhas de uma vez

| Controle | O que faz |
|---|---|
| **Set type of selected rows** ▸ **Apply** | o tipo escolhido em cada linha selecionada |
| **Set group** ▸ **Apply** | o grupo digitado em cada linha selecionada; a caixa oferece os grupos já presentes no lote |
| **Apply concentration to selection** | copia a concentração da primeira linha selecionada para as demais linhas selecionadas — um conjunto de padrões injetados num mesmo nível |
| **Set dilution** ▸ **Apply** | um fator de diluição em cada linha selecionada; precisa ser um número acima de zero, e qualquer outra coisa é recusada com uma mensagem em vez de lida como 1 (`Enter` na caixa também aplica) |
| **Batch order** ▸ **Number in table order** | 1, 2, 3… descendo a tabela |
| **Batch order** ▸ **Number by acquisition time** | 1, 2, 3… pelo tempo que cada arquivo carrega; arquivos sem tempo são numerados por último, na ordem da tabela, e a mensagem diz quantos |
| **Batch order** ▸ **Clear batch order** | remove o número |
| **Sort by batch order** | coloca as próprias linhas na ordem da corrida |

As opções de **Batch order** agem sobre as linhas selecionadas, ou sobre
todas quando nenhuma está selecionada. Numerar todas as linhas começa em 1.
Uma seleção mantém o lugar que já tinha — renumerar as linhas 5 a 9 recomeça
em 5 — e uma seleção ainda sem números segue o maior número existente no
resto do lote, de modo que numerar um trecho nunca dá por acidente o mesmo
número a duas linhas.

Selecionam-se linhas com um clique, `Shift`-clique para um intervalo e
`Ctrl`-clique (`⌘`-clique no Mac) para acrescentar uma.

### Colar de uma planilha

Uma coluna copiada de uma planilha é colada na tabela com `Ctrl+V` (`⌘V`):
clique na primeira célula a preencher e cole, e os valores descem pela coluna
a partir dali, um por linha. Um bloco de várias colunas preenche também para
a direita. Um único valor colado com várias linhas selecionadas vai para
aquela coluna de cada linha selecionada.

Cada célula colada é aceita exatamente como se tivesse sido digitada: uma
diluição zero, uma ordem 2,5 ou uma concentração que não é número fica como
estava, e a mensagem conta as células aceitas e as deixadas. Um tipo é
reconhecido pelo nome, sem distinguir maiúsculas — `blank` é Blank. As
colunas File, Vial e Acquired vêm do arquivo e são puladas.

Cada valor alterado, uma linha por vez ou muitas de uma vez, é uma linha na
[[audit-trail]]: a amostra, o campo, o que era e o que passou a ser. Um valor
reposto ao que já era não registra nada.

As colunas que o arquivo *de fato* registra — o frasco, o volume de injeção, o
método de aquisição, o potencial de desagrupamento — são somente de leitura e
aparecem no Explorer: veja [[sample-information]].

## Tipos de amostra e o que os usa

| Tipo | Usado por |
|---|---|
| Unknown | reportada contra a curva; na carta de controle de um padrão interno |
| Standard | define a curva de [[calibration]], com a sua Actual conc.; o padrão mais baixo e o mais alto ancoram [[detection-limits-and-carryover]]; na carta de controle |
| Quality Control | o conjunto de réplicas para a precisão de [[batch-qc]] e para [[compare-algorithms]]; pontuada quanto à exatidão contra a sua Actual conc.; na carta de controle |
| Blank | contada como branco para carryover (arraste); na carta de controle, já que carrega o padrão interno |
| Double Blank | um branco extraído sem o padrão interno: um branco para carryover, **não** na carta de controle |
| Solvent | uma injeção de solvente: um branco para carryover, **não** na carta de controle |

A distinção nos dois últimos é deliberada. Plotar na carta de um padrão uma
injeção que nunca viu esse padrão interno coloca um zero no meio da corrida e
faz um lote íntegro parecer ter perdido o padrão duas vezes.

## Grupos

Um grupo é o que o estudo chamar de grupo. A página [[statistics]] pode agrupar
por ele, o [[metric-plot]] pode colorir por ele, e a seção de estatística do
relatório pode ser disposta por ele. Uma amostra sem grupo está em nenhum
grupo: ela cai fora de um resumo por grupo em vez de ser reunida em um grupo
fantasma "sem rótulo".

## Ordem

As linhas ficam na ordem em que os arquivos foram abertos até que **Sort by
batch order** as coloque na ordem da corrida; a lista de amostras do Explorer
e o próximo processamento seguem a tabela.

A ordem da corrida — o que leem as cartas de [[batch-qc]], a tendência de
[[mass-drift]], o eixo de ordem de injeção do [[metric-plot]] e o branco após
o padrão mais alto em [[detection-limits-and-carryover]] — é decidida assim:

1. **Toda injeção tem batch order**: a batch order. A carta diz *in batch
   order*.
2. **Nenhuma tem**: os tempos de aquisição que os arquivos carregam, como
   antes; um arquivo sem tempo vai por último, na ordem de abertura. A carta
   diz *in acquisition order*, ou, quando alguns arquivos não trazem tempo,
   que a sequência é um palpite.
3. **Algumas têm**: primeiro as injeções numeradas, pelo número, depois as
   outras pelo tempo de aquisição. Nada é encaixado *entre* duas injeções
   numeradas, porque os números e o relógio são duas afirmações que não
   precisam concordar, e intercalá-los faria a ordem depender de em qual se
   acreditou a cada passo. A carta diz quantas injeções foram numeradas, e
   que essa não é a ordem da corrida até que todas sejam.

Duas injeções com o mesmo número ficam na ordem dos seus tempos de aquisição,
depois na ordem de abertura.

A batch order é digitada, não lida: um `.wiff` carrega a hora em que a
injeção foi adquirida, mas não a sua posição na sequência, e um mzML
convertido em outro lugar pode não carregar nenhuma das duas. É o que usar
quando o relógio está errado, quando um arquivo foi readquirido depois, ou
quando os arquivos vieram sem tempos. É salva com o projeto, e um projeto
salvo antes dela existir abre sem batch order em nenhuma linha. A tabela de
amostras do [[report]] e a planilha Samples da pasta de trabalho exportada a
trazem como primeira coluna.

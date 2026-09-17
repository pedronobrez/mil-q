---
title: Vista de contorno
---
**View ▸ Contour** no topo do [[explorer]] desenha o canal ativo como uma
superfície: tempo de retenção na horizontal, m/z na vertical, intensidade como
cor. Um cromatograma soma e elimina o eixo de massa e um espectro soma e elimina
o eixo de tempo; o contorno são os mesmos dados sem nenhum dos dois somados, de
modo que uma interferência situada ao lado de um alvo, ou uma crista percorrendo
toda a corrida em uma massa, é visível em vez de inferida.

## O que é desenhado

Cada scan do canal é uma linha e cada bin de m/z uma coluna. O eixo de massa é
dividido em cerca de 1,400 bins — grosso modo um por pixel de tela ao longo de
uma faixa ampla; mais fino do que isso a figura é a mesma, apenas mais lenta.
Uma corrida longa tem mais scans do que uma tela tem linhas, e os scans acima do
limite de cerca de 900 linhas são **promediados em sua linha, não pulados**:
amostrar cada k-ésimo scan é mais rápido e perde inteiramente um pico de um
único scan, o que é o oposto daquilo para que serve uma figura dos dados. A
média em vez da soma, porque o último grupo em geral é curto e uma linha que
fica mais escura apenas por isso seria uma mentira sobre os dados.

Os espectros são tomados sem seus zeros restaurados: um histograma de
intensidades não pode ser alterado pelo acréscimo de pontos de intensidade zero,
e restaurá-los foi medido como triplicando o tempo para a mesma grade.

## Controles

| Controle | Efeito |
|---|---|
| **Intensity** | como as intensidades viram cor: *sqrt* (padrão), *log* ou *linear*. Uma rampa linear sobre quatro décadas mostra o pico base e mais nada; a raiz quadrada traz os íons menores à vista sem o achatamento que faz um gráfico logarítmico parecer uniformemente cinza |
| **Colours** | a paleta: inferno, viridis, magma, turbo, CET-L9 |
| **Extract this view** | o cromatograma e o espectro do retângulo na tela — ambos tomados do leitor, não da grade |
| **Rebuild** | reconstruir a grade sobre a faixa atualmente na tela, em resolução plena para aquela faixa |
| clicar | o espectro do scan sob o cursor, no painel de espectro |
| leitura | o tempo de retenção, o m/z e a intensidade sob o cursor |

O topo da escala de cor é o percentil 99.7 das intensidades, não o máximo: um
único scan saturado ou com um pico espúrio de outro modo definiria a escala para
todo o resto e deixaria o restante da superfície preto.

## Uma infusão como filme

Numa amostra lida como [[direct-infusion]] a mesma superfície é um filme. Não
há cromatografia, de modo que nada se move ao longo do eixo de tempo exceto a
própria pulverização: um fragmento é uma **crista em m/z constante percorrendo
toda a extensão da corrida**, e um transiente de pulverização é uma **coluna
brilhante da largura de um scan**. A média a partir da qual uma infusão é lida
esconde os dois, que é para isso que serve o filme.

Três coisas aparecem, e apenas numa infusão:

| | |
|---|---|
| **a faixa** | o cromatograma de íons totais do próprio canal, um ponto por scan, no eixo de tempo da superfície. É o cromatograma do instrumento, não uma linha da grade: as linhas da grade podem ser vários scans promediados e seus bins de m/z são mais largos que os passos do instrumento |
| **as marcas ✕** | os scans deixados de fora da média, marcados na faixa e sombreados na superfície |
| **Play** | percorre o painel de espectro por todos os scans da corrida, a dez scans por segundo vezes a velocidade ao lado (1×, 5×, 20×). Pressione de novo para pausar; ele para sozinho no último scan, e iniciá-lo ali recomeça do primeiro |

O cursor tanto na faixa quanto na superfície é o scan que o painel de espectro
está mostrando, venha ele de onde vier — do Play, dos botões ◀ ▶, das setas do
teclado, do número do scan ou de um clique na superfície.

### O que ele mostrou nas infusões reais

Duas infusões de ácidos biliares em ZenoTOF 7600, um canal de íons produto
cada, um scan a cada 0.25 s:

| | `DCA-d4_TOFMSMS_Mix1` | `CA-d4_…EAD_22CE…_mix1` |
|---|---|---|
| scans, duração | 473, 1.98 min | 146, 0.62 min |
| a grade | 473 linhas × 1,400 bins | 146 × 1,400 |
| scans promediados por linha | nenhum — 473 está abaixo do limite de 900 linhas | nenhum |
| construída e desenhada | 1.4 s | 0.8 s |
| deixados de fora da média | 4 scans (o primeiro segundo) | 4 scans |
| o scan mais alto | **4.38×** a mediana da corrida | 1.04× |

`DCA-d4_TOFMSMS_Mix1` é o arquivo contra o qual a regra de infusão foi
escrita, e o filme é onde seus três transientes ficam visíveis em vez de
estatísticos: o scan 2 em 0.0084 min a 4.38 vezes o total mediano, e mais dois
no meio da corrida em 1.0819 e 1.0988 min a 2.40 e 4.36 vezes. Os três se leem
na faixa como picos e na superfície como colunas brilhantes, e como aqui nenhum
scan é agrupado numa linha os próprios totais de linha da grade carregam as
mesmas três razões — 4.38, 2.40 e 4.36. O outro arquivo não tem transiente
algum: seu scan mais alto é 1.04 vezes sua mediana, e sua faixa é uma banda
plana.

**O Play roda na velocidade em que o arquivo consegue ser desenhado.** O
temporizador pede um scan a cada 100 ms em 1×, 20 ms em 5× e 5 ms em 20×; um
quadro — ler o scan, desenhá-lo, rotulá-lo — foi medido em **52 ms** no
`DCA-d4_TOFMSMS_Mix1` e **89 ms** no arquivo CA-d4 EAD. Assim 1× roda como
pedido — dez scans por segundo são duas vezes e meia o tempo real num ciclo de
0.25 s, e a corrida de 473 scans dá 47 segundos de filme — enquanto 20× chega
a cerca de dezenove scans por segundo em vez de duzentos. Um tique que chega
enquanto o anterior ainda está desenhando é descartado, de modo que o filme
fica mais lento em vez de ficar atrasado em relação a si mesmo. Esses
números são o que são porque o painel de espectro **não é reescalonado
enquanto o Play está rodando** — a escala fica onde estava, de modo que o que
se move na tela são os dados e não os eixos. Com o reescalonamento, os mesmos
dois quadros custaram 245 ms e 880 ms.

## Nada é quantificado a partir do contorno

Seus bins de m/z são mais largos que os passos do instrumento e suas linhas
podem ser vários scans promediados, de modo que ele é uma figura,
deliberadamente. *Extract this view* volta ao leitor tanto para o XIC quanto
para o espectro, e são esses que o [[manual-xic]] e a aba Results utilizam.

A leitura sob o cursor busca as bordas dos bins para a direita, porque é ali que
um valor situado exatamente sobre uma borda é colocado pelo histograma; buscar
para a esquerda lê a célula ao lado e a leitura discorda da figura — apanhado
por um teste, não a olho nu.

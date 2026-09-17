---
title: A área de trabalho Method
---
A área de trabalho Method (Ctrl+3) é a tabela de componentes — o equivalente
da tabela de componentes do MultiQuant. Um componente diz o que extrair
(precursor, fragmento, tolerância), onde o pico é esperado (tempo de
retenção e meia janela) e como o seu resultado é reportado (área, razão a um
padrão interno, ou concentração).

## Colunas

| Coluna | Significado |
|---|---|
| Name | o nome do componente; como ele é referido em todo o resto |
| Group | um agrupamento em texto livre — ceramidas, esfingomielinas — que dobra a árvore de componentes em Analytics e permite aplicar parâmetros de integração a um grupo de uma vez |
| Precursor | o m/z do precursor; o canal é associado por ele |
| Fragment | o íon produto extraído; vazio significa que o próprio precursor é extraído |
| RT | o tempo de retenção esperado em minutos; vazio significa que a corrida inteira é pesquisada |
| ± RT | a meia janela: o ápice tem de cair dentro de RT ± isto. O padrão é 0.5 min |
| Tol. e Unit | a meia largura da janela de massa, em Da ou ppm; o padrão do método quando deixado em branco |
| Formula e Adduct | opcionais; com os dois e sem precursor, o precursor é calculado — `C18H30D4O4` com [M−H]⁻ é como um padrão marcado é inserido. Com os dois, um padrão interno também pode ser uma lock mass para a [[mass-recalibration|recalibração de massa]]; o *Fill formulas from names* os preenche a partir dos nomes, ver abaixo |
| IS | marcado quando o componente **é** um padrão interno |
| Internal standard | o nome do padrão interno contra o qual este componente é reportado |
| Response | o que a tabela de resultados reporta: `area`, `ratio` ao padrão interno, ou `concentration` |
| Conc. unit | a unidade de concentração mostrada para este componente, quando difere da do método |
| Qualifier of | o quantificador que esta transição confirma, quando ela é um qualificador |
| Ion ratio % e ± ratio % | a razão de áreas qualificador/quantificador esperada, e a tolerância que sobrepõe a do método |
| Min. response | para um padrão interno: a menor área que ele tem de dar em uma injeção antes que uma razão a ele signifique alguma coisa — ver [[internal-standards-and-qualifiers]] |
| Provenance | não é uma coluna: de onde a linha veio, mostrado na dica de tela da célula Name — veja abaixo |

As colunas de padrão interno e de qualificador são explicadas em
[[internal-standards-and-qualifiers]].

### De onde veio a linha

Uma linha escrita pelo **Use in method…**, na aba Infusions, carrega a sua
procedência: de qual infusão foi lida, o canal, a energia de colisão, o
arquivo, a hora de aquisição e o registro da sua própria biblioteca com que o
espectro bateu. Ela não tem coluna — é uma frase, e uma coluna de frases é uma
tabela que ninguém lê — então aparece na **dica de tela da célula Name**,
embaixo do nome, e é salva com o projeto e escrita no CSV como `provenance`.
Uma linha que você digitou não carrega nenhuma, que é a resposta verdadeira
para ela: a dica é então só o nome. Nada no programa decide nada com base
nesse texto; ele está ali para quem for ler o método daqui a seis meses, e o
[[infusion-report]] descreve o que o escreve.

## Construir a tabela

- **Add** e **Remove** editam linhas à mão.
- **Generate from acquisition method** lê o método da primeira amostra aberta
  e faz um componente por canal de íons produto, nomeado a partir do seu
  precursor, com o precursor e a faixa de massas que o canal declara. Um
  método de oitenta transições chega em um clique; nomeá-lo é para o que
  serve [[annotate-from-lipid-maps]].
- **Import CSV…** e **Export CSV…** leem e escrevem a tabela como uma
  planilha, ver abaixo.
- **Export for Skyline…** escreve o método como uma lista de transições de
  moléculas pequenas, ver [[export]].
- **Suggest from data…** propõe tempos de retenção e larguras de janela a
  partir das injeções abertas, ver [[suggest-from-data]].
- **Check method** lê o método contra si mesmo e contra os arquivos abertos,
  ver [[check-method]].
- **Method report…** escreve tudo isso, mais as fórmulas, os candidatos a
  lock mass, o canal que serve cada componente e o agendamento que o método
  implica, como um só documento PDF ou HTML: [[method-report]].
- **Annotate from LIPID MAPS…** propõe nomes de espécie, ver
  [[annotate-from-lipid-maps]].
- **Fill formulas from names** lê a notação abreviada de lipídios que os
  nomes já carregam e preenche com ela as células Formula vazias, ver
  abaixo.
- **Repair precursors…** é a saída daquilo que aquele recusa: onde uma
  fórmula e o precursor escrito ao lado dela discordam, ele oferece a massa
  da fórmula para o precursor, linha por linha — e, onde os dois estão a um
  dalton inteiro e a massa é a que o instrumento adquiriu, ele oferece em vez
  disso os nomes cuja fórmula corresponde àquela massa, ver abaixo.
- **Export schedule…** escreve a aquisição agendada que o método implica, com
  o dwell time que um ciclo alvo deixa a cada transição, ver
  [[acquisition-schedule]].

Uma linha também pode chegar de um frasco, e não desta tabela: **File ▸ New
standard…** recebe um nome, um número de lote e uma infusão daquele padrão e
escreve o componente aqui — fórmula, aduto, precursor exato, fragmento,
procedência — junto com o registro na sua própria biblioteca que lhe dá um
histórico. Veja [[new-standard]].

## Fill formulas from names

Uma fórmula é o que transforma um componente numa lock mass para a
[[mass-recalibration|recalibração de massa]], e um método que nomeia os seus
componentes em notação abreviada de lipídios já disse do que eles são feitos.
O **Fill formulas from names** faz a aritmética: `SM(d18:1/12:0)`,
`Cer(d18:1/16:0)`, `PC 34:1`, `LPC 18:0`, `TG 52:2`, `FA 18:1`, a classe
escrita depois da cadeia (`C16:0-Ceramide`, `C14_SM`), uma hidroxila como
`h24:0`, `(2OH)` ou `;O3`, uma posição de dupla ligação entre parênteses que
nada diz sobre a composição, e deutério não posicionado como `-d4`, `d7` ou
`(d9)`.

Três regras tornam seguro apertá-lo:

- **somente as células vazias são preenchidas.** Uma fórmula que alguém
  digitou é do método; uma leitura de um nome é um palpite sobre ele.
- **nada mais se move** — em particular nenhum precursor. Uma fórmula e um
  aduto podem substituir um precursor quando uma linha é digitada à mão, e
  aqui não podem: o precursor é aquilo contra o qual isto foi conferido, e
  movê-lo moveria cada janela de extração do lote sem que ninguém pedisse.
- **o precursor tem de concordar.** A massa da fórmula através do aduto da
  linha é comparada com o precursor já escrito, até a última casa decimal
  desse precursor — um escrito `647.5` é bom até um décimo, um escrito
  `806.5624` até um décimo de milésimo. Onde discordam, a célula fica vazia e
  os dois números são listados, porque uma fórmula errada é uma lock mass
  errada, o que é pior do que lock mass nenhuma. Uma unidade inteira na
  última casa é permitida em vez de meia, já que uma massa escrita é tão
  frequentemente truncada quanto arredondada; as leituras que de fato estão
  em questão diferem por uma dupla ligação, um metileno ou uma hidroxila,
  nunca por um décimo.

Uma linha sem aduto não pode ser conferida e por isso não é preenchida. O
diálogo dá as contagens e lista, nome por nome, o que foi recusado e por quê
— e quais padrões internos continuam sem fórmula, e portanto sem lock mass.

No método contra o qual isto foi escrito: 125 de 141 componentes e 10 de 11
padrões internos, em milissegundos. Treze das 16 recusas eram o precursor
escrito, digitado com menos casas do que merecia; as outras três erram por um
dalton inteiro ou mais, e nesse lote o instrumento havia adquirido a massa
como ela estava escrita, o que põe o *nome* em questão. O *Repair
precursors…*, abaixo, é onde qualquer um dos dois se resolve. A
[[mass-recalibration]] carrega os números.

## Repair precursors from formulas

Uma recusa deixa um impasse: a fórmula e o precursor não podem estar os dois
certos, e o *Fill formulas from names* deliberadamente se recusa a adivinhar
qual. O **Repair precursors…** — oferecido também no diálogo das recusas — é
onde isso se resolve, à mão. Ele lista todo componente cuja fórmula
contradiz o seu precursor, pelos dois caminhos: a que o método já carrega, e
a que o nome implica e o preenchimento recusou escrever.

Cada linha mostra o nome, o precursor como está escrito, a massa que a
fórmula dá através do aduto da linha, a diferença em mDa e em ppm, a janela
de extração antes e depois, e uma nota. O **Apply** escreve a fórmula *e* o
precursor das linhas marcadas, uma entrada de [[audit-trail|auditoria]] para
cada — `precursor 484.465 → 484.4724`, com a fórmula na nota. Uma linha não
marcada não é tocada, e nenhuma linha que não foi listada tampouco.

A marcação é o argumento do diálogo:

- **abaixo de meio dalton, marcada.** Isso é um mesmo composto escrito com
  menos casas — `484.465` para 484.4724, uma massa digitada com uma casa
  decimal — e tomar a da fórmula é aritmética.
- **meio dalton ou mais, oferecida desmarcada.** Isso são dois compostos
  diferentes: um hidrogênio, uma dupla ligação, um dígito perdido. Qual dos
  dois, o nome ou a massa, é o engano não é algo que a aritmética resolva, e
  a linha diz isso em vez de decidir.

### O que um precursor de fato move

Duas coisas, e a menor delas é a óbvia:

- a **janela de extração**, mas só onde a linha não tem fragmento. Uma linha
  que nomeia um extrai pelo fragmento, e por isso a janela fica exatamente
  onde estava; o diálogo mostra as duas janelas para que isso se veja em vez
  de se supor.
- **qual canal de aquisição é lido.** O canal é escolhido pelo precursor,
  dentro de 0,7 Da do precursor do próprio canal. Um reparo maior que isso
  leva o componente para outro canal — ou para fora de todo canal de íons
  produto, e nesse caso ele recai sobre a varredura de survey e relata um
  número que não é o composto.

Portanto processe o lote de novo em seguida, e rode o [[check-method]] de
novo também.

### Medido, no lote de 26 injeções

Dezesseis componentes recusados; treze abaixo de meio dalton, três inteiros.
Aplicando os treze:

| | |
|---|---|
| componentes reparados | 13 de 16 |
| quanto a massa escrita errava | 3,0 a 260 mDa, −235 a +392 ppm |
| canal de aquisição alterado | nenhum — todos ficaram dentro de 0,7 Da |
| janelas de extração movidas | nenhuma — todas as 141 linhas têm fragmento |
| linhas com pico, antes → depois | idênticas, componente por componente |
| área mediana, antes → depois | idêntica, componente por componente |
| linhas que se moveram | 0 de 338, a maior diferença de área 0,000 |

Esse é o resultado honesto: neste lote os treze reparos não movem um único
número. O que eles compram é a fórmula ao lado deles. O método passa de 125
fórmulas para 138 de 141, e de 10 dos seus 11 padrões internos com fórmula
para os 11 — o último padrão sem uma lock mass possível para a
[[mass-recalibration]] era o `dHCer(d18:0/12:0)`, a linha 15 ppm fora. Oito
dos treze precursores reparados ficam dentro do survey de 50–700, que é onde
uma lock mass pode sequer ser medida; se alguma delas é forte o bastante para
ser medida é outra pergunta, e a [[mass-drift]] a responde.

O achado *formula against precursor* do [[check-method]] não muda aqui, e não
poderia: ele lê uma fórmula que a tabela já carrega, e o *Fill formulas from
names* recusa escrever as dezesseis. O diálogo das recusas é onde elas são
relatadas neste lote; o achado é o que uma fórmula digitada ou importada
produz.

As três linhas de um dalton inteiro são a razão de as demais serem
oferecidas desmarcadas. Aplicadas, contra um lote adquirido com as massas
como foram escritas:

| Componente | Escrito → reparado | O que o reparo fez |
|---|---|---|
| `C18:1 Cer` | 464,4 → 564,5350 | deixou o canal adquirido de 464,6 por canal nenhum; recaiu sobre o survey, e 22 linhas com pico de mediana 9 contagens viraram 10 linhas de mediana 55 — um número que não é o composto |
| `LacCER(d18:1/18:1(9Z))` | 886,6407 → 888,6407 | o mesmo: 888,64 nunca foi adquirido, 886,6 foi; 21 linhas de mediana 2 viraram 25 de mediana 32, tiradas do survey |
| `LacCER(d18:0/18:1)` | 889,6563 → 890,6563 | caiu num canal real — o que o próprio `LacCER(d18:1/18:0)` do método já usa, com a mesma fórmula e o mesmo fragmento. 16 linhas de mediana 2 viraram 25 de mediana 4, indistinguíveis do seu isômero |

Cada uma delas diz a mesma coisa: o instrumento adquiriu a massa como ela
estava escrita, então a massa escrita é aquela sob a qual estão os dados e o
*nome* é o que pede correção. Nenhuma aritmética poderia saber disso, e é
por isso que nada ali vem marcado.

### Quando o engano é o nome: renomeie a linha

Uma linha de um dalton inteiro tem três respostas, e não duas — manter,
reparar a massa ou **renomear** — e a coluna *Rename to* é a terceira. Ela
oferece os nomes cuja fórmula *de fato* corresponde à massa que foi escrita:
primeiro os da própria classe do nome escrito, com as cadeias movidas em até
quatro carbonos e três duplas ligações, uma hidroxila acílica posta ou tirada
e o `d`/`t`/`m` de uma base esfingoide variado; depois o que o
[[lipid-maps|LIPID MAPS]] tiver naquela massa, marcado como de outra classe.
Nada vem pré-selecionado. A lista é ordenada por quão pouco cada entrada muda
o nome escrito, e cada entrada carrega a sua fórmula e a que distância a massa
dessa fórmula fica da massa escrita, em ppm.

Escolher uma escreve o nome e a sua fórmula e **não move número nenhum** — o
precursor, o fragmento, a janela e portanto o canal ficam intocados — e
registra `Name renamed` na [[audit-trail|auditoria]] com a razão:
`formula C48H87NO13 matches the written 886.6407 to −17.7 ppm`.

A busca casa a massa *nominal*, meio dalton para cada lado, e não as quatro
casas decimais com que o precursor foi digitado. É esse o ponto: uma linha só
recebe a oferta de renomeação porque a sua massa escrita já discorda do seu
próprio nome por um dalton inteiro, o que diz de onde vieram aquelas casas —
foram calculadas para o composto que o nome errou. O
`LacCER(d18:1/18:1(9Z))` está escrito 886,6407 contra uma fórmula de
888,6407, e a diferença é exatamente 2,0000 onde uma dupla ligação de verdade
é 2,0157. Casar aquela fração até a última casa não responde nada; casar a
massa nominal responde o isômero, e o ppm na linha é o que diz que a resposta
é nominal.

### Medido, nas três linhas de um dalton inteiro

| Escrito | O que é oferecido | O topo da lista |
|---|---|---|
| `LacCER(d18:1/18:1(9Z))`, 886,6407 | 204 nomes na classe, sobre **quatro** fórmulas; 25 mostrados | `LacCER(d18:1/18:2)` e `LacCER(d18:2/18:1)`, ambos C48H87NO13 em 886,6250, −17,7 ppm |
| `LacCER(d18:0/18:1)`, 889,6563 | nada, nem da classe nem do banco | uma cadeia move um lipídio em 14 Da, uma dupla ligação em 2, uma hidroxila em 16 — nada que essa classe possa ser fica a um dalton |
| `C18:1 Cer`, 464,4 | nada na classe; uma espécie do LIPID MAPS, `CAR 20:4;O` a −136 ppm | o nome se lê como 564,5350, cem daltons fora; a busca alcança quatro carbonos, não onze |

Duas das três são respondidas com um silêncio, e as duas recusas valem mais do
que valeria um palpite. Um **dalton inteiro ímpar não é uma cadeia**: todo
movimento que a busca pode fazer é um número par de daltons nominais, de modo
que metade dos inteiros é inalcançável e o `LacCER(d18:0/18:1)` é um dígito
digitado errado e não um composto mal nomeado. E 204 nomes sobre quatro
fórmulas é a outra metade do mesmo fato — uma massa fixa a composição e nunca
a divisão entre as cadeias, e é por isso que a lista é longa, que ela é
ordenada por quão pouco muda, e que nada nela vem marcado por você.

Renomeando o `LacCER(d18:1/18:1(9Z))` para `LacCER(d18:1/18:2)` e processando
o lote de novo: **78 de 78 linhas idênticas** — os três componentes de um
dalton inteiro nas 26 injeções, com toda área, altura, tempo de retenção,
limite, contagem de pontos, canal e nota iguais. Essa é a alegação inteira. Uma
renomeação é escrituração: o que ela compra é uma linha cuja fórmula concorda
com a sua própria massa, que é do que se faz uma lock mass para a
[[mass-recalibration]], e um nome que significa o composto sob o qual os dados
de fato estão.

Depois disso a linha volta a este mesmo diálogo, agora 15,7 mDa fora e
marcada, porque os 886,6407 escritos nunca foram a massa exata de coisa
alguma: agora o nome está certo e o número é o que foi digitado. Aplicar
também esse reparo deixa outra vez 78 de 78 linhas idênticas — 16 mDa está
bem dentro dos 0,7 Da que escolhem o canal — e a linha termina com o nome, a
fórmula e a massa dizendo todos o mesmo composto.

## Padrões do método

Abaixo da tabela: a **default tolerance** (tolerância padrão) e a sua
unidade, que todo componente sem a sua própria usa; a **concentration unit**
do lote; e a tolerância de **ion ratio** que aprova e a faixa mais larga que
é *marginal* em vez de reprovação (20% e 30% para começar). Os padrões de
integração que todo componente herda — suavização, linha de base, critérios,
o algoritmo — são editados no painel Integration da [[analytics-workspace]]
com **Back to method defaults**, e os [[acceptance-criteria]] da mesma
maneira.

## A disposição do CSV

Apenas `name` e `precursor` são obrigatórios. Os cabeçalhos são reconhecidos
em inglês ou em português, de modo que uma lista escrita por uma versão
anterior continua funcionando.

```
name,precursor,fragment,rt,window,tolerance,unit
12,13-DiHOME,313.2384,183.1391,14.7,0.6,0.02,Da
9,10-DiHOME,313.2384,201.1496,14.2,0.6,20,ppm
```

| Campo | Cabeçalhos aceitos |
|---|---|
| name | name, compound, component, analyte, nome, composto, analito |
| group | group, grupo |
| precursor | precursor, q1, precursor_mz, parent, precursormz |
| fragment | fragment, q3, product, fragment_mz, productmz, fragmento, produto |
| rt | rt, retention_time, rt_min, tr, tempo |
| rt_halfwidth | window, rt_window, rt_halfwidth, half_window, janela, meia_janela, tolerancia_rt |
| tolerance, unit | tolerance, tol, mz_tolerance, tolerancia; unit, tol_unit, unidade |
| formula, adduct | formula, chemical_formula, molecular_formula, elemental_formula, composition; adduct, aduto, ion |
| is_internal_standard | is, is_internal_standard, internal_standard?, istd, is_istd, e_padrao_interno — verdadeiro para 1, true, yes, y, sim, is, istd, x |
| internal_standard | internal_standard, is_name, istd_name, padrao_interno |
| response | response, response_type, resposta |
| concentration_unit | concentration_unit, conc_unit, units, unidade_concentracao |
| qualifier_of, ion_ratio, ion_ratio_tolerance | qualifier_of, qualifier, qualificador_de, quantifier; ion_ratio, expected_ion_ratio, razao_ionica; ion_ratio_tolerance, ion_ratio_tol |
| regression, weighting | regression, curve, fit, regressao; weighting, weight, ponderacao, peso |
| lm_id | lm_id, lipidmaps, lipidmaps_id, lmid |
| min_response | min_response, response_floor, min_area, floor, piso_resposta, resposta_minima, area_minima |
| provenance | provenance, source, origin, procedencia, proveniencia, origem — texto livre, escrito pelo *Use in method…*; veja acima |

Os parâmetros de integração próprios de um componente e os seus critérios de
aceitação não estão no CSV; eles são salvos no projeto.

## Como um componente encontra o seu canal

Para cada amostra, o canal que carrega um componente é escolhido por três
condições: o seu precursor está dentro de 0.7 Da do precursor do componente;
a sua faixa de massas contém o alvo (o fragmento, ou o precursor quando não
há fragmento); e, quando o componente declara um tempo de retenção, o canal
foi adquirido naquele tempo. A última condição é por que o tempo faz parte do
método: um método agendado repete o mesmo precursor em períodos diferentes —
313.24 em um experimento cobrindo 0–13 min e outro cobrindo 13–21.5 — e
associar apenas pelo precursor escolhe um canal que nem sequer estava sendo
adquirido quando o composto elui. Falhando tudo isso, um canal de varredura
completa cuja faixa contenha o alvo é usado; falhando isso, a linha diz
*no matching channel*. Quando o canal associado não cobre a janela pedida, a
linha diz isso em vez de reportar um pico de algum outro tempo.

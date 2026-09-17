---
title: Massa exata do precursor
---
A lista de precursores de um método é escrita à mão — `351.20`, `313.24` — e só
é boa até as casas decimais com que foi digitada. Consultar um lipídio a partir
disso é pedir ao banco de dados dígitos que o número não carrega: a ±0.005 Da
uma massa próxima de 350 é incerta em 14 ppm, e a janela de busca se enche do
que por acaso estiver por perto.

A varredura de survey (survey scan) contém o número real. Antes de uma busca de
lipídio em nome de um componente, o programa encontra o íon precursor no canal
de varredura completa (TOF MS) **no momento em que o canal de íons produto
efetivamente vê o pico**, e usa a massa que o instrumento mediu.

## Como é medida

1. A própria transição do componente é integrada para descobrir quando ele
   elui; esse tempo ancora a busca.
2. No canal de survey, o espectro naquele tempo é buscado dentro de ±0.25 Da do
   precursor escrito — amplo o bastante para absorver um valor arredondado à
   mão, bem dentro do cerca de 1 Da que o Q1 isola, de modo que uma massa
   nominal vizinha nunca pode ser capturada.
3. O pico encontrado é centroidizado; um pico mais fraco que 100 contagens não
   é confiado como medição de massa. Essas cem são um piso fixo escrito para
   uma varredura de survey de um TripleTOF, e são fixas só aqui: onde o
   espectro é a média de uma [[direct-infusion]] inteira, o piso é medido
   naquela aquisição e sai muito mais baixo — veja o [[signal-to-noise]].
4. O mesmo é feito em cada amostra aberta. As amostras têm de concordar dentro
   de 25 ppm para estarem medindo o mesmo íon; o consenso é a mediana.
5. O **precursor sobrevivente** na varredura de íons produto — o íon não
   fragmentado que passou pelo Q1 — também é medido, e os dois têm de concordar
   dentro de 25 ppm.

Essa última verificação importa. O survey vê tudo o que elui naquele momento,
de modo que uma interferência forte dentro da janela de busca pode vencer; o
que quer que sobreviva à fragmentação teve de passar antes pela janela de
isolamento do Q1, o que é a confirmação de que o pico do survey é o precursor
da própria transição.

## Para que a massa é usada depois

Onde o survey consegue medir um precursor, uma busca de lipídio usa essa massa
a ±10 ppm. Onde não consegue, a janela recai sobre a precisão do próprio
precursor tal como escrito: uma massa escrita como `351.20` é conhecida a
±5 mDa, e pedir 10 ppm dela seria inventar dígitos.

Em dados reais a diferença decide a resposta. Uma transição escrita como
`325.20` corresponde a `FA 18:3;O3` em precisão nominal; a varredura de survey
coloca o íon em 325.1887 e a varredura de íons produto concorda dentro de
1 ppm, o que descarta essa espécie a 41 ppm.

## O survey confirma o aduto

O survey responde a uma segunda pergunta que a varredura de íons produto não
consegue. Um canal escrito `647.5` é uma massa; qual *íon* essa massa é —
protonado, amoniado, sodiado — é uma dedução a partir da fórmula da molécula,
e ela está errada no instante em que a fórmula estiver. O Q1 deixou passar uma
massa e jogou fora os isótopos junto com todo o resto, de modo que a varredura
de íons produto não pode decidir. O survey guarda as duas metades da resposta:
a massa exata de cada aduto que a molécula poderia ter produzido, e o padrão
isotópico que diz se o que está ali é um íon monoisotópico ou o satélite de
outra pessoa.

De cada aduto candidato pedem-se duas coisas:

1. **Está ali?** O pico mais próximo dentro de ±0.05 Da da massa exata do
   íon, centroidizado, tem de ficar dentro de **25 ppm** — o mesmo número que
   o consenso acima usa para dizer que duas medidas são do mesmo íon — e ter
   ao menos 100 contagens.
2. **Parece esse íon?** M, M+1 e M+2 teóricos são calculados para a
   **composição do próprio íon**, átomos do aduto incluídos: `[M+NH4]+`
   carrega um nitrogênio e quatro hidrogênios que a molécula não tem, e
   `[M+Cl]-` carrega um M+2 de 32% que a molécula também não tem. Cada
   satélite é pontuado contra o maior entre medido e esperado, e os satélites
   são promediados com peso pelo quanto cada um é do padrão — o que coloca
   cerca de cinco sextos do peso no M+1 para um lipídio.

Ambas são reportadas para todos os candidatos, presentes ou não, porque um
aduto que o survey não mostra também é uma medida.

### O que foi medido

Injeção 01 de um lote de 26 injeções de esfingolipídios num TripleTOF 5600,
positivo, com survey TOF MS 50–700. O survey é promediado sobre as mesmas
scans que o espectro de produto — dois deles, a um scan a cada
14,6 s.

Estas são corridas **cromatográficas**, não infusões: não havia nenhuma
infusão com varredura de survey em mãos, então o survey foi promediado sobre
a própria eluição de cada composto, que é a mesma medida que uma infusão faz
sobre a corrida inteira. Nada aqui se limita a infusões — qualquer aquisição
cujo método tenha um canal de varredura completa sobre o precursor recebe a
mesma resposta.

`SM(d18:1/12:0)`, C35H71N2O6P, escrito `647.5`, sobre seu pico em 5.60 min:

| aduto | exata | encontrado | Δ ppm | altura | do mais forte | M+1 medido / esperado | padrão |
|---|---|---|---|---|---|---|---|
| `[M+H]+` | 647.5123 | 647.5112 | −1.6 | 51.341 | 100% | 0.37 / 0.40 | 0.87 |
| `[M+Na]+` | 669.4942 | 669.4956 | +2.1 | 6.443 | 12.5% | 0.53 / 0.40 | 0.76 |
| `[M+K]+` | 685.4681 | 685.4571 | −16.1 | 223 | 0.4% | 2.76 / 0.40 | 0.13 |
| `[M+NH4]+` | 664.5388 | — | mais próximo a 69 ppm | — | — | — | — |

`Cer(d18:1/16:0)`, C34H67NO3, escrito `538.6`, sobre seu pico em 4.89 min:

| aduto | exata | encontrado | Δ ppm | altura | do mais forte | M+1 medido / esperado | padrão |
|---|---|---|---|---|---|---|---|
| `[M+H]+` | 538.5194 | 538.5197 | +0.6 | 7.690 | 100% | 0.33 / 0.38 | 0.77 |
| `[M+Na]+` | 560.5013 | 560.5071 | +10.4 | 1.025 | 13.3% | 0.67 / 0.38 | 0.55 |
| `[M+NH4]+` | 555.5459 | 555.5340 | −21.5 | 170 | 2.2% | 1.00 / 0.38 | 0.33 |
| `[M+K]+` | 576.4753 | — | mais próximo a 60 ppm | — | — | — | — |

Três coisas nessas duas tabelas são toda a razão de o padrão ser perguntado.

**A massa sozinha admite um íon que não está ali.** O `[M+NH4]+` da ceramida
está a 21.5 ppm, dentro dos 25 que dizem "mesmo íon", e tem 170 contagens,
acima das 100 que dizem "mensurável". Seu M+1 e seu M+2 voltam a 1.00 e 1.00
do seu M, que é a cara de um trecho de ruído plano e de mais nada. O padrão
lhe dá 0.33 e ele fica em último.

**Um satélite é onde um lipídio guarda a própria família.** O `[M+H]+`
verdadeiro da ceramida tem um M+2 quatro vezes grande demais — 0.29 contra
0.076 — porque a janela em 540.53 contém a **diidroceramida** coeluente,
C34H69NO3 em 540.5350, a 17 ppm do próprio M+2 da ceramida em 540.5259 e
dentro dos mesmos 0.02 Da. Uma regra que somasse os erros dos satélites daria
0.43 ao aduto do próprio composto e o chamaria de discordância; ponderada por
satélite ela dá 0.77. Toda classe de lipídio tem seu análogo saturado dois
daltons acima, então isto não é um acidente de um lote.

**Vários adutos de uma molécula é o caso comum, não a exceção.** Os dois
compostos ficam em cerca de `[M+H]+` 100%, `[M+Na]+` 13%, e isso vale saber:
um oitavo do sinal está num canal que ninguém adquiriu.

### Quando não confirma

O mesmo canal 647.5 tem um pico **maior** em 9.26 min do que em 5.60. O survey
em 9.26 não mostra nada dentro de 25 ppm de nenhum aduto da fórmula da
esfingomielina: seu pico mais próximo é 647.5575, +69.9 ppm do `[M+H]+`, e
nenhuma fórmula que este programa consegue montar o explica como aquela
molécula. O aduto é então reportado como lido apenas da massa escrita, que é
o que ele sempre foi.

Onde a aquisição **não tem survey algum** — as nove infusões de ácidos
biliares, adquiridas só como varreduras de íons produto — nada muda e o
relatório diz isso: *nenhum survey cobrindo 430.35, então nada independente
diz que íon é este*. Isso não é uma falha; é a diferença entre um aduto
medido e um aduto deduzido, escrita.

A única coisa que o survey pode passar por cima é um precursor escrito que
não cabe em **nada**. A ceramida acima está escrita `538.6` para um íon de
538.5194 — 0.08 Da fora, oitenta vezes o que se permite a um aduto. Sem
survey isso é recusado, porque um erro de digitação e um arredondamento não
podem ser distinguidos. Com survey, o instrumento já disse que íon estava
ali, então é lido como `[M+H]+` e a frase diz por quê: *0.0806 Da da massa
escrita, dentro dos ±0.7 Da que o quadrupolo deixa passar*.

## Onde aparece

- [[annotate-from-lipid-maps]] — cada proposta diz se sua massa veio do survey
  ou foi escrita, e que janela foi usada.
- o Explain da aba [[lipid-maps]] — o precursor ali digitado é aquilo pelo que
  os candidatos são consultados;
- [[mass-drift]] — a mesma medição feita em cada injeção, para ver se o eixo de
  massa se manteve ao longo da corrida;
- [[mass-recalibration]] — corrigir o eixo a partir dos padrões que carregam
  uma fórmula. Com ela ligada, esta medida é reportada crua e corrigida lado
  a lado: o valor medido nunca é sobrescrito, porque a correção foi ajustada
  a partir dele.
- a caixa Adduct da aba [[lipid-maps]], em *from the precursor* — a linha
  abaixo diz se o survey confirmou o aduto, e o cabeçalho do
  [[infusion-report]] e a aba Infusions carregam o mesmo numa célula cada.
  Um registro escrito numa biblioteca sua diz no comentário qual dos dois
  foi.

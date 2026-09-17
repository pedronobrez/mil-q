---
title: Padrões internos e qualificadores
---
## Padrões internos

Um padrão interno é um composto adicionado a toda amostra na mesma
quantidade, para que a sua resposta acompanhe o que quer que o preparo de
amostra e o instrumento tenham feito àquela injeção, e dividir a resposta de
um analito por ela cancele os dois.

Na [[method-workspace]], marque **IS** no componente que *é* o padrão, e
escreva o seu nome na coluna **Internal standard** de todo analito reportado
contra ele. Um componente apontado para um nome que nenhum componente
carrega, ou para um componente não marcado como IS, é mostrado com o
problema na coluna IS da [[results-table]] em vez de tratado silenciosamente
como se não tivesse padrão — uma planilha importada costuma produzir
exatamente esse erro. O padrão também pode ser trocado a partir da própria
tabela de resultados, onde a coluna IS é uma lista suspensa; toda razão,
resposta e concentração que vinha do padrão antigo é recalculada de
imediato.

Para cada linha os resultados carregam a área e a altura do padrão, a
**razão de áreas** e a **razão de alturas**. A razão é a partir do que uma
curva de [[calibration]] é construída quando há um padrão definido, e a área
bruta caso contrário; a coluna **Response** do método diz o que a tabela de
resultados reporta — `area`, `ratio` ou `concentration` lida da curva.

Um padrão que mal está presente não normaliza nada, por melhor que a
aritmética seja feita. A página [[batch-qc]] traça a carta de cada padrão
interno ao longo da corrida e diz quais deles o lote pode de fato usar;
[[check-method]] diz quais padrões não têm tempo de retenção e quantos
componentes cada um serve.

## O piso de resposta

**Min. response** em um padrão interno é a menor área que ele tem de dar em
uma injeção antes que uma razão a ele signifique alguma coisa. É declarado
por quem conhece o método — o que o padrão dá quando a corrida está certa —
porque nada mais pode fornecê-lo: o lote não consegue derivar um (medido em
um lote real, a precisão dos padrões não acompanhou a sua resposta), e o
sinal/ruído não pode substituí-lo em uma aquisição agendada, onde a linha de
base é de zeros exatos e "S/N" é a altura contra uma constante arbitrária —
ver [[signal-to-noise]].

Uma vez declarado, três coisas o leem:

- a **carta de controle** do padrão em [[batch-qc]] é utilizável quando a sua
  mediana supera o piso, e não de outro modo, no lugar da regra de S/N 10; e
  em uma carta utilizável as injeções que ficaram abaixo do piso são
  listadas;
- toda linha normalizada contra o padrão é verificada na aceitação: uma
  injeção em que o padrão deu menos que o seu piso é sinalizada
  *IS 40 below its floor of 100* e falha — ver [[acceptance-criteria]];
- [[check-method]] avisa sobre um padrão que serve componentes e não declara
  piso nenhum.

O piso é uma área nas mesmas unidades da tabela de resultados, viaja no CSV
como `min_response` e é salvo com o projeto. **Suggest floors…** na página
[[batch-qc]] propõe um a partir do lote — metade da mediana de cada padrão
sobre as injeções que não foram falhas, com a sua base ao lado — para alguém
aceitar, já que uma proposta a partir de um lote é evidência e não a
declaração.

## Qualificadores e razões iônicas

Um qualificador é uma segunda transição do mesmo composto, adquirida para
confirmar que o pico no quantificador é o composto e não uma interferência:
as duas transições devem manter uma razão de áreas fixa, e uma razão longe
dela significa que outra coisa está contribuindo.

Declare o qualificador como um componente próprio, nomeie o quantificador em
**Qualifier of** e informe a **Ion ratio %** esperada — a área do
qualificador como porcentagem da do quantificador. Depois do processamento,
cada linha de qualificador carrega a razão medida e uma confiança:

| Confiança | Condição |
|---|---|
| Pass | o desvio em relação à razão esperada, relativo a ela, está dentro da tolerância (20% por padrão) |
| Marginal | além da tolerância mas dentro da faixa marginal (30% por padrão) |
| Fail | além da faixa marginal |

A tolerância é escrita nos padrões do método, ou por qualificador em
**± ratio %**. Uma razão iônica reprovada é um sinalizador na linha e torna o
seu estado Fail; uma marginal torna o estado Marginal quando nada mais falha
— ver [[acceptance-criteria]].

## Transições compartilhadas

Dois componentes que declaram o mesmo precursor e o mesmo fragmento — dois
isômeros, digamos — extraem o mesmo traço, e sem nada que os separe a
integração retorna o mesmo pico duas vezes sob dois nomes. **Check method**
reporta o par, e [[suggest-from-data]] se recusa a pré-marcar um tempo de
retenção para qualquer um dos dois; a única coisa que os separa é um tempo
de retenção que seja diferente, e diferente de propósito.

## Um padrão no mesmo spray

Sem coluna o pareamento é o mesmo e a aritmética não é: o analito e o seu
padrão são duas alturas num único espectro médio em vez de dois picos
integrados, e um padrão deuterado fica perto o bastante do seu analito para
um alcançar os íons do outro. Para que lado isso vai, qual é o tamanho e
quando não pode acontecer de jeito nenhum estão medidos na
[[infusion-quantitation]]. O piso de resposta acima importa mais ali, não
menos — a supressão iônica é compartilhada pelo par, então a razão sobrevive
a ela e só as respostas absolutas a mostram.

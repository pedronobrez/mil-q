---
title: Relatório do método
---
**Method report…** no [[method-workspace]] escreve tudo o que este programa
consegue dizer sobre um método *antes* que ele seja executado, como um
único PDF ou um único arquivo HTML. Nada nele é uma verificação nova: ele
roda o [[check-method]], o *Fill formulas from names*, o *Repair
precursors…* e o [[acquisition-schedule]] e dispõe as respostas em um só
documento — aquilo que se entrega a quem escreveu o método, que se arquiva
ao lado dele, ou que se lê seis meses depois quando um lote adquirido sob
ele está sendo defendido.

Ele não dá nota ao método. Não há pontuação, nem selo, nem semáforo, e a
seção final é um parágrafo de frases simples, cada uma contando algo
medido mais acima na página. Um método com oitenta e dois componentes sem
tempo de retenção pode estar exatamente certo — pode ser um método de
triagem — e um visto verde não convidaria ninguém a ler os oitenta e dois.

Ele também não altera o método. O *Fill formulas from names* escreve nas
células que recebe, então o relatório lhe entrega **cópias**: ele pode
dizer quantas fórmulas poderiam ser derivadas sem derivar nenhuma delas.

## As seções

| Seção | O que há nela |
|---|---|
| Components | a tabela como o método a declara — nome, precursor, fragmento, aduto, fórmula, RT ± janela, IS, grupo, piso de resposta, e de onde veio a fórmula. Uma linha marcada pelo [[check-method|verificador]] carrega `!` para um achado *serious* e `†` para um *warning* |
| What the check finds | cada achado agrupado por severidade, com a contagem de *achados* no título, a explicação de cada um e os componentes que ele nomeia. Verificações que não puderam rodar — as que precisam de um arquivo aberto — são listadas como não feitas, e não como aprovadas |
| Formulas | quantos componentes carregam uma fórmula, quantos mais os próprios nomes forneceriam, e cada recusa com as **duas** massas: o que a fórmula pesa e o que o método escreveu, em mDa e em ppm, e se o erro mais provável é a massa ou o nome |
| Lock-mass candidates | cada padrão interno que carrega uma fórmula, com sua massa neutra, seu aduto e o m/z exato que disso decorre — e a frase que diz que ser candidato não é ser uma lock mass |
| The acquisition | com um arquivo aberto: qual canal serve cada componente ([[explorer-components-and-results|correspondência]] por precursor e tempo), o que as varreduras de survey cobrem e quais precursores caem fora delas |
| The schedule | o [[acquisition-schedule]] que o método implica: transições com tempo, quantas são adquiridas ao mesmo tempo no momento mais cheio e quando, e o dwell que o ciclo alvo deixa a cada uma |
| What the method is missing | o parágrafo final, uma frase por medida |

## O que precisa de arquivo, e o que não precisa

Os componentes, os achados que leem o método contra si mesmo, as fórmulas
e os candidatos a lock mass não precisam de nada além da tabela. Abra um
arquivo e o relatório ganha a seção da aquisição, a verificação de janela e
as faixas do survey; processe um lote e o **ciclo alvo** do agendamento vem
da largura que os próprios picos do lote mediram ([[batch-qc|Sampling]]) em
vez de dez segundos redondos. Sem nada aberto, o documento diz quais seções
faltam e por quê.

A primeira amostra aberta é a aquisição, a mesma que o [[check-method]]
usa.

## Por que um candidato é apenas um candidato

Se um padrão *poderia* ancorar um eixo de massa é uma propriedade do
método: ele precisa de uma fórmula e de um aduto, porque um precursor
digitado com uma casa decimal é bom até algumas centenas de partes por
milhão e o erro que uma [[mass-recalibration|recalibração]] corrige é de
poucas. Se ele *é* uma lock mass é uma propriedade de um lote — a varredura
de survey tem de alcançá-lo, o mesmo íon tem de ser medido em cada injeção,
e esse íon tem de ficar perto da massa que a própria fórmula nomeia.
Nenhuma dessas três coisas pode ser lida de um método, e a seção diz isso
com essas palavras, em vez de sugerir uma resposta.

Onde um padrão não declara aduto, o m/z é calculado pelo aduto que o
precursor escrito aparenta ser, marcado com um asterisco. Um aduto
adivinhado a partir de uma massa arredondada é um palpite: digite-o na
tabela.

## No método real

O método de esfingolipídios com 141 componentes, contra a primeira injeção
do seu lote de 26 injeções: 15 páginas impressas em cerca de cinco
segundos, sendo a leitura em si uma fração de segundo. Três achados
*serious* e quatro *warnings*, tocando todas as 141 linhas — 89 com um
achado *serious*, 52 com um *warning*, nenhuma limpa. Nenhum componente
carrega fórmula e 125 tomariam uma do próprio nome, restando 16 cujo nome e
precursor escrito se contradizem, 3 deles por um dalton inteiro. Nenhum
padrão pode ser candidato a lock mass, porque nenhum carrega fórmula. Todos
os 141 componentes são servidos por um canal próprio, e 72 precursores caem
fora do survey de 50–700. Agendado, são 59 transições com 82 deixadas de
fora por não terem tempo, no máximo 24 adquiridas ao mesmo tempo em 4,70
min, e o ciclo que os próprios picos do lote sugerem — 12,4 s — deixa a
cada uma dessas 24 cerca de 512 ms de dwell. Digite 3 s e as mesmas 24
ficam com 120 ms, que é a figura em [[measured-facts]].

## Para onde vai

Um PDF ou um arquivo HTML, escolhido na caixa de salvar; o HTML abre sozinho
em um navegador. Escrever um fica registrado na [[audit-trail|trilha]] como
*Method report*, com o número de componentes, os achados e a aquisição
contra a qual foi construído. É um documento diferente do
[[report|relatório do lote]], que responde o que uma corrida mediu; este
responde o que o método pede.

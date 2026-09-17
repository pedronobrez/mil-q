---
title: Revisão de picos
---
A grade de revisão é a visão em torno da qual o MultiQuant foi construído: o
mesmo componente em todo o lote de uma vez, de modo que um outlier (valor
discrepante) salta aos olhos ao lado dos vizinhos em vez de ter de ser caçado
amostra por amostra.

## Os painéis

Cada painel é o cromatograma de uma amostra para o componente selecionado — o
XIC, condicionado como a integração o viu. O título traz o nome da amostra, a
área, o sinal/ruído e o tempo de retenção; um `✎` marca uma linha integrada à
mão. Uma amostra em que nada foi encontrado é desenhada em cinza, com o motivo
no título (*no peak above noise*, *channel does not cover 5.10–6.10 min*,
*only 4 points to detect in*).

O que é desenhado sobre um pico encontrado:

| Elemento | Significado |
|---|---|
| área sombreada | exatamente o que foi integrado: o traço acima da linha de base reta traçada entre as duas fronteiras do pico. A faixa sozinha dizia onde estavam os limites, o que um leitor toma pela área — e num pico de dois ou três pontos os dois não se parecem em nada |
| linha tracejada | essa linha de base |
| faixa vertical fina | as fronteiras |
| faixa clara | a janela esperada de tempo de retenção, RT ± meia largura |
| curva laranja | a gaussiana ajustada, quando a área veio de um ajuste — o sombreado fica então sob a curva, porque a área da curva é o número. Ver [[integration-algorithms]] |
| traço tracejado vermelho | o padrão interno, com **Show IS** ligado |
| faixa cinza | a região de ruído, quando há uma definida |

## Controles

| Controle | Efeito |
|---|---|
| **Columns** e **Rows** | a forma da grade; a paginação aparece quando o lote é maior que uma página. Os painéis são guardados e recolocados em vez de reconstruídos, pelo que mudar a forma é imediato e não redimensiona a janela — ver [[workspaces]] |
| **Manual** | arrastar sobre um painel integra exatamente aquele intervalo (Shift+arrastar faz o mesmo sem a chave) |
| **Show IS** | desenha o padrão interno atrás do analito, reescalado à altura dele — os dois raramente compartilham uma magnitude, e só a forma e o tempo estão sendo comparados |
| **Same Y** | uma única escala de intensidade em todos os painéis, para que as alturas se comparem diretamente |
| **Zoom** | *Expected window*, justo no *Peak*, ou a corrida inteira (*Whole run*) |
| **Link X** | dar zoom em um painel dá zoom em todos |
| **Magnify peak** (barra de ferramentas) ou duplo clique | um painel ocupando o painel inteiro |

Os painéis ficam cercados dentro dos próprios dados: nada fica fora do traço de
um pico, e num painel tão pequeno é fácil perder a referência.

## Integração manual

Arraste sobre um pico com **Manual** ligado, ou com Shift pressionado. O
intervalo é integrado como marcado — uma linha de base reta entre as duas
extremidades, a área acima dela, sem detecção de pico — e a linha é marcada
como manual com `✎`. Uma linha manual sobrevive ao reprocessamento enquanto
valerem os parâmetros sob os quais foi desenhada: acrescentar uma injeção,
mudar outro componente ou reprocessar o lote a deixa exatamente como o
operador a definiu. O que a substitui é uma mudança nos parâmetros de extração
ou de integração do **próprio** componente dela — outra janela de massa, outra
suavização, outro algoritmo — porque uma fronteira desenhada sobre um traço não
é uma decisão sobre um traço diferente. Ela é integrada de novo
automaticamente, a linha de status e a [[audit-trail]] dizem quantas linhas
foram, e basta repetir o arraste. Clique
com o botão direito no painel e escolha **Back to automatic integration** para
devolvê-la ao detector. Ambas as coisas são escritas na
[[audit-trail]], com as fronteiras e a área antes e depois, de modo que um
pico decidido por alguém pode ser distinguido de um encontrado pelo
detector.

## A região de ruído

Clique com o botão direito em um painel com um trecho de linha de base
sombreado e escolha **Set noise region from the shaded range**: esse intervalo
passa a ser onde se mede o ruído por trás do sinal/ruído do componente,
pico a pico ou por desvio padrão, conforme diz o painel Integration.
**Apply** nesse painel mantém a definição. Por que a região importa está em
[[signal-to-noise]].

## Como ler uma grade

- Um pico que se desloca de painel em painel enquanto a janela esperada fica
  parada é retenção derivando; a página [[batch-qc]] traça isso.
- Um padrão desenhado atrás do analito com **Show IS** que atinge o ápice em
  outro tempo é um padrão que não é o padrão daquele analito.
- Um painel cinza entre os encontrados, com *no peak above noise*, numa
  amostra que visivelmente tem um pico, costuma ser um portão: ver
  [[integration-parameters]].

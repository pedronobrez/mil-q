---
title: Trilha de alterações
---
Tudo com que um lote é processado é salvo com o projeto — o método, os
parâmetros de integração, a calibração. O que não fica salvo em lugar nenhum é
a sequência de decisões que alguém tomou por cima disso: este pico integrado à
mão, aquele padrão retirado da curva, esta injeção redigitada como branco.
Reabrir um projeto seis meses depois mostra a resposta, e não como se chegou a
ela.

A trilha de alterações é esse registro. Ela é a aba **Audit trail** da
[[analytics-workspace]] e também *File ▸ Audit trail…*, que faz a mesma
pergunta ao projeto em vez de fazê-la à área de trabalho em que se está.

## O que é registrado

Uma linha por ação, com o horário em que foi feita, o que mudou e o valor
antes e depois.

| Alteração | Registrada como |
|---|---|
| um pico integrado à mão na grade de [[peak-review]] | o componente e a amostra, as fronteiras e a área antes e depois, e o intervalo arrastado |
| uma linha devolvida à integração automática | o mesmo, no sentido inverso |
| a caixa **Used** de uma linha da [[results-table]] | usada ↔ excluída, com a área |
| um padrão incluído ou excluído numa curva de [[calibration]] | usado ↔ excluído, com sua concentração |
| **Remove outliers** numa curva | quantos padrões estavam excluídos antes e depois, e a tolerância |
| um componente acrescentado, removido ou editado na [[method-workspace]] | a coluna que foi digitada, e o que havia nela |
| um padrão sob essa tabela — tolerância, unidades, faixas de razão iônica | o mesmo, quando a digitação termina e não a cada dígito |
| o tipo, o grupo, a concentração, a diluição, o nome ou o comentário de uma amostra na [[samples-workspace]] | o campo, antes e depois |
| **Process batch**, e cada reprocessamento após uma mudança de parâmetro | com o que foi processado, e quantas linhas voltaram |
| o interruptor de recalibração de massa em [[mass-recalibration]] | ligado ↔ desligado |
| o projeto sendo salvo | o caminho, com a contagem de linhas e de amostras |

Os valores são registrados como foram mostrados na tela, e mantidos curtos: a
trilha é feita para ser lida de relance, e uma linha que precisa ser
desdobrada é uma linha que ninguém lê.

## Como lê-la

A tabela ordena por qualquer coluna — os horários estão em ISO, de modo que
ordenar *When* como texto o ordena como tempo — e a caixa de filtro reduz às
linhas que contêm o que se digita, em qualquer parte delas. Digitar o nome de
um componente dá o histórico daquele componente; digitar `Manual` dá todas as
integrações feitas à mão.

**Export CSV…** escreve a trilha inteira, não a visão filtrada. Uma trilha com
linhas de fora não é aquilo que ela afirma ser, e o filtro é uma forma de ler
e não uma forma de escolher o que aconteceu.

A trilha também é uma seção do relatório do lote, *Changes made by hand*,
impressa sempre que houver algo nela — ver [[report]].

## O que ela não é

**Isto não é uma trilha de auditoria regulatória.** Não há assinaturas
eletrônicas nem contas de usuário: ela registra *o que foi feito e quando*,
nunca *quem fez*. O projeto é um arquivo JSON — ver [[projects-and-files]] —
que qualquer pessoa pode abrir num editor de texto, de modo que nada aqui
detectaria o registro sendo alterado fora do aplicativo, e nada aqui é
evidência no sentido em que a 21 CFR Parte 11 ou o Anexo 11 entendem a
palavra.

Para o que ela serve é para a pergunta comum que um revisor faz de um lote:
quais destes números uma pessoa decidiu, e o que eles eram antes? Para isso
ela basta, e é o que o software pode afirmar honestamente.

## O que ela não registra

Ler, ordenar, filtrar e ampliar não mudam nada e não são registrados. Também
não é registrado nada derivado que o projeto não guarde — a comparação de
algoritmos, a medição de deriva de massa, uma busca em biblioteca espectral —
porque essas coisas são refeitas sob demanda em vez de decididas. A trilha só
recebe acréscimos: nada no aplicativo edita ou apaga uma entrada, e um projeto
salvo antes disto existir abre com uma trilha vazia em vez de uma inventada.

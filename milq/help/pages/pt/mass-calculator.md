---
title: Calculadora de massas
---
A aba **Mass calc** do [[explorer]] transforma uma fórmula nos números de que
um espectrometrista de massas precisa, e uma massa medida em um erro.

## Fórmula

Digite uma fórmula molecular: `C18H34O4`. A sintaxe aceita grupos com
multiplicadores, `C6H4(NO2)2`, e isótopos individuais entre colchetes,
`[13C]`, com `D` aceito para deutério — de modo que um padrão interno
marcado como `C18H30D4O4` é digitado tal como é escrito. O painel reporta a
massa monoisotópica, a massa média, o equivalente de anéis e duplas ligações
(RDBE) e o m/z do íon para o aduto escolhido.

## Adutos

| Negativo | Positivo |
|---|---|
| [M−H]⁻ | [M+H]⁺ |
| [M+Cl]⁻ | [M+NH₄]⁺ |
| [M+HCOO]⁻ | [M+Na]⁺ |
| [M+CH₃COO]⁻ | [M+K]⁺ |
| [M−2H]²⁻ | [M+2H]²⁺ |

A massa do íon leva o elétron em conta: um cátion é mais leve que a soma dos
seus átomos por uma massa de elétron e um ânion é mais pesado, o que importa
na quarta casa decimal.

A mesma lista de adutos é usada onde quer que um precursor seja calculado a
partir de uma fórmula — na [[method-workspace]], um componente com fórmula e
aduto e sem precursor tem o seu precursor preenchido a partir deles.

## Exatidão de massa

Digite um m/z medido abaixo do calculado e o erro é mostrado em mDa e em
ppm. Esta é a verificação mais rápida de que um pico em tela é o que uma
fórmula diz que ele é.

## Padrão isotópico

O padrão isotópico teórico do íon — m/z e abundância relativa de M, M+1, M+2
e assim por diante — é tabulado, e **Overlay on spectrum** o desenha no
painel do espectro como bastões escalados ao pico mais próximo da massa
monoisotópica, de modo que os satélites medidos possam ser comparados com os
esperados. **Clear overlay** o remove (o menu de contexto do espectro também).

A sobreposição só é significativa em um espectro que carregue os satélites.
Uma varredura de íons produto isola o precursor monoisotópico no Q1, de modo
que os seus fragmentos não têm M+1 a comparar; sobreponha no canal de survey
TOF MS.

## Enviar ao localizador de fórmulas

**Send m/z to formula finder** passa a massa do íon calculada ao
[[formula-finder]], que é a pergunta inversa: que composições esta massa
poderia ser?

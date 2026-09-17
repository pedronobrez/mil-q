---
title: Projetos e arquivos
---
## O arquivo de projeto

Um projeto é um único arquivo, `name.oqproj`, JSON, legível por qualquer
coisa. Ele contém:

| Chave | Conteúdo |
|---|---|
| `version` | a versão do formato do arquivo, atualmente 5 |
| `method` | a tabela de componentes, os padrões de integração e de aceitação, a tolerância e as unidades, as faixas de razão iônica — tudo o que está na [[method-workspace]] |
| `samples` | uma entrada por injeção: o caminho do arquivo bruto e o índice da amostra, o nome exibido, o tipo, o grupo, a concentração esperada, a diluição e o comentário — tudo o que está na [[samples-workspace]] |
| `results` | cada linha da [[results-table]], incluindo integrações manuais, notas, o algoritmo que produziu cada área, os pontos sobre o pico e, para um pico ajustado, o modelo |
| `calibrations` | cada curva: regressão, ponderação, coeficientes, r² e cada padrão com a indicação de se é usado |
| `view` | como o painel de espectros do Explorer ficou: cada espectro fixado como a *receita* que o produziu — amostra, canal e scan ou faixa de tempo, com a janela de fundo se alguma foi subtraída —, mais o piso dos rótulos, Normalise, Mirror e Centroid, e a receita do espectro que estava ao vivo. Ver [[chromatograms-and-spectra]]; um projeto escrito antes disto existir abre com o painel vazio |
| `audit` | o que foi alterado à mão, na ordem em que foi alterado — ver [[audit-trail]]; um projeto escrito antes disto existir não tem a chave e abre com uma trilha vazia |

Ele **não** contém os dados brutos — o projeto aponta para os arquivos por
caminho — nem a última comparação de algoritmos, que é derivada e refeita sob
demanda. **Um espectro fixado é salvo como sua receita e nunca como seus
pontos**, pelo mesmo motivo: duas médias de corrida inteira de uma infusão
são 544.216 pontos, o que dá 20 MB escritos e 3 kB como as duas receitas que
os produziram, e uma cópia congelada dentro do documento deixaria de ser uma
leitura do arquivo para o qual ele aponta. Eles são lidos dos arquivos de
novo quando o projeto abre — medido nessas duas infusões, 5,9 s contra os
3,2 s que os arquivos levam para abrir — e um fixado cujo arquivo saiu do
lugar permanece na lista marcado como *not available: file missing* em vez de
ser descartado sem uma palavra.

Um arquivo que mudou de lugar é reportado pelo nome quando o projeto abre, e
o projeto abre sem ele; ver [[starting-a-project]].

## O que fica ao lado de um projeto

Um diretório, `nome.oqcache/`, e ele não guarda nada que se perca ao ser
apagado: os espectros promediados das infusões que os arquivos do projeto
carregam, um `.npz` de massas e intensidades cada, para que um arquivo que não
mudou seja lido uma vez em vez de a cada **Measure**. Ele fica ao lado do
projeto porque as médias pertencem àquele lote — achadas onde o lote é achado,
apagadas com ele, e deixadas para trás quando o projeto é copiado para outro
lugar, já que arranjos que viajassem sem os seus arquivos seriam a leitura de
nada.

**Sem projeto aberto** não há lugar que lhes pertença e o diretório de cache
do próprio sistema é usado — ver a tabela ao pé desta página — que é o
diretório que o sistema operacional tem o direito de esvaziar. A configuração
`cache/dir` sobrepõe-se aos dois.

Uma entrada é aposentada quando o arquivo muda: a chave guarda o tamanho e a
data de modificação da aquisição e **os do seu `.wiff.scan`**, que é onde os
scans estão. O diretório é limitado em 512 MB, cerca de cento e vinte
infusões, e acima disso as entradas usadas há mais tempo saem primeiro.
**File ▸ Clear cached spectra…** o esvazia e diz quanto se foi. Medido em nove
infusões no ZenoTOF: 39,1 MB para as nove, e um segundo *Measure* em cerca de
metade do tempo do primeiro. Ver [[infusion-report]].

`*.oqcache/` está no `.gitignore` do repositório, junto com os dados brutos:
ele é derivado de arquivos que nunca são versionados e é reconstruído
perguntando de novo.

Projetos escritos pelo programa sob o nome anterior, `.opvproj`, são abertos;
nada novo é escrito com esse sufixo. Um projeto escrito por uma versão mais
antiga abre em uma mais nova: os campos que a mais nova acrescentou assumem
seus padrões — um método salvo antes de existirem algoritmos de integração é
lido de volta como *valley*, que foi o que ele executou.

## Dados brutos

`.wiff` com seu `.wiff.scan`, e mzML. Nunca modificados. Ver [[formats]].
O que uma pasta contém e o que daria errado nela — um companheiro que não
está lá, um `.scan` com o nome errado, arquivos que nenhum leitor daqui
abre — é respondido antes de qualquer coisa ser aberta por *File ▸ Check a
folder…*; ver [[checking-files]], que é também onde o único reparo,
renomear um `.scan` órfão, é oferecido.

## Arquivos CSV

**A tabela de componentes** — `Import CSV…` e `Export CSV…` na área de
trabalho Method; o layout e os cabeçalhos aceitos estão em
[[method-workspace]].

**Resultados** — `Export CSV…` abaixo da tabela de resultados escreve as
colunas visíveis das linhas visíveis; na aba Statistics, o resumo como
mostrado; no Explorer, as linhas da aba Results.

**Cromatogramas e espectros** — `File ▸ Export chromatograms (CSV)…` escreve
cada traço do cromatograma do Explorer como colunas de tempo e intensidade;
`Export spectrum (CSV)…` escreve o espectro na tela como m/z e intensidade.

## mzML

`File ▸ Export sample as mzML…` escreve a amostra selecionada espectro por
espectro; o que sobrevive à viagem está em [[formats]].

## O relatório e o manual

`File ▸ Export report…` escreve PDF ou HTML — ver [[report]]. `Help ▸ Export
manual as PDF…` escreve este manual.

## Onde a aplicação guarda os próprios arquivos

| O quê | Onde |
|---|---|
| preferências | o repositório de configurações da plataforma, organização `MIL-Q`, aplicação `MIL-Q`: geometria da janela, última pasta, painéis recolhidos, o aviso inicial |
| espectros promediados, sem projeto aberto | `~/Library/Caches/MIL-Q` no macOS, `%LOCALAPPDATA%\MIL-Q\Cache` no Windows, `$XDG_CACHE_HOME/milq` nos demais — ou onde a configuração `cache/dir` disser |
| o runtime .NET, quando instalado pelo bootstrap | `~/.dotnet` |
| assemblies NuGet baixados, o índice do LIPID MAPS | `~/.milq`, ou o diretório indicado pela variável de ambiente `OPENPEAKVIEW_HOME` |

Apagar `~/.milq` custa um download dos assemblies e do índice de lipídios
na próxima vez que cada um for necessário; nada sobre qualquer lote está lá
dentro. Apagar o diretório de cache custa um **Measure** frio; nada nele é uma
medição que não possa ser feita de novo a partir dos arquivos.

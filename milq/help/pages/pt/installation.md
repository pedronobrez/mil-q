---
title: Instalação
---
O MIL-Q é desenvolvido e usado no macOS, Apple Silicon incluído. A suíte
de testes e a aplicação iniciam em Linux e Windows na integração contínua, e
instaladores são construídos para os três; a leitura de um `.wiff` só foi
verificada no macOS, porque esse caminho carrega as montagens .NET da SCIEX
e as outras duas plataformas são verificadas apenas até "as montagens
carregam". Ver [[how-wiff-is-read]].

## Instaladores

Cada versão publicada no GitHub traz três arquivos; o que entrou em cada uma
delas está no [[version-history]]:

| Arquivo | Plataforma | Observações |
|---|---|---|
| `MIL-Q-<version>-macos-arm64.dmg` | macOS em Apple Silicon | arraste a aplicação para Applications |
| `MIL-Q-<version>-macos-x86_64.dmg` | macOS em Intel | o mesmo, compilado numa máquina Intel |
| `MIL-Q-<version>-windows-x64.msi` | Windows 10 1703 ou mais recente | um instalador padrão |
| `MIL-Q-<version>-windows-x64.zip` | Windows 10 1703 ou mais recente | sem instalação: descompacte em qualquer lugar e execute `MIL-Q\MIL-Q.exe`. Para uma máquina cujo administrador não deixa correr um instalador — uma partilhada numa biblioteca, por exemplo. É a mesma pasta que o instalador deixa, e nada é escrito fora dela a não ser as preferências e o `~/.milq` |
| `MIL-Q-<version>-linux-x86_64.tar.gz` | Linux | descompacte e execute `MIL-Q/MIL-Q`; o `MIL-Q/install.sh` acrescenta uma entrada no lançador |
| `SHA256SUMS` | todos | uma linha por instalador; `shasum -a 256 -c SHA256SUMS` confere o download |

As duas imagens de disco não são intercambiáveis: um bundle é o interpretador
e cada extensão compilada para a máquina que o construiu, portanto a de Apple
Silicon não arranca num Mac Intel nem o contrário. O `uname -m` diz que
máquina você tem — `arm64` ou `x86_64`. As somas são calculadas sobre os
ficheiros que a release serve, depois de publicados, e não sobre o que saiu
da compilação.

O ícone da aplicação — a marca da suíte, um pico branco com um vizinho azul —
está nos três: o bundle do macOS o carrega como `MIL-Q.icns`, o
executável do Windows o carrega nos seus recursos (verificado lendo-os de
volta do instalador construído: as mesmas seis imagens do `.ico`, de 16 a 256
pixels) e a entrada no menu Iniciar e em *Add or remove programs* o exibe, e
o tarball do Linux distribui `milq.png` com uma entrada `.desktop`. A
própria janela toma o seu ícone do mesmo desenho em todas as plataformas.

### macOS 26 e o ícone Liquid Glass

No macOS 26 um `.icns` clássico é apenas colocado dentro da moldura de vidro
do sistema e mantém as cores seja qual for a aparência escolhida — por isso,
com o estilo de ícones *Clear* ou *Tinted* ligado, todos os ícones ficaram
translúcidos e este continuou azul. Da 0.7.8 à 0.10.1 o bundle carregava
também um ícone em camadas: um documento do Icon Composer compilado pelo
`actool` do Xcode 26 em `Assets.car` e nomeado por `CFBundleIconName`, de
modo que o Dock e o Finder o desenhavam no estilo escolhido. **A 1.0.0 sai
sem ele.** O documento desenhava os dois picos coeluentes do OpenQuant e a
marca do MIL-Q ainda não foi redesenhada para o Icon Composer; o `.icns` é
o que o Dock e o Finder mostram até lá, que é o que todo macOS anterior ao
26 já recebia. O passo do build continua lá e diz isso. O `.icns` permanece para o macOS 15 e
anteriores, que ignoram a chave mais nova. O log do build diz se o ícone em
camadas foi compilado; uma máquina sem Xcode 26 envia só o `.icns`. Foi
preciso mais uma coisa, descoberta no primeiro build com o ícone em camadas:
o sistema desenhava-o em vidro e o Dock continuava a mostrar o quadrado
azul enquanto a aplicação estivesse aberta, porque o Qt entrega o ícone da
janela ao Dock como ícone da aplicação e um PNG plano cobria o ícone em
camadas. Dentro do bundle a aplicação já não define ícone de janela; o
bundle é dono dele.

### Linux: uma entrada no lançador, para um usuário

O tarball é a pasta da aplicação tal como o PyInstaller a construiu, e o
Linux não tem bundle a que dar um ícone. O `install.sh` dentro da pasta
escreve uma entrada `.desktop` sob `~/.local/share/applications` apontando
para a pasta onde ela foi descompactada, e o ícone sob
`~/.local/share/icons`, de modo que a aplicação aparece no lançador e no dock
com o seu ícone; nada sob `/usr` é tocado, e `install.sh --remove` desfaz
isso. Mova a pasta e execute-o de novo.

### O macOS e o atributo de quarentena

A imagem de disco não é assinada. Não é isso que faz o macOS reclamar: o
Gatekeeper reage ao atributo `com.apple.quarantine`, que é anexado por
aquilo que baixa o arquivo — um navegador, o Mail, o AirDrop — e não por
aquilo que o constrói. Ou clique com o botão direito na aplicação e escolha
**Open** uma vez, ou limpe o atributo:

```
xattr -dr com.apple.quarantine /Applications/MIL-Q.app
```

O Apple Silicon insiste em *alguma* assinatura, ou o binário não inicia; a
assinatura ad-hoc que a build aplica é suficiente.

### Windows: 10 1703 ou mais recente, e não sob o Wine

O `Qt6Core.dll` do wheel do PyQt6 importa dezoito símbolos `ucnv_*` de
`icuuc.dll`, a biblioteca de conversores da ICU, e o wheel não distribui ICU
própria porque o Windows fornece uma em `System32` desde aquela versão. Wine
e CrossOver não implementam nenhuma das duas, de modo que a aplicação para
na importação com *"DLL load failed while importing QtCore: Module not
found"*, o que parece um instalador quebrado e não é. Uma biblioteca de
stub que satisfaz aqueles dezoito símbolos existe no repositório de código
sob `packaging/wine/` e deliberadamente **não** está no instalador: em uma
máquina Windows real, um `icuuc.dll` local à aplicação seria encontrado
antes do genuíno.

O instalador foi construído e iniciado em um runner Windows do GitHub, e a
build do Windows leu uma aquisição real sob o CrossOver com o stub no lugar,
dando os mesmos números que a build do macOS. Ele não foi instalado em uma
máquina Windows física pelos autores; ver [[troubleshooting]] se ele se
comportar mal ali.

## A partir do código-fonte

```
git clone https://github.com/pedronobrez/mil-q
cd milq
python3 -m pip install -r requirements.txt
python3 -m milq.bootstrap --install
python3 run.py
```

Os requisitos são numpy, PyQt6, pyqtgraph, alpharaw (que carrega as
montagens Clearcore2 da SCIEX), pythonnet e certifi. Python 3.11 ou mais
recente.

O comando de bootstrap é necessário uma única vez, e apenas quando a máquina
não tem runtime .NET 8: ele baixa o script `dotnet-install` da Microsoft e
instala um runtime de cerca de 30 MB em `~/.dotnet`. Ele também busca no
NuGet as montagens de compatibilidade que o .NET Core não distribui e de que
o Clearcore2 precisa (`System.Configuration.ConfigurationManager` e suas
dependências), guardando-as em cache sob o diretório home da aplicação. Sem
um runtime, arquivos mzML ainda abrem; arquivos `.wiff` reportam que as
bibliotecas da SCIEX estão indisponíveis.

## Onde as coisas ficam

| O quê | Onde |
|---|---|
| o runtime .NET | `~/.dotnet` |
| montagens baixadas, o índice do LIPID MAPS | `~/.milq` (substituível pela variável de ambiente `OPENPEAKVIEW_HOME`) |
| preferências: geometria da janela, última pasta, painéis recolhidos, o aviso inicial | o armazenamento de configurações da plataforma, sob `MIL-Q/MIL-Q` |
| projetos | onde quer que tenham sido salvos: arquivos `.oqproj`, ver [[projects-and-files]] |

## LIPID MAPS

O banco de dados de lipídios não é distribuído junto. O primeiro uso da aba
**LIPID MAPS** no Explorer oferece baixá-lo: um arquivo de 21 MB de
lipidmaps.org vira um índice local de 45 MB com 49,969 estruturas
curadas, depois do que as consultas não precisam de rede. Ver [[lipid-maps]].

## Verificar uma instalação

```
MIL-Q --selftest file.wiff
```

reporta a versão, a plataforma, se o índice do LIPID MAPS está instalado, se
as bibliotecas da SCIEX carregam e onde o runtime .NET foi encontrado, e
então abre cada arquivo nomeado e imprime o que foi lido. Ver
[[command-line]].

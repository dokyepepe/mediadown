# Media Downloader

Aplicativo desktop Windows para analisar, baixar e converter vídeos, áudios e playlists com **yt-dlp** e **FFmpeg**, usando uma interface nativa em **PySide6/Qt**. Não há conta, telemetria nem envio do histórico: configurações, fila e histórico permanecem locais.

> Use o aplicativo somente para conteúdo que você tem direito de acessar e baixar. O projeto não remove nem contorna DRM.

## Estado do projeto

Versão 1.1.0. O MVP implementa o fluxo completo de análise, seleção, fila, download, pós-processamento e histórico. A cobertura real de sites acompanha os extractors do yt-dlp; alterações nas plataformas podem exigir uma atualização do componente.

![Placeholder da tela inicial](docs/screenshots/home-placeholder.svg)

## Recursos

- interface Windows com sidebar, onboarding, estados vazios e tema claro/escuro/sistema;
- conjunto próprio de ícones SVG vetoriais, com renderização HiDPI pelo Qt;
- análise assíncrona de URL, título, autor, duração, origem, thumbnail e formatos;
- playlists enumeradas com ações para baixar um item, ignorar itens, baixar a seleção ou baixar tudo;
- vídeo automático/MP4/MKV/WEBM e limite de resolução disponível;
- áudio MP3/M4A/AAC/OPUS/FLAC/WAV, bitrate MP3, capa e metadados;
- legendas oficiais/automáticas, download ou incorporação;
- fila concorrente limitada de 1 a 5, cancelamento, retry e pausa de agendamento;
- progresso, velocidade, ETA, bytes e estados de FFmpeg sem exibir 100% prematuramente, com eventos limitados para downloads longos;
- histórico SQLite pesquisável, filtros e ações de arquivo/pasta/URL;
- página Sobre com catálogo das principais plataformas, validado contra os extractors instalados do yt-dlp e integrações nativas;
- reconhecimento de links Spotify com metadados via oEmbed, abertura no serviço e playlists autorizadas via OAuth 2.0 PKCE;
- preferências persistentes, templates de nome, proxy e cookies consentidos;
- logs rotativos sem registrar cookies, tokens e credenciais deliberadamente;
- atualização controlada do yt-dlp: wheel oficial do PyPI com SHA-256, ativado no reinício;
- Deno interno e yt-dlp-ejs para o suporte completo atual do extractor do YouTube;
- PyInstaller sem console e instalador Inno Setup x64 com atalhos e desinstalador.

## Arquitetura

```text
src/mediadownloader/
├── main.py                 # composição e entrada Qt
├── models/                 # dataclasses e enums
├── ui/                     # janela, páginas e widgets reutilizáveis
├── core/                   # yt-dlp, FFmpeg, formatos, workers e fila
├── services/               # configurações, SQLite, clipboard e update
└── utils/                  # paths, logs, validação, erros e formatação
```

A UI emite intenções; `QueueManager` e services coordenam o trabalho; `DownloadEngine` é a única camada que conhece yt-dlp. Operações bloqueantes rodam em `QThreadPool/QRunnable` e retornam à interface por signals/slots. Widgets Qt não são alterados por threads de background.

`MediaExtractor` escolhe o provedor de análise. URLs comuns seguem para `DownloadEngine`; URLs oficiais do Spotify seguem para `SpotifyService` e nunca são entregues ao método de download.

Dados do usuário:

- configurações e SQLite: `%LOCALAPPDATA%` por meio de `platformdirs`;
- logs: `%LOCALAPPDATA%\MediaDownloader\Logs\app.log` (o caminho exato pode variar conforme a política do Windows/platformdirs);
- componentes atualizados: subpasta `components` no diretório de dados local.
- autorização Spotify: Gerenciador de Credenciais do Windows, entrada `MediaDownloader/SpotifyOAuth`.

## Integração com Spotify

A integração é deliberadamente limitada a metadados. Links de faixas, álbuns, artistas, playlists, shows, episódios e audiobooks podem ser analisados via oEmbed sem login. O aplicativo mostra a capa sem recorte, identifica claramente a origem e sempre oferece **Abrir Spotify**.

O Media Downloader não baixa, descriptografa, converte ou exporta áudio do Spotify. Para uma busca manual em uma fonte independente e autorizada, o usuário pode copiar título e artista; nenhuma pesquisa ou download é iniciado automaticamente.

Para consultar até 20 itens de uma playlist pertencente à sua conta ou na qual você colabora:

1. Crie um aplicativo no [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Cadastre exatamente `http://127.0.0.1:43819/callback` em **Redirect URIs**.
3. Copie somente o **Client ID** — nunca é necessário informar o Client Secret.
4. Em Configurações → Spotify, informe o Client ID e escolha **Conectar conta**.
5. Autorize somente os escopos de leitura de playlists exibidos pelo Spotify.

O login ocorre no navegador padrão usando Authorization Code com PKCE e proteção `state`. Tokens não entram no arquivo de configurações ou nos logs; ficam no cofre de credenciais do usuário do Windows. Use **Desconectar** para removê-los.

Aplicativos Spotify em Development Mode estão sujeitos às regras e cotas atuais do serviço, inclusive restrições de usuário, propriedade/colaboração de playlists e possíveis requisitos de conta Premium do proprietário do aplicativo. Consulte a [documentação oficial de autorização](https://developer.spotify.com/documentation/web-api/concepts/authorization) e o [guia de mudanças de 2026](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide).

## Desenvolvimento

Requisitos: Windows 10/11 x64, Python 3.12 ou mais recente e PowerShell 5.1+. O script baixa um build FFmpeg “essentials” via HTTPS e valida o SHA-256 publicado pela mesma fonte.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts/run_dev.ps1
```

Sem baixar FFmpeg (útil para trabalhar apenas na UI/testes):

```powershell
.\scripts\setup_dev.ps1 -SkipFFmpeg
```

O usuário final não precisa de Python, FFmpeg nem Deno no PATH; os componentes são empacotados na distribuição.

## Testes

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

Os testes cobrem URLs, templates, sanitização, configurações, fila, formatadores, paths, seleção de formatos e histórico. Downloads reais não fazem parte da suíte unitária; o engine deve ser validado manualmente com conteúdo público autorizado antes de publicar uma release.

## Gerar o executável

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

Saída:

```text
dist/MediaDownloader/MediaDownloader.exe
```

O build é `onedir`, mais previsível para Qt e FFmpeg e mais rápido na inicialização que `onefile`. `utils/paths.py` resolve corretamente assets e binários no desenvolvimento e no bundle PyInstaller. A versão é definida uma única vez em `src/mediadownloader/version.py`; metadados do PE e do instalador são derivados dela no build.

## Gerar o instalador

Instale [Inno Setup 6](https://jrsoftware.org/isinfo.php) ou use:

```powershell
winget install --id JRSoftware.InnoSetup -e
powershell -ExecutionPolicy Bypass -File scripts/build_installer.ps1
```

Saída:

```text
release/MediaDownloader-Setup-x64.exe
```

O instalador usa `C:\Program Files\Media Downloader`, oferece atalhos na Área de Trabalho e Menu Iniciar e cria desinstalador. Na desinstalação, pergunta separadamente se dados pessoais devem ser removidos; por padrão eles são preservados.

## FFmpeg

`scripts/setup_ffmpeg.ps1` baixa `ffmpeg-release-essentials.zip` de gyan.dev, confere o hash publicado e copia somente `ffmpeg.exe` e `ffprobe.exe` para `resources/ffmpeg`. `scripts/setup_deno.ps1` faz o mesmo com a release oficial x64 do Deno e seu `.sha256sum`. Para substituir o build FFmpeg, mantenha os nomes e reveja as obrigações LGPL/GPL. O aplicativo nunca depende do PATH quando os binários internos existem.

## Atualização de componentes

O botão de atualização do yt-dlp consulta o JSON oficial do PyPI, baixa o wheel universal, valida o SHA-256 informado pelo índice e instala em dados locais. A nova versão entra em vigor depois de reiniciar. O FFmpeg é atualizado deliberadamente pelo processo de build, porque trocar sua licença/configuração silenciosamente em máquinas finais seria arriscado.

## Licenças

Veja [`licenses/THIRD_PARTY_NOTICES.md`](licenses/THIRD_PARTY_NOTICES.md). Preserve os avisos e licenças incorporados às dependências no bundle. Ao redistribuir FFmpeg sob GPL, cumpra também as obrigações de oferta/disponibilização do código-fonte correspondente.

## Troubleshooting

- **“FFmpeg não encontrado”**: execute `scripts/setup_ffmpeg.ps1` e reinicie o app.
- **Site deixou de funcionar**: em Configurações → Componentes, verifique/atualize yt-dlp.
- **Conteúdo privado**: configure cookies somente para uma conta à qual você tem acesso legítimo.
- **Erro de merge/conversão**: consulte `app.log`; confirme espaço em disco e a versão do FFmpeg.
- **Antivírus sinaliza build local**: builds PyInstaller sem assinatura podem gerar falso positivo. Para distribuição pública, assine EXE e Setup com certificado Authenticode.
- **Restrição geográfica/DRM**: o aplicativo informa o problema, mas não tenta contornar a proteção.
- **Playlist Spotify retorna acesso negado**: confirme que a conta é proprietária ou colaboradora, que o Client ID e a Redirect URI estão corretos e reconecte a conta.
- **Spotify não conecta**: libere a porta local `43819`, confira a Redirect URI exata e verifique as limitações atuais do Development Mode.

## Limitações conhecidas

- pausar a fila não suspende um processo ativo; apenas impede que o próximo comece;
- tamanho final é estimado quando a plataforma não informa o total;
- MP4 pode exigir remux; combinações incompatíveis são resolvidas pelo yt-dlp/FFmpeg sem recodificação sempre que possível;
- o executável e instalador gerados localmente não são assinados digitalmente;
- importação de cookies depende dos mecanismos e permissões do yt-dlp/navegador;
- atualização automática do aplicativo inteiro não está incluída; apenas o componente yt-dlp possui atualização controlada;
- o Spotify fornece apenas metadados; playlists são limitadas aos primeiros 20 itens para apresentação e seu áudio nunca é baixado.

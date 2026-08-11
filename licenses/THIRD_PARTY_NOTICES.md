# Componentes de terceiros

Esta distribuição incorpora componentes mantidos por projetos independentes:

- **yt-dlp** — disponibilizado sob The Unlicense. Fonte e licença: <https://github.com/yt-dlp/yt-dlp>
- **yt-dlp-ejs** — Unlicense; inclui componentes MIT/ISC. Fonte: <https://github.com/yt-dlp/ejs>
- **FFmpeg** — licenciado sob LGPL 2.1+ e, conforme as opções do build, GPL 2+. Fonte e informações legais: <https://ffmpeg.org/legal.html>. O script padrão usa o build “essentials” de gyan.dev; verifique `ffmpeg -version` para a configuração exata do binário distribuído.
- **Deno** — MIT License. Runtime JavaScript recomendado pelo yt-dlp para suporte completo ao YouTube: <https://github.com/denoland/deno>
- **PySide6 / Qt** — PySide6 é disponibilizado sob LGPLv3/GPLv3/licença comercial. Licenças: <https://www.qt.io/licensing/open-source-lgpl-obligations>
- **Python** — Python Software Foundation License: <https://docs.python.org/3/license.html>
- **platformdirs** — MIT License: <https://github.com/tox-dev/platformdirs>
- **PyInstaller** (ferramenta de build) — GPLv2 com exceção para distribuir aplicações: <https://pyinstaller.org/en/stable/license.html>
- **Spotify attribution asset** — o logotipo completo preto é um asset oficial não modificado, usado somente para atribuir metadados obtidos do Spotify. Spotify é marca da Spotify AB e não endossa este aplicativo. Fonte e regras de uso: <https://developer.spotify.com/documentation/design>. Consulte também `assets/third_party/spotify/SOURCE.md`.

Os avisos e arquivos de licença incluídos pelos pacotes Python/Qt no ambiente de build devem permanecer no diretório `_internal` gerado pelo PyInstaller. Ao trocar o build de FFmpeg, reavalie as obrigações de licença e disponibilização de código-fonte correspondentes.

# Componentes de terceiros

Esta distribuição incorpora componentes mantidos por projetos independentes:

- **yt-dlp** — disponibilizado sob The Unlicense. Fonte e licença: <https://github.com/yt-dlp/yt-dlp>
- **yt-dlp-ejs** — Unlicense; inclui componentes MIT/ISC. Fonte: <https://github.com/yt-dlp/ejs>
- **FFmpeg** — licenciado sob LGPL 2.1+ e, conforme as opções do build, GPL 2+. Fonte e informações legais: <https://ffmpeg.org/legal.html>. O script padrão usa o build “essentials” de gyan.dev; verifique `ffmpeg -version` para a configuração exata do binário distribuído.
- **Deno** — MIT License. Runtime JavaScript recomendado pelo yt-dlp para suporte completo ao YouTube: <https://github.com/denoland/deno>
- **PySide6 / Qt** — PySide6 é disponibilizado sob LGPLv3/GPLv3/licença comercial. Licenças: <https://www.qt.io/licensing/open-source-lgpl-obligations>
- **Python** — Python Software Foundation License: <https://docs.python.org/3/license.html>
- **packaging** — Apache License 2.0 ou BSD 2-Clause. Fonte: <https://github.com/pypa/packaging>
- **platformdirs** — MIT License: <https://github.com/tox-dev/platformdirs>
- **qrcode** — BSD License. Geração local de QR Codes na edição desktop: <https://github.com/lincolnloop/python-qrcode>
- **Pillow** — HPND License. Codificação PNG dos QR Codes no desktop: <https://python-pillow.github.io>
- **ZXing Core** — Apache License 2.0. Geração local de QR Codes no Android: <https://github.com/zxing/zxing>
- **PyInstaller** (ferramenta de build) — GPLv2 com exceção para distribuir aplicações: <https://pyinstaller.org/en/stable/license.html>
- **Spotify attribution asset** — o logotipo completo preto é um asset oficial não modificado, usado somente para atribuir metadados obtidos do Spotify. Spotify é marca da Spotify AB e não endossa este aplicativo. Fonte e regras de uso: <https://developer.spotify.com/documentation/design>. Consulte também `assets/third_party/spotify/SOURCE.md`.
- **Simple Icons / logos de plataformas** — formas vetoriais obtidas do projeto Simple Icons, disponibilizado sob CC0 1.0. As marcas continuam pertencendo aos respectivos titulares e seu uso apenas identifica as plataformas compatíveis; nenhuma delas endossa este aplicativo. Fonte e detalhes: <https://github.com/simple-icons/simple-icons>. Consulte também `assets/icons/brands/SOURCE.md`.

Os avisos e arquivos de licença incluídos pelos pacotes Python/Qt no ambiente de build devem permanecer no diretório `_internal` gerado pelo PyInstaller. Ao trocar o build de FFmpeg, reavalie as obrigações de licença e disponibilização de código-fonte correspondentes.

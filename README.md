# One Pace Legendas PT (Fixed) — Addon Stremio

Addon do Stremio com legendas em **português** para o [One Pace](https://onepace.net), o fan edit que remove o filler de One Piece.

> **Que variante de português?** A base é **PT-BR**, herdada da tradução da comunidade. Os arcos finais — **Whole Cake Island, Wapol's Omnivorous Hurrah, Reverie, Wano e Egghead** — foram adaptados a **PT-PT** neste fork (111 dos 465 episódios). Ver a tabela abaixo.

Fork do [addon original de rafaelmotac](https://github.com/rafaelmotac/onepace-ptbr-addon) com **legendas revistas, corrigidas e ressincronizadas**, alojado numa instância própria na Beamup.

Funciona com o **One Pace Addon**, **One Pace RD Premium** e qualquer outro addon que use episódios do One Pace no Stremio.

## Instalar

Cola este URL no Stremio (Addons > barra de pesquisa):

```
https://e4872e87374f-onepace-ptbr-addon.baby-beamup.club/manifest.json
```

As legendas aparecem automaticamente ao ver episódios do One Pace, como opção **Portuguese** (SRT limpo, compatível com qualquer player).

> Apenas a variante `.srt` é oferecida: o pipeline de legendas externas do Stremio só aceita `.srt`/`.vtt`, pelo que legendas `.ass` externas nunca carregam (stremio-bugs#2312).

## Episódios disponíveis (471 no total)

| Saga | Arcos | Episódios | Variante |
|------|-------|:---------:|----------|
| East Blue | Romance Dawn, Orange Town, Syrup Village, Gaimon, Baratie, Arlong Park, Buggy's Crew, Loguetown | 38 | PT-BR |
| Alabasta | Reverse Mountain, Whisky Peak, Koby-Meppo, Little Garden, Drum Island, Alabasta | 39 | PT-BR |
| Skypiea | Jaya, Skypiea | 33 | PT-BR |
| Water Seven | Long Ring Long Land, Water Seven, Enies Lobby, Post-Enies Lobby | 57 | PT-BR |
| Thriller Bark | Thriller Bark | 22 | PT-BR |
| Marineford | Sabaody, Amazon Lily, Impel Down, Straw Hats Adventures, Marineford, Post-War | 52 | PT-BR |
| Fishman Island | Return to Sabaody, Fishman Island | 27 | PT-BR |
| Dressrosa | Punk Hazard, Dressrosa, Zou | 80 | PT-BR |
| Whole Cake Island | Whole Cake Island, Wapol's Omnivorous Hurrah, Reverie | 43 | **PT-PT** (WC_2–WC_7 ficam em PT-BR) |
| Wano | Wano (Atos 1-3) | 60 | **PT-PT** (falta WA_55) |
| Egghead | Egghead | 20 | **PT-PT** |

Total: **354 em PT-BR**, **117 em PT-PT**. A adaptação PT-PT começou nos arcos que faltavam ver; os anteriores podem vir a ser convertidos, mas não há data.

> Legendas baseadas nas traduções da comunidade [onepaceptbr](https://onepaceptbr.github.io/) e no [repo oficial de legendas do One Pace](https://github.com/one-pace/one-pace-public-subtitles), com correções de sincronização e texto feitas neste fork.

## Como funciona

```
Stremio pede legendas para o episódio "RO_1"
  -> o addon consulta subs/mapping.json
  -> encontra 01_Romance_Dawn/RO_1.srt
  -> devolve o URL servido pelo próprio addon (/subs/01_Romance_Dawn/RO_1.srt)
  -> o Stremio mostra "Portuguese" na lista de legendas
```

O addon é um único serviço: o mesmo servidor Express responde ao manifest, ao handler de legendas e serve os ficheiros `.srt` da pasta `subs/`. Não depende de GitHub raw nem de um servidor estático separado.

- Sem configuração, os URLs das legendas são construídos a partir do host de cada pedido (`X-Forwarded-Host`/`Host`).
- A variável de ambiente `SUBS_BASE_URL` (definida na Beamup) tem prioridade e força uma base fixa.

## Correr localmente

```bash
npm install
npm start
```

O addon fica disponível em `http://127.0.0.1:7000/manifest.json` (porta configurável via `PORT`).

Para usar na rede local (ex. TV da sala), substitui `127.0.0.1` pelo IP da máquina.

## Publicar alterações (deploy na Beamup)

O deploy é feito por git push para o remote `beamup`:

```bash
git add -A
git commit -m "fix: corrige legendas do episódio X"
git push beamup main:master
```

O branch local é `main`, mas a Beamup só faz deploy do `master` — daí o `main:master`. O servidor recompila e reinicia a app sozinho (~2 minutos). Se o push falhar com "pre-receive hook declined", costuma ser um erro transitório do servidor — repete o push.

As respostas ficam em cache no Cloudflare até 4 horas (`max-age=14400`), portanto alterações podem demorar a refletir-se em episódios pedidos recentemente.

### Os `.ass` não vão no deploy

`subs/` tem ~461 MB, dos quais ~447 MB são `.ass`. O addon nunca os oferece (só a variante `.srt`, ver nota acima), mas continuam a fazer falta em git: são a fonte de posicionamento do `fix_subtitle_positions.py`. Por isso são apagados **durante o build**, não do repo:

```json
"heroku-prebuild": "node scripts/strip_deploy_assets.js --yes"
```

O buildpack Node corre este script antes de instalar dependências, e a imagem final fica com ~14 MB de legendas em vez de ~461 MB.

> Não tentes fazer isto com `.dockerignore` nem `.slugignore` — **nenhum dos dois funciona aqui**. Não há Dockerfile (a Beamup usa buildpacks herokuish, que ignoram o `.dockerignore`), e o herokuish só lê o `.slugignore` no comando `slug-generate`, que o dokku não corre — ele corre `buildpack-build`. O hook do `package.json` é o único ponto que executa mesmo.

Para ver o que seria removido, sem apagar nada: `npm run strip:dry`.

## Atualizar legendas

### A partir do repo oficial do One Pace

```bash
git clone https://github.com/one-pace/one-pace-public-subtitles.git
npm run convert
```

### A partir do Google Drive (onepaceptbr)

```bash
npm run download
npm run download:dry  # só listar
```

## Testes e lint

```bash
npm test
npm run lint
```

## Estrutura do projeto

```
onepace-ptbr-addon-fixed/
├── index.js                     # Addon Stremio + servidor de legendas (ESM)
├── package.json
├── Procfile                     # Processo web para a Beamup (dokku)
├── beamup.json                  # Configuração do projeto na Beamup
├── logo.png                     # Logo do addon (servido em /logo.png)
├── subs/                        # Legendas corrigidas, por arco
│   ├── mapping.json             # Mapeamento ID de episódio -> caminho
│   ├── 01_Romance_Dawn/
│   │   ├── RO_1.srt             # servido ao Stremio
│   │   └── RO_1.ass             # original, só para os scripts (não vai no deploy)
│   └── ...
├── scripts/
│   ├── subtitle_converter.py    # Módulo partilhado
│   ├── convert_ass_to_srt.py    # Converte ASS -> SRT
│   ├── download_all_subs.py     # Descarrega do Google Drive
│   ├── fix_subtitle_positions.py # Desempilha legendas sobrepostas nos .srt
│   ├── translate_subs.py        # Traduz EN -> PT-BR
│   └── strip_deploy_assets.js   # Tira os .ass do slug (ver secção do deploy)
└── tests/
    └── addon.test.js            # Testes do addon
```

## Créditos

- [One Pace](https://onepace.net) — projeto de fan edit de One Piece
- [One Pace Public Subtitles](https://github.com/one-pace/one-pace-public-subtitles) — legendas oficiais
- [onepaceptbr](https://onepaceptbr.github.io/) — equipa de tradução PT-BR
- [rafaelmotac/onepace-ptbr-addon](https://github.com/rafaelmotac/onepace-ptbr-addon) — addon original de que este projeto é fork
- [Stremio Addon SDK](https://github.com/Stremio/stremio-addon-sdk)
- [One Pace Addon](https://github.com/fedew04/OnePaceStremio) — catálogo e streams para o Stremio

## Licença

MIT

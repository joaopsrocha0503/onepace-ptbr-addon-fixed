# PROJECT GOAL — Legendas One Pace (addon Stremio)

> Ficheiro de contexto para retomar o trabalho em qualquer sessão nova.
> **Última atualização: 2026-07-22**

## ▶️ ONDE COMEÇAR NA PRÓXIMA SESSÃO

**Traduzir `subs/37_Egghead/EH_1.srt` para PT-PT, e continuar daí para a frente.**
O arco 36 (Wano) está **completo: WA_1 … WA_54**. Falta só o **arco 37 — Egghead
(EH_1 … EH_20)**, o último do âmbito.
Não é preciso pedir confirmação — o utilizador já autorizou avançar arco fora.

⚠️ **O extrator de texto do `.srt` tem de casar blocos pelo cabeçalho seguinte, não pela
próxima linha em branco** — ver [Método para ficheiros grandes](#método-para-ficheiros-grandes-extrair--traduzir--reinjetar).
Um parser ingénuo salta os blocos de créditos **sem dar erro**.

⚠️ **Ler antes de traduzir a primeira linha:** os `.srt` foram achatados pela frente 1.
Isso muda como se traduz e como se verifica — ver
[Impacto do achatamento na tradução](#impacto-do-achatamento-na-tradução).

| Frente | Estado |
|---|---|
| **1. Posicionamento / sobreposição** | ✅ **CONCLUÍDA.** 117 episódios, em produção na Beamup como **v2.1.0** (`9d5839f`) desde 2026-07-21 |
| **2. Adaptação PT-BR → PT-PT** | ▶️ **EM CURSO.** Arcos 33/34/35/36 completos; falta só o 37 (Egghead). Em produção como **v2.5.0** |

---

# FRENTE 1 — Posicionamento das legendas (✅ CONCLUÍDA)

> Fechada a 2026-07-21. Commit `a73777f`, em produção na Beamup.
> Mantida aqui como registo: se aparecer alguma sobreposição estranha em Wano ou
> Egghead (que não foram vistos a olho), é aqui que está tudo o que é preciso saber.

## Problema

Os `.srt` foram convertidos a partir dos `.ass` e a conversão **deitou fora todo o
posicionamento** (`\pos`, `\move`, `\anN`, alinhamento do estilo). Resultado: cartazes,
letreiros e notas de tradução — que no original apareciam no topo ou a meio do ecrã —
caem todos para o rodapé e ficam **sobrepostos ao diálogo**. É mais visível em nomes de
ataques e nos quadros de apresentação de personagens (nome, recompensa, etc.).

Há ainda dois tipos de lixo gráfico no `.srt`:
- **Karaoke do genérico expandido letra a letra** — um bloco de SRT por caractere
  (o WC_23 tem 414). Estilos `IS_ROM`, `Karaoke*`, `Kanji*`.
- **Logo animado do fansub** partido em 4 peças (Mola / Shi / Chibukai / Fansub!).
  Estilos `NDTBoard`, `NDTSkull`, `NDTHat`, `NDTHat2`.

## Posicionamento NÃO funciona no Stremio — testado e descartado

Testado no Stremio a 2026-07-21, com o WC_15, as duas vias falharam. **Não voltar a
tentar nenhuma delas:**

| Tentativa | Resultado |
|---|---|
| `{\an8}` / `{\an5}` num `.srt` | O Stremio imprime a tag **como texto no ecrã** (`{\an5}SALA DO TESOURO`) |
| `line:45% align:center` num `.vtt` | O Stremio **ignora os cue settings** e empilha na mesma no rodapé |

O `.vtt` chegou a parecer bom porque já não mostrava lixo, mas o letreiro ficou a ~85% da
altura em vez dos 45% pedidos — e, pior, **por baixo** do diálogo, invertendo a relação do
original (o Stremio empilha por ordem de início).

## Solução adotada: achatamento das sobreposições

Em vez de pedir posicionamento ao leitor, a sobreposição é eliminada **no próprio
ficheiro**. Onde vários blocos coincidem no tempo, o tempo é partido nas fronteiras e o
que está ativo em simultâneo passa a ser **um único bloco multi-linha**:

```
00:07:05,100 --> 00:07:05,940   Ainda consegues ficar de pé?
00:07:05,940 --> 00:07:09,010   SALA DO TESOURO
                                Ainda consegues ficar de pé?
00:07:09,010 --> 00:07:09,700   SALA DO TESOURO
```

A **ordem dentro do bloco** vem da zona vertical original no `.ass` (topo primeiro, rodapé
por último), o que repõe a relação que o fansub tinha: cartaz por cima do diálogo. Os
`.ass` no repo são os originais PT-BR com toda a formatação, logo a zona é **derivada, não
adivinhada** (`\pos`/`\move` → fração da altura; senão o `\anN` ou o alinhamento do estilo).

Vantagens sobre as tentativas falhadas: funciona em **qualquer leitor**, controla a ordem,
e mantém-se em `.srt` — zero alterações ao `index.js`, ao `mapping.json` ou ao deploy.

Custo aceite: os **timestamps deixam de ser comparáveis 1:1** com o original, porque os
blocos são partidos nas fronteiras de sobreposição. Ver secção de verificação.

**Decisão do utilizador (2026-07-21):** remover karaoke letra-a-letra **e** logo do fansub.
Mas as **notas de tradução ficam** (estilo `NDTText`, ex.: *"Memo vem de 'memória'."*) —
são conteúdo, e ficam por cima do diálogo.

## Comandos

```bash
# análise, não escreve nada
python scripts/fix_subtitle_positions.py WC_15 WC_23

# aplicar (o --backup é a única forma de voltar atrás se a estratégia mudar)
python scripts/fix_subtitle_positions.py WC_15 --write --backup subs_pre_merge

# aplicar a tudo
python scripts/fix_subtitle_positions.py --all --write --backup subs_pre_merge
```

## Verificação por episódio

Os timestamps mudam por definição, por isso **não** se compara `-->`. O que tem de se
verificar é que **nenhum texto desapareceu** além do lixo gráfico:

```bash
python -c "
import sys; sys.path.insert(0,'scripts')
from fix_subtitle_positions import parse_srt
o=parse_srt('subs_pre_merge/<arco>/<EP>.srt'); n=parse_srt('subs/<arco>/<EP>.srt')
blob='\n'.join(e['text'] for e in n)
print(sorted({e['text'] for e in o if e['text'] not in blob}))
"
```

Só devem sair `Mola`, `Shi`, `Chibukai`, `Fansub!` (o logo) e, se houver genérico
convertido letra a letra, os caracteres soltos. O próprio script já aborta sem escrever
se detetar perda de conteúdo no achatamento.

## Armadilhas já encontradas (não repetir)

- **O emparelhamento tem de casar por TEXTO antes de casar por ordem.** Vários eventos
  partilham os mesmos timestamps (diálogo + cartaz + logo). Emparelhar só por ordem faz
  com que, num `.srt` que já perdeu blocos, a fila desalinhe e se **apague a linha errada**
  — cheguei a perder a nota de tradução do WC_15 assim. Corrigido em `pair_entries()`.
- **Não descartar segmentos curtos sem verificar cobertura.** Uma versão anterior descartava
  em silêncio tudo abaixo de 120 ms, o que podia apagar uma legenda inteira. `drop_slivers()`
  só descarta quando o conteúdo continua visível noutro segmento.
- **`scripts/regenerate_srt.py` DESFAZ esta correção** — regenera o `.srt` do `.ass`. Se
  algum dia for preciso correr, correr o `fix_subtitle_positions.py` logo a seguir.
- O texto do `.srt` **diverge** do `.ass` nos episódios já traduzidos para PT-PT (o `.ass`
  está em PT-BR). Por isso o casamento por texto não chega sozinho.
- Reexecutar o script **é seguro** (verificado byte a byte no WC_15 e no WC_23): depois do
  achatamento não há sobreposições, logo não há nada para fundir.
- **Há `.ass` corrompidos na origem.** 9 ficheiros têm linhas `Dialogue:` inválidas e
  faziam o script rebentar. Dois padrões distintos: falta o campo `End`
  (`EN_7.ass:311`), ou a linha tem só 4 dos 10 campos, saltando de `End` direto para o
  texto (os 31 versos do genérico em `PW_1/3/4/5/6`). `parse_ass()` valida e ignora,
  **contando e reportando** com `[!]` na saída. Verificado que **não se perde conteúdo**:
  o bloco do `.srt` fica sem par e é tratado como diálogo normal no rodapé.

## Âmbito

**Decisão do utilizador (2026-07-21): só de Whole Cake Island para a frente.** Os arcos
anteriores (`01_Romance_Dawn` … `32_Zou`) deixaram de ser relevantes — não aplicar lá.

Âmbito = arcos **33 a 37**: `WC` (39) + `COVER_WAPOL` (1) + `REV` (3) + `WA` (54) +
`EH` (20) = **117 episódios**.

## Deteção de lixo — quatro camadas

Chegou-se a estas quatro por tentativa e erro. Nenhuma sozinha chega, e a ordem importa.

| # | Regra | Apanha |
|---|---|---|
| 1 | `DROP_STYLES` — lista explícita de nomes | `IS_ROM`, `Karaoke*`, `Kanji*`, peças do logo `NDT*` |
| 2 | `junk_styles()` — estilo com ≥10 blocos e **mediana ≤2 caracteres** | Karaoke de arcos novos, sem depender do nome: `TOPPU` (Wano), `Translation ED` (Egghead), `Insert` |
| 3 | `drop_scattered_glyphs()` — **≥4 cues de ≤2 caracteres em simultâneo** | Texto espalhado pelo ecrã a soletrar. Escapa às outras duas: estilo legítimo no resto do ficheiro e duração longa |
| 4 | Fragmento de ≤2 caracteres e ≤250 ms | Restos soltos |

E `protected()` **imuniza** estilos de conteúdo (letreiros, cartazes, notas, créditos,
diálogo) contra a camada 2 — ver armadilhas.

## Estado atual — ✅ APLICADO

| | |
|---|---|
| Episódios processados | 117 / 117 |
| Abortados | 0 |
| Cues sobrepostas no resultado | **0** |
| Blocos finais | 51 308 |
| Blocos removidos | 25 139 |
| — fragmentos de karaoke (≤4 chars) | 24 439 |
| — peças do logo do fansub | 520 |
| — palavras de karaoke (estilo `TOPPU`) | 180 |
| Remoções inesperadas | **0** |
| `.srt` com tags `{\an}` literais | **0** |
| Caracteres corrompidos (`U+FFFD`) | **0** (nos `.srt` e nos `.ass`) |
| Testes | 9 / 9 |
| Idempotência | verificada em WC_23, WA_13, EH_15 |

Originais em `subs_pre_merge/` (mesma estrutura de arcos, no `.gitignore`).

**Validação:** só o **WC_15** foi visto a olho no Stremio. Os outros 116 foram validados
por comparação automática contra o backup. O utilizador optou por não ver Wano/Egghead
para evitar spoilers — se aparecer algo estranho quando lá chegar, corrige-se então.

## Fecho — 2026-07-21

- Commit `a73777f` na `main` (ramo `fix/legendas-sobrepostas`, integrado com fast-forward)
- `git push origin main` — backup no GitHub
- `git push beamup main:master` — **deploy feito e verificado em produção**

Verificação em produção (com `?cb=<sha>` para furar a cache de 4 h do Cloudflare):
o handler devolve o caminho com subpasta de arco, o `.srt` servido é byte a byte igual ao
local, **0 cues sobrepostas** e **0 tags literais**. O caminho antigo e plano dá 404,
como esperado.

Os originais pré-achatamento estão em `subs_pre_merge/`, que está no `.gitignore` --
**só existem nesta máquina**. O histórico do git preserva as versões anteriores.

### Versão e compatibilidade — `9d5839f`

Addon subido a **2.1.0** (minor, não major): nada parte do lado de quem consome — o `id`
do manifest, os recursos e os tipos mantêm-se, e o Stremio apanha os URLs novos sozinho,
**sem reinstalar**. Mas é mais do que um patch: mudou a organização de `subs/`, o esquema
de URLs e os 117 ficheiros de legendas.

O `index.js` ganhou uma **rota de compatibilidade** para `/subs/<ficheiro>.srt`, o formato
plano usado até à reorganização. As respostas ficam 4 h em cache no Cloudflare, por isso um
cliente pode continuar a pedir o caminho antigo durante esse tempo — sem a rota recebia 404
e ficava sem legendas. Só apanha um segmento, logo nunca colide com
`/subs/<arco>/<ficheiro>`, e devolve **302** (não 301) para não envenenar caches se a
estrutura voltar a mudar. Coberta por teste.

**Nota sobre a cache:** ao contrário do deploy anterior, não foi preciso esperar 4 h — os
`.srt` ficaram em caminhos novos, que nunca tinham estado em cache, portanto não havia
cópia velha para expirar.

## A verificação tem de procurar lixo CRIADO, não só conteúdo perdido

O erro mais caro desta frente. A primeira aplicação aos 117 episódios passou com
"0 remoções inesperadas" e foi dada como concluída. **Estava errada.** A verificação só
procurava conteúdo *perdido*, e o problema era o inverso: conteúdo *criado*.

Os fragmentos de karaoke de Wano e Egghead não foram removidos nem perdidos — foram
**fundidos** pelo achatamento em blocos de até **74 linhas**, em 111 dos 117 ficheiros.
Nenhuma verificação de perda apanha isso.

Por isso `process()` tem agora **duas** redes simétricas, e ambas abortam sem escrever:

1. nenhum bloco de entrada pode desaparecer;
2. nenhum bloco de saída pode fundir mais de `MAX_MERGED_ABORT` (4) cues **minúsculas**.

A guarda 2 conta **cues fundidas, não linhas** — um bloco de créditos do fansub é uma só
cue com 23 linhas e é perfeitamente legítimo. E só aborta quando as cues são minúsculas:
há momentos com 8–10 elementos simultâneos legítimos (música inserida, cenas cheias de
letreiros), que ficam empilhados — que é o que o leitor faria de qualquer forma — e
geram apenas um aviso `[~]`.

## Uma heurística por mediana varre estilos de conteúdo

A camada 2 (`junk_styles`) chegou a apagar `Captions-207+` e `OPLetreros` — **letreiros de
cenário**, conteúdo a sério — em episódios onde esses estilos calhavam ter entradas
curtas. Notou-se porque havia remoções aos **39 minutos**, muito longe do genérico.

Daí `protected()`: estilos cujo nome contém `caption`, `letrero`, `sign`, `note`, `title`,
`credit`, `narrator`, `main`, `normal`, … nunca são deduzidos como lixo. Só saem por
`DROP_STYLES` explícito. **Ao acrescentar arcos novos, verificar sempre o que foi removido
com mais de 4 caracteres** — é aí que os falsos positivos aparecem.

## Armadilha de verificação (custou-me duas verificações falsas)

No Windows o `glob`/`rglob` devolve caminhos com `\`, por isso um
`caminho.replace('subs_pre_merge/', 'subs/')` **nunca corresponde** — o script acaba a
comparar cada ficheiro consigo próprio e reporta alegremente "0 diferenças". Usar
`Path.relative_to()` e um `assert` de que o par existe.

Outra: comparar textos com `x not in blob` faz correspondência de **substring**, e um bloco
de karaoke com um único caractere (`B`, `i`, `n`) encontra-se sempre dentro de qualquer
texto. É preciso comparar por **sequências contíguas de linhas** exatas.

Comando de verificação correto:

```python
from pathlib import Path
import sys; sys.path.insert(0, 'scripts')
from fix_subtitle_positions import parse_srt

def windows(entries):
    out = set()
    for e in entries:
        ls = e['text'].split('\n')
        for i in range(len(ls)):
            for j in range(i + 1, len(ls) + 1):
                out.add('\n'.join(ls[i:j]))
    return out

root = Path('subs_pre_merge')
for bak in sorted(root.rglob('*.srt')):
    novo = Path('subs') / bak.relative_to(root)
    assert novo.exists(), novo
    pres = windows(parse_srt(str(novo)))
    falta = [e['text'] for e in parse_srt(str(bak)) if e['text'] not in pres]
    inesperado = {t for t in falta
                  if t not in {'Mola', 'Shi', 'Chibukai', 'Fansub!'} and len(t.strip()) > 2}
    if inesperado:
        print(novo.name, sorted(inesperado)[:4])
```

Não deve imprimir nada.

---

# FRENTE 2 — Adaptação PT-BR → PT-PT (▶️ ATIVA)

> Retomada a 2026-07-21, depois de a frente 1 fechar. **Próximo: WA_11.**

## Impacto do achatamento na tradução

A frente 1 reescreveu os `.srt`. Três consequências, todas obrigatórias:

1. **Traduzir por cima do que está em `subs/`** — nunca a partir de `subs_pre_merge/`.
   Usar o backup como fonte desfaz a correção das sobreposições.
2. **Alguns blocos contêm agora mais do que uma legenda** (cartaz + diálogo, ou
   nota + nome de ataque), em linhas separadas dentro do mesmo bloco. Traduzir **cada
   linha no lugar**: não juntar linhas, não reordenar, não colapsar o bloco. A ordem
   codifica a posição original no ecrã (o que estava em cima fica na primeira linha).
3. **A verificação por `diff` de timestamps deixou de servir** — o achatamento partiu
   blocos nas fronteiras de sobreposição, logo os tempos mudaram de propósito. Verificar
   por *conteúdo*, com o método de janelas de linhas da frente 1: comparar o ficheiro
   traduzido contra si próprio antes da tradução, e confirmar que só mudou texto.

Uma verificação simples e suficiente por episódio: o **número de blocos e todos os
timestamps têm de ficar exatamente iguais** antes e depois de traduzir, porque a tradução
só toca no texto.

```bash
diff <(grep -E ' --> ' <copia-antes>) <(grep -E ' --> ' subs/33_Whole_Cake_Island/WC_N.srt)
```

Sem output = integridade OK.

## Arquitetura (Opção A, já implementada)

- `subs/` é **PT-PT** (traduzido no lugar); `subs_ptbr_backup/` guarda os originais PT-BR.
  **Zero alterações de código.** O histórico git também preserva os originais.
- Cada ficheiro é UTF-8, LF. Formato SRT: número / timestamps / texto / linha em branco.

## Regras de tradução

Ver **`STYLE_GUIDE_PTPT.md`** (aprovado pelo utilizador). Resumo do essencial:
- `você`→`tu` com conjugação de 2.ª pessoa; ênclise (`diz-me`, `preocupas-te`).
- Gerúndio → `a` + infinitivo (`está a fazer`).
- Realeza/superiores → 3.ª pessoa de cortesia (Vossa Majestade, Kaido-sama acalme-se).
- **Preservar sempre:** nomes próprios, nomes de ataques (Gomu Gomu no…, Gear Fourth),
  honoríficos (-sama, -chan, -kun, -san), sufixos-onomatopeia da Big Mom e restantes
  personagens, e os blocos de créditos do fansub + notas de tradução.
- Artigos PT antes de nomes: `a mama`, `a Germa`, `o Sanji`.
- Vocabulário (amostra): ônibus→autocarro, celular→telemóvel, suco→sumo,
  banheiro→casa de banho, droga→raios, garota→miúda/rapariga, garoto→rapaz,
  chutar→dar pontapé, bunda→rabo, café da manhã→pequeno-almoço, berinjela→beringela,
  sério→a sério, entendi→percebi, sobrenome→apelido, quebrar→partir, conectar→ligar,
  decepção→deceção, jornada→viagem, lugar→sítio, que saco→que seca, moleza→canja.
- Pretérito PT-PT com acento: começámos, chegámos, derrotámos; connosco, anónimo,
  cerimónia, dezasseis, "Controlo de qualidade" (nos créditos).
- "caprichado" NÃO é PT-PT → usar "bem-feito".

## Âmbito acordado

- **NÃO traduzir WC_2–WC_7** (ficam em PT-BR por opção do utilizador).
- Processo por episódio: traduzir no lugar em `subs/`, **verificar timestamps** no fim.
- **NÃO** mostrar amostra episódio a episódio.
- **Parar e avisar** só se algo não se enquadrar no guia. O utilizador concedeu autonomia
  de decisão ("confio no teu julgamento").
- Autonomia para fazer o **redeploy** sem esperar por aprovação (dado a 2026-07-22).
- Ao fechar um arco: dar resumo e **atualizar este ficheiro**.

## Progresso

| Arco | Ficheiros | Estado |
|---|---|---|
| 33 — Whole Cake Island | WC_1, WC_8–WC_39 | ✅ 32/32 (2026-07-22). WC_2–WC_7 ficam em PT-BR por opção |
| 34 — Wapol's Omnivorous Hurrah | COVER_WAPOL_1 | ✅ 1/1 (2026-07-22) |
| 35 — Reverie | REV_1–REV_3 | ✅ 3/3 (2026-07-22) |
| 36 — Wano | WA_1–WA_54 | ✅ **54/54** (2026-07-22) |
| **37 — Egghead** | **EH_1–EH_20** | ⬜ **0/20, por começar. Próximo: EH_1** |

> ⚠️ **Não confiar só nesta tabela** — já esteve desatualizada e levou a retraduzir o
> WC_23, que afinal já estava feito. Método fiável para descobrir o próximo por traduzir:
> contar marcadores PT-BR por ficheiro
> (`você`, `a gente`, `acontecendo`, `falando`, `hein?`, `vilarejo`, gerúndios `-ndo`).
> ```bash
> cd subs/36_Wano
> for f in WA_*.srt; do echo "$f $(grep -ciE 'você|a gente|acontecendo|falando|hein\?' $f)"; done
> ```
>
> **Como ler o resultado:** há um salto claro, não um limiar fino. A 2026-07-22 os
> traduzidos (WA_1–WA_36) davam **0 a 10** e os por traduzir (WA_37+) davam **33 a 70**.
> Tudo o que está abaixo de ~10 é falso positivo — `vocês` e `boa gente`/`toda a gente`
> são legítimos em PT-PT. Na dúvida, abrir o ficheiro e olhar: um episódio por traduzir
> nota-se à primeira linha de diálogo.

## Método para ficheiros grandes (extrair → traduzir → reinjetar)

Os episódios de Reverie e Wano têm 400–900 linhas de texto. Reescrever o `.srt` inteiro
à mão arrisca partir timestamps. O método usado desde 2026-07-22:

1. **Extrair** só as linhas de texto, percorrendo o `.srt` estruturalmente (tudo o que vem
   a seguir a uma linha com `-->` até à linha em branco seguinte).
2. **Traduzir** esse ficheiro plano, mantendo a **contagem de linhas exatamente igual** —
   uma linha de entrada, uma linha de saída, na mesma ordem.
3. **Reinjetar** nas mesmas posições. Números de bloco, timestamps e linhas em branco
   nunca são tocados.

O script (`srt.js`, com os modos `extract` e `splice`) é descartável e vive no scratchpad
da sessão — são ~50 linhas de Node, mais rápido reescrever do que ir procurar. O `splice`
**aborta** se a contagem de linhas não bater certo, que é a rede de segurança principal.

Antes de reinjetar, confirmar o alinhamento com um `paste` lado a lado em 3–4 pontos do
ficheiro; se as linhas escorregarem, o erro é silencioso e espalha-se por tudo.

### ⚠️ Três armadilhas do script (todas custaram retrabalho a 2026-07-22)

1. **O fim de um bloco NÃO é a próxima linha em branco.** Os blocos de créditos do fansub
   têm **linhas em branco lá dentro** (`Timing:` ⏎ `FJATP` ⏎ ⏎ `Gráficos:` …). Um parser
   que pare na primeira linha em branco salta esse texto **sem dar erro** — o `splice`
   passa, o `diff` de timestamps passa, e o bloco fica em PT-BR. O fim do bloco é o
   **cabeçalho do bloco seguinte** (linha só com dígitos seguida de uma linha com `-->`).
   Este bug existia também nas sessões anteriores: os créditos de todos os arcos 33/35 e
   de WA_1–WA_10 ficaram por traduzir e só foram corrigidos a 2026-07-22.
2. **Os `.srt` são maioritariamente CRLF.** Ler, `split('\n')` e juntar com `'\n'` produz um
   ficheiro **misto** CRLF/LF. Detetar o terminador dominante e voltar a juntar com ele.
3. **Não mexer nos espaços iniciais/finais.** Muitas linhas de continuação começam por um
   espaço. O `splice` deve **repor os espaços do original** à volta do texto traduzido, em
   vez de confiar em quem escreveu a tradução.

E a armadilha que não é do script: **nunca colapsar duas linhas numa só**. Um letreiro de
duas linhas (`ATRAÇÕES` / `PRINCIPAIS`) tem de continuar a ser duas linhas depois de
traduzido (`OS` / `HEADLINERS`). O `splice` aborta e diz quantas linhas faltam; para
encontrar **onde**, alinhar os dois ficheiros pelas linhas-âncora (letreiros em maiúsculas
e URLs) e reportar o primeiro índice em que divergem.

> **Localizador de desalinhamento que funciona** (usado no WA_46 e no WA_49, os dois
> únicos episódios de WA_37–54 em que colapsei uma frase de duas linhas numa só). Voltar a
> extrair o original para um ficheiro à parte e procurar o ponto em que a tradução passa a
> corresponder à linha *anterior* do original:
> ```js
> const a = fs.readFileSync('orig.txt','utf8').split('\n').map(s=>s.trim());
> const b = fs.readFileSync('trad.txt','utf8').split('\n').map(s=>s.trim());
> for (let i=1;i<a.length-1;i++)
>   if (a[i]!==b[i] && a[i]!=='' && a[i]===b[i-1]) { console.log('desvio em', i+1, a[i]); break; }
> ```
> Comparar as posições das **linhas em branco** dos dois ficheiros estreita primeiro a
> janela — os blocos de créditos e os letreiros multi-linha têm brancos lá dentro e são
> âncoras fiáveis.

⚠️ **Bug do `splice` a evitar ao reescrever o script:** `split(/\r?\n/)` já devolve um
elemento `''` final quando o ficheiro acaba em newline. Voltar a acrescentar o terminador
no `join` duplica-o e o ficheiro fica com mais um byte — o `cmp` de ida-e-volta apanha isto
e é o primeiro teste a fazer (extrair + reinjetar um episódio **já traduzido** e confirmar
que fica byte a byte igual).

Só o `.srt` é traduzido. **O `.ass` fica intocado** (continua em PT-BR) — é a fonte do
posicionamento da frente 1, não é servido ao utilizador.

> ⚠️ **Os `.srt` já foram achatados pela frente 1.** Ao retomar a tradução, traduzir por
> cima do resultado achatado que está em `subs/` — **nunca** a partir do `subs_pre_merge/`.
> Alguns blocos contêm agora mais do que uma legenda (cartaz + diálogo): traduzir cada
> linha no lugar, sem juntar, reordenar nem colapsar linhas.
>
> A verificação antiga por `diff` de timestamps **já não se aplica** — os tempos mudaram
> com o achatamento. Comparar contra `subs_pre_merge/` com o método de janelas de linhas
> descrito na frente 1.

## Decisões a consolidar no guia de estilo

- WC_11+ introduzem um **tema de encerramento** ("Somos a esperança") com pequenas
  variações de fraseado por episódio — traduzir de forma consistente.
- **Germa = feminino** ("a Germa", "toda a Germa será minha").
- **"a mama" = Big Mom**, mas **"mamã" = Sora** (mãe biológica do Sanji, WC_15), para
  distinguir as duas personagens.
- **"apelido" (PT-BR = nickname) → "alcunha"** (em PT-PT "apelido" é *sobrenome*).
- **"bilhão" → "mil milhões"**.
- Sufixos-onomatopeia preservados: -bon, -soir, -fa, -ju, -nasu, -souffle, -rero (Bege),
  -gao (Pekoms), -nen (Du Feld), -Lambida/-pero (Perospero), -quiquiriquí (Tamago).
- Créditos: **"Controle de qualidade" → "Controlo de qualidade"**; restantes labels
  mantidos (Edição de vídeo, Tempos/Timing, Edição de áudio, Legendas, Revisão).
- Vocabulário adicional: pesquisa→investigação, meleca→ranho, pelúcia→peluche,
  geladeira→frigorífico, zumbi→zombie, gêmeas→gémeas, gênio→génio, úmido→húmido,
  machucar→magoar, respingar→salpicar, servo→criado, zombar→gozar, "que cara"→"que tipo",
  "dar certo"→"correr bem", "chance"→"hipótese/oportunidade".

## ⚠️ Termos em inglês — MANTER em inglês

**Decisão do utilizador (2026-07-22):** termos do universo One Piece que estão em inglês
**não se traduzem**, mesmo que o PT-BR de origem os tenha traduzido.

O caso que deu origem à regra: traduzi *Headliner* para "Astro Principal" nos WA_1–WA_10
(o original oscilava entre "Astro Principal" e "Atração Principal") — corrigido a
2026-07-22, ficam todos **Headliner** / **Headliners** / **HEADLINER** nos letreiros.

Manter tal e qual: `Headliner`, `Gifter`, `SMILE`, `Raid Suit`, `Vivre Card`, `Room`,
`Shambles`, nomes de ataques e de técnicas, `Den Den Mushi`, `Kibi Dango`, `yokozuna`,
`ronin`, `daimyo`, `seppuku`, `sakoku`/`kaikoku`, honoríficos e sufixos japoneses.

> Já vinham traduzidos do PT-BR de origem e **ficam como estão**, por serem a forma
> estabelecida no material: "Piratas das Feras", "Nove Bainhas Vermelhas",
> "Governador Geral", "Akuma no Mi"/"Fruta do Diabo". A regra aplica-se a escolhas
> *novas* minhas, não a reverter o que o fansub já tinha fixado.

## Convenções fixadas no arco Wano

- **`Headliner`** (ver acima) e **`UTILIZADOR DA SMILE DE X`** nos letreiros.
- `Fazenda Paradisíaca` → **`Quinta Paradisíaca`**.
- `vilarejo`/`Vila` → **`Aldeia`** (Okobore, Amigasa), mas **`Cidade Bakura`** — o
  original chama "vilarejo" a ambas, mas Bakura é a cidade dos oficiais.
- `sumô` → **`sumo`**; `abdômen` → **`abdómen`**; `Fênix` → **`Fénix`**.
- `Hein?` → **`Hã?`** (sempre, incluindo em `, hein?` → `, não é?` / `, hã?`).
- `pirralho`/`moleque` → **`fedelho/a`**; `cachorro` → **`cão`**; `garota` → **`miúda`**.
- `cachoeira` → **`cascata`**; `banheiro` → **`casa de banho`**.
- **`Rei Neptune`** (não "Netuno") — coerência com o arco Reverie.
- `Recompensa: ¬1.5 Bilhões` → **`¬1,5 Mil Milhões`**.
- O **genérico de abertura** repete-se em todos os episódios com pequenas variações de
  redação no original — usar sempre o mesmo fraseado PT-PT. Nas canções vale a regra §8
  do guia: a métrica ganha, o gerúndio pode ficar.
- O **aviso do reprodutor** (`Seu reprodutor de mídia não suporta…`) também varia de
  episódio para episódio no original — mesmo fraseado PT-PT em todos.
- Gralhas do original corrigidas em silêncio quando inequívocas: `Kaidouu`, `cortouo`,
  `á deriva`, `sauce salgado`, `brilo`, `PIRATAS FESTAS`, `muto`, `Kouzki`, `Grágicos`,
  `PREHISTÓRICA`, `espirítos`, `leles`, `houveram`, `jutando`, `sere fugia`,
  `pequeninoss`, `finji`, `captivos`, `Pedir para ela guardar` (→ `Pedi-lhe`).
  Restos de espanhol no original também: `MONJE Y COVEIRO`, `Plata`, `TENDÃO DE RES`,
  `Aviso de rompimiento`, `guardias`, e o aviso do reprodutor inteiro em espanhol no WA_31.
  E um erro de facto: o WA_35 legenda o Edward Newgate como **"Piratas da Barba Negra"** —
  corrigido para **Barba Branca**.

## Convenções fixadas em WA_11–WA_36

- **Créditos do fansub:** `Controle de qualidade` → **`Controlo de qualidade`**,
  `Karaokê` → **`Karaoke`**. Os labels em inglês (`Timing`, `Typesetting`,
  `Quality Control`, `Soundtracking`, `Graphics`, `Subtitle Editing`) **ficam em inglês** —
  é assim que o original os escreve nos episódios mais recentes.
- **Aviso do reprodutor** — fraseado único em todos os episódios:
  `O teu reprodutor de multimédia não suporta o formato de legenda usado neste episódio.` /
  `É provável que as legendas não funcionem corretamente.` /
  `Usa um dos reprodutores de vídeo recomendados, de preferência o mpv:` / `https://mpv.io`
- **`berries`** (não `BERRYS`/`BERRIS`) — é a forma que o resto do corpus usa.
- `bilhão`/`bilhões` → **`mil milhões`**; nas recompensas ditas por extenso,
  `Dois bilhões duzentos e…` → **`Dois mil duzentos e…`**.
- **`Grande Astro` / `Grandes Astros`** (All-Stars) **mantém-se em português** — é forma já
  fixada pelo fansub, como `Governador Geral`. A regra dos termos ingleses aplica-se a
  escolhas novas minhas; o caso do `Headliner` foi decidido explicitamente pelo utilizador.
- `Waiters`, `Gifters`, `Pleasures`, `Numbers`, `Smile`, `SAD`, `Tobiroppo`, `Sumashi`,
  `Smart Tanishi`, `Tanishi Visual`, `Ryuuou`, `Meitou`, `Enma`, `Ame no Habakiri`,
  `Kapparyuu`, `Ninpou`, `aburaage`, `kappa`, `youkai` — todos em inglês/japonês.
- `sumô` → **`sumo`** (e `Sumo Infernal`); `apelido` (=alcunha) → **`alcunha`**;
  `Fazenda` → **`Quinta`**; `cachoeira` → **`cascata`**; `banheiros públicos` →
  **`banhos públicos`**; `garçonete` → **`empregada (de mesa)`**; `zumbi` → **`zombie`**;
  `geisha` → **`gueixa`**; `franco-atirador` mantém-se.
- **`Cidade Bakura`** mesmo quando o original escreve `Vila`/`Vilarejo Bakura`.
- Alcunhas inventadas mantêm-se como nomes próprios (`Musgojuurou`, `Sombrangoro`,
  `Gizão`, `Balão`, `Barbinha`); só `Cejogoro` foi aportuguesado para **`Sobrancegoro`**
  por ser espanhol (`ceja`).

## Convenções fixadas em WA_37–WA_54 (fecho do arco)

- **`Headliner`** também onde o original escreve `Astro Principal` / `Atração Principal`
  (WA_43, WA_51, WA_52, WA_53) — coerente com a decisão do utilizador.
- **`Grande Astro` / `Grandes Astros`** para o *posto* de All-Star, mesmo onde o original
  escreve `Celebridade(s)` (WA_44, WA_47, WA_48, WA_49, WA_50, WA_52, WA_54). **Exceção
  deliberada:** no número do Queen no WA_43 (`quem é a atração principal?` / `a celebridade
  do canto e da dança?`) ficou `atração principal`/`celebridade`, porque ali é trocadilho de
  showman e não o nome do posto.
- **Aviso do reprodutor**: o original aparece em **inglês** (WA_38, WA_51, WA_54) e em
  variantes PT-BR — todos convertidos para o mesmo fraseado PT-PT de sempre.
- **Créditos**: `Trilha Sonora` → **`Banda Sonora`**; `Controle de Qualidade` →
  **`Controlo`**; `Karaokê` → **`Karaoke`**. Quando o bloco inteiro está em inglês
  (`Video Editing`, `Quality Control`, `Timing`…) **fica em inglês** (WA_51).
- `Fênix` → **`Fénix`**; `zumbi` → **`zombie`**; `Karatê` → **`Karaté`**;
  `terremoto` → **`terramoto`**; `equipe` → **`equipa`**; `saquê` → **`saqué`**;
  `infectado` → **`infetado`**; `demônio` → **`demónio`**.
- `sobrenome` (=nome de família) → **`apelido`** (WA_40); `apelido` (=alcunha) →
  **`alcunha`**, como já estava.
- `Casa de Show`/`Salão de Shows` → **`Casa de Espetáculos`**; `portão/porta dos fundos` →
  **`portão/porta das traseiras`**; `Fazenda Paradisíaca` → **`Quinta Paradisíaca`**;
  `Vilarejo Bakura` → **`Cidade Bakura`**; `cachoeiras` → **`cascatas`**.
- `chutar a bunda` → **`dar um pontapé no rabo`**; `pirralho/moleque` → **`fedelho/puto`**;
  `garoto/cara` → **`rapaz/tipo`**; `pessoal/galera` → **`malta`**; `Beleza!/Eba!` →
  **`Boa!`**; `Droga!` → **`Raios!`**; `Que saco/Que chato` → **`Que seca`**;
  `babaca` → **`idiota`**; `puxa-sacos` → **`graxistas`**; `dar no pé/cair fora` →
  **`pirar-nos/sair daqui`**; `Foi mal` → **`Desculpa`**; `legal/maneiro` → **`fixe`**.
- Recompensas: `4 Bilhões 388 Milhões` → **`4 Mil Milhões e 388 Milhões de Berries`**;
  `1.5 bilhão` → **`1,5 mil milhões`**.
- **Termos mantidos**: `Sulong`, `Gifters`, `Pleasures`, `Waiters`, `Numbers`, `Tobiroppo`,
  `Oniwabanshu`, `kunoichi`, `oni`, `kappa`, `oshiruko`, `mochi`, `tatame`, `Live Floor`,
  `pleasure hall`, `Golden Festival`, `Wapometal`, `road poneglyph`, `Haki`, `Ryuo`,
  `Akuma no Mi …`, nomes de ataques e alcunhas (`Yamabro`, `Chobro`, `Desgrenhado`,
  `Ruivotaro`, `Buggyjiro`, `Cabeça de Musgo`, `Pay-Pay`, `Mana`, `-gara`, `mew`, `miau`).
- **Gralhas do original corrigidas em silêncio:** `emde três dias`, `cadeirão`→`caldeirão`,
  `setença`→`sentença`, `Técnicamente`, `MONGES CEGO`→`MONGE CEGO`, `KURI, CASTILLO`
  (espanhol)→`CASTELO`, `se despidou`→`despiu-se`, `Grágicos`, `almeijamos`→`almejamos`,
  `combicei`→`acalentei`, `desgraçadoo`, `logol`, `Qaualquer`, `o luffy`→`o Luffy`,
  `ão se esqueça`→`não te esqueças`, `é muito divirto`→`é muito divertido`,
  `Atachem seus pés`→`Ataquem-lhe os pés`, `1.5 bilhão`.
- **Incoerências do próprio original mantidas** (não são gralhas inequívocas):
  `Kanjuro, a Chuva da Noite` (WA_41) vs `Kanjuro Chuva da Tarde` (WA_47);
  `Torre do Cérebro Direito` (WA_51) vs `Torre do Hemisfério Direito` (WA_52);
  `Kaido` vs `Kaidou` na mesma cena.

## ⚠️ Género dos termos em inglês — NÃO assumir masculino

**Decisão do utilizador (2026-07-22):** perante um termo inglês, **não assumir logo o
masculino nem copiar o artigo do PT-BR de origem**. Parar, pensar qual é o substantivo
português subjacente, e **pesquisar na internet** o uso estabelecido quando houver dúvida.

O que deu origem à regra: eu tinha fixado "o Red Line" e "o Grand Line" só porque era
assim que o original PT-BR estava. Está errado — a pesquisa confirma que o uso
estabelecido em português é **feminino** para ambos (`linha`/`rota` são femininos), e o
guia da Omelete até usa o pronome: *"Para atravessá-**la**"*, a falar da Red Line, apesar
de a Red Line ser um **continente**. Corrigido a 2026-07-22 em WC_1, WC_8, WC_10, REV_2 e REV_3.

**Método:** identificar o substantivo português subjacente (`Line`→`linha`, f.;
`Blue`→`mar`, m.; `Suit`→`fato`, m.), e confirmar com uma pesquisa se o uso da comunidade
não seguir a lógica. A lógica sozinha não chega — a Red Line é um continente (masculino)
mas trata-se por feminino.

| Termo | Género | Porquê |
|---|---|---|
| `a Red Line`, `a Grand Line` | **feminino** | `linha`/`rota`; uso estabelecido, confirmado por pesquisa |
| `o East/North/South/All Blue` | masculino | `mar` |
| `a Vivre Card` | **feminino** | forma dominante no corpus (WC_7, WC_10–WC_27) |
| `o Sunny` | masculino | `navio` |
| `o Log Pose`, `o Raid Suit`, `o Clima Tact`, `o Haki` | masculino | `dispositivo`, `fato`, `bastão`, termo japonês |
| `a Shusui`, `a Kitetsu` | feminino | `espada` |
| `um Headliner` / `uma Headliner` | **varia com a pessoa** | nome de agente: Holdem é `um`, Speed é `uma` |

## Convenções fixadas no arco Reverie

- **`o Reverie`** (masculino — é uma *conferência/conselho*, mas o uso corrente trata-o
  como masculino; mantido).
- Solfejo dos príncipes Ryugu aportuguesado: `-fa-so-la-si-do` → **`-fá-sol-lá-si-dó`**,
  `-fa-mi-re-do` → **`-fá-mi-ré-dó`**.

---

# Estrutura do repositório

`subs/` está organizada em **subpastas numeradas por arco, em ordem cronológica**
(`01_Romance_Dawn` … `37_Egghead`). `subs_ptbr_backup/` e `subs_originais_backup/`
espelham a mesma estrutura.

- `subs/mapping.json` mapeia videoID → caminho relativo (ex.: `33_Whole_Cake_Island/WC_15.srt`).
- `index.js` serve `subs/` estaticamente (`app.use("/subs", express.static(...))`).
  ⚠️ Os URLs usam `encodePath()`, **não** `encodeURIComponent` — este último converteria
  a `/` em `%2F` e partiria todos os URLs.
- A regra de arcos vive num só sítio: `ARC_DIR` / `arc_subdir()` em
  `scripts/subtitle_converter.py`. Os scripts de download/conversão já a usam.
- `COVER_WAPOL` (*Wapol's Omnivorous Hurrah*) não tem pasta no GDrive, logo não está em
  `ARC_PREFIX`; entra em `_EXTRA_ARCS`, posicionado a seguir a Whole Cake Island.

**Depois de mexer em `subs/` é preciso redeploy para a Beamup** (os URLs das legendas mudam).

## Problema conhecido, não relacionado

`npx eslint` falha com `'setTimeout' is not defined` em `index.js`. É **pré-existente**
(confirmado por `git stash`), falta `globals.node` no `eslint.config.js`. Não corrigido
por estar fora de âmbito.

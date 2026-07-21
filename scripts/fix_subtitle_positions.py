#!/usr/bin/env python3
"""Elimina legendas sobrepostas nos .srt, usando o .ass emparelhado como fonte.

Problema
--------
Os .srt do addon foram convertidos a partir dos .ass e a conversao deitou fora
todo o posicionamento (\\pos, \\move, \\anN, alinhamento do estilo). Cartazes,
letreiros e notas de traducao -- que no original apareciam no topo ou a meio do
ecra -- caem todos para o rodape, em cima do dialogo.

Porque nao se resolve com posicionamento
----------------------------------------
Testado no Stremio (2026-07-21), as duas vias falharam:

  - {\\an8} num .srt  -> o Stremio imprime a tag como TEXTO no ecra;
  - line:45% num .vtt -> o Stremio ignora os cue settings e empilha na mesma.

Estrategia adotada: achatamento
-------------------------------
Em vez de pedir posicionamento ao leitor, a sobreposicao e eliminada no proprio
ficheiro. Onde varios blocos coincidem no tempo, o tempo e partido nas fronteiras
e o que esta ativo em simultaneo passa a ser UM unico bloco multi-linha:

    00:07:05,100 -> 00:07:05,940   Ainda consegues ficar de pe?
    00:07:05,940 -> 00:07:09,010   SALA DO TESOURO
                                   Ainda consegues ficar de pe?
    00:07:09,010 -> 00:07:09,700   SALA DO TESOURO

A ordem dentro do bloco vem da zona vertical original no .ass (topo primeiro,
rodape por ultimo), o que repoe a relacao que o fansub tinha: o cartaz por cima
do dialogo. Funciona em qualquer leitor, porque nao depende de suporte a
posicionamento nenhum.

Sao ainda removidos os blocos que sao puramente graficos: o karaoke do generico
expandido letra a letra (um bloco por caractere) e os pedacos do logo animado do
fansub. As notas de traducao (estilo NDTText) SAO conteudo e ficam.

Reexecutar e seguro: depois do achatamento ja nao existem sobreposicoes, logo
uma segunda passagem nao tem nada para fundir e reproduz o mesmo ficheiro.
Verificado byte a byte no WC_15 e no WC_23. Ainda assim, usar --backup na
primeira aplicacao -- e a unica forma de voltar atras se a estrategia mudar.

Uso
---
  python scripts/fix_subtitle_positions.py WC_15               # so analisa
  python scripts/fix_subtitle_positions.py WC_15 --write
  python scripts/fix_subtitle_positions.py --all --write --backup subs_pre_merge
"""

import argparse
import collections
import os
import re
import shutil
import statistics
import sys

SUBS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "subs")

# Estilos que sao elementos graficos, nao legendas.
# NDTText NAO entra aqui: transporta a nota de traducao (conteudo util).
# Os restantes NDT* sao os pedacos do logo do fansub.
DROP_STYLES: tuple[str, ...] = (
    "Karaoke", "Kanji", "IS_ROM", "NDTBoard", "NDTSkull", "NDTHat", "NDTHat2",
)

# Fracao da altura do ecra que separa as tres zonas verticais.
TOP_LIMIT = 0.35
MID_LIMIT = 0.62

ZONE_RANK = {"top": 0, "mid": 1, "bottom": 2}

# Segmentos mais curtos do que isto sao descartados -- so quando nao fazem falta
# (ver drop_slivers), para nao piscarem no ecra.
MIN_SEGMENT_MS = 120

# Um estilo com >= JUNK_MIN_BLOCKS blocos e mediana <= JUNK_MAX_CHARS caracteres
# e karaoke silaba a silaba (ver junk_styles).
JUNK_MIN_BLOCKS = 10
JUNK_MAX_CHARS = 2

# Marcas de nome que identificam estilos de CONTEUDO (dialogo, letreiros,
# cartazes, notas, creditos). Ver protected(): imunes a heuristica de karaoke.
PROTECTED_MARKS: tuple[str, ...] = (
    "caption", "letrero", "sign", "note", "title", "titulo", "credit",
    "narrator", "main", "normal", "recuerdo", "pensante", "flashback",
    "thought", "secondary", "denden", "enmedio", "principio", "warning",
    "default", "lyrics",
)

# Fragmento de <= 2 caracteres e <= TINY_MS: e karaoke, nao legenda.
TINY_MS = 250

# Quantas cues de <= 2 caracteres em simultaneo bastam para serem texto
# espalhado pelo ecra e nao dialogo (ver drop_scattered_glyphs).
GLYPH_GROUP_MIN = 4

# Quantas cues distintas se podem fundir num bloco antes de ser sinal de lixo.
# Cartaz + dialogo + nota = 3; acima de 4 e karaoke por classificar. Conta cues
# FUNDIDAS, nao linhas: um bloco de creditos do fansub e uma so cue com 23
# linhas e e perfeitamente legitimo.
MAX_MERGED_ABORT = 4

# Rede de seguranca: acima desta fracao de blocos sem par no .ass, algo esta
# muito errado (.ass trocado, .srt de outra fonte) e aborta-se sem escrever.
# Nao serve para detetar reexecucao -- essa e inofensiva, ver docstring.
UNMATCHED_ABORT = 0.25


def ass_time(value: str) -> int:
    hours, minutes, seconds = value.split(":")
    return int(round((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000))


def srt_time(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000 + int(millis)


def fmt_ms(total: int) -> str:
    hours, total = divmod(total, 3600000)
    minutes, total = divmod(total, 60000)
    seconds, millis = divmod(total, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def normalize(text: str) -> str:
    """Texto comparavel entre .ass e .srt: sem tags, quebras uniformizadas."""
    text = re.sub(r"\{[^}]*\}", "", text)
    text = text.replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ")
    return "\n".join(line.strip() for line in text.split("\n")).strip()


_ASS_TIME = re.compile(r"^\d+:\d{2}:\d{2}\.\d+$")


def parse_ass(path: str) -> tuple[int, dict[str, int], list[dict], int]:
    """-> (PlayResY, {estilo: alinhamento}, [eventos por ordem], nº malformadas)

    Ha .ass com linhas Dialogue corrompidas na origem -- o EN_7.ass, por
    exemplo, tem uma linha sem o campo End. Sao ignoradas e contadas, nunca
    silenciosamente: o bloco correspondente do .srt fica sem par e acaba como
    dialogo normal no rodape, que e o comportamento seguro.
    """
    text = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")

    play_res_y = 720
    match = re.search(r"^PlayResY:\s*(\d+)", text, re.M)
    if match:
        play_res_y = int(match.group(1))

    styles: dict[str, int] = {}
    style_format = None
    events: list[dict] = []
    event_format = None
    malformed = 0

    for line in text.split("\n"):
        if line.startswith("Format:") and "Alignment" in line:
            style_format = [x.strip() for x in line[len("Format:"):].split(",")]
        elif line.startswith("Format:") and "Text" in line:
            event_format = [x.strip() for x in line[len("Format:"):].split(",")]
        elif line.startswith("Style:") and style_format:
            fields = dict(zip(style_format, line[len("Style:"):].split(",")))
            styles[fields["Name"].strip()] = int(fields["Alignment"])
        elif line.startswith("Dialogue:") and event_format:
            # o campo Text e o ultimo e pode conter virgulas
            parts = line[len("Dialogue:"):].split(",", len(event_format) - 1)
            fields = dict(zip(event_format, parts))
            start, end = fields.get("Start", "").strip(), fields.get("End", "").strip()
            if (len(parts) < len(event_format) or "Text" not in fields
                    or not (_ASS_TIME.match(start) and _ASS_TIME.match(end))):
                malformed += 1
                continue
            events.append({
                "start": ass_time(start),
                "end": ass_time(end),
                "style": fields.get("Style", "").strip(),
                "text": fields["Text"],
            })

    return play_res_y, styles, events, malformed


def zone_of(event: dict, styles: dict[str, int], play_res_y: int) -> str:
    """Zona vertical de um evento .ass: 'top' | 'mid' | 'bottom'."""
    text = event["text"]

    # \pos / \move ganham ao alinhamento. Com varias ocorrencias, o libass
    # aplica a ultima.
    y = None
    moves = re.findall(r"\\move\(\s*[-\d.]+\s*,\s*([-\d.]+)", text)
    if moves:
        y = float(moves[-1])
    positions = re.findall(r"\\pos\(\s*[-\d.]+\s*,\s*([-\d.]+)", text)
    if positions:
        y = float(positions[-1])

    if y is not None:
        ratio = y / play_res_y
        if ratio < TOP_LIMIT:
            return "top"
        return "mid" if ratio < MID_LIMIT else "bottom"

    alignment = None
    for match in re.finditer(r"\\an([1-9])", text):
        alignment = int(match.group(1))
    if alignment is None:
        alignment = styles.get(event["style"], 2)

    if alignment in (7, 8, 9):
        return "top"
    return "mid" if alignment in (4, 5, 6) else "bottom"


def parse_srt(path: str) -> list[dict]:
    raw = open(path, encoding="utf-8-sig").read().replace("\r\n", "\n")
    blocks = [b for b in raw.strip().split("\n\n") if b.strip()]
    entries: list[dict] = []

    for block in blocks:
        lines = block.split("\n")
        match = re.match(r"\s*([\d:]+,\d+) --> ([\d:]+,\d+)", lines[1] if len(lines) > 1 else "")
        if not match:
            # texto com uma linha em branco no meio parte o bloco em dois:
            # reagregar ao anterior em vez de perder conteudo
            if entries:
                entries[-1]["text"] += "\n\n" + block
                continue
            raise ValueError(f"bloco SRT malformado no inicio de {path}: {block[:80]!r}")
        entries.append({
            "start": srt_time(match.group(1)),
            "end": srt_time(match.group(2)),
            "text": "\n".join(lines[2:]),
        })

    return entries


def pair_entries(entries: list[dict], events: list[dict]) -> list[dict | None]:
    """Emparelhar cada bloco do .srt com o evento .ass correspondente.

    Varios eventos partilham timestamps (ex.: dialogo + cartaz + logo do fansub),
    por isso a chave temporal sozinha nao chega. Dentro de cada grupo:

      1. casar por texto igual;
      2. o que sobrar, casar por ordem de ficheiro, que a conversao preservou.

    O passo 2 continua a ser preciso porque o texto do .srt diverge do .ass nos
    episodios ja traduzidos para PT-PT (o .ass esta em PT-BR).
    """
    by_key: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
    for index, entry in enumerate(entries):
        by_key[(entry["start"], entry["end"])].append(index)

    events_by_key: dict[tuple[int, int], list[dict]] = collections.defaultdict(list)
    for event in events:
        events_by_key[(event["start"], event["end"])].append(event)

    pairing: list[dict | None] = [None] * len(entries)

    for key, indices in by_key.items():
        candidates = events_by_key.get(key, [])
        taken = [False] * len(candidates)

        pending = []
        for index in indices:
            wanted = normalize(entries[index]["text"])
            for position, event in enumerate(candidates):
                if not taken[position] and normalize(event["text"]) == wanted:
                    pairing[index] = event
                    taken[position] = True
                    break
            else:
                pending.append(index)

        leftover = (event for position, event in enumerate(candidates) if not taken[position])
        for index in pending:
            pairing[index] = next(leftover, None)

    return pairing


def junk_styles(entries: list[dict], pairing: list[dict | None]) -> set[str]:
    """Estilos .ass cujos blocos sao fragmentos de karaoke letra-a-letra.

    Detetado pela FORMA, nao pelo nome. Os nomes variam muito por arco e por
    fansub -- Wano usa "TOPPU", Egghead "Translation ED", Whole Cake "IS_ROM" --
    e uma lista de nomes fixa deixa sempre arcos novos de fora. Um estilo cuja
    mediana de comprimento de texto e <= 2 caracteres, ao longo de dezenas de
    blocos, so pode ser karaoke silaba a silaba: nenhuma legenda a serio tem
    essa forma.

    Isto importa muito mais do que parece. Se estes blocos ficarem, sobrepoem-se
    uns aos outros e o achatamento funde-os num unico bloco de dezenas de linhas
    -- chegaram a aparecer blocos de 74 linhas em Wano.
    """
    per_style: dict[str, list[int]] = collections.defaultdict(list)
    for index, entry in enumerate(entries):
        event = pairing[index]
        if event is not None:
            per_style[event["style"]].append(len(entry["text"].strip()))

    return {
        style for style, lengths in per_style.items()
        if not protected(style)
        and len(lengths) >= JUNK_MIN_BLOCKS
        and statistics.median(lengths) <= JUNK_MAX_CHARS
    }


def protected(style: str) -> bool:
    """Estilos que nunca podem ser varridos pela heuristica de karaoke.

    A mediana engana-se em estilos de CONTEUDO que, num episodio concreto,
    calhem ter entradas curtas -- ja aconteceu com "Captions-207+" e
    "OPLetreros", que sao letreiros de cenario e chegaram a ser apagados a meio
    do episodio, aos 39 minutos, muito longe do generico.

    Um estilo destes so sai por DROP_STYLES explicito, nunca por deducao.
    """
    lowered = style.lower()
    return any(mark in lowered for mark in PROTECTED_MARKS)


def classify(entries: list[dict], events: list[dict], styles: dict[str, int],
             play_res_y: int) -> tuple[list[dict], list[tuple[dict, str]], int]:
    """-> (blocos a manter com zona atribuida, blocos removidos, sem par)"""
    pairing = pair_entries(entries, events)
    kept: list[dict] = []
    dropped: list[tuple[dict, str]] = []
    unmatched = 0
    junk = junk_styles(entries, pairing)

    for index, entry in enumerate(entries):
        event = pairing[index]
        text = entry["text"].strip()

        if event is None:
            unmatched += 1
            # sem par no .ass e com 1-2 caracteres: karaoke expandido
            if len(text) <= 2:
                dropped.append((entry, "karaoke-expandido"))
                continue
            entry["zone"] = "bottom"
        else:
            if event["style"].startswith(DROP_STYLES):
                dropped.append((entry, event["style"]))
                continue
            if event["style"] in junk:
                dropped.append((entry, f"karaoke:{event['style']}"))
                continue
            entry["zone"] = zone_of(event, styles, play_res_y)

        # rede final: fragmento minusculo que escapou a classificacao por estilo
        if len(text) <= 2 and entry["end"] - entry["start"] <= TINY_MS:
            dropped.append((entry, "fragmento-minusculo"))
            continue

        kept.append(entry)

    return kept, dropped, unmatched


def drop_scattered_glyphs(kept: list[dict]) -> tuple[list[dict], list[dict]]:
    """Remover grupos de cues de 1-2 caracteres exibidas ao mesmo tempo.

    Sao texto espalhado pelo ecra a soletrar uma palavra, posicionado caractere
    a caractere. Escapa as outras duas redes: o estilo pode ser legitimo no
    resto do ficheiro (o InsertEsp do WC_3 tem 49 blocos, mediana 13 chars) e a
    duracao pode ser longa (2,2 s no mesmo caso).

    O sinal decisivo e a simultaneidade: dialogo a serio nunca tem quatro ou
    mais legendas de um caractere no ecra ao mesmo tempo.
    """
    tiny = [e for e in kept if len(e["text"].strip()) <= 2]
    doomed: set[int] = set()

    for anchor in tiny:
        group = [e for e in tiny
                 if e["start"] < anchor["end"] and e["end"] > anchor["start"]]
        if len(group) >= GLYPH_GROUP_MIN:
            doomed.update(id(e) for e in group)

    return ([e for e in kept if id(e) not in doomed],
            [e for e in kept if id(e) in doomed])


def flatten(kept: list[dict]) -> list[dict]:
    """Partir o tempo nas fronteiras e fundir o que estiver ativo em simultaneo."""
    edges = sorted({t for entry in kept for t in (entry["start"], entry["end"])})
    segments: list[dict] = []

    for start, end in zip(edges, edges[1:]):
        active = [e for e in kept if e["start"] <= start and e["end"] >= end]
        if not active:
            continue
        # topo primeiro, rodape por ultimo -- repoe a ordem original
        active.sort(key=lambda e: ZONE_RANK[e["zone"]])
        text = "\n".join(e["text"] for e in active)

        # o achatamento parte blocos que nada tinha por baixo: reunir
        if segments and segments[-1]["text"] == text and segments[-1]["end"] == start:
            segments[-1]["end"] = end
        else:
            segments.append({"start": start, "end": end, "text": text, "active": active})

    return drop_slivers(segments)


def drop_slivers(segments: list[dict]) -> list[dict]:
    """Remover segmentos curtos de mais para serem lidos.

    So se descarta um segmento quando todo o seu conteudo continua visivel
    noutro segmento -- caso contrario perdia-se uma legenda inteira, que foi
    exatamente o que uma versao anterior deste script fazia em silencio.
    """
    keepers = [s for s in segments if s["end"] - s["start"] >= MIN_SEGMENT_MS]
    covered = {id(e) for s in keepers for e in s["active"]}
    return [
        s for s in segments
        if s["end"] - s["start"] >= MIN_SEGMENT_MS
        or any(id(e) not in covered for e in s["active"])
    ]


def process(srt_path: str, ass_path: str, write: bool = False,
            backup_dir: str | None = None, subs_dir: str | None = None) -> dict:
    play_res_y, styles, events, malformed = parse_ass(ass_path)
    entries = parse_srt(srt_path)

    kept, dropped, unmatched = classify(entries, events, styles, play_res_y)

    if entries and unmatched / len(entries) > UNMATCHED_ABORT:
        return {
            "aborted": f"{unmatched}/{len(entries)} blocos sem par no .ass"
                       " -- este .srt ja parece achatado; reprocessar do original",
        }

    kept, scattered = drop_scattered_glyphs(kept)
    dropped.extend((e, "glifos-espalhados") for e in scattered)

    segments = flatten(kept)

    # rede de seguranca: nenhum texto util pode desaparecer
    blob = "\n".join(s["text"] for s in segments)
    lost = [e for e in kept if e["text"] not in blob]
    if lost:
        return {"aborted": f"{len(lost)} blocos perdidos no achatamento (bug) -- nada escrito"}

    # Guarda contra o inverso: em vez de perder conteudo, CRIAR lixo. Se sobrar
    # karaoke por classificar, o achatamento funde-o num bloco enorme -- uma
    # verificacao que so procure conteudo perdido nunca apanha isso.
    #
    # Conta cues FUNDIDAS, nao linhas: um bloco de creditos do fansub e uma so
    # cue com 23 linhas e e legitimo. E so aborta quando as cues fundidas sao
    # MINUSCULAS, que e a assinatura do karaoke silaba a silaba. Ha momentos
    # legitimos com 8-10 elementos simultaneos (musica inserida, cenas cheias de
    # letreiros); esses ficam empilhados -- que e o que o leitor faria de
    # qualquer forma -- e so geram aviso.
    crowded = [s for s in segments if len(s["active"]) > MAX_MERGED_ABORT]
    for segment in crowded:
        lengths = [len(e["text"].strip()) for e in segment["active"]]
        if statistics.median(lengths) <= JUNK_MAX_CHARS + 1:
            return {"aborted": f"bloco com {len(segment['active'])} cues minusculas fundidas"
                               f" em {fmt_ms(segment['start'])} -- sobrou karaoke por"
                               " classificar; nada escrito"}

    if write:
        if backup_dir and subs_dir:
            relative = os.path.relpath(os.path.dirname(srt_path), subs_dir)
            target = backup_dir if relative == "." else os.path.join(backup_dir, relative)
            os.makedirs(target, exist_ok=True)
            shutil.copy2(srt_path, os.path.join(target, os.path.basename(srt_path)))

        blocks = [
            f"{number}\n{fmt_ms(s['start'])} --> {fmt_ms(s['end'])}\n{s['text']}\n"
            for number, s in enumerate(segments, 1)
        ]
        with open(srt_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(blocks))

    return {
        "total": len(entries),
        "kept": len(kept),
        "segments": len(segments),
        "merged": sum(1 for s in segments if len(s["active"]) > 1),
        "dropped": dropped,
        "crowded": len(crowded),
        "malformed": malformed,
        "zones": collections.Counter(e["zone"] for e in kept),
    }


def find_episodes(subs_dir: str) -> dict[str, str]:
    """id do episodio -> pasta que o contem (subs/ esta organizada por arco)."""
    index: dict[str, str] = {}
    for root, _dirs, files in os.walk(subs_dir):
        for name in files:
            if name.endswith(".ass"):
                index.setdefault(name[:-4], root)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("episodes", nargs="*", help="ids de episodio (ex.: WC_15 WC_23)")
    parser.add_argument("--all", action="store_true", help="processar todos os episodios")
    parser.add_argument("--write", action="store_true", help="escrever (sem isto, so analisa)")
    parser.add_argument("--backup", help="guardar o .srt original nesta pasta antes de escrever")
    parser.add_argument("--subs", default=SUBS_DIR, help="caminho para subs/")
    args = parser.parse_args()

    index = find_episodes(args.subs)
    if not index:
        print(f"Erro: nenhum .ass encontrado em {args.subs}")
        sys.exit(1)

    episodes = sorted(index) if args.all else args.episodes
    if not episodes:
        print("Erro: indique ids de episodio ou --all")
        sys.exit(1)

    print("MODO:", "ESCRITA" if args.write else "ANALISE (nada e escrito)")
    problems = 0

    for episode in episodes:
        directory = index.get(episode)
        srt_path = os.path.join(directory, f"{episode}.srt") if directory else None

        if directory is None or not os.path.exists(srt_path):
            print(f"  {episode}: sem .ass/.srt, ignorado")
            problems += 1
            continue

        result = process(
            srt_path, os.path.join(directory, f"{episode}.ass"),
            args.write, args.backup, args.subs,
        )

        if "aborted" in result:
            print(f"  {episode}: ABORTADO -- {result['aborted']}")
            problems += 1
            continue

        reasons = collections.Counter(reason for _, reason in result["dropped"])
        print(
            f"  {episode}: {result['total']} -> {result['segments']} blocos"
            f" | {result['merged']} fundidos"
            f" | removidos {len(result['dropped'])} {dict(reasons)}"
            f" | zonas {dict(result['zones'])}"
            + (f"  [!] {result['malformed']} linhas .ass malformadas"
               if result["malformed"] else "")
            + (f"  [~] {result['crowded']} blocos com >4 cues empilhadas"
               if result["crowded"] else "")
        )

    if problems:
        print(f"\n{problems} episodios com problemas (ver acima)")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Regenerate clean .srt files from their paired .ass source in subs/.

Fixes the bug where decorative karaoke/romaji opening-theme effects (hundreds of
sub-second syllable fragments) were included indiscriminately, corrupting the
ordering and timing of the .srt and hiding real dialogue for the rest of the
episode.

Rules (per spec):
  - Iterate "Dialogue:" lines of the .ass.
  - Strip ASS override tags ({...}) and convert \\N / \\n to line breaks.
  - EXCLUDE lines whose Style name (field 4) contains "romaji" or "karaoke"
    (case-insensitive) -- always decorative opening effects, never real dialogue.
  - Safety net: also exclude entries with a very short duration (< 150 ms),
    which are typically text-effect fragments, not dialogue.
  - Do NOT use an inclusion whitelist: real-dialogue style names vary a lot
    (Main, OP Normal2, Recuerdo, Secondary, Flashbacks, Narrator, OPLetreros,
    NDTText, ...), so only exclude what is clearly decorative/karaoke.
  - Sort resulting entries by start time and renumber.

Usage:
  # Preview a sample without touching any file:
  python regenerate_srt.py --subs ../subs --preview --episodes RO_1,AL_1,WA_1

  # Regenerate ALL episodes, backing up originals first:
  python regenerate_srt.py --subs ../subs --backup ../subs_originais_backup --all
"""

import argparse
import os
import re
import shutil
import sys

# Ensure we can print pt-BR / stray CJK glyphs regardless of the Windows console
# code page (cp1252 would otherwise crash on e.g. Japanese leftovers).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_ASS_TAG_PATTERN = re.compile(r"\{[^}]*\}")
_TIME_PATTERN = re.compile(r"(\d+):(\d{2}):(\d{2})\.(\d{2})")

# Substrings that mark a Style as purely decorative karaoke/romaji.
_DECORATIVE_STYLE_MARKERS = ("romaji", "karaoke")

# ASS drawing-mode tag (\p1..\p9). A Dialogue line in drawing mode carries vector
# shape coordinates (e.g. "m 848 508 l 84 ...") as its "text" -- never real
# subtitle text -- so such lines must be dropped entirely.
_DRAWING_TAG_PATTERN = re.compile(r"\\p[1-9]")

# CJK ranges (Hiragana, Katakana, CJK ideographs, half/fullwidth kana). These
# subs are Portuguese, so a line made up solely of CJK with no Latin letters is
# always original-language opening karaoke, regardless of its Style name.
_CJK_PATTERN = re.compile(r"[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ]")
_LATIN_PATTERN = re.compile(r"[A-Za-zÀ-ɏ]")

# Duration safety net: entries shorter than this are treated as text-effect
# fragments, not dialogue.
_MIN_DURATION_MS = 150


def _read_text(path):
    """Read a subtitle file trying a few common encodings."""
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(path, encoding=enc) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
    return None


def _ass_time_to_ms(t):
    """Convert ASS time (H:MM:SS.CC) to milliseconds. Returns None if unparsable."""
    m = _TIME_PATTERN.match(t.strip())
    if not m:
        return None
    h, mm, ss, cs = m.groups()
    return ((int(h) * 60 + int(mm)) * 60 + int(ss)) * 1000 + int(cs) * 10


def _ms_to_srt_time(ms):
    """Convert milliseconds to SRT timestamp HH:MM:SS,mmm."""
    if ms < 0:
        ms = 0
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class ConversionResult:
    """Outcome of converting one .ass file."""

    def __init__(
        self,
        entries,
        skipped_decorative,
        skipped_drawing,
        skipped_cjk,
        skipped_short,
        skipped_empty,
        skipped_duplicate=0,
    ):
        self.entries = entries  # list of (start_ms, end_ms, text)
        self.skipped_decorative = skipped_decorative
        self.skipped_drawing = skipped_drawing
        self.skipped_cjk = skipped_cjk
        self.skipped_short = skipped_short
        self.skipped_empty = skipped_empty
        self.skipped_duplicate = skipped_duplicate

    @property
    def skipped_karaoke_total(self):
        """All entries dropped as decorative opening/karaoke effects."""
        return self.skipped_decorative + self.skipped_drawing + self.skipped_cjk


def convert_ass(ass_content):
    """Parse ASS content and return a ConversionResult with clean dialogue entries."""
    events = False
    format_line = None
    entries = []
    skipped_decorative = skipped_drawing = skipped_cjk = 0
    skipped_short = skipped_empty = 0

    for raw in ass_content.split("\n"):
        line = raw.strip()
        if line == "[Events]":
            events = True
            continue
        if events and line.startswith("[") and line.endswith("]"):
            events = False
            continue
        if not events:
            continue
        if line.startswith("Format:"):
            format_line = [f.strip() for f in line[len("Format:"):].split(",")]
            continue
        if not line.startswith("Dialogue:") or not format_line:
            continue

        parts = line[len("Dialogue:"):].split(",", len(format_line) - 1)
        if len(parts) != len(format_line):
            continue
        entry = dict(zip(format_line, parts))

        style = entry.get("Style", "").strip().lower()
        if any(marker in style for marker in _DECORATIVE_STYLE_MARKERS):
            skipped_decorative += 1
            continue

        raw_text = entry.get("Text", "")
        # ASS drawing-mode lines carry vector shapes as "text", not dialogue.
        if _DRAWING_TAG_PATTERN.search(raw_text):
            skipped_drawing += 1
            continue

        start_ms = _ass_time_to_ms(entry.get("Start", ""))
        end_ms = _ass_time_to_ms(entry.get("End", ""))
        if start_ms is None or end_ms is None:
            continue

        text = _ASS_TAG_PATTERN.sub("", raw_text)
        text = text.replace("\\N", "\n").replace("\\n", "\n").strip()
        if not text:
            skipped_empty += 1
            continue

        # Pure original-language (CJK) line with no Latin letters -> opening karaoke.
        if _CJK_PATTERN.search(text) and not _LATIN_PATTERN.search(text):
            skipped_cjk += 1
            continue

        if end_ms - start_ms < _MIN_DURATION_MS:
            skipped_short += 1
            continue

        entries.append((start_ms, end_ms, text))

    entries.sort(key=lambda e: (e[0], e[1]))

    # Collapse exact-duplicate overlapping lines (same start, end AND text),
    # which ASS emits when a caption is layered for outline/glow effects.
    deduped = []
    seen = set()
    skipped_duplicate = 0
    for e in entries:
        if e in seen:
            skipped_duplicate += 1
            continue
        seen.add(e)
        deduped.append(e)

    return ConversionResult(
        deduped, skipped_decorative, skipped_drawing, skipped_cjk,
        skipped_short, skipped_empty, skipped_duplicate,
    )


def entries_to_srt(entries):
    """Render sorted entries to SRT text."""
    out = []
    for i, (start_ms, end_ms, text) in enumerate(entries, start=1):
        out.append(str(i))
        out.append(f"{_ms_to_srt_time(start_ms)} --> {_ms_to_srt_time(end_ms)}")
        out.append(text)
        out.append("")
    return "\n".join(out)


def _summarize(ep_id, result, old_srt_count):
    """Print a human-readable summary for one episode (preview mode)."""
    n = len(result.entries)
    print(f"\n=== {ep_id} ===")
    print(
        f"  entradas: {n}  (antes no .srt: {old_srt_count})   "
        f"excluidas -> estilo karaoke/romaji: {result.skipped_decorative}, "
        f"desenho(\\p): {result.skipped_drawing}, "
        f"cjk(karaoke jp): {result.skipped_cjk}, "
        f"curtas(<{_MIN_DURATION_MS}ms): {result.skipped_short}, "
        f"duplicados: {result.skipped_duplicate}, "
        f"vazias: {result.skipped_empty}"
    )
    if n == 0:
        print("  (!) NENHUMA entrada resultante")
        return
    first = result.entries[0]
    last = result.entries[-1]
    print(f"  primeira: {_ms_to_srt_time(first[0])}   ultima: {_ms_to_srt_time(last[0])}")
    print("  exemplos:")
    for start_ms, end_ms, text in result.entries[:4]:
        one_line = text.replace("\n", " / ")
        print(f"    [{_ms_to_srt_time(start_ms)}] {one_line}")


def _count_srt_entries(path):
    """Rough count of entries in an existing .srt (number of '-->' arrows)."""
    if not os.path.exists(path):
        return 0
    content = _read_text(path) or ""
    return content.count("-->")


def _index_arcs(subs_dir):
    """Map episode id -> directory holding it.

    subs/ is organised in one subfolder per arc (e.g. 33_Whole_Cake_Island/),
    so an episode id no longer resolves to subs_dir directly. Older flat
    layouts still work: the walk includes subs_dir itself.
    """
    index = {}
    for root, _dirs, files in os.walk(subs_dir):
        for f in files:
            if f.endswith(".ass"):
                index.setdefault(f[:-4], root)
    return index


def _episode_ids(index, requested):
    """Resolve the list of episode ids (base names) to process."""
    return requested if requested else sorted(index)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subs", required=True, help="Path to subs/ directory")
    parser.add_argument("--backup", help="Directory to back up original .srt files")
    parser.add_argument("--episodes", help="Comma-separated episode ids (e.g. RO_1,AL_1)")
    parser.add_argument("--all", action="store_true", help="Process every .ass in subs/")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Only print summaries; do not write or overwrite anything",
    )
    args = parser.parse_args()

    subs_dir = args.subs
    if not os.path.isdir(subs_dir):
        print(f"Erro: subs dir nao encontrado: {subs_dir}")
        sys.exit(1)

    requested = [e.strip() for e in args.episodes.split(",")] if args.episodes else None
    if not requested and not args.all:
        print("Erro: especifique --episodes ou --all")
        sys.exit(1)

    arc_index = _index_arcs(subs_dir)
    ep_ids = _episode_ids(arc_index, requested)

    if args.preview:
        for ep_id in ep_ids:
            ep_dir = arc_index.get(ep_id, subs_dir)
            ass_path = os.path.join(ep_dir, f"{ep_id}.ass")
            srt_path = os.path.join(ep_dir, f"{ep_id}.srt")
            if not os.path.exists(ass_path):
                print(f"\n=== {ep_id} ===\n  (!) .ass nao encontrado")
                continue
            content = _read_text(ass_path)
            if content is None:
                print(f"\n=== {ep_id} ===\n  (!) nao consegui ler .ass")
                continue
            result = convert_ass(content)
            _summarize(ep_id, result, _count_srt_entries(srt_path))
        print(f"\n[PREVIEW] {len(ep_ids)} episodios analisados. Nada foi escrito.")
        return

    # Real run: back up, then overwrite.
    if args.backup:
        os.makedirs(args.backup, exist_ok=True)

    ok = 0
    suspicious = []
    for ep_id in ep_ids:
        ep_dir = arc_index.get(ep_id, subs_dir)
        ass_path = os.path.join(ep_dir, f"{ep_id}.ass")
        srt_path = os.path.join(ep_dir, f"{ep_id}.srt")
        if not os.path.exists(ass_path):
            suspicious.append((ep_id, "sem .ass"))
            continue
        content = _read_text(ass_path)
        if content is None:
            suspicious.append((ep_id, "nao consegui ler .ass"))
            continue

        old_count = _count_srt_entries(srt_path)

        if args.backup and os.path.exists(srt_path):
            # espelhar a subpasta do arco dentro do backup
            arc = os.path.relpath(ep_dir, subs_dir)
            backup_dir = args.backup if arc == "." else os.path.join(args.backup, arc)
            os.makedirs(backup_dir, exist_ok=True)
            shutil.copy2(srt_path, os.path.join(backup_dir, f"{ep_id}.srt"))

        result = convert_ass(content)
        srt_text = entries_to_srt(result.entries)
        with open(srt_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(srt_text)

        n = len(result.entries)
        ok += 1
        # Flag suspicious outcomes for manual review.
        if n == 0:
            suspicious.append((ep_id, f"0 entradas (antes {old_count})"))
        elif n < 10:
            suspicious.append((ep_id, f"muito poucas entradas: {n} (antes {old_count})"))
        elif old_count and result.skipped_karaoke_total == 0 and abs(n - old_count) <= 1:
            suspicious.append(
                (ep_id, f"sem mudanca significativa: {n} vs {old_count}, 0 karaoke removido")
            )

    print(f"\nConcluido: {ok} episodios regenerados.")
    if suspicious:
        print(f"\nSuspeitos p/ revisao manual ({len(suspicious)}):")
        for ep_id, why in suspicious:
            print(f"  - {ep_id}: {why}")
    else:
        print("Nenhum episodio suspeito.")


if __name__ == "__main__":
    main()

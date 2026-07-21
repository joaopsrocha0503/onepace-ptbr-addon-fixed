#!/usr/bin/env python3
"""Shared module for subtitle conversion and arc mapping utilities."""

import re
import shutil
from pathlib import Path

# Pre-compiled regex for time conversion (ASS format: H:MM:SS.CC)
_TIME_PATTERN = re.compile(r"(\d+):(\d{2}):(\d{2})\.(\d{2})")

# Pre-compiled regex for ASS tag removal
_ASS_TAG_PATTERN = re.compile(r"\{[^}]*\}")

# Complete mapping: Arc display name -> Stremio episode ID prefix
ARC_PREFIX: dict[str, str] = {
    "Romance Dawn": "RO",
    "Orange Town": "OR",
    "Syrup Village": "SY",
    "Gaimon": "GA",
    "Baratie": "BA",
    "Arlong Park": "AR",
    "Buggy's Crew": "BUGGYS_CREW",
    "Loguetown": "LO",
    "Reverse Mountain": "RM",
    "Whisky Peak": "WH",
    "Koby-Meppo": "COVER_KOBYMEPPO",
    "Little Garden": "LI",
    "Drum Island": "DI",
    "Alabasta": "AL",
    "Jaya": "JA",
    "Skypiea": "SK",
    "Long Ring Long Land": "LR",
    "Water Seven": "WS",
    "Enies Lobby": "EN",
    "Post-Enies Lobby": "PEN",
    "Thriller Bark": "TB",
    "Sabaody": "SAB",
    "Amazon Lily": "AM",
    "Impel Down": "IM",
    "Straw Hats Adventures": "COVER_SHSS",
    "Marineford": "MA",
    "Post-War": "PW",
    "Return to Sabaody": "RTS",
    "Fishman Island": "FI",
    "Punk Hazard": "PH",
    "Dressrosa": "DR",
    "Zou": "ZO",
    "Whole Cake Island": "WC",
    "Reverie": "REV",
    "Wano": "WA",
    "Egghead": "EH",
}

# "Wapol's Omnivorous Hurrah" nao tem pasta no GDrive (logo, nao entra em
# ARC_PREFIX), mas os ficheiros COVER_WAPOL_* existem e precisam de arco.
# Ordem cronologica: a seguir a Whole Cake Island (ver PROJECT_GOAL.md).
_EXTRA_ARCS: dict[str, str] = {"COVER_WAPOL": "Wapol's Omnivorous Hurrah"}

_FILENAME_PREFIX = re.compile(r"^(.*)_\d+\.[A-Za-z]+$")


def _build_arc_dirs() -> dict[str, str]:
    """prefixo do episodio -> subpasta numerada de subs/ (ex.: 14_Alabasta)."""
    ordered: list[tuple[str, str]] = []
    for name, prefix in ARC_PREFIX.items():
        ordered.append((prefix, name))
        if prefix == "WC":
            ordered.append(("COVER_WAPOL", _EXTRA_ARCS["COVER_WAPOL"]))
    return {
        prefix: f"{i:02d}_" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
        for i, (prefix, name) in enumerate(ordered, 1)
    }


# Stremio episode ID prefix -> subpasta de arco dentro de subs/
ARC_DIR: dict[str, str] = _build_arc_dirs()


def arc_subdir(episode_id: str) -> str | None:
    """Subpasta de arco para um id de episodio ou nome de ficheiro.

    Aceita "WC_15" ou "WC_15.srt" e devolve "33_Whole_Cake_Island".
    Devolve None se o prefixo nao corresponder a nenhum arco conhecido.
    """
    match = _FILENAME_PREFIX.match(episode_id)
    stem = match.group(1) if match else episode_id.rsplit("_", 1)[0]
    return ARC_DIR.get(stem)


# Filesystem directory name -> Stremio episode ID prefix
ARC_TO_PREFIX: dict[str, str] = {
    "romancedawn": "RO",
    "orangetown": "OR",
    "syrupvillage": "SY",
    "gaimon": "GA",
    "baratie": "BA",
    "arlongpark": "AR",
    "loguetown": "LO",
    "reversemountain": "RM",
    "whiskypeak": "WH",
    "littlegarden": "LI",
    "drumisland": "DI",
    "alabasta": "AL",
    "jaya": "JA",
    "skypiea": "SK",
    "longringlongland": "LR",
    "waterseven": "WS",
    "enieslobby": "EN",
    "thrillerbark": "TB",
    "sabaody": "SAB",
    "amazonlily": "AM",
    "impeldown": "IM",
    "marineford": "MA",
    "fishmanisland": "FI",
    "punkhazard": "PH",
    "dressrosa": "DR",
    "zou": "ZO",
    "wholecakeisland": "WC",
    "reverie": "REV",
    "wano": "WA",
    "egghead": "EH",
}

# Final Subs arc name (with spaces) -> Stremio episode ID prefix
FINAL_SUBS_ARC_MAP: dict[str, str] = {
    "Romance Dawn": "RO",
    "Orange Town": "OR",
    "Syrup Village": "SY",
    "Gaimon": "GA",
    "Baratie": "BA",
    "Arlong Park": "AR",
    "Loguetown": "LO",
    "Reverse Mountain": "RM",
    "Whisky Peak": "WH",
    "Whiskey Peak": "WH",
    "Little Garden": "LI",
    "Drum Island": "DI",
    "Alabasta": "AL",
    "Jaya": "JA",
    "Skypiea": "SK",
    "Long Ring Long Land": "LR",
    "Water Seven": "WS",
    "Enies Lobby": "EN",
    "Thriller Bark": "TB",
    "Sabaody": "SAB",
    "Amazon Lily": "AM",
    "Impel Down": "IM",
    "Marineford": "MA",
    "Fishman Island": "FI",
    "Punk Hazard": "PH",
    "Dressrosa": "DR",
    "Zou": "ZO",
    "Whole Cake Island": "WC",
    "Reverie": "REV",
    "Wano": "WA",
    "Egghead": "EH",
}

# Styles to skip during ASS -> SRT conversion
_SKIP_STYLES: list[str] = [
    "sign",
    "song",
    "op ",
    "ed ",
    "karaoke",
    "title",
    "chapter",
    "credit",
    "eyecatch",
    "next ep",
    "preview",
]

# Episode number extraction patterns (most specific first)
_EPISODE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:ep(?:isode)?[\s._-]*)(\d+)", re.IGNORECASE),
    re.compile(
        r"[\s._-](\d{1,3})[\s._-]*(?:ptbr|pt-br|pt|portugues)?$", re.IGNORECASE
    ),
    re.compile(r"[\s._-](\d{1,3})[\s._-]", re.IGNORECASE),
    re.compile(r"(\d{1,3})[\s._-]*(?:ptbr|pt-br|pt|portugues)", re.IGNORECASE),
    re.compile(r"^(\d{1,3})$", re.IGNORECASE),
    re.compile(r"(\d{1,3})", re.IGNORECASE),
]


def convert_time(t: str) -> str:
    """Convert ASS time format (H:MM:SS.CC) to SRT format (HH:MM:SS,CC0)."""
    match = _TIME_PATTERN.match(t)
    if match:
        h, m, s, cs = match.groups()
        return f"{int(h):02d}:{m}:{s},{cs}0"
    return t


def ass_to_srt(ass_content: str) -> str:
    """Convert ASS subtitle content to SRT format, stripping formatting tags."""
    lines = ass_content.split("\n")
    events_section = False
    format_line: list[str] | None = None
    dialogues: list[dict[str, str]] = []

    for line in lines:
        line = line.strip()
        if line == "[Events]":
            events_section = True
            continue
        if line.startswith("[") and line.endswith("]") and events_section:
            events_section = False
            continue
        if events_section and line.startswith("Format:"):
            format_line = [f.strip() for f in line[7:].split(",")]
            continue
        if events_section and line.startswith("Dialogue:"):
            if format_line:
                parts = line[10:].split(",", len(format_line) - 1)
                if len(parts) == len(format_line):
                    entry = dict(zip(format_line, parts))
                    style = entry.get("Style", "").lower()
                    if any(s in style for s in _SKIP_STYLES):
                        continue
                    dialogues.append(entry)

    srt_lines: list[str] = []
    counter = 1
    for d in dialogues:
        start = d.get("Start", "0:00:00.00")
        end = d.get("End", "0:00:00.00")
        text = d.get("Text", "")

        text = _ASS_TAG_PATTERN.sub("", text)
        text = text.replace("\\N", "\n").replace("\\n", "\n")
        text = text.strip()

        if not text:
            continue

        srt_lines.append(str(counter))
        srt_lines.append(f"{convert_time(start)} --> {convert_time(end)}")
        srt_lines.append(text)
        srt_lines.append("")
        counter += 1

    return "\n".join(srt_lines)


def extract_episode_number(filename: str) -> int | None:
    """Extract episode number from a subtitle filename. Returns None if not found."""
    name = Path(filename).stem

    for pattern in _EPISODE_PATTERNS:
        match = pattern.search(name)
        if match:
            num = int(match.group(1))
            if 1 <= num <= 999:
                return num

    return None


def convert_file_to_srt(input_path: str, output_path: str) -> bool:
    """Convert an ASS/SSA file to SRT. Copies directly if already SRT. Returns True on success."""
    ext = Path(input_path).suffix.lower()

    if ext == ".srt":
        shutil.copy2(input_path, output_path)
        return True

    if ext not in (".ass", ".ssa"):
        print(f"    Formato nao suportado: {ext}")
        return False

    content: str | None = None
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            with open(input_path, encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if not content:
        print(f"    Nao consegui ler {input_path}")
        return False

    try:
        srt = ass_to_srt(content)
        if srt.strip():
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt)
            return True
        print(f"    SRT vazio para {input_path}")
        return False
    except Exception as e:
        print(f"    Erro convertendo {input_path}: {e}")
        return False

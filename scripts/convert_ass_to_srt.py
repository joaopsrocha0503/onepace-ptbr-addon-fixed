#!/usr/bin/env python3
"""
Convert pt-BR ASS subtitle files from the one-pace-public-subtitles repo to SRT,
mapping each file to the Stremio episode ID.

Usage:
  python convert_ass_to_srt.py <repo-path> <output-dir>

Example:
  python convert_ass_to_srt.py ../one-pace-public-subtitles ./subs
"""

import argparse
import json
import os
import re
import sys

from subtitle_converter import (
    ARC_TO_PREFIX,
    FINAL_SUBS_ARC_MAP,
    arc_subdir,
    ass_to_srt,
)


def find_and_convert(repo_path: str, output_dir: str) -> dict[str, str]:
    """Find all ptbr.ass and Portugues.ass files and convert them to SRT."""
    os.makedirs(output_dir, exist_ok=True)
    converted: dict[str, str] = {}

    # Source 1: Individual files (ptbr.ass) in episode directories
    main_dir = os.path.join(repo_path, "main")
    for root, _dirs, files in os.walk(main_dir):
        for f in files:
            if f.endswith("ptbr.ass") and "Other" not in root:
                match = re.match(r"(\w+)\s+(\d+)\s+ptbr\.ass", f)
                if match:
                    arc_name = match.group(1).lower()
                    ep_num = int(match.group(2))
                    prefix = ARC_TO_PREFIX.get(arc_name)
                    if prefix:
                        episode_id = f"{prefix}_{ep_num}"
                        if episode_id not in converted:
                            converted[episode_id] = os.path.join(root, f)

    # Source 2: Final Subs (Portugues.ass) - overrides source 1
    final_subs = os.path.join(repo_path, "main", "Release", "Final Subs")
    if os.path.exists(final_subs):
        for f in os.listdir(final_subs):
            if "Portugues" in f and f.endswith(".ass"):
                match = re.search(r"]\s+(.+?)\s+(\d+)\s+\[", f)
                if match:
                    arc_name = match.group(1)
                    ep_num = int(match.group(2))
                    prefix = FINAL_SUBS_ARC_MAP.get(arc_name)
                    if prefix:
                        episode_id = f"{prefix}_{ep_num}"
                        converted[episode_id] = os.path.join(final_subs, f)

    mapping: dict[str, str] = {}
    for episode_id, ass_path in sorted(converted.items()):
        try:
            ass_content = None
            for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
                try:
                    with open(ass_path, encoding=enc) as fh:
                        ass_content = fh.read()
                    break
                except UnicodeDecodeError:
                    continue
            if not ass_content:
                print(f"  ERRO {episode_id}: nao consegui ler {ass_path}")
                continue
            srt_content = ass_to_srt(ass_content)
            # subs/ esta organizada por arco; o mapping guarda o caminho relativo
            subdir = arc_subdir(episode_id)
            srt_filename = f"{subdir}/{episode_id}.srt" if subdir else f"{episode_id}.srt"
            srt_path = os.path.join(output_dir, srt_filename)
            os.makedirs(os.path.dirname(srt_path), exist_ok=True)
            with open(srt_path, "w", encoding="utf-8") as fh:
                fh.write(srt_content)
            mapping[episode_id] = srt_filename
            print(f"  {episode_id} -> {srt_filename} (de {os.path.basename(ass_path)})")
        except Exception as e:
            print(f"  ERRO {episode_id}: {e}")

    mapping_path = os.path.join(output_dir, "mapping.json")
    with open(mapping_path, "w") as fh:
        json.dump(mapping, fh, indent=2)
    print(f"\nMapeamento salvo em {mapping_path}")
    print(f"Total: {len(mapping)} episodios convertidos")

    return mapping


def main() -> None:
    """Entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Convert pt-BR ASS subtitles from one-pace-public-subtitles repo to SRT"
    )
    parser.add_argument("repo_path", help="Path to the one-pace-public-subtitles repo")
    parser.add_argument("output_dir", help="Output directory for SRT files")
    args = parser.parse_args()

    if not os.path.isdir(args.repo_path):
        print(f"Erro: caminho do repo nao encontrado: {args.repo_path}")
        sys.exit(1)

    print("Convertendo legendas ASS -> SRT...\n")
    find_and_convert(args.repo_path, args.output_dir)


if __name__ == "__main__":
    main()

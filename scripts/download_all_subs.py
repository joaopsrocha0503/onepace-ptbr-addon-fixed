#!/usr/bin/env python3
"""
One Pace PT-BR -- Download and automatic subtitle conversion.

This script:
1. Downloads all pt-BR subtitles from Google Drive folders
   listed on onepaceptbr.github.io
2. Converts ASS/SSA -> SRT
3. Maps each file to the Stremio episode ID
4. Generates the final mapping.json for the addon

Requirements:
  pip install gdown

Usage:
  python3 download_all_subs.py
  python3 download_all_subs.py --output ./subs
  python3 download_all_subs.py --dry-run
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from subtitle_converter import (
    ARC_PREFIX,
    arc_subdir,
    convert_file_to_srt,
    extract_episode_number,
)


def _srt_rel_path(episode_id: str) -> str:
    """Caminho relativo do .srt dentro de subs/, ja com a subpasta do arco."""
    subdir = arc_subdir(episode_id)
    return f"{subdir}/{episode_id}.srt" if subdir else f"{episode_id}.srt"

SUBTITLE_EXTENSIONS: set[str] = {".ass", ".ssa", ".srt"}

# Google Drive folder IDs extracted from onepaceptbr.github.io
GDRIVE_FOLDERS: list[tuple[str, str]] = [
    ("Buggy's Crew", "1N7SX80QdYA3RmiB9a0Gv0CcVO5U-W42T"),
    ("Loguetown", "1kGtlrg_yDQhmk90hzgKJkEJyHG8dE0Bm"),
    ("Reverse Mountain", "19Y27qgR7sQM7xcaeQVT5p_utRZhEMwv-"),
    ("Whisky Peak", "1-0aNZMiCfiabU7lItI9hnUw9tDDvGNUi"),
    ("Koby-Meppo", "1-1HHj1J1GyOJB-0s0tYFulXZ3Edih2dA"),
    ("Little Garden", "1-38c5xnM21BsE4gPF-AUOBKo5sRje1gA"),
    ("Drum Island", "1-394JF2Js6SLOfA5_xzZF8rMUbXuxuew"),
    ("Alabasta", "1-CHXA4WOhu-NcFXo3zlb8IHZRcLjmKa9"),
    ("Jaya", "1-DbtZkM4ZQryu6ddZ_jSg-I0mkA0ZmJ9"),
    ("Skypiea", "1-PQqH_ck_vLSrvvRlcS94t7sTEGDjecW"),
    ("Long Ring Long Land", "1-ReUSBrY2JuIkVoH900AHZvimo88INMs"),
    ("Water Seven", "1-RyaFfPEpcTMXoob8vD8LMTTHHjV0oFX"),
    ("Enies Lobby", "1-Y0wp4cby90m3zFLHDsZbUYEKaIQiksG"),
    ("Post-Enies Lobby", "1-ZntQeVbCs7XY8Abe3g-yfvYSV_TP5vp"),
    ("Thriller Bark", "1-boleMHeog-R1t81Kf-ApXH629m7j2xR"),
    ("Sabaody", "1-elhWG655zJKUEpTdh25LsbnlQ-Rx7NG"),
    ("Amazon Lily", "1-i8blh_fRWjag4B_gySYmK0aABIES1HG"),
    ("Impel Down", "1-ktbonZpkWu3MDnHCUaaMQp45CgvWO4t"),
    ("Straw Hats Adventures", "1019fNv55FqIAG7GU4rsxJM_62HVKr9S4"),
    ("Marineford", "105LxQOh3l58DS_MgB_i5onaRNcQheNrY"),
    ("Post-War", "10928v4_qkWERla3eHFsq7c3wIk43-XGj"),
    ("Return to Sabaody", "10DDgiuLpGFH_nHTCYJmoFWKbOXPvwVhN"),
    ("Fishman Island", "10Rha6Tz0VguhV_rOvJ8MjGrap6zsy7tj"),
    ("Punk Hazard", "10T3VDRRZv6PtXqi9CIWmOyJjWoEOfRbT"),
    ("Dressrosa", "10TqoScXsXwEdKKsWAPTVoVFRwF1ry_qD"),
    ("Zou", "10Wh5vds63c9jyehohgb5nsnG0DLOW6cc"),
    ("Whole Cake Island", "10aU7oDKch2exbCA_TAAWHi48V_BR2h35"),
    ("Reverie", "10h8tbsKhH_SDCzpq1E2KMLKHKU1DvzFC"),
    ("Wano", "10rAsSYTRuEea234r2q5I_z7nA1ZpDz8_"),
    ("Egghead", "10xFDV_4BjggDKJuEixYvR6i3Kk1_xnE6"),
]


def download_gdrive_folder(folder_id: str, output_dir: str) -> bool:
    """Download a Google Drive folder using gdown. Returns True on success."""
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    os.makedirs(output_dir, exist_ok=True)

    try:
        result = subprocess.run(
            ["gdown", "--folder", "--remaining-ok", url, "-O", output_dir],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            result = subprocess.run(
                ["gdown", "--folder", url, "-O", output_dir, "--fuzzy"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.returncode == 0
        return True
    except FileNotFoundError:
        print("  gdown nao encontrado! Instale com: pip install gdown")
        return False
    except subprocess.TimeoutExpired:
        print(f"  Timeout ao baixar pasta {folder_id}")
        return False
    except Exception as e:
        print(f"  Erro: {e}")
        return False


def collect_subtitle_files(directory: str) -> list[str]:
    """Collect all subtitle files (.ass, .ssa, .srt) recursively, without duplicates."""
    sub_files: list[str] = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if Path(f).suffix.lower() in SUBTITLE_EXTENSIONS:
                sub_files.append(os.path.join(root, f))
    return sub_files


def main() -> None:
    """Main pipeline: download, convert, and map subtitles."""
    parser = argparse.ArgumentParser(
        description="Download and convert pt-BR subtitles from One Pace for the Stremio addon"
    )
    parser.add_argument(
        "--output", "-o", default="./subs", help="Output directory for SRT files (default: ./subs)"
    )
    parser.add_argument(
        "--download-dir",
        "-d",
        default="./downloads",
        help="Temporary directory for GDrive downloads (default: ./downloads)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only show what would be done, without downloading"
    )
    parser.add_argument(
        "--skip-download", action="store_true", help="Skip download and only convert existing files"
    )
    parser.add_argument(
        "--arcs", nargs="*", help="Download only specific arcs (e.g. --arcs Alabasta Wano)"
    )
    args = parser.parse_args()

    output_dir: str = args.output
    download_dir: str = args.download_dir
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(download_dir, exist_ok=True)

    print("=" * 60)
    print("  One Pace PT-BR -- Download & Conversao de Legendas")
    print("=" * 60)
    print(f"  Download dir: {download_dir}")
    print(f"  Output dir:   {output_dir}")
    print(f"  Arcos:        {len(GDRIVE_FOLDERS)} pastas mapeadas")
    print("=" * 60)

    if args.dry_run:
        print("\nDRY RUN -- nada sera baixado\n")
        for arc_name, folder_id in GDRIVE_FOLDERS:
            prefix = ARC_PREFIX.get(arc_name, "???")
            print(f"  {arc_name:25s} -> {prefix}_* | GDrive: {folder_id}")
        print(f"\n  Total: {len(GDRIVE_FOLDERS)} pastas")
        return

    # Phase 1: Download
    if not args.skip_download:
        print("\nFASE 1: Baixando legendas do Google Drive...\n")

        for arc_name, folder_id in GDRIVE_FOLDERS:
            if args.arcs and arc_name not in args.arcs:
                continue

            arc_dir = os.path.join(download_dir, arc_name.replace(" ", "_"))
            print(f"  {arc_name}...")

            if os.path.exists(arc_dir) and os.listdir(arc_dir):
                file_count = sum(1 for _ in Path(arc_dir).rglob("*") if _.is_file())
                print(f"     Ja existe ({file_count} arquivos), pulando download")
                continue

            success = download_gdrive_folder(folder_id, arc_dir)
            if success:
                file_count = sum(1 for _ in Path(arc_dir).rglob("*") if _.is_file())
                print(f"     {file_count} arquivos baixados")
            else:
                print("     Falha no download")
    else:
        print("\nPulando download (--skip-download)\n")

    # Phase 2: Conversion
    print("\nFASE 2: Convertendo e mapeando legendas...\n")

    mapping: dict[str, str] = {}

    mapping_path = os.path.join(output_dir, "mapping.json")
    if os.path.exists(mapping_path):
        with open(mapping_path) as f:
            mapping = json.load(f)
        print(f"  Mapping existente carregado: {len(mapping)} episodios\n")

    for arc_name, _folder_id in GDRIVE_FOLDERS:
        if args.arcs and arc_name not in args.arcs:
            continue

        prefix = ARC_PREFIX.get(arc_name)
        if not prefix:
            print(f"  Sem prefixo para '{arc_name}', pulando")
            continue

        arc_dir = os.path.join(download_dir, arc_name.replace(" ", "_"))
        if not os.path.exists(arc_dir):
            continue

        sub_files = collect_subtitle_files(arc_dir)

        if not sub_files:
            print(f"  {arc_name}: nenhum arquivo de legenda encontrado")
            continue

        print(f"  {arc_name} ({prefix}_*): {len(sub_files)} arquivos")

        if len(sub_files) == 1:
            ep_num = extract_episode_number(sub_files[0])
            if ep_num is None:
                ep_num = 1
            episode_id = f"{prefix}_{ep_num}"
            rel = _srt_rel_path(episode_id)
            srt_path = os.path.join(output_dir, rel)
            os.makedirs(os.path.dirname(srt_path), exist_ok=True)

            if convert_file_to_srt(sub_files[0], srt_path):
                mapping[episode_id] = rel
                print(f"     {episode_id} <- {Path(sub_files[0]).name}")
            continue

        for sub_file in sorted(sub_files):
            ep_num = extract_episode_number(sub_file)
            if ep_num is None:
                print(f"     Nao consegui extrair episodio de: {Path(sub_file).name}")
                continue

            episode_id = f"{prefix}_{ep_num}"
            rel = _srt_rel_path(episode_id)
            srt_path = os.path.join(output_dir, rel)
            os.makedirs(os.path.dirname(srt_path), exist_ok=True)

            if convert_file_to_srt(sub_file, srt_path):
                mapping[episode_id] = rel
                print(f"     {episode_id} <- {Path(sub_file).name}")

    # Phase 3: Save mapping
    print("\nFASE 3: Salvando mapping.json...\n")

    def sort_key(episode_id: str) -> tuple[str, int]:
        parts = episode_id.rsplit("_", 1)
        prefix = parts[0]
        num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        return (prefix, num)

    sorted_mapping = dict(sorted(mapping.items(), key=lambda x: sort_key(x[0])))

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(sorted_mapping, f, indent=2, ensure_ascii=False)

    print(f"  Total: {len(sorted_mapping)} episodios mapeados")
    print(f"  Salvo em: {mapping_path}")

    print(f"\n{'=' * 60}")
    print("  RESUMO POR ARCO")
    print(f"{'=' * 60}")
    arc_counts: dict[str, int] = {}
    for ep_id in sorted_mapping:
        ep_prefix = ep_id.rsplit("_", 1)[0]
        arc_counts[ep_prefix] = arc_counts.get(ep_prefix, 0) + 1

    prefix_to_name: dict[str, str] = {v: k for k, v in ARC_PREFIX.items()}
    arc_prefix_values = list(ARC_PREFIX.values())
    for prefix, count in sorted(
        arc_counts.items(),
        key=lambda x: arc_prefix_values.index(x[0]) if x[0] in arc_prefix_values else 999,
    ):
        name = prefix_to_name.get(prefix, prefix)
        print(f"  {name:25s} ({prefix:15s}): {count:3d} eps")

    print(f"\n  {'TOTAL':25s} {'':15s}: {len(sorted_mapping):3d} eps")
    print(f"{'=' * 60}")
    print("\nPronto! Agora e so rodar o addon:")
    print("   npm start\n")


if __name__ == "__main__":
    main()

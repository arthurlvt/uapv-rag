"""
rag_count_sources.py
--------------------
Sanity check : compte tous les fichiers sources (.pdf, .tex) dans le dossier
des ressources, regroupe par UE et par doc_type, et compare avec un fichier
de chunks (par défaut chunks_all.json) pour vérifier que tous les fichiers
ont bien été indexés.

Usage :
    # Comptage simple
    python rag_count_sources.py --input ./ressources

    # Comparaison avec un JSON de chunks
    python rag_count_sources.py --input ./ressources --chunks ./chunks_all.json

    # Restreindre les extensions
    python rag_count_sources.py --input ./ressources --extensions .pdf

L'objectif : repérer les fichiers oubliés à l'extraction (extensions
non supportées, erreurs silencieuses, doublons, etc.).
"""
import os
import json
import argparse
from collections import defaultdict, Counter

from rag_extract import detect_doc_type


def count_files(input_dir: str, extensions: set[str]) -> tuple[list[dict], dict]:
    """
    Parcourt récursivement `input_dir` et liste les fichiers
    correspondant aux extensions données.

    Retourne (liste_des_fichiers, stats) où chaque fichier est un dict
    {ue, doc_type, source, path}, et stats agrège par UE / type.
    """
    files_info = []
    stats = defaultdict(lambda: {
        "fichiers": 0,
        "par_type": Counter(),
        "par_ext": Counter(),
    })

    for root, _, files in os.walk(input_dir):
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in extensions:
                continue

            filepath = os.path.join(root, filename)

            # On considère que le 1er sous-dossier de input_dir est l'UE
            rel = os.path.relpath(filepath, input_dir)
            parts = rel.replace("\\", "/").split("/")
            ue = parts[0] if len(parts) >= 2 else "Inconnu"

            doc_type = detect_doc_type(filepath)

            files_info.append({
                "ue":       ue,
                "doc_type": doc_type,
                "source":   filename,
                "path":     filepath,
                "ext":      ext,
            })

            stats[ue]["fichiers"] += 1
            stats[ue]["par_type"][doc_type] += 1
            stats[ue]["par_ext"][ext] += 1

    return files_info, dict(stats)


def load_chunks_stats(chunks_path: str) -> dict:
    """Agrège les chunks par (ue, source) -> nombre de chunks."""
    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)

    by_source = defaultdict(int)
    for c in chunks:
        by_source[(c["ue"], c["source"])] += 1

    return dict(by_source)


def print_summary(stats: dict, total_files: int) -> None:
    print("\n── Fichiers trouvés sur disque ─────────")
    for ue in sorted(stats.keys()):
        s = stats[ue]
        types_str = ", ".join(f"{t}:{n}" for t, n in s["par_type"].most_common())
        exts_str  = ", ".join(f"{e}:{n}" for e, n in s["par_ext"].most_common())
        print(f"  {ue:<30} {s['fichiers']:>4} fichier(s)  "
              f"[{types_str}]  ({exts_str})")
    print(f"  {'TOTAL':<30} {total_files:>4} fichier(s)")
    print("────────────────────────────────────────")


def compare_with_chunks(files_info: list[dict], chunks_stats: dict) -> None:
    """
    Compare les fichiers sur disque avec les fichiers indexés dans les chunks.
    Signale ceux qui sont sur disque mais absents des chunks (fichiers oubliés)
    ET ceux dans les chunks mais introuvables sur disque (orphelins).
    """
    on_disk = {(f["ue"], f["source"]) for f in files_info}
    in_chunks = set(chunks_stats.keys())

    missing  = on_disk - in_chunks   # sur disque mais pas dans les chunks
    orphans  = in_chunks - on_disk   # dans les chunks mais introuvables
    indexed  = on_disk & in_chunks

    print("\n── Comparaison disque vs chunks ────────")
    print(f"  Fichiers sur disque        : {len(on_disk)}")
    print(f"  Fichiers dans les chunks   : {len(in_chunks)}")
    print(f"  Indexés (intersection)     : {len(indexed)}")
    print(f"  Manquants (non indexés)    : {len(missing)}")
    print(f"  Orphelins (chunks sans src): {len(orphans)}")

    if missing:
        print("\n  ⚠ Fichiers présents sur disque mais NON indexés :")
        for ue, src in sorted(missing):
            print(f"    [{ue}] {src}")

    if orphans:
        print("\n  ⚠ Fichiers indexés mais introuvables sur disque :")
        for ue, src in sorted(orphans):
            print(f"    [{ue}] {src} ({chunks_stats[(ue, src)]} chunks)")

    if indexed:
        # Stats : nombre de chunks moyens par fichier
        total_chunks = sum(chunks_stats[k] for k in indexed)
        avg = total_chunks / len(indexed)
        max_key = max(indexed, key=lambda k: chunks_stats[k])
        min_key = min(indexed, key=lambda k: chunks_stats[k])
        print(f"\n  Chunks par fichier (indexés)~:")
        print(f"    moyenne : {avg:.1f}")
        print(f"    max     : {chunks_stats[max_key]}  → {max_key[0]}/{max_key[1]}")
        print(f"    min     : {chunks_stats[min_key]}  → {min_key[0]}/{min_key[1]}")

    print("────────────────────────────────────────\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compte les fichiers sources et compare avec un JSON de chunks"
    )
    parser.add_argument("--input", required=True,
        help="Dossier racine des ressources (ex: ./ressources)")
    parser.add_argument("--chunks", default=None,
        help="Optionnel : JSON de chunks pour comparer (ex: ./chunks_all.json)")
    parser.add_argument("--extensions", nargs="+", default=[".pdf", ".tex"],
        help="Extensions à compter (défaut: .pdf .tex)")
    args = parser.parse_args()

    if not os.path.isdir(args.input):
        raise SystemExit(f"Erreur : '{args.input}' n'est pas un dossier")

    extensions = {e.lower() if e.startswith(".") else "." + e.lower()
                  for e in args.extensions}

    print(f"\nDossier scanné : {args.input}")
    print(f"Extensions     : {sorted(extensions)}")

    files_info, stats = count_files(args.input, extensions)
    print_summary(stats, total_files=len(files_info))

    if args.chunks:
        if not os.path.isfile(args.chunks):
            print(f"\n⚠ Fichier de chunks introuvable : {args.chunks}")
        else:
            chunks_stats = load_chunks_stats(args.chunks)
            compare_with_chunks(files_info, chunks_stats)
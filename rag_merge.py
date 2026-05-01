"""
rag_merge.py
------------
Étape 1.5 : fusion de plusieurs JSON de chunks par UE en un JSON global.

Cas d'usage typique :
- Tu as extrait chaque UE séparément avec `rag_extract_ue.py`, ce qui a
  produit `chunks_Mathematiques.json`, `chunks_FondementInformatique.json`,
  `chunks_Programmation.json`, etc.
- Tu veux maintenant un unique `chunks.json` à indexer dans la suite du
  pipeline RAG (embeddings, stockage vectoriel...).

Le merge :
- concatène tous les chunks
- vérifie la cohérence des champs (ue, doc_type, source, chunk_id, text)
- détecte et signale les doublons (même UE + source + chunk_id)
- affiche un résumé global

Usage :
    # Fusionne tous les chunks_*.json du dossier courant
    python rag_merge.py --output chunks.json

    # Liste explicite de fichiers à fusionner
    python rag_merge.py --inputs chunks_Math.json chunks_Info.json \\
        --output chunks.json

    # Ne garder qu'une UE
    python rag_merge.py --filter-ue Mathematiques --output chunks_Math_only.json
"""
import os
import json
import glob
import argparse
from collections import defaultdict


REQUIRED_FIELDS = {"ue", "doc_type", "source", "chunk_id", "text"}


def load_chunks(path: str) -> list[dict]:
    """Charge un fichier JSON de chunks et vérifie sa structure."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"{path} : doit contenir une liste de chunks")

    for i, c in enumerate(data):
        missing = REQUIRED_FIELDS - set(c.keys())
        if missing:
            raise ValueError(
                f"{path} : chunk #{i} il manque les champs {missing}"
            )

    return data


def discover_inputs(pattern: str = "chunks_*.json",
                    exclude: set[str] | None = None) -> list[str]:
    """Trouve tous les fichiers correspondant au pattern, hors `exclude`."""
    exclude = exclude or set()
    files = sorted(glob.glob(pattern))
    files = [f for f in files if os.path.basename(f) not in exclude]
    return files


def merge(
    inputs: list[str],
    output: str,
    filter_ue: str | None = None,
    deduplicate: bool = True,
) -> None:
    """
    Fusionne tous les fichiers `inputs` en un seul JSON `output`.

    - Si `filter_ue` est défini, ne garde que les chunks de cette UE.
    - Si `deduplicate` est True, élimine les doublons selon (ue, source, chunk_id).
    """
    all_chunks: list[dict] = []
    per_file_stats = []
    seen_keys: set[tuple] = set()
    duplicates = 0

    for path in inputs:
        try:
            chunks = load_chunks(path)
        except Exception as e:
            print(f"  ! Erreur sur {path} : {e}")
            continue

        kept = 0
        for c in chunks:
            if filter_ue and c["ue"] != filter_ue:
                continue
            key = (c["ue"], c["source"], c["chunk_id"])
            if deduplicate and key in seen_keys:
                duplicates += 1
                continue
            seen_keys.add(key)
            all_chunks.append(c)
            kept += 1

        per_file_stats.append((path, len(chunks), kept))
        print(f"  + {path:<50} {len(chunks):>5} chunks  (gardés {kept})")

    # Écriture
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # Résumé
    by_ue = defaultdict(lambda: {"chunks": 0, "fichiers": set()})
    by_type = defaultdict(int)
    for c in all_chunks:
        by_ue[c["ue"]]["chunks"] += 1
        by_ue[c["ue"]]["fichiers"].add(c["source"])
        by_type[c["doc_type"]] += 1

    print("\n── Résumé global ───────────────────────")
    for ue, s in sorted(by_ue.items()):
        print(f"  {ue:<30} {len(s['fichiers']):>3} fichier(s)  "
              f"{s['chunks']:>5} chunks")
    print(f"  {'TOTAL':<30} "
          f"{sum(len(s['fichiers']) for s in by_ue.values()):>3} fichier(s)  "
          f"{len(all_chunks):>5} chunks")

    print("\n  Par type de document :")
    for t, n in sorted(by_type.items()):
        print(f"    {t:<12} {n:>5} chunks")

    if duplicates:
        print(f"\n  ⚠ {duplicates} doublon(s) ignoré(s)")
    print("────────────────────────────────────────\n")

    print(f"Terminé — {len(all_chunks)} chunks fusionnés dans : {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fusion de plusieurs JSON de chunks RAG en un seul"
    )
    parser.add_argument("--inputs", nargs="*", default=None,
        help="Liste explicite de fichiers à fusionner. "
             "Par défaut : auto-découverte de chunks_*.json")
    parser.add_argument("--output", default="./chunks.json",
        help="Fichier JSON de sortie (défaut: ./chunks.json)")
    parser.add_argument("--filter-ue", default=None,
        help="Ne conserver que les chunks de cette UE")
    parser.add_argument("--no-dedup", action="store_true",
        help="Ne pas dédupliquer (par défaut, on déduplique)")
    parser.add_argument("--pattern", default="chunks_*.json",
        help="Pattern de découverte automatique (défaut: chunks_*.json)")
    args = parser.parse_args()

    if args.inputs:
        inputs = args.inputs
    else:
        # Exclure le fichier de sortie de la liste des entrées
        out_basename = os.path.basename(args.output)
        inputs = discover_inputs(
            pattern=args.pattern,
            exclude={out_basename, "chunks.json"},
        )

    if not inputs:
        raise SystemExit(
            "Aucun fichier d'entrée trouvé. "
            "Spécifie --inputs ou place des fichiers chunks_*.json dans le dossier."
        )

    print(f"\nFichiers à fusionner ({len(inputs)}) :")
    for p in inputs:
        print(f"  - {p}")
    print(f"Sortie : {args.output}")
    if args.filter_ue:
        print(f"Filtre UE : {args.filter_ue}")
    print()

    merge(
        inputs=inputs,
        output=args.output,
        filter_ue=args.filter_ue,
        deduplicate=not args.no_dedup,
    )
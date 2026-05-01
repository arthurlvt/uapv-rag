"""
rag_extract_ue.py
-----------------
Étape 1 (variante) : extraction ciblée pour UNE SEULE UE.

Différence avec `rag_extract.py` :
- `rag_extract.py` parcourt un dossier `ressources/` et déduit l'UE
  comme étant le 1er sous-dossier (`Mathematiques`, `FondementInformatique`...).
- `rag_extract_ue.py` reçoit directement le dossier d'une UE et utilise
  le nom de ce dossier (ou un nom forcé via `--ue-name`) comme UE.
  Pratique pour ré-extraire ponctuellement après ajout/modif de fichiers
  dans une seule UE, sans tout retraiter.

Usage :
    python rag_extract_ue.py --input ./ressources/FondementInformatique
    python rag_extract_ue.py --input ./ressources/FondementInformatique \\
        --ue-name FondementInformatique \\
        --output ./chunks_FondementInformatique.json

Le script réutilise les fonctions de `rag_extract.py` (pas de duplication
de logique : extraction PDF, nettoyage LaTeX, chunking).
"""
import os
import json
import argparse

from rag_extract import (
    extract_file,
    clean_text,
    chunk_text,
    detect_doc_type,
)


def process_ue_directory(
    ue_dir: str,
    ue_name: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[dict]:
    """
    Parcourt récursivement `ue_dir` (un dossier d'UE) et produit
    des chunks enrichis de métadonnées avec ue = ue_name.

    Le `doc_type` est déduit du chemin relatif (sous-dossiers TDs/CCs/cours/TPs...).
    """
    results = []
    supported = {".pdf", ".tex"}
    stats = {"fichiers": 0, "chunks": 0, "par_type": {}}

    for root, _, files in os.walk(ue_dir):
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported:
                continue

            filepath = os.path.join(root, filename)
            doc_type = detect_doc_type(filepath)

            print(f"  [{ue_name}] [{doc_type}] {filename}")

            try:
                raw, source_type = extract_file(filepath)
                cleaned = clean_text(raw, source_type=source_type)
                chunks = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)

                for i, chunk in enumerate(chunks):
                    results.append({
                        "ue":       ue_name,
                        "doc_type": doc_type,
                        "source":   filename,
                        "chunk_id": i,
                        "text":     chunk,
                    })

                stats["fichiers"] += 1
                stats["chunks"]   += len(chunks)
                stats["par_type"][doc_type] = stats["par_type"].get(doc_type, 0) + 1

                print(f"     → {len(chunks)} chunks")

            except Exception as e:
                print(f"     ERREUR : {e}")

    # Résumé
    print("\n── Résumé ──────────────────────────────")
    print(f"  UE              : {ue_name}")
    print(f"  Fichiers traités: {stats['fichiers']}")
    print(f"  Chunks produits : {stats['chunks']}")
    if stats["par_type"]:
        print(f"  Répartition par type :")
        for t, n in sorted(stats["par_type"].items()):
            print(f"    {t:<12} {n} fichier(s)")
    print("────────────────────────────────────────\n")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extraction RAG ciblée pour UNE seule UE"
    )
    parser.add_argument("--input", required=True,
        help="Dossier racine de l'UE (ex: ./ressources/FondementInformatique)")
    parser.add_argument("--ue-name", default=None,
        help="Nom de l'UE à utiliser dans les chunks "
             "(par défaut, nom du dossier --input)")
    parser.add_argument("--output", default=None,
        help="Fichier JSON de sortie "
             "(par défaut: ./chunks_<UE>.json)")
    parser.add_argument("--chunk-size", type=int, default=500,
        help="Taille des chunks en mots")
    parser.add_argument("--overlap", type=int, default=50,
        help="Chevauchement entre chunks")
    args = parser.parse_args()

    if not os.path.isdir(args.input):
        raise SystemExit(f"Erreur : '{args.input}' n'est pas un dossier")

    ue_name = args.ue_name or os.path.basename(os.path.normpath(args.input))
    output  = args.output  or f"./chunks_{ue_name}.json"

    print(f"\nDossier UE     : {args.input}")
    print(f"Nom de l'UE    : {ue_name}")
    print(f"Sortie         : {output}")
    print(f"Chunk size     : {args.chunk_size} mots | Overlap : {args.overlap} mots\n")

    chunks = process_ue_directory(
        args.input,
        ue_name=ue_name,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )

    with open(output, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"Terminé — {len(chunks)} chunks sauvegardés dans : {output}")
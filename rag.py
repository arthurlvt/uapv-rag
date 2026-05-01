import argparse
import sys


# ── Sous-commande : extract ────────────────────────────────────────────────────

def cmd_extract(args):
    from modules.rag_extract import process_directory
    import json

    print(f"\nDossier source : {args.input}")
    print(f"Chunk size     : {args.chunk_size} mots | Overlap : {args.overlap} mots\n")

    chunks = process_directory(args.input, args.chunk_size, args.overlap)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"Terminé — {len(chunks)} chunks sauvegardés dans : {args.output}")


# ── Sous-commande : extract-ue ─────────────────────────────────────────────────

def cmd_extract_ue(args):
    import os, json
    from modules.rag_extract_ue import process_ue_directory

    if not os.path.isdir(args.input):
        sys.exit(f"Erreur : '{args.input}' n'est pas un dossier")

    ue_name = args.ue_name or os.path.basename(os.path.normpath(args.input))
    output  = args.output  or f"./chunks_{ue_name}.json"

    print(f"\nDossier UE  : {args.input}")
    print(f"Nom de l'UE : {ue_name}")
    print(f"Sortie      : {output}")
    print(f"Chunk size  : {args.chunk_size} mots | Overlap : {args.overlap} mots\n")

    chunks = process_ue_directory(
        args.input,
        ue_name=ue_name,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )

    with open(output, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"Terminé — {len(chunks)} chunks sauvegardés dans : {output}")


# ── Sous-commande : merge ──────────────────────────────────────────────────────

def cmd_merge(args):
    import os
    from modules.rag_merge import merge, discover_inputs

    if args.inputs:
        inputs = args.inputs
    else:
        out_basename = os.path.basename(args.output)
        inputs = discover_inputs(
            pattern=args.pattern,
            exclude={out_basename, "chunks.json"},
        )

    if not inputs:
        sys.exit(
            "Aucun fichier d'entrée trouvé. "
            "Spécifie --inputs ou place des fichiers chunks_*.json dans le dossier."
        )

    print(f"\nFichiers à fusionner ({len(inputs)}) :")
    for p in inputs:
        print(f"  - {p}")
    print(f"Sortie : {args.output}\n")

    merge(
        inputs=inputs,
        output=args.output,
        filter_ue=args.filter_ue,
        deduplicate=not args.no_dedup,
    )


# ── Sous-commande : check ──────────────────────────────────────────────────────

def cmd_check(args):
    import os
    from modules.rag_count_sources import count_files, load_chunks_stats, print_summary, compare_with_chunks

    if not os.path.isdir(args.input):
        sys.exit(f"Erreur : '{args.input}' n'est pas un dossier")

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


# ── Sous-commande : chat ───────────────────────────────────────────────────────

def cmd_chat(args):
    from modules.rag_app import load_chunks, build_index, run_chat
    chunks = load_chunks()
    index  = build_index(chunks)
    run_chat(chunks, index)


# ── Parser principal ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="rag",
        description="🎓 Pipeline RAG — UAPV L1 Informatique",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commandes :
  extract       Extraire et chunker tous les cours
  extract-ue    Extraire et chunker une seule UE
  merge         Fusionner plusieurs JSON de chunks
  check         Vérifier la couverture des fichiers sources
  chat          Lancer l'assistant IA

exemples :
  python rag.py extract
  python rag.py extract --input ./cours --output ./chunks_all.json
  python rag.py extract-ue --input ./cours/maths/analyse1
  python rag.py merge
  python rag.py check --input ./cours --chunks ./chunks_all.json
  python rag.py chat
        """,
    )

    sub = parser.add_subparsers(dest="command", metavar="commande")
    sub.required = True

    # ── extract ────────────────────────────────────────────────────────────────
    p_extract = sub.add_parser("extract", help="Extraire et chunker tous les cours")
    p_extract.add_argument("--input",      default="./cours",           help="Dossier racine (défaut: ./cours)")
    p_extract.add_argument("--output",     default="./chunks_all.json", help="JSON de sortie (défaut: ./chunks/chunks_all.json)")
    p_extract.add_argument("--chunk-size", type=int, default=500,       help="Taille des chunks en mots (défaut: 500)")
    p_extract.add_argument("--overlap",    type=int, default=50,        help="Chevauchement en mots (défaut: 50)")
    p_extract.set_defaults(func=cmd_extract)

    # ── extract-ue ─────────────────────────────────────────────────────────────
    p_ue = sub.add_parser("extract-ue", help="Extraire et chunker une seule UE")
    p_ue.add_argument("--input",      required=True,  help="Dossier de l'UE (ex: ./cours/maths/analyse1)")
    p_ue.add_argument("--ue-name",    default=None,   help="Nom de l'UE (défaut: nom du dossier)")
    p_ue.add_argument("--output",     default=None,   help="JSON de sortie (défaut: ./chunks/chunks_<UE>.json)")
    p_ue.add_argument("--chunk-size", type=int, default=500, help="Taille des chunks en mots (défaut: 500)")
    p_ue.add_argument("--overlap",    type=int, default=50,  help="Chevauchement en mots (défaut: 50)")
    p_ue.set_defaults(func=cmd_extract_ue)

    # ── merge ──────────────────────────────────────────────────────────────────
    p_merge = sub.add_parser("merge", help="Fusionner plusieurs JSON de chunks")
    p_merge.add_argument("--inputs",    nargs="*", default=None,             help="Fichiers à fusionner (défaut: auto chunks_*.json)")
    p_merge.add_argument("--output",   default="./chunks_all.json",          help="JSON de sortie (défaut: ./chunks/chunks_all.json)")
    p_merge.add_argument("--filter-ue", default=None,                        help="Ne garder qu'une UE")
    p_merge.add_argument("--no-dedup",  action="store_true",                 help="Désactiver la déduplication")
    p_merge.add_argument("--pattern",  default="chunks_*.json",              help="Pattern de découverte (défaut: chunks_*.json)")
    p_merge.set_defaults(func=cmd_merge)

    # ── check ──────────────────────────────────────────────────────────────────
    p_check = sub.add_parser("check", help="Vérifier la couverture des fichiers sources")
    p_check.add_argument("--input",      required=True,              help="Dossier racine des cours")
    p_check.add_argument("--chunks",     default=None,               help="JSON de chunks à comparer (optionnel)")
    p_check.add_argument("--extensions", nargs="+", default=[".pdf", ".tex"], help="Extensions à analyser (défaut: .pdf .tex)")
    p_check.set_defaults(func=cmd_check)

    # ── chat ───────────────────────────────────────────────────────────────────
    p_chat = sub.add_parser("chat", help="Lancer l'assistant IA")
    p_chat.set_defaults(func=cmd_chat)

    # ── Dispatch ───────────────────────────────────────────────────────────────
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
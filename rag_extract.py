"""
rag_extract.py
--------------
Extraction, nettoyage et chunking de TOUTES les ressources de cours.

Structure attendue (3 niveaux) :
    cours/
    ├── fondementInformatique/          ← catégorie (niveau 1)
    │   ├── S1_fondementInfo/           ← UE        (niveau 2)
    │   │   ├── CCs/                    ← doc_type  (niveau 3)
    │   │   │   └── fichier.pdf
    │   │   ├── cours/
    │   │   └── TDs/
    │   └── cours_info.pdf              ← PDF global (UE = catégorie)
    ├── maths/
    │   ├── analyse1/
    │   │   ├── CCs/
    │   │   ├── cours/
    │   │   └── analyse1_cours.pdf      ← PDF global dans UE
    │   └── ...
    └── programmation/
        ├── CPP/
        │   ├── cours/
        │   └── TPs/
        └── cheatsheets.pdf             ← PDF global (UE = catégorie)

Chaque chunk produit :
    {
        "category": "maths",            # dossier niveau 1
        "ue":       "analyse1",         # dossier niveau 2
        "doc_type": "cours",            # type détecté automatiquement
        "source":   "analyse1_cours.pdf",
        "chunk_id": 0,
        "text":     "..."
    }

Usage :
    python rag_extract.py
    python rag_extract.py --input ./cours --output ./chunks_all.json
    python rag_extract.py --input ./cours --output ./chunks_all.json --chunk-size 400 --overlap 40
"""

import os
import re
import json
import argparse


# ── Détection du type de document ─────────────────────────────────────────────

DOC_TYPE_KEYWORDS = {
    "correction": ["correction", "corrigé", "corrige", "solution", "reponse", "réponse"],
    "CC":         ["cc", "controle", "contrôle", "exam", "partiel", "ds"],
    "TP":         ["tp", "travaux pratiques"],
    "TD":         ["td", "travaux dirigés", "travaux diriges"],
    "cours":      ["cours", "lecture", "cm", "poly", "polycopié", "cheatsheet"],
}

def detect_doc_type(filepath: str) -> str:
    """
    Déduit le type de document depuis le chemin complet.
    Analyse le nom du fichier ET les dossiers parents (en minuscules).
    Priorité : correction > CC > TP > TD > cours > autre.
    """
    path_lower = filepath.lower().replace("\\", "/")
    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        if any(kw in path_lower for kw in keywords):
            return doc_type
    return "autre"


# ── Détection catégorie / UE ───────────────────────────────────────────────────

def detect_category_and_ue(filepath: str, root_dir: str) -> tuple[str, str]:
    """
    Extrait la catégorie (niveau 1) et l'UE (niveau 2) depuis le chemin relatif.

    Règles :
      - Si ≥ 3 parties : category = parts[0], ue = parts[1]
      - Si   2 parties : category = parts[0], ue = parts[0]  (PDF global)

    Exemples avec root_dir = "./cours" :
      fondementInformatique/S1_fondementInfo/CCs/f.pdf  → ("fondementInformatique", "S1_fondementInfo")
      fondementInformatique/cours_info.pdf              → ("fondementInformatique", "fondementInformatique")
      maths/analyse1/cours/f.pdf                        → ("maths", "analyse1")
      maths/analyse1/analyse1_cours.pdf                 → ("maths", "analyse1")
      programmation/CPP/TPs/f.pdf                       → ("programmation", "CPP")
      programmation/cheatsheets.pdf                     → ("programmation", "programmation")
    """
    rel   = os.path.relpath(filepath, root_dir)
    parts = rel.replace("\\", "/").split("/")

    category = parts[0] if len(parts) >= 1 else "Inconnu"
    ue       = parts[1] if len(parts) >= 3 else category

    return category, ue


# ── Extraction du texte ────────────────────────────────────────────────────────

def extract_pdf(path: str) -> str:
    """Extrait le texte brut d'un PDF texte (non scanné) via PyMuPDF."""
    import fitz  # PyMuPDF
    text = []
    with fitz.open(path) as doc:
        for page in doc:
            text.append(page.get_text())
    return "\n".join(text)


def extract_latex(path: str) -> str:
    """Lit un fichier .tex et retourne son contenu brut."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def extract_file(path: str) -> tuple[str, str]:
    """
    Détecte le format, extrait le texte.
    Retourne (texte_brut, source_type) où source_type ∈ {"pdf", "latex"}.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_pdf(path), "pdf"
    elif ext == ".tex":
        return extract_latex(path), "latex"
    else:
        raise ValueError(f"Format non supporté : {ext}")


# ── Nettoyage ──────────────────────────────────────────────────────────────────

def clean_latex(text: str) -> str:
    """Supprime les commandes LaTeX, conserve le contenu sémantique."""
    # Commentaires
    text = re.sub(r"%.*", "", text)

    # Environnements non textuels
    for env in ["figure", "table", "equation", "align", "tikzpicture",
                "lstlisting", "verbatim", "array", "tabular"]:
        text = re.sub(
            rf"\\begin\{{{env}\*?\}}.*?\\end\{{{env}\*?\}}",
            " ", text, flags=re.DOTALL
        )

    # Commandes de structure → garder le titre
    text = re.sub(
        r"\\(section|subsection|subsubsection|paragraph|chapter)\*?\{([^}]+)\}",
        r"\2 : ", text
    )

    # Mise en forme → garder le contenu
    text = re.sub(r"\\(textbf|textit|emph|underline|texttt)\{([^}]+)\}", r"\2", text)

    # Commandes restantes avec arguments
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?\{[^}]*\}", "", text)

    # Commandes sans arguments
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)

    # Accolades résiduelles
    text = re.sub(r"[{}]", "", text)

    return text


def clean_text(text: str, source_type: str = "pdf") -> str:
    """
    Nettoyage général :
    - Applique clean_latex si fichier .tex
    - Supprime les numéros de page isolés
    - Supprime les lignes trop courtes (artefacts en-tête / pied de page)
    - Normalise les espaces et les sauts de ligne multiples
    """
    if source_type == "latex":
        text = clean_latex(text)

    # Numéros de page seuls sur une ligne
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # Lignes trop courtes (< 4 caractères)
    lines = [line for line in text.splitlines() if len(line.strip()) >= 4]
    text = "\n".join(lines)

    # Espaces multiples → un seul
    text = re.sub(r"[ \t]+", " ", text)

    # Sauts de ligne multiples → double saut
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Découpe le texte en chunks de `chunk_size` mots avec `overlap` mots
    de chevauchement entre chunks consécutifs.

    Le chevauchement garantit qu'une notion importante à cheval sur deux
    chunks reste accessible dans au moins l'un d'eux.
    """
    words  = text.split()
    chunks = []
    start  = 0

    while start < len(words):
        end   = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


# ── Pipeline principal ─────────────────────────────────────────────────────────

def process_directory(
    input_dir:  str,
    chunk_size: int = 500,
    overlap:    int = 50,
) -> list[dict]:
    """
    Parcourt récursivement `input_dir`, extrait et nettoie le texte de chaque
    fichier .pdf / .tex, puis produit des chunks enrichis de métadonnées.
    """
    results   = []
    supported = {".pdf", ".tex"}
    stats: dict[str, dict] = {}

    for root, _, files in os.walk(input_dir):
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported:
                continue

            filepath         = os.path.join(root, filename)
            category, ue     = detect_category_and_ue(filepath, input_dir)
            doc_type         = detect_doc_type(filepath)

            print(f"  [{category}/{ue}] [{doc_type}] {filename}")

            try:
                raw, source_type = extract_file(filepath)
                cleaned          = clean_text(raw, source_type=source_type)
                chunks           = chunk_text(cleaned, chunk_size=chunk_size, overlap=overlap)

                for i, chunk in enumerate(chunks):
                    results.append({
                        "category": category,
                        "ue":       ue,
                        "doc_type": doc_type,
                        "source":   filename,
                        "chunk_id": i,
                        "text":     chunk,
                    })

                key = f"{category}/{ue}"
                if key not in stats:
                    stats[key] = {"fichiers": 0, "chunks": 0}
                stats[key]["fichiers"] += 1
                stats[key]["chunks"]   += len(chunks)

                print(f"     → {len(chunks)} chunks")

            except Exception as e:
                print(f"     ERREUR : {e}")

    # ── Résumé ─────────────────────────────────────────────────────────────────
    print("\n── Résumé ───────────────────────────────────────────────────")
    for key, s in sorted(stats.items()):
        print(f"  {key:<45} {s['fichiers']:>3} fichier(s)  {s['chunks']:>5} chunks")
    total_f = sum(s["fichiers"] for s in stats.values())
    total_c = sum(s["chunks"]   for s in stats.values())
    print(f"  {'TOTAL':<45} {total_f:>3} fichier(s)  {total_c:>5} chunks")
    print("─────────────────────────────────────────────────────────────\n")

    return results


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline d'extraction RAG — UAPV L1 Informatique"
    )
    parser.add_argument(
        "--input",      default="./cours",           help="Dossier racine des ressources"
    )
    parser.add_argument(
        "--output",     default="./chunks_all.json", help="Fichier JSON de sortie"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=500,       help="Taille des chunks (en mots)"
    )
    parser.add_argument(
        "--overlap",    type=int, default=50,        help="Chevauchement entre chunks (en mots)"
    )
    args = parser.parse_args()

    print(f"\nDossier source : {args.input}")
    print(f"Chunk size     : {args.chunk_size} mots | Overlap : {args.overlap} mots\n")

    chunks = process_directory(args.input, args.chunk_size, args.overlap)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"Terminé — {len(chunks)} chunks sauvegardés dans : {args.output}")
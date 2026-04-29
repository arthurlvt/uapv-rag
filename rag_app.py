"""
rag_app.py
----------
Assistant RAG pour étudiants L1 Informatique — UAPV / CERI.

Chargement des chunks (par ordre de priorité) :
  1. Variable d'env  CHUNKS_URL  → URL raw GitHub du chunks_all.json
  2. Fichier local   chunks_all.json                (mode dev)

Variables d'environnement :
  GROQ_API_KEY   — clé API Groq                        (obligatoire)
  CHUNKS_URL     — URL raw GitHub du chunks_all.json   (recommandé en prod)

Exemple .env pour le dev local :
  GROQ_API_KEY=gsk_...
  CHUNKS_URL=https://raw.githubusercontent.com/OWNER/REPO/main/chunks_all.json

Usage :
  python rag_app.py
"""

import os
import json
import sys
import urllib.request
from pathlib import Path


# ── Chargement silencieux du .env local (dev) ──────────────────────────────────
# Évite d'avoir besoin de python-dotenv
_env_file = Path(".env")
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())


# ── Dépendances ────────────────────────────────────────────────────────────────

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False
    print("⚠️  rank-bm25 non installé — fallback sur recherche par overlap de mots.")
    print("   Pour de meilleurs résultats : pip install rank-bm25\n")

try:
    from groq import Groq
except ImportError:
    print("❌ La bibliothèque groq n'est pas installée.")
    print("   → pip install groq")
    sys.exit(1)


# ── Configuration ──────────────────────────────────────────────────────────────

LOCAL_CHUNKS = Path("chunks_all.json")
TOP_K        = 5       # chunks récupérés par requête
MODEL        = "llama-3.3-70b-versatile"
MAX_TOKENS   = 1024    # longueur max de la réponse

SYSTEM_PROMPT = """\
Tu es un assistant pédagogique pour des étudiants de première année \
en licence informatique à l'Université d'Avignon (UAPV / CERI).

Tes règles :
- Réponds UNIQUEMENT à partir des extraits de cours fournis dans le contexte.
- Explique clairement, avec des exemples simples adaptés à des débutants.
- Si la réponse n'est pas dans les extraits, dis-le honnêtement — n'invente jamais.
- Ne mentionne jamais les termes "chunks", "RAG" ou "extraits" à l'étudiant.
- Reste bienveillant, encourageant et pédagogique.
- Réponds toujours en français.\
"""


# ── Chargement des chunks ──────────────────────────────────────────────────────

def load_chunks() -> list[dict]:
    """
    Charge chunks_all.json depuis CHUNKS_URL (GitHub raw) ou en local.
    Quitte avec un message clair si aucune source n'est disponible.
    """
    url = os.getenv("CHUNKS_URL", "").strip()

    if url:
        print("📥 Chargement des chunks depuis GitHub...", end=" ", flush=True)
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            print(f"✅  {len(data)} chunks chargés.")
            return data
        except Exception as exc:
            print(f"\n⚠️  Échec ({exc}) — tentative locale...")

    if LOCAL_CHUNKS.exists():
        print(f"📂 Chargement local depuis {LOCAL_CHUNKS}...", end=" ", flush=True)
        with open(LOCAL_CHUNKS, encoding="utf-8") as f:
            data = json.load(f)
        print(f"✅  {len(data)} chunks chargés.")
        return data

    print("\n❌  Impossible de charger les chunks.")
    print("    → Définir CHUNKS_URL ou placer chunks_all.json dans le dossier courant.")
    print("    → Exemple : export CHUNKS_URL='https://raw.githubusercontent.com/OWNER/REPO/main/chunks_all.json'")
    sys.exit(1)


# ── Index de recherche ─────────────────────────────────────────────────────────

def build_index(chunks: list[dict]) -> "BM25Okapi | None":
    """Construit un index BM25 sur le texte de chaque chunk."""
    if not HAS_BM25:
        return None
    tokenized = [chunk["text"].lower().split() for chunk in chunks]
    return BM25Okapi(tokenized)


def retrieve(
    query:  str,
    chunks: list[dict],
    index:  "BM25Okapi | None",
    top_k:  int = TOP_K,
) -> list[dict]:
    """
    Retourne les top_k chunks les plus pertinents pour `query`.
    Utilise BM25 si disponible, sinon overlap de mots (fallback).
    """
    if HAS_BM25 and index is not None:
        scores      = index.get_scores(query.lower().split())
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [chunks[i] for i in top_indices]

    # Fallback : overlap de mots
    q_words = set(query.lower().split())
    scored  = sorted(chunks, key=lambda c: len(q_words & set(c["text"].lower().split())), reverse=True)
    return scored[:top_k]


# ── Formatage du contexte ──────────────────────────────────────────────────────

def format_context(retrieved: list[dict]) -> str:
    """
    Formate les chunks récupérés en bloc de contexte injecté dans le prompt système.
    """
    parts = []
    for i, chunk in enumerate(retrieved, 1):
        header = (
            f"[Extrait {i}"
            f" | Matière : {chunk.get('ue', '?')}"
            f" | Type : {chunk.get('doc_type', '?')}"
            f" | Source : {chunk.get('source', '?')}]"
        )
        parts.append(f"{header}\n{chunk.get('text', '')}")
    return "\n\n---\n\n".join(parts)


# ── Boucle de conversation ─────────────────────────────────────────────────────

def run_chat(chunks: list[dict], index: "BM25Okapi | None") -> None:
    """
    Boucle de conversation RAG : récupération → prompt → Groq → réponse.

    L'historique conserve uniquement les échanges utilisateur/assistant,
    sans répéter le contexte à chaque tour (économie de tokens).
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        print("❌  Variable GROQ_API_KEY manquante.")
        print("    → export GROQ_API_KEY='gsk_...'")
        sys.exit(1)

    client  = Groq(api_key=api_key)
    history: list[dict] = []

    print("\n" + "═" * 62)
    print("  🎓 Assistant IA — L1 Informatique UAPV")
    print("  Tapez 'exit' ou 'quit' pour quitter.")
    print("═" * 62 + "\n")

    while True:
        # ── Lecture de la question ──────────────────────────────────────
        try:
            user_input = input("Vous : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAu revoir !")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Au revoir !")
            break

        # ── Récupération des chunks pertinents ──────────────────────────
        retrieved = retrieve(user_input, chunks, index)
        context   = format_context(retrieved)

        # ── Construction des messages ───────────────────────────────────
        # Le contexte est injecté dans le message système à chaque tour,
        # car il change à chaque question. L'historique reste léger.
        system = SYSTEM_PROMPT + "\n\n## Extraits de cours :\n\n" + context

        messages = (
            [{"role": "system", "content": system}]
            + history
            + [{"role": "user", "content": user_input}]
        )

        # ── Appel à Groq ────────────────────────────────────────────────
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=MAX_TOKENS,
            )
            reply = response.choices[0].message.content
        except Exception as exc:
            print(f"  ⚠️  Erreur Groq : {exc}\n")
            continue

        # ── Mise à jour de l'historique ─────────────────────────────────
        history.append({"role": "user",      "content": user_input})
        history.append({"role": "assistant", "content": reply})

        print(f"\nAssistant : {reply}\n")


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    chunks = load_chunks()
    index  = build_index(chunks)
    run_chat(chunks, index)
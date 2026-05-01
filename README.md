# uapv-rag — Assistant IA pour étudiants L1 Informatique

Pipeline RAG (Retrieval-Augmented Generation) construit sur les ressources de cours de la Licence 1 Informatique d'Avignon Université. L'objectif est de fournir aux étudiants un assistant capable de répondre à leurs questions en s'appuyant sur les vrais documents du cursus (cours, TDs, TPs, CCs avec corrections), pas seulement sur la connaissance générale du LLM.
Ce README me permettra de présenter l'avancement du projet car je n'utilise presque pas ou pas bien les messages de commit lol.



## Première Etape: Extraction de tous les cours de l'UAPV / personnels (2025/2026)

La première grosse partie de ce projet -- qui en réalité est toujours d'actualité -- a été de télécharger / extraire toute les ressources mises à disposition par l'Université d'Avignon et également les cours que j'ai rédigé moi même afin d'avoir la plage de données la plus étendue possible. Ensuite, il a fallu trier chaque cours selon l'UE et leur catégorie (TDs, TPs, CCs, cours) puis de les convertir si besoin en latex afin que ce soit lisible par tous mais aussi et surtout par un programme ce qui n'aura pas été une mince affaire. Le but étant d'avoir un assistant des plus efficaces possible il faut en permanence regarder si de nouvelles ressources ne sont pas disponibles.


## Deuxième Etape: Tests de reqûetes API avec une IA ()

Pour cette deuxième étape, j'ai cherché une IA dont l'utilisation d'API était gratuite et cette étape n'a encore une fois pas été simple à mettre en place car la plus part des développeurs d'IA demandent un abonnement pour utiliser leur API. J'ai finalement opté provisoirement pour Groq IA même si celle-ci n'est pas la meilleure, cela me permettra déjà d'avancer pas mal dans mon outil. J'ai donc réalisé un "petit" programme python, simple initialement avec un appel d'API à Groq avec son modèle **llama-3.3-70b-versatile** et quelques lignes permettant qu'il garde la discussion, l'historique.


## Troisième Etape: Création de chunks ()

La troisième étape consistait à découper l'ensemble des ressources extraites en **chunks** — des morceaux de texte de taille fixe (500 mots par défaut) avec un léger chevauchement entre eux (50 mots) pour éviter de couper une notion importante en deux. Chaque chunk est enrichi de métadonnées : la catégorie de cours (maths, programmation, fondementInformatique...), l'UE précise (analyse1, CPP, S1_fondementInfo...), le type de document (cours, TD, TP, CC, correction) et le fichier source. Ces métadonnées permettront plus tard de cibler la recherche et d'indiquer à l'étudiant d'où vient la réponse.

L'extraction gère deux formats : les **PDFs** (via PyMuPDF) et les **fichiers LaTeX** (.tex), avec un nettoyage spécifique pour chaque format — suppression des commandes LaTeX, des numéros de page isolés, des artefacts d'en-tête et de pied de page. L'ensemble du pipeline est regroupé dans un seul point d'entrée (`rag.py`) qui expose plusieurs sous-commandes.


## Quatrième Etape: Mise en place du RAG et du pipeline automatisé (30/04/2026 - 01/05/2026)

Une fois les chunks prêts, le cœur du RAG a pu être mis en place. À chaque question d'un étudiant, le système récupère les **5 chunks les plus pertinents** grâce à une recherche **BM25** (algorithme de ranking textuel), les injecte dans le prompt système envoyé à Groq, et l'IA répond en s'appuyant exclusivement sur ces extraits — sans inventer.

Pour que les chunks restent toujours à jour sans intervention manuelle, un workflow **GitHub Actions** tourne automatiquement chaque nuit à 3h UTC. Il clone le repo public [uapv-cours](https://github.com/arthurlvt/uapv-cours) contenant toutes les ressources pédagogiques, régénère le fichier `chunks_all.json` et le commite dans ce repo privé si des changements ont été détectés. De plus, un second workflow se déclenche automatiquement à chaque push sur `uapv-cours` (via un `repository_dispatch`), ce qui garantit que l'ajout d'un nouveau document de cours se reflète quasi immédiatement dans l'assistant.


## Cinquième Etape: Amélioration du RAG avec la recherche sémantique

à venir...


## Etape Parallèle: Rédaction d'un rapport de recherche

Cette étape que je réalise continuellement tout au long du projet est pour moi la plus importante car elle englobe l'intégralité du projet, allant de la recherche des différents éléments à la mise en place et la structuration du projet!



## Prochaines étapes

- [ ] Remplacer BM25 par une recherche par **embeddings** (recherche sémantique) pour des résultats plus pertinents
- [ ] Déployer l'assistant sur un serveur pour un accès via interface web
- [ ] Ajouter une interface graphique simple pour les étudiants
- [ ] Étendre les ressources aux autres matières encore manquantes
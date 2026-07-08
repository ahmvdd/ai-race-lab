# AI Race Lab

Deux modèles Ollama locaux s'affrontent sur une grille NxN pour trouver un bonus caché en premier. Chaque modèle reçoit un résumé de ses parties précédentes (mémoire injectée dans le prompt) pour observer s'il adapte sa stratégie au fil des épisodes.

## Prérequis

- Python 3.10+
- [Ollama](https://ollama.com) qui tourne en local (`ollama serve`)
- Les modèles pull-és, ex. : `ollama pull llama3.2 && ollama pull phi3`

```bash
pip install -r requirements.txt
```

## Lancer une session

```bash
python scripts/run_experiment.py --model-a llama3.2 --model-b phi3 --episodes 6
```

Options principales :

| Option | Défaut | Effet |
|---|---|---|
| `--grid-size` | 6 | Taille de la grille. Plus grand = plus dur. |
| `--visibility` | 2 | Rayon de visibilité du bonus (Tchebychev). **Paramètre le plus impactant** : à 1 l'agent doit vraiment explorer, à 3+ sur une petite grille il voit le bonus presque tout de suite. |
| `--episodes` | 6 | Nombre de parties de la session. |
| `--memory-depth` | 3 | Nombre de parties précédentes résumées dans le prompt (0 = pas de mémoire). |
| `--memory-strategy` | brut | `brut` = résumé seul, `conseil` = résumé + conseil explicite de stratégie. |
| `--swap-start` | off | Alterne qui joue en premier à chaque épisode (contrôle du biais d'ordre). |
| `--seed` | aléatoire | Grilles reproductibles (le bonus change à chaque épisode : seed+épisode). |
| `--chat` | off | Chaque agent peut ajouter un message court à son coup (bluff, moquerie, négociation), relayé à l'adversaire au tour suivant. Purement cosmétique/expérimental : ça ne change pas les règles du jeu, et ça n'entraîne pas les modèles. |

Chaque session produit dans `logs/` :
- `session_<timestamp>.jsonl` — un objet JSON complet par épisode (trails, positions, invalides, messages si `--chat`…)
- `session_<timestamp>.csv` — le même en tableur, avec les ratios d'efficacité calculés (les messages ne sont pas dans le CSV, seulement le JSONL)

## Analyser les résultats

```bash
python analysis/plot_results.py logs/session_XXXX.jsonl
```

Génère un PNG à 4 graphes + un résumé texte, **sans relancer les modèles** :

1. **Coups par épisode** — descend-il au fil des parties ?
2. **Ratio d'efficacité** (coups / distance Manhattan optimale) — *la* métrique honnête de progression : 1.0 = trajet parfait. Calculé **uniquement sur les épisodes gagnés** : le perdant s'arrête quand l'autre trouve le bonus, son nombre de coups est tronqué et donnerait un ratio faussement bon.
3. **Victoires cumulées** A vs B.
4. **Réponses invalides par épisode** — à lire en parallèle du reste : si l'efficacité s'améliore *et* que les invalides baissent, le "progrès" est peut-être juste un meilleur respect du format, pas une meilleure stratégie.

## Comment lire les résultats

- Une **réponse invalide** (mal formatée ou coup hors grille) est comptée séparément et remplacée par un coup aléatoire valide pour ne pas bloquer la partie. Elle pollue donc légèrement le trail — d'où l'intérêt de la courbe 4.
- Un épisode sans vainqueur (`winner: null`) signifie que le plafond de coups (`grid_size² × 3` par agent) a été atteint.
- Pour comparer deux configs (ex. visibilité 1 vs 3), lancez deux sessions avec le **même `--seed`** et les mêmes modèles.

## Tests

```bash
pytest
```

Les tests tournent **sans Ollama** : le moteur de jeu (`ai_race/engine.py`) est pur, et l'orchestrateur (`ai_race/runner.py`) est testé avec un faux LLM injecté.

## Structure

```
ai_race/
├── engine.py         # logique de jeu pure (grille, règles) — zéro I/O
├── ollama_client.py  # appel API Ollama + parsing des réponses
├── memory.py         # résumé/mémoire injectée par agent
├── runner.py         # orchestration épisode/session (LLM injectable)
└── logging_utils.py  # écriture JSONL + CSV
scripts/run_experiment.py   # CLI
analysis/plot_results.py    # graphes + résumé depuis les logs
tests/                      # tests unitaires, sans réseau
```

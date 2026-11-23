---
name: stagelink-audit
description: Audit non destructif de StageLink avant une mission, comparaison entre exigences et implémentation réelle, diagnostic et rapport d'état des lieux.
---

# Skill — Audit StageLink

## Objectif
Établir un état factuel sans modifier le dépôt.

## Procédure
1. Lire `AGENTS.md` et les instructions du dépôt.
2. Exécuter les vérifications Git non destructives : branche, statut, diff, fichiers non suivis. Ne pas afficher de secrets.
3. Repérer les applications, modèles, vues, services, templates, tâches, migrations, tests et configurations concernés.
4. Comparer les exigences fournies avec le code réellement observé.
5. Exécuter uniquement des commandes d'inspection sûres. Ne pas lancer de migration, paiement, tâche destructive ou écriture en base.
6. Ne modifier aucun fichier pendant un audit.
7. Séparer les faits observés, hypothèses et points non vérifiables.

## Livrable
Présenter : implémenté, testé (preuve), restant, anomalies, divergences métier/techniques, risques, dépendances et questions à la propriétaire. Pour chaque constat, citer le fichier et le symbole ou la zone concernés.

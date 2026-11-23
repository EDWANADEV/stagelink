---
name: stagelink-git-workflow
description: Workflow Git StageLink par mission : branches dédiées, commits prudents, Pull Requests et rapport de livraison sans fusion automatique.
---

# Skill — Workflow Git StageLink

## Début de mission
1. Lire `AGENTS.md`.
2. Vérifier branche, `git status`, diff indexé/non indexé et fichiers non suivis.
3. Identifier la PR existante et la branche de base convenue.
4. Vérifier que `output.css` et les autres changements préexistants sont préservés.
5. Ne pas changer de branche si le répertoire contient des changements non compris.

## Branche
- Une branche dédiée par journée ou mission, avec nom explicite, par exemple `feat/day-6-reviews-ai`.
- Ne jamais travailler directement sur `main`.
- Ne jamais créer une branche portant un nom déjà utilisé sans vérifier son état.
- Ne jamais mélanger deux missions indépendantes dans une même branche sans accord.

## Commits et PR
- Inspecter le diff avant tout commit.
- Ne jamais inclure `.env`, secrets, données personnelles, fichiers générés non concernés ou `output.css` préexistant.
- Ne pas pousser ou créer une PR si l'autorisation ou les accès ne le permettent pas ; préparer alors le titre, la description et les étapes.
- À la fin, préparer une PR vers la branche cible convenue.
- Ne jamais fusionner, supprimer une branche distante ou réécrire l'historique sans autorisation explicite.

## Rapport
Inclure branche, base, commits, fichiers, statut de push/PR, tests, risques et confirmation de préservation des changements locaux.

---
name: stagelink-django
description: Développement contrôlé de fonctionnalités Django StageLink en respectant SSR, architecture existante, règles métier approuvées et sécurité.
---

# Skill — Développement Django StageLink

## Avant de coder
- Confirmer la mission, la branche et les critères d'acceptation.
- Lire les modèles, vues, services, templates, URLs, migrations et tests directement concernés.
- Identifier les règles métier déjà validées. Toute règle manquante est une question, pas une invitation à inventer.

## Implémentation
- Conserver Django SSR et les conventions existantes.
- Mettre la logique métier dans les services lorsque cela améliore la clarté et la testabilité.
- Garder les vues centrées sur HTTP et les templates sur la présentation.
- Valider côté serveur, vérifier les permissions sur chaque action sensible.
- Prévoir les cas limites, transactions, concurrence et erreurs.
- Éviter les changements de schéma si une solution sans migration est suffisante ; toute migration doit être justifiée.
- Ne pas ajouter de DRF, d'application, signal, middleware ou dépendance sans accord.

## Page d'accueil — aperçu limité des offres
- Appliquer les règles de la section 6 de `AGENTS.md`.
- Le masquage visuel n'est pas un contrôle d'accès : les champs non autorisés ne doivent jamais quitter le serveur.
- Utiliser une liste blanche de champs explicitement approuvés.
- Si la liste des champs visibles aux visiteurs anonymes n'est pas définie, demander la décision à la propriétaire avant de l'implémenter.
- Prévoir des tests qui inspectent le HTML et les réponses réseau pour s'assurer qu'aucune donnée restreinte n'est transmise.
- L'appel à l'inscription/connexion doit être clair et accessible.

## Tests et livraison
- Ajouter des tests unitaires et/ou d'intégration couvrant succès, permissions, erreurs et cas limites.
- Vérifier migrations, `manage.py check` et tests ciblés.
- Signaler précisément les tests non exécutés.
- Terminer par le rapport obligatoire.

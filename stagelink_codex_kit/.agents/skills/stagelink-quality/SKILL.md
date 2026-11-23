---
name: stagelink-quality
description: Revue qualité StageLink : PEP 8, Ruff, tests, sécurité, performance Django, requêtes N+1, internationalisation et maîtrise des coûts.
---

# Skill — Qualité StageLink

## Revue obligatoire
- PEP 8 et conventions du dépôt ; Ruff si configuré.
- Tests ciblés, vérification Django et migrations.
- Permissions et validation serveur.
- CSRF, téléversements, redirections, secrets et journaux.
- Requêtes ORM : rechercher N+1, utiliser `select_related`/`prefetch_related` à bon escient.
- Index et champs : justifier chaque ajout.
- Internationalisation FR/EN avec mécanismes Django.
- Accessibilité, responsive et absence de régression frontend.

## Maîtrise des coûts
- Réduire appels réseau et fournisseurs externes.
- Éviter les tâches périodiques trop fréquentes et les traitements redondants.
- Charger seulement les champs et relations nécessaires.
- Ne pas ajouter de dépendance sans bénéfice démontré.
- Pour une fonction IA, vérifier limites de taille, nombre d'appels, timeouts, gestion des erreurs et solution de repli.

## Page d'accueil
Vérifier qu'un visiteur anonyme ne reçoit pas les champs d'offre restreints. Un effet CSS de flou ne protège pas une donnée déjà présente dans le DOM, le HTML, le JSON ou les scripts. Tester la réponse serveur et les réponses réseau.

## Rapport
Fournir les commandes exécutées, résultats exacts, tests ignorés et raisons. Ne jamais annoncer une conformité complète sur la base d'une vérification partielle.

# Kit Codex StageLink

Ce kit contient :
- `AGENTS.md` : règles permanentes à la racine du dépôt.
- `.agents/skills/*/SKILL.md` : Skills spécialisés.
- `docs/rapport-mission-template.md` : modèle de rapport.

## Intégration
Copier les fichiers et dossiers dans le dépôt StageLink en conservant exactement leur structure. Si un fichier existe déjà, ne pas l'écraser : comparer et fusionner manuellement.

## Skills inclus
- stagelink-audit
- stagelink-django
- stagelink-payments
- stagelink-quality
- stagelink-git-workflow
- stagelink-ai

## Important
Ce kit est une base de gouvernance préparée à partir des exigences communiquées. Il ne remplace pas l'inspection du dépôt réel. Vérifier la compatibilité du chemin `.agents/skills/` avec la configuration Codex utilisée avant l'intégration définitive.


## Version 2 — décisions métier consolidées
Cette version formalise les mêmes restrictions pour les offres StageLink et les offres externes relayées : pas de nom d'entreprise, de coordonnées ni de lien source dans l'aperçu anonyme ; accès au détail après inscription gratuite ou connexion ; contrôle d'accès côté serveur. Le titre réel n'est pas automatiquement public, car il peut permettre de retrouver l'annonce en dehors de StageLink : sa visibilité doit être confirmée avant implémentation.

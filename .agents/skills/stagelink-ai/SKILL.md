---
name: stagelink-ai
description: Cadrage et intégration des fonctionnalités d'intelligence artificielle facultatives de StageLink, avec analyse des données, coûts, sécurité et cas d'utilisation UML.
---

# Skill — Intelligence artificielle StageLink

## Principes
- L'IA est facultative et ne doit jamais bloquer les fonctions essentielles.
- Ne jamais inventer diplômes, expériences, compétences ou informations personnelles.
- Ne jamais envoyer un CV, un profil ou des données personnelles à un fournisseur sans décision explicite de la propriétaire et information/consentement appropriés.
- Ne choisir ni fournisseur, ni modèle, ni budget, ni politique de conservation sans validation.
- Ne pas intégrer une fonction tant que ses acteurs, données d'entrée, résultats, limites et critères de réussite ne sont pas cadrés.
- Minimiser les données transmises et les coûts ; éviter les appels inutiles et prévoir limites, timeouts, quotas et gestion des erreurs.
- Prévoir une solution de repli lorsque le fournisseur est indisponible.
- Les sorties IA doivent être présentées comme des suggestions à vérifier par l'utilisateur, pas comme des faits garantis.

## Cadrage avant intégration
Pour chaque cas envisagé, documenter :
1. Problème utilisateur et objectif.
2. Acteur principal et acteurs secondaires/systèmes externes.
3. Déclencheur et préconditions.
4. Données d'entrée et leur provenance.
5. Traitement IA et données éventuellement transmises.
6. Résultat attendu et action de l'utilisateur.
7. Scénario nominal.
8. Scénarios alternatifs, erreurs et indisponibilité.
9. Permissions, confidentialité et conservation.
10. Coût estimatif, limites d'usage et solution de repli.
11. Critères d'acceptation et tests.

## Rapport IA — section UML obligatoire
En plus du rapport standard, fournir une section « Cas d'utilisation et acteurs pour le diagramme UML » contenant :
- Liste des acteurs humains (ex. étudiant) et acteurs externes (ex. fournisseur IA), uniquement s'ils interviennent réellement.
- Pour chaque cas d'utilisation : identifiant, nom, acteur principal, acteurs secondaires, objectif, préconditions, déclencheur, scénario nominal, extensions/erreurs, postconditions.
- Relations `include` et `extend` proposées, avec justification ; ne pas les imposer si elles ne sont pas nécessaires.
- Frontière du système : ce qui relève de StageLink et ce qui relève du fournisseur IA.
- Données utilisées/transmises et consentement ou information requis.
- Cas non retenus et questions métier en attente.
- Une proposition textuelle structurée que la propriétaire pourra convertir en diagramme UML.

Ne jamais présenter une proposition UML comme une règle métier approuvée. La propriétaire valide les acteurs, les cas d'utilisation et les relations avant qu'ils soient considérés comme définitifs.


# StageLink — Instructions permanentes pour Codex

## 1. Autorité et décisions métier
- La propriétaire du projet conserve la décision finale.
- Ne jamais créer, modifier, supprimer ou interpréter une règle métier sans validation explicite de la propriétaire.
- Lorsqu'une décision métier manque ou qu'une exigence est ambiguë, arrêter uniquement la partie concernée, exposer le problème et poser une question précise. Ne pas choisir silencieusement une option.
- Les propositions techniques sont autorisées, mais doivent être distinguées des décisions métier.
- Les avis concernent exclusivement l'expérience de la plateforme StageLink. Ils ne portent ni sur les entreprises, ni sur les recruteurs, ni sur les stages.

## 2. Première action obligatoire
Avant toute modification :
1. Lire ce fichier et le Skill pertinent.
2. Lire les instructions locales du dépôt.
3. Examiner la branche, `git status`, les différences locales et les processus de travail en cours.
4. Identifier les fichiers concernés et lire leur implémentation actuelle, tests et migrations.
5. Résumer le périmètre et les risques avant une modification importante.
6. Ne jamais supposer qu'une fonctionnalité décrite dans la documentation est effectivement implémentée.

## 3. Architecture et technologies
- Respecter l'architecture Django existante et les responsabilités des applications.
- StageLink utilise Django avec des templates rendus côté serveur (SSR).
- Ne pas transformer le projet en API REST et ne pas ajouter Django REST Framework ou de nouvelles routes API sans autorisation explicite. Signaler les éléments DRF préexistants au lieu de les étendre.
- Ne pas créer une application Django si une application existante peut raisonnablement porter la fonctionnalité.
- Séparer proprement modèles, vues, services, tâches Celery, adaptateurs, templates et JavaScript.
- Ne pas ajouter de signal, middleware, dépendance ou abstraction sans justification concrète.

## 4. Qualité, performance et internationalisation
- Respecter PEP 8 et les conventions du dépôt ; utiliser Ruff si déjà configuré ou validé.
- Prévenir les requêtes N+1 avec `select_related`, `prefetch_related` et des requêtes ciblées lorsque pertinent.
- Éviter les lectures, écritures, appels réseau, tâches asynchrones et calculs inutiles.
- Ajouter des index uniquement sur justification mesurable ou fonctionnelle.
- Internationaliser les textes avec les mécanismes Django (`gettext`, `gettext_lazy`, blocs de traduction des templates) et préserver le français et l'anglais (`fr`, `en`).
- Ne pas coder en dur des textes visibles destinés à l'utilisateur sans vérifier les conventions de traduction du projet.
- Écrire ou adapter des tests pertinents ; ne pas prétendre qu'un test a réussi s'il n'a pas été exécuté.

## 5. Sécurité et données
- Les permissions sont toujours vérifiées côté serveur.
- Ne jamais faire confiance aux champs, paramètres, fichiers ou statuts fournis par le navigateur.
- Ne jamais afficher, copier ou journaliser les secrets de `.env`.
- Ne jamais inclure de clés, tokens, données personnelles ou CV réels dans les prompts, rapports, commits ou captures.
- Contrôler les fichiers téléversés, les redirections et les URLs externes.
- Utiliser des transactions et protections contre la concurrence pour les opérations critiques.
- Préserver les historiques et la traçabilité métier.
- Pour les paiements, seule une confirmation serveur vérifiée du prestataire peut valider une transaction.

## 6. Page d'accueil et aperçu des offres
- L'aperçu public des offres doit inciter à créer un compte ou à se connecter.
- Les visiteurs non authentifiés ne doivent voir qu'un aperçu volontairement limité : quelques informations non sensibles et validées pour l'affichage public.
- Les informations utiles à la candidature ou permettant de contourner le parcours d'inscription doivent être réservées aux utilisateurs autorisés, selon les règles confirmées par la propriétaire.
- IMPORTANT : un floutage CSS ou un voile visuel n'est jamais une protection d'accès. Les données masquées ne doivent pas être envoyées au navigateur (HTML, attributs, JSON, scripts, données structurées, source de page).
- Construire la réponse serveur avec une liste blanche de champs publics. Ne pas sérialiser l'objet complet puis le masquer côté frontend.
- Les visiteurs doivent être invités clairement à s'inscrire ou se connecter pour accéder aux détails et au parcours de candidature.
- Avant de décider quels champs sont visibles, demander validation à la propriétaire si la liste n'a pas été explicitement définie.
- Tester qu'un visiteur anonyme ne peut pas retrouver les champs restreints dans le HTML, le DOM, les réponses réseau ou les URLs.

### Règles métier confirmées pour les aperçus publics
- Les mêmes restrictions s'appliquent aux offres publiées directement par les entreprises sur StageLink et aux offres externes relayées.
- Ne jamais afficher le nom de l'entreprise dans l'aperçu public.
- Ne jamais exposer aux visiteurs anonymes les coordonnées, contacts, liens vers l'annonce originale, liens de candidature externes ou toute information permettant de contourner StageLink.
- Le clic sur une carte ou sur l'action d'ouverture d'une offre doit conduire à une invitation à créer un compte gratuit ou à se connecter avant l'accès au détail.
- Après authentification, le serveur doit réévaluer les droits avant de fournir le détail. Préserver une redirection de retour vers l'offre uniquement si elle est locale, sûre et autorisée.
- Le titre réel d'une offre peut lui-même permettre de retrouver l'annonce ailleurs. Ne pas décider seul de le publier : demander confirmation. À défaut de décision explicite, utiliser uniquement un aperçu générique construit à partir de champs publics approuvés.
- Ces règles sont des exigences de confidentialité et de parcours ; elles ne doivent pas être remplacées par un simple floutage CSS, un overlay ou du JavaScript.

## 7. Git, branches et Pull Requests
- Chaque journée ou mission possède une branche dédiée, créée depuis la branche de référence convenue.
- Ne jamais travailler directement sur `main`.
- Ne jamais changer de branche avec des modifications locales non comprises.
- Ne jamais écraser, réinitialiser, supprimer ou intégrer des modifications préexistantes.
- `output.css` contient une modification locale préexistante à préserver absolument : ne pas l'écraser, le régénérer, le restaurer, le supprimer ou l'inclure accidentellement dans un commit.
- À la fin de chaque mission, préparer une Pull Request vers la branche cible convenue, avec résumé, tests, risques et points en attente.
- Ne jamais fusionner une Pull Request, supprimer une branche distante ou pousser des changements sans autorisation explicite.
- Si la PR du Jour 5 existe déjà, vérifier son état avant d'en créer une autre.

## 8. Coût et usage des outils IA
- Réduire les appels redondants à Codex, aux fournisseurs IA, aux APIs et aux outils externes.
- Inspecter les fichiers ciblés plutôt que relire systématiquement tout le dépôt.
- Regrouper les modifications cohérentes et exécuter les tests au niveau approprié.
- Ne pas ajouter de fournisseur IA, de modèle payant ou de dépendance sans validation.
- Pour toute fonction IA, définir les données minimales nécessaires, les coûts estimés, les limites, les erreurs et une solution de repli.
- L'IA doit rester facultative : une panne de fournisseur ne doit pas bloquer les fonctions essentielles de StageLink.

## 9. Rapport obligatoire en fin de mission
Utiliser `docs/rapport-mission-template.md` si présent. Le rapport doit présenter :
- périmètre, branche, PR et statut ;
- travaux et fichiers modifiés ;
- tests réellement exécutés et résultats ;
- problèmes rencontrés, causes établies ou hypothèses, solutions appliquées ;
- décisions métier validées et questions en attente ;
- risques et anomalies restantes ;
- recommandations et prochaine étape ;
- état Git et confirmation que `output.css` a été préservé.
Pour une mission d'intégration IA, ajouter obligatoirement les cas d'utilisation, acteurs, interactions, préconditions, scénarios nominaux/alternatifs et limites, afin d'aider la propriétaire à compléter le diagramme de cas d'utilisation UML.

## 10. État honnête
Ne jamais déclarer une tâche terminée sur la seule base du code écrit. Distinguer clairement : implémenté, testé, validé, non vérifié, bloqué et recommandé.

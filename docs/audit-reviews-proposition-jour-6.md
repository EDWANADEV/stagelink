# Audit fonctionnel et proposition UX — Reviews StageLink

## Conclusion exécutive

Le dépôt contient un modèle et un service métier d'avis, ainsi qu'une administration en lecture seule. Il ne contient aucune route publique Reviews, aucun formulaire, aucune vue d'interface, aucun template public, aucune pagination et aucun parcours relié à la navigation. Il n'est donc pas possible de consulter ou déposer un avis dans l'application Web actuelle. La création d'une interface est bloquée par des règles produit non définies ; ce document propose un parcours, sans l'activer.

**Portée métier confirmée :** chaque avis concerne uniquement l'expérience de la plateforme StageLink. Il ne concerne ni une entreprise, ni un recruteur, ni une offre, ni une expérience professionnelle.

## État fonctionnel observé

| Capacité | Présente | Détail constaté |
|---|---:|---|
| Enregistrement d'un avis | Oui, service uniquement | `ReviewService.create_review` crée note/commentaire, lie l'avis à l'utilisateur et remplit la traçabilité `created_by`/`updated_by`. |
| Note | Oui | `PositiveSmallIntegerField`, validateurs réglés par `REVIEW_MIN_RATING` et `REVIEW_MAX_RATING` (1–5 par défaut). `full_clean()` est appelé au service. |
| Commentaire | Oui | Texte libre, facultatif, sans limite applicative de longueur constatée ni validation éditoriale supplémentaire. |
| Un avis actif | Oui, limite fixe | Le service interdit un deuxième avis actif par compte ; le soft delete permet ensuite d'en créer un nouveau. Le verrou de ligne utilisateur sérialise désormais les créations concurrentes. |
| Modification/suppression | Oui, service uniquement | Le service vérifie que l'utilisateur est connecté et propriétaire ; suppression logique via `BaseModel.soft_delete`. Aucun endpoint ne l'expose. |
| Consultation | Non, sauf admin | Pas de lecture publique ou personnelle par vue. |
| Modération/réponse | Non | L'admin est lecture seule ; pas d'état de modération ni d'outil de réponse. Aucun statut de publication à inventer. |
| URLs, formulaire, templates | Non | `reviews/views.py` ne contient que le stub initial ; aucune `reviews/urls.py`, aucun `forms.py`, aucun template Reviews et aucune entrée de navigation. |
| Traductions | Partielle | Les libellés et erreurs Python utilisent `gettext_lazy`. Les chaînes Reviews n'ont pas encore de catalogue public d'interface ; elles seront nécessaires si un parcours est approuvé. |
| Tests | Partiels, service seulement | Création, modification, limites note, ownership, soft delete, limite active et concurrence PostgreSQL sont couverts. Aucun test de vue/formulaire/route, pagination, rendu, abuse rate, accessibilité ou traduction d'interface car ces couches n'existent pas. |

## Modèle, permissions et technique

`Review` hérite de `BaseModel` : UUID, dates, créateurs/modificateurs et `is_deleted`. Il n'a que `user`, `rating`, `comment`. Il n'a aucune FK vers `InternshipOffer`, `Application`, entreprise ou recruteur, conforme au périmètre StageLink. La FK utilisateur utilise `CASCADE`; la suppression d'un compte supprime donc ses avis, comportement existant non modifié.

Le manager par défaut filtre les objets supprimés ; `all_objects` permet les accès comprenant les avis supprimés. Les services appellent `full_clean()` avant l'écriture et la suppression reste logique. La permission d'admin `require_review_admin` existe mais aucun endpoint l'utilise ; l'administration Django se base sur les permissions Django habituelles. `ReviewAdmin` interdit ajout/suppression et rend les champs en lecture seule, tout en sélectionnant l'utilisateur pour éviter un N+1 dans la liste.

La concurrence de création est protégée en verrouillant l'utilisateur avant le test d'avis actif. Aucune contrainte DB unique ne lie directement `Review.user`, car les suppressions logiques doivent permettre une nouvelle entrée et la limite est exprimée au niveau service. Les updates/deletes ne sont pas exposés publiquement ; avant leur exposition, il faudra charger la ligne cible avec verrou et refaire l'autorisation sur la version DB courante afin de couvrir une course entre modification/suppression.

L'ordre est `-created_at`. Les colonnes UUID, FK user, dates et `is_deleted` sont indexées par le modèle de base/la FK ; aucun index supplémentaire n'est justifié tant qu'une requête publique et un profil volumétrique ne sont pas définis. Pour une future liste paginée : queryset `Review.objects.select_related("user")`, champs projetés au strict nécessaire, pagination Django ; confirmer d'abord quels champs d'auteur/commentaire peuvent être publics. La recherche admin dans le commentaire peut coûter cher en croissance (recherche LIKE non indexée) ; mesurer avant d'ajouter un index spécialisé.

## Incohérence `REVIEW_MAX_PER_USER`

`config/settings/base.py` définit `REVIEW_MAX_PER_USER` (1 par défaut), mais `ReviewService.create_review` ne le lit pas : il interdit dès qu'un avis actif existe. Mettre la variable à 2, 0 ou une autre valeur n'a donc aucun effet ; la règle appliquée est strictement une entrée active. Ce rapport ne change ni le paramètre ni le service. Décision requise : la limite doit-elle rester toujours 1 (auquel cas le paramètre est inutile), ou la limite configurable doit-elle devenir la règle appliquée ? Le sens d'une valeur 0 doit aussi être défini avant codage.

## Parcours UX proposé — à valider

Proposition d'interface SSR sans dépendance REST :

1. Lien « Donner mon avis sur StageLink » vers une page qui explique explicitement que l'avis concerne uniquement la plateforme.
2. Liste paginée des avis publiés (si la règle de publication est décidée), note agrégée seulement si approuvée, commentaire et date. Ne pas exposer email, nom complet ou profil utilisateur sans accord explicite ; option par défaut proposée : auteur anonyme ou pseudonyme non identifiant.
3. Formulaire de note et commentaire, avec libellé/descriptions accessibles, exemples de longueur et erreur traduite. Ne pas ajouter des critères de notation.
4. Après validation, confirmation honnête de l'enregistrement ou indication « en attente » uniquement si la propriétaire décide d'une modération préalable.
5. Espace « Mon avis » pour modifier/supprimer son propre avis, avec confirmation avant suppression logique.
6. Utilisateurs non authentifiés : invitation à se connecter ; la destination et l'éligibilité après connexion sont à confirmer.

Ce parcours n'est pas créé, car l'authentification requise par le service ne répond pas aux questions d'éligibilité, visibilité, modération, consentement de publication et limite. Le texte d'un commentaire peut révéler des informations personnelles : avertissement et politique de modération/abus sont également à décider.

### Ébauche de mise en page (sans règles implicites)

```text
[Avis sur StageLink]
  Explication : cet espace évalue la plateforme, pas une entreprise ou une offre.
  [Synthèse note moyenne]            <- uniquement si autorisée
  [Action Donner mon avis]           <- visible selon éligibilité à décider

  [Mon avis / action Modifier]       <- uniquement avis de l'utilisateur courant
  [Action Supprimer]                 <- confirmation avant suppression logique

  [Liste des avis publiables]        <- visibilité/modération/auteur à décider
  [Carte : note textuelle, date, commentaire, auteur selon décision]
  [Pagination]
  [État vide / erreur / indisponibilité]
```

Sur mobile, la synthèse et les cartes passent en colonne ; les notes doivent être présentées textuellement (« 4 sur 5 ») et pas seulement avec des étoiles/couleurs. Les champs portent des labels persistants ; les erreurs sont liées aux champs et annoncées ; les actions ont des zones tactiles suffisantes. L'identité de l'auteur, la synthèse et la liste ne sont que des emplacements conditionnels, pas une décision de publication.

## Décisions métier à obtenir avant interface

1. Quels utilisateurs peuvent déposer : tout compte authentifié, étudiants uniquement, ou autre ? Le service actuel accepte tout utilisateur authentifié.
2. À quel moment / sous quelle condition peut-on déposer ? Aucun lien ni précondition d'éligibilité n'existe.
3. Limite d'avis actifs par compte et comportement de `REVIEW_MAX_PER_USER` (voir ci-dessus).
4. Publication immédiate ou modération préalable ? Qui modère et selon quels motifs ?
5. Les avis sont-ils publics, visibles aux seuls utilisateurs connectés, ou privés à l'auteur/admin ?
6. Quel attribut d'auteur afficher : aucun, pseudonyme, prénom ou autre ?
7. Suppression d'avis : définitive/logique (le code actuel conserve l'historique) et traitement des avis supprimés dans l'admin.
8. Des réponses de StageLink sont-elles permises, par quel rôle et visibles par qui ?
9. Faut-il un champ commentaire obligatoire, taille maximale, signalement ou limitation de fréquence ? Ces règles n'existent pas dans le service actuel.

## Scénarios de tests nécessaires si le parcours est approuvé

- Contrôle de chaque rôle/état connecté, CSRF et accès d'un utilisateur à l'avis d'un autre.
- Validation serveur note/commentaire, limite de longueur si approuvée, traduction FR/EN.
- Concurrence des créations ; modification contre suppression concurrentes ; avis supprimé non exposé en public.
- Visibilité conforme à la décision de publication et aucune fuite de données utilisateur.
- Pagination première/dernière page, page hors plage, ordre stable avec dates identiques.
- Requêtes ORM sans N+1 avec volumétrie représentative et absence de sur-fetch.
- Accessibilité clavier, labels, erreurs, messages de succès, responsive mobile.
- Protections anti-abus seulement après seuils définis (rate limit, signalement, modération).

## Fichiers existants concernés

`stagelink/reviews/models.py`, `services.py`, `permissions.py`, `admin.py`, `migrations/0001_initial.py`, `tests.py`, et paramètres `REVIEW_MIN_RATING`, `REVIEW_MAX_RATING`, `REVIEW_MAX_PER_USER` de `config/settings/base.py`. Aucun changement à la règle configurable n'est inclus.

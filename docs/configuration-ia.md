# Configuration de l'assistance IA StageLink

## Fournisseur et architecture

StageLink utilise OpenAI comme fournisseur principal, à la demande de la propriétaire. L'adaptateur appelle l'API Responses par HTTPS avec `requests`, déjà présente dans les dépendances. Le modèle par défaut est `gpt-6.2-sol`; le nom est configurable. Les vues SSR appellent les services UC-A à UC-E, qui passent par un adaptateur remplaçable. UC-F reste un calcul local explicable. UC-G n'est pas implémenté.

La requête Responses fixe `store: false`, n'active aucun outil et ne transmet que les champs nécessaires au cas d'usage. La plateforme indique qu'elle ne s'entraîne pas sur les données API par défaut; les journaux de surveillance peuvent néanmoins contenir du contenu et être conservés jusqu'à 30 jours selon les contrôles du compte. Consultez les [contrôles de données de l'API](https://developers.openai.com/api/docs/guides/your-data) avant l'activation et vérifiez les réglages de conservation de votre projet.

## Dépendances

Aucune nouvelle dépendance n'a été ajoutée. L'adaptateur utilise `requests`, qui est déjà déclaré dans `pyproject.toml`. L'appel réseau est synchrone, borné par timeout et sans reprise automatique.

## Variables d'environnement

Le fichier versionné `.env.example` contient les variables IA avec une fausse clé. `.env` est ignoré par Git. En développement, StageLink lit `.env` à la racine du dépôt tant que `DJANGO_READ_DOT_ENV_FILE` reste à `True` (valeur par défaut).

| Variable | Valeur par défaut | Rôle |
| --- | --- | --- |
| `OPENAI_API_KEY` | vide | Clé secrète serveur OpenAI; son absence désactive l'adaptateur. |
| `AI_OPENAI_MODEL` | `gpt-6.2-sol` | Modèle choisi dans le compte API. |
| `AI_PROVIDER_ADAPTER` | `stagelink.ai_assistant.openai_adapter.OpenAIAdapter` | Chemin Python de l'adaptateur; prévu pour permettre une substitution ultérieure. |
| `AI_EXTERNAL_PROCESSING_APPROVED` | `False` | Interrupteur d'activation côté propriétaire. Doit être explicitement activé après vérification des réglages de compte et de confidentialité. |
| `AI_REQUEST_TIMEOUT_SECONDS` | `12` | Timeout HTTP par appel. |
| `AI_MAX_INPUT_CHARACTERS` | `8000` | Taille maximale du JSON minimisé transmis. |
| `AI_MAX_OUTPUT_TOKENS` | `1800` | Plafond de génération, également borne supérieure appliquée par le service. |
| `AI_USER_COOLDOWN_SECONDS` | `15` | Délai minimal par compte; la clé de cache bloque aussi les appels simultanés durant le timeout. |
| `AI_MAX_DAILY_REQUESTS` | `100` | Plafond global journalier de demandes acceptées par le cache partagé. |
| `AI_MAX_DAILY_REQUESTS_PER_USER` | `20` | Plafond journalier par compte. |

Les limites sont volontairement conservatrices et peuvent être diminuées par l'environnement. En production, le cache Redis déjà configuré est requis pour partager les verrous et quotas entre workers. Si le cache n'est pas disponible, les nouvelles demandes IA échouent de façon fermée.

## Configuration en développement

1. Si `.env` n'existe pas, copiez `.env.example` vers `.env`. S'il existe déjà, **ne le remplacez pas** : ajoutez seulement les lignes IA manquantes.
2. Remplacez `OPENAI_API_KEY` par la clé créée dans le projet API OpenAI. Gardez-la côté serveur.
3. Vérifiez le modèle disponible pour votre projet et ajustez `AI_OPENAI_MODEL` si nécessaire.
4. Après avoir vérifié les paramètres de traitement et de conservation du projet OpenAI, mettez `AI_EXTERNAL_PROCESSING_APPROVED=True`. La valeur par défaut reste désactivée.
5. Démarrez StageLink selon le parcours habituel, par exemple `uv run python manage.py runserver`.
6. Chaque demande externe exige aussi une case de consentement dans l'interface. Sans clé, interrupteur ou case cochée, aucun appel n'est fait.

Pour contrôler la configuration locale sans afficher la clé :

```sh
uv run python manage.py shell -c 'from stagelink.ai_assistant.providers import is_ai_configured; print("Fournisseur IA prêt" if is_ai_configured() else "IA inactive : configuration absente ou traitement externe non approuvé")'
```

Cette commande vérifie localement la présence d'une clé non vide/non fictive, l'adaptateur et l'interrupteur sans afficher la clé. Elle ne teste pas l'accès réseau, la disponibilité du modèle ni la facturation. Pour vérifier ces éléments, une demande réelle depuis l'interface avec un texte fictif court et le consentement activé sera facturée selon le tarif du compte.

## Configuration en production

Renseignez les mêmes variables dans le gestionnaire de secrets ou l'environnement du service Django. N'ajoutez pas la clé à une image, un dépôt, une valeur de build, un template ou un bundle frontend. Définissez `DJANGO_READ_DOT_ENV_FILE=False` et injectez les secrets au démarrage. Activez `AI_EXTERNAL_PROCESSING_APPROVED=True` seulement après validation de la politique de confidentialité, des paramètres de conservation et de la limite de dépenses du projet OpenAI.

La base et Redis doivent être configurés comme pour le reste de StageLink. Ne lancez pas la fonctionnalité tant que le cache partagé n'est pas disponible : il protège les limites d'appels entre processus. Une indisponibilité OpenAI, un timeout, une réponse invalide ou une erreur d'authentification affiche un message générique; l'application continue sans l'assistance IA.

## Données et sécurité

- Les étudiants voient l'information sur le transfert puis cochent explicitement la case avant UC-A, UC-B, UC-C ou UC-D. Les représentants d'entreprise font de même avant UC-E.
- UC-A transmet le brouillon choisi et quelques champs de l'offre; ni CV, coordonnées, email, profil complet, ni historique de candidatures.
- UC-B transmet les champs utiles de l'offre et la question posée; UC-C ajoute seulement la réponse de la session en cours. L'état d'entretien est borné à six tours et reste dans la session StageLink.
- UC-D transmet la présentation personnelle, domaine d'étude, niveau et compétences saisis; jamais le CV. La suggestion ne sauvegarde rien avant action normale de l'étudiant.
- UC-E transmet uniquement titre, description et compétences de l'offre; salaire, lieu, conditions et données de candidature sont exclus.
- UC-F utilise les filtres ORM/matching local et n'appelle pas OpenAI.
- UC-G demeure en attente; aucun CV ni dossier de candidature n'est envoyé.
- Les suggestions sont affichées comme texte échappé par les templates Django. Elles ne sont ni conservées ni appliquées automatiquement.
- Les journaux locaux ne contiennent pas les prompts, réponses ou clés; ils enregistrent le cas d'usage, l'adaptateur, la durée et les compteurs de tokens retournés par l'API.

## Erreurs et maîtrise des coûts

Un appel unique est fait par action, sans retry. Le timeout est de 12 secondes par défaut; les demandes dépassant 8 000 caractères de faits sont refusées. Les réponses dépassant 16 000 caractères ou sans texte exploitable sont rejetées. Le cache bloque une demande simultanée par compte et applique les plafonds journaliers global et par utilisateur.

À titre d'ordre de grandeur uniquement, au tarif actuellement publié de `$2 / 1M` tokens d'entrée et `$10 / 1M` tokens de sortie pour `gpt-6.2-sol`, 5 000 tokens d'entrée et 1 800 de sortie coûteraient environ `$0.028` par requête, ou `$2.80` pour 100 requêtes au maximum. La tokenisation réelle, le modèle sélectionné et les tarifs changent le total; le plafond d'appels n'est pas un budget monétaire garanti. Suivez la consommation dans le tableau de bord OpenAI et baissez les plafonds si nécessaire. [Tarifs officiels](https://developers.openai.com/api/docs/pricing).

## Tests et état de vérification

Les tests du dépôt utilisent des adaptateurs simulés et des réponses HTTP simulées; ils ne requièrent aucune clé réelle et ne facturent aucun appel. Aucun appel OpenAI réel n'est lancé pendant les tests. L'activation de production nécessite encore une vérification manuelle depuis l'interface après configuration par la propriétaire.

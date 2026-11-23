# Audit du parcours de donation et de paiement — Jour 6

## Périmètre observé

Les pages sont rendues avec Django. L'entrée est exposée dans la navigation et le tableau de bord. La page de donation est publique ; l'authentification n'est pas requise. La configuration serveur détermine les prestataires affichés. Les états de paiement proviennent des modèles `Donation` et `Payment` et du traitement prestataire côté serveur. Ce document n'affirme pas qu'un parcours de production a été validé.

## Parcours, état réel et expérience utilisateur

| Étape | Ce que voit / peut faire l'utilisateur | Traitement actuel | Écart ou risque observé |
|---|---|---|---|
| Découvrir les dons | Entrée « Faire un don », page expliquant le soutien à StageLink | `DonationPageView`, page SSR | La page ne donne pas d'information sur les frais, reçus fiscaux ou politique de remboursement. Ces sujets sont des décisions produit et ne sont pas ajoutés ici. |
| Choisir un montant | Presets 1 000, 5 000, 10 000 XAF ou saisie libre | Formulaire client et `DonationForm` serveur ; entier positif, maximum accepté 9 999 999 999 XAF | Validation côté serveur présente. Les presets sont accessibles comme boutons. Le récapitulatif se met à jour côté client. |
| Choisir un prestataire/moyen | Carte Stripe, carte Flutterwave, Mobile Money Flutterwave selon configuration | Les options sont rendues depuis `get_available_payment_methods`; les coordonnées email/téléphone/réseau apparaissent selon la sélection | L'email prérempli pour un utilisateur connecté peut être édité ; choix Mobile Money MTN/Orange fixé dans l'UI. Ne pas ajouter de réseaux sans validation opérationnelle. |
| Valider | Le navigateur valide les champs requis ; message récapitulatif ; bouton d'envoi | Le JS envoie un POST same-origin avec CSRF et clé d'idempotence ; serveur revalide le montant et le choix fournisseur/service | L'action et le message ne prétendent pas confirmer un don. Les erreurs d'initialisation sont présentées ; les messages serveur sont maintenant traduits. |
| Créer le paiement | Indication de connexion au prestataire et bouton bloqué | Le serveur crée/réutilise un paiement selon sa clé d'idempotence puis appelle le prestataire | Les contrôles sont maintenant désactivés pendant la requête, évitant une discordance d'option affichée et de requête en vol. La logique actuelle appelle encore le réseau dans la transaction HTTP configurée (`ATOMIC_REQUESTS`) : enjeu de durée transactionnelle à traiter séparément dans le chantier paiement. |
| Ouvrir Checkout | Redirection externe HTTPS si URL renvoyée acceptable côté navigateur | Stripe est limité à `checkout.stripe.com`; Flutterwave est vérifié HTTPS côté navigateur | Le domaine Flutterwave n'est pas allowlisté côté navigateur. La réponse provient du serveur fournisseur par TLS ; une liste d'hôtes doit être confirmée sur les domaines réels officiellement utilisés avant de la durcir. |
| Retour | Page de statut, montant, lien pour un autre don | La vue ne modifie jamais le paiement en fonction de paramètres navigateur ; elle lit `Payment.status` | UUID aléatoire sert de jeton d'accès de fait, notamment pour les dons anonymes. La page complète expose le montant au détenteur du lien ; ne pas partager le lien. Aucun email ou nom de donateur n'est affiché. |
| Attente / retard du webhook | État pending puis vérification bornée | Fragment SSR `GET`, `no-store`, sélection DB `id,status`, 10 tentatives espacées de 5 secondes, abort réseau à 6 secondes ; bouton de relance après épuisement | Les vérifications automatiques cessent après environ 50 secondes. L'utilisateur peut demander une nouvelle série. Pas de polling illimité ni de rechargement complet. |
| Confirmation / échec / annulation | Statut serveur traduit et annoncé aux technologies d'assistance | Les états `success`, `failed`, `cancelled` sont lus depuis DB. Un retour `cancelled=1` ne modifie rien et affiche un message neutre d'interruption | Une annulation navigateur peut laisser le paiement en pending jusqu'à l'événement serveur. Le message précise que le retour n'est ni une confirmation ni une annulation métier. |
| Remboursement | État dédié | Les états `refunded` et `partially_refunded` existants sont présentés séparément | Corrige l'ancienne présentation qui assimilait ces états à « paiement confirmé ». Aucun remboursement ni transition métier n'est exécuté. |
| Fournisseur indisponible / erreur réseau | Message générique, formulaire réactivé et données à nouveau éditables | Erreur serveur traduite ; erreurs de transport ou réponse JSON invalide ramenées au message générique | La nouvelle tentative garde la même clé pendant que les champs soumis restent inchangés : utile quand le résultat réseau est incertain. La politique d'une nouvelle tentative après modification des données doit rester cohérente avec l'idempotence existante. |

## Sécurité et confidentialité du statut

- La route dédiée est GET, marquée `never_cache`, utilise un convertisseur UUID, lit uniquement `id` et `status`, et renvoie un fragment HTML limité à l'état. Elle ne renvoie pas le montant, le donateur, les coordonnées, le payload prestataire ou une réponse JSON.
- L'identifiant UUID reste un secret de lien (capability). L'accès anonyme à la page complète existe déjà et est nécessaire au parcours de don anonyme. Les liens ne doivent pas être réutilisés comme preuve ni publiés ; HTTPS et une politique de Referer restrictive en déploiement sont à vérifier.
- Une personne connaissant le UUID peut consulter le montant sur la page de retour existante, pas sur le fragment de statut. Cette propriété découle du parcours actuel ; rendre le retour authentifié ou masquer le montant serait une décision produit et n'a pas été changé.
- Aucune limitation de débit applicative de la route de statut n'est définie. Le polling navigateur est borné ; si une observation de trafic justifie un rate limit serveur, choisir seuils/proxy après mesure.

## Améliorations apportées dans cette reprise

- Les remboursements total et partiel ont un libellé et une explication distincts.
- Le paramètre de retour `cancelled=1` déclenche uniquement un message de contexte ; il ne change pas l'état consulté en DB.
- Après la série automatique, le bouton « Vérifier à nouveau » permet à l'utilisateur d'initier une autre série bornée.
- Pendant la création du paiement, les champs sont verrouillés et le formulaire porte `aria-busy`; les erreurs de transport ne révèlent plus le message brut du navigateur.
- Les nouveaux textes visibles de paiement sont traduits en anglais dans le catalogue existant. Les erreurs HTTP de validation critiques emploient gettext.

## Tests à exécuter / couverture attendue

Tests couvrent les statuts persistés (dont remboursements), le paramètre de retour non autoritatif, l'absence de fuite montant/don dans le fragment, l'UUID inconnu/malformé et l'actualisation bornée sans rechargement. Ajouter/maintenir test manuel navigateur sur mobile pour le clavier numérique, sélection de moyen, double clic, timeout, récupération réseau, relance manuelle et navigation Checkout annulée. Les tests Django ne simulent pas le comportement JavaScript réel ni les domaines de redirection de production.

## Décisions produit à demander

1. Souhaitez-vous afficher le montant sur la page anonyme qui sert de retour ? Aujourd'hui il est accessible au détenteur de l'UUID.
2. Quelle politique de reçus, frais, dons récurrents et information de remboursement doit apparaître ? Aucun comportement de ce type n'est ajouté.
3. Quels domaines Flutterwave précis doivent être autorisés pour la redirection ? Confirmer depuis l'environnement fournisseur avant allowlist.
4. Faut-il un canal d'information après 50 secondes (email, support, etc.) ? La mission n'en invente pas.

## Fichiers concernés

`stagelink/donation/templates/donation/donate.html`, `stagelink/static/js/donation.js`, `stagelink/payments/views.py`, les templates de retour, `stagelink/payments/tests.py`, `stagelink/donation/tests.py` et `locale/en_US/LC_MESSAGES/django.po`.

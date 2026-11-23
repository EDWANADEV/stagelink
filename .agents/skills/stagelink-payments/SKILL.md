---
name: stagelink-payments
description: Diagnostic et développement sécurisé des dons et paiements StageLink avec Stripe, Flutterwave, webhooks, PostgreSQL et Celery.
---

# Skill — Paiements StageLink

## Règles non négociables
- Ne jamais considérer la redirection navigateur comme une preuve de paiement.
- Vérifier signature webhook, référence, montant, devise, statut et transaction auprès du prestataire selon l'intégration existante.
- Protéger l'idempotence et les traitements en double.
- Préserver la cohérence Donation/Payment et l'historique des événements.
- Ne jamais journaliser les secrets, données de carte ou payloads sensibles.
- Ne jamais effectuer de paiement réel sans autorisation explicite ; privilégier sandbox.
- Ne jamais modifier les clés ou la configuration secrète.

## Diagnostic
Vérifier séparément : création Checkout, réponse HTTP, identifiant de requête prestataire, réception webhook, réponse HTTP webhook, persistance PostgreSQL, publication Celery, worker, Beat si le mécanisme périodique est utilisé, vérification prestataire et mise à jour métier.

Ne pas attribuer une cause au 502 sans preuve provenant des logs non secrets et identifiants de requête. Distinguer timeout simulé et incident réel.

## Modifications
- Lire les adaptateurs, services, modèles, tâches, vues, webhooks et tests concernés.
- Préserver les événements persistants et la reprise des événements échoués.
- Vérifier le comportement si `.delay()` échoue après commit et le rôle réel de Beat.
- Ne pas changer le traitement des devises ou l'arrondi sans validation et preuve du contrat prestataire.
- Tester les cas de doublon, mauvais montant/devise/référence, signature invalide, timeout, événement tardif et reprise.

## Livraison
Rapporter la chaîne complète vérifiée et les maillons non vérifiés. Un paiement sandbox n'est validé que si les preuves de bout en bout sont disponibles.

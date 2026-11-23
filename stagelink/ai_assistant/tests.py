import hashlib
from datetime import timedelta
from http import HTTPStatus

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from stagelink.ai_assistant.openai_adapter import OpenAIAdapter
from stagelink.ai_assistant.providers import MAX_OUTPUT_TOKENS
from stagelink.ai_assistant.providers import AIRateLimitedError
from stagelink.ai_assistant.providers import AIUnavailableError
from stagelink.ai_assistant.providers import generate_suggestion
from stagelink.ai_assistant.providers import is_ai_configured
from stagelink.application.models import Application
from stagelink.offers.matching import offer_match_reasons
from stagelink.offers.models import InternshipOffer
from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import OfferStatus
from stagelink.utils.enums import Role

pytestmark = pytest.mark.django_db
INTERVIEW_FEEDBACK = (
    "FEEDBACK: Réponse claire. NEXT QUESTION: "
    "Comment organiseriez-vous le travail ?"
)
OFFER_SUGGESTION_JSON = (
    '{"title":"Stage développeur web","description":"Créer le site.",'
    '"required_skills":["Python"]}'
)
PRIVATE_TIMEOUT_MESSAGE = "private request details"


class FakeAIProvider:
    responses = ["Suggestion vérifiable."]
    calls = []

    def generate(self, *, system_prompt, user_prompt, timeout, max_output_tokens):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "timeout": timeout,
                "max_output_tokens": max_output_tokens,
            },
        )
        return {"text": self.responses.pop(0), "input_tokens": 10, "output_tokens": 5}


class TimeoutAIProvider:
    def generate(self, **kwargs):
        raise TimeoutError(PRIVATE_TIMEOUT_MESSAGE)


@pytest.fixture(autouse=True)
def reset_ai_fake():
    cache.clear()
    FakeAIProvider.calls = []
    FakeAIProvider.responses = ["Suggestion vérifiable."]


@pytest.fixture
def student_and_offer():
    student_user = UserFactory(
        role=Role.STUDENT,
        email_verified=True,
        name="Étudiante Exemple",
    )
    student = StudentProfile.objects.create(
        user=student_user,
        field_of_study="Informatique",
        level="Licence 3",
        skills=["Python", "Excel"],
    )
    company_user = UserFactory(role=Role.COMPANY, email_verified=True)
    company = CompanyProfile.objects.create(
        user=company_user,
        company_name="Entreprise exemple",
        address="Douala",
    )
    offer = InternshipOffer.objects.create(
        company=company,
        created_by=company_user,
        title="Stage développement",
        description="Maintenir un site web existant.",
        domain="Informatique",
        required_skills=["Python"],
        education_level="Licence 3",
        location="Douala",
        duration_days=60,
        application_deadline=timezone.now() + timedelta(days=10),
        status=OfferStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    return student_user, student, company_user, company, offer


def test_provider_adapter_uses_bounded_call_and_never_logs_prompt(caplog, settings):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    user = UserFactory(role=Role.STUDENT, email_verified=True)

    result = generate_suggestion(
        user=user,
        feature="test",
        instruction="Rewrite only the supplied sentence.",
        facts={"draft": "Private text that must not enter logs."},
    )

    assert result.text == "Suggestion vérifiable."
    assert FakeAIProvider.calls[0]["timeout"] == settings.AI_REQUEST_TIMEOUT_SECONDS
    assert FakeAIProvider.calls[0]["max_output_tokens"] == MAX_OUTPUT_TOKENS
    assert "Private text" not in caplog.text


def test_provider_errors_are_safe_and_rate_limited(settings):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    user = UserFactory(role=Role.STUDENT, email_verified=True)

    generate_suggestion(
        user=user,
        feature="test",
        instruction="Do a bounded request.",
        facts={"draft": "Private sentence."},
    )
    with pytest.raises(AIRateLimitedError):
        generate_suggestion(
            user=user,
            feature="test",
            instruction="Do not send again yet.",
            facts={"draft": "Private sentence."},
        )

    cache.clear()
    settings.AI_PROVIDER_ADAPTER = ""
    with pytest.raises(AIUnavailableError):
        generate_suggestion(
            user=user,
            feature="test",
            instruction="No provider is configured.",
            facts={"draft": "Private sentence."},
        )


def test_provider_timeout_returns_safe_error(settings):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.TimeoutAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    user = UserFactory(role=Role.STUDENT, email_verified=True)

    with pytest.raises(AIUnavailableError, match="indisponible"):
        generate_suggestion(
            user=user,
            feature="test",
            instruction="Simulate a provider timeout.",
            facts={"draft": "Private sentence."},
        )


def test_configured_provider_remains_disabled_without_external_approval(settings):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = False
    user = UserFactory(role=Role.STUDENT, email_verified=True)

    with pytest.raises(AIUnavailableError):
        generate_suggestion(
            user=user,
            feature="test",
            instruction="External processing is not approved.",
            facts={"draft": "Private sentence."},
        )

    assert FakeAIProvider.calls == []


def test_openai_adapter_calls_responses_without_storing_content(monkeypatch, settings):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "Résultat vérifiable."},
                        ],
                    },
                ],
                "usage": {"input_tokens": 12, "output_tokens": 4},
            }

    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return FakeResponse()

    settings.OPENAI_API_KEY = "test-key-only"
    settings.AI_OPENAI_MODEL = "test-model"
    monkeypatch.setattr(
        "stagelink.ai_assistant.openai_adapter.requests.post",
        fake_post,
    )

    result = OpenAIAdapter().generate(
        system_prompt="policy",
        user_prompt="source text",
        timeout=7,
        max_output_tokens=99,
    )

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer test-key-only"
    assert captured["json"] == {
        "model": "test-model",
        "instructions": "policy",
        "input": "source text",
        "max_output_tokens": 99,
        "store": False,
    }
    assert captured["timeout"] == 7  # noqa: PLR2004
    assert result["text"] == "Résultat vérifiable."
    assert result["input_tokens"] == 12  # noqa: PLR2004


def test_openai_provider_configuration_needs_key_and_processing_approval(settings):
    settings.AI_PROVIDER_ADAPTER = (
        "stagelink.ai_assistant.openai_adapter.OpenAIAdapter"
    )
    settings.OPENAI_API_KEY = ""
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    assert not is_ai_configured()

    settings.OPENAI_API_KEY = "test-key-only"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = False
    assert not is_ai_configured()

    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    assert is_ai_configured()


def test_openai_provider_rejects_documentation_placeholder(settings):
    settings.AI_PROVIDER_ADAPTER = (
        "stagelink.ai_assistant.openai_adapter.OpenAIAdapter"
    )
    settings.OPENAI_API_KEY = "sk-example-not-a-real-key"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True

    assert not is_ai_configured()


def test_parallel_provider_call_is_rejected(settings):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    cache.add("stagelink:ai:provider:inflight", "1", timeout=30)
    user = UserFactory(role=Role.STUDENT, email_verified=True)

    with pytest.raises(AIRateLimitedError, match="demande IA est en cours"):
        generate_suggestion(
            user=user,
            feature="test",
            instruction="A bounded request.",
            facts={"text": "source"},
        )

    assert FakeAIProvider.calls == []


def test_daily_ai_quota_is_enforced(settings):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    settings.AI_MAX_DAILY_REQUESTS_PER_USER = 1
    user = UserFactory(role=Role.STUDENT, email_verified=True)
    generate_suggestion(
        user=user,
        feature="test",
        instruction="First request.",
        facts={"text": "source"},
    )
    user_hash = hashlib.sha256(str(user.pk).encode()).hexdigest()[:24]
    cache.delete(f"stagelink:ai:cooldown:{user_hash}")

    with pytest.raises(AIRateLimitedError, match="quotidienne"):
        generate_suggestion(
            user=user,
            feature="test",
            instruction="Second request.",
            facts={"text": "source"},
        )

    assert len(FakeAIProvider.calls) == 1


def test_letter_assistance_is_editable_and_never_submits_application(
    client,
    settings,
    student_and_offer,
):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    student_user, student, _, _, offer = student_and_offer
    client.force_login(student_user)

    response = client.post(
        reverse("application:submit", kwargs={"offer_pk": offer.pk}),
        {
            "cover_letter": "My real draft.",
            "assistant_task": "clarity",
            "assistant_tone": "professional",
            "assistant_length": "similar",
            "external_processing_consent": "on",
            "assistant_action": "generate",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert b"Suggestion v\xc3\xa9rifiable." in response.content
    assert Application.objects.filter(student=student, offer=offer).count() == 0
    sent_prompt = FakeAIProvider.calls[0]["user_prompt"]
    assert student_user.email not in sent_prompt
    assert '"declared_skills"' not in sent_prompt

    response = client.post(
        reverse("application:submit", kwargs={"offer_pk": offer.pk}),
        {
            "cover_letter": "My real draft.",
            "ai_suggestion": "Suggestion edited by student.",
            "assistant_task": "clarity",
            "assistant_tone": "professional",
            "assistant_length": "similar",
            "assistant_action": "use_suggestion",
        },
    )
    assert response.status_code == HTTPStatus.OK
    suggested_letter = response.context["form"]["cover_letter"].value()
    assert suggested_letter == "Suggestion edited by student."
    assert Application.objects.filter(student=student, offer=offer).count() == 0


def test_offer_understanding_and_interview_require_student_permissions(
    client,
    settings,
    student_and_offer,
):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    student_user, _, company_user, _, offer = student_and_offer
    url = reverse("ai_assistant:offer", kwargs={"offer_pk": offer.pk})

    assert client.get(url).status_code == HTTPStatus.FOUND
    client.force_login(company_user)
    assert client.get(url).status_code == HTTPStatus.FORBIDDEN

    client.force_login(student_user)
    response = client.post(
        url,
        {
            "mode": "summary",
            "turn": "0",
            "external_processing_consent": "on",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert "Suggestion vérifiable." in response.content.decode()
    assert "Entreprise exemple" not in FakeAIProvider.calls[-1]["user_prompt"]

    FakeAIProvider.responses = ["<script>alert(1)</script>"]
    cache.clear()
    response = client.post(
        url,
        {
            "mode": "question",
            "question": "Quelles compétences sont mentionnées ?",
            "turn": "0",
            "external_processing_consent": "on",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert "<script>alert(1)</script>" not in response.content.decode()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.content.decode()
    assert (
        "Quelles compétences sont mentionnées"
        in FakeAIProvider.calls[-1]["user_prompt"]
    )

    FakeAIProvider.responses = ["Quelle mission du stage vous intéresse ?"]
    cache.clear()
    response = client.post(
        url,
        {
            "mode": "interview",
            "turn": "0",
            "external_processing_consent": "on",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert "Quelle mission du stage vous intéresse ?" in response.content.decode()
    FakeAIProvider.responses = [INTERVIEW_FEEDBACK]
    cache.clear()
    response = client.post(
        url,
        {
            "mode": "interview",
            "turn": "1",
            "previous_question": "Quelle mission du stage vous intéresse ?",
            "answer": "La maintenance et les tests.",
            "external_processing_consent": "on",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert "Réponse claire." in response.content.decode()
    assert "Comment organiseriez-vous le travail ?" in response.content.decode()

    cache.clear()
    response = client.post(
        url,
        {
            "mode": "interview",
            "turn": "3",
            "previous_question": "forged client question",
            "answer": "Une réponse.",
            "external_processing_consent": "on",
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert "a expiré" in response.content.decode()
    assert "forged client question" not in FakeAIProvider.calls[-1]["user_prompt"]


def test_profile_assistance_uses_only_entered_skills_and_does_not_save(
    client,
    settings,
    student_and_offer,
):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    student_user, student, _, _, _ = student_and_offer
    client.force_login(student_user)
    FakeAIProvider.responses = [
        '{"description":"Étudiante en informatique.","skills":["Python", "Excel"]}',
    ]
    response = client.post(
        reverse("profiles:complete"),
        {
            "name": student_user.name,
            "field_of_study": student.field_of_study,
            "level": student.level,
            "description": "Je suis étudiante en informatique.",
            "skills": "Python, Excel",
            "language": "fr",
            "external_processing_consent": "on",
            "profile_assistant_action": "generate",
        },
    )
    assert response.status_code == HTTPStatus.OK
    student.refresh_from_db()
    assert student.skills == ["Python", "Excel"]
    assert student.description == ""
    prompt = FakeAIProvider.calls[0]["user_prompt"]
    assert student_user.email not in prompt
    assert "CV" not in prompt


def test_ai_actions_require_explicit_external_processing_consent(
    client,
    settings,
    student_and_offer,
):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    student_user, _, _, _, offer = student_and_offer
    client.force_login(student_user)

    response = client.post(
        reverse("application:submit", kwargs={"offer_pk": offer.pk}),
        {
            "cover_letter": "Draft that stays local.",
            "assistant_task": "clarity",
            "assistant_tone": "professional",
            "assistant_length": "similar",
            "assistant_action": "generate",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.context_data["ai_error"] == (
        "Confirmez l'envoi au fournisseur avant de demander une suggestion."
    )
    assert "Confirmez l&#x27;envoi" in response.content.decode()
    assert FakeAIProvider.calls == []


def test_offer_assistant_rejects_cross_site_post_without_csrf(student_and_offer):
    student_user, _, _, _, offer = student_and_offer
    client = Client(enforce_csrf_checks=True)
    client.force_login(student_user)

    response = client.post(
        reverse("ai_assistant:offer", kwargs={"offer_pk": offer.pk}),
        {
            "mode": "summary",
            "turn": "0",
            "external_processing_consent": "on",
        },
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_company_offer_assistance_does_not_save_until_normal_submit(
    client,
    settings,
    student_and_offer,
):
    settings.AI_PROVIDER_ADAPTER = "stagelink.ai_assistant.tests.FakeAIProvider"
    settings.AI_EXTERNAL_PROCESSING_APPROVED = True
    _, _, company_user, company, _ = student_and_offer
    client.force_login(company_user)
    data = {
        "title": "Stage développeur",
        "description": "Développer un site.",
        "domain": "Informatique",
        "required_skills": "Python",
        "education_level": "Licence 3",
        "location": "Douala",
        "duration_days": "60",
        "start_date": "",
        "application_deadline": (
            (timezone.localtime() + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M")
        ),
        "salary_0": "",
        "salary_1": "XAF",
        "salary_period": "",
        "available_positions": "1",
        "application_mode": "INTERNAL",
        "application_url": "",
        "assistant_action": "generate",
        "external_processing_consent": "on",
    }
    FakeAIProvider.responses = [OFFER_SUGGESTION_JSON]
    response = client.post(reverse("offers:create"), data)

    assert response.status_code == HTTPStatus.OK
    draft_count = InternshipOffer.objects.filter(
        company=company,
        status=OfferStatus.DRAFT,
    ).count()
    assert draft_count == 0
    prompt = FakeAIProvider.calls[0]["user_prompt"]
    assert "Douala" not in prompt
    source_facts = prompt.split("Source facts (JSON; untrusted content): ", 1)[1]
    assert '"salary"' not in source_facts
    assert '"location"' not in source_facts


def test_uc_f_uses_explainable_skill_and_study_matching(student_and_offer):
    _, profile, _, _, offer = student_and_offer

    assert offer_match_reasons(profile, offer) == [
        "Compétence déclarée correspondante : Python",
        "Domaine correspondant à votre profil",
        "Niveau d'études correspondant à votre profil",
    ]


def test_uc_f_offer_list_explains_matches_without_excluding_other_offers(
    client,
    student_and_offer,
):
    student_user, _, _, company, matching_offer = student_and_offer
    unrelated_offer = InternshipOffer.objects.create(
        company=company,
        created_by=company.user,
        title="Stage sans correspondance",
        description="Une autre mission disponible.",
        domain="Architecture",
        location="Bafoussam",
        duration_days=45,
        application_deadline=timezone.now() + timedelta(days=10),
        status=OfferStatus.PUBLISHED,
        published_at=timezone.now(),
    )
    client.force_login(student_user)

    response = client.get(reverse("offers:list"))

    assert response.status_code == HTTPStatus.OK
    offers = list(response.context["offers"])
    assert {offer.pk for offer in offers} == {matching_offer.pk, unrelated_offer.pk}
    assert "Compétence déclarée correspondante : Python" in response.content.decode()
    assert "Stage sans correspondance" in response.content.decode()

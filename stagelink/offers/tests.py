from datetime import timedelta
from http import HTTPStatus

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from stagelink.offers.admin import InternshipOfferAdminForm
from stagelink.offers.models import InternshipOffer
from stagelink.offers.services import publish_offer
from stagelink.offers.services import update_offer
from stagelink.offers.views import OFFERS_PER_PAGE
from stagelink.profiles.models import CompanyProfile
from stagelink.profiles.models import StudentProfile
from stagelink.users.tests.factories import UserFactory
from stagelink.utils.enums import ApplicationMode
from stagelink.utils.enums import OfferStatus
from stagelink.utils.enums import Role

pytestmark = pytest.mark.django_db


def make_company(name="Acme"):
    user = UserFactory(role=Role.COMPANY, email_verified=True)
    return CompanyProfile.objects.create(
        user=user,
        company_name=name,
        address="Douala",
    )


def make_offer(company=None, **kwargs):
    defaults = {
        "title": "Stagiaire développeur",
        "description": "Développement web.",
        "domain": "Informatique",
        "location": "Douala",
        "duration_days": 60,
        "application_deadline": timezone.now() + timedelta(days=10),
        "status": OfferStatus.PUBLISHED,
        "published_at": timezone.now(),
    }
    defaults.update(kwargs)
    return InternshipOffer.objects.create(
        company=company,
        created_by=company.user if company else None,
        **defaults,
    )


def offer_post_data(**overrides):
    deadline = timezone.localtime() + timedelta(days=15)
    data = {
        "title": "Stage marketing",
        "description": "Campagnes digitales.",
        "domain": "Marketing",
        "required_skills": "SEO, Canva, seo",
        "education_level": "Licence 3",
        "location": "Yaoundé",
        "duration_days": "90",
        "start_date": "",
        "application_deadline": deadline.strftime("%Y-%m-%dT%H:%M"),
        "salary_0": "",
        "salary_1": "XAF",
        "salary_period": "",
        "available_positions": "2",
        "application_mode": ApplicationMode.INTERNAL,
        "application_url": "",
    }
    data.update(overrides)
    return data


@pytest.fixture
def company():
    return make_company()


@pytest.fixture
def company_client(client, company):
    client.force_login(company.user)
    return client


class TestModel:
    def test_is_available(self, company):
        assert make_offer(company).is_available
        assert not make_offer(company, status=OfferStatus.DRAFT).is_available
        assert not make_offer(
            company,
            application_deadline=timezone.now() - timedelta(days=1),
        ).is_available

    def test_is_relayed(self, company):
        assert make_offer(
            None,
            application_mode=ApplicationMode.EXTERNAL,
            application_url="https://example.com",
        ).is_relayed
        assert not make_offer(company).is_relayed


class TestOfferList:
    url = reverse("offers:list")

    def test_lists_only_available_offers(self, client, company):
        visible = make_offer(company, title="Visible")
        make_offer(company, title="Brouillon", status=OfferStatus.DRAFT)
        make_offer(company, title="Fermée", status=OfferStatus.CLOSED)
        make_offer(
            company,
            title="Expirée",
            application_deadline=timezone.now() - timedelta(days=1),
        )
        deleted = make_offer(company, title="Supprimée")
        deleted.soft_delete()

        response = client.get(self.url)

        assert response.status_code == HTTPStatus.OK
        assert list(response.context["offers"]) == [visible]

    def test_search_and_filters(self, client, company):
        python = make_offer(company, title="Data", required_skills=["Python"])
        make_offer(company, title="Vente", domain="Commerce", location="Kribi")

        response = client.get(self.url, {"q": "python"})
        assert list(response.context["offers"]) == [python]

        response = client.get(self.url, {"domain": "Commerce", "location": "kri"})
        assert [o.title for o in response.context["offers"]] == ["Vente"]

    def test_search_by_company_name(self, client):
        offer = make_offer(make_company("Orange Cameroun"))
        make_offer(make_company("MTN"))

        response = client.get(self.url, {"q": "orange"})

        assert list(response.context["offers"]) == [offer]

    def test_invalid_filter_is_ignored(self, client, company):
        make_offer(company)

        response = client.get(self.url, {"domain": "Inconnu"})

        assert response.status_code == HTTPStatus.OK
        assert len(response.context["offers"]) == 1

    def test_pagination_keeps_filters(self, client, company):
        for index in range(OFFERS_PER_PAGE + 1):
            make_offer(company, title=f"Offre {index}")

        response = client.get(self.url, {"q": "Offre"})

        assert response.context["is_paginated"]
        assert len(response.context["offers"]) == OFFERS_PER_PAGE
        assert "?q=Offre&amp;page=2" in response.content.decode()
        assert (
            len(client.get(self.url, {"q": "Offre", "page": 2}).context["offers"]) == 1
        )


class TestOfferDetail:
    def test_published_offer_is_public(self, client, company):
        offer = make_offer(company)
        response = client.get(reverse("offers:detail", kwargs={"pk": offer.pk}))
        assert response.status_code == HTTPStatus.OK

    def test_draft_visible_only_by_owner(self, client, company):
        offer = make_offer(company, status=OfferStatus.DRAFT)
        url = reverse("offers:detail", kwargs={"pk": offer.pk})

        assert client.get(url).status_code == HTTPStatus.NOT_FOUND

        client.force_login(make_company("Autre").user)
        assert client.get(url).status_code == HTTPStatus.NOT_FOUND

        client.force_login(company.user)
        assert client.get(url).status_code == HTTPStatus.OK


class TestExternalRedirect:
    def test_redirects_relayed_offer_to_source(self, client):
        offer = make_offer(
            None,
            application_mode=ApplicationMode.EXTERNAL,
            application_url="https://jobs.example.com/stage/42",
        )

        response = client.get(reverse("offers:apply-external", kwargs={"pk": offer.pk}))

        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == "https://jobs.example.com/stage/42"

    def test_no_redirect_for_internal_or_closed_offer(self, client, company):
        internal = make_offer(company)
        closed = make_offer(
            None,
            status=OfferStatus.CLOSED,
            application_mode=ApplicationMode.EXTERNAL,
            application_url="https://jobs.example.com",
        )

        for offer in (internal, closed):
            url = reverse("offers:apply-external", kwargs={"pk": offer.pk})
            assert client.get(url).status_code == HTTPStatus.NOT_FOUND


class TestCompanyManagement:
    def test_requires_company_role(self, client):
        student = UserFactory(role=Role.STUDENT, email_verified=True)
        StudentProfile.objects.create(user=student, field_of_study="Droit", level="L2")
        client.force_login(student)

        assert client.get(reverse("offers:create")).status_code == HTTPStatus.FORBIDDEN

    def test_anonymous_redirected_to_login(self, client):
        response = client.get(reverse("offers:company-list"))
        assert response.status_code == HTTPStatus.FOUND
        assert reverse("users:signin") in response["Location"]

    def test_create_form_renders(self, company_client):
        response = company_client.get(reverse("offers:create"))

        content = response.content.decode()
        assert response.status_code == HTTPStatus.OK
        assert 'name="salary_0"' in content
        assert 'value="XAF"' in content
        assert 'value="EUR"' in content

    def test_create_offer_as_draft(self, company_client, company):
        response = company_client.post(reverse("offers:create"), offer_post_data())

        offer = InternshipOffer.objects.get()
        assert response.status_code == HTTPStatus.FOUND
        assert offer.company == company
        assert offer.created_by == company.user
        assert offer.status == OfferStatus.DRAFT
        assert offer.required_skills == ["SEO", "Canva"]

    def test_create_rejects_past_deadline(self, company_client):
        data = offer_post_data(application_deadline="2020-01-01T10:00")

        response = company_client.post(reverse("offers:create"), data)

        assert response.status_code == HTTPStatus.OK
        assert "application_deadline" in response.context["form"].errors
        assert not InternshipOffer.objects.exists()

    def test_external_offer_requires_url(self, company_client):
        data = offer_post_data(application_mode=ApplicationMode.EXTERNAL)

        response = company_client.post(reverse("offers:create"), data)

        assert "application_url" in response.context["form"].errors

    def test_update_own_offer(self, company_client, company):
        offer = make_offer(company, status=OfferStatus.DRAFT)

        company_client.post(
            reverse("offers:update", kwargs={"pk": offer.pk}),
            offer_post_data(title="Titre modifié"),
        )

        offer.refresh_from_db()
        assert offer.title == "Titre modifié"
        assert offer.updated_by == company.user

    def test_cannot_touch_other_company_offer(self, company_client):
        other = make_offer(make_company("Autre"), status=OfferStatus.DRAFT)

        for name in ("update", "publish", "close"):
            url = reverse(f"offers:{name}", kwargs={"pk": other.pk})
            response = (
                company_client.get(url)
                if name == "update"
                else company_client.post(url)
            )
            assert response.status_code == HTTPStatus.NOT_FOUND

        other.refresh_from_db()
        assert other.status == OfferStatus.DRAFT

    def test_publish_then_close(self, company_client, company):
        offer = make_offer(company, status=OfferStatus.DRAFT, published_at=None)

        company_client.post(reverse("offers:publish", kwargs={"pk": offer.pk}))
        offer.refresh_from_db()
        assert offer.status == OfferStatus.PUBLISHED
        assert offer.published_at is not None

        company_client.post(reverse("offers:close", kwargs={"pk": offer.pk}))
        offer.refresh_from_db()
        assert offer.status == OfferStatus.CLOSED

    def test_status_actions_reject_get(self, company_client, company):
        offer = make_offer(company, status=OfferStatus.DRAFT)
        url = reverse("offers:publish", kwargs={"pk": offer.pk})
        assert company_client.get(url).status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_closed_offer_not_editable(self, company_client, company):
        offer = make_offer(company, status=OfferStatus.CLOSED)
        url = reverse("offers:update", kwargs={"pk": offer.pk})
        assert company_client.get(url).status_code == HTTPStatus.NOT_FOUND

    def test_company_list_filters_by_status(self, company_client, company):
        make_offer(company, status=OfferStatus.DRAFT)
        published = make_offer(company)
        make_offer(make_company("Autre"))

        response = company_client.get(
            reverse("offers:company-list"),
            {"status": "PUBLISHED"},
        )

        assert list(response.context["offers"]) == [published]


class TestServices:
    def test_publish_rejects_expired_deadline(self, company):
        offer = make_offer(
            company,
            status=OfferStatus.DRAFT,
            application_deadline=timezone.now() - timedelta(hours=1),
        )
        with pytest.raises(ValidationError):
            publish_offer(company.user, offer)

    def test_update_rejects_closed_offer(self, company):
        offer = make_offer(company, status=OfferStatus.CLOSED)
        with pytest.raises(ValidationError):
            update_offer(company.user, offer, {"title": "Nouveau"})


class TestAdmin:
    def test_relayed_offer_must_be_external(self):
        data = {
            "title": "Stage relayé",
            "description": "Source externe.",
            "domain": "Finance",
            "required_skills": "[]",
            "location": "Douala",
            "duration_days": 30,
            "application_deadline": timezone.now() + timedelta(days=5),
            "salary_period": "",
            "available_positions": 1,
            "status": OfferStatus.DRAFT,
            "application_mode": ApplicationMode.INTERNAL,
            "salary_0": "",
            "salary_1": "XAF",
        }
        form = InternshipOfferAdminForm(data=data)
        assert not form.is_valid()
        assert "application_mode" in form.errors

    def test_admin_search_by_company_name(self, admin_client, company):
        make_offer(company)
        response = admin_client.get(
            reverse("admin:offers_internshipoffer_changelist"),
            {"q": "Acme"},
        )
        assert response.status_code == HTTPStatus.OK


class TestDashboardLinks:
    def test_company_dashboard_links_to_offers(self, company_client, company):
        offer = make_offer(company)

        content = company_client.get(reverse("profiles:dashboard")).content.decode()

        assert reverse("offers:create") in content
        assert reverse("offers:company-list") in content
        assert reverse("offers:detail", kwargs={"pk": offer.pk}) in content

    def test_student_dashboard_links_to_search(self, client):
        student = UserFactory(role=Role.STUDENT, email_verified=True)
        StudentProfile.objects.create(user=student, field_of_study="Droit", level="L2")
        client.force_login(student)

        content = client.get(reverse("profiles:dashboard")).content.decode()

        assert reverse("offers:list") in content

from django.utils.translation import gettext as _


def offer_match_reasons(profile, offer):
    """Return explainable exact overlaps without hiding or ranking offers."""
    if profile is None:
        return []

    reasons = []
    profile_skills = {
        skill.strip().casefold()
        for skill in profile.skills or []
        if isinstance(skill, str) and skill.strip()
    }
    offer_skills = [
        skill.strip()
        for skill in offer.required_skills or []
        if isinstance(skill, str) and skill.strip()
    ]
    matching_skills = [
        skill for skill in offer_skills if skill.casefold() in profile_skills
    ]
    if matching_skills:
        reasons.append(
            _("Compétence déclarée correspondante : %(skills)s")
            % {"skills": ", ".join(matching_skills)},
        )

    if profile.field_of_study.strip().casefold() == offer.domain.strip().casefold():
        reasons.append(_("Domaine correspondant à votre profil"))
    if (
        profile.level.strip()
        and offer.education_level.strip()
        and profile.level.strip().casefold() == offer.education_level.strip().casefold()
    ):
        reasons.append(_("Niveau d'études correspondant à votre profil"))
    return reasons

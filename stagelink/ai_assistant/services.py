import json

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .providers import AIInvalidResponseError
from .providers import generate_suggestion

MAX_OFFER_TITLE_LENGTH = 255


def improve_letter(*, user, offer, draft, task, tone, length):  # noqa: PLR0913
    return generate_suggestion(
        user=user,
        feature="UC-A",
        instruction=(
            "Improve the submitted motivation-letter draft for the selected "
            "published internship offer. Correct language, clarity, structure, "
            "or adapt emphasis to the offer as requested. Preserve every fact. "
            "Use the requested tone and length; never add achievements or "
            "qualifications."
        ),
        facts={
            "draft": draft,
            "offer": {
                "title": offer.title,
                "description": offer.description,
                "required_skills": offer.required_skills,
                "education_level": offer.education_level,
            },
            "requested_task": task,
            "requested_tone": tone,
            "requested_length": length,
        },
    ).text


OFFER_EXPLANATIONS = {
    "summary": (
        "Summarize the offer using only its supplied fields. Mark missing facts "
        "as not specified."
    ),
    "missions": (
        "Explain the missions stated in the offer. Do not add duties that are "
        "not present."
    ),
    "skills": (
        "Explain the requested skills using the supplied offer text. Do not "
        "infer additional requirements."
    ),
    "requirements": (
        "Clarify the stated requirements and list missing information as not "
        "specified."
    ),
}


def explain_offer(*, user, offer, mode):
    if mode not in OFFER_EXPLANATIONS:
        raise ValidationError(_("Choisissez une aide proposée pour cette offre."))
    return generate_suggestion(
        user=user,
        feature="UC-B",
        instruction=OFFER_EXPLANATIONS[mode],
        facts={
            "title": offer.title,
            "description": offer.description,
            "domain": offer.domain,
            "required_skills": offer.required_skills,
            "education_level": offer.education_level,
            "location": offer.location,
            "duration_days": offer.duration_days,
            "start_date": offer.start_date.isoformat() if offer.start_date else None,
            "application_deadline": offer.application_deadline.isoformat(),
            "salary": str(offer.salary) if offer.salary else None,
            "salary_period": offer.salary_period,
        },
    ).text


def interview_turn(*, user, offer, turn, previous_question="", answer=""):
    first_question = turn == 0
    instruction = (
        "Ask one realistic interview question based only on the offer. Return "
        "only the question."
        if first_question
        else (
            "Give concise, constructive feedback on the student's answer, then ask one "
            "new offer-relevant question. Format exactly as FEEDBACK: followed "
            "by the feedback, "
            "then NEXT QUESTION: followed by one question. Do not rate employability."
        )
    )
    return generate_suggestion(
        user=user,
        feature="UC-C",
        instruction=instruction,
        facts={
            "offer": {
                "title": offer.title,
                "description": offer.description,
                "required_skills": offer.required_skills,
                "education_level": offer.education_level,
            },
            "turn": turn,
            "previous_question": previous_question,
            "student_answer": answer,
        },
    ).text


def improve_profile_presentation(*, user, field_of_study, level, skills):
    return generate_suggestion(
        user=user,
        feature="UC-D",
        instruction=(
            "Suggest a clearer professional presentation of the supplied field "
            "of study, "
            "level and already-declared skills. Do not add, remove or strengthen "
            "facts; "
            "return a concise editable suggestion and label any ambiguous wording."
        ),
        facts={
            "field_of_study": field_of_study,
            "level": level,
            "declared_skills": skills,
        },
    ).text


def improve_offer_draft(*, user, title, description, required_skills):
    result = generate_suggestion(
        user=user,
        feature="UC-E",
        instruction=(
            "Improve the clarity and structure of this company offer draft. "
            "Return only a JSON object with string keys title and description "
            "and array-of-string key required_skills. Use only supplied facts. "
            "Do not invent salary, location, conditions, duties or requirements."
        ),
        facts={
            "draft_title": title,
            "draft_description": description,
            "declared_required_skills": required_skills,
        },
    )
    try:
        suggestion = json.loads(result.text)
    except json.JSONDecodeError as error:
        raise AIInvalidResponseError(
            _("La suggestion de l'offre n'a pas pu être structurée."),
        ) from error

    if (
        not isinstance(suggestion, dict)
        or not isinstance(suggestion.get("title"), str)
        or not isinstance(suggestion.get("description"), str)
        or not isinstance(suggestion.get("required_skills"), list)
        or not all(isinstance(skill, str) for skill in suggestion["required_skills"])
        or len(suggestion["title"]) > MAX_OFFER_TITLE_LENGTH
    ):
        raise AIInvalidResponseError(_("La suggestion de l'offre est incomplète."))
    return suggestion

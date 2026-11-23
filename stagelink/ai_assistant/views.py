from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView

from stagelink.offers.models import InternshipOffer
from stagelink.utils.enums import OfferStatus
from stagelink.utils.enums import Role

from .forms import MAX_INTERVIEW_TURNS
from .forms import OfferAssistantForm
from .providers import AIAssistantError
from .providers import is_ai_configured
from .services import ask_offer_question
from .services import explain_offer
from .services import interview_turn


@method_decorator(transaction.non_atomic_requests, name="dispatch")
class OfferAssistantView(LoginRequiredMixin, FormView):
    template_name = "ai_assistant/offer.html"
    form_class = OfferAssistantForm
    login_url = "users:signin"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role != Role.STUDENT:
            raise PermissionDenied
        self.offer = get_object_or_404(
            InternshipOffer.objects.select_related("company").filter(
                status__in=(OfferStatus.PUBLISHED, OfferStatus.CLOSED),
            ),
            pk=kwargs["offer_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        requested_mode = self.request.GET.get("mode", "summary")
        valid_modes = {
            choice[0] for choice in OfferAssistantForm.base_fields["mode"].choices
        }
        if requested_mode in valid_modes:
            initial["mode"] = requested_mode
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["offer"] = self.offer
        context["ai_configured"] = is_ai_configured()
        context["ai_response"] = getattr(self, "ai_response", "")
        context["interview_question"] = getattr(self, "interview_question", "")
        context["interview_turn"] = getattr(self, "interview_turn_number", 0)
        context["interview_done"] = getattr(self, "interview_done", False)
        context["ai_error"] = getattr(self, "ai_error", "")
        return context

    def form_valid(self, form):  # noqa: PLR0912 -- bounded mode dispatch.
        if not form.cleaned_data.get("external_processing_consent"):
            self.ai_error = _(
                "Confirmez l'envoi au fournisseur avant de demander une suggestion.",
            )
            return self.render_to_response(self.get_context_data(form=form))
        mode = form.cleaned_data["mode"]
        try:
            if mode == "interview":
                turn = form.cleaned_data["turn"]
                session_key = f"stagelink_ai_interview_{self.offer.pk}"
                if turn == 0:
                    session_state = None
                else:
                    session_state = self.request.session.get(session_key)
                    if not session_state or session_state.get("next_turn") != turn:
                        raise ValidationError(  # noqa: TRY301
                            _("Cette séance d'entretien a expiré. Recommencez-la."),
                        )
                response = interview_turn(
                    user=self.request.user,
                    offer=self.offer,
                    turn=turn,
                    previous_question=(
                        session_state["question"] if session_state else ""
                    ),
                    answer=form.cleaned_data["answer"],
                )
                self.interview_turn_number = turn + 1
                if turn == 0:
                    self.interview_question = response
                else:
                    feedback, separator, question = response.partition("NEXT QUESTION:")
                    if not separator or not question.strip():
                        raise AIAssistantError(  # noqa: TRY301
                            _("La réponse de préparation n'a pas pu être structurée."),
                        )
                    self.ai_response = feedback.replace("FEEDBACK:", "", 1).strip()
                    self.interview_question = question.strip()
                self.interview_done = (
                    self.interview_turn_number >= MAX_INTERVIEW_TURNS
                )
                if self.interview_done:
                    self.request.session.pop(session_key, None)
                else:
                    self.request.session[session_key] = {
                        "next_turn": self.interview_turn_number,
                        "question": self.interview_question,
                    }
                form = OfferAssistantForm(
                    initial={
                        "mode": "interview",
                        "turn": self.interview_turn_number,
                        "previous_question": self.interview_question,
                    },
                )
            elif mode == "question":
                self.ai_response = ask_offer_question(
                    user=self.request.user,
                    offer=self.offer,
                    question=form.cleaned_data["question"],
                )
            else:
                self.ai_response = explain_offer(
                    user=self.request.user,
                    offer=self.offer,
                    mode=mode,
                )
        except (AIAssistantError, ValidationError) as error:
            self.ai_error = " ".join(getattr(error, "messages", [str(error)]))

        return self.render_to_response(self.get_context_data(form=form))

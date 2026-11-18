from __future__ import annotations

from django import forms

# Classes communes à tous les champs de saisie du design system.
BASE_FIELD_CLASSES = (
    "w-full rounded-control border border-border bg-surface px-4 py-2.5 "
    "text-sm text-text placeholder:text-text-muted "
    "transition-colors duration-150 "
    "focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 "
    "disabled:cursor-not-allowed disabled:bg-background disabled:opacity-60"
)

# Classes appliquées aux champs fichiers (CV, logo).
FILE_FIELD_CLASSES = (
    "block w-full text-sm text-text-muted "
    "file:mr-4 file:rounded-control file:border-0 file:bg-primary/10 "
    "file:px-4 file:py-2 file:text-sm file:font-semibold file:text-primary "
    "hover:file:bg-primary/20"
)

# Classes appliquées aux cases à cocher.
CHECKBOX_FIELD_CLASSES = "size-4 rounded border-border accent-primary"

# Classes ajoutées aux champs en erreur.
ERROR_FIELD_CLASSES = (
    "border-status-rejected-text focus:border-status-rejected-text "
    "focus:ring-status-rejected-text/20"
)

# Widgets à ne pas styliser comme des champs de saisie classiques.
UNSTYLED_WIDGETS = (
    forms.HiddenInput,
    forms.RadioSelect,
    forms.CheckboxSelectMultiple,
)


class DesignSystemFormMixin:
    """
    Applique automatiquement les classes Tailwind du design system
    aux widgets d'un formulaire Django.

    Les classes déjà définies sur un widget sont conservées.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            self._style_widget(field.widget)

    @staticmethod
    def _style_widget(widget: forms.Widget) -> None:
        """Ajoute les classes adaptées au type de widget."""
        if isinstance(widget, UNSTYLED_WIDGETS):
            return

        if isinstance(widget, forms.CheckboxInput):
            classes = CHECKBOX_FIELD_CLASSES
        elif isinstance(widget, forms.FileInput):
            classes = FILE_FIELD_CLASSES
        else:
            classes = BASE_FIELD_CLASSES

        existing_classes = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{classes} {existing_classes}".strip()

    def full_clean(self) -> None:
        """Valide le formulaire puis signale visuellement les champs en erreur."""
        super().full_clean()
        for field_name in self.errors:
            if field_name not in self.fields:
                continue

            widget = self.fields[field_name].widget
            if isinstance(widget, (*UNSTYLED_WIDGETS, forms.CheckboxInput)):
                continue

            widget.attrs["class"] = (
                f"{widget.attrs.get('class', '')} {ERROR_FIELD_CLASSES}".strip()
            )
            widget.attrs["aria-invalid"] = "true"

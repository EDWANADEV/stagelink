from pathlib import Path

from django import template
from django.conf import settings
from django.utils.html import mark_safe


register = template.Library()


ICONS_DIR = (
    Path(settings.BASE_DIR)
    / "stagelink"
    / "static"
    / "icons"
    / "tabler"
)


ALLOWED_ICONS = {
    "arrow-left",
    "arrow-right",
    "bell",
    "check",
    "download",
    "edit",
    "eye",
    "eye-off",
    "menu-2",
    "search",
    "trash",
    "user",
    "x",
}


@register.simple_tag
def icon(
    name: str,
    size: str = "size-5",
    class_: str = "",
    label: str = "",
) -> str:
    """Affiche une icône Tabler SVG locale."""
    if name not in ALLOWED_ICONS:
        return ""

    icon_path = ICONS_DIR / f"{name}.svg"

    if not icon_path.is_file():
        return ""

    svg = icon_path.read_text(encoding="utf-8")

    classes = f"{size} shrink-0 {class_}".strip()

    accessibility = (
        f'role="img" aria-label="{label}"'
        if label
        else 'aria-hidden="true"'
    )

    svg = svg.replace(
        "<svg",
        f'<svg class="{classes}" {accessibility} focusable="false"',
        1,
    )

    return mark_safe(svg)

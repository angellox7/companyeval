from django import template
from django.urls import reverse

from evaluations.constants import SECTION_URL_NAMES
from evaluations.formatting import format_usd

register = template.Library()


@register.filter
def usd(value):
    return format_usd(value)


@register.simple_tag
def section_url(key, deal_id):
    return reverse(SECTION_URL_NAMES[key], args=[deal_id])

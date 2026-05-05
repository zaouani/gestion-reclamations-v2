# reclamations/templatetags/huitd_filters.py
from django import template

register = template.Library()

@register.filter(name='filter_etape')
def filter_etape(actions, etape):
    """Filtre les actions 8D par étape (D3, D5, D6, D7)"""
    return [action for action in actions if action.etape == etape]
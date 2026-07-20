from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.decorators import role_required
from reclamations.notifications import NotificationService

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def reclamations_en_retard(request):
    """Affiche les réclamations en retard"""
    reclamations_retard = NotificationService.get_reclamations_a_notifier()
    reclamations_alerte = NotificationService.get_reclamations_en_alerte()
    total_a_traiter = len(reclamations_retard) + len(reclamations_alerte)
    context = {
        'reclamations_retard': reclamations_retard,
        'reclamations_alerte': reclamations_alerte,
        'total_a_traiter': total_a_traiter,
    }
    return render(request, 'reclamations/notifications/liste.html', context)

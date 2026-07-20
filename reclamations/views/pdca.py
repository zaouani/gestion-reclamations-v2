from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from reclamations.models import Action8D


@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer'])
def pdca_modifier(request, pk):
    """Modifier une action PDCA (Action8D)"""
    action = get_object_or_404(
        Action8D.objects.select_related(
            'huitd__reclamation__client'
        ),
        pk=pk
    )
    
    if request.method == 'POST':
        # Identification
        action.type_action = request.POST.get('type_action', 'CORRECTIVE')
        action.numero_cause = request.POST.get('numero_cause', '')
        action.action = request.POST.get('action', '')
        action.pilote = request.POST.get('pilote', '')
        
        # Planification
        action.date_prevue = request.POST.get('date_prevue') or None
        action.delai_semaines = request.POST.get('delai_semaines', '')
        
        # Suivi
        action.date_realisee = request.POST.get('date_realisee') or None
        
        # Vérification
        action.efficacite = request.POST.get('efficacite', '0')  # ← CORRIGÉ
        action.comment_verification = request.POST.get('comment_verification', '')
        
        # Statut
        action.statut = request.POST.get('statut', 'PLANIFIE')
        action.avancement = 100 if action.statut == 'REALISE' else  int(request.POST.get('avancement', 0))
        # Remarque et déploiement
        action.remarque = request.POST.get('remarque', '')
        action.deploiement = request.POST.get('deploiement', '')
        
        # Si statut passé à REALISE et pas de date, mettre la date du jour
        if action.statut == 'REALISE' and not action.date_realisee:
            action.date_realisee = timezone.now().date()
        
        action.save()
        reclamation = action.huitd.reclamation
        if reclamation.verifier_et_cloturer():
            messages.success(request, "✅ Action mise à jour - Réclamation clôturée automatiquement (toutes les actions sont terminées)")
        else:
            messages.success(request, "✅ Action PDCA mise à jour avec succès !")
        
        return redirect('reclamations:dashboard_pdca')
    
    context = {
        'action': action,
        'statut_choices': Action8D.STATUT_CHOICES,
        'type_choices': Action8D.TYPE_CHOICES,
    }
    return render(request, 'reclamations/pdca/pdca_edit.html', context)


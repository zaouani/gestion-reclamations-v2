import json
import os
import re
import traceback

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import role_required
from reclamations.models import (
    Action8D,
    Alteration8D,
    CauseCinqP,
    CauseIshikawa,
    CinqW2H,
    EvaluationFacteurHumain,
    Evidence8D,
    FacteurHumain,
    FacteurVRS,
    HuitD,
    Participant8D,
    Reclamation,
    VRS,
)

#Gestion des 8d
@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def huitd_creer(request, reclamation_id):
    """Créer une fiche 8D avec toutes les méthodes initialisées"""
    reclamation = get_object_or_404(Reclamation, pk=reclamation_id)

    if HuitD.objects.filter(reclamation=reclamation).exists():
        huitd = HuitD.objects.get(reclamation=reclamation)
        messages.warning(request, "⚠️ Un 8D existe déjà")
        return redirect('reclamations:huitd_modifier', pk=huitd.id)

    try:
        with transaction.atomic():
            huitd = HuitD.objects.create(
                reclamation=reclamation,
                ref=f"8D-{reclamation.numero_reclamation}",
                date_ouverture=timezone.now().date(),
                client=reclamation.client.nom,
                designation_piece=reclamation.lignes.first().produit.designation if reclamation.lignes.exists() else '',
                decision_8d='OUI',
                etat='EN_COURS'
            )

            # 5W2H
            CinqW2H.objects.create(huitd=huitd)

            # VRS + facteurs
            vrs = VRS.objects.create(huitd=huitd)
            for cat in ['A', 'B', 'C', 'E', 'F']:
                FacteurVRS.objects.create(vrs=vrs, categorie=cat)

            # Facteur Humain + 19 critères
            fh = FacteurHumain.objects.create(huitd=huitd)
            _init_evaluations_fh(fh)

            # 5P par défaut
            CauseCinqP.objects.create(huitd=huitd, type_cause='OCCURRENCE', facteur_prouve='A')
            messages.success(request, f"✅ Fiche 8D créée pour {reclamation.numero_reclamation}")
            return redirect('reclamations:huitd_modifier', pk=huitd.id)

    except Exception as e:
        messages.error(request, f"❌ Erreur : {str(e)}")
        return redirect('reclamations:detail_reclamation', pk=reclamation.id)

def _init_evaluations_fh(fh):
    """Initialise les 19 critères du facteur humain"""
    criteres = [
        ('1', '1.1', '1.1 Are the references worked on the same as those previously planned?'),
        ('1', '1.2', '1.2 Are the tools used those requested in the GP/FI?'),
        ('1', '1.3', '1.3 Is there a problem caused by a defective tool?'),
        ('1', '1.4', '1.4 Are there any blind operations not described in the GP/FI?'),
        ('1', '1.5', '1.5 Are there any components handled that represent quality problems?'),
        ('2', '2.1', '2.1 Are temperature, lighting, noise and cleaning appropriate?'),
        ('2', '2.2', '2.2 Are the PPE suitable for the job?'),
        ('2', '2.3', '2.3 Is the layout adequate for all the operations?'),
        ('2', '2.4', '2.4 Does the operator encounter any ergonomic problems?'),
        ('2', '2.5', '2.5 Is the flow of incoming and outgoing parts well defined?'),
        ('3', '3.1', '3.1 Is the operator overloaded?'),
        ('3', '3.2', '3.2 Is the operator stressed?'),
        ('3', '3.3', '3.3 Is the operator motivated?'),
        ('3', '3.4', '3.4 Is the operator tired?'),
        ('3', '3.5', '3.5 Is the operator in good health?'),
        ('3', '3.6', '3.6 Is the operator suitable for this job?'),
        ('3', '3.7', '3.7 Has the operator worked last 6 months in this position?'),
        ('3', '3.8', '3.8 Is the operator aware of the consequences of this error?'),
        ('3', '3.9', '3.9 Does the operator have any other problems?'),
    ]
    for cat, num, critere in criteres:
        EvaluationFacteurHumain.objects.create(
            facteur_humain=fh, categorie=cat, numero_critere=num, critere=critere
        )

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def huitd_detail(request, pk):
    """Afficher la fiche 8D"""
    huitd = get_object_or_404(
        HuitD.objects.select_related(
            'reclamation__client', 'cinq_w2h', 'vrs', 'facteur_humain'
        ).prefetch_related(
            'participants', 'causes_ishikawa', 'vrs__facteurs',
            'causes_5p', 'facteur_humain__evaluations',
            'actions', 'alterations', 'evidences',
        ),
        pk=pk
    )
    return render(request, 'reclamations/huitd/huitd_detail.html', {'huitd': huitd})

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def huitd_modifier(request, pk):
    """Modifier la fiche 8D - dispatch selon section"""
    huitd = get_object_or_404(
        HuitD.objects.select_related('cinq_w2h', 'vrs', 'facteur_humain').prefetch_related(
            'participants', 'causes_ishikawa', 'vrs__facteurs',
            'causes_5p', 'facteur_humain__evaluations', 'actions', 'alterations','evidences'
        ),
        pk=pk
    )

    if request.method == 'POST':
        section = request.POST.get('section', '')

        try:
            with transaction.atomic():
                if section == 'general': return _save_general(request, huitd)
                if section == 'd1': return _save_d1(request, huitd)
                if section == 'd2': return _save_d2(request, huitd)
                if section == 'd3': return _save_d3(request, huitd)
                if section == 'd4': return _save_d4(request, huitd)
                if section == 'd5': return _save_d5(request, huitd)
                if section == 'd6': return _save_d6(request, huitd)
                if section == 'd7': return _save_d7(request, huitd)
                if section == 'd8': return _save_d8(request, huitd)
                if section == 'decision': return _save_decision(request, huitd)
                if section == '5w2h': return _save_5w2h(request, huitd)
                if section == 'ishikawa': return _save_ishikawa(request, huitd)
                if section == 'vrs': return _save_vrs(request, huitd)
                if section == '5p': return _save_5p(request, huitd)
                if section == 'fh': return _save_fh(request, huitd)
                if section == 'evidences': 
                    return _save_evidences(request, huitd)

        except Exception as e:
            messages.error(request, f"❌ Erreur : {str(e)}")
            traceback.print_exc()

    # Préparer les choix pour les rôles
    role_choices = Participant8D.ROLE_CHOICES
    vrs_data = []
    if huitd.vrs:
        for f in huitd.vrs.facteurs.all():
            vrs_data.append({
                'id': f.id,
                'categorie': f.categorie,
                'facteur_probable': f.facteur_probable,
                'parametre_mesurable': f.parametre_mesurable,
                'standard_exigence': f.standard_exigence,
                'donnees_bonnes': f.donnees_bonnes,
                'donnees_mauvaises': f.donnees_mauvaises,
                'standard_suivi': f.standard_suivi,
                'standard_approprie': f.standard_approprie,
                'lien_prouve': f.lien_prouve,
                'facteur_prouve': f.facteur_prouve,
                  })
    
    context = {
        'huitd': huitd,
        'role_choices': role_choices,
        'vrs_data': json.dumps(vrs_data),
    }

    return render(request, 'reclamations/huitd/huitd_formulaire.html', context)

@login_required
@role_required(['admin', 'quality_manager', 'quality_engineer', 'product_quality_engineer'])
def huitd_supprimer_evidence(request, pk):
    evidence = get_object_or_404(Evidence8D, pk=pk)
    huitd_id = evidence.huitd.id
    evidence.delete()
    messages.success(request, "✅ Évidence supprimée")
    return redirect('reclamations:huitd_modifier', pk=huitd_id)

@login_required
def marquer_8d_non_applicable(request, pk):
    """Marque une réclamation comme 8D non applicable"""
    reclamation = get_object_or_404(Reclamation, pk=pk)
    
    reclamation.huitd_non_applicable = True
     # Passer l'état 8D à CLOTURE
    reclamation.etat_8d = 'CLOTURE'
    
    # Si une date de clôture est nécessaire
    if not reclamation.date_cloture_8d:
        reclamation.date_cloture_8d = timezone.now().date()
    reclamation.save()
    
    messages.success(request, f"✅ La réclamation {reclamation.numero_reclamation} a été marquée comme 8D non applicable et l'état 8D est passé à CLOTURE.")
    return redirect('reclamations:qualite_dashboard')

@login_required
def annuler_8d_non_applicable(request, pk):
    """Annule la mention 8D non applicable"""
    reclamation = get_object_or_404(Reclamation, pk=pk)
    
    reclamation.huitd_non_applicable = False
    # Remettre l'état 8D à OUVERT (ou EN_COURS selon votre besoin)
    reclamation.etat_8d = 'EN_COURS'
    
    # Effacer la date de clôture
    reclamation.date_cloture_8d = None
    reclamation.save()
    
    messages.success(request, f"✅ La mention 8D non applicable a été annulée pour {reclamation.numero_reclamation}. Un 8D est maintenant requis.")
    return redirect('reclamations:qualite_dashboard')

def _save_general(request, huitd):
    huitd.numero_of = request.POST.get('numero_of', '')
    huitd.date_ouverture = request.POST.get('date_ouverture') or None
    huitd.designation_piece = request.POST.get('designation_piece', '')
    huitd.numero_article = request.POST.get('numero_article', '')
    huitd.numero_nc = request.POST.get('numero_nc', '')
    huitd.client = request.POST.get('client', '')
    huitd.lieu_detection = request.POST.get('lieu_detection', 'QUALITE')
    huitd.interne = request.POST.get('interne', '')
    huitd.etat = request.POST.get('huitd_etat')
    huitd.numero_8d = request.POST.get('numero_8d', '')
    huitd.save()
    messages.success(request, "✅ Infos générales enregistrées")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d1(request, huitd):
    """Sauvegarde la section D1 - 5W2H avec gestion des images"""
    
    # Sauvegarde des champs texte D1
    huitd.d1_qui = request.POST.get('d1_qui', '')
    huitd.d1_quoi = request.POST.get('d1_quoi', '')
    huitd.d1_ou = request.POST.get('d1_ou', '')
    huitd.d1_quand = request.POST.get('d1_quand', '')
    huitd.d1_comment = request.POST.get('d1_comment', '')
    huitd.d1_combien = request.POST.get('d1_combien', '')
    huitd.d1_pourquoi = request.POST.get('d1_pourquoi', '')
    huitd.d1_caracterisation = request.POST.get('d1_caracterisation', '')
    huitd.d1_probleme_connu = request.POST.get('d1_probleme_connu') == 'on'
    huitd.d1_risque = request.POST.get('d1_risque') == 'on'
    huitd.d1_risque_detail = request.POST.get('d1_risque_detail', '')
    
    # ========== GESTION DES IMAGES ==========
    
    # Vérifier si l'utilateur veut supprimer l'image défectueuse
    if request.POST.get('supprimer_defectueux') == '1':
        if huitd.d1_illustration_defectueux:
            # Supprimer le fichier physique
            if os.path.isfile(huitd.d1_illustration_defectueux.path):
                os.remove(huitd.d1_illustration_defectueux.path)
            huitd.d1_illustration_defectueux = None
    
    # Vérifier si l'utilisateur veut supprimer l'image conforme
    if request.POST.get('supprimer_conforme') == '1':
        if huitd.d1_illustration_conforme:
            # Supprimer le fichier physique
            if os.path.isfile(huitd.d1_illustration_conforme.path):
                os.remove(huitd.d1_illustration_conforme.path)
            huitd.d1_illustration_conforme = None
    
    # Gérer la nouvelle image défectueuse (remplace l'ancienne si existante)
    if 'illustration_defectueux' in request.FILES:
        # Supprimer l'ancienne image si elle existe
        if huitd.d1_illustration_defectueux and not request.POST.get('supprimer_defectueux'):
            if os.path.isfile(huitd.d1_illustration_defectueux.path):
                os.remove(huitd.d1_illustration_defectueux.path)
        huitd.d1_illustration_defectueux = request.FILES['illustration_defectueux']
    
    # Gérer la nouvelle image conforme
    if 'illustration_conforme' in request.FILES:
        # Supprimer l'ancienne image si elle existe
        if huitd.d1_illustration_conforme and not request.POST.get('supprimer_conforme'):
            if os.path.isfile(huitd.d1_illustration_conforme.path):
                os.remove(huitd.d1_illustration_conforme.path)
        huitd.d1_illustration_conforme = request.FILES['illustration_conforme']
    
    huitd.save()
    
    messages.success(request, "✅ D1 - 5W2H enregistré avec succès!")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d2(request, huitd):
    huitd.d2_date = request.POST.get('d2_date') or None
    huitd.d2_actions = request.POST.get('d2_actions', '')
    huitd.d2_tri = request.POST.get('d2_tri') == 'oui'
    huitd.d2_of_concernes = request.POST.get('of_concernes', '')
    huitd.d2_quantite_rebutee = request.POST.get('quantite_rebutee', 'N/A')
    huitd.d2_quantite_retoucher = request.POST.get('quantite_retoucher', 'N/A')
    huitd.save()
    messages.success(request, "✅ D2 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d3(request, huitd):
    """Sauvegarde la section D3 - Équipe 8D avec participants"""
    
    # Sauvegarde des champs D3 existants dans HuitD
    huitd.d3_date = request.POST.get('d3_date') or None
    huitd.pilote = request.POST.get('pilote', '')
    huitd.pilote_fonction = request.POST.get('pilote_fonction', '')
    huitd.animateur = request.POST.get('animateur', '')
    huitd.animateur_fonction = request.POST.get('animateur_fonction', '')
    huitd.save()
    
    # ========== GESTION DES PARTICIPANTS (uniquement les participants supplémentaires) ==========
    # Récupérer toutes les données des participants
    participant_ids = request.POST.getlist('participant_id[]')
    participant_noms = request.POST.getlist('participant_nom[]')
    participant_fonctions = request.POST.getlist('participant_fonction[]')
    participant_ordres = request.POST.getlist('participant_ordre[]')
    
    participants_a_conserver = []
    
    # Parcourir tous les participants
    for i in range(len(participant_noms)):
        nom = participant_noms[i].strip()
        if not nom:  # Ignorer les lignes vides
            continue
        
        fonction = participant_fonctions[i] if i < len(participant_fonctions) else ''
        ordre = int(participant_ordres[i]) if i < len(participant_ordres) and participant_ordres[i].isdigit() else i + 1
        participant_id = participant_ids[i] if i < len(participant_ids) else ''
        
        # Vérifier si c'est un participant existant ou nouveau
        if participant_id and participant_id != '' and participant_id.isdigit():
            # Modifier participant existant
            try:
                participant = Participant8D.objects.get(id=int(participant_id), huitd=huitd)
                participant.nom = nom
                participant.fonction = fonction
                participant.ordre = ordre
                participant.save()
                participants_a_conserver.append(participant.id)
            except Participant8D.DoesNotExist:
                # Créer nouveau participant
                participant = Participant8D.objects.create(
                    huitd=huitd,
                    nom=nom,
                    fonction=fonction,
                    ordre=ordre
                )
                participants_a_conserver.append(participant.id)
        elif participant_id and participant_id.startswith('new_'):
            # Créer nouveau participant
            participant = Participant8D.objects.create(
                huitd=huitd,
                nom=nom,
                fonction=fonction,
                ordre=ordre
            )
            participants_a_conserver.append(participant.id)
    
    # Supprimer les participants qui ne sont plus dans la liste
    if participants_a_conserver:
        huitd.participants.exclude(id__in=participants_a_conserver).delete()
    else:
        huitd.participants.all().delete()
    
    messages.success(request, "✅ D3 - Équipe 8D enregistrée avec succès!")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d4(request, huitd):
    huitd.d4_date = request.POST.get('d4_date') or None
    huitd.d4_causes_apparition = request.POST.get('d4_causes_apparition', '')
    huitd.d4_causes_non_detection = request.POST.get('d4_causes_non_detection', '')
    huitd.decision_8d = request.POST.get('decision_8d', 'OUI')
    huitd.save()
    messages.success(request, "✅ D4 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d5(request, huitd):
    huitd.d5_causes_occurrence = request.POST.get('d5_causes_occurrence', "voir ishikawa et 5W2H see / Ishikawa and 5W2H")
    huitd.d5_causes_non_detection = request.POST.get('d5_causes_non_detection', "voir ishikawa et 5W2H / see Ishikawa and 5W2H")
    huitd.save()
    messages.success(request, "✅ D5 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d6(request, huitd):
    """Sauvegarde D6 - Plan d'actions et vérification clôture"""
    huitd.actions.all().delete()

    types_action = request.POST.getlist('action_type[]')
    causes = request.POST.getlist('action_cause[]')
    actions = request.POST.getlist('action_desc[]')
    pilotes = request.POST.getlist('action_pilote[]')
    dates_prevues = request.POST.getlist('action_date_prevue[]')
    delai_semaines = request.POST.getlist('action_delai[]')
    statuts = request.POST.getlist('action_statut[]')
    
    for i in range(len(actions)):
        if actions[i].strip():
            Action8D.objects.create(
                huitd=huitd,
                type_action=types_action[i] if i < len(types_action) else 'CORRECTIVE',
                numero_cause=causes[i] if i < len(causes) else '',
                action=actions[i],
                pilote=pilotes[i] if i < len(pilotes) else '', 
                delai_semaines=delai_semaines[i] if i < len(delai_semaines) else '',
                statut=statuts[i] if i < len(statuts) else 'PLANIFIE',
                ordre=i+1
            )
    
    # Vérifier si la réclamation peut être clôturée
    reclamation = huitd.reclamation
    if reclamation.verifier_et_cloturer():
        messages.success(request, "✅ D6 enregistré - Réclamation clôturée automatiquement (toutes les actions sont terminées)")
    else:
        messages.success(request, "✅ D6 enregistré")
    
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d7(request, huitd):
    huitd.d7_verification = request.POST.get('d7_verification', '')
    huitd.d7_suffisant = request.POST.get('d7_suffisant', '')
    huitd.save()
    messages.success(request, "✅ D7 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d8(request, huitd):
    huitd.d8_transversalisation = request.POST.get('transversalisation', '')
    huitd.save()
    huitd.alterations.all().delete()
    docs = ['Inspection Sheet (PV)','Control Plan','Instruction Sheet (FI)','Maintenance Plan','Audit Frequency','Workstation Documents Updated','Process Improvement','PFMEA','Standardization of Tools and Equipment','Training Plan','Deploy to Similar Products/Processes (Other Program)','Deploy to Similar Products/Processes (Other APU)']
    for i, doc in enumerate(docs):
        r = request.POST.get(f'alt_remark_{i}', '')
        p = request.POST.get(f'alt_pilote_{i}', '')
        d = request.POST.get(f'alt_deadline_{i}') or None
        if r or p or d:
            Alteration8D.objects.create(huitd=huitd, type_document=doc, remarque=r, pilote=p, deadline=d, ordre=i+1)
    messages.success(request, "✅ D8 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_decision(request, huitd):
    huitd.huitd_accepte = request.POST.get('huitd_accepte') == 'oui'
    huitd.decision_hcim = request.POST.get('decision_hcim', '')
    huitd.fin_huitd = request.POST.get('fin_huitd') or None
    huitd.fin_huitd_signature = request.POST.get('fin_huitd_signature', '')
    huitd.save()
    messages.success(request, "✅ Décision enregistrée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_5w2h(request, huitd):
    w = huitd.cinq_w2h
    w.c_what_happened = request.POST.get('c_what_happened', '')
    w.c_who_detected = request.POST.get('c_who_detected', '')
    w.c_where_detected = request.POST.get('c_where_detected', '')
    w.c_when_detected = request.POST.get('c_when_detected', '')
    w.c_how_detected = request.POST.get('c_how_detected', '')
    w.c_how_many = request.POST.get('c_how_many', '')
    w.c_why_problem = request.POST.get('c_why_problem', '')
    w.c_logistic_impact = request.POST.get('c_logistic_impact', '')
    w.c_other_customers_delivered = request.POST.get('c_other_customers_delivered', '')
    w.c_other_customers_defect = request.POST.get('c_other_customers_defect', '')
    w.h_symptoms = request.POST.get('h_symptoms', '')
    w.h_defects_ruled_out = request.POST.get('h_defects_ruled_out', '')
    w.h_where_created = request.POST.get('h_where_created', '')
    w.h_when_generated = request.POST.get('h_when_generated', '')
    w.h_rework = request.POST.get('h_rework', '')
    w.h_detection_expected = request.POST.get('h_detection_expected', '')
    w.h_reinjection = request.POST.get('h_reinjection', '')
    w.h_known_problem = request.POST.get('h_known_problem', '')
    w.h_last_reported = request.POST.get('h_last_reported', '')
    w.save()
    messages.success(request, "✅ 5W2H enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_ishikawa(request, huitd):
    huitd.causes_ishikawa.all().delete()
    for cat in ['A','B','C','D','E','F']:
        causes = request.POST.getlist(f'ishikawa_{cat}_cause[]')
        for i, cause in enumerate(causes):
            if cause.strip():
                type_key = f'ishikawa_{cat}_type_{i}'
                type_cause = request.POST.get(type_key, 'OCCURRENCE')
                CauseIshikawa.objects.create(huitd=huitd, categorie=cat, cause=cause, type_cause=type_cause, ordre=i+1)
    messages.success(request, "✅ Ishikawa enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_vrs(request, huitd):
    """Sauvegarde du tableau VRS avec index numériques"""
    
    # Récupérer ou créer le VRS
    vrs, created = VRS.objects.get_or_create(huitd=huitd)
    
    # Supprimer toutes les anciennes entrées
    vrs.facteurs.all().delete()
    
    # Trouver tous les indices
    indices = set()
    for key in request.POST.keys():
        match = re.search(r'vrs_categorie_(\d+)', key)
        if match:
            indices.add(int(match.group(1)))
    
    # Ordre par catégorie
    ordre_par_categorie = {}
    
    for idx in sorted(indices):
        categorie = request.POST.get(f'vrs_categorie_{idx}', '')
        if not categorie or categorie == 'D':
            continue
        
        if categorie not in ordre_par_categorie:
            ordre_par_categorie[categorie] = 1
        
        FacteurVRS.objects.create(
            vrs=vrs,
            categorie=categorie,
            facteur_probable=request.POST.get(f'vrs_facteur_{idx}', ''),
            parametre_mesurable=request.POST.get(f'vrs_parametre_{idx}', ''),
            standard_exigence=request.POST.get(f'vrs_standard_{idx}', ''),
            donnees_bonnes=request.POST.get(f'vrs_bonnes_{idx}', ''),
            donnees_mauvaises=request.POST.get(f'vrs_mauvaises_{idx}', ''),
            standard_suivi=request.POST.get(f'vrs_suivi_{idx}') == '1',
            standard_approprie=request.POST.get(f'vrs_appro_{idx}') == '1',
            lien_prouve=request.POST.get(f'vrs_lien_{idx}') == '1',
            facteur_prouve=request.POST.get(f'vrs_prouve_{idx}') == '1',
            ordre=ordre_par_categorie[categorie]
        )
        
        ordre_par_categorie[categorie] += 1
    
    messages.success(request, "✅ VRS enregistré avec succès!")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_5p(request, huitd):
    huitd.causes_5p.all().delete()
    types_cause = request.POST.getlist('5p_type[]')
    facteurs = request.POST.getlist('5p_facteur[]')
    p1s = request.POST.getlist('5p_p1[]')
    p2s = request.POST.getlist('5p_p2[]')
    p3s = request.POST.getlist('5p_p3[]')
    p4s = request.POST.getlist('5p_p4[]')
    p5s = request.POST.getlist('5p_p5[]')
    for i in range(len(types_cause)):
        if any([p1s[i].strip() if i < len(p1s) else '', p2s[i].strip() if i < len(p2s) else '', p3s[i].strip() if i < len(p3s) else '', p4s[i].strip() if i < len(p4s) else '', p5s[i].strip() if i < len(p5s) else '']):
            CauseCinqP.objects.create(
                huitd=huitd,
                type_cause=types_cause[i] if i < len(types_cause) else 'OCCURRENCE',
                facteur_prouve=facteurs[i] if i < len(facteurs) else '',
                pourquoi_1=p1s[i] if i < len(p1s) else '',
                pourquoi_2=p2s[i] if i < len(p2s) else '',
                pourquoi_3=p3s[i] if i < len(p3s) else '',
                pourquoi_4=p4s[i] if i < len(p4s) else '',
                pourquoi_5=p5s[i] if i < len(p5s) else '',
            )
    messages.success(request, "✅ 5P enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_fh(request, huitd):
    for ev in huitd.facteur_humain.evaluations.all():
        key = f'fh_eval_{ev.categorie}_{ev.numero_critere}'
        ev.evaluation = request.POST.get(key, '')
        ev.commentaire = request.POST.get(f'{key}_comment', '')
        ev.save()
    messages.success(request, "✅ Facteur Humain enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_evidences(request, huitd):
    """Sauvegarde la section des évidences"""
    
    # Récupérer toutes les données des évidences
    evidence_ids = request.POST.getlist('evidence_id[]')
    evidence_titres = request.POST.getlist('evidence_titre[]')
    evidence_descriptions = request.POST.getlist('evidence_description[]')
    evidence_fichiers = request.FILES.getlist('evidence_fichier[]')
    evidence_supprimer_fichier = request.POST.getlist('evidence_supprimer_fichier[]')
    
    evidences_a_conserver = []
    
    # Traiter les évidences existantes et nouvelles
    for i in range(len(evidence_titres)):
        titre = evidence_titres[i].strip()
        if not titre:
            continue
        
        description = evidence_descriptions[i] if i < len(evidence_descriptions) else ''
        evidence_id = evidence_ids[i] if i < len(evidence_ids) else ''
        fichier = evidence_fichiers[i] if i < len(evidence_fichiers) else None
        
        # Vérifier si l'utilisateur veut supprimer le fichier
        supprimer_fichier = False
        if i < len(evidence_supprimer_fichier):
            supprimer_fichier = evidence_supprimer_fichier[i] == '1'
        
        if evidence_id and evidence_id != '' and evidence_id.isdigit():
            # Modifier évidence existante
            try:
                evidence = Evidence8D.objects.get(id=int(evidence_id), huitd=huitd)
                evidence.titre = titre
                evidence.description = description
                
                # Supprimer l'ancien fichier si demandé
                if supprimer_fichier and evidence.fichier:
                    if os.path.isfile(evidence.fichier.path):
                        os.remove(evidence.fichier.path)
                    evidence.fichier = None
                
                # Remplacer le fichier si nouveau fourni
                if fichier:
                    if evidence.fichier and os.path.isfile(evidence.fichier.path):
                        os.remove(evidence.fichier.path)
                    evidence.fichier = fichier
                
                evidence.save()
                evidences_a_conserver.append(evidence.id)
            except Evidence8D.DoesNotExist:
                # Créer nouvelle évidence (cas rare)
                evidence = Evidence8D.objects.create(
                    huitd=huitd,
                    titre=titre,
                    description=description,
                    fichier=fichier if fichier else None
                )
                evidences_a_conserver.append(evidence.id)
        else:
            # Créer nouvelle évidence
            if not fichier:
                continue  # Une nouvelle évidence doit avoir un fichier
            evidence = Evidence8D.objects.create(
                huitd=huitd,
                titre=titre,
                description=description,
                fichier=fichier
            )
            evidences_a_conserver.append(evidence.id)
    
    # Supprimer les évidences qui ne sont plus dans la liste
    if evidences_a_conserver:
        # Supprimer physiquement les fichiers des évidences supprimées
        for evidence in huitd.evidences.exclude(id__in=evidences_a_conserver):
            if evidence.fichier and os.path.isfile(evidence.fichier.path):
                os.remove(evidence.fichier.path)
        huitd.evidences.exclude(id__in=evidences_a_conserver).delete()
    else:
        # Supprimer toutes les évidences
        for evidence in huitd.evidences.all():
            if evidence.fichier and os.path.isfile(evidence.fichier.path):
                os.remove(evidence.fichier.path)
        huitd.evidences.all().delete()
    
    # ========== CLÔTURE DU 8D ==========
    # Vérifier si le 8D a au moins une évidence
    if huitd.evidences.exists():
        # Changer l'état du 8D en CLOTURE
        huitd.etat = 'CLOTURE'
        huitd.fin_huitd = timezone.now().date()
        huitd.save()
        messages.success(request, "✅ Évidences enregistrées et 8D clôturé avec succès!")
    else:
        # Si plus d'évidence, on remet l'état à EN_COURS
        if huitd.etat == 'CLOTURE':
            huitd.etat = 'EN_COURS'
            huitd.fin_huitd = None
            huitd.save()
        messages.success(request, "✅ Évidences enregistrées avec succès!")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

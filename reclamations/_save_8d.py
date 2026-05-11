
def _save_general(request, huitd):
    """Sauvegarde Informations Générales"""
    huitd.numero_of = request.POST.get('numero_of', '')
    huitd.date_ouverture = request.POST.get('date_ouverture') or None
    huitd.designation_piece = request.POST.get('designation_piece', '')
    huitd.numero_article = request.POST.get('numero_article', '')
    huitd.numero_nc = request.POST.get('numero_nc', '')
    huitd.client = request.POST.get('client', '')
    huitd.lieu_detection = request.POST.get('lieu_detection', 'QUALITE')
    huitd.interne = request.POST.get('interne', '')
    huitd.save()
    messages.success(request, "✅ Informations générales enregistrées")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d1(request, huitd):
    """Sauvegarde D1 - 5W2H"""
    huitd.d1_qui = request.POST.get('d1_qui', '')
    huitd.d1_quoi = request.POST.get('d1_quoi', '')
    huitd.d1_ou = request.POST.get('d1_ou', '')
    huitd.d1_quand = request.POST.get('d1_quand', '')
    huitd.d1_comment = request.POST.get('d1_comment', '')
    huitd.d1_combien = request.POST.get('d1_combien', '')
    huitd.d1_pourquoi = request.POST.get('d1_pourquoi', '')
    huitd.d1_caracterisation = request.POST.get('d1_caracterisation', '')
    huitd.d1_probleme_connu = request.POST.get('d1_probleme_connu') == 'oui'
    huitd.d1_risque = request.POST.get('d1_risque') == 'oui'
    huitd.d1_risque_detail = request.POST.get('d1_risque_detail', '')
    
    if request.FILES.get('illustration_defectueux'):
        huitd.d1_illustration_defectueux = request.FILES['illustration_defectueux']
    if request.FILES.get('illustration_conforme'):
        huitd.d1_illustration_conforme = request.FILES['illustration_conforme']
    
    huitd.save()
    messages.success(request, "✅ D1 - Description du problème enregistrée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d2(request, huitd):
    """Sauvegarde D2 - Actions d'urgence"""
    huitd.d2_date = request.POST.get('d2_date') or None
    huitd.d2_actions = request.POST.get('d2_actions', '')
    huitd.d2_tri = request.POST.get('d2_tri') == 'oui'
    huitd.d2_of_concernes = request.POST.get('of_concernes', '')
    huitd.d2_quantite_rebutee = request.POST.get('quantite_rebutee', 'N/A')
    huitd.d2_quantite_retoucher = request.POST.get('quantite_retoucher', 'N/A')
    huitd.save()
    messages.success(request, "✅ D2 - Actions d'urgence enregistrées")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d3(request, huitd):
    """Sauvegarde D3 - Équipe"""
    huitd.d3_date = request.POST.get('d3_date') or None
    huitd.pilote = request.POST.get('pilote', '')
    huitd.pilote_fonction = request.POST.get('pilote_fonction', '')
    huitd.animateur = request.POST.get('animateur', '')
    huitd.animateur_fonction = request.POST.get('animateur_fonction', '')
    huitd.save()
    
    # Participants
    participant_ids = request.POST.getlist('participant_id[]')
    noms = request.POST.getlist('participant_nom[]')
    fonctions = request.POST.getlist('participant_fonction[]')
    
    conserves = []
    for i in range(len(noms)):
        if not noms[i].strip():
            continue
        pid = participant_ids[i] if i < len(participant_ids) else None
        if pid and pid.startswith('new_'):
            p = Participant8D.objects.create(huitd=huitd, nom=noms[i], fonction=fonctions[i] if i < len(fonctions) else '', ordre=i+1)
            conserves.append(p.id)
        elif pid and pid.isdigit():
            Participant8D.objects.filter(id=pid, huitd=huitd).update(nom=noms[i], fonction=fonctions[i] if i < len(fonctions) else '', ordre=i+1)
            conserves.append(int(pid))
    
    huitd.participants.exclude(id__in=conserves).delete()
    messages.success(request, "✅ D3 - Équipe enregistrée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d4(request, huitd):
    """Sauvegarde D4 - Analyse préliminaire"""
    huitd.d4_date = request.POST.get('d4_date') or None
    huitd.d4_causes_apparition = request.POST.get('d4_causes_apparition', '')
    huitd.d4_causes_non_detection = request.POST.get('d4_causes_non_detection', '')
    huitd.decision_8d = request.POST.get('decision_8d', 'OUI')
    huitd.save()
    messages.success(request, "✅ D4 - Analyse préliminaire enregistrée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d5(request, huitd):
    """Sauvegarde D5 - Causes racines"""
    huitd.d5_causes_occurrence = request.POST.get('d5_causes_occurrence', '')
    huitd.d5_causes_non_detection = request.POST.get('d5_causes_non_detection', '')
    huitd.save()
    messages.success(request, "✅ D5 - Causes racines enregistrées")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_5w2h(request, huitd):
    """Sauvegarde 5W2H complet"""
    w2h = huitd.cinq_w2h
    w2h.nom = request.POST.get('w2h_nom', '')
    w2h.site = request.POST.get('w2h_site', '')
    w2h.date = request.POST.get('w2h_date') or None
    
    # Customer View
    w2h.c_what_happened = request.POST.get('c_what_happened', '')
    w2h.c_who_detected = request.POST.get('c_who_detected', '')
    w2h.c_where_detected = request.POST.get('c_where_detected', '')
    w2h.c_when_detected = request.POST.get('c_when_detected', '')
    w2h.c_how_detected = request.POST.get('c_how_detected', '')
    w2h.c_how_many = request.POST.get('c_how_many', '')
    w2h.c_why_problem = request.POST.get('c_why_problem', '')
    w2h.c_logistic_impact = request.POST.get('c_logistic_impact', '')
    w2h.c_other_customers_delivered = request.POST.get('c_other_customers_delivered', '')
    w2h.c_other_customers_defect = request.POST.get('c_other_customers_defect', '')
    
    # HCIM View
    w2h.h_symptoms = request.POST.get('h_symptoms', '')
    w2h.h_defects_ruled_out = request.POST.get('h_defects_ruled_out', '')
    w2h.h_where_created = request.POST.get('h_where_created', '')
    w2h.h_when_generated = request.POST.get('h_when_generated', '')
    w2h.h_rework = request.POST.get('h_rework', '')
    w2h.h_detection_expected = request.POST.get('h_detection_expected', '')
    w2h.h_reinjection = request.POST.get('h_reinjection', '')
    w2h.h_known_problem = request.POST.get('h_known_problem', '')
    w2h.h_last_reported = request.POST.get('h_last_reported', '')
    
    w2h.save()
    messages.success(request, "✅ 5W2H enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_ishikawa(request, huitd):
    """Sauvegarde Ishikawa"""
    # Supprimer les causes existantes et recréer
    huitd.causes_ishikawa.all().delete()
    
    for categorie in ['A', 'B', 'C', 'D', 'E', 'F']:
        causes = request.POST.getlist(f'ishikawa_{categorie}_cause[]')
        types = []
        for i in range(len(causes)):
            type_val = request.POST.get(f'ishikawa_{categorie}_type_{i}')
            if type_val:
                types.append(type_val)
        
        for i, cause in enumerate(causes):
            if cause.strip():
                CauseIshikawa.objects.create(
                    huitd=huitd,
                    categorie=categorie,
                    cause=cause,
                    type_cause=types[i] if i < len(types) else 'OCCURRENCE',
                    ordre=i+1
                )
    
    messages.success(request, "✅ Ishikawa enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_vrs(request, huitd):
    """Sauvegarde VRS"""
    vrs = huitd.vrs
    vrs.designation = request.POST.get('vrs_designation', '')
    vrs.nom = request.POST.get('vrs_nom', '')
    vrs.site = request.POST.get('vrs_site', '')
    vrs.date = request.POST.get('vrs_date') or None
    vrs.save()
    
    for f in vrs.facteurs.all():
        cat = f.categorie
        f.facteur_probable = request.POST.get(f'vrs_facteur_{cat}', '')
        f.parametre_mesurable = request.POST.get(f'vrs_parametre_{cat}', '')
        f.standard_exigence = request.POST.get(f'vrs_standard_{cat}', '')
        f.donnees_bonnes = request.POST.get(f'vrs_bonnes_{cat}', '')
        f.donnees_mauvaises = request.POST.get(f'vrs_mauvaises_{cat}', '')
        f.standard_suivi = request.POST.get(f'vrs_suivi_{cat}') == 'on'
        f.standard_approprie = request.POST.get(f'vrs_appro_{cat}') == 'on'
        f.lien_prouve = request.POST.get(f'vrs_lien_{cat}') == 'on'
        f.facteur_prouve = request.POST.get(f'vrs_prouve_{cat}') == 'on'
        f.save()
    
    messages.success(request, "✅ VRS enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_5p(request, huitd):
    """Sauvegarde 5 Pourquoi"""
    huitd.causes_5p.all().delete()
    
    types_cause = request.POST.getlist('5p_type[]')
    facteurs = request.POST.getlist('5p_facteur[]')
    p1s = request.POST.getlist('5p_p1[]')
    p2s = request.POST.getlist('5p_p2[]')
    p3s = request.POST.getlist('5p_p3[]')
    p4s = request.POST.getlist('5p_p4[]')
    p5s = request.POST.getlist('5p_p5[]')
    
    for i in range(len(types_cause)):
        if p1s[i].strip() or p2s[i].strip() or p3s[i].strip() or p4s[i].strip() or p5s[i].strip():
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
    
    messages.success(request, "✅ 5 Pourquoi enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_fh(request, huitd):
    """Sauvegarde Facteur Humain"""
    fh = huitd.facteur_humain
    fh.designation = request.POST.get('fh_designation', '')
    fh.nom = request.POST.get('fh_nom', '')
    fh.site = request.POST.get('fh_site', '')
    fh.date = request.POST.get('fh_date') or None
    fh.save()
    
    for ev in fh.evaluations.all():
        key = f'fh_eval_{ev.categorie}_{ev.numero_critere}'
        ev.evaluation = request.POST.get(key, '')
        ev.commentaire = request.POST.get(f'{key}_comment', '')
        ev.save()
    
    messages.success(request, "✅ Facteur Humain enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d6(request, huitd):
    """Sauvegarde D6 - Plan d'actions"""
    huitd.actions.all().delete()
    
    types_action = request.POST.getlist('action_type[]')
    causes = request.POST.getlist('action_cause[]')
    actions = request.POST.getlist('action_desc[]')
    pilotes = request.POST.getlist('action_pilote[]')
    delais = request.POST.getlist('action_delai[]')
    statuts = request.POST.getlist('action_statut[]')
    
    for i in range(len(actions)):
        if actions[i].strip():
            Action8D.objects.create(
                huitd=huitd,
                type_action=types_action[i] if i < len(types_action) else 'CORRECTIVE',
                numero_cause=causes[i] if i < len(causes) else '',
                action=actions[i],
                pilote=pilotes[i] if i < len(pilotes) else '',
                delai_semaines=delais[i] if i < len(delais) else '',
                statut=statuts[i] if i < len(statuts) else 'PLANIFIE',
                ordre=i+1
            )
    
    messages.success(request, "✅ D6 - Plan d'actions enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d7(request, huitd):
    """Sauvegarde D7 - Vérification"""
    huitd.d7_verification = request.POST.get('d7_verification', '')
    huitd.d7_suffisant = request.POST.get('d7_suffisant', '')
    huitd.save()
    messages.success(request, "✅ D7 - Vérification enregistrée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d8(request, huitd):
    """Sauvegarde D8 - Transversalisation + Altérations"""
    huitd.d8_transversalisation = request.POST.get('transversalisation', '')
    huitd.save()
    
    # Altérations
    huitd.alterations.all().delete()
    
    alt_docs = [
        'Inspection Sheet (PV)', 'Control Plan', 'Instruction Sheet (FI)',
        'Maintenance Plan', 'Audit Frequency', 'Workstation Documents Updated',
        'Process Improvement (Procedure / Instruction)', 'PFMEA',
        'Standardization of Tools and Equipment', 'Training Plan',
        'Deploy to Similar Products/Processes (Other Program)',
        'Deploy to Similar Products/Processes (Other APU)',
    ]
    
    for i, doc in enumerate(alt_docs):
        remarque = request.POST.get(f'alt_remark_{i}', '')
        pilote = request.POST.get(f'alt_pilote_{i}', '')
        deadline = request.POST.get(f'alt_deadline_{i}') or None
        
        if remarque or pilote or deadline:
            Alteration8D.objects.create(
                huitd=huitd,
                type_document=doc,
                remarque=remarque,
                pilote=pilote,
                deadline=deadline,
                ordre=i+1
            )
    
    messages.success(request, "✅ D8 - Transversalisation enregistrée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_decision(request, huitd):
    """Sauvegarde Décision HCIM & Clôture"""
    huitd.huitd_accepte = request.POST.get('huitd_accepte') == 'oui'
    huitd.decision_hcim = request.POST.get('decision_hcim', '')
    huitd.etat = request.POST.get('etat', 'OUVERT')
    huitd.fin_huitd = request.POST.get('fin_huitd') or None
    huitd.fin_huitd_signature = request.POST.get('fin_huitd_signature', '')
    
    if huitd.etat == 'CLOTURE' and not huitd.fin_huitd:
        huitd.fin_huitd = timezone.now().date()
    
    huitd.save()
    messages.success(request, "✅ Décision enregistrée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_general(request, huitd):
    huitd.numero_of = request.POST.get('numero_of', '')
    huitd.date_ouverture = request.POST.get('date_ouverture') or None
    huitd.designation_piece = request.POST.get('designation_piece', '')
    huitd.numero_article = request.POST.get('numero_article', '')
    huitd.numero_nc = request.POST.get('numero_nc', '')
    huitd.client = request.POST.get('client', '')
    huitd.lieu_detection = request.POST.get('lieu_detection', 'QUALITE')
    huitd.interne = request.POST.get('interne', '')
    huitd.save()
    messages.success(request, "✅ Infos générales enregistrées")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d1(request, huitd):
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
    if request.FILES.get('illustration_defectueux'): huitd.d1_illustration_defectueux = request.FILES['illustration_defectueux']
    if request.FILES.get('illustration_conforme'): huitd.d1_illustration_conforme = request.FILES['illustration_conforme']
    huitd.save()
    messages.success(request, "✅ D1 enregistré")
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
    huitd.d3_date = request.POST.get('d3_date') or None
    huitd.pilote = request.POST.get('pilote', '')
    huitd.pilote_fonction = request.POST.get('pilote_fonction', '')
    huitd.animateur = request.POST.get('animateur', '')
    huitd.animateur_fonction = request.POST.get('animateur_fonction', '')
    huitd.save()
    messages.success(request, "✅ D3 enregistré")
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
    huitd.d5_causes_occurrence = request.POST.get('d5_causes_occurrence', '')
    huitd.d5_causes_non_detection = request.POST.get('d5_causes_non_detection', '')
    huitd.save()
    messages.success(request, "✅ D5 enregistré")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

def _save_d6(request, huitd):
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
    for f in huitd.vrs.facteurs.all():
        f.facteur_probable = request.POST.get(f'vrs_facteur_{f.categorie}', '')
        f.parametre_mesurable = request.POST.get(f'vrs_parametre_{f.categorie}', '')
        f.standard_exigence = request.POST.get(f'vrs_standard_{f.categorie}', '')
        f.donnees_bonnes = request.POST.get(f'vrs_bonnes_{f.categorie}', '')
        f.donnees_mauvaises = request.POST.get(f'vrs_mauvaises_{f.categorie}', '')
        f.standard_suivi = request.POST.get(f'vrs_suivi_{f.categorie}') == 'on'
        f.standard_approprie = request.POST.get(f'vrs_appro_{f.categorie}') == 'on'
        f.lien_prouve = request.POST.get(f'vrs_lien_{f.categorie}') == 'on'
        f.facteur_prouve = request.POST.get(f'vrs_prouve_{f.categorie}') == 'on'
        f.save()
    messages.success(request, "✅ VRS enregistré")
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
    titre = request.POST.get('titre', '')
    description = request.POST.get('description_ev', '')
    fichier = request.FILES.get('fichier')
    if fichier:
        Evidence8D.objects.create(huitd=huitd, titre=titre, description=description, fichier=fichier)
        messages.success(request, "✅ Évidence ajoutée")
    else:
        messages.warning(request, "⚠️ Aucun fichier")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)

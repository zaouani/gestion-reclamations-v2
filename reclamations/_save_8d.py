def _save_d0(request, huitd):
    """Sauvegarde D0 - Identification"""
    huitd.ref = request.POST.get('ref', '')
    huitd.version = request.POST.get('version', '')
    huitd.date_ouverture = request.POST.get('date_ouverture') or None
    huitd.designation_piece = request.POST.get('designation_piece', '')
    huitd.numero_article = request.POST.get('numero_article', '')
    huitd.numero_of = request.POST.get('numero_of', '')
    huitd.numero_nc = request.POST.get('numero_nc', '')
    huitd.client = request.POST.get('client', '')
    huitd.lieu_detection = request.POST.get('lieu_detection', 'QUALITE')
    huitd.decision_8d = request.POST.get('decision_8d', 'OUI')
    huitd.save()
    messages.success(request, "✅ D0 - Identification sauvegardée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d1(request, huitd):
    """Sauvegarde D1 - Équipe"""
    huitd.pilote = request.POST.get('pilote', '')
    huitd.animateur = request.POST.get('animateur', '')
    huitd.save()
    
    # Participants
    participant_ids = request.POST.getlist('participant_id[]')
    roles = request.POST.getlist('role[]')
    noms = request.POST.getlist('nom[]')
    fonctions = request.POST.getlist('fonction[]')
    
    participants_conserves = []
    for i in range(len(noms)):
        if not noms[i].strip():
            continue
        pid = participant_ids[i] if i < len(participant_ids) else None
        if pid and pid.startswith('new_'):
            p = Participant8D.objects.create(huitd=huitd, nom=noms[i], role=roles[i] if i < len(roles) else '', fonction=fonctions[i] if i < len(fonctions) else '', ordre=i+1)
            participants_conserves.append(p.id)
        elif pid and pid.isdigit():
            try:
                p = Participant8D.objects.get(id=pid, huitd=huitd)
                p.nom = noms[i]
                p.role = roles[i] if i < len(roles) else ''
                p.fonction = fonctions[i] if i < len(fonctions) else ''
                p.ordre = i + 1
                p.save()
                participants_conserves.append(p.id)
            except Participant8D.DoesNotExist:
                pass
    
    huitd.participants.exclude(id__in=participants_conserves).delete()
    messages.success(request, "✅ D1 - Équipe sauvegardée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_d2(request, huitd):
    """Sauvegarde D2 - Caractérisation"""
    caract = huitd.caracterisation
    caract.description = request.POST.get('description', '')
    caract.probleme_connu = request.POST.get('probleme_connu') == 'on'
    caract.risque_similaire = request.POST.get('risque_similaire') == 'on'
    caract.risque_similaire_detail = request.POST.get('risque_similaire_detail', '')
    caract.tri_necessaire = request.POST.get('tri_necessaire') == 'on'
    caract.of_concernes = request.POST.get('of_concernes', '')
    caract.actions_suffisantes = request.POST.get('actions_suffisantes') == 'on'
    caract.quantite_rebutee = request.POST.get('quantite_rebutee', 'N/A')
    caract.quantite_retoucher = request.POST.get('quantite_retoucher', 'N/A')
    
    if request.FILES.get('illustration_defectueux'):
        caract.illustration_defectueux = request.FILES['illustration_defectueux']
    if request.FILES.get('illustration_conforme'):
        caract.illustration_conforme = request.FILES['illustration_conforme']
    
    caract.save()
    messages.success(request, "✅ D2 - Caractérisation sauvegardée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_5w2h(request, huitd):
    """Sauvegarde 5W2H"""
    w2h = huitd.cinq_w2h
    w2h.nom = request.POST.get('nom', '')
    w2h.site = request.POST.get('site', '')
    w2h.date = request.POST.get('date') or None
    
    # Vue Client
    w2h.quoi = request.POST.get('quoi', '')
    w2h.qui = request.POST.get('qui', '')
    w2h.ou = request.POST.get('ou', '')
    w2h.quand = request.POST.get('quand', '')
    w2h.comment = request.POST.get('comment', '')
    w2h.combien = request.POST.get('combien', '')
    w2h.pourquoi_probleme = request.POST.get('pourquoi_probleme', '')
    w2h.impact_logistique = request.POST.get('impact_logistique', '')
    w2h.autres_clients_livres = request.POST.get('autres_clients_livres', '')
    w2h.autres_clients_defaut = request.POST.get('autres_clients_defaut', '')
    
    # Vue Interne
    w2h.symptomes = request.POST.get('symptomes', '')
    w2h.defauts_ecartes = request.POST.get('defauts_ecartes', '')
    w2h.ou_cree = request.POST.get('ou_cree', '')
    w2h.quand_genere = request.POST.get('quand_genere', '')
    w2h.rework = request.POST.get('rework', '')
    w2h.detection_attendue = request.POST.get('detection_attendue', '')
    w2h.reinjection = request.POST.get('reinjection', '')
    w2h.probleme_connu = request.POST.get('probleme_connu', '')
    w2h.dernier_cas = request.POST.get('dernier_cas', '')
    
    w2h.save()
    messages.success(request, "✅ 5W2H sauvegardé")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_ishikawa(request, huitd):
    """Sauvegarde Ishikawa"""
    ish = huitd.ishikawa
    ish.designation = request.POST.get('designation', '')
    ish.nom = request.POST.get('nom', '')
    ish.site = request.POST.get('site', '')
    ish.date = request.POST.get('date') or None
    ish.save()
    
    facteur_ids = request.POST.getlist('facteur_id[]')
    facteurs_probables = request.POST.getlist('facteur_probable[]')
    parametres = request.POST.getlist('parametre_mesurable[]')
    standards = request.POST.getlist('standard_exigence[]')
    donnees_bonnes = request.POST.getlist('donnees_bonnes[]')
    donnees_mauvaises = request.POST.getlist('donnees_mauvaises[]')
    standards_suivis = request.POST.getlist('standard_suivi[]')
    standards_appro = request.POST.getlist('standard_approprie[]')
    liens_prouves = request.POST.getlist('lien_prouve[]')
    facteurs_prouves = request.POST.getlist('facteur_prouve[]')
    
    for i, fid in enumerate(facteur_ids):
        if fid and fid.isdigit():
            try:
                f = FacteurIshikawa.objects.get(id=fid, ishikawa=ish)
                f.facteur_probable = facteurs_probables[i] if i < len(facteurs_probables) else ''
                f.parametre_mesurable = parametres[i] if i < len(parametres) else ''
                f.standard_exigence = standards[i] if i < len(standards) else ''
                f.donnees_bonnes = donnees_bonnes[i] if i < len(donnees_bonnes) else ''
                f.donnees_mauvaises = donnees_mauvaises[i] if i < len(donnees_mauvaises) else ''
                f.standard_suivi = str(fid) in standards_suivis
                f.standard_approprie = str(fid) in standards_appro
                f.lien_prouve = str(fid) in liens_prouves
                f.facteur_prouve = str(fid) in facteurs_prouves
                f.save()
            except FacteurIshikawa.DoesNotExist:
                pass
    
    messages.success(request, "✅ Ishikawa sauvegardé")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_vrs(request, huitd):
    """Sauvegarde VRS"""
    vrs = huitd.vrs
    vrs.designation = request.POST.get('designation', '')
    vrs.nom = request.POST.get('nom', '')
    vrs.site = request.POST.get('site', '')
    vrs.date = request.POST.get('date') or None
    vrs.suivi = request.POST.get('suivi', 'PR-SM-06')
    vrs.save()
    messages.success(request, "✅ VRS sauvegardé")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_5p(request, huitd):
    """Sauvegarde 5 Pourquoi"""
    cinq_p_ids = request.POST.getlist('cinq_p_id[]')
    categories = request.POST.getlist('categorie[]')
    facteurs = request.POST.getlist('facteur_prouve[]')
    p1s = request.POST.getlist('pourquoi_1[]')
    p2s = request.POST.getlist('pourquoi_2[]')
    p3s = request.POST.getlist('pourquoi_3[]')
    p4s = request.POST.getlist('pourquoi_4[]')
    p5s = request.POST.getlist('pourquoi_5[]')
    
    conserves = []
    for i, pid in enumerate(cinq_p_ids):
        if pid and pid.startswith('new_'):
            cp = CinqP.objects.create(
                huitd=huitd,
                categorie=categories[i] if i < len(categories) else 'OCCURRENCE',
                facteur_prouve=facteurs[i] if i < len(facteurs) else '',
                pourquoi_1=p1s[i] if i < len(p1s) else '',
                pourquoi_2=p2s[i] if i < len(p2s) else '',
                pourquoi_3=p3s[i] if i < len(p3s) else '',
                pourquoi_4=p4s[i] if i < len(p4s) else '',
                pourquoi_5=p5s[i] if i < len(p5s) else '',
            )
            conserves.append(cp.id)
        elif pid and pid.isdigit():
            try:
                cp = CinqP.objects.get(id=pid, huitd=huitd)
                cp.categorie = categories[i] if i < len(categories) else cp.categorie
                cp.facteur_prouve = facteurs[i] if i < len(facteurs) else ''
                cp.pourquoi_1 = p1s[i] if i < len(p1s) else ''
                cp.pourquoi_2 = p2s[i] if i < len(p2s) else ''
                cp.pourquoi_3 = p3s[i] if i < len(p3s) else ''
                cp.pourquoi_4 = p4s[i] if i < len(p4s) else ''
                cp.pourquoi_5 = p5s[i] if i < len(p5s) else ''
                cp.save()
                conserves.append(cp.id)
            except CinqP.DoesNotExist:
                pass
    
    huitd.cinq_p.exclude(id__in=conserves).delete()
    messages.success(request, "✅ 5 Pourquoi sauvegardé")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_fh(request, huitd):
    """Sauvegarde Facteur Humain"""
    fh = huitd.facteur_humain
    fh.description = request.POST.get('description', '')
    fh.analyse = request.POST.get('analyse', '')
    fh.actions = request.POST.get('actions', '')
    fh.save()
    messages.success(request, "✅ Facteur Humain sauvegardé")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_actions(request, huitd):
    """Sauvegarde Plan d'actions"""
    action_ids = request.POST.getlist('action_id[]')
    types_action = request.POST.getlist('type_action[]')
    numeros_cause = request.POST.getlist('numero_cause[]')
    actions_list = request.POST.getlist('action[]')
    pilotes = request.POST.getlist('pilote[]')
    delais = request.POST.getlist('delai[]')
    statuts = request.POST.getlist('statut[]')
    
    conservees = []
    for i in range(len(actions_list)):
        if not actions_list[i].strip():
            continue
        aid = action_ids[i] if i < len(action_ids) else None
        if aid and aid.startswith('new_'):
            a = Action8D.objects.create(
                huitd=huitd,
                type_action=types_action[i] if i < len(types_action) else 'AC',
                numero_cause=numeros_cause[i] if i < len(numeros_cause) else '',
                action=actions_list[i],
                pilote=pilotes[i] if i < len(pilotes) else '',
                delai=delais[i] if i < len(delais) and delais[i] else None,
                statut=statuts[i] if i < len(statuts) else 'PLANIFIE',
                ordre=i+1
            )
            conservees.append(a.id)
        elif aid and aid.isdigit():
            try:
                a = Action8D.objects.get(id=aid, huitd=huitd)
                a.type_action = types_action[i] if i < len(types_action) else a.type_action
                a.numero_cause = numeros_cause[i] if i < len(numeros_cause) else ''
                a.action = actions_list[i]
                a.pilote = pilotes[i] if i < len(pilotes) else ''
                a.delai = delais[i] if i < len(delais) and delais[i] else None
                a.statut = statuts[i] if i < len(statuts) else a.statut
                a.ordre = i+1
                a.save()
                conservees.append(a.id)
            except Action8D.DoesNotExist:
                pass
    
    huitd.actions.exclude(id__in=conservees).delete()
    messages.success(request, "✅ Plan d'actions sauvegardé")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_alterations(request, huitd):
    """Sauvegarde Altérations"""
    alt_ids = request.POST.getlist('alt_id[]')
    types_doc = request.POST.getlist('type_document[]')
    descriptions = request.POST.getlist('description_alt[]')
    remarques = request.POST.getlist('remarque[]')
    pilotes = request.POST.getlist('pilote_alt[]')
    deadlines = request.POST.getlist('deadline[]')
    statuts = request.POST.getlist('statut_alt[]')
    
    conservees = []
    for i in range(len(descriptions)):
        if not descriptions[i].strip():
            continue
        aid = alt_ids[i] if i < len(alt_ids) else None
        if aid and aid.startswith('new_'):
            a = AlterationNecessaire.objects.create(
                huitd=huitd,
                type_document=types_doc[i] if i < len(types_doc) else '',
                description=descriptions[i],
                remarque=remarques[i] if i < len(remarques) else '',
                pilote=pilotes[i] if i < len(pilotes) else '',
                deadline=deadlines[i] if i < len(deadlines) and deadlines[i] else None,
                statut=statuts[i] if i < len(statuts) else 'Planifié',
                ordre=i+1
            )
            conservees.append(a.id)
        elif aid and aid.isdigit():
            try:
                a = AlterationNecessaire.objects.get(id=aid, huitd=huitd)
                a.type_document = types_doc[i] if i < len(types_doc) else a.type_document
                a.description = descriptions[i]
                a.remarque = remarques[i] if i < len(remarques) else ''
                a.pilote = pilotes[i] if i < len(pilotes) else ''
                a.deadline = deadlines[i] if i < len(deadlines) and deadlines[i] else None
                a.statut = statuts[i] if i < len(statuts) else a.statut
                a.ordre = i+1
                a.save()
                conservees.append(a.id)
            except AlterationNecessaire.DoesNotExist:
                pass
    
    huitd.alterations.exclude(id__in=conservees).delete()
    messages.success(request, "✅ Altérations sauvegardées")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_transversalisation(request, huitd):
    """Sauvegarde Transversalisation"""
    huitd.transversalisation = request.POST.get('transversalisation', '')
    huitd.save()
    messages.success(request, "✅ Leçons apprises sauvegardées")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_decision(request, huitd):
    """Sauvegarde Décision"""
    huitd.decision_hcim = request.POST.get('decision_hcim', '')
    huitd.huitd_accepte = request.POST.get('huitd_accepte') == 'on'
    huitd.etat = request.POST.get('etat', 'OUVERT')
    
    if huitd.etat == 'CLOTURE':
        huitd.fin_huitd = request.POST.get('fin_huitd') or timezone.now().date()
        huitd.fin_huitd_signature = request.POST.get('fin_huitd_signature', '')
    
    huitd.save()
    messages.success(request, "✅ Décision sauvegardée")
    return redirect('reclamations:huitd_modifier', pk=huitd.id)


def _save_evidences(request, huitd):
    """Sauvegarde Évidences"""
    titre = request.POST.get('titre', '')
    description = request.POST.get('description_ev', '')
    
    if request.FILES.get('fichier'):
        Evidence8D.objects.create(
            huitd=huitd,
            titre=titre,
            description=description,
            fichier=request.FILES['fichier']
        )
        messages.success(request, "✅ Évidence ajoutée")
    else:
        messages.warning(request, "⚠️ Aucun fichier sélectionné")
    
    return redirect('reclamations:huitd_modifier', pk=huitd.id)



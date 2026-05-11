from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, DecimalValidator
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal


class UAP(models.Model):
    """Unité Autonome de Production"""
    nom = models.CharField(max_length=100, unique=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "UAP"
        verbose_name_plural = "UAP"
    
    def __str__(self):
        return self.nom

class Site(models.Model):
    """Site de production"""
    nom = models.CharField(max_length=100, unique=True)
    uap = models.ForeignKey(UAP, on_delete=models.PROTECT, related_name='sites')
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
    
    def __str__(self):
        return f"{self.nom}"

class Client(models.Model):
    """Client"""
    nom = models.CharField(max_length=100, unique=True)
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
    
    def __str__(self):
        return self.nom

class Programme(models.Model):
    """Programme lié à plusieurs clients"""
    nom = models.CharField("Nom du programme", max_length=100, unique=True)  # Unique globalement
    clients = models.ManyToManyField(Client, related_name='programmes', blank=True)  # Plusieurs clients
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Programme"
        verbose_name_plural = "Programmes"
        ordering = ['nom']
    
    def __str__(self):
        return f"{self.nom}"
    
    def get_clients_list(self):
        """Retourne la liste des clients sous forme de chaîne"""
        return ", ".join([client.nom for client in self.clients.all()])

class SiteClient(models.Model):
    """Site/Établissement du client"""
    nom = models.CharField(max_length=200)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sites_client')
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    code_postal = models.CharField(max_length=20, blank=True)
    pays = models.CharField(max_length=100, blank=True, default='France')
    contact_principal = models.CharField(max_length=200, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Site client"
        verbose_name_plural = "Sites clients"
        unique_together = ['nom', 'client']  # Un client ne peut pas avoir deux sites avec le même nom
        ordering = ['client', 'nom']
    
    def __str__(self):
        return f"{self.nom} ({self.client.nom})"

class Produit(models.Model):
    """Produit (référence unique)"""
    product_number = models.CharField("N° Produit", max_length=50, unique=True)
    designation = models.CharField(max_length=200, blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"
    
    def __str__(self):
        return self.product_number

class Reclamation(models.Model):
    """En-tête de réclamation"""
    
    TYPE_NC_CHOICES = [
        ('FOURNISSEUR', 'Fournisseur'),
        ('LOGISTIQUE', 'Logistique'),
        ('TRANSPORT', 'Transport'),
        ('TECHNIQUE', 'Technique'),
        ('Stockage','Stockage'),
    ]
    
    ETAT_CHOICES = [
        ('OUVERT', 'Ouvert'),
        ('EN_COURS', 'En cours'),
        ('CLOTURE', 'Clôturé'),
    ]

    IMPUTATION_CHOICES = [
        ('Vérification Encours','Vérification Encours'),
        ('CIM', 'CIM'),
        ('CIB', 'CIB'),
        ('CLIENT', 'CLIENT'),
        ('ALERTE', 'ALERTE'),
        ('KTN','KTN'),
    ]
    
    numero_reclamation = models.CharField("N° Réclamation", max_length=50, unique=True)
    date_reclamation = models.DateField(default=timezone.now)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='reclamations')
    site_client = models.ForeignKey('SiteClient', on_delete=models.SET_NULL, null=True, blank=True, related_name='reclamations')
    programme = models.ForeignKey( Programme, on_delete=models.PROTECT, related_name='reclamations', null=True, blank=True)
    imputation = models.CharField("Imputation", max_length=20, choices=IMPUTATION_CHOICES, default='CIM')
    type_nc = models.CharField("Type NC", max_length=20, choices=TYPE_NC_CHOICES, default='TECHNIQUE')
    numero_4d = models.CharField("N° 4D", max_length=50, blank=True, null=True, help_text="Numéro de la démarche 4D" )
    numero_8d = models.CharField("N° 8D", max_length=50, blank=True, null=True,help_text="Numéro de la démarche 8D" )
    # États
    etat_4d = models.CharField("État 4D", max_length=20, choices=ETAT_CHOICES, default='OUVERT')
    etat_8d = models.CharField("État 8D", max_length=20, choices=ETAT_CHOICES, default='OUVERT')
    
    # Métadonnées
    evidence = models.TextField(blank=True)
    me = models.BooleanField("ME", default=False)
    cloture = models.BooleanField(default=False)
    date_cloture = models.DateField(null=True, blank=True)
    date_cloture_4d = models.DateField(null=True, blank=True)
    date_cloture_8d = models.DateField(null=True, blank=True)
    
    # Objectifs et décisions
    decision = models.TextField(blank=True)
    nqc = models.DecimalField("Coût NQC (MAD)", max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    
    # Timestamps
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reclamations_crees'
    )
    class Meta:
        verbose_name = "Réclamation"
        verbose_name_plural = "Réclamations"
        ordering = ['-date_reclamation', '-id']
    
    def __str__(self):
        return f"{self.numero_reclamation} - {self.client.nom}"
    
    def save(self, *args, **kwargs):
            # Remplir automatiquement les dates de clôture
            today = timezone.now().date()
            
            # Si l'état 4D passe à CLOTURE et que la date n'est pas déjà remplie
            if self.etat_4d == 'CLOTURE' and not self.date_cloture_4d:
                self.date_cloture_4d = today
            
            # Si l'état 8D passe à CLOTURE et que la date n'est pas déjà remplie
            if self.etat_8d == 'CLOTURE' and not self.date_cloture_8d:
                self.date_cloture_8d = today
            
            # Si la réclamation est clôturée et que la date n'est pas déjà remplie
            if self.cloture and not self.date_cloture:
                self.date_cloture = today
            
            super().save(*args, **kwargs)

class LigneReclamation(models.Model):
    """Lignes de réclamation"""
    reclamation = models.ForeignKey(Reclamation, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name='lignes_reclamation')
    quantite = models.IntegerField(validators=[MinValueValidator(1)])
    description_non_conformite = models.TextField("Description non-conformité")
    commentaire = models.TextField(blank=True)
    site = models.ForeignKey('Site', on_delete=models.PROTECT, related_name='lignes_reclamation', null=True, blank=True)
    uap_concernee = models.ForeignKey(UAP, on_delete=models.SET_NULL, null=True, blank=True, related_name='lignes_reclamation')
    
    class Meta:
        verbose_name = "Ligne de réclamation"
        verbose_name_plural = "Lignes de réclamation"
        unique_together = ['reclamation', 'produit']
    
    def __str__(self):
        return f"{self.reclamation.numero_reclamation} - {self.produit.product_number}"
    def save(self, *args, **kwargs):
        # Si un site est sélectionné, définir automatiquement l'UAP correspondante
        if self.site and not self.uap_concernee:
            self.uap_concernee = self.site.uap
        super().save(*args, **kwargs)

class NonConformite(models.Model):
    """Non-conformité individuelle liée à une ligne de réclamation"""
    ligne_reclamation = models.ForeignKey(
        'LigneReclamation', 
        on_delete=models.CASCADE, 
        related_name='non_conformites'
    )
    description = models.TextField("Description de la non-conformité")
    quantite = models.IntegerField(
        "Quantité concernée",
        validators=[MinValueValidator(1)],
        default=1
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Non-conformité"
        verbose_name_plural = "Non-conformités"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.description[:50]} - {self.quantite} pcs"
        
class ObjectifsAnnuel(models.Model):
    """Objectifs par année et par site"""
    annee = models.IntegerField("Année", default=timezone.now().year)
    site = models.ForeignKey('Site', on_delete=models.CASCADE, related_name='objectifs', null=True, blank=True)  # D'abord nullable
    objectif_rebut = models.DecimalField(
        "Objectif rebut (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    objectif_ppm_externe = models.IntegerField(
        "Objectif PPM Externe",
        default=0,
        validators=[MinValueValidator(0)]
    )
    objectif_rework = models.DecimalField(
        "Objectif Rework (%)",
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Objectif annuel"
        verbose_name_plural = "Objectifs annuels"
        ordering = ['-annee', 'site__nom']
        unique_together = ['annee', 'site']
    
    def __str__(self):
        if self.site:
            return f"Objectifs {self.annee} - {self.site.nom}"
        return f"Objectifs {self.annee}"

class Livraison(models.Model):
    """Livraisons clients pour le calcul PPM"""
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='livraisons')
    date_livraison = models.DateField()
    quantite_livree = models.IntegerField(validators=[MinValueValidator(1)])
    numero_bon_livraison = models.CharField(max_length=100, blank=True)
    reference_commande = models.CharField(max_length=100, blank=True)
    remarques = models.TextField(blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Livraison"
        verbose_name_plural = "Livraisons"
        ordering = ['-date_livraison']
    
    def __str__(self):
        return f"{self.client.nom} - {self.date_livraison} - {self.quantite_livree} pcs"

#Gestion des 8d
# models.py - Modèle 8D complet avec toutes les méthodes

class HuitD(models.Model):
    """Formulaire 8D - Structure maîtresse"""
    
    ETAT_CHOICES = [
        ('OUVERT', 'Ouvert'),
        ('EN_COURS', 'En cours'),
        ('CLOTURE', 'Clôturé'),
    ]
    
    DECISION_CHOICES = [('OUI', 'Oui'), ('NON', 'Non')]
    
    LIEU_CHOICES = [
        ('QUALITE', 'Qualité / Quality'),
        ('PRODUCTION', 'Production'),
        ('CLIENT', 'Client / Customer'),
        ('FOURNISSEUR', 'Fournisseur / Supplier'),
    ]
    
    # ========== LIAISON ==========
    reclamation = models.OneToOneField('Reclamation', on_delete=models.CASCADE, related_name='huitd')
    
    # ========== EN-TÊTE ==========
    ref = models.CharField("Réf", max_length=50, blank=True)
    version = models.CharField("Version", max_length=20, blank=True)
    date_maj = models.DateField("Date MàJ", auto_now=True)
    
    # ========== INFORMATIONS GÉNÉRALES ==========
    numero_of = models.CharField("N° OF", max_length=50, blank=True)
    date_ouverture = models.DateField("Date d'ouverture / Opening Date", null=True, blank=True)
    designation_piece = models.CharField("Désignation pièces / Parts Designation", max_length=200, blank=True)
    numero_article = models.CharField("N° article", max_length=50, blank=True)
    numero_nc = models.CharField("N° NC", max_length=50, blank=True)
    client = models.CharField("Client", max_length=100, blank=True)
    interne = models.CharField("Interne / Internal", max_length=20, choices=LIEU_CHOICES, blank=True)
    lieu_detection = models.CharField("Lieu de détection / Detection Site", max_length=20, choices=LIEU_CHOICES, default='QUALITE')
    
    # ========== D1 - 5W2H / Description du problème ==========
    d1_qui = models.TextField("Qui ? / Who ?", blank=True)
    d1_quoi = models.TextField("Quoi ? / What ?", blank=True)
    d1_ou = models.TextField("Où ? / Where ?", blank=True)
    d1_quand = models.TextField("Quand ? / When ?", blank=True)
    d1_comment = models.TextField("Comment ? / How ?", blank=True)
    d1_combien = models.TextField("Combien ? / How much ?", blank=True)
    d1_pourquoi = models.TextField("Pourquoi ? / Why ?", blank=True)
    
    # Caractérisation
    d1_caracterisation = models.TextField("Caractérisation du défaut / Characterization of the defect", blank=True)
    d1_probleme_connu = models.BooleanField("Le problème est-il déjà connu ? / Is the problem already known?", default=False)
    d1_risque = models.BooleanField("Risque sur produit/process similaire ?", default=False)
    d1_risque_detail = models.TextField("Si oui, sur lequel ?", blank=True)
    
    # Illustrations
    d1_illustration_defectueux = models.ImageField("Illustration produit défectueux", upload_to='8d/d1/', blank=True)
    d1_illustration_conforme = models.ImageField("Illustration produit conforme", upload_to='8d/d1/', blank=True)
    
    # ========== D2 - Actions d'urgence ==========
    d2_date = models.DateField("Date D2", null=True, blank=True)
    d2_actions = models.TextField("Actions envisagées pour éviter la non détection", blank=True)
    d2_tri = models.BooleanField("Un tri est-il nécessaire ? / Is sorting necessary?", default=False)
    d2_of_concernes = models.TextField("OF concernés / OF concerned", blank=True)
    d2_quantite_rebutee = models.CharField("Qté rebutée / Scrap Qty", max_length=50, default='N/A')
    d2_quantite_retoucher = models.CharField("Qté à retoucher / Qty to be reworked", max_length=50, default='N/A')
    
    # ========== D3 - Équipe ==========
    d3_date = models.DateField("Date D3", null=True, blank=True)
    pilote = models.CharField("Pilote / Leader", max_length=100, blank=True)
    pilote_fonction = models.CharField("Fonction pilote", max_length=100, blank=True)
    animateur = models.CharField("Animateur / Animator", max_length=100, blank=True)
    animateur_fonction = models.CharField("Fonction animateur", max_length=100, blank=True)
    
    # ========== D4 - Analyse préliminaire ==========
    d4_date = models.DateField("Date D4", null=True, blank=True)
    d4_causes_apparition = models.TextField("Cause(s) probable(s) d'apparition du défaut ?", blank=True)
    d4_causes_non_detection = models.TextField("Cause(s) probable(s) de non détection ?", blank=True)
    decision_8d = models.CharField("Engager un 8D ?", max_length=3, choices=DECISION_CHOICES, default='OUI')
    
    # ========== D5 - Causes racines (liens vers méthodes) ==========
    d5_causes_occurrence = models.TextField("Causes racines de l'occurrence", blank=True)
    d5_causes_non_detection = models.TextField("Causes racines de la non détection", blank=True)
    
    # ========== D6 - Actions (géré par Action8D) ==========
    
    # ========== D7 - Vérification ==========
    d7_verification = models.TextField("Comment est vérifié l'efficacité des actions (qui ? comment ?) ?", blank=True)
    d7_suffisant = models.TextField("Ces actions sont-elles suffisantes pour éradiquer le problème ?", blank=True)
    
    # ========== D8 - Transversalisation ==========
    d8_transversalisation = models.TextField("Sur quels périmètres peut-on transversaliser les leçons apprises ?", blank=True)
    
    # ========== DÉCISION HCIM ==========
    huitd_accepte = models.BooleanField("8D accepté / 8D Report Accepted", default=False)
    decision_hcim = models.CharField("Non, exigé par / required by", max_length=100, blank=True)
    
    # ========== CLÔTURE ==========
    etat = models.CharField("État", max_length=20, choices=ETAT_CHOICES, default='OUVERT')
    fin_huitd = models.DateField("Fin du 8D / Closure of 8D", null=True, blank=True)
    fin_huitd_signature = models.CharField("Date & Signature", max_length=100, blank=True)
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "8D"
        verbose_name_plural = "8Ds"
    
    def __str__(self):
        return f"8D - {self.reclamation.numero_reclamation}"


class Participant8D(models.Model):
    """Participants équipe 8D"""
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='participants')
    role = models.CharField("Rôle / Role", max_length=100, blank=True)
    nom = models.CharField("Nom / Name", max_length=100)
    fonction = models.CharField("Fonction / Function", max_length=100, blank=True)
    ordre = models.IntegerField("Ordre", default=1)
    
    class Meta:
        ordering = ['ordre']


# ============================================================
# MÉTHODES D'ANALYSE DES CAUSES RACINES
# ============================================================

class CinqW2H(models.Model):
    """5W2H / CARACTERISATION - Vue Client + Vue Interne"""
    
    huitd = models.OneToOneField(HuitD, on_delete=models.CASCADE, related_name='cinq_w2h')
    
    # Infos générales
    nom = models.CharField("Nom / Name", max_length=100, blank=True)
    site = models.CharField("Site", max_length=100, blank=True)
    date = models.DateField("Date", null=True, blank=True)
    suivi = models.CharField("Suivant", max_length=50, default="PR-SM-06", blank=True)
    
    # === CUSTOMER VIEW / CARACTERISATION CLIENT ===
    c_what_happened = models.TextField("What happened ? / Que s'est-il passé ?", blank=True)
    c_who_detected = models.TextField("Who detected it? / Qui a détecté le problème ?", blank=True)
    c_where_detected = models.TextField("Where was it detected? / Où a-t-il été détecté ?", blank=True)
    c_when_detected = models.TextField("When did it happen? / Quand a-t-il été détecté ?", blank=True)
    c_how_detected = models.TextField("How was it detected? / Comment a-t-il été détecté ?", blank=True)
    c_how_many = models.TextField("How many were detected? / Combien de cas ont été détectés ?", blank=True)
    c_why_problem = models.TextField("Why is it a problem ? / Pourquoi est-ce un problème ?", blank=True)
    c_logistic_impact = models.TextField("What is the logistic impact on the customer ? / Quel est l'impact logistique sur le client ?", blank=True)
    c_other_customers_delivered = models.TextField("Was the product delivered to other customer ? / A quels autres Client le produit a-t-il été livré ?", blank=True)
    c_other_customers_defect = models.TextField("Was the defect reported by other customers ? / Le défaut a-t-il été rapporté par d'autres clients ?", blank=True)
    
    # === HCIM VIEW / CARACTERISATION INTERNE ===
    h_symptoms = models.TextField("What are the symptoms ? / De quoi s'agit-il ?", blank=True)
    h_defects_ruled_out = models.TextField("Which defects can be crossed out straightaway ? / Quel type de défaut peut être écarté d'emblée ?", blank=True)
    h_where_created = models.TextField("Where was the defect created amongst the operations ? / Où le défaut a-t-il pu être créé ?", blank=True)
    h_when_generated = models.TextField("When was the problem internally generated ? / Quand le problème a-t-il été généré en interne ?", blank=True)
    h_rework = models.TextField("Are the bad parts from a reworked process? / Les pièces mauvaises sont-elles issues d'une gamme rework ?", blank=True)
    h_detection_expected = models.TextField("At which operation should the problem have been detected ? / A quel stade le défaut est-il censé être détecté ?", blank=True)
    h_reinjection = models.TextField("Are we capturing the defect when reinjecting products in the normal process ? / Le produit non conforme ré-introduit dans le processus est-il détecté par celui-ci ?", blank=True)
    h_known_problem = models.TextField("Is the non conformity a known problem, a recurrent problem, internally and/or externally ? / La non-conformité est-elle connue, récurrente en externe ou en interne ?", blank=True)
    h_last_reported = models.TextField("When was the last reported problem? / A quelle date remonte le dernier cas ?", blank=True)
    
    class Meta:
        verbose_name = "5W2H"
        verbose_name_plural = "5W2H"


class CauseIshikawa(models.Model):
    """Causes du diagramme Ishikawa 6M (Arêtes de poisson)"""
    
    TYPE_CHOICES = [
        ('OCCURRENCE', 'Occurrence'),
        ('NON_DETECTION', 'No Detection'),
    ]
    
    CATEGORIE_CHOICES = [
        ('A', 'A - Milieu / Environment'),
        ('B', 'B - Méthodes / Methods'),
        ('C', 'C - Moyens / Resources'),
        ('D', 'D - Main d\'œuvre / Personnel'),
        ('E', 'E - Matières / Materials'),
        ('F', 'F - Mesures / Measures'),
    ]
    
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='causes_ishikawa')
    categorie = models.CharField("Catégorie 6M", max_length=1, choices=CATEGORIE_CHOICES)
    cause = models.TextField("Facteur / Factor")
    type_cause = models.CharField("Type", max_length=15, choices=TYPE_CHOICES, default='OCCURRENCE')
    ordre = models.IntegerField("Ordre", default=1)
    
    class Meta:
        ordering = ['categorie', 'ordre']
        verbose_name = "Cause Ishikawa"
        verbose_name_plural = "Causes Ishikawa"


class VRS(models.Model):
    """Verification of Standards (VRS)"""
    
    huitd = models.OneToOneField(HuitD, on_delete=models.CASCADE, related_name='vrs')
    
    # Infos générales
    designation = models.CharField("Designation", max_length=200, blank=True)
    nom = models.CharField("Nom / Name", max_length=100, blank=True)
    site = models.CharField("Site", max_length=100, blank=True)
    date = models.DateField("Date", null=True, blank=True)
    suivi = models.CharField("Suivant", max_length=50, default="PR-SM-06", blank=True)
    
    class Meta:
        verbose_name = "VRS"
        verbose_name_plural = "VRS"


class FacteurVRS(models.Model):
    """Facteurs du tableau VRS pour chaque 6M"""
    
    CATEGORIE_CHOICES = [
        ('A', 'A - Milieu / Environment'),
        ('B', 'B - Méthodes / Methods'),
        ('C', 'C - Moyens / Resources'),
        ('D', 'D - Main d\'œuvre / Personnel'),
        ('E', 'E - Matières / Materials'),
        ('F', 'F - Mesures / Measures'),
    ]
    
    vrs = models.ForeignKey(VRS, on_delete=models.CASCADE, related_name='facteurs')
    categorie = models.CharField("Catégorie 6M", max_length=1, choices=CATEGORIE_CHOICES)
    facteur_probable = models.TextField("Facteur probable / Probable factor", blank=True)
    parametre_mesurable = models.TextField("Paramètre mesurable / Is there a measurable parameter", blank=True)
    standard_exigence = models.TextField("Standard ou exigences / What is the standard or requirement", blank=True)
    donnees_bonnes = models.TextField("Données réelles (bonnes) / Real data (good parts)", blank=True)
    donnees_mauvaises = models.TextField("Données réelles (mauvaises) / Real data (bad parts)", blank=True)
    standard_suivi = models.BooleanField("Standard suivi ? / Is the standard followed?", default=False)
    standard_approprie = models.BooleanField("Standard approprié ? / Is the standard appropriate", default=False)
    lien_prouve = models.BooleanField("Lien prouvé ? / Proven location", default=False)
    facteur_prouve = models.BooleanField("Facteur prouvé / Proven factor", default=False)
    
    class Meta:
        ordering = ['categorie']


class CauseCinqP(models.Model):
    """Analyse 5 WHY"""
    
    TYPE_CHOICES = [
        ('OCCURRENCE', 'Occurrence'),
        ('NON_DETECTION', 'No Detection'),
    ]
    
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='causes_5p')
    type_cause = models.CharField("Type", max_length=15, choices=TYPE_CHOICES)
    facteur_prouve = models.CharField("Facteur prouvé / Proven factor", max_length=10, blank=True)
    pourquoi_1 = models.TextField("1. Pourquoi ? / Why?", blank=True)
    pourquoi_2 = models.TextField("2. Pourquoi ? / Why?", blank=True)
    pourquoi_3 = models.TextField("3. Pourquoi ? / Why?", blank=True)
    pourquoi_4 = models.TextField("4. Pourquoi ? / Why?", blank=True)
    pourquoi_5 = models.TextField("5. Pourquoi ? / Why?", blank=True)
    
    class Meta:
        ordering = ['type_cause', 'facteur_prouve']
        verbose_name = "5 Pourquoi"
        verbose_name_plural = "5 Pourquoi"


class FacteurHumain(models.Model):
    """Human Factors Cause Analysis"""
    
    CATEGORIE_CHOICES = [
        ('1', '1. Moyens et outils / Means and tools'),
        ('2', '2. Conditions de travail / Working conditions'),
        ('3', '3. Autres facteurs / Other factors'),
    ]
    
    huitd = models.OneToOneField(HuitD, on_delete=models.CASCADE, related_name='facteur_humain')
    designation = models.CharField("Designation", max_length=200, blank=True)
    nom = models.CharField("Nom / Name", max_length=100, blank=True)
    site = models.CharField("Site", max_length=100, blank=True)
    date = models.DateField("Date", null=True, blank=True)
    suivi = models.CharField("Suivant", max_length=50, default="PR-SM-06", blank=True)
    
    class Meta:
        verbose_name = "Facteur Humain"
        verbose_name_plural = "Facteurs Humains"


class EvaluationFacteurHumain(models.Model):
    """Évaluation détaillée des facteurs humains"""
    
    facteur_humain = models.ForeignKey(FacteurHumain, on_delete=models.CASCADE, related_name='evaluations')
    categorie = models.CharField("Catégorie", max_length=1, choices=[
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
    ])
    numero_critere = models.CharField("N° Critère", max_length=10)
    critere = models.TextField("Criteria / Critères")
    evaluation = models.CharField("Evaluation", max_length=100, blank=True)
    commentaire = models.TextField("Comments / Commentaires", blank=True)
    
    class Meta:
        ordering = ['categorie', 'numero_critere']


# ============================================================
# ACTIONS ET STANDARDISATION
# ============================================================

class Action8D(models.Model):
    """Plan d'actions 8D"""
    
    TYPE_CHOICES = [
        ('CORRECTIVE', 'AC - Action Corrective'),
        ('PREVENTIVE', 'AP - Action Préventive'),
    ]
    
    STATUT_CHOICES = [
        ('PLANIFIE', 'Planifié'),
        ('EN_COURS', 'En cours'),
        ('REALISE', 'Réalisé'),
        ('EFFICACE', 'Efficace'),
    ]
    
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='actions')
    type_action = models.CharField("Type", max_length=15, choices=TYPE_CHOICES, default='CORRECTIVE')
    numero_cause = models.CharField("Causes retenues / Causes retained", max_length=10, blank=True)
    action = models.TextField("Actions : occurrence - non détection")
    pilote = models.CharField("Pilote", max_length=100, blank=True)
    delai_semaines = models.CharField("Délai/Deadline", max_length=50, blank=True)
    statut = models.CharField("Statut / Status", max_length=20, choices=STATUT_CHOICES, default='PLANIFIE')
    ordre = models.IntegerField("Ordre", default=1)
    
    class Meta:
        ordering = ['ordre']


class Alteration8D(models.Model):
    """Altérations nécessaires (standardisation)"""
    
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='alterations')
    type_document = models.CharField("Alteration Necessary", max_length=200)
    remarque = models.TextField("Remark", blank=True)
    pilote = models.CharField("Pilot", max_length=100, blank=True)
    deadline = models.DateField("Deadline", null=True, blank=True)
    ordre = models.IntegerField("Ordre", default=1)
    
    class Meta:
        ordering = ['ordre']


class Evidence8D(models.Model):
    """Évidences / Pièces jointes"""
    
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='evidences')
    titre = models.CharField("Titre", max_length=200)
    fichier = models.FileField("Fichier", upload_to='8d/evidences/')
    description = models.TextField("Description", blank=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_ajout']
#Gestion des actions
class AnalyseNC(models.Model):
    """Analyse des causes racines et actions par non-conformité"""
    
    non_conformite = models.OneToOneField(
        NonConformite, 
        on_delete=models.CASCADE, 
        related_name='analyse'
    )
    
    # Cause racine
    cause_racine = models.TextField("Cause racine identifiée", blank=True)
    methode_analyse = models.CharField(
        "Méthode d'analyse", 
        max_length=50, 
        blank=True,
        choices=[
            ('5P', '5 Pourquoi'),
            ('ISHIKAWA', 'Ishikawa'),
            ('PARETO', 'Pareto'),
            ('AUTRE', 'Autre'),
        ]
    )
    
    # Actions
    actions_proposees = models.TextField("Actions proposées", blank=True, 
        help_text="Actions qui seront suivies dans le PDCA")
    
    # Statut
    statut = models.CharField(
        "Statut de l'analyse", 
        max_length=20,
        choices=[
            ('A_FAIRE', 'À faire'),
            ('EN_COURS', 'En cours'),
            ('TERMINE', 'Terminé'),
        ],
        default='A_FAIRE'
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Analyse NC"
        verbose_name_plural = "Analyses NC"
    
    def __str__(self):
        return f"Analyse - {self.non_conformite.description[:50]}"
    
    @property
    def reclamation(self):
        return self.non_conformite.ligne_reclamation.reclamation

class ActionPDCA(models.Model):
    """Action PDCA issue de l'analyse des NC"""
    
    STATUT_CHOICES = [
        ('PLAN', 'Planifié'),
        ('DO', 'En cours'),
        ('CHECK', 'En vérification'),
        ('ACT', 'Standardisé'),
        ('CLOTURE', 'Clôturé'),
    ]
    
    PRIORITE_CHOICES = [
        ('CRITIQUE', '🔴 Critique'),
        ('ELEVEE', '🟠 Élevée'),
        ('MOYENNE', '🟡 Moyenne'),
        ('BASSE', '🟢 Basse'),
    ]
    
    CATEGORIE_CHOICES = [
        ('QUALITE', 'Qualité'),
        ('PROCESS', 'Process'),
        ('FORMATION', 'Formation'),
        ('MAINTENANCE', 'Maintenance'),
        ('FOURNISSEUR', 'Fournisseur'),
        ('DOCUMENTATION', 'Documentation'),
        ('CONTROLE', 'Contrôle'),
        ('AUTRE', 'Autre'),
    ]
    
    # Liens
    analyse_nc = models.ForeignKey(
        AnalyseNC, 
        on_delete=models.CASCADE, 
        related_name='actions_pdca'
    )
    
    # Description
    titre = models.CharField("Titre de l'action", max_length=200)
    description = models.TextField("Description détaillée", blank=True)
    categorie = models.CharField("Catégorie", max_length=20, choices=CATEGORIE_CHOICES, default='AUTRE')
    
    # Planification
    responsable = models.CharField("Responsable", max_length=100)
    date_debut = models.DateField("Date début", null=True, blank=True)
    date_cible = models.DateField("Date cible")
    date_realisation = models.DateField("Date réalisation", null=True, blank=True)
    priorite = models.CharField("Priorité", max_length=20, choices=PRIORITE_CHOICES, default='MOYENNE')
    
    # Suivi
    statut = models.CharField("Statut PDCA", max_length=20, choices=STATUT_CHOICES, default='PLAN')
    pourcentage_avancement = models.IntegerField("% Avancement", default=0)
    
    # Évaluation
    efficacite = models.CharField(
        "Efficacité", 
        max_length=20,
        choices=[
            ('EFFICACE', 'Efficace'),
            ('PARTIEL', 'Partiellement efficace'),
            ('INEFFICACE', 'Inefficace'),
            ('NON_EVALUE', 'Non évaluée'),
        ],
        default='NON_EVALUE'
    )
    commentaire_efficacite = models.TextField("Commentaire sur l'efficacité", blank=True)
    date_evaluation = models.DateField("Date d'évaluation", null=True, blank=True)
    
    # Vérification
    critere_succes = models.TextField("Critères de succès", blank=True)
    indicateur_avant = models.CharField("Indicateur avant", max_length=100, blank=True)
    valeur_avant = models.CharField("Valeur avant", max_length=50, blank=True)
    indicateur_apres = models.CharField("Indicateur après", max_length=100, blank=True)
    valeur_apres = models.CharField("Valeur après", max_length=50, blank=True)
    resultat_obtenu = models.TextField("Résultat obtenu", blank=True)
    
    # Standardisation
    document_modifie = models.CharField("Document modifié", max_length=200, blank=True)
    formation_realisee = models.BooleanField("Formation réalisée", default=False)
    
    # Commentaires
    commentaires = models.TextField("Commentaires", blank=True)
    blocage = models.TextField("Points de blocage", blank=True)
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Action PDCA"
        verbose_name_plural = "Actions PDCA"
        ordering = ['priorite', 'date_cible']
    
    def __str__(self):
        return f"[{self.get_priorite_display()}] {self.titre[:60]}"
    
    @property
    def en_retard(self):
        if self.date_realisation:
            return False
        return self.date_cible < timezone.now().date()
    
    @property
    def delai_restant(self):
        if self.date_realisation:
            return 0
        delta = self.date_cible - timezone.now().date()
        return delta.days
    
    @property
    def reclamation(self):
        return self.analyse_nc.non_conformite.ligne_reclamation.reclamation

#========= Gestion des FAIs =============

class ArticleFAI(models.Model):
    """Article suivi pour FAI"""
    STATUT_CHOICES = [
        ('INFO', 'Information'),
        ('ALERTE', 'Alerte'),
        ('URGENT', 'Urgent'),
        ('CRITIQUE', 'Critique'),
    ]
    
    produit = models.OneToOneField('Produit', on_delete=models.CASCADE, related_name='fai_article')
    numero_of = models.CharField("N° OF", max_length=50, blank=True)
    derniere_production = models.DateField("Date dernière production", null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='INFO')
    date_analyse = models.DateField("Date d'analyse", auto_now=True)
    commentaire = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Article FAI"
        verbose_name_plural = "Articles FAI"
        ordering = ['-derniere_production']
    
    def __str__(self):
        return f"{self.produit.product_number} - {self.get_statut_display()}"

class HistoriqueImportFAI(models.Model):
    """Historique des imports FAI"""
    date_import = models.DateTimeField(auto_now_add=True)
    fichier_nom = models.CharField(max_length=255)
    lignes_importees = models.IntegerField()
    lignes_modifiees = models.IntegerField()
    erreurs = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Historique import FAI"
        verbose_name_plural = "Historiques import FAI"
        ordering = ['-date_import']
    
    def __str__(self):
        return f"Import du {self.date_import.strftime('%d/%m/%Y %H:%M')} - {self.lignes_importees} lignes"
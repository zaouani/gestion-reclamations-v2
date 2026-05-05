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

class HuitD(models.Model):
    """Modèle principal 8D"""
    ETAT_CHOICES = [
        ('OUVERT', 'Ouvert'),
        ('EN_COURS', 'En cours'),
        ('CLOTURE', 'Clôturé'),
    ]
    
    DECISION_8D_CHOICES = [
        ('OUI', 'Oui'),
        ('NON', 'Non - Exigé par le client'),
    ]
    
    reclamation = models.OneToOneField(Reclamation, on_delete=models.CASCADE, related_name='huitd')
    
    # Références
    numero_8d = models.CharField("N° 8D", max_length=50, blank=True)
    ref = models.CharField("Réf", max_length=50, blank=True)
    version = models.CharField("Version", max_length=20, blank=True)
    
    # Informations générales
    date_ouverture = models.DateField("Date d'ouverture", null=True, blank=True)
    designation_piece = models.CharField("Désignation pièces", max_length=200, blank=True)
    numero_article = models.CharField("N° article", max_length=50, blank=True)
    numero_of = models.CharField("N° OF", max_length=50, blank=True)
    numero_nc = models.CharField("N° NC", max_length=50, blank=True)
    
    # Client / Détection
    client = models.CharField("Client", max_length=100, blank=True)
    lieu_detection = models.CharField("Lieu de détection", max_length=100, blank=True,
        choices=[('QUALITE', 'Qualité'), ('PRODUCTION', 'Production'), ('CLIENT', 'Client'), ('FOURNISSEUR', 'Fournisseur')])
    
    # Décision 8D
    decision_8d = models.CharField("Décision 8D", max_length=3, choices=DECISION_8D_CHOICES, default='OUI')
    decision_hcim = models.CharField("Décision HCIM", max_length=50, blank=True)
    huitd_accepte = models.BooleanField("8D accepté", default=False)
    fin_huitd = models.DateField("Fin du 8D", null=True, blank=True)
    fin_huitd_signature = models.CharField("Signature clôture", max_length=100, blank=True)
    
    # Équipe
    pilote = models.CharField("Pilote", max_length=100, blank=True)
    animateur = models.CharField("Animateur", max_length=100, blank=True)
    
    # État
    etat = models.CharField("État", max_length=20, choices=ETAT_CHOICES, default='OUVERT')
    
    # Leçons apprises
    transversalisation = models.TextField("Leçons apprises - Périmètres", blank=True)
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "8D"
        verbose_name_plural = "8Ds"
    
    def __str__(self):
        return f"8D - {self.numero_8d or self.reclamation.numero_reclamation}"

class Participant8D(models.Model):
    """Participants de l'équipe 8D"""
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='participants')
    nom = models.CharField("Nom", max_length=100)
    fonction = models.CharField("Fonction", max_length=100, blank=True)
    role = models.CharField("Rôle", max_length=100, blank=True)
    ordre = models.IntegerField("Ordre", default=1)
    
    class Meta:
        ordering = ['ordre']

class CinqW2H(models.Model):
    """Analyse 5W2H"""
    huitd = models.OneToOneField(HuitD, on_delete=models.CASCADE, related_name='cinq_w2h')
    
    nom = models.CharField("Nom", max_length=100, blank=True)
    site = models.CharField("Site", max_length=100, blank=True)
    date = models.DateField("Date", null=True, blank=True)
    
    # Vue Client
    quoi = models.TextField("Que s'est-il passé ?", blank=True)
    qui = models.TextField("Qui a détecté ?", blank=True)
    ou = models.TextField("Où a été détecté ?", blank=True)
    quand = models.TextField("Quand a été détecté ?", blank=True)
    comment = models.TextField("Comment a été détecté ?", blank=True)
    combien = models.TextField("Combien détectés ?", blank=True)
    pourquoi_probleme = models.TextField("Pourquoi est-ce un problème ?", blank=True)
    impact_logistique = models.TextField("Impact logistique client ?", blank=True)
    autres_clients_livres = models.TextField("Produit livré à autres clients ?", blank=True)
    autres_clients_defaut = models.TextField("Défaut rapporté par autres clients ?", blank=True)
    
    # Vue Interne
    symptomes = models.TextField("De quoi s'agit-il ?", blank=True)
    defauts_ecartes = models.TextField("Défauts écartés d'emblée ?", blank=True)
    ou_cree = models.TextField("Où le défaut a pu être créé ?", blank=True)
    quand_genere = models.TextField("Quand généré en interne ?", blank=True)
    rework = models.TextField("Pièces issues d'une gamme rework ?", blank=True)
    detection_attendue = models.TextField("À quel stade détecté ?", blank=True)
    reinjection = models.TextField("Détection lors réintroduction ?", blank=True)
    probleme_connu = models.TextField("Problème connu / récurrent ?", blank=True)
    dernier_cas = models.TextField("Date du dernier cas ?", blank=True)

class Ishikawa(models.Model):
    """Analyse Ishikawa (6M)"""
    huitd = models.OneToOneField(HuitD, on_delete=models.CASCADE, related_name='ishikawa')
    
    designation = models.CharField("Désignation", max_length=200, blank=True)
    nom = models.CharField("Nom", max_length=100, blank=True)
    site = models.CharField("Site", max_length=100, blank=True)
    date = models.DateField("Date", null=True, blank=True)

class FacteurIshikawa(models.Model):
    """Facteurs du diagramme Ishikawa"""
    CATEGORIE_CHOICES = [
        ('A', 'A - Milieu / Environment'),
        ('B', 'B - Méthodes / Methods'),
        ('C', 'C - Moyens / Resources'),
        ('D', 'D - Main d\'œuvre / Personnel'),
        ('E', 'E - Matières / Materials'),
        ('F', 'F - Mesures / Measures'),
    ]
    
    ishikawa = models.ForeignKey(Ishikawa, on_delete=models.CASCADE, related_name='facteurs')
    categorie = models.CharField("Catégorie 6M", max_length=1, choices=CATEGORIE_CHOICES)
    facteur_probable = models.TextField("Facteur probable", blank=True)
    parametre_mesurable = models.TextField("Paramètre mesurable ?", blank=True)
    standard_exigence = models.TextField("Standard ou exigence", blank=True)
    donnees_bonnes = models.TextField("Données réelles (pièces bonnes)", blank=True)
    donnees_mauvaises = models.TextField("Données réelles (pièces mauvaises)", blank=True)
    standard_suivi = models.BooleanField("Standard suivi ?", default=False)
    standard_approprie = models.BooleanField("Standard approprié ?", default=False)
    lien_prouve = models.BooleanField("Lien prouvé ?", default=False)
    facteur_prouve = models.BooleanField("Facteur prouvé", default=False)
    
    class Meta:
        ordering = ['categorie']

class CinqP(models.Model):
    """Analyse 5 Pourquoi"""
    CATEGORIE_CHOICES = [
        ('OCCURRENCE', 'Occurrence'),
        ('NON_DETECTION', 'Non détection'),
    ]
    
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='cinq_p')
    
    designation = models.CharField("Désignation", max_length=200, blank=True)
    nom = models.CharField("Nom", max_length=100, blank=True)
    site = models.CharField("Site", max_length=100, blank=True)
    date = models.DateField("Date", null=True, blank=True)
    
    categorie = models.CharField("Catégorie", max_length=15, choices=CATEGORIE_CHOICES, default='OCCURRENCE')
    facteur_prouve = models.CharField("Facteur prouvé (B, E, C...)", max_length=10, blank=True)
    pourquoi_1 = models.TextField("1. Pourquoi ?", blank=True)
    pourquoi_2 = models.TextField("2. Pourquoi ?", blank=True)
    pourquoi_3 = models.TextField("3. Pourquoi ?", blank=True)
    pourquoi_4 = models.TextField("4. Pourquoi ?", blank=True)
    pourquoi_5 = models.TextField("5. Pourquoi ?", blank=True)

class FacteurHumain(models.Model):
    """Analyse des facteurs humains"""
    huitd = models.OneToOneField(HuitD, on_delete=models.CASCADE, related_name='facteur_humain')
    description = models.TextField("Description", blank=True)
    analyse = models.TextField("Analyse", blank=True)
    actions = models.TextField("Actions", blank=True)

class VRS(models.Model):
    """Vérification des Standards (VRS)"""
    huitd = models.OneToOneField(HuitD, on_delete=models.CASCADE, related_name='vrs')
    
    designation = models.CharField("Désignation", max_length=200, blank=True)
    nom = models.CharField("Nom", max_length=100, blank=True)
    site = models.CharField("Site", max_length=100, blank=True)
    date = models.DateField("Date", null=True, blank=True)
    suivi = models.CharField("Suivant", max_length=50, blank=True, default="PR-SM-06")

class Action8D(models.Model):
    """Plan d'actions 8D"""
    TYPE_CHOICES = [
        ('AC', 'Action Corrective'),
        ('AP', 'Action Préventive'),
        ('CONTAINMENT', 'Action de confinement'),
    ]
    
    STATUT_CHOICES = [
        ('PLANIFIE', 'Planifié'),
        ('EN_COURS', 'En cours'),
        ('REALISE', 'Réalisé'),
        ('EFFICACE', 'Efficace'),
        ('INEFFICACE', 'Inefficace'),
    ]
    
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='actions')
    
    type_action = models.CharField("Type", max_length=15, choices=TYPE_CHOICES)
    numero_cause = models.CharField("N° Cause (B, E, C...)", max_length=10, blank=True)
    action = models.TextField("Action")
    pilote = models.CharField("Pilote", max_length=100, blank=True)
    delai = models.DateField("Délai / Deadline", null=True, blank=True)
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default='PLANIFIE')
    ordre = models.IntegerField("Ordre", default=1)
    
    class Meta:
        ordering = ['ordre']

class AlterationNecessaire(models.Model):
    """Altérations nécessaires (standardisation)"""
    huitd = models.ForeignKey(HuitD, on_delete=models.CASCADE, related_name='alterations')
    
    type_document = models.CharField("Type document", max_length=100, blank=True)
    description = models.TextField("Description", blank=True)
    remarque = models.TextField("Remarque", blank=True)
    pilote = models.CharField("Pilote", max_length=100, blank=True)
    deadline = models.DateField("Deadline", null=True, blank=True)
    statut = models.CharField("Statut", max_length=50, blank=True)
    ordre = models.IntegerField("Ordre", default=1)
    
    class Meta:
        ordering = ['ordre']

class CaracterisationDefaut(models.Model):
    """Caractérisation du défaut"""
    huitd = models.OneToOneField(HuitD, on_delete=models.CASCADE, related_name='caracterisation')
    
    description = models.TextField("Caractérisation du défaut", blank=True)
    probleme_connu = models.BooleanField("Problème déjà connu ?", default=False)
    risque_similaire = models.BooleanField("Risque sur produit/process similaire ?", default=False)
    risque_similaire_detail = models.TextField("Si oui, lequel ?", blank=True)
    
    illustration_defectueux = models.ImageField("Photo produit défectueux", upload_to='8d/defectueux/', blank=True)
    illustration_conforme = models.ImageField("Photo produit conforme", upload_to='8d/conforme/', blank=True)
    
    tri_necessaire = models.BooleanField("Tri nécessaire ?", default=False)
    of_concernes = models.TextField("OF concernés", blank=True)
    actions_suffisantes = models.BooleanField("Actions suffisantes ?", default=False)
    quantite_rebutee = models.CharField("Qté rebutée", max_length=50, default="N/A")
    quantite_retoucher = models.CharField("Qté à retoucher", max_length=50, default="N/A")

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
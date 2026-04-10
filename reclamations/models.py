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
    ]
    
    ETAT_CHOICES = [
        ('OUVERT', 'Ouvert'),
        ('EN_COURS', 'En cours'),
        ('CLOTURE', 'Clôturé'),
    ]

    IMPUTATION_CHOICES = [
        ('CIM', 'CIM'),
        ('CIB', 'CIB'),
        ('CLIENT', 'CLIENT'),
        ('ALERTE', 'ALERTE'),
    ]
    
    numero_reclamation = models.CharField("N° Réclamation", max_length=50, unique=True)
    date_reclamation = models.DateField(default=timezone.now)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='reclamations')
    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name='clients')
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
    uap_concernee = models.ForeignKey(UAP, on_delete=models.SET_NULL, null=True, blank=True, related_name='lignes_reclamation')
    
    class Meta:
        verbose_name = "Ligne de réclamation"
        verbose_name_plural = "Lignes de réclamation"
        unique_together = ['reclamation', 'produit']
    
    def __str__(self):
        return f"{self.reclamation.numero_reclamation} - {self.produit.product_number}"
        
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
    
class HuitD(models.Model):
    """Modèle pour la méthode 8D"""
    ETAT_CHOICES = [
        ('EN_COURS', 'En cours'),
        ('VALIDE', 'Validé'),
        ('CLOTURE', 'Clôturé'),
    ]
    
    reclamation = models.OneToOneField(Reclamation, on_delete=models.CASCADE, related_name='huitd')
    numero_8d = models.CharField("N° 8D", max_length=50, blank=True, null=True)
    
    # D0 - Préparation
    d0_date = models.DateField("Date de démarrage", null=True, blank=True)
    d0_equipe = models.TextField("Équipe 8D", blank=True, help_text="Membres de l'équipe")
    
    # D1 - Établir l'équipe
    d1_leader = models.CharField("Chef d'équipe", max_length=100, blank=True)
    d1_membres = models.TextField("Membres de l'équipe", blank=True)
    d1_competences = models.TextField("Compétences requises", blank=True)
    
    # D2 - Décrire le problème
    d2_description = models.TextField("Description du problème", blank=True)
    d2_impact = models.TextField("Impact client / interne", blank=True)
    d2_quantification = models.TextField("Quantification (données)", blank=True)
    d2_historique = models.TextField("Historique du problème", blank=True)
    
    # D3 - Actions immédiates
    d3_actions = models.TextField("Actions immédiates", blank=True)
    d3_responsable = models.CharField("Responsable", max_length=100, blank=True)
    d3_date = models.DateField("Date de réalisation", null=True, blank=True)
    d3_efficacite = models.TextField("Efficacité des actions", blank=True)
    
    # D4 - Causes racines
    d4_causes = models.TextField("Causes racines identifiées", blank=True)
    d4_methodes = models.TextField("Méthodes d'analyse utilisées", blank=True)
    d4_validation = models.TextField("Validation des causes", blank=True)
    
    # D5 - Actions correctives
    d5_actions = models.TextField("Actions correctives", blank=True)
    d5_responsable = models.CharField("Responsable", max_length=100, blank=True)
    d5_date_prevue = models.DateField("Date prévue", null=True, blank=True)
    d5_date_reelle = models.DateField("Date réalisée", null=True, blank=True)
    d5_validation = models.TextField("Validation des actions", blank=True)
    
    # D6 - Actions préventives
    d6_actions = models.TextField("Actions préventives", blank=True)
    d6_responsable = models.CharField("Responsable", max_length=100, blank=True)
    d6_date = models.DateField("Date de réalisation", null=True, blank=True)
    d6_standardisation = models.TextField("Standardisation", blank=True)
    
    # D7 - Prévention de la récurrence
    d7_actions = models.TextField("Actions de prévention", blank=True)
    d7_documentation = models.TextField("Documentation mise à jour", blank=True)
    d7_formation = models.TextField("Formation réalisée", blank=True)
    
    # D8 - Félicitations
    d8_equipe = models.TextField("Reconnaissance de l'équipe", blank=True)
    d8_retour = models.TextField("Retour d'expérience", blank=True)
    d8_amelioration = models.TextField("Améliorations identifiées", blank=True)
    
    # Validation
    etat = models.CharField("État", max_length=20, choices=ETAT_CHOICES, default='EN_COURS')
    date_validation = models.DateField("Date de validation", null=True, blank=True)
    valide_par = models.CharField("Validé par", max_length=100, blank=True)
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Démarche 8D"
        verbose_name_plural = "Démarches 8D"
    
    def __str__(self):
        return f"8D - {self.reclamation.numero_reclamation}"

#========= Gestion des FAIs =============

class OrdreFabrication(models.Model):
    """Ordre de fabrication extrait de l'ERP"""
    STATUT_CHOICES = [
        ('CREEE', 'Créé'),
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('CLOTURE', 'Clôturé'),
        ('ANNULE', 'Annulé'),
    ]
    
    numero_of = models.CharField("N° OF", max_length=50, unique=True)
    date_creation = models.DateField("Date création OF")
    date_previsionnelle = models.DateField("Date prévisionnelle fin", null=True, blank=True)
    date_reelle_fin = models.DateField("Date réelle fin", null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='CREEE')
    
    # Informations complémentaires
    responsable = models.CharField("Responsable OF", max_length=200, blank=True)
    atelier = models.CharField("Atelier", max_length=100, blank=True)
    priorite = models.IntegerField("Priorité", default=3, choices=[(1, 'Haute'), (2, 'Moyenne'), (3, 'Basse')])
    
    date_import = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Ordre de fabrication"
        verbose_name_plural = "Ordres de fabrication"
        ordering = ['-date_creation', '-priorite']
        indexes = [
            models.Index(fields=['statut', 'date_creation']),
            models.Index(fields=['numero_of']),
        ]
    
    def __str__(self):
        return f"{self.numero_of} - {self.get_statut_display()}"

class LigneOF(models.Model):
    """Lignes d'un OF (produits à fabriquer)"""
    ordre_fabrication = models.ForeignKey(OrdreFabrication, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name='lignes_of')
    quantite_prevue = models.IntegerField(default=0)
    quantite_produite = models.IntegerField(default=0)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Ligne OF"
        verbose_name_plural = "Lignes OF"
        unique_together = ['ordre_fabrication', 'produit']
    
    def __str__(self):
        return f"{self.ordre_fabrication.numero_of} - {self.produit.product_number}"

class AlerteFAI(models.Model):
    """Alertes FAI générées"""
    NIVEAU_CHOICES = [
        ('INFO', 'Information'),
        ('ALERTE', 'Alerte'),
        ('URGENT', 'Urgent'),
        ('CRITIQUE', 'Critique'),
    ]
    
    STATUT_CHOICES = [
        ('NOUVELLE', 'Nouvelle'),
        ('EN_COURS', 'En cours'),
        ('TRAITEE', 'Traitée'),
        ('IGNOREE', 'Ignorée'),
    ]
    
    ordre_fabrication = models.ForeignKey(OrdreFabrication, on_delete=models.CASCADE, related_name='alertes_fai')
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='alertes_fai')
    niveau = models.CharField(max_length=20, choices=NIVEAU_CHOICES, default='ALERTE')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='NOUVELLE')
    
    # Dates clés
    derniere_production = models.DateField("Date dernière production", null=True, blank=True)
    derniere_inspection = models.DateField("Date dernière inspection FAI", null=True, blank=True)
    date_expiration = models.DateField("Date expiration FAI", null=True, blank=True)
    
    # Message
    message = models.TextField()
    commentaire = models.TextField(blank=True)
    
    # Traitement
    traite_par = models.CharField(max_length=200, blank=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Alerte FAI"
        verbose_name_plural = "Alertes FAI"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['statut', 'niveau']),
            models.Index(fields=['ordre_fabrication', 'produit']),
        ]
    
    def __str__(self):
        return f"{self.get_niveau_display()} - {self.ordre_fabrication.numero_of} - {self.produit.product_number}"
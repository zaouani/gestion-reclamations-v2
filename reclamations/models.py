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
    createur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reclamations_crees')
    
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
    
    
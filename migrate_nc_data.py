# migrate_nc_data.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from reclamations.models import LigneReclamation, NonConformite

def migrate_existing_nc():
    """Migre les données existantes vers le nouveau modèle"""
    print("="*50)
    print("Migration des non-conformités existantes")
    print("="*50)
    
    total_migrees = 0
    for ligne in LigneReclamation.objects.all():
        if ligne.description_non_conformite and ligne.description_non_conformite.strip():
            # Créer une NC par ligne existante
            nc = NonConformite.objects.create(
                ligne_reclamation=ligne,
                description=ligne.description_non_conformite,
                quantite=ligne.quantite or 1
            )
            total_migrees += 1
            print(f"✓ Migré: {ligne.reclamation.numero_reclamation} - {ligne.produit.product_number}")
    
    print(f"\n✅ Migration terminée! {total_migrees} non-conformités créées.")
    
    # Afficher un résumé
    print("\n📊 RÉSUMÉ:")
    print(f"   - Lignes de réclamation: {LigneReclamation.objects.count()}")
    print(f"   - Non-conformités créées: {NonConformite.objects.count()}")

if __name__ == "__main__":
    migrate_existing_nc()
# accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from .models import User, Role
from .decorators import role_required, permission_required

@login_required
@role_required(['admin', 'quality_manager'])
def liste_utilisateurs(request):
    """Liste des utilisateurs"""
    users = User.objects.all().order_by('-date_joined')
    
    # Filtres
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(role=role_filter)
    
    search = request.GET.get('search', '')
    if search:
        users = users.filter(
            models.Q(username__icontains=search) |
            models.Q(first_name__icontains=search) |
            models.Q(last_name__icontains=search) |
            models.Q(email__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(users, 20)
    page = request.GET.get('page', 1)
    users_page = paginator.get_page(page)
    
    context = {
        'users': users_page,
        'roles': User.ROLE_CHOICES,
        'role_filter': role_filter,
        'search': search,
    }
    return render(request, 'accounts/liste_utilisateurs.html', context)

@login_required
@role_required(['admin'])
def creer_utilisateur(request):
    """Créer un nouvel utilisateur"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        role = request.POST.get('role')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        phone = request.POST.get('phone', '')
        department = request.POST.get('department', '')
        position = request.POST.get('position', '')
        
        # Validation
        if password != password_confirm:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return redirect('accounts:creer_utilisateur')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Ce nom d'utilisateur existe déjà.")
            return redirect('accounts:creer_utilisateur')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, "Cet email est déjà utilisé.")
            return redirect('accounts:creer_utilisateur')
        
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    phone=phone,
                    department=department,
                    position=position,
                    is_active=True
                )
                messages.success(request, f"Utilisateur '{username}' créé avec succès.")
                return redirect('accounts:liste_utilisateurs')
                
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
    
    context = {
        'roles': User.ROLE_CHOICES,
    }
    return render(request, 'accounts/creer_utilisateur.html', context)

@login_required
@role_required(['admin'])
def modifier_utilisateur(request, user_id):
    """Modifier un utilisateur"""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.role = request.POST.get('role')
        user.phone = request.POST.get('phone', '')
        user.department = request.POST.get('department', '')
        user.position = request.POST.get('position', '')
        user.is_active = request.POST.get('is_active') == 'on'
        
        # Changement de mot de passe
        password = request.POST.get('password')
        if password:
            password_confirm = request.POST.get('password_confirm')
            if password == password_confirm:
                user.set_password(password)
            else:
                messages.error(request, "Les mots de passe ne correspondent pas.")
                return redirect('accounts:modifier_utilisateur', user_id=user.id)
        
        user.save()
        messages.success(request, f"Utilisateur '{user.username}' modifié avec succès.")
        return redirect('accounts:liste_utilisateurs')
    
    context = {
        'user': user,
        'roles': User.ROLE_CHOICES,
    }
    return render(request, 'accounts/modifier_utilisateur.html', context)

@login_required
@role_required(['admin'])
def supprimer_utilisateur(request, user_id):
    """Supprimer un utilisateur"""
    user = get_object_or_404(User, id=user_id)
    
    if user == request.user:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect('accounts:liste_utilisateurs')
    
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f"Utilisateur '{username}' supprimé avec succès.")
        return redirect('accounts:liste_utilisateurs')
    
    context = {'user': user}
    return render(request, 'accounts/supprimer_utilisateur.html', context)

@login_required
def mon_profil(request):
    """Afficher et modifier son propre profil"""
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email')
        request.user.phone = request.POST.get('phone', '')
        request.user.department = request.POST.get('department', '')
        request.user.position = request.POST.get('position', '')
        
        # Changement de mot de passe
        password = request.POST.get('password')
        if password:
            password_confirm = request.POST.get('password_confirm')
            if password == password_confirm:
                request.user.set_password(password)
                messages.success(request, "Mot de passe modifié. Veuillez vous reconnecter.")
                return redirect('accounts:login')
            else:
                messages.error(request, "Les mots de passe ne correspondent pas.")
                return redirect('accounts:mon_profil')
        
        request.user.save()
        messages.success(request, "Profil mis à jour avec succès.")
        return redirect('accounts:mon_profil')
    
    return render(request, 'accounts/mon_profil.html')
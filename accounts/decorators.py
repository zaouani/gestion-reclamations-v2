from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def role_required(allowed_roles=[]):
    """Décorateur pour vérifier si l'utilisateur a le rôle requis"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, "Vous n'avez pas les droits nécessaires pour accéder à cette page.")
            return redirect('reclamations:dashboard')
        return wrapped
    return decorator


def permission_required(permission_codename):
    """Décorateur pour vérifier une permission spécifique"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            if request.user.has_permission(permission_codename):
                return view_func(request, *args, **kwargs)
            
            messages.error(request, f"Permission '{permission_codename}' requise.")
            return redirect('reclamations:dashboard')
        return wrapped
    return decorator
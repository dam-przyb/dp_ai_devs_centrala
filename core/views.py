from django.shortcuts import render
from .nav_registry import NAV


def dashboard(request):
    """Root view — renders the full shell with an empty workspace."""
    return render(request, "core/base.html", {"nav": NAV})

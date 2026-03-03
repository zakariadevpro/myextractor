from collections import defaultdict

from app.core.roles import ROLE_ADMIN, ROLE_MANAGER, ROLE_SUPER_ADMIN, ROLE_USER

PERMISSION_CATALOG: dict[str, dict[str, str]] = {
    "access.manager": {
        "label": "Acces Manager",
        "description": "Donne acces aux endpoints manager.",
        "category": "access",
    },
    "access.admin": {
        "label": "Acces Admin",
        "description": "Donne acces aux endpoints admin.",
        "category": "access",
    },
    "access.super_admin": {
        "label": "Acces Super Admin",
        "description": "Donne acces aux operations reservees super admin.",
        "category": "access",
    },
    "users.view": {
        "label": "Voir Utilisateurs",
        "description": "Consulter la liste des utilisateurs de l'organisation.",
        "category": "users",
    },
    "users.manage": {
        "label": "Gerer Utilisateurs",
        "description": "Creer, modifier et desactiver les utilisateurs.",
        "category": "users",
    },
    "users.permissions.manage": {
        "label": "Gerer Permissions",
        "description": "Affecter les permissions individuelles des utilisateurs.",
        "category": "users",
    },
    "leads.view": {
        "label": "Voir Leads",
        "description": "Consulter les leads.",
        "category": "leads",
    },
    "leads.export": {
        "label": "Exporter Leads",
        "description": "Exporter les leads en CSV/XLSX.",
        "category": "leads",
    },
    "leads.manage": {
        "label": "Gerer Leads",
        "description": "Modifier, supprimer, dedoublonner les leads.",
        "category": "leads",
    },
    "extraction.view": {
        "label": "Voir Extractions",
        "description": "Consulter l'historique des extractions.",
        "category": "extraction",
    },
    "extraction.create": {
        "label": "Creer Extractions",
        "description": "Lancer de nouvelles extractions.",
        "category": "extraction",
    },
    "extraction.cancel": {
        "label": "Annuler Extractions",
        "description": "Annuler un job d'extraction en cours.",
        "category": "extraction",
    },
    "audit.view": {
        "label": "Voir Audit",
        "description": "Consulter les journaux d'audit.",
        "category": "audit",
    },
    "settings.view": {
        "label": "Voir Parametres",
        "description": "Acceder aux pages parametres.",
        "category": "settings",
    },
    "subscriptions.manage": {
        "label": "Gerer Abonnements",
        "description": "Gerer la facturation et les abonnements.",
        "category": "settings",
    },
    "api_keys.manage": {
        "label": "Gerer API Keys",
        "description": "Creer/revoquer les cles API.",
        "category": "settings",
    },
    "workflows.manage": {
        "label": "Gerer Workflows",
        "description": "Creer/modifier les workflows automatiques.",
        "category": "settings",
    },
    "scoring.manage": {
        "label": "Gerer Scoring",
        "description": "Configurer le scoring des leads.",
        "category": "settings",
    },
}

ROLE_DEFAULT_PERMISSIONS: dict[str, set[str]] = {
    ROLE_USER: {
        "leads.view",
        "extraction.view",
        "settings.view",
    },
    ROLE_MANAGER: {
        "access.manager",
        "users.view",
        "leads.view",
        "leads.export",
        "extraction.view",
        "extraction.create",
        "extraction.cancel",
        "audit.view",
        "settings.view",
    },
    ROLE_ADMIN: {
        "access.manager",
        "access.admin",
        "users.view",
        "users.manage",
        "leads.view",
        "leads.export",
        "leads.manage",
        "extraction.view",
        "extraction.create",
        "extraction.cancel",
        "audit.view",
        "settings.view",
        "subscriptions.manage",
        "api_keys.manage",
        "workflows.manage",
        "scoring.manage",
    },
    ROLE_SUPER_ADMIN: set(PERMISSION_CATALOG.keys()),
}


def normalize_permission_name(value: str) -> str:
    return str(value or "").strip().lower()


def is_known_permission(value: str) -> bool:
    return normalize_permission_name(value) in PERMISSION_CATALOG


def list_permission_catalog() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for key in sorted(PERMISSION_CATALOG.keys()):
        meta = PERMISSION_CATALOG[key]
        items.append(
            {
                "key": key,
                "label": meta["label"],
                "description": meta["description"],
                "category": meta["category"],
            }
        )
    return items


def list_permission_categories() -> list[str]:
    categories = defaultdict(int)
    for meta in PERMISSION_CATALOG.values():
        categories[meta["category"]] += 1
    return sorted(categories.keys())


def get_role_default_permissions(role: str) -> set[str]:
    return set(ROLE_DEFAULT_PERMISSIONS.get(str(role or "").lower(), set()))


def resolve_effective_permissions(role: str, grants: set[str], revokes: set[str]) -> set[str]:
    defaults = get_role_default_permissions(role)
    return (defaults | set(grants)) - set(revokes)

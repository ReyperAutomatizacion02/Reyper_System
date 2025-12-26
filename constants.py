# Definición de Módulos del Sistema
SYSTEM_MODULES = [
    {'name': 'Administracion', 'icon': 'ph-briefcase', 'label': 'Administración'},
    {'name': 'Almacen', 'icon': 'ph-package', 'label': 'Almacén'},
    {'name': 'Logistica', 'icon': 'ph-truck', 'label': 'Logística'},
    {'name': 'Produccion', 'icon': 'ph-factory', 'label': 'Producción'},
    {'name': 'Diseño', 'icon': 'ph-paint-brush', 'label': 'Diseño'},
    {'name': 'Ventas', 'icon': 'ph-shopping-cart', 'label': 'Ventas'},
    {'name': 'Compras', 'icon': 'ph-shopping-bag', 'label': 'Compras'},
    {'name': 'Recursos Humanos', 'icon': 'ph-users', 'label': 'RRHH'},
    {'name': 'Contabilidad', 'icon': 'ph-currency-dollar', 'label': 'Contabilidad'}
]

def get_allowed_modules(user_roles):
    """Filtra los módulos del sistema basado en los roles del usuario."""
    if 'Admin' in user_roles:
        return SYSTEM_MODULES
    return [m for m in SYSTEM_MODULES if m['name'] in user_roles]

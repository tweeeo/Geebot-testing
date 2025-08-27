"""
Utilidades para mapear roles de Genius a roles internos del bot
"""
from typing import List, Dict, Any


def map_genius_roles(user_info: Dict[str, Any]) -> List[str]:
    """
    Dado el objeto de usuario de Genius, devuelve una lista de nombres de roles internos
    reconocidos por el bot para asignación en Discord.

    Posibles valores devueltos:
    - "Verified Artist", "Staff", "Moderator", "Editor", "Transcriber", "Mediator", "Contributor"
    """
    roles_out: List[str] = []

    try:
        # Extraer posibles fuentes de roles
        roles_for_display = (user_info.get("roles_for_display") or [])
        role_for_display = (user_info.get("role_for_display") or "").strip()
        artist_info = (user_info.get("artist") or {})

        # Mapeo canónico
        role_mapping = {
            "verified_artist": "Verified Artist",
            "staff": "Staff",
            "moderator": "Moderator",
            "editor": "Editor",
            "transcriber": "Transcriber",
            "mediator": "Mediator",
            "contributor": "Contributor",
        }

        # 1) Intentar con roles_for_display (preferido si viene como lista)
        for r in roles_for_display:
            key = str(r).lower().replace(" ", "_")
            if key in role_mapping:
                name = role_mapping[key]
                if name not in roles_out:
                    roles_out.append(name)

        # 2) Fallbacks: artista verificado, staff y role_for_display como texto
        if not roles_out:
            if artist_info.get("is_verified"):
                roles_out.append("Verified Artist")

            if user_info.get("staff") or user_info.get("is_staff"):
                if "Staff" not in roles_out:
                    roles_out.append("Staff")

            role_disp_lower = role_for_display.lower()
            for key, name in role_mapping.items():
                if key in role_disp_lower and name not in roles_out:
                    roles_out.append(name)

        # 3) Último recurso
        if not roles_out:
            roles_out.append("Contributor")

    except Exception:
        # En caso de error, usar valor seguro
        roles_out = ["Contributor"]

    return roles_out
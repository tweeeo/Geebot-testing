#!/usr/bin/env python3
"""
Script para inicializar la configuración por defecto en la base de datos
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def init_default_config():
    """Inicializar configuración por defecto"""
    print("🔧 Inicializando configuración por defecto...")
    
    try:
        from src.utils.dynamic_config import config
        
        # Configuración por defecto con los valores actuales del bot
        default_values = {
            "DISCORD_TOKEN": "MTQwNDg1NTQwNjQ4MzczODgwNg.GMtVzA.fhtyzNYIIHfed9MzdAogcexGJKrSOsNg4WmUkw",
            "GENIUS_CLIENT_ID": "ughQE4sdl2nlurcgiUFIVMzM33AJNPSEsusgY7Vr6f4WlPRW20IDQuBj7mua7uay",
            "GENIUS_CLIENT_SECRET": "eYFDTD4lPo6XE6kh041XVyZy_Hd9tkRSCnCxBOjWsgw91zP10sDjJcsy3OwxrCs_V122S7cDbKQxJ4XjLpg6Fw",
            "BASE_URL": "https://geebot.onrender.com",
            "VERIFICATION_CHANNEL_ID": "0",  # Debe ser configurado por el usuario
            "VERIFIED_ROLE_ID": "1404855696842821653",
            "ROLE_VERIFIED_ARTIST": "1404856059717484684",
            "ROLE_STAFF": "1404856078394724463",
            "ROLE_MODERATOR": "1404855980738740385",
            "ROLE_EDITOR": "1404855934764847194",
            "ROLE_TRANSCRIBER": "1404855862710763630",
            "ROLE_MEDIATOR": "1404855801201557514",
            "ROLE_CONTRIBUTOR": "1404855696842821653",
            "KEEP_ALIVE_INTERVAL": "300"
        }
        
        # Actualizar solo los valores que están vacíos
        configs_to_update = {}
        for key, default_value in default_values.items():
            current_value = config.get(key, "")
            if not current_value or current_value == "":
                configs_to_update[key] = default_value
                print(f"  ✅ {key}: {default_value}")
            else:
                print(f"  ⏭️ {key}: Ya configurado ({current_value})")
        
        if configs_to_update:
            success = config.update_multiple(configs_to_update)
            if success:
                print(f"\n✅ {len(configs_to_update)} configuraciones inicializadas correctamente")
            else:
                print("\n❌ Error inicializando configuraciones")
        else:
            print("\n✅ Todas las configuraciones ya están establecidas")
        
        # Verificar sincronización
        print("\n🔍 Verificando sincronización...")
        from src.utils.config import reload_config
        reload_config()
        
        print("✅ Configuración inicializada y sincronizada")
        
    except Exception as e:
        print(f"❌ Error inicializando configuración: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    init_default_config()
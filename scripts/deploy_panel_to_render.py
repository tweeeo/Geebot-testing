#!/usr/bin/env python3
"""
Script para ayudar con el despliegue del Panel de Control a Render
"""

import os
import sys
from pathlib import Path

def print_deployment_instructions():
    """Mostrar instrucciones de despliegue"""
    print("🚀 Instrucciones para Desplegar Panel de Control en Render")
    print("=" * 60)
    
    print("\n1. CREAR NUEVO SERVICIO WEB EN RENDER:")
    print("   - Ve a https://dashboard.render.com")
    print("   - Clic en 'New +' > 'Web Service'")
    print("   - Conecta tu repositorio de GitHub")
    print("   - Nombre: geebot-panel (o el que prefieras)")
    
    print("\n2. CONFIGURACIÓN DEL SERVICIO:")
    print("   - Environment: Python 3")
    print("   - Build Command: pip install -r requirements.txt")
    print("   - Start Command: python run_panel.py")
    print("   - Instance Type: Free (o el que prefieras)")
    
    print("\n3. VARIABLES DE ENTORNO REQUERIDAS:")
    print("   Configura estas variables en Render Dashboard:")
    
    # Variables del panel
    panel_vars = {
        "PANEL_HOST": "0.0.0.0",
        "PANEL_PORT": "10000",
        "PANEL_USERNAME": "admin",
        "PANEL_PASSWORD_HASH": "GENERAR_CON_SCRIPT"
    }
    
    print("\n   📋 Variables del Panel:")
    for key, value in panel_vars.items():
        if key == "PANEL_PASSWORD_HASH":
            print(f"   {key}={value} (usar scripts/generate_password_hash.py)")
        else:
            print(f"   {key}={value}")
    
    # Variables del bot (las mismas que el bot principal)
    bot_vars = [
        "DISCORD_TOKEN",
        "GENIUS_CLIENT_ID", 
        "GENIUS_CLIENT_SECRET",
        "BASE_URL",
        "VERIFICATION_CHANNEL_ID",
        "VERIFIED_ROLE_ID",
        "ROLE_VERIFIED_ARTIST",
        "ROLE_STAFF",
        "ROLE_MODERATOR", 
        "ROLE_EDITOR",
        "ROLE_TRANSCRIBER",
        "ROLE_MEDIATOR",
        "ROLE_CONTRIBUTOR",
        "KEEP_ALIVE_INTERVAL"
    ]
    
    print("\n   🤖 Variables del Bot (copiar del servicio principal):")
    for var in bot_vars:
        print(f"   {var}=<valor_del_bot_principal>")
    
    print("\n4. GENERAR HASH DE CONTRASEÑA:")
    print("   Ejecuta: python scripts/generate_password_hash.py")
    print("   Copia el hash generado a PANEL_PASSWORD_HASH en Render")
    
    print("\n5. DESPLEGAR:")
    print("   - Clic en 'Create Web Service'")
    print("   - Espera a que termine el build")
    print("   - Accede a tu panel en la URL proporcionada por Render")
    
    print("\n6. ACCESO AL PANEL:")
    print("   - URL: https://tu-servicio.onrender.com")
    print("   - Usuario: admin (o el configurado en PANEL_USERNAME)")
    print("   - Contraseña: la que configuraste")
    
    print("\n7. CONFIGURACIÓN ADICIONAL:")
    print("   - El panel puede ejecutarse en paralelo al bot principal")
    print("   - Usa el mismo repositorio pero diferentes comandos de inicio")
    print("   - Ambos servicios pueden compartir las mismas variables de entorno")
    
    print("\n" + "=" * 60)
    print("✅ Una vez desplegado, podrás configurar el bot desde el navegador")

def check_requirements():
    """Verificar que los archivos necesarios existen"""
    print("\n🔍 Verificando archivos necesarios...")
    
    required_files = [
        "run_panel.py",
        "src/panel/main.py",
        "assets/panel_templates/base.html",
        "assets/panel_templates/dashboard.html",
        "assets/panel_templates/config.html",
        "scripts/generate_password_hash.py",
        "requirements.txt"
    ]
    
    missing_files = []
    for file_path in required_files:
        full_path = Path(__file__).parent.parent / file_path
        if not full_path.exists():
            missing_files.append(file_path)
        else:
            print(f"   ✅ {file_path}")
    
    if missing_files:
        print(f"\n❌ Archivos faltantes:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    print("\n✅ Todos los archivos necesarios están presentes")
    return True

def main():
    """Función principal"""
    print("🎛️ Asistente de Despliegue - Panel de Control GeeBot")
    
    if not check_requirements():
        print("\n❌ Faltan archivos necesarios. Ejecuta primero la configuración del panel.")
        sys.exit(1)
    
    print_deployment_instructions()
    
    print("\n🔧 ¿Quieres generar un hash de contraseña ahora? (y/n): ", end="")
    response = input().lower().strip()
    
    if response in ['y', 'yes', 's', 'si']:
        try:
            # Importar y ejecutar el generador de hash
            sys.path.insert(0, str(Path(__file__).parent))
            from generate_password_hash import generate_password_hash
            generate_password_hash()
        except ImportError:
            print("❌ No se pudo importar el generador de hash")
            print("Ejecuta manualmente: python scripts/generate_password_hash.py")

if __name__ == "__main__":
    main()
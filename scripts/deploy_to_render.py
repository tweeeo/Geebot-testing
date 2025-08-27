#!/usr/bin/env python3
"""
Script de deployment para Render
Verifica que todo esté listo antes del deploy
"""

import os
import sys
import subprocess
import json

def check_git_status():
    """Verifica el estado de Git"""
    print("📋 Verificando estado de Git...")
    
    try:
        # Verificar si hay cambios sin commit
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, check=True)
        
        if result.stdout.strip():
            print("  ⚠️  Hay cambios sin commit:")
            print(result.stdout)
            
            response = input("¿Quieres hacer commit de estos cambios? (y/N): ").lower().strip()
            if response in ['y', 'yes', 'sí', 'si']:
                commit_message = input("Mensaje de commit: ").strip()
                if not commit_message:
                    commit_message = "feat: Update for Render deployment"
                
                subprocess.run(['git', 'add', '.'], check=True)
                subprocess.run(['git', 'commit', '-m', commit_message], check=True)
                print("  ✅ Cambios committeados")
            else:
                print("  ⚠️  Continuando sin commit...")
        else:
            print("  ✅ No hay cambios pendientes")
            
        # Verificar branch actual
        result = subprocess.run(['git', 'branch', '--show-current'], 
                              capture_output=True, text=True, check=True)
        current_branch = result.stdout.strip()
        print(f"  📍 Branch actual: {current_branch}")
        
        if current_branch != 'main' and current_branch != 'master':
            print(f"  ⚠️  No estás en main/master. Render deployará desde {current_branch}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Error con Git: {e}")
        return False
    except FileNotFoundError:
        print("  ❌ Git no encontrado. Instala Git primero.")
        return False

def check_required_files():
    """Verifica que todos los archivos necesarios existan"""
    print("📁 Verificando archivos requeridos...")
    
    required_files = {
        'main.py': 'Archivo principal del bot (nuevo punto de entrada)',
        'src/bot/main.py': 'Código principal del bot',
        'src/web/server.py': 'Servidor web para OAuth',
        'src/database/models.py': 'Manejo de base de datos',
        'src/services/keep_alive.py': 'Sistema keep-alive',
        'src/utils/config.py': 'Configuración del proyecto',
        'requirements.txt': 'Dependencias de Python',
        'README.md': 'Documentación',
        'assets/templates/index.html': 'Template principal',
        'assets/templates/base.html': 'Template base',
        'assets/templates/success.html': 'Template de éxito',
        'assets/templates/error.html': 'Template de error',
        'assets/static/css/style.css': 'Estilos CSS'
    }
    
    missing_files = []
    
    for file_path, description in required_files.items():
        if os.path.exists(file_path):
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} - {description}")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️  Archivos faltantes: {len(missing_files)}")
        return False
    else:
        print(f"\n✅ Todos los archivos requeridos están presentes")
        return True

def check_requirements():
    """Verifica requirements.txt"""
    print("📦 Verificando requirements.txt...")
    
    if not os.path.exists('requirements.txt'):
        print("  ❌ requirements.txt no encontrado")
        return False
    
    required_packages = [
        'discord.py',
        'quart',
        'aiohttp',
        'aiosqlite'
    ]
    
    try:
        with open('requirements.txt', 'r') as f:
            content = f.read().lower()
        
        missing_packages = []
        for package in required_packages:
            if package.lower() in content:
                print(f"  ✅ {package}")
            else:
                print(f"  ❌ {package}")
                missing_packages.append(package)
        
        if missing_packages:
            print(f"  ⚠️  Paquetes faltantes: {missing_packages}")
            return False
        else:
            print("  ✅ Todas las dependencias están listadas")
            return True
            
    except Exception as e:
        print(f"  ❌ Error leyendo requirements.txt: {e}")
        return False

def show_deployment_checklist():
    """Muestra checklist para deployment en Render"""
    print("\n" + "="*60)
    print("🚀 CHECKLIST PARA DEPLOYMENT EN RENDER")
    print("="*60)
    
    checklist = [
        "1. Crear cuenta en render.com",
        "2. Conectar tu repositorio de GitHub",
        "3. Crear nuevo Web Service",
        "4. Configurar variables de entorno:",
        "   - DISCORD_TOKEN",
        "   - GENIUS_CLIENT_ID", 
        "   - GENIUS_CLIENT_SECRET",
        "5. Actualizar Redirect URI en Genius.com:",
        "   - https://tu-servicio.onrender.com/callback",
        "6. Hacer push a main/master para trigger deploy",
        "7. Verificar que el servicio esté funcionando:",
        "   - https://tu-servicio.onrender.com/ping",
        "   - https://tu-servicio.onrender.com/health"
    ]
    
    for item in checklist:
        print(f"  {item}")
    
    print("\n" + "="*60)

def main():
    """Función principal"""
    print("🤖 GeeBot - Deployment Checker para Render")
    print("="*50)
    
    checks = [
        ("Git Status", check_git_status),
        ("Archivos Requeridos", check_required_files),
        ("Requirements", check_requirements)
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        print(f"\n🔍 {check_name}")
        print("-" * 30)
        
        try:
            result = check_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"  ❌ Error en {check_name}: {e}")
            all_passed = False
    
    print("\n" + "="*50)
    
    if all_passed:
        print("✅ TODAS LAS VERIFICACIONES PASARON")
        print("🚀 Tu proyecto está listo para deployment en Render!")
        
        show_deployment_checklist()
        
        print("\n🔗 Enlaces útiles:")
        print("  - Render Dashboard: https://dashboard.render.com")
        print("  - Genius API: https://genius.com/api-clients")
        print("  - Tu bot (después del deploy): https://tu-servicio.onrender.com")
        
    else:
        print("❌ ALGUNAS VERIFICACIONES FALLARON")
        print("🔧 Resuelve los problemas antes de hacer deploy")
        return 1
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️  Verificación interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)
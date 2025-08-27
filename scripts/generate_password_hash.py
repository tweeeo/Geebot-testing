#!/usr/bin/env python3
"""
Script para generar hash de contraseña para el panel de control
"""

import bcrypt
import getpass
import sys

def generate_password_hash():
    """Generar hash de contraseña"""
    print("🔐 Generador de Hash de Contraseña para Panel de Control")
    print("-" * 50)
    
    try:
        # Solicitar contraseña
        password = getpass.getpass("Ingresa la nueva contraseña: ")
        
        if len(password) < 6:
            print("❌ La contraseña debe tener al menos 6 caracteres")
            return
        
        # Confirmar contraseña
        confirm_password = getpass.getpass("Confirma la contraseña: ")
        
        if password != confirm_password:
            print("❌ Las contraseñas no coinciden")
            return
        
        # Generar hash
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        hash_string = password_hash.decode('utf-8')
        
        print("\n✅ Hash generado exitosamente!")
        print("-" * 50)
        print("Configura esta variable de entorno en Render:")
        print(f"PANEL_PASSWORD_HASH={hash_string}")
        print("-" * 50)
        print("\nTambién puedes configurar el usuario (opcional):")
        print("PANEL_USERNAME=tu_usuario_personalizado")
        print("\nSi no configuras PANEL_USERNAME, se usará 'admin' por defecto")
        
    except KeyboardInterrupt:
        print("\n🛑 Operación cancelada")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    generate_password_hash()
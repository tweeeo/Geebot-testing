#!/usr/bin/env python3
"""
Script de debug para verificar la configuración OAuth2 de Genius
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config import *
from urllib.parse import urlencode

def test_oauth_url():
    """Genera y muestra la URL OAuth2 que se está enviando"""
    
    print("🔍 Debug de configuración OAuth2 de Genius")
    print("=" * 50)
    
    # Mostrar configuración actual
    print(f"CLIENT_ID: {GENIUS_CLIENT_ID}")
    print(f"CLIENT_SECRET: {GENIUS_CLIENT_SECRET[:10]}...{GENIUS_CLIENT_SECRET[-10:]}")
    print(f"REDIRECT_URI: {GENIUS_REDIRECT_URI}")
    print(f"BASE_URL: {BASE_URL}")
    
    print("\n🌐 URL OAuth2 generada:")
    print("=" * 30)
    
    # Simular los parámetros que se envían
    test_state = "test-debug-state-12345"
    params = {
        "client_id": GENIUS_CLIENT_ID,
        "redirect_uri": GENIUS_REDIRECT_URI,
        "scope": "me",
        "state": test_state,
        "response_type": "code"
    }
    
    auth_url = f"https://api.genius.com/oauth/authorize?{urlencode(params)}"
    print(auth_url)
    
    print("\n📋 Verificaciones necesarias:")
    print("=" * 35)
    print("1. ¿El CLIENT_ID coincide con el de tu aplicación en Genius?")
    print("2. ¿El REDIRECT_URI está exactamente configurado como:")
    print(f"   {GENIUS_REDIRECT_URI}")
    print("3. ¿Tu aplicación está habilitada/aprobada en Genius?")
    print("4. ¿Estás logueado en Genius.com en tu navegador?")
    
    print("\n🧪 Prueba manual:")
    print("=" * 18)
    print("1. Copia la URL de arriba")
    print("2. Pégala en tu navegador")
    print("3. Si ves una página de login en lugar de autorización,")
    print("   las credenciales están mal configuradas")
    print("4. Si ves 'Invalid Authorization', revisa el redirect_uri")

if __name__ == "__main__":
    test_oauth_url()
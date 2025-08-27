import os
from .dynamic_config import config

# ============================================================================
# CONFIGURACIÓN DINÁMICA - Ahora se configura desde el panel web
# ============================================================================

# Inicializar configuraciones por defecto
config.init_default_configs()

# Función para obtener configuración con fallback
def get_config(key: str, default=None, convert_type=None):
    """Obtener configuración desde sistema dinámico o variables de entorno"""
    value = config.get(key, default)
    
    # Si el valor está vacío o es None, usar el default
    if not value or value == "":
        value = default
    
    if value and convert_type:
        try:
            return convert_type(value)
        except (ValueError, TypeError):
            return default if default is not None else 0
    
    return value

# Discord Bot Token - Ahora opcional al inicio
TOKEN = get_config("DISCORD_TOKEN")

# Genius OAuth2 Credentials - Ahora opcional al inicio  
GENIUS_CLIENT_ID = get_config("GENIUS_CLIENT_ID")
GENIUS_CLIENT_SECRET = get_config("GENIUS_CLIENT_SECRET")

# URLs dinámicas
BASE_URL = get_config("BASE_URL", "https://geebot.onrender.com")
GENIUS_REDIRECT_URI = f"{BASE_URL}/callback"

# Configuración del servidor web para Render
WEB_SERVER_HOST = "0.0.0.0"  # Render requiere 0.0.0.0
WEB_SERVER_PORT = int(os.environ.get("PORT", 10000))  # Render usa puerto 10000 por defecto 

# Discord Server Configuration - Ahora dinámico
VERIFICATION_CHANNEL_ID = get_config("VERIFICATION_CHANNEL_ID", "0", int)
VERIFIED_ROLE_ID = get_config("VERIFIED_ROLE_ID", "1404855696842821653", int)

# Role IDs for Genius roles - Ahora dinámico
GENIUS_ROLE_IDS = {
    "Verified Artist": get_config("ROLE_VERIFIED_ARTIST", "1404856059717484684", int),
    "Staff": get_config("ROLE_STAFF", "1404856078394724463", int),
    "Moderator": get_config("ROLE_MODERATOR", "1404855980738740385", int),
    "Editor": get_config("ROLE_EDITOR", "1404855934764847194", int),
    "Transcriber": get_config("ROLE_TRANSCRIBER", "1404855862710763630", int),
    "Mediator": get_config("ROLE_MEDIATOR", "1404855801201557514", int),
    "Contributor": get_config("ROLE_CONTRIBUTOR", "1404855696842821653", int)
}

# Sección: Comandos (valores por defecto)
CMD_PREFIX = get_config("CMD_PREFIX", "!!")
ENABLE_COMMAND_PING = get_config("ENABLE_COMMAND_PING", "true").lower() == "true"
ENABLE_COMMAND_TEST_WELCOME = get_config("ENABLE_COMMAND_TEST_WELCOME", "true").lower() == "true"

# Sección: Mensajes (valores por defecto)
WELCOME_REACTION_ENABLED = get_config("WELCOME_REACTION_ENABLED", "true").lower() == "true"
WELCOME_MESSAGE_TEXT = get_config("WELCOME_MESSAGE_TEXT", "")

# Sección: Verificación (valores por defecto)
VERIFICATION_EMBED_TITLE = get_config("VERIFICATION_EMBED_TITLE", "Verificación con Genius")
VERIFICATION_EMBED_DESCRIPTION = get_config("VERIFICATION_EMBED_DESCRIPTION", "Conecta tu cuenta de Genius para obtener roles.")
VERIFICATION_BUTTON_LABEL = get_config("VERIFICATION_BUTTON_LABEL", "Verificar con Genius")

# Keep-Alive Configuration
KEEP_ALIVE_ENABLED = True
KEEP_ALIVE_INTERVAL = get_config("KEEP_ALIVE_INTERVAL", 300, int)
KEEP_ALIVE_TIMEOUT = 30  # Timeout para requests de keep-alive

# Función para verificar si el bot está configurado
def is_bot_configured():
    """Verificar si el bot tiene la configuración mínima necesaria"""
    return config.is_configured()

# Función para obtener configuraciones faltantes
def get_missing_configs():
    """Obtener lista de configuraciones faltantes"""
    return config.get_missing_configs()

# Función para recargar configuración
def reload_config():
    """Recargar configuración desde la base de datos"""
    global TOKEN, GENIUS_CLIENT_ID, GENIUS_CLIENT_SECRET, BASE_URL
    global VERIFICATION_CHANNEL_ID, VERIFIED_ROLE_ID, GENIUS_ROLE_IDS, KEEP_ALIVE_INTERVAL
    global CMD_PREFIX, ENABLE_COMMAND_PING, ENABLE_COMMAND_TEST_WELCOME
    global WELCOME_REACTION_ENABLED, WELCOME_MESSAGE_TEXT
    global VERIFICATION_EMBED_TITLE, VERIFICATION_EMBED_DESCRIPTION, VERIFICATION_BUTTON_LABEL

    config._load_config()
    
    # Actualizar variables globales
    TOKEN = get_config("DISCORD_TOKEN")
    GENIUS_CLIENT_ID = get_config("GENIUS_CLIENT_ID")
    GENIUS_CLIENT_SECRET = get_config("GENIUS_CLIENT_SECRET")
    BASE_URL = get_config("BASE_URL", "https://geebot.onrender.com")
    VERIFICATION_CHANNEL_ID = get_config("VERIFICATION_CHANNEL_ID", "0", int)
    VERIFIED_ROLE_ID = get_config("VERIFIED_ROLE_ID", "1404855696842821653", int)
    KEEP_ALIVE_INTERVAL = get_config("KEEP_ALIVE_INTERVAL", 300, int)

    # Sección: Comandos
    CMD_PREFIX = get_config("CMD_PREFIX", "!!")
    ENABLE_COMMAND_PING = get_config("ENABLE_COMMAND_PING", "true").lower() == "true"
    ENABLE_COMMAND_TEST_WELCOME = get_config("ENABLE_COMMAND_TEST_WELCOME", "true").lower() == "true"

    # Sección: Mensajes
    WELCOME_REACTION_ENABLED = get_config("WELCOME_REACTION_ENABLED", "true").lower() == "true"
    WELCOME_MESSAGE_TEXT = get_config("WELCOME_MESSAGE_TEXT", "")

    # Sección: Verificación
    VERIFICATION_EMBED_TITLE = get_config("VERIFICATION_EMBED_TITLE", "Verificación con Genius")
    VERIFICATION_EMBED_DESCRIPTION = get_config("VERIFICATION_EMBED_DESCRIPTION", "Conecta tu cuenta de Genius para obtener roles.")
    VERIFICATION_BUTTON_LABEL = get_config("VERIFICATION_BUTTON_LABEL", "Verificar con Genius")
    
    # Actualizar roles
    GENIUS_ROLE_IDS = {
        "Verified Artist": get_config("ROLE_VERIFIED_ARTIST", "1404856059717484684", int),
        "Staff": get_config("ROLE_STAFF", "1404856078394724463", int),
        "Moderator": get_config("ROLE_MODERATOR", "1404855980738740385", int),
        "Editor": get_config("ROLE_EDITOR", "1404855934764847194", int),
        "Transcriber": get_config("ROLE_TRANSCRIBER", "1404855862710763630", int),
        "Mediator": get_config("ROLE_MEDIATOR", "1404855801201557514", int),
        "Contributor": get_config("ROLE_CONTRIBUTOR", "1404855696842821653", int)
    }
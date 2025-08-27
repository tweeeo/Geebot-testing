from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import bcrypt
import os
import json
import time
from typing import Dict, Any
import secrets
from pathlib import Path

# Configuración
PANEL_USERNAME = os.environ.get("PANEL_USERNAME", "tweo")
PANEL_PASSWORD_HASH = os.environ.get("PANEL_PASSWORD_HASH")

# Si no hay hash configurado, usar contraseña por defecto "mateo856794123"
if not PANEL_PASSWORD_HASH:
    PANEL_PASSWORD_HASH = bcrypt.hashpw("mateo856794123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    print("⚠️ Usando contraseña por defecto 'mateo856794123'. Configura PANEL_PASSWORD_HASH en producción.")

# Permitir múltiples usuarios de panel
allowed_users = {
    PANEL_USERNAME: PANEL_PASSWORD_HASH,
}
# Agregar accesos solicitados (hash generados en tiempo de arranque)
additional_plain_users = {
    "fri": "friadminiqgaming",
    "polka": "polkadelamusic69",
}
for uname, pwd in additional_plain_users.items():
    try:
        allowed_users[uname] = bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    except Exception:
        pass

app = FastAPI(title="GeeBot Control Panel", description="Panel de control para configurar el bot")
security = HTTPBasic()

# Middleware para logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log solo para rutas importantes (no health checks constantes)
    if request.url.path != "/health":
        print(f"📝 {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    
    return response

# Configurar templates y archivos estáticos
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "assets" / "panel_templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "assets" / "static")), name="static")

# Favicon por defecto para todas las páginas del panel
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import FileResponse
    return FileResponse(str(BASE_DIR / "assets" / "static" / "favicon.ico"))

# Configuración actual del bot
CONFIG_MAPPING = {
    "DISCORD_TOKEN": {
        "name": "Discord Bot Token",
        "type": "password",
        "description": "Token del bot de Discord",
        "required": True
    },
    "GENIUS_CLIENT_ID": {
        "name": "Genius Client ID",
        "type": "text",
        "description": "ID de cliente de la aplicación Genius",
        "required": True
    },
    "GENIUS_CLIENT_SECRET": {
        "name": "Genius Client Secret",
        "type": "password",
        "description": "Secreto de cliente de la aplicación Genius",
        "required": True
    },
    "BASE_URL": {
        "name": "URL Base",
        "type": "url",
        "description": "URL base del servidor (ej: https://geebot.onrender.com)",
        "required": True
    },
    "VERIFICATION_CHANNEL_ID": {
        "name": "Canal de Verificación",
        "type": "number",
        "description": "ID del canal donde estará el botón de verificación",
        "required": True
    },
    "VERIFIED_ROLE_ID": {
        "name": "Rol Verificado",
        "type": "number",
        "description": "ID del rol general para usuarios verificados",
        "required": True
    },
    "ROLE_VERIFIED_ARTIST": {
        "name": "Rol Artista Verificado",
        "type": "number",
        "description": "ID del rol para artistas verificados",
        "required": False
    },
    "ROLE_STAFF": {
        "name": "Rol Staff",
        "type": "number",
        "description": "ID del rol para staff",
        "required": False
    },
    "ROLE_MODERATOR": {
        "name": "Rol Moderador",
        "type": "number",
        "description": "ID del rol para moderadores",
        "required": False
    },
    "ROLE_EDITOR": {
        "name": "Rol Editor",
        "type": "number",
        "description": "ID del rol para editores",
        "required": False
    },
    "ROLE_TRANSCRIBER": {
        "name": "Rol Transcriptor",
        "type": "number",
        "description": "ID del rol para transcriptores",
        "required": False
    },
    "ROLE_MEDIATOR": {
        "name": "Rol Mediador",
        "type": "number",
        "description": "ID del rol para mediadores",
        "required": False
    },
    "ROLE_CONTRIBUTOR": {
        "name": "Rol Contribuidor",
        "type": "number",
        "description": "ID del rol para contribuidores",
        "required": False
    },
    "KEEP_ALIVE_INTERVAL": {
        "name": "Intervalo Keep-Alive",
        "type": "number",
        "description": "Intervalo en segundos para keep-alive (300 = 5 minutos)",
        "required": False
    },
    # Configuraciones de comandos habilitados
    "ENABLE_COMMAND_VERIFIED_LIST": {
        "name": "Habilitar comando verified_list",
        "type": "checkbox",
        "description": "Permite usar el comando para listar usuarios verificados",
        "required": False
    },
    "ENABLE_COMMAND_TEST_ROLES": {
        "name": "Habilitar comando test_roles",
        "type": "checkbox",
        "description": "Permite usar el comando para probar asignación de roles",
        "required": False
    },
    "ENABLE_COMMAND_LIST_ROLES": {
        "name": "Habilitar comando list_roles",
        "type": "checkbox",
        "description": "Permite usar el comando para listar roles del servidor",
        "required": False
    },
    "ENABLE_COMMAND_SHOW_CONFIG": {
        "name": "Habilitar comando show_config",
        "type": "checkbox",
        "description": "Permite usar el comando para mostrar configuración",
        "required": False
    },
    "ENABLE_COMMAND_CLEANUP_VERIFICATIONS": {
        "name": "Habilitar comando cleanup_verifications",
        "type": "checkbox",
        "description": "Permite usar el comando para limpiar verificaciones",
        "required": False
    },
    "ENABLE_COMMAND_SYNC": {
        "name": "Habilitar comando sync",
        "type": "checkbox",
        "description": "Permite usar el comando para sincronizar comandos slash",
        "required": False
    },
    "ENABLE_COMMAND_BOT_STATS": {
        "name": "Habilitar comando bot_stats",
        "type": "checkbox",
        "description": "Permite usar el comando para mostrar estadísticas del bot",
        "required": False
    }
}

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verificar credenciales de autenticación (soporte multiusuario)"""
    uname = credentials.username
    pwd = credentials.password

    # Intento con usuario principal
    if secrets.compare_digest(uname, PANEL_USERNAME):
        if bcrypt.checkpw(pwd.encode('utf-8'), PANEL_PASSWORD_HASH.encode('utf-8')):
            return uname

    # Intento con usuarios adicionales
    stored = allowed_users.get(uname)
    if stored and bcrypt.checkpw(pwd.encode('utf-8'), stored.encode('utf-8')):
        return uname

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales incorrectas",
        headers={"WWW-Authenticate": "Basic"},
    )

def get_current_config() -> Dict[str, Any]:
    """Obtener configuración actual desde sistema dinámico"""
    from src.utils.dynamic_config import config as dynamic_config
    
    result = {}
    for key, info in CONFIG_MAPPING.items():
        value = dynamic_config.get(key, "")
        # Ocultar valores sensibles para mostrar
        if info["type"] == "password" and value:
            result[key] = "●" * 8  # Mostrar asteriscos
        else:
            result[key] = value
    return result

def get_raw_config() -> Dict[str, Any]:
    """Obtener configuración actual sin ocultar valores"""
    from src.utils.dynamic_config import config as dynamic_config
    
    result = {}
    for key in CONFIG_MAPPING.keys():
        result[key] = dynamic_config.get(key, "")
    return result

async def notify_bot_config_reload():
    """Notificar al bot que debe recargar su configuración"""
    try:
        # Importar y recargar configuración del bot
        from src.utils.config import reload_config
        reload_config()
        print("🔄 Bot notificado para recargar configuración")
    except Exception as e:
        print(f"⚠️ Error notificando al bot: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint para Render"""
    return {"status": "healthy", "service": "geebot-panel", "timestamp": "2024-01-01T12:00:00Z"}

@app.get("/api/bot-status")
async def api_bot_status():
    """API endpoint para obtener estado del bot"""
    try:
        from src.utils.bot_instance import get_bot_stats
        stats = get_bot_stats()
        return stats
    except Exception as e:
        return {"status": "error", "message": str(e), "guilds": 0, "users": 0, "latency": 0}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(verify_credentials)):
    """Panel principal"""
    config = get_current_config()
    
    # Estadísticas básicas
    stats = {
        "total_configs": len(CONFIG_MAPPING),
        "configured": sum(1 for v in get_raw_config().values() if v),
        "missing": sum(1 for v in get_raw_config().values() if not v)
    }
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": username,
        "config": config,
        "config_mapping": CONFIG_MAPPING,
        "stats": stats
    })

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, username: str = Depends(verify_credentials)):
    """Página de configuración"""
    config = get_raw_config()
    
    return templates.TemplateResponse("config.html", {
        "request": request,
        "username": username,
        "config": config,
        "config_mapping": CONFIG_MAPPING
    })

# ----------------------
# Configuración avanzada: Comandos y Mensajes
# ----------------------

# Mapeo de configuración por secciones
COMMANDS_CONFIG_MAPPING = {
    "CMD_PREFIX": {
        "name": "Prefijo de Comandos",
        "type": "text",
        "description": "Prefijo para comandos con texto (ej: !!)",
        "required": False
    },
    "ENABLE_COMMAND_PING": {
        "name": "Habilitar comando ping",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!ping",
        "required": False
    },
    "ENABLE_COMMAND_TEST_WELCOME": {
        "name": "Habilitar comando test_welcome",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!test_welcome",
        "required": False
    },
    "ENABLE_COMMAND_HELP": {
        "name": "Habilitar comando help",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!help",
        "required": False
    },
    "ENABLE_COMMAND_TEST": {
        "name": "Habilitar comando test",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!test",
        "required": False
    },
    "ENABLE_COMMAND_SETUP_VERIFICATION": {
        "name": "Habilitar comando setup_verification",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!setup_verification",
        "required": False
    },
    "ENABLE_COMMAND_VERIFY_STATUS": {
        "name": "Habilitar comando verify_status",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!verify_status",
        "required": False
    },
    "ENABLE_COMMAND_UNVERIFY": {
        "name": "Habilitar comando unverify",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!unverify",
        "required": False
    },
    "ENABLE_COMMAND_VERIFIED_LIST": {
        "name": "Habilitar comando verified_list",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!verified_list",
        "required": False
    },
    "ENABLE_COMMAND_TEST_ROLES": {
        "name": "Habilitar comando test_roles",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!test_roles",
        "required": False
    },
    "ENABLE_COMMAND_LIST_ROLES": {
        "name": "Habilitar comando list_roles",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!list_roles",
        "required": False
    },
    "ENABLE_COMMAND_SHOW_CONFIG": {
        "name": "Habilitar comando show_config",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!show_config",
        "required": False
    },
    "ENABLE_COMMAND_CLEANUP_VERIFICATIONS": {
        "name": "Habilitar comando cleanup_verifications",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!cleanup_verifications",
        "required": False
    },
    "ENABLE_COMMAND_SYNC": {
        "name": "Habilitar comando sync",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!sync",
        "required": False
    },
    "ENABLE_COMMAND_BOT_STATS": {
        "name": "Habilitar comando bot_stats",
        "type": "checkbox",
        "description": "Activa o desactiva el comando !!bot_stats",
        "required": False
    }
}

MESSAGES_CONFIG_MAPPING = {
    "WELCOME_REACTION_ENABLED": {
        "name": "Reacciones de Bienvenida",
        "type": "checkbox",
        "description": "Habilita reacciones automáticas a mensajes de bienvenida",
        "required": False
    },
    "WELCOME_MESSAGE_TEXT": {
        "name": "Texto de Bienvenida",
        "type": "textarea",
        "description": "Mensaje que puede usar el bot para bienvenida",
        "required": False
    },
    "SUCCESS_VERIFICATION_MESSAGE": {
        "name": "Mensaje de Verificación Exitosa",
        "type": "textarea",
        "description": "Mensaje mostrado cuando la verificación es exitosa",
        "required": False
    },
    "ERROR_VERIFICATION_MESSAGE": {
        "name": "Mensaje de Error en Verificación",
        "type": "textarea",
        "description": "Mensaje mostrado cuando hay error en la verificación",
        "required": False
    },
    "OAUTH_ERROR_MESSAGE": {
        "name": "Mensaje de Error OAuth",
        "type": "textarea",
        "description": "Mensaje mostrado cuando hay error en el proceso OAuth",
        "required": False
    },
    "ALREADY_VERIFIED_MESSAGE": {
        "name": "Mensaje Usuario Ya Verificado",
        "type": "textarea",
        "description": "Mensaje para usuarios que ya están verificados",
        "required": False
    },
    "VERIFICATION_TIMEOUT_MESSAGE": {
        "name": "Mensaje de Timeout en Verificación",
        "type": "textarea",
        "description": "Mensaje cuando expira el tiempo de verificación",
        "required": False
    },
    "ROLE_ASSIGNMENT_SUCCESS_MESSAGE": {
        "name": "Mensaje de Asignación de Rol Exitosa",
        "type": "textarea",
        "description": "Mensaje cuando se asigna un rol correctamente",
        "required": False
    },
    "ROLE_ASSIGNMENT_ERROR_MESSAGE": {
        "name": "Mensaje de Error en Asignación de Rol",
        "type": "textarea",
        "description": "Mensaje cuando hay error al asignar un rol",
        "required": False
    }
}

VERIFICATION_CONFIG_MAPPING = {
    "VERIFICATION_EMBED_TITLE": {
        "name": "Título del Embed de Verificación",
        "type": "text",
        "description": "Título mostrado en el embed del flujo de verificación",
        "required": False
    },
    "VERIFICATION_EMBED_DESCRIPTION": {
        "name": "Descripción del Embed de Verificación",
        "type": "textarea",
        "description": "Descripción para el embed de verificación",
        "required": False
    },
    "VERIFICATION_BUTTON_LABEL": {
        "name": "Texto del Botón de Verificación",
        "type": "text",
        "description": "Etiqueta del botón de verificación",
        "required": False
    }
}

@app.get("/config/commands", response_class=HTMLResponse)
async def config_commands_page(request: Request, username: str = Depends(verify_credentials)):
    from src.utils.dynamic_config import config as dynamic_config
    data = {k: (dynamic_config.get(k, "") or "") for k in COMMANDS_CONFIG_MAPPING.keys()}
    return templates.TemplateResponse("config_commands.html", {
        "request": request,
        "username": username,
        "config": data,
        "mapping": COMMANDS_CONFIG_MAPPING
    })

@app.post("/config/commands/update")
async def update_commands_config(request: Request, username: str = Depends(verify_credentials)):
    from src.utils.dynamic_config import config as dynamic_config
    form = await request.form()

    updates = {}
    updated_list = []
    errors = []

    for key, info in COMMANDS_CONFIG_MAPPING.items():
        if info["type"] == "checkbox":
            new_value = "true" if form.get(key) == "on" else "false"
        else:
            new_value = (form.get(key) or "").strip()

        current = dynamic_config.get(key, "") or ""
        if new_value != current:
            updates[key] = new_value
            updated_list.append(info["name"])

    if updates:
        if not dynamic_config.update_multiple(updates):
            errors.append("Error al guardar configuraciones de comandos")
        else:
            from src.utils.config import reload_config
            reload_config()

    return templates.TemplateResponse("config_success.html", {
        "request": request,
        "username": username,
        "updated_configs": updated_list,
        "errors": errors
    })

@app.get("/config/messages", response_class=HTMLResponse)
async def config_messages_page(request: Request, username: str = Depends(verify_credentials)):
    from src.utils.dynamic_config import config as dynamic_config
    data = {k: (dynamic_config.get(k, "") or "") for k in MESSAGES_CONFIG_MAPPING.keys()}
    return templates.TemplateResponse("config_messages.html", {
        "request": request,
        "username": username,
        "config": data,
        "mapping": MESSAGES_CONFIG_MAPPING
    })

@app.post("/config/messages/update")
async def update_messages_config(request: Request, username: str = Depends(verify_credentials)):
    from src.utils.dynamic_config import config as dynamic_config
    form = await request.form()

    updates = {}
    updated_list = []
    errors = []

    for key, info in MESSAGES_CONFIG_MAPPING.items():
        if info["type"] == "checkbox":
            new_value = "true" if form.get(key) == "on" else "false"
        elif info["type"] == "textarea":
            new_value = (form.get(key) or "").strip()
        else:
            new_value = (form.get(key) or "").strip()

        current = dynamic_config.get(key, "") or ""
        if new_value != current:
            updates[key] = new_value
            updated_list.append(info["name"])

    if updates:
        if not dynamic_config.update_multiple(updates):
            errors.append("Error al guardar configuraciones de mensajes")
        else:
            from src.utils.config import reload_config
            reload_config()

    return templates.TemplateResponse("config_success.html", {
        "request": request,
        "username": username,
        "updated_configs": updated_list,
        "errors": errors
    })

@app.get("/config/verification", response_class=HTMLResponse)
async def config_verification_page(request: Request, username: str = Depends(verify_credentials)):
    from src.utils.dynamic_config import config as dynamic_config
    data = {k: (dynamic_config.get(k, "") or "") for k in VERIFICATION_CONFIG_MAPPING.keys()}
    return templates.TemplateResponse("config_verification.html", {
        "request": request,
        "username": username,
        "config": data,
        "mapping": VERIFICATION_CONFIG_MAPPING
    })

@app.post("/config/verification/update")
async def update_verification_config(request: Request, username: str = Depends(verify_credentials)):
    from src.utils.dynamic_config import config as dynamic_config
    form = await request.form()

    updates = {}
    updated_list = []
    errors = []

    for key, info in VERIFICATION_CONFIG_MAPPING.items():
        new_value = (form.get(key) or "").strip()
        current = dynamic_config.get(key, "") or ""
        if new_value != current:
            updates[key] = new_value
            updated_list.append(info["name"])

    if updates:
        if not dynamic_config.update_multiple(updates):
            errors.append("Error al guardar configuraciones de verificación")
        else:
            from src.utils.config import reload_config
            reload_config()

    return templates.TemplateResponse("config_success.html", {
        "request": request,
        "username": username,
        "updated_configs": updated_list,
        "errors": errors
    })

@app.post("/config/update")
async def update_config(request: Request, username: str = Depends(verify_credentials)):
    """Actualizar configuración"""
    from src.utils.dynamic_config import config as dynamic_config
    
    form_data = await request.form()
    
    updated_configs = []
    errors = []
    configs_to_update = {}
    
    for key, info in CONFIG_MAPPING.items():
        if info["type"] == "checkbox":
            # Para checkboxes, si está presente en form_data significa que está marcado
            new_value = "true" if key in form_data else "false"
        else:
            new_value = form_data.get(key, "").strip()
        
        # Validaciones básicas
        if info["required"] and not new_value:
            errors.append(f"{info['name']} es requerido")
            continue
            
        if info["type"] == "number" and new_value:
            try:
                int(new_value)
            except ValueError:
                errors.append(f"{info['name']} debe ser un número válido")
                continue
        
        # Verificar si el valor cambió
        current_value = dynamic_config.get(key, "")
        if new_value != current_value:
            configs_to_update[key] = new_value
            updated_configs.append(info["name"])
    
    if errors:
        config = get_raw_config()
        return templates.TemplateResponse("config.html", {
            "request": request,
            "username": username,
            "config": config,
            "config_mapping": CONFIG_MAPPING,
            "errors": errors
        })
    
    # Actualizar configuraciones en la base de datos
    if configs_to_update:
        success = dynamic_config.update_multiple(configs_to_update)
        if not success:
            errors.append("Error al guardar las configuraciones")
            config = get_raw_config()
            return templates.TemplateResponse("config.html", {
                "request": request,
                "username": username,
                "config": config,
                "config_mapping": CONFIG_MAPPING,
                "errors": errors
            })
        
        # Recargar configuración del bot si está disponible
        try:
            from src.utils.config import reload_config
            reload_config()
            print(f"✅ Configuración recargada: {', '.join(updated_configs)}")
            
            # Intentar notificar al bot para que recargue su configuración
            try:
                import asyncio
                from src.bot.main import bot
                if bot and not bot.is_closed():
                    # Crear tarea para recargar configuración del bot
                    asyncio.create_task(notify_bot_config_reload())
            except:
                pass
                
        except Exception as e:
            print(f"⚠️ Error recargando configuración: {e}")
            pass  # El bot puede no estar ejecutándose aún
    
    # Redirigir con mensaje de éxito
    return templates.TemplateResponse("config_success.html", {
        "request": request,
        "username": username,
        "updated_configs": updated_configs
    })

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, username: str = Depends(verify_credentials)):
    """Página de logs (placeholder para futuras implementaciones)"""
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "username": username,
        "logs": ["Panel de logs en desarrollo..."]
    })

@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request, username: str = Depends(verify_credentials)):
    """Página de estado del bot"""
    # Intentar obtener estado del bot
    bot_status = "unknown"
    bot_stats = {}

    try:
        from src.utils.bot_instance import is_bot_ready, get_bot_stats
        bot_stats = get_bot_stats()
        bot_status = bot_stats.get("status", "unknown")
    except Exception:
        bot_status = "offline"
        bot_stats = {
            "status": "offline",
            "guilds": 0,
            "users": 0,
            "latency": 0
        }

    # Obtener estadísticas de la base de datos (verificados y pendientes)
    db_stats = {"verified_users": 0, "pending_verifications": 0}
    try:
        from src.database.models import db
        db_stats = await db.get_stats()
    except Exception:
        pass

    # Verificar configuración
    raw_config = get_raw_config()
    # Solo verificar campos requeridos
    required_configs = {k: v for k, v in raw_config.items() if CONFIG_MAPPING[k]["required"]}
    config_complete = all(value for value in required_configs.values())

    status_info = {
        "bot_status": bot_status,
        "config_status": "configured" if config_complete else "incomplete",
        "bot_stats": bot_stats,
        "database": db_stats
    }

    return templates.TemplateResponse("status.html", {
        "request": request,
        "username": username,
        "status": status_info,
        "config": get_current_config()
    })

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PANEL_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
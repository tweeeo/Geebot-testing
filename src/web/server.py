from quart import Quart, request, redirect, render_template_string, render_template, jsonify
import aiohttp
from src.database.models import db
import asyncio
from urllib.parse import urlencode
import logging
import time
import os
import sys
from datetime import datetime

app = Quart(__name__)

# Configurar carpetas para templates y archivos estáticos
# Usar rutas absolutas para Render
template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'templates')
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'static')

app.template_folder = template_dir
app.static_folder = static_dir

# Debug: Verificar que las carpetas existen
print(f"📁 Template folder: {template_dir} - Exists: {os.path.exists(template_dir)}")
print(f"📁 Static folder: {static_dir} - Exists: {os.path.exists(static_dir)}")
if os.path.exists(template_dir):
    print(f"📄 Templates found: {os.listdir(template_dir)}")
if os.path.exists(static_dir):
    print(f"🎨 Static files found: {os.listdir(static_dir)}")

# Ruta explícita para servir archivos estáticos
@app.route('/static/<path:filename>')
async def serve_static(filename):
    """Sirve archivos estáticos"""
    try:
        from quart import send_from_directory
        return await send_from_directory(app.static_folder, filename)
    except Exception as e:
        logger.error(f"Error serving static file {filename}: {e}")
        return "File not found", 404

# Favicon por defecto en todas las páginas
@app.route('/favicon.ico')
async def favicon():
    try:
        from quart import send_from_directory
        return await send_from_directory(app.static_folder, 'favicon.ico')
    except Exception as e:
        logger.error(f"Error serving favicon: {e}")
        return "", 204

# Middleware para actualizar actividad en todas las rutas
@app.before_request
async def update_activity():
    """Actualiza la última actividad en cada request"""
    global last_activity, keep_alive_stats
    last_activity = time.time()
    keep_alive_stats["requests_count"] += 1

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales para keep-alive
server_start_time = time.time()
last_activity = time.time()
keep_alive_stats = {
    "requests_count": 0,
    "last_ping": None,
    "uptime_seconds": 0
}

class GeniusAPI:
    BASE_URL = "https://api.genius.com"
    
    @staticmethod
    async def exchange_code_for_token(code: str) -> str:
        """Intercambia el código de autorización por un access token"""
        from src.utils.dynamic_config import config
        async with aiohttp.ClientSession() as session:
            data = {
                "code": code,
                "client_id": config.get('GENIUS_CLIENT_ID', ''),
                "client_secret": config.get('GENIUS_CLIENT_SECRET', ''),
                "redirect_uri": config.get('GENIUS_REDIRECT_URI', ''),
                "response_type": "code",
                "grant_type": "authorization_code"
            }
            
            async with session.post(f"{GeniusAPI.BASE_URL}/oauth/token", json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("access_token")
                else:
                    error_text = await response.text()
                    logger.error(f"Error getting access token: {response.status} - {error_text}")
                    raise Exception(f"Error getting access token: {response.status}")
    
    @staticmethod
    async def get_user_info(access_token: str) -> dict:
        """Obtiene la información del usuario autenticado"""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{GeniusAPI.BASE_URL}/account", headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    user_data = result.get("response", {}).get("user", {})
                    
                    # Extraer roles del usuario basado en la estructura real de la API de Genius
                    roles = []

                    # Log completo de la respuesta para debug (solo campos relevantes)
                    logger.info(f"Usuario: {user_data.get('name')} (IQ: {user_data.get('iq', 0)})")
                    logger.info(f"Role for display: {user_data.get('role_for_display')}")
                    logger.info(f"Human readable role: {user_data.get('human_readable_role_for_display')}")
                    logger.info(f"Roles for display: {user_data.get('roles_for_display', [])}")

                    # MÉTODO PRINCIPAL: Usar roles_for_display (más preciso)
                    roles_for_display = user_data.get("roles_for_display", [])
                    if roles_for_display:
                        logger.info(f"🎯 Usando roles_for_display: {roles_for_display}")

                        # Mapear roles de Genius a nuestros roles
                        role_mapping = {
                            "verified_artist": "Verified Artist",
                            "staff": "Staff",
                            "moderator": "Moderator",
                            "editor": "Editor",
                            "transcriber": "Transcriber",
                            "mediator": "Mediator",
                            "contributor": "Contributor"
                        }

                        for genius_role in roles_for_display:
                            genius_role_lower = genius_role.lower()
                            if genius_role_lower in role_mapping:
                                mapped_role = role_mapping[genius_role_lower]
                                if mapped_role not in roles:
                                    roles.append(mapped_role)
                                    logger.info(f"✅ Detected: {mapped_role} (from roles_for_display)")
                            else:
                                logger.warning(f"⚠️ Rol no mapeado en roles_for_display: {genius_role}")

                    # MÉTODO SECUNDARIO: Verificar campos específicos si no hay roles_for_display
                    if not roles:
                        logger.info("🔍 No se encontró roles_for_display, usando métodos alternativos...")

                        # Verificar Verified Artist
                        artist_data = user_data.get("artist", {})
                        if artist_data and artist_data.get("is_verified"):
                            roles.append("Verified Artist")
                            logger.info("✅ Detected: Verified Artist")

                        # Verificar Staff
                        if user_data.get("staff") or user_data.get("is_staff"):
                            roles.append("Staff")
                            logger.info("✅ Detected: Staff")

                        # Verificar por role_for_display individual
                        role_display = user_data.get("role_for_display", "").lower()
                        if role_display:
                            if "staff" in role_display:
                                roles.append("Staff")
                                logger.info("✅ Detected: Staff (role_for_display)")
                            elif "moderator" in role_display:
                                roles.append("Moderator")
                                logger.info("✅ Detected: Moderator (role_for_display)")
                            elif "editor" in role_display:
                                roles.append("Editor")
                                logger.info("✅ Detected: Editor (role_for_display)")
                            elif "transcriber" in role_display:
                                roles.append("Transcriber")
                                logger.info("✅ Detected: Transcriber (role_for_display)")
                            elif "mediator" in role_display:
                                roles.append("Mediator")
                                logger.info("✅ Detected: Mediator (role_for_display)")

                        # Siempre asignar Contributor como rol base si no hay otros
                        if not roles:
                            roles.append("Contributor")
                            logger.info("✅ Detected: Contributor (rol base)")

                    logger.info(f"🎯 Roles finales detectados: {roles}")
                    
                    return {
                        "id": user_data.get("id"),
                        "login": user_data.get("login"),
                        "name": user_data.get("name") or user_data.get("login"),
                        "roles": roles,
                        "iq": user_data.get("iq", 0),
                        "avatar_url": user_data.get("avatar", {}).get("medium", {}).get("url")
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Error getting user info: {response.status} - {error_text}")
                    raise Exception(f"Error getting user info: {response.status}")

@app.route("/")
async def index():
    try:
        # Obtener datos básicos para la página principal
        uptime_seconds = int(time.time() - server_start_time)
        
        # Verificar estado del bot
        bot_status = "unknown"
        try:
            from src.utils.bot_instance import is_bot_ready
            if is_bot_ready():
                bot_status = "online"
            else:
                bot_status = "connecting"
        except Exception:
            bot_status = "offline"
        
        template_data = {
            "bot_status": bot_status,
            "uptime": format_uptime(uptime_seconds),
            "requests_count": keep_alive_stats["requests_count"],
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        }
        
        return await render_template("index.html", **template_data)
    except Exception as e:
        logger.error(f"❌ Error rendering index.html: {e}")
        return f"""
        <html>
        <head><title>GeeBot - Error</title></head>
        <body>
            <h1>🤖 GeeBot - Error de Template</h1>
            <p>Error: {str(e)}</p>
            <p>Template folder: {app.template_folder}</p>
            <p>Static folder: {app.static_folder}</p>
            <p>Working directory: {os.getcwd()}</p>
            <hr>
            <h2>Debug Info:</h2>
            <p>Templates exist: {os.path.exists(app.template_folder)}</p>
            <p>Static exist: {os.path.exists(app.static_folder)}</p>
            {f"<p>Templates: {os.listdir(app.template_folder)}</p>" if os.path.exists(app.template_folder) else ""}
        </body>
        </html>
        """, 500

@app.route("/debug")
async def debug():
    """Ruta de debug para verificar configuración"""
    from src.utils.dynamic_config import config
    debug_data = {
        "status": "debug",
        "config": {
            "base_url": config.get('BASE_URL', ''),
            "redirect_uri": config.get('GENIUS_REDIRECT_URI', ''),
            "client_id_configured": bool(config.get('GENIUS_CLIENT_ID', '')),
            "client_secret_configured": bool(config.get('GENIUS_CLIENT_SECRET', '')),
            "template_folder": app.template_folder,
            "static_folder": app.static_folder,
            "templates_exist": os.path.exists(app.template_folder),
            "static_exist": os.path.exists(app.static_folder),
            "working_directory": os.getcwd()
        }
    }
    
    # Si se solicita JSON específicamente, devolver JSON
    if request.args.get('format') == 'json':
        return jsonify(debug_data)
    
    # Por defecto, mostrar página bonita
    try:
        return await render_template("debug.html", data=debug_data)
    except Exception as e:
        logger.error(f"❌ Error rendering debug.html: {e}")
        return jsonify(debug_data)

@app.route("/auth")
async def auth():
    """Inicia el proceso de autenticación OAuth2"""
    from src.utils.dynamic_config import config
    
    state = request.args.get("state")
    if not state:
        return await render_template("error.html", error_message="Estado de verificación inválido")
    
    # Obtener configuración dinámica
    genius_client_id = config.get('GENIUS_CLIENT_ID', '')
    genius_client_secret = config.get('GENIUS_CLIENT_SECRET', '')
    genius_redirect_uri = config.get('GENIUS_REDIRECT_URI', '')
    
    # Debug: Verificar configuración
    logger.info(f"🔧 OAuth Config - Client ID: {genius_client_id[:10] if genius_client_id else 'NOT SET'}...")
    logger.info(f"🔧 OAuth Config - Redirect URI: {genius_redirect_uri}")
    logger.info(f"🔧 OAuth Config - State: {state}")
    
    # Verificar que las credenciales estén configuradas
    if not genius_client_id or not genius_client_secret:
        logger.error("❌ Credenciales de Genius no configuradas")
        return await render_template("error.html", 
                                   error_message="Error de configuración: Credenciales de Genius no encontradas")
    
    # Construir URL de autorización
    params = {
        "client_id": genius_client_id,
        "redirect_uri": genius_redirect_uri,
        "scope": "me",  # Scope básico para obtener información del usuario
        "state": state,
        "response_type": "code"
    }
    
    auth_url = f"https://api.genius.com/oauth/authorize?{urlencode(params)}"
    logger.info(f"🔗 Redirecting to: {auth_url}")
    return redirect(auth_url)

@app.route("/callback")
async def callback():
    """Maneja el callback de OAuth2"""
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    
    if error:
        return await render_template("error.html", 
                                          error_message=f"Error de autorización: {error}")
    
    if not code or not state:
        return await render_template("error.html", 
                                          error_message="Parámetros de callback inválidos")
    
    try:
        # Obtener discord_id del estado
        discord_id = await db.get_pending_verification(state)
        if not discord_id:
            return await render_template("error.html", 
                                              error_message="Estado de verificación expirado o inválido")
        
        # Intercambiar código por token
        access_token = await GeniusAPI.exchange_code_for_token(code)
        if not access_token:
            return await render_template("error.html", 
                                              error_message="Error al obtener token de acceso")
        
        # Obtener información del usuario
        user_info = await GeniusAPI.get_user_info(access_token)
        
        # Guardar verificación en la base de datos
        await db.save_verification(discord_id, user_info, access_token)
        
        # Notificar al bot que la verificación está completa
        asyncio.create_task(handle_verification_complete(discord_id, user_info))
        
        return await render_template("success.html",
                                          genius_name=user_info["name"],
                                          genius_username=user_info["login"],
                                          genius_roles=user_info["roles"],
                                          genius_iq=user_info.get("iq"),
                                          genius_avatar=user_info.get("avatar_url"))
        
    except Exception as e:
        logger.error(f"Error in callback: {str(e)}")
        return await render_template("error.html", 
                                          error_message=f"Error interno: {str(e)}")

# ============================================================================
# KEEP-ALIVE ENDPOINTS
# ============================================================================

def format_uptime(seconds):
    """Formatea el uptime en formato legible"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{seconds}s"

def get_memory_usage():
    """Obtiene el uso de memoria del proceso en MB"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024  # Retorna número en MB
    except ImportError:
        return 0
    except Exception:
        return 0

@app.route("/ping")
async def ping():
    """Endpoint simple de ping para keep-alive"""
    global last_activity, keep_alive_stats
    
    last_activity = time.time()
    keep_alive_stats["requests_count"] += 1
    keep_alive_stats["last_ping"] = datetime.now().isoformat()
    keep_alive_stats["uptime_seconds"] = int(time.time() - server_start_time)
    
    # Obtener BOT_INSTANCE_ID usando el módulo compartido
    try:
        from src.utils.bot_instance import get_instance_id
        instance_id = get_instance_id()
    except Exception:
        instance_id = "unknown"
    
    ping_data = {
        "status": "alive",
        "message": "Bot server is running",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": keep_alive_stats["uptime_seconds"],
        "instance_id": instance_id
    }
    
    # Si se solicita JSON específicamente, devolver JSON
    if request.args.get('format') == 'json':
        return jsonify(ping_data)
    
    # Por defecto, mostrar página bonita
    try:
        return await render_template("simple_status.html", data=ping_data)
    except Exception as e:
        logger.error(f"❌ Error rendering simple_status.html: {e}")
        return jsonify(ping_data)

@app.route("/health")
async def health():
    """Endpoint de health check más detallado"""
    global last_activity, keep_alive_stats
    
    last_activity = time.time()
    keep_alive_stats["requests_count"] += 1
    uptime_seconds = int(time.time() - server_start_time)
    
    # Verificar estado del bot usando el módulo compartido
    bot_status = "unknown"
    bot_guilds = 0
    bot_users = 0
    bot_latency = None
    
    try:
        from src.utils.bot_instance import is_bot_ready, get_bot_guilds_count, get_bot_users_count, get_bot_latency, get_instance_id
        
        if is_bot_ready():
            bot_status = "ready"
            bot_guilds = get_bot_guilds_count()
            bot_users = get_bot_users_count()
            bot_latency = get_bot_latency()
        else:
            bot_status = "connecting"
    except ImportError as e:
        logger.warning(f"Error importing bot_instance module: {e}")
        bot_status = "error"
    except Exception as e:
        logger.warning(f"Error checking bot status: {e}")
        bot_status = "error"
    
    # Verificar base de datos
    db_status = "unknown"
    try:
        await db.init_db()  # Esto es seguro llamar múltiples veces
        db_status = "connected"
    except Exception as e:
        logger.warning(f"Error checking database: {e}")
        db_status = "error"
    
    # Obtener estadísticas de memoria
    memory_info = get_memory_usage()
    
    # Obtener estadísticas de la base de datos
    db_stats = {"verified_users": 0, "pending_verifications": 0}
    try:
        db_stats = await db.get_stats()
    except Exception as e:
        logger.warning(f"Error getting DB stats: {e}")
    
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": uptime_seconds,
        "uptime_human": format_uptime(uptime_seconds),
        "start_time": datetime.fromtimestamp(server_start_time).strftime("%d/%m/%Y %H:%M:%S"),
        "instance_id": get_instance_id(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "bot": {
            "status": bot_status,
            "guilds_count": bot_guilds,
            "users_count": bot_users if bot_users > 0 else "N/A",
            "latency": f"{bot_latency}ms" if bot_latency is not None else "N/A"
        },
        "server": {
            "status": "running",
            "requests_count": keep_alive_stats["requests_count"],
            "memory_usage": {
                "rss_mb": memory_info
            }
        },
        "database": {
            "status": db_status,
            "verified_users": db_stats.get("verified_users", 0),
            "pending_verifications": db_stats.get("pending_verifications", 0)
        },
        "services": {
            "genius_api": "online",
            "oauth_flow": "active"
        }
    }
    
    # Si se solicita JSON específicamente, devolver JSON
    if request.args.get('format') == 'json':
        return jsonify(health_data)
    
    # Por defecto, mostrar página bonita
    try:
        return await render_template("simple_status.html", data=health_data)
    except Exception as e:
        logger.error(f"❌ Error rendering simple_status.html: {e}")
        return jsonify(health_data)

@app.route("/status")
async def status():
    """Página de estado detallado del sistema"""
    global last_activity, keep_alive_stats
    
    last_activity = time.time()
    keep_alive_stats["requests_count"] += 1
    uptime_seconds = int(time.time() - server_start_time)
    
    # Verificar estado del bot
    bot_status = "unknown"
    bot_guilds = 0
    bot_users = 0
    bot_latency = None
    
    try:
        from src.utils.bot_instance import is_bot_ready, get_bot_guilds_count, get_bot_users_count, get_bot_latency, get_instance_id
        
        if is_bot_ready():
            bot_status = "ready"
            bot_guilds = get_bot_guilds_count()
            bot_users = get_bot_users_count()
            bot_latency = get_bot_latency()
        else:
            bot_status = "connecting"
    except ImportError as e:
        logger.warning(f"Error importing bot_instance module: {e}")
        bot_status = "error"
    except Exception as e:
        logger.warning(f"Error checking bot status: {e}")
        bot_status = "error"
    
    # Verificar base de datos
    db_status = "unknown"
    try:
        await db.init_db()
        db_status = "connected"
    except Exception as e:
        logger.warning(f"Error checking database: {e}")
        db_status = "error"
    
    # Obtener estadísticas de memoria
    memory_info = get_memory_usage()
    
    # Obtener estadísticas de la base de datos
    db_stats = {"verified_users": 0, "pending_verifications": 0}
    try:
        db_stats = await db.get_stats()
    except Exception as e:
        logger.warning(f"Error getting DB stats: {e}")
    
    status_data = {
        "status": "healthy",
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "uptime_seconds": uptime_seconds,
        "uptime_human": format_uptime(uptime_seconds),
        "start_time": datetime.fromtimestamp(server_start_time).strftime("%d/%m/%Y %H:%M:%S"),
        "instance_id": get_instance_id(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "bot": {
            "status": bot_status,
            "guilds_count": bot_guilds,
            "users_count": bot_users if bot_users > 0 else "N/A",
            "latency": f"{bot_latency}ms" if bot_latency is not None else "N/A"
        },
        "server": {
            "status": "running",
            "requests_count": keep_alive_stats["requests_count"],
            "memory_usage": {
                "rss_mb": memory_info
            }
        },
        "database": {
            "status": db_status,
            "verified_users": db_stats.get("verified_users", 0),
            "pending_verifications": db_stats.get("pending_verifications", 0)
        },
        "services": {
            "genius_api": "online",
            "oauth_flow": "active"
        }
    }
    
    # Si se solicita JSON específicamente, devolver JSON
    if request.args.get('format') == 'json':
        return jsonify(status_data)
    
    # Por defecto, mostrar página bonita usando el template status.html
    try:
        return await render_template("status.html", data=status_data)
    except Exception as e:
        logger.error(f"❌ Error rendering status.html: {e}")
        logger.error(f"❌ Error type: {type(e).__name__}")
        logger.error(f"❌ Error details: {str(e)}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return jsonify(status_data)

async def handle_verification_complete(discord_id: int, user_info: dict):
    """Maneja la verificación completada notificando al bot"""
    try:
        from src.utils.bot_instance import get_bot_instance, is_bot_ready
        
        bot = get_bot_instance()
        if bot and is_bot_ready():
            # Buscar el usuario en todos los servidores
            user = bot.get_user(discord_id)
            if not user:
                logger.warning(f"Usuario {discord_id} no encontrado en caché del bot")
                return
            
            # Buscar el usuario en los servidores donde está el bot
            for guild in bot.guilds:
                member = guild.get_member(discord_id)
                if member:
                    await assign_roles_to_member(member, user_info, guild)
                    break
        else:
            logger.warning("Bot no está listo para procesar verificación")
            
    except Exception as e:
        logger.error(f"Error manejando verificación completada: {e}")

async def assign_roles_to_member(member, user_info: dict, guild):
    """Asigna roles al miembro basado en su información de Genius"""
    try:
        from src.utils.dynamic_config import config
        
        roles_to_add = []
        
        # Agregar rol de verificado general
        verified_role_id = config.get('VERIFIED_ROLE_ID', '')
        if verified_role_id and verified_role_id.isdigit():
            verified_role = guild.get_role(int(verified_role_id))
            if verified_role:
                roles_to_add.append(verified_role)
        
        # Mapeo de roles de Genius
        genius_role_mapping = {
            "Contributor": config.get('ROLE_CONTRIBUTOR', ''),
            "Editor": config.get('ROLE_EDITOR', ''),
            "Moderator": config.get('ROLE_MODERATOR', ''),
            "Staff": config.get('ROLE_STAFF', ''),
            "Verified Artist": config.get('ROLE_VERIFIED_ARTIST', ''),
            "Transcriber": config.get('ROLE_TRANSCRIBER', ''),
            "Mediator": config.get('ROLE_MEDIATOR', '')
        }
        
        # Agregar roles específicos de Genius
        for genius_role in user_info.get("roles", []):
            role_id = genius_role_mapping.get(genius_role, '')
            if role_id and role_id.isdigit():
                role = guild.get_role(int(role_id))
                if role:
                    roles_to_add.append(role)
        
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason="Verificación con Genius completada")
            logger.info(f"✅ Roles asignados a {member}: {[role.name for role in roles_to_add]}")
        
        # Actualizar nickname si es posible
        try:
            genius_name = user_info.get("name", user_info.get("login", ""))
            if genius_name and genius_name != member.display_name:
                await member.edit(nick=genius_name, reason="Nickname de Genius")
                logger.info(f"✅ Nickname actualizado para {member}: {genius_name}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo actualizar nickname de {member}: {e}")
            
    except Exception as e:
        logger.error(f"Error asignando roles a {member}: {e}")

async def start_server():
    """Inicia el servidor web"""
    try:
        logger.info(f"🌐 Iniciando servidor web en {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
        await app.run_task(host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)
    except Exception as e:
        logger.error(f"Error iniciando servidor web: {e}")
        raise
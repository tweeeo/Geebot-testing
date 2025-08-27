#!/usr/bin/env python3
"""
Genius en Español Bot - Versión Unificada
Combina bot, servidor OAuth y panel en una sola aplicación
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Variables globales para el bot
discord_bot = None
bot_task = None

async def start_discord_bot():
    """Iniciar bot de Discord en background con validación y logs claros"""
    global discord_bot, bot_task
    try:
        from src.utils.dynamic_config import config

        # 1) Sincronizar variables de entorno críticas -> configuración dinámica si faltan
        env_token = os.environ.get('DISCORD_TOKEN')
        # Si hay token en entorno y difiere del guardado, sobrescribir DB para aplicarlo
        if env_token and env_token != config.get('DISCORD_TOKEN'):
            config.set('DISCORD_TOKEN', env_token, description='Token sincronizado desde entorno (override)')
        env_client = os.environ.get('GENIUS_CLIENT_ID')
        if env_client and not config.get('GENIUS_CLIENT_ID'):
            config.set('GENIUS_CLIENT_ID', env_client)
        env_secret = os.environ.get('GENIUS_CLIENT_SECRET')
        if env_secret and not config.get('GENIUS_CLIENT_SECRET'):
            config.set('GENIUS_CLIENT_SECRET', env_secret)
        env_base = os.environ.get('BASE_URL') or os.environ.get('RENDER_EXTERNAL_URL')
        if env_base and not config.get('BASE_URL'):
            config.set('BASE_URL', env_base)
        
        # Normalizar token (trim espacios/line breaks)
        token_raw = config.get('DISCORD_TOKEN')
        token = token_raw.strip() if isinstance(token_raw, str) else token_raw
        if not token:
            logger.error("❌ DISCORD_TOKEN no configurado")
            return

        # Validación básica de formato (no garantiza validez, pero detecta pegas corruptas)
        masked = (token[:6] + "..." + str(len(token))) if isinstance(token, str) else "<no-string>"
        if isinstance(token, str) and ("\n" in token or "\r" in token or ' ' in token):
            logger.warning(f"⚠️ DISCORD_TOKEN contiene espacios o saltos de línea. Usando token normalizado: {masked}")
        else:
            logger.info(f"🔐 Usando DISCORD_TOKEN (mascarado): {masked}")
        
        # Configurar modo unificado para evitar conflictos de servidor
        os.environ["UNIFIED_MODE"] = "true"
        
        # Importar y configurar bot
        from src.bot.main import bot
        discord_bot = bot
        
        # Registrar instancia del bot para el panel
        from src.utils.bot_instance import set_bot_instance
        set_bot_instance(bot)
        
        async def run_bot():
            try:
                # login separado para capturar fallo de token
                await bot.login(token)
                logger.info("✅ Login correcto, conectando al gateway...")
                await bot.connect(reconnect=True)
            except Exception as e:
                logger.error(f"❌ Error en ejecución del bot (login/connect): {e}")
                raise
        
        logger.info("🤖 Iniciando bot de Discord...")
        bot_task = asyncio.create_task(run_bot())
        
    except Exception as e:
        logger.error(f"❌ Error iniciando bot de Discord: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación"""
    # Startup
    try:
        logger.info("🚀 Iniciando GeeBot...")
        
        # Inicializar base de datos
        from src.database.models import db
        await db.init_db()
        logger.info("✅ Base de datos inicializada")
        
        # Verificar configuración
        from src.utils.dynamic_config import config
        if config.is_configured():
            logger.info("✅ Configuración completa, iniciando bot...")
            await start_discord_bot()
        else:
            logger.warning("⚠️ Configuración incompleta, solo panel disponible")
        
        # Mostrar información
        port = int(os.environ.get("PORT", 10000))
        # Preferir URL de config dinámica, luego URL externa de Render, luego env BASE_URL y por último localhost
        try:
            from src.utils.dynamic_config import config as dyn_config
        except Exception:
            dyn_config = None
        base_url = (
            (dyn_config.get('BASE_URL') if dyn_config else None)
            or os.environ.get("RENDER_EXTERNAL_URL")
            or os.environ.get("BASE_URL")
            or f"http://localhost:{port}"
        )
        
        logger.info(f"🌐 Servicio disponible en: {base_url}")
        logger.info(f"🎛️ Panel de control: {base_url}/panel")
        logger.info("👤 Usuario: tweo")
        logger.info("🔑 Contraseña: mateo856794123")
        
    except Exception as e:
        logger.error(f"❌ Error en startup: {e}")
    
    yield
    
    # Shutdown
    global discord_bot, bot_task
    try:
        logger.info("🔄 Cerrando servicios...")
        
        if discord_bot:
            await discord_bot.close()
            logger.info("✅ Bot de Discord cerrado")
        
        if bot_task:
            bot_task.cancel()
            
    except Exception as e:
        logger.error(f"❌ Error en shutdown: {e}")

# Crear aplicación FastAPI principal con lifespan
app = FastAPI(
    title="GeeBot", 
    description="Bot completo unificado",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar templates
templates = Jinja2Templates(directory="assets/templates")

# Montar archivos estáticos
try:
    app.mount("/static", StaticFiles(directory="assets/static"), name="static")
    logger.info("✅ Archivos estáticos montados")
except Exception as e:
    logger.warning(f"⚠️ No se pudieron montar archivos estáticos: {e}")

# Rutas principales
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirige la raíz al panel"""
    return RedirectResponse(url="/panel")

@app.get("/health")
async def health_check():
    """Health check para Render"""
    return {"status": "ok", "service": "geebot"}

@app.get("/ping")
async def ping():
    """Ping endpoint para keep-alive"""
    return {"status": "ok", "service": "geebot", "timestamp": "2025-01-01T00:00:00Z"}

@app.get("/config")
async def config_endpoint():
    """Endpoint de configuración - redirige al panel"""
    return RedirectResponse(url="/panel/config")

# Rutas de comodidad para compatibilidad con URLs antiguas
@app.get("/logs")
async def logs_redirect():
    return RedirectResponse(url="/panel/logs")

@app.get("/status")
async def status_redirect():
    return RedirectResponse(url="/panel/status")

@app.get("/panel")
async def panel_slash_redirect():
    return RedirectResponse(url="/panel/")

# Rutas del servidor OAuth/Web
try:
    from src.web.routes import setup_routes
    setup_routes(app)
    logger.info("✅ Rutas OAuth configuradas")
except Exception as e:
    logger.error(f"⚠️ Error configurando rutas OAuth: {e}")

# Montar panel de control en /panel
try:
    from src.panel.main import app as panel_app
    app.mount("/panel", panel_app)
    logger.info("✅ Panel de control montado en /panel")
except Exception as e:
    logger.error(f"⚠️ Error montando panel: {e}")

# Ruta de estado completa
@app.get("/status", response_class=HTMLResponse)
async def status(request: Request):
    """Estado del servicio con interfaz web"""
    try:
        from src.utils.dynamic_config import config
        import psutil
        import platform
        
        # Obtener información del sistema
        process = psutil.Process()
        memory_info = process.memory_info()
        
        # Datos para el template
        data = {
            "status": "healthy",
            "instance_id": f"render-{os.environ.get('RENDER_SERVICE_ID', 'local')[:8]}",
            "uptime_human": "N/A",  # Se puede calcular después
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "python_version": platform.python_version(),
            
            # Bot info
            "bot": {
                "status": "online" if discord_bot and not discord_bot.is_closed() else "offline",
                "guilds_count": len(discord_bot.guilds) if discord_bot and not discord_bot.is_closed() else 0,
                "users_count": sum(guild.member_count for guild in discord_bot.guilds) if discord_bot and not discord_bot.is_closed() else 0,
                "latency": f"{discord_bot.latency * 1000:.0f}ms" if discord_bot and not discord_bot.is_closed() else "N/A"
            },
            
            # Server info
            "server": {
                "status": "online",
                "requests_count": "N/A",
                "memory_usage": {
                    "rss_mb": memory_info.rss / 1024 / 1024
                }
            },
            
            # Database info
            "database": {
                "status": "connected",
                "verified_users": 0,  # Se puede obtener de la DB
                "pending_verifications": 0
            },
            
            # Services info
            "services": {
                "genius_api": "online",
                "oauth_flow": "online",
                "discord_api": "online"
            }
        }
        
        return templates.TemplateResponse("status_simple.html", {
            "request": request,
            "data": data
        })
        
    except Exception as e:
        logger.error(f"Error en status: {e}")
        return templates.TemplateResponse("error_simple.html", {
            "request": request,
            "error_message": str(e)
        })

# Ruta de estado JSON (para APIs)
@app.get("/api/status")
async def api_status():
    """Estado del servicio en formato JSON"""
    try:
        from src.utils.dynamic_config import config
        
        status_info = {
            "service": "GeeBot",
            "status": "running",
            "configured": config.is_configured(),
            "discord_bot": "running" if discord_bot and not discord_bot.is_closed() else "stopped",
            "panel": "/panel",
            "oauth": "/auth",
            "health": "/health"
        }
        
        return status_info
    except Exception as e:
        logger.error(f"Error en api_status: {e}")
        return {"service": "GeeBot", "status": "error", "error": str(e)}

async def main():
    """Función principal"""
    try:
        # Puerto (Render usa PORT, local puede usar 10000)
        port = int(os.environ.get("PORT", 10000))
        
        # Configurar uvicorn
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True
        )
        
        server = uvicorn.Server(config)
        logger.info(f"🚀 Iniciando servidor en puerto {port}")
        await server.serve()
        
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
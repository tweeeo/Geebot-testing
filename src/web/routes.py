"""
Rutas del servidor web para OAuth y verificaciones
"""

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import aiohttp
import logging
from urllib.parse import urlencode
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Configurar templates
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "assets" / "templates"))

def setup_routes(app: FastAPI):
    """Configurar rutas del servidor web"""
    # Asegurar ruta de estáticos para que url_for('static') funcione en templates
    try:
        from fastapi.staticfiles import StaticFiles
        static_dir = str(BASE_DIR / "assets" / "static")
        has_static = any(getattr(r, "name", None) == "static" for r in getattr(app.router, "routes", []))
        if not has_static:
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
            logger.info(f"✅ Archivos estáticos montados en /static -> {static_dir}")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo montar /static en rutas web: {e}")
    
    @app.get("/auth")
    async def auth_page(request: Request, state: str = Query(None)):
        """Inicia el flujo OAuth de Genius redirigiendo a authorize"""
        try:
            from src.utils.dynamic_config import config
            
            if not state:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error_message": "Estado de verificación inválido o faltante"
                })
            
            client_id = config.get('GENIUS_CLIENT_ID')
            client_secret = config.get('GENIUS_CLIENT_SECRET')
            base_url = config.get('BASE_URL', 'https://geebot-testing.onrender.com')
            
            if not client_id or not client_secret:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error_message": "Genius API no configurado. Falta CLIENT_ID o CLIENT_SECRET."
                })
            
            params = {
                'client_id': client_id,
                'redirect_uri': f'{base_url}/callback',
                'scope': 'me',
                'state': state,
                'response_type': 'code'
            }
            auth_url = f"https://api.genius.com/oauth/authorize?{urlencode(params)}"
            return RedirectResponse(url=auth_url)
            
        except Exception as e:
            logger.error(f"Error en auth page: {e}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": str(e)
            })
    
    @app.get("/callback")
    async def oauth_callback(request: Request, code: str = Query(None), error: str = Query(None)):
        """Callback de OAuth de Genius"""
        try:
            if error:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error_message": f"Error de autorización de Genius: {error}"
                })
            
            if not code:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error_message": "No se recibió código de autorización"
                })
            
            from src.utils.dynamic_config import config
            
            client_id = config.get('GENIUS_CLIENT_ID')
            client_secret = config.get('GENIUS_CLIENT_SECRET')
            base_url = config.get('BASE_URL', 'https://geebot-testing.onrender.com')
            
            if not client_id or not client_secret:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error_message": "Credenciales de Genius API no configuradas"
                })
            
            # Intercambiar código por token
            token_data = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': f'{base_url}/callback',
                'grant_type': 'authorization_code'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post('https://api.genius.com/oauth/token', data=token_data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Error obteniendo token: {resp.status} - {error_text}")
                        return templates.TemplateResponse("error.html", {
                            "request": request,
                            "error_message": f"No se pudo obtener token de acceso (HTTP {resp.status})"
                        })
                    
                    token_response = await resp.json()
                    access_token = token_response.get('access_token')
                    
                    if not access_token:
                        return templates.TemplateResponse("error.html", {
                            "request": request,
                            "error": "Token inválido",
                            "message": "No se recibió token de acceso válido"
                        })
            
            # Obtener información del usuario
            headers = {'Authorization': f'Bearer {access_token}'}
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.genius.com/account', headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Error obteniendo usuario: {resp.status} - {error_text}")
                        return templates.TemplateResponse("error.html", {
                            "request": request,
                            "error_message": f"No se pudo obtener información del usuario (HTTP {resp.status})"
                        })
                    
                    user_data = await resp.json()
                    user_info = user_data.get('response', {}).get('user', {})
            
            # Completar verificación end-to-end: persistir, asignar roles y actualizar nickname
            try:
                from src.database.models import db
                from src.utils.bot_instance import get_bot_instance
                from src.utils.dynamic_config import config
                import asyncio
                
                # 1) Resolver discord_id desde el state
                state = request.query_params.get('state')
                if not state:
                    return templates.TemplateResponse("error.html", {
                        "request": request,
                        "error_message": "Falta parámetro 'state' en el callback"
                    })
                discord_id = await db.get_pending_verification(state)
                if not discord_id:
                    return templates.TemplateResponse("error.html", {
                        "request": request,
                        "error_message": "Estado de verificación inválido o expirado"
                    })
                
                # 2) Mapear roles de Genius a roles internos visibles (centralizado)
                try:
                    from src.utils.role_mapping import map_genius_roles
                    roles_out = map_genius_roles(user_info)
                    print(f"🔍 DEBUG - Final roles_out: {roles_out}")
                except Exception as e:
                    print(f"❌ DEBUG - Exception in role mapping: {e}")
                    roles_out = ["Contributor"]
                
                # 3) Guardar verificación en DB
                await db.save_verification(int(discord_id), {
                    'id': user_info.get('id'),
                    'login': user_info.get('login'),
                    'name': user_info.get('name') or user_info.get('login'),
                    'roles': roles_out
                }, access_token)
                
                # 4) Intentar asignar roles y actualizar nickname en Discord
                try:
                    bot = get_bot_instance()
                    if bot and not bot.is_closed():
                        # Determinar guild objetivo
                        target_guild = None
                        try:
                            verification_channel_id = config.get('VERIFICATION_CHANNEL_ID', '')
                            ch_id = int(verification_channel_id) if verification_channel_id.isdigit() else 0
                        except Exception:
                            ch_id = 0
                        if ch_id:
                            channel = bot.get_channel(ch_id)
                            if channel is not None:
                                target_guild = channel.guild
                        if target_guild is None:
                            # Fallback: buscar guild que tenga alguno de los roles configurados
                            genius_role_ids = []
                            for role_key in ['ROLE_CONTRIBUTOR', 'ROLE_EDITOR', 'ROLE_MODERATOR', 'ROLE_STAFF', 'ROLE_VERIFIED_ARTIST', 'ROLE_TRANSCRIBER', 'ROLE_MEDIATOR']:
                                role_id = config.get(role_key, '')
                                if role_id and role_id.isdigit():
                                    genius_role_ids.append(int(role_id))
                            
                            for g in bot.guilds:
                                if any(g.get_role(rid) for rid in genius_role_ids):
                                    target_guild = g
                                    break
                            if target_guild is None and bot.guilds:
                                target_guild = bot.guilds[0]
                        
                        if target_guild is not None:
                            member = target_guild.get_member(int(discord_id))
                            if member is None:
                                try:
                                    member = await target_guild.fetch_member(int(discord_id))
                                except Exception:
                                    member = None
                            if member is not None:
                                # Preparar roles a asignar
                                role_ids = []
                                genius_role_mapping = {
                                    "Contributor": config.get('ROLE_CONTRIBUTOR', ''),
                                    "Editor": config.get('ROLE_EDITOR', ''),
                                    "Moderator": config.get('ROLE_MODERATOR', ''),
                                    "Staff": config.get('ROLE_STAFF', ''),
                                    "Verified Artist": config.get('ROLE_VERIFIED_ARTIST', ''),
                                    "Transcriber": config.get('ROLE_TRANSCRIBER', ''),
                                    "Mediator": config.get('ROLE_MEDIATOR', '')
                                }
                                
                                print(f"🔍 DEBUG - Role mapping config: {genius_role_mapping}")
                                print(f"🔍 DEBUG - Roles to assign: {roles_out}")
                                
                                for name in roles_out:
                                    role_id = genius_role_mapping.get(name, '')
                                    print(f"🔍 DEBUG - Checking role '{name}' -> ID: '{role_id}'")
                                    if role_id and role_id.isdigit():
                                        role_ids.append(int(role_id))
                                        print(f"✅ DEBUG - Added role ID: {role_id}")
                                
                                verified_role_id = config.get('VERIFIED_ROLE_ID', '')
                                if verified_role_id and verified_role_id.isdigit():
                                    role_ids.append(int(verified_role_id))
                                    print(f"✅ DEBUG - Added verified role ID: {verified_role_id}")
                                
                                print(f"🔍 DEBUG - Final role IDs to assign: {role_ids}")
                                discord_roles = [target_guild.get_role(rid) for rid in role_ids]
                                discord_roles = [r for r in discord_roles if r is not None]
                                if discord_roles:
                                    try:
                                        await member.add_roles(*discord_roles, reason="Genius verification")
                                    except Exception:
                                        pass
                                # Actualizar nickname
                                try:
                                    desired = (user_info.get('name') or user_info.get('login') or '')
                                    desired = desired[:32] if desired else None
                                    if desired:
                                        await member.edit(nick=desired, reason="Genius verification")
                                except Exception:
                                    pass
                except Exception as e:
                    logger.error(f"Error asignando roles/nickname en Discord: {e}")
                
                # 5) Mostrar éxito (redirigir a página estática de éxito)
                return RedirectResponse(url="/static/success/index.html")
            except Exception as e:
                logger.error(f"Error completando verificación end-to-end: {e}")
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error_message": f"Error completando verificación: {str(e)}"
                })
            
        except Exception as e:
            logger.error(f"Error en callback: {e}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Error interno",
                "message": str(e)
            })
    
    @app.get("/verify/{user_id}")
    async def verify_user(user_id: str):
        """API para verificar usuario"""
        try:
            # Aquí iría la lógica de verificación del bot
            return {"status": "success", "user_id": user_id}
        except Exception as e:
            logger.error(f"Error verificando usuario {user_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/status/simple", response_class=HTMLResponse)
    async def simple_status(request: Request):
        """Estado simple del bot"""
        try:
            from src.utils.dynamic_config import config
            
            return templates.TemplateResponse("simple_status.html", {
                "request": request,
                "configured": config.is_configured(),
                "discord_token": bool(config.get('DISCORD_TOKEN')),
                "genius_configured": bool(config.get('GENIUS_CLIENT_ID') and config.get('GENIUS_CLIENT_SECRET'))
            })
            
        except Exception as e:
            logger.error(f"Error en status: {e}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Error de estado",
                "message": str(e)
            })
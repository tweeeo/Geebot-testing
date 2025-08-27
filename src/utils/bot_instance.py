"""
Utilidad para verificar el estado del bot desde el panel de control
"""

import os
import asyncio
import requests
import time
from typing import Optional

# Variable global para almacenar la instancia del bot
_bot_instance: Optional[object] = None
_bot_ready: bool = False
_last_heartbeat: float = 0

def set_bot_instance(bot):
    """Establecer la instancia del bot"""
    global _bot_instance, _bot_ready, _last_heartbeat
    _bot_instance = bot
    _bot_ready = True
    _last_heartbeat = time.time()

def get_bot_instance():
    """Obtener la instancia del bot"""
    return _bot_instance

def update_heartbeat():
    """Actualizar el heartbeat del bot"""
    global _last_heartbeat
    _last_heartbeat = time.time()

def is_bot_ready() -> bool:
    """Verificar si el bot está listo"""
    global _bot_ready, _last_heartbeat
    
    # Si tenemos instancia local del bot
    if _bot_instance is not None:
        try:
            if hasattr(_bot_instance, 'is_ready'):
                ready = _bot_instance.is_ready()
                if ready:
                    update_heartbeat()
                return ready
            return _bot_ready
        except:
            return False
    
    # Si no hay instancia local, verificar por heartbeat o API externa
    return check_external_bot_status()

def check_external_bot_status() -> bool:
    """Verificar estado del bot externamente (para servicios separados)"""
    global _last_heartbeat
    
    # Verificar heartbeat reciente (últimos 15 minutos para evitar falsos negativos)
    if _last_heartbeat > 0 and (time.time() - _last_heartbeat) < 900:
        return True
    
    # Intentar verificar a través de Discord API si tenemos token (dinámico o env)
    discord_token = os.environ.get('DISCORD_TOKEN')
    if not discord_token:
        try:
            # Obtener token desde configuración dinámica si es posible
            from src.utils.dynamic_config import config as dynamic_config
            discord_token = dynamic_config.get('DISCORD_TOKEN')
        except Exception:
            discord_token = None
    
    if discord_token:
        try:
            headers = {
                'Authorization': f'Bot {discord_token}',
                'Content-Type': 'application/json'
            }
            response = requests.get('https://discord.com/api/v10/users/@me', 
                                  headers=headers, timeout=5)
            if response.status_code == 200:
                update_heartbeat()
                return True
        except Exception:
            pass
    
    return False

def get_bot_stats() -> dict:
    """Obtener estadísticas del bot"""
    # Si tenemos instancia local
    if _bot_instance:
        try:
            return {
                "status": "online" if is_bot_ready() else "offline",
                "guilds": len(_bot_instance.guilds) if hasattr(_bot_instance, 'guilds') else 0,
                "users": sum(guild.member_count for guild in _bot_instance.guilds) if hasattr(_bot_instance, 'guilds') else 0,
                "latency": round(_bot_instance.latency * 1000, 2) if hasattr(_bot_instance, 'latency') else 0
            }
        except Exception:
            pass
    
    # Si no hay instancia local, obtener stats básicos
    status = "online" if check_external_bot_status() else "offline"
    
    # Intentar obtener información básica del bot via Discord API (token dinámico o env)
    discord_token = os.environ.get('DISCORD_TOKEN')
    if not discord_token:
        try:
            from src.utils.dynamic_config import config as dynamic_config
            discord_token = dynamic_config.get('DISCORD_TOKEN')
        except Exception:
            discord_token = None
    guilds_count = 0
    
    if discord_token and status == "online":
        try:
            headers = {
                'Authorization': f'Bot {discord_token}',
                'Content-Type': 'application/json'
            }
            # Obtener guilds
            response = requests.get('https://discord.com/api/v10/users/@me/guilds', 
                                  headers=headers, timeout=5)
            if response.status_code == 200:
                guilds_count = len(response.json())
        except Exception:
            pass
    
    return {
        "status": status,
        "guilds": guilds_count,
        "users": 0,  # No podemos obtener esto fácilmente sin la instancia
        "latency": 0  # No podemos obtener esto sin la instancia
    }
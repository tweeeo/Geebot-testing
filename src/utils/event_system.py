"""
Sistema de eventos para sincronización en tiempo real
Permite notificar al bot cuando la configuración cambia desde el panel
"""

import asyncio
import threading
import time
from typing import Dict, List, Callable, Any
import logging

logger = logging.getLogger(__name__)

class EventSystem:
    """Sistema de eventos para comunicación entre componentes"""
    
    def __init__(self):
        self.listeners: Dict[str, List[Callable]] = {}
        self.async_listeners: Dict[str, List[Callable]] = {}
        self.lock = threading.Lock()
        self._loop = None
    
    def set_event_loop(self, loop):
        """Establecer el loop de eventos para callbacks async"""
        self._loop = loop
    
    def subscribe(self, event_name: str, callback: Callable):
        """Suscribirse a un evento (callback síncrono)"""
        with self.lock:
            if event_name not in self.listeners:
                self.listeners[event_name] = []
            self.listeners[event_name].append(callback)
            logger.debug(f"Suscrito a evento '{event_name}' (sync)")
    
    def subscribe_async(self, event_name: str, callback: Callable):
        """Suscribirse a un evento (callback asíncrono)"""
        with self.lock:
            if event_name not in self.async_listeners:
                self.async_listeners[event_name] = []
            self.async_listeners[event_name].append(callback)
            logger.debug(f"Suscrito a evento '{event_name}' (async)")
    
    def emit(self, event_name: str, data: Any = None):
        """Emitir un evento"""
        logger.info(f"Emitiendo evento: {event_name}")
        
        # Ejecutar callbacks síncronos
        with self.lock:
            sync_callbacks = self.listeners.get(event_name, [])
        
        for callback in sync_callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error en callback síncrono para {event_name}: {e}")
        
        # Ejecutar callbacks asíncronos
        with self.lock:
            async_callbacks = self.async_listeners.get(event_name, [])
        
        if async_callbacks and self._loop:
            for callback in async_callbacks:
                try:
                    # Crear tarea en el loop de eventos
                    asyncio.run_coroutine_threadsafe(callback(data), self._loop)
                except Exception as e:
                    logger.error(f"Error en callback asíncrono para {event_name}: {e}")
    
    def unsubscribe(self, event_name: str, callback: Callable):
        """Desuscribirse de un evento"""
        with self.lock:
            if event_name in self.listeners and callback in self.listeners[event_name]:
                self.listeners[event_name].remove(callback)
            if event_name in self.async_listeners and callback in self.async_listeners[event_name]:
                self.async_listeners[event_name].remove(callback)

# Instancia global del sistema de eventos
event_system = EventSystem()

# Eventos predefinidos
class Events:
    CONFIG_UPDATED = "config_updated"
    BOT_RESTART_REQUIRED = "bot_restart_required"
    ROLE_CONFIG_CHANGED = "role_config_changed"
    DISCORD_TOKEN_CHANGED = "discord_token_changed"
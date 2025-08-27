"""
Sistema de señales para comunicación entre procesos
Permite notificar al bot cuando la configuración cambia desde el panel
"""

import os
import time
import sqlite3
import threading
import asyncio
from typing import Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)

class SignalSystem:
    """Sistema de señales para comunicación entre procesos usando SQLite"""
    
    def __init__(self, db_path: str = None):
        # Usar almacenamiento persistente en Render si está disponible
        if db_path is None:
            data_dir = os.environ.get("RENDER_DATA_DIR", "/opt/render/project/src/data")
            if os.path.exists(data_dir):
                self.db_path = os.path.join(data_dir, "signals.db")
            else:
                self.db_path = "signals.db"
        else:
            self.db_path = db_path
        
        # Crear directorio si no existe
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        self.listeners = {}
        self.lock = threading.Lock()
        self.running = False
        self.poll_thread = None
        self.last_check = time.time()
        self._init_database()
    
    def _init_database(self):
        """Inicializar base de datos de señales"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_type TEXT NOT NULL,
                    data TEXT,
                    timestamp REAL NOT NULL,
                    processed BOOLEAN DEFAULT 0
                )
            """)
            conn.commit()
    
    def emit_signal(self, signal_type: str, data: Any = None):
        """Emitir una señal"""
        try:
            import json
            data_json = json.dumps(data) if data else None
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO signals (signal_type, data, timestamp)
                    VALUES (?, ?, ?)
                """, (signal_type, data_json, time.time()))
                conn.commit()
            
            logger.info(f"📡 Señal emitida: {signal_type}")
            
        except Exception as e:
            logger.error(f"❌ Error emitiendo señal {signal_type}: {e}")
    
    def subscribe(self, signal_type: str, callback: Callable):
        """Suscribirse a un tipo de señal"""
        with self.lock:
            if signal_type not in self.listeners:
                self.listeners[signal_type] = []
            self.listeners[signal_type].append(callback)
            logger.debug(f"Suscrito a señal: {signal_type}")
    
    def start_polling(self, interval: float = 1.0):
        """Iniciar polling de señales"""
        if self.running:
            return
        
        self.running = True
        self.poll_thread = threading.Thread(
            target=self._poll_signals,
            args=(interval,),
            daemon=True
        )
        self.poll_thread.start()
        logger.info(f"🔄 Sistema de señales iniciado (polling cada {interval}s)")
    
    def stop_polling(self):
        """Detener polling de señales"""
        self.running = False
        if self.poll_thread:
            self.poll_thread.join(timeout=2)
        logger.info("⏹️ Sistema de señales detenido")
    
    def _poll_signals(self, interval: float):
        """Polling de señales en hilo separado"""
        while self.running:
            try:
                self._process_pending_signals()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"❌ Error en polling de señales: {e}")
                time.sleep(interval)
    
    def _process_pending_signals(self):
        """Procesar señales pendientes"""
        try:
            import json
            
            with sqlite3.connect(self.db_path) as conn:
                # Obtener señales no procesadas desde la última verificación
                cursor = conn.execute("""
                    SELECT id, signal_type, data, timestamp
                    FROM signals
                    WHERE processed = 0 AND timestamp > ?
                    ORDER BY timestamp ASC
                """, (self.last_check,))
                
                signals = cursor.fetchall()
                
                for signal_id, signal_type, data_json, timestamp in signals:
                    try:
                        # Deserializar datos
                        data = json.loads(data_json) if data_json else None
                        
                        # Ejecutar callbacks
                        with self.lock:
                            callbacks = self.listeners.get(signal_type, [])
                        
                        for callback in callbacks:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    # Para callbacks async, crear tarea
                                    loop = asyncio.get_event_loop()
                                    asyncio.run_coroutine_threadsafe(callback(data), loop)
                                else:
                                    callback(data)
                            except Exception as e:
                                logger.error(f"❌ Error en callback para {signal_type}: {e}")
                        
                        # Marcar como procesada
                        conn.execute("""
                            UPDATE signals SET processed = 1 WHERE id = ?
                        """, (signal_id,))
                        
                        logger.debug(f"📨 Señal procesada: {signal_type}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error procesando señal {signal_id}: {e}")
                
                conn.commit()
                self.last_check = time.time()
                
        except Exception as e:
            logger.error(f"❌ Error procesando señales pendientes: {e}")
    
    def cleanup_old_signals(self, max_age_hours: int = 24):
        """Limpiar señales antiguas"""
        try:
            cutoff_time = time.time() - (max_age_hours * 3600)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    DELETE FROM signals WHERE timestamp < ? AND processed = 1
                """, (cutoff_time,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                if deleted_count > 0:
                    logger.info(f"🧹 Limpiadas {deleted_count} señales antiguas")
                    
        except Exception as e:
            logger.error(f"❌ Error limpiando señales antiguas: {e}")

# Instancia global
signal_system = SignalSystem()

# Tipos de señales predefinidas
class Signals:
    CONFIG_UPDATED = "config_updated"
    ROLE_CONFIG_CHANGED = "role_config_changed"
    DISCORD_TOKEN_CHANGED = "discord_token_changed"
    BOT_RESTART_REQUIRED = "bot_restart_required"
"""
Sistema de configuración dinámico para GeeBot
Permite configurar el bot desde el panel web sin reiniciar
"""

import os
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
import threading

class DynamicConfig:
    """Gestor de configuración dinámico"""
    
    def __init__(self, db_path: Optional[str] = None):
        # Usar almacenamiento persistente en Render si está disponible
        if db_path is None:
            data_dir = os.environ.get("RENDER_DATA_DIR", "/opt/render/project/src/data")
            if os.path.exists(data_dir):
                self.db_path = os.path.join(data_dir, "config.db")
            else:
                self.db_path = "config.db"
        else:
            self.db_path = db_path
        
        # Crear directorio si no existe
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        self.config_cache = {}
        self.lock = threading.Lock()
        self._init_database()
        self._load_config()
    
    def _init_database(self):
        """Inicializar base de datos de configuración"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    description TEXT,
                    required BOOLEAN DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _load_config(self):
        """Cargar configuración desde la base de datos"""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("SELECT key, value FROM config")
                    self.config_cache = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Establecer valores por defecto para comandos habilitados
                self._set_default_command_configs()
                
            except Exception as e:
                print(f"⚠️ Error cargando configuración: {e}")
                self.config_cache = {}
    
    def _set_default_command_configs(self):
        """Establecer valores por defecto para configuraciones de comandos"""
        default_command_configs = {
            'ENABLE_COMMAND_VERIFIED_LIST': 'true',
            'ENABLE_COMMAND_TEST_ROLES': 'true',
            'ENABLE_COMMAND_LIST_ROLES': 'true',
            'ENABLE_COMMAND_SHOW_CONFIG': 'true',
            'ENABLE_COMMAND_CLEANUP_VERIFICATIONS': 'true',
            'ENABLE_COMMAND_SYNC': 'true',
            'ENABLE_COMMAND_BOT_STATS': 'true'
        }
        
        for key, default_value in default_command_configs.items():
            if key not in self.config_cache:
                self.config_cache[key] = default_value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtener valor de configuración"""
        # Primero intentar desde cache
        if key in self.config_cache and self.config_cache[key]:
            return self.config_cache[key]
        
        # Luego desde variables de entorno (para compatibilidad)
        env_value = os.environ.get(key)
        if env_value:
            return env_value
        
        return default
    
    def set(self, key: str, value: str, description: str = "", required: bool = False):
        """Establecer valor de configuración"""
        with self.lock:
            try:
                # Obtener valor anterior para comparar
                old_value = self.config_cache.get(key)
                
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO config (key, value, description, required)
                        VALUES (?, ?, ?, ?)
                    """, (key, value, description, required))
                    conn.commit()
                
                # Actualizar cache
                self.config_cache[key] = value
                
                # También actualizar variable de entorno para compatibilidad
                os.environ[key] = value
                
                # Emitir evento si el valor cambió
                if old_value != value:
                    self._emit_config_event(key, value, old_value)
                
                return True
            except Exception as e:
                print(f"❌ Error guardando configuración {key}: {e}")
                return False
    
    def get_all(self) -> Dict[str, Any]:
        """Obtener toda la configuración"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT key, value, description, required 
                FROM config 
                ORDER BY key
            """)
            return {
                row[0]: {
                    'value': row[1] or '',
                    'description': row[2] or '',
                    'required': bool(row[3])
                }
                for row in cursor.fetchall()
            }
    
    def update_multiple(self, configs: Dict[str, str]) -> bool:
        """Actualizar múltiples configuraciones"""
        with self.lock:
            try:
                # Obtener valores anteriores para comparar
                old_values = {}
                for key in configs.keys():
                    old_values[key] = self.config_cache.get(key)
                
                with sqlite3.connect(self.db_path) as conn:
                    for key, value in configs.items():
                        conn.execute("""
                            INSERT OR REPLACE INTO config (key, value)
                            VALUES (?, ?)
                        """, (key, value))
                    conn.commit()
                
                # Actualizar cache y variables de entorno
                changed_configs = {}
                for key, value in configs.items():
                    self.config_cache[key] = value
                    os.environ[key] = value
                    
                    # Registrar cambios
                    if old_values[key] != value:
                        changed_configs[key] = {'old': old_values[key], 'new': value}
                
                # Emitir eventos para configuraciones que cambiaron
                if changed_configs:
                    self._emit_multiple_config_events(changed_configs)
                
                return True
            except Exception as e:
                print(f"❌ Error actualizando configuraciones: {e}")
                return False
    
    def is_configured(self) -> bool:
        """Verificar si las configuraciones básicas están completas"""
        required_keys = [
            'DISCORD_TOKEN',
            'GENIUS_CLIENT_ID', 
            'GENIUS_CLIENT_SECRET',
            'BASE_URL'
        ]
        
        for key in required_keys:
            if not self.get(key):
                return False
        return True
    
    def get_missing_configs(self) -> list:
        """Obtener lista de configuraciones faltantes"""
        required_keys = [
            'DISCORD_TOKEN',
            'GENIUS_CLIENT_ID',
            'GENIUS_CLIENT_SECRET', 
            'BASE_URL',
            'VERIFICATION_CHANNEL_ID',
            'VERIFIED_ROLE_ID'
        ]
        
        missing = []
        for key in required_keys:
            if not self.get(key):
                missing.append(key)
        return missing
    
    def init_default_configs(self):
        """Inicializar configuraciones por defecto"""
        default_configs = {
            'DISCORD_TOKEN': {'desc': 'Token del bot de Discord', 'required': True},
            'GENIUS_CLIENT_ID': {'desc': 'ID de cliente de la aplicación Genius', 'required': True},
            'GENIUS_CLIENT_SECRET': {'desc': 'Secreto de cliente de la aplicación Genius', 'required': True},
            'BASE_URL': {'desc': 'URL base del servidor', 'required': True},
            'VERIFICATION_CHANNEL_ID': {'desc': 'ID del canal de verificación', 'required': True},
            'VERIFIED_ROLE_ID': {'desc': 'ID del rol de usuario verificado', 'required': True},
            'ROLE_VERIFIED_ARTIST': {'desc': 'ID del rol de artista verificado', 'required': False},
            'ROLE_STAFF': {'desc': 'ID del rol de staff', 'required': False},
            'ROLE_MODERATOR': {'desc': 'ID del rol de moderador', 'required': False},
            'ROLE_EDITOR': {'desc': 'ID del rol de editor', 'required': False},
            'ROLE_TRANSCRIBER': {'desc': 'ID del rol de transcriptor', 'required': False},
            'ROLE_MEDIATOR': {'desc': 'ID del rol de mediador', 'required': False},
            'ROLE_CONTRIBUTOR': {'desc': 'ID del rol de contribuidor', 'required': False},
            'KEEP_ALIVE_INTERVAL': {'desc': 'Intervalo de keep-alive en segundos', 'required': False},

            # Sección: Comandos
            'CMD_PREFIX': {'desc': 'Prefijo de comandos (ej: !!)', 'required': False},
            'ENABLE_COMMAND_PING': {'desc': 'Habilitar comando ping', 'required': False},
            'ENABLE_COMMAND_TEST_WELCOME': {'desc': 'Habilitar comando test_welcome', 'required': False},
            'ENABLE_COMMAND_HELP': {'desc': 'Habilitar comando help', 'required': False},
            'ENABLE_COMMAND_TEST': {'desc': 'Habilitar comando test', 'required': False},
            'ENABLE_COMMAND_SETUP_VERIFICATION': {'desc': 'Habilitar comando setup_verification', 'required': False},
            'ENABLE_COMMAND_VERIFY_STATUS': {'desc': 'Habilitar comando verify_status', 'required': False},
            'ENABLE_COMMAND_UNVERIFY': {'desc': 'Habilitar comando unverify', 'required': False},
            'ENABLE_COMMAND_VERIFIED_LIST': {'desc': 'Habilitar comando verified_list', 'required': False},
            'ENABLE_COMMAND_TEST_ROLES': {'desc': 'Habilitar comando test_roles', 'required': False},
            'ENABLE_COMMAND_LIST_ROLES': {'desc': 'Habilitar comando list_roles', 'required': False},
            'ENABLE_COMMAND_SHOW_CONFIG': {'desc': 'Habilitar comando show_config', 'required': False},
            'ENABLE_COMMAND_CLEANUP_VERIFICATIONS': {'desc': 'Habilitar comando cleanup_verifications', 'required': False},
            'ENABLE_COMMAND_SYNC': {'desc': 'Habilitar comando sync', 'required': False},
            'ENABLE_COMMAND_BOT_STATS': {'desc': 'Habilitar comando bot_stats', 'required': False},

            # Sección: Mensajes
            'WELCOME_REACTION_ENABLED': {'desc': 'Reaccionar a mensajes de bienvenida', 'required': False},
            'WELCOME_MESSAGE_TEXT': {'desc': 'Texto de mensaje de bienvenida', 'required': False},
            'SUCCESS_VERIFICATION_MESSAGE': {'desc': 'Mensaje de verificación exitosa', 'required': False},
            'ERROR_VERIFICATION_MESSAGE': {'desc': 'Mensaje de error en verificación', 'required': False},
            'OAUTH_ERROR_MESSAGE': {'desc': 'Mensaje de error OAuth', 'required': False},
            'ALREADY_VERIFIED_MESSAGE': {'desc': 'Mensaje para usuarios ya verificados', 'required': False},
            'VERIFICATION_TIMEOUT_MESSAGE': {'desc': 'Mensaje de timeout en verificación', 'required': False},
            'ROLE_ASSIGNMENT_SUCCESS_MESSAGE': {'desc': 'Mensaje de asignación de rol exitosa', 'required': False},
            'ROLE_ASSIGNMENT_ERROR_MESSAGE': {'desc': 'Mensaje de error en asignación de rol', 'required': False},

            # Sección: Verificación
            'VERIFICATION_EMBED_TITLE': {'desc': 'Título del embed de verificación', 'required': False},
            'VERIFICATION_EMBED_DESCRIPTION': {'desc': 'Descripción del embed de verificación', 'required': False},
            'VERIFICATION_BUTTON_LABEL': {'desc': 'Texto del botón de verificación', 'required': False},
        }
        
        with sqlite3.connect(self.db_path) as conn:
            for key, info in default_configs.items():
                # Solo insertar si no existe
                cursor = conn.execute("SELECT key FROM config WHERE key = ?", (key,))
                if not cursor.fetchone():
                    conn.execute("""
                        INSERT INTO config (key, value, description, required)
                        VALUES (?, ?, ?, ?)
                    """, (key, '', info['desc'], info['required']))
            conn.commit()
    
    def _emit_config_event(self, key: str, new_value: str, old_value: str):
        """Emitir evento cuando cambia una configuración"""
        try:
            # Usar sistema de eventos local
            from .event_system import event_system, Events
            
            event_system.emit(Events.CONFIG_UPDATED, {
                'key': key,
                'old_value': old_value,
                'new_value': new_value
            })
            
            # Usar sistema de señales para comunicación entre procesos
            from .signal_system import signal_system, Signals
            
            signal_system.emit_signal(Signals.CONFIG_UPDATED, {
                'key': key,
                'old_value': old_value,
                'new_value': new_value
            })
            
            # Señales específicas para configuraciones críticas
            if key == 'DISCORD_TOKEN':
                signal_system.emit_signal(Signals.DISCORD_TOKEN_CHANGED, {
                    'old_token': old_value,
                    'new_token': new_value
                })
            elif key.startswith('ROLE_'):
                signal_system.emit_signal(Signals.ROLE_CONFIG_CHANGED, {
                    'role_key': key,
                    'old_value': old_value,
                    'new_value': new_value
                })
            
            print(f"🔄 Evento y señal emitidos para configuración: {key}")
            
        except Exception as e:
            print(f"⚠️ Error emitiendo evento para {key}: {e}")
    
    def _emit_multiple_config_events(self, changed_configs: Dict[str, Dict]):
        """Emitir eventos para múltiples configuraciones que cambiaron"""
        try:
            # Usar sistema de eventos local
            from .event_system import event_system, Events
            
            event_system.emit(Events.CONFIG_UPDATED, {
                'multiple': True,
                'changes': changed_configs
            })
            
            # Usar sistema de señales para comunicación entre procesos
            from .signal_system import signal_system, Signals
            
            signal_system.emit_signal(Signals.CONFIG_UPDATED, {
                'multiple': True,
                'changes': changed_configs
            })
            
            # Verificar si hay cambios críticos que requieren reinicio
            critical_keys = ['DISCORD_TOKEN', 'GENIUS_CLIENT_ID', 'GENIUS_CLIENT_SECRET']
            if any(key in changed_configs for key in critical_keys):
                signal_system.emit_signal(Signals.BOT_RESTART_REQUIRED, {
                    'reason': 'critical_config_changed',
                    'changed_keys': [k for k in changed_configs.keys() if k in critical_keys]
                })
            
            # Señales específicas para roles
            role_changes = {k: v for k, v in changed_configs.items() if k.startswith('ROLE_')}
            if role_changes:
                signal_system.emit_signal(Signals.ROLE_CONFIG_CHANGED, {
                    'multiple': True,
                    'role_changes': role_changes
                })
            
            print(f"🔄 Eventos y señales emitidos para {len(changed_configs)} configuraciones")
            
        except Exception as e:
            print(f"⚠️ Error emitiendo eventos múltiples: {e}")

# Instancia global
config = DynamicConfig()
# Inicializador del paquete de comandos
import os
import importlib
import logging

logger = logging.getLogger(__name__)

def load_all_commands(bot):
    """Carga todos los comandos disponibles en este directorio"""
    command_files = []
    
    # Obtener todos los archivos .py en este directorio
    for filename in os.listdir(os.path.dirname(__file__)):
        if filename.endswith('.py') and filename != '__init__.py':
            command_name = filename[:-3]  # Quitar la extensión .py
            command_files.append(command_name)
    
    # Cargar cada módulo de comando
    for command_name in command_files:
        try:
            # Importar el módulo dinámicamente
            module = importlib.import_module(f'.{command_name}', package=__name__)
            
            # Verificar si el módulo tiene una función load_commands
            if hasattr(module, 'load_commands'):
                try:
                    module.load_commands(bot)
                    logger.info(f"✅ Comando {command_name} cargado correctamente")
                except Exception as cmd_error:
                    logger.error(f"❌ Error en la función load_commands de {command_name}: {cmd_error}")
            else:
                logger.warning(f"⚠️ El módulo {command_name} no tiene función load_commands")
        except Exception as e:
            logger.error(f"❌ Error importando módulo {command_name}: {e}")
    
    return command_files
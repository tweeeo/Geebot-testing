"""
Sistema de Keep-Alive para mantener el bot activo
Evita que servicios de hosting apaguen el bot por inactividad
"""

import asyncio
import aiohttp
import logging
import time
from datetime import datetime
from src.utils.config import BASE_URL

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KeepAliveService:
    def __init__(self, base_url=None, interval=300):  # 5 minutos por defecto
        self.base_url = base_url or BASE_URL
        self.interval = interval  # segundos
        self.running = False
        self.session = None
        self.stats = {
            "pings_sent": 0,
            "pings_successful": 0,
            "pings_failed": 0,
            "last_ping": None,
            "last_success": None,
            "last_error": None,
            "start_time": None
        }
    
    async def start(self):
        """Inicia el servicio de keep-alive"""
        if self.running:
            logger.warning("Keep-alive service ya está ejecutándose")
            return
        
        self.running = True
        self.stats["start_time"] = datetime.now()
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        )
        
        logger.info(f"🔄 Keep-alive iniciado - ping cada {self.interval} segundos")
        logger.info(f"🎯 Target URL: {self.base_url}")
        
        # Iniciar el loop de keep-alive
        asyncio.create_task(self._keep_alive_loop())
    
    async def stop(self):
        """Detiene el servicio de keep-alive"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("🛑 Keep-alive service detenido")
    
    async def _keep_alive_loop(self):
        """Loop principal de keep-alive"""
        while self.running:
            try:
                await self._ping_server()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                logger.info("Keep-alive loop cancelado")
                break
            except Exception as e:
                logger.error(f"Error en keep-alive loop: {e}")
                await asyncio.sleep(60)  # Esperar 1 minuto antes de reintentar
    
    async def _ping_server(self):
        """Envía un ping al servidor"""
        if not self.session:
            logger.error("Session no inicializada")
            return
        
        # Usar formato JSON para keep-alive
        ping_url = f"{self.base_url}/ping?format=json"
        self.stats["pings_sent"] += 1
        self.stats["last_ping"] = datetime.now()
        
        try:
            logger.debug(f"📡 Enviando ping a {ping_url}")
            
            async with self.session.get(ping_url) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        self.stats["pings_successful"] += 1
                        self.stats["last_success"] = datetime.now()
                        
                        uptime = data.get("uptime_seconds", 0)
                        logger.info(f"✅ Ping exitoso - Server uptime: {self._format_uptime(uptime)}")
                    except Exception as json_error:
                        # Si no puede parsear JSON, al menos verificar que el servidor responda
                        self.stats["pings_successful"] += 1
                        self.stats["last_success"] = datetime.now()
                        logger.info(f"✅ Ping exitoso - Server respondió (sin JSON)")
                else:
                    self.stats["pings_failed"] += 1
                    self.stats["last_error"] = f"HTTP {response.status}"
                    logger.warning(f"⚠️ Ping falló - HTTP {response.status}")
        
        except aiohttp.ClientError as e:
            self.stats["pings_failed"] += 1
            self.stats["last_error"] = str(e)
            logger.error(f"❌ Error de conexión en ping: {e}")
        
        except Exception as e:
            self.stats["pings_failed"] += 1
            self.stats["last_error"] = str(e)
            logger.error(f"❌ Error inesperado en ping: {e}")
    
    def _format_uptime(self, seconds):
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
    
    def get_stats(self):
        """Obtiene estadísticas del keep-alive"""
        stats = self.stats.copy()
        if stats["start_time"]:
            stats["running_time"] = datetime.now() - stats["start_time"]
            stats["success_rate"] = (
                (stats["pings_successful"] / stats["pings_sent"] * 100) 
                if stats["pings_sent"] > 0 else 0
            )
        return stats
    
    async def health_check(self):
        """Realiza un health check completo"""
        health_url = f"{self.base_url}/health?format=json"
        
        try:
            async with self.session.get(health_url) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                        logger.info("🏥 Health check exitoso")
                        return data
                    except Exception:
                        logger.info("🏥 Health check exitoso (sin JSON)")
                        return {"status": "ok"}
                else:
                    logger.warning(f"⚠️ Health check falló - HTTP {response.status}")
                    return None
        
        except Exception as e:
            logger.error(f"❌ Error en health check: {e}")
            return None

# Instancia global del servicio
keep_alive_service = KeepAliveService()

async def start_keep_alive(interval=300):
    """Función helper para iniciar el keep-alive"""
    keep_alive_service.interval = interval
    await keep_alive_service.start()

async def stop_keep_alive():
    """Función helper para detener el keep-alive"""
    await keep_alive_service.stop()

def get_keep_alive_stats():
    """Función helper para obtener estadísticas"""
    return keep_alive_service.get_stats()

# Función para usar en otros módulos
async def ping_self():
    """Envía un ping manual al servidor"""
    await keep_alive_service._ping_server()

if __name__ == "__main__":
    # Modo de prueba
    async def test_keep_alive():
        logger.info("🧪 Iniciando prueba de keep-alive...")
        await start_keep_alive(interval=30)  # Ping cada 30 segundos para prueba
        
        # Ejecutar por 5 minutos
        await asyncio.sleep(300)
        
        stats = get_keep_alive_stats()
        logger.info(f"📊 Estadísticas finales: {stats}")
        
        await stop_keep_alive()
    
    asyncio.run(test_keep_alive())
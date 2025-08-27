import aiosqlite
import asyncio
import os
from typing import Optional, Dict, Any

class Database:
    def __init__(self, db_path: str = None):
        # Configuración específica para Render
        if db_path is None:
            # En Render, usar disco persistente si está disponible
            data_dir = os.environ.get("RENDER_DATA_DIR", "/opt/render/project/src/data")
            if os.path.exists(data_dir):
                self.db_path = os.path.join(data_dir, "verification.db")
            else:
                # Fallback a directorio actual
                self.db_path = "verification.db"
        else:
            self.db_path = db_path
        
        # Crear directorio si no existe
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    async def init_db(self):
        """Inicializa la base de datos con las tablas necesarias"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS verifications (
                    discord_id INTEGER PRIMARY KEY,
                    genius_id INTEGER,
                    genius_username TEXT,
                    genius_display_name TEXT,
                    genius_roles TEXT,
                    access_token TEXT,
                    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pending_verifications (
                    state TEXT PRIMARY KEY,
                    discord_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
    
    async def create_pending_verification(self, state: str, discord_id: int):
        """Crea una verificación pendiente"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO pending_verifications (state, discord_id) VALUES (?, ?)",
                (state, discord_id)
            )
            await db.commit()
    
    async def get_pending_verification(self, state: str) -> Optional[int]:
        """Obtiene el discord_id de una verificación pendiente"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT discord_id FROM pending_verifications WHERE state = ?",
                (state,)
            )
            result = await cursor.fetchone()
            if result:
                # Eliminar la verificación pendiente después de usarla
                await db.execute(
                    "DELETE FROM pending_verifications WHERE state = ?",
                    (state,)
                )
                await db.commit()
                return result[0]
            return None
    
    async def save_verification(self, discord_id: int, genius_data: Dict[str, Any], access_token: str):
        """Guarda una verificación completada"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO verifications 
                (discord_id, genius_id, genius_username, genius_display_name, genius_roles, access_token)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                discord_id,
                genius_data.get('id'),
                genius_data.get('login'),
                genius_data.get('name'),
                ','.join(genius_data.get('roles', [])),
                access_token
            ))
            await db.commit()
    
    async def get_verification(self, discord_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene los datos de verificación de un usuario"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM verifications WHERE discord_id = ?",
                (discord_id,)
            )
            result = await cursor.fetchone()
            if result:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, result))
            return None
    
    async def is_verified(self, discord_id: int) -> bool:
        """Verifica si un usuario ya está verificado"""
        verification = await self.get_verification(discord_id)
        return verification is not None
    
    async def remove_verification(self, discord_id: int):
        """Elimina la verificación de un usuario"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM verifications WHERE discord_id = ?",
                (discord_id,)
            )
            await db.commit()
    
    async def get_verified_count(self) -> int:
        """Obtiene el número total de usuarios verificados"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM verifications")
            result = await cursor.fetchone()
            return result[0] if result else 0
    
    async def get_pending_count(self) -> int:
        """Obtiene el número de verificaciones pendientes"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM pending_verifications")
            result = await cursor.fetchone()
            return result[0] if result else 0
    
    async def get_stats(self) -> Dict[str, int]:
        """Obtiene estadísticas generales de la base de datos"""
        return {
            "verified_users": await self.get_verified_count(),
            "pending_verifications": await self.get_pending_count()
        }

# Instancia global de la base de datos
db = Database()
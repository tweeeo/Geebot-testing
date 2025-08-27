#!/usr/bin/env python3
"""
Genius en Español Bot - Punto de entrada principal
Reorganizado con estructura modular
"""

import sys
import os
import asyncio

# Agregar el directorio actual al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    """Función principal que inicia el bot y el servidor web"""
    from src.bot.main import run_bot
    await run_bot()

if __name__ == "__main__":
    # Ejecutar el bot
    asyncio.run(main())
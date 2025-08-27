# Archivos Legacy (Compatibilidad)

Esta carpeta contiene archivos de compatibilidad que redirigen a las nuevas ubicaciones de los módulos.

## ⚠️ Importante

Estos archivos se mantienen solo para compatibilidad con código existente que pueda importar desde las ubicaciones antiguas.

## Archivos

- `config.py` → `src.utils.config`
- `database.py` → `src.database.models`
- `keep_alive.py` → `src.services.keep_alive`
- `web_server.py` → `src.web.server`
- `main.py` → Punto de entrada legacy (usar `main_dynamic.py`)

## Migración

Si encuentras código que importa desde estos archivos, actualízalo para usar las nuevas ubicaciones:

```python
# ❌ Antiguo
from config import TOKEN
from database import db

# ✅ Nuevo
from src.utils.config import TOKEN
from src.database.models import db
```
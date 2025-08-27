# Comandos Adicionales para Genius en Español Bot

Este directorio contiene comandos adicionales para el bot de Genius en Español.

## Comando `message`

Este comando permite enviar mensajes personalizados con embeds, botones y más opciones de configuración.

### Características

- **Tipos de mensaje**: 
  - **Mensaje Simple**: Texto plano sin formato especial
  - **Mensaje con Embed**: Formato enriquecido con campos, colores, imágenes y editable
- **Embeds personalizados**: Título, descripción, color, imagen y footer
- **Campos adicionales**: Añade múltiples campos con formato personalizado
- **Botones interactivos**: Añade botones con enlaces a sitios web
- **Vista previa en tiempo real**: Visualiza cómo quedará tu mensaje antes de enviarlo
- **Selección de canal**: Elige a qué canal enviar el mensaje
- **Mensajes editables**: Los mensajes con embed incluyen un botón para editarlos después

### Uso

#### Slash Command (Recomendado)

```
/message [canal]
```

El parámetro `canal` es opcional. Si no se proporciona, se te pedirá seleccionar un canal durante la configuración.

#### Comando con Prefijo

```
!!message [#canal]
```

### Guía de Uso

1. Ejecuta el comando `/message`
2. Selecciona el tipo de mensaje que deseas crear:
   - **Mensaje Simple**: Un mensaje de texto plano sin formato especial
   - **Mensaje con Embed**: Un mensaje con formato enriquecido que incluye un botón para editarlo
3. Según tu elección:
   - Para **Mensaje Simple**: Escribe el texto del mensaje y selecciona un canal
   - Para **Mensaje con Embed**: Se abrirá un modal donde podrás configurar:
     - Título del embed
     - Descripción
     - Color (en formato hexadecimal)
     - URL de imagen
     - Texto de footer
4. Para mensajes con embed, después de enviar el formulario, verás una vista previa del mensaje
5. Usa los botones para:
   - Añadir campos adicionales
   - Añadir botones con enlaces
   - Limpiar campos
   - Editar el mensaje
   - Seleccionar un canal
   - Enviar el mensaje final
6. Los mensajes con embed incluyen un botón para editarlos posteriormente

### Permisos Requeridos

Este comando requiere permisos de administrador para ser utilizado.

### Ejemplos de Uso

- Anuncios importantes del servidor
- Mensajes de bienvenida personalizados
- Guías informativas con botones a recursos externos
- Mensajes de eventos con imágenes y detalles
- Mensajes de votación con enlaces a formularios

### Notas

- Los botones solo pueden contener enlaces (limitación de Discord)
- El mensaje puede contener hasta 25 campos
- La longitud total del mensaje está limitada por Discord
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import uuid
import logging
import os
import sys

# Agregar el directorio raíz al path para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database.models import db
from src.utils.config import *
from src.services.keep_alive import start_keep_alive, stop_keep_alive, get_keep_alive_stats
from src.utils.bot_instance import set_bot_instance

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Identificador único para esta instancia del bot
BOT_INSTANCE_ID = str(uuid.uuid4())[:8]
logger.info(f"🤖 Bot iniciado - Instancia ID: {BOT_INSTANCE_ID}")

# Tiempo de inicio del servidor para calcular uptime
import time
server_start_time = time.time()

def has_staff_permissions(user: discord.Member) -> bool:
    """
    Verifica si un usuario tiene permisos de staff (administrador o roles específicos)
    """
    # Verificar si es administrador
    if user.guild_permissions.administrator:
        return True
    
    # Verificar roles específicos de staff
    staff_role_names = ["Staff", "Moderator", "Editor", "Moderador"]  # Incluir variantes en español
    user_role_names = [role.name for role in user.roles]
    
    for staff_role in staff_role_names:
        if staff_role in user_role_names:
            return True
    
    return False

def has_manage_messages_or_staff(user: discord.Member) -> bool:
    """
    Verifica si un usuario tiene permisos para gestionar mensajes o es staff
    """
    return user.guild_permissions.manage_messages or has_staff_permissions(user)

async def remove_genius_roles(member: discord.Member, guild: discord.Guild):
    """Elimina todos los roles de Genius de un usuario"""
    try:
        # Obtener configuración dinámica
        from src.utils.dynamic_config import config
        
        # Lista de todos los roles de Genius que el bot puede asignar
        genius_role_ids = []
        genius_roles = ['ROLE_CONTRIBUTOR', 'ROLE_EDITOR', 'ROLE_MODERATOR', 'ROLE_STAFF', 'ROLE_VERIFIED_ARTIST', 'ROLE_TRANSCRIBER', 'ROLE_MEDIATOR']
        for role_key in genius_roles:
            role_id = config.get(role_key, '')
            if role_id and role_id.isdigit():
                genius_role_ids.append(int(role_id))
        
        verified_role_id = config.get('VERIFIED_ROLE_ID', '')
        if verified_role_id and verified_role_id.isdigit():
            genius_role_ids.append(int(verified_role_id))

        # Debug: mostrar configuración de roles
        print(f"🔍 DEBUG UNVERIFY - Genius role IDs configurados: {genius_role_ids}")
        print(f"🔍 DEBUG UNVERIFY - Roles del usuario: {[f'{role.name} (ID: {role.id})' for role in member.roles]}")
        
        # Encontrar roles que el usuario tiene y que son de Genius
        roles_to_remove = []
        for role in member.roles:
            if role.id in genius_role_ids:
                roles_to_remove.append(role)
                print(f"✅ DEBUG UNVERIFY - Rol a eliminar: {role.name} (ID: {role.id})")
            else:
                print(f"⏭️ DEBUG UNVERIFY - Rol no es de Genius: {role.name} (ID: {role.id})")

        print(f"🔍 DEBUG UNVERIFY - Total roles a eliminar: {len(roles_to_remove)}")
        
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Usuario desverificado")
            logger.info(f"✅ Roles de Genius eliminados de {member}: {[role.name for role in roles_to_remove]}")
        else:
            logger.info(f"ℹ️ {member} no tenía roles de Genius para eliminar")

        # Intentar restaurar nickname (opcional)
        try:
            await member.edit(nick=None, reason="Usuario desverificado")
            logger.info(f"✅ Nickname restaurado para {member}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo restaurar nickname de {member}: {e}")

    except Exception as e:
        logger.error(f"❌ Error eliminando roles de Genius de {member}: {e}")

async def setup_config_event_listeners():
    """Configurar listeners para eventos de configuración"""
    try:
        # Sistema de eventos local
        from src.utils.event_system import event_system, Events
        
        # Establecer el loop de eventos para callbacks async
        event_system.set_event_loop(asyncio.get_event_loop())
        
        # Suscribirse a eventos de configuración
        event_system.subscribe_async(Events.CONFIG_UPDATED, on_config_updated)
        event_system.subscribe_async(Events.ROLE_CONFIG_CHANGED, on_role_config_changed)
        event_system.subscribe_async(Events.DISCORD_TOKEN_CHANGED, on_discord_token_changed)
        
        # Sistema de señales para comunicación entre procesos
        from src.utils.signal_system import signal_system, Signals
        
        # Suscribirse a señales de configuración
        signal_system.subscribe(Signals.CONFIG_UPDATED, on_config_signal)
        signal_system.subscribe(Signals.ROLE_CONFIG_CHANGED, on_role_config_signal)
        signal_system.subscribe(Signals.DISCORD_TOKEN_CHANGED, on_discord_token_signal)
        
        # Iniciar polling de señales
        signal_system.start_polling(interval=2.0)
        
        logger.info("✅ Sistema de eventos y señales de configuración configurado")
        
    except Exception as e:
        logger.error(f"❌ Error configurando listeners de eventos: {e}")

async def on_config_updated(data):
    """Callback cuando se actualiza la configuración"""
    try:
        logger.info(f"🔄 Configuración actualizada: {data}")
        
        # La configuración dinámica se actualiza automáticamente
        # No necesitamos recargar nada manualmente
        
        logger.info("✅ Configuración dinámica actualizada automáticamente")
        
    except Exception as e:
        logger.error(f"❌ Error procesando actualización de configuración: {e}")

async def on_role_config_changed(data):
    """Callback cuando cambian configuraciones de roles"""
    try:
        logger.info(f"🎭 Configuración de roles actualizada: {data}")
        
        # Obtener configuración dinámica actualizada
        from src.utils.dynamic_config import config
        verified_role_id = config.get('VERIFIED_ROLE_ID', '')
        
        # Log de los nuevos valores
        logger.info(f"🔄 Roles actualizados - VERIFIED_ROLE_ID: {verified_role_id}")
        logger.info(f"🔄 Configuración de roles actualizada dinámicamente")
        
    except Exception as e:
        logger.error(f"❌ Error procesando cambio de roles: {e}")

async def on_discord_token_changed(data):
    """Callback cuando cambia el token de Discord"""
    try:
        logger.warning("⚠️ Token de Discord cambiado - Se requiere reinicio del bot")
        
        # Nota: Cambiar el token requiere reiniciar la conexión del bot
        # En un entorno de producción, esto podría requerir un reinicio completo
        
    except Exception as e:
        logger.error(f"❌ Error procesando cambio de token: {e}")

def on_config_signal(data):
    """Callback síncrono para señales de configuración"""
    try:
        logger.info(f"📡 Señal de configuración recibida: {data}")
        
        # La configuración dinámica se actualiza automáticamente
        # No necesitamos recargar nada manualmente
        
        logger.info("✅ Configuración dinámica actualizada desde señal")
        
    except Exception as e:
        logger.error(f"❌ Error procesando señal de configuración: {e}")

def on_role_config_signal(data):
    """Callback síncrono para señales de cambio de roles"""
    try:
        logger.info(f"🎭 Señal de roles recibida: {data}")
        
        # La configuración dinámica se actualiza automáticamente
        # No necesitamos recargar nada manualmente
        
        logger.info("✅ Configuración de roles actualizada dinámicamente desde señal")
        
    except Exception as e:
        logger.error(f"❌ Error procesando señal de roles: {e}")

def on_discord_token_signal(data):
    """Callback síncrono para señales de cambio de token"""
    try:
        logger.warning("⚠️ Señal de cambio de token recibida - Se requiere reinicio")
        
        # En un entorno de producción, esto podría disparar un reinicio automático
        
    except Exception as e:
        logger.error(f"❌ Error procesando señal de token: {e}")

intents = discord.Intents.default()
# Asegúrate de habilitar estos intents también en el Developer Portal
intents.guilds = True
intents.messages = True  # necesario para recibir MessageCreate
intents.message_content = True  # necesario para leer el contenido y usar prefijos
intents.guild_reactions = True
intents.members = True  # Necesario para obtener miembros del servidor

# Prefijo dinámico desde configuración
def get_prefix(_bot, message):
    # Devuelve el prefijo actual sin reiniciar el bot
    from src.utils.dynamic_config import config
    return config.get('CMD_PREFIX', '!!') or "!!"

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# Establecer la instancia del bot para acceso desde otros módulos
set_bot_instance(bot)

@bot.event
async def on_member_remove(member: discord.Member):
    """Se ejecuta cuando un miembro se sale del servidor"""
    try:
        # Verificar si el usuario estaba verificado
        if await db.is_verified(member.id):
            logger.info(f"👋 Usuario verificado {member} se salió del servidor {member.guild.name}")

            # Eliminar verificación de la base de datos
            await db.remove_verification(member.id)
            logger.info(f"🗑️ Verificación eliminada para {member}")

            # Nota: No necesitamos eliminar roles porque el usuario ya no está en el servidor
            # Los roles se eliminan automáticamente cuando alguien se sale

        else:
            logger.debug(f"Usuario no verificado {member} se salió del servidor")

    except Exception as e:
        logger.error(f"Error procesando salida de miembro {member}: {e}")

@bot.event
async def on_message(message: discord.Message):
    """Se ejecuta cuando se recibe un mensaje"""
    try:
        # Ignorar mensajes del bot
        if message.author == bot.user:
            return
        
        # Verificar si es un mensaje de bienvenida del sistema de Discord
        # Tipos de mensajes de bienvenida que Discord puede enviar:
        welcome_message_types = [
            discord.MessageType.new_member,           # Usuario se unió al servidor
            discord.MessageType.premium_guild_subscription,  # Boost del servidor
            discord.MessageType.premium_guild_tier_1,        # Servidor alcanzó nivel 1
            discord.MessageType.premium_guild_tier_2,        # Servidor alcanzó nivel 2  
            discord.MessageType.premium_guild_tier_3         # Servidor alcanzó nivel 3
        ]
        
        if (message.type in welcome_message_types and 
            message.author.bot is False):
            
            # Reaccionar con emoji de saludo
            await message.add_reaction("👋🏻")
            
            # Log específico según el tipo de mensaje
            if message.type == discord.MessageType.new_member:
                logger.info(f"👋 Reaccioné al mensaje de bienvenida de {message.author} en {message.guild.name}")
            elif message.type in [discord.MessageType.premium_guild_subscription, 
                                discord.MessageType.premium_guild_tier_1,
                                discord.MessageType.premium_guild_tier_2, 
                                discord.MessageType.premium_guild_tier_3]:
                logger.info(f"🎉 Reaccioné al mensaje de boost/nivel de {message.author} en {message.guild.name}")
        
        # Procesar comandos normalmente
        await bot.process_commands(message)
        
    except discord.Forbidden:
        logger.warning(f"No tengo permisos para reaccionar al mensaje en {message.guild.name if message.guild else 'DM'}")
    except discord.HTTPException as e:
        logger.warning(f"Error HTTP al reaccionar al mensaje: {e}")
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}")

# Comando simple para ver si responde (solo para staff)
@bot.command(name='ping')
async def ping(ctx: commands.Context):
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_PING', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    
    logger.info(f"🏓 [COMANDO] Ping ejecutado por {ctx.author} - ID: {ctx.message.id} - Instancia: {BOT_INSTANCE_ID}")
    await ctx.send(f'Pong! 🏓 (Instancia: `{BOT_INSTANCE_ID}`)')

# Comando de prueba para verificar reacciones de bienvenida (solo administradores y staff)
@bot.command(name='test_welcome')
async def test_welcome_reaction(ctx: commands.Context):
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_TEST_WELCOME', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    """Comando de prueba para verificar que las reacciones de bienvenida funcionan"""
    try:
        # Reaccionar al mensaje del comando con el emoji de bienvenida
        await ctx.message.add_reaction("👋🏻")
        
        embed = discord.Embed(
            title="🧪 Prueba de Reacciones de Bienvenida",
            description="✅ **Funcionalidad activa**\n\nEl bot ahora reaccionará automáticamente con 👋🏻 a:\n• Mensajes de nuevos miembros\n• Mensajes de boost del servidor\n• Mensajes de nivel del servidor",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📋 Tipos de Mensaje Soportados",
            value="• `new_member` - Usuario se unió\n• `premium_guild_subscription` - Boost\n• `premium_guild_tier_1/2/3` - Niveles",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Configuración",
            value="• Emoji: 👋🏻 (`:wave_tone1:`)\n• Solo usuarios reales (no bots)\n• Logging habilitado",
            inline=False
        )
        
        embed.set_footer(text="Prueba completada - El bot reaccionó a este mensaje")
        
        await ctx.send(embed=embed)
        logger.info(f"🧪 Prueba de reacciones de bienvenida ejecutada por {ctx.author}")
        
    except Exception as e:
        await ctx.send(f"❌ Error en la prueba: {e}")
        logger.error(f"Error en test_welcome_reaction: {e}")

class HelpView(discord.ui.View):
    def __init__(self, is_admin=False):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.is_admin = is_admin
        self.current_page = 0
        self.pages = self.create_pages()
        
    def create_pages(self):
        """Crea las páginas del sistema de ayuda"""
        pages = []
        
        # Página 1: Información General
        embed1 = discord.Embed(
            title="Genius en Español - Ayuda (Página 1/4)",
            description="Bot de verificación con Genius para obtener roles automáticamente",
            color=0x5865f2
        )
        
        embed1.add_field(
            name="¿Qué es GeeBot?",
            value=(
                "Este bot permite verificar tu cuenta de **Genius** "
                "y obtener roles automáticamente en Discord basados en tu perfil de la plataforma.\n\n"
                "- **Conecta** tu cuenta de Genius\n"
                "- **Obtén roles** automáticamente\n"
                "- **Verificación** instantánea"
            ),
            inline=False
        )
        
        embed1.add_field(
            name="Inicio Rápido",
            value=(
                "1️. Un administrador ejecuta `!!setup_verification` o `/setup_verification`\n"
                "2️. Haz clic en el botón **🔗 Verificar con Genius**\n"
                "3️. Autoriza la aplicación en Genius.com\n"
                "4️. ¡Listo! Obtienes tus roles automáticamente"
            ),
            inline=False
        )
        
        embed1.add_field(
            name="Tipos de Comandos",
            value=(
                "- **Comandos con prefijo:** `!!comando`\n"
                "- **Slash commands:** `/comando`\n"
                "- Ambos tipos funcionan igual, ¡usa el que prefieras!"
            ),
            inline=False
        )
        
        embed1.set_footer(text="Usa los botones para navegar • Página 1 de 4")
        pages.append(embed1)
        
        # Página 2: Comandos de Usuario
        embed2 = discord.Embed(
            title="Genius en Español - Comandos de Usuario (Página 2/4)",
            description="Comandos disponibles para todos los usuarios",
            color=0x5865f2
        )
        
        user_commands = [
            {
                "name": "verify_status",
                "description": "Verifica tu estado de verificación actual",
                "prefix_usage": "!!verify_status [@usuario]",
                "slash_usage": "/verify_status [usuario]"
            },
            {
                "name": "help",
                "description": "Muestra el menú de ayuda interactivo",
                "prefix_usage": "!!help",
                "slash_usage": "/help"
            }
        ]
        
        for cmd in user_commands:
            embed2.add_field(
                name=f"**{cmd['name']}**",
                value=f"- {cmd['description']}\n"
                      f"- **Prefijo:** `{cmd['prefix_usage']}`\n"
                      f"- **Slash:** `{cmd['slash_usage']}`",
                inline=False
            )
        
        embed2.set_footer(text="Usa los botones para navegar • Página 2 de 4")
        pages.append(embed2)
        
        # Página 3: Comandos de Administrador (solo si es admin)
        if self.is_admin:
            embed3 = discord.Embed(
                title="Genius en Español - Comandos de Admin (Página 3/4)",
                description="Comandos disponibles solo para administradores",
                color=0xff6b6b
            )
            
            admin_commands = [
                {
                    "name": "setup_verification",
                    "description": "Configura el mensaje de verificación",
                    "prefix_usage": "!!setup_verification",
                    "slash_usage": "/setup_verification"
                },
                {
                    "name": "unverify",
                    "description": "Desverifica a un usuario y elimina sus roles",
                    "prefix_usage": "!!unverify @usuario",
                    "slash_usage": "/unverify usuario"
                },
                {
                    "name": "verified_list",
                    "description": "Lista todos los usuarios verificados del servidor",
                    "prefix_usage": "!!verified_list",
                    "slash_usage": "/verified_list"
                },
                {
                    "name": "list_roles",
                    "description": "Muestra todos los roles del servidor con sus IDs",
                    "prefix_usage": "!!list_roles",
                    "slash_usage": "/list_roles"
                },
                {
                    "name": "show_config",
                    "description": "Muestra la configuración actual del bot",
                    "prefix_usage": "!!show_config",
                    "slash_usage": "/show_config"
                },
                {
                    "name": "test_roles",
                    "description": "Prueba la asignación de roles manualmente",
                    "prefix_usage": "!!test_roles [@usuario]",
                    "slash_usage": "/test_roles [usuario]"
                },
                {
                    "name": "cleanup_verifications",
                    "description": "Limpia verificaciones de usuarios que ya no están",
                    "prefix_usage": "!!cleanup_verifications",
                    "slash_usage": "/cleanup_verifications"
                },
                {
                    "name": "bot_stats",
                    "description": "Muestra estadísticas completas del bot y sistema",
                    "prefix_usage": "!!bot_stats",
                    "slash_usage": "/bot_stats"
                },
                {
                    "name": "message",
                    "description": "Envía un mensaje personalizado con embeds y botones",
                    "prefix_usage": "!!message [#canal]",
                    "slash_usage": "/message [canal]"
                },
                {
                    "name": "clean",
                    "description": "Elimina los últimos mensajes del canal actual",
                    "prefix_usage": "!!clean [cantidad]",
                    "slash_usage": "/clean [cantidad]"
                },
                {
                    "name": "test_welcome",
                    "description": "Prueba las reacciones automáticas de bienvenida",
                    "prefix_usage": "!!test_welcome",
                    "slash_usage": "N/A (solo prefijo)"
                },
                {
                    "name": "sync",
                    "description": "Sincroniza los comandos slash con Discord",
                    "prefix_usage": "!!sync",
                    "slash_usage": "N/A (solo prefijo)"
                }
            ]
            
            # Mostrar comandos de forma más compacta
            for cmd in admin_commands:
                embed3.add_field(
                    name=f"**{cmd['name']}**",
                    value=f"- {cmd['description']}\n"
                          f"- `{cmd['prefix_usage']}`\n"
                          f"- `{cmd['slash_usage']}`",
                    inline=True
                )
            
            embed3.set_footer(text="Usa los botones para navegar • Página 3 de 4")
            embed3.set_author(
                name="Modo Administrador Activado",
                icon_url="https://cdn.discordapp.com/emojis/852558866305024000.png"
            )
            pages.append(embed3)
        else:
            # Página 3 para usuarios normales: Información sobre roles
            embed3 = discord.Embed(
                title="Genius en Español - Roles Disponibles (Página 3/4)",
                description="Roles que puedes obtener al verificarte con Genius",
                color=0x5865f2
            )
            
            roles_info = [
                ("🎤 **Verified Artist**", "Artistas verificados en Genius"),
                ("👑 **Staff**", "Personal oficial de Genius"),
                ("🛡️ **Moderator**", "Moderadores de comunidad"),
                ("✏️ **Editor**", "Editores de contenido"),
                ("📝 **Transcriber**", "Transcriptores de letras"),
                ("⚖️ **Mediator**", "Mediadores de disputas"),
                ("🤝 **Contributor**", "Contribuidores generales")
            ]
            
            roles_text = ""
            for role_name, role_desc in roles_info:
                roles_text += f"{role_name}\n{role_desc}\n\n"
            
            embed3.add_field(
                name="🏷️ Roles de Genius Soportados",
                value=roles_text,
                inline=False
            )
            
            embed3.set_footer(text="Usa los botones para navegar • Página 3 de 4")
            pages.append(embed3)
        
        # Página 4: Información Adicional
        embed4 = discord.Embed(
            title="Genius en Español - Información Adicional (Página 4/4)",
            description="Detalles técnicos y enlaces útiles",
            color=0x5865f2
        )
        
        embed4.add_field(
            name="Proceso de Verificación Detallado",
            value=(
                "1️. **Setup:** un Moderador ejecuta `!!setup_verification` o `/setup_verification`\n"
                "2️. **Click:** Usuario hace clic en 🔗 Verificar con Genius\n"
                "3️. **Redirect:** Redirección a Genius.com\n"
                "4️. **Auth:** Usuario autoriza la aplicación\n"
                "5. **Magic:** Bot automáticamente:\n"
                "   • Cambia nickname al nombre de Genius\n"
                "   • Asigna roles basados en estatus\n"
                "   • Confirma verificación exitosa"
            ),
            inline=False
        )
        
        embed4.add_field(
            name="Ventajas de los Slash Commands",
            value=(
                "• **Autocompletado:** Discord sugiere opciones automáticamente\n"
                "• **Validación:** Parámetros validados antes de enviar\n"
                "• **Interfaz moderna:** Integración nativa con Discord\n"
                "• **Privacidad:** Algunos comandos pueden ser privados (ephemeral)"
            ),
            inline=False
        )
        
        embed4.add_field(
            name="Notas Importantes",
            value=(
                "• Los roles se asignan automáticamente según tu cuenta en Genius\n"
                "• Solo puedes verificarte una vez por cuenta\n"
                "• Los moderadores pueden desverificar usuarios si es necesario\n"
                "• El bot respeta la privacidad y solo accede a información pública"
            ),
            inline=False
        )
        
        embed4.set_footer(text="Usa los botones para navegar • Página 4 de 4")
        pages.append(embed4)
        
        return pages
    
    def update_buttons(self):
        """Actualiza el estado de los botones según la página actual"""
        # Botón anterior
        self.children[0].disabled = (self.current_page == 0)
        
        # Botón siguiente
        self.children[1].disabled = (self.current_page == len(self.pages) - 1)
        
        # Actualizar labels con números de página
        self.children[0].label = f"◀️ Anterior"
        self.children[1].label = f"Siguiente ▶️"
    
    @discord.ui.button(label='◀️ Anterior', style=discord.ButtonStyle.secondary, disabled=True)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label='Siguiente ▶️', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label='🏠 Inicio', style=discord.ButtonStyle.primary)
    async def go_home(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label='❌ Cerrar', style=discord.ButtonStyle.danger)
    async def close_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Ayuda Cerrada",
            description="¡Gracias por usar el bot! Usa `!!help` cuando necesites ayuda nuevamente.",
            color=0x95a5a6
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def on_timeout(self):
        """Se ejecuta cuando el view expira"""
        # Deshabilitar todos los botones
        for item in self.children:
            item.disabled = True

@bot.command(name='help')
async def help_command(ctx):
    """Muestra la ayuda interactiva del bot con paginación (solo para staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_HELP', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    
    logger.info(f"❓ [COMANDO] Help ejecutado por {ctx.author}")
    
    # Verificar si el usuario es administrador o staff
    is_admin = has_staff_permissions(ctx.author)
    
    # Crear vista con paginación
    view = HelpView(is_admin=is_admin)
    view.update_buttons()
    
    # Enviar el primer embed con la vista
    await ctx.send(embed=view.pages[0], view=view)

@bot.command(name='test')
async def test(ctx):
    """Comando de prueba simple (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_TEST', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    
    logger.info(f"🧪 [COMANDO] Test ejecutado por {ctx.author}")
    await ctx.send("✅ **Test exitoso!** El bot está funcionando correctamente.")

class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='🔗 Verificar con Genius', style=discord.ButtonStyle.primary, custom_id='verify_button')
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🔗 [BOTÓN] Verificación iniciada por {interaction.user} - Instancia: {BOT_INSTANCE_ID}")
        
        # Verificar si el usuario ya está verificado
        if await db.is_verified(interaction.user.id):
            embed = discord.Embed(
                title="⚠️ Ya Verificado",
                description="Tu cuenta ya está verificada",
                color=0xffa500
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Generar estado único para la verificación
        state = str(uuid.uuid4())
        logger.info(f"🔗 [BOTÓN] Estado generado: {state} para usuario {interaction.user.id}")
        
        # Guardar verificación pendiente
        await db.create_pending_verification(state, interaction.user.id)
        
        # Crear URL de verificación
        verification_url = f"{BASE_URL}/auth?state={state}"
        logger.info(f"🔗 [BOTÓN] URL generada: {verification_url}")
        
        embed = discord.Embed(
            title="🔗 Verificación",
            description="Haz clic en el enlace de abajo para verificar tu cuenta de Genius",
            color=0x5865f2
        )
        embed.add_field(
            name="Instrucciones:",
            value="1. Haz clic en el enlace\n2. Inicia sesión en Genius\n3. Autoriza la aplicación\n4. ¡Listo!",
            inline=False
        )
        embed.add_field(
            name="🔗 Enlace de Verificación",
            value=f"[Verificar con Genius]({verification_url})",
            inline=False
        )
        embed.set_footer(text="Este enlace expira en 10 minutos")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} ha iniciado sesión!')
    logger.info(f'Bot conectado a {len(bot.guilds)} servidores')
    logger.info(f'🤖 Esta instancia: {BOT_INSTANCE_ID}')

    # Evitar ejecutar múltiples veces si el bot se reconecta
    if not hasattr(bot, '_ready_once'):
        bot._ready_once = True

        # Verificar duplicación después de 10 segundos
        asyncio.create_task(check_for_duplicate_instances())

        # Inicializar base de datos
        await db.init_db()

        # Agregar la vista persistente
        bot.add_view(VerificationView())
        
        # Configurar sistema de eventos para sincronización en tiempo real
        await setup_config_event_listeners()
        
        # Cargar comandos adicionales
        try:
            # Cargar todos los comandos dinámicamente
            from src.bot.commands import load_all_commands
            loaded_commands = load_all_commands(bot)
            logger.info(f"✅ Comandos cargados: {', '.join(loaded_commands)}")
            
            # Sincronizar los comandos con Discord
            logger.info("🔄 Sincronizando comandos con Discord...")
            try:
                # Intentar sincronizar varias veces si es necesario
                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    try:
                        synced = await bot.tree.sync()
                        logger.info(f"✅ Comandos sincronizados correctamente: {len(synced)} comandos")
                        
                        # Registrar los comandos sincronizados
                        if synced:
                            command_names = [cmd.name for cmd in synced]
                            logger.info(f"📋 Comandos slash disponibles: {', '.join(command_names)}")
                        break  # Salir del bucle si la sincronización fue exitosa
                    except Exception as attempt_error:
                        if attempt < max_attempts:
                            logger.warning(f"⚠️ Intento {attempt} fallido: {attempt_error}. Reintentando en 2 segundos...")
                            await asyncio.sleep(2)
                        else:
                            raise  # Re-lanzar la excepción en el último intento
                
            except Exception as sync_error:
                logger.error(f"❌ Error sincronizando comandos después de {max_attempts} intentos: {sync_error}")
                logger.info("ℹ️ Los comandos se pueden sincronizar manualmente con !!sync")
            
            logger.info("✅ Todos los comandos adicionales cargados correctamente")
        except Exception as e:
            logger.error(f"❌ Error cargando comandos adicionales: {e}")

        # Solo iniciar servidor web si no estamos en modo unificado
        if not os.environ.get("UNIFIED_MODE", False):
            # Iniciar servidor web en background
            asyncio.create_task(start_web_server())
            logger.info("🌐 Servidor web iniciado en modo independiente")
        else:
            logger.info("🌐 Modo unificado: servidor web gestionado externamente")
        
        # Iniciar keep-alive service si está habilitado
        if KEEP_ALIVE_ENABLED:
            asyncio.create_task(start_keep_alive(interval=KEEP_ALIVE_INTERVAL))
            logger.info(f"🔄 Keep-alive habilitado (intervalo: {KEEP_ALIVE_INTERVAL}s)")

        logger.info("Bot listo, servidor web y keep-alive iniciados!")
    else:
        logger.info("Bot reconectado (no reinicializando servicios)")

async def start_web_server():
    """Inicia el servidor web en background"""
    try:
        from src.web.server import start_server
        await start_server()
    except Exception as e:
        logger.error(f"Error iniciando servidor web: {e}")

@bot.command(name='setup_verification')
async def setup_verification(ctx):
    """Comando para configurar el canal de verificación (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_SETUP_VERIFICATION', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    try:
        logger.info(f"🔧 [COMANDO] setup_verification ejecutado por {ctx.author} en {ctx.guild.name} - Instancia: {BOT_INSTANCE_ID}")
        base_url = config.get('BASE_URL', '')
        logger.info(f"🔧 [DEBUG] BASE_URL actual: {base_url}")

        embed = discord.Embed(
            title="🔐 Verificación con Genius",
            description="Verifica tu cuenta de Genius para acceder a las funciones del servidor.",
            color=0x5865f2
        )
        embed.add_field(
            name="¿Por qué verificar?",
            value="• Acceso a canales\n• Roles basados en cuenta de Genius\n• Nickname automático de Genius",
            inline=False
        )
        embed.set_footer(text="Haz clic en el botón de abajo para comenzar")

        view = VerificationView()
        logger.info(f"📤 [COMANDO] Enviando embed de verificación...")
        message = await ctx.send(embed=embed, view=view)
        logger.info(f"✅ [COMANDO] Setup de verificación completado exitosamente - Mensaje ID: {message.id}")

    except Exception as e:
        logger.error(f"❌ [COMANDO] Error en setup_verification: {e}")
        await ctx.send(f"❌ Error configurando verificación: {str(e)}")

@bot.command(name='verify_status')
async def verify_status(ctx, user: discord.Member = None):
    """Verifica el estado de verificación de un usuario"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_VERIFY_STATUS', 'true').lower() == 'true':
        return
    
    # Si el usuario especifica a otro usuario, verificar permisos
    if user and user != ctx.author:
        if not has_staff_permissions(ctx.author):
            embed = discord.Embed(
                title="❌ Sin Permisos",
                description="Solo puedes verificar tu propio estado de verificación. Los administradores y staff pueden verificar el estado de otros usuarios.",
                color=0xf04747
            )
            await ctx.send(embed=embed)
            return
    
    target_user = user or ctx.author
    
    verification = await db.get_verification(target_user.id)
    
    if verification:
        embed = discord.Embed(
            title="✅ Usuario Verificado",
            color=0x43b581
        )
        embed.add_field(name="Discord", value=f"{target_user.mention}", inline=True)
        embed.add_field(name="Genius Username", value=verification['genius_username'], inline=True)
        embed.add_field(name="Genius Display Name", value=verification['genius_display_name'], inline=True)
        embed.add_field(name="Roles en Genius", value=verification['genius_roles'] or "Contributor", inline=False)
        embed.add_field(name="Verificado el", value=verification['verified_at'], inline=True)
    else:
        embed = discord.Embed(
            title="❌ Usuario No Verificado",
            description=f"{target_user.mention} no ha verificado su cuenta de Genius.com",
            color=0xf04747
        )
    
    await ctx.send(embed=embed)

@bot.command(name='unverify')
async def unverify(ctx, user: discord.Member):
    """Desverifica a un usuario y elimina sus roles de Genius (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_UNVERIFY', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    if await db.is_verified(user.id):
        # Eliminar de la base de datos
        await db.remove_verification(user.id)

        # Eliminar roles de Genius del usuario
        await remove_genius_roles(user, ctx.guild)

        embed = discord.Embed(
            title="✅ Usuario Desverificado",
            description=f"{user.mention} ha sido desverificado exitosamente",
            color=0x43b581
        )
        embed.add_field(
            name="Acciones realizadas:",
            value="• Eliminado de la base de datos\n• Roles de Genius removidos\n• Nickname restaurado",
            inline=False
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Error",
            description=f"{user.mention} no estaba verificado",
            color=0xf04747
        )
        await ctx.send(embed=embed)

@bot.command(name='verified_list')
async def verified_list(ctx):
    """Lista todos los usuarios verificados (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_VERIFIED_LIST', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    logger.info(f"📋 [COMANDO] verified_list ejecutado por {ctx.author}")
    
    try:
        # Obtener estadísticas de la base de datos
        stats = await db.get_stats()
        verified_count = stats.get("verified_users", 0)
        
        if verified_count == 0:
            embed = discord.Embed(
                title="📋 Lista de Usuarios Verificados",
                description="No hay usuarios verificados en este servidor",
                color=0xffa500
            )
            await ctx.send(embed=embed)
            return
        
        # Obtener todos los usuarios verificados
        # Necesitamos agregar un método a la base de datos para esto
        try:
            import aiosqlite
            async with aiosqlite.connect(db.db_path) as database:
                cursor = await database.execute("""
                    SELECT discord_id, genius_username, genius_display_name, 
                           genius_roles, verified_at 
                    FROM verifications 
                    ORDER BY verified_at DESC
                """)
                verified_users = await cursor.fetchall()
        except Exception as e:
            logger.error(f"Error obteniendo usuarios verificados: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Error al obtener la lista de usuarios verificados",
                color=0xf04747
            )
            await ctx.send(embed=embed)
            return
        
        # Crear embed con la lista
        embed = discord.Embed(
            title="📋 Lista de Usuarios Verificados",
            description=f"Total de usuarios verificados: **{verified_count}**",
            color=0x43b581
        )
        
        # Procesar usuarios en grupos de 10 para evitar límites de embed
        users_per_page = 10
        current_page = 0
        total_pages = (len(verified_users) + users_per_page - 1) // users_per_page
        
        start_idx = current_page * users_per_page
        end_idx = min(start_idx + users_per_page, len(verified_users))
        
        users_text = ""
        for i, user_data in enumerate(verified_users[start_idx:end_idx], start_idx + 1):
            discord_id, genius_username, genius_display_name, genius_roles, verified_at = user_data
            
            # Intentar obtener el usuario de Discord
            discord_user = ctx.guild.get_member(discord_id)
            if discord_user:
                discord_name = f"{discord_user.mention}"
                status_emoji = "🟢"
            else:
                discord_name = f"Usuario no encontrado (ID: {discord_id})"
                status_emoji = "🔴"
            
            # Formatear roles
            roles_list = genius_roles.split(',') if genius_roles else ['Contributor']
            roles_text = ', '.join(roles_list)
            
            # Formatear fecha
            try:
                from datetime import datetime
                verified_date = datetime.fromisoformat(verified_at.replace('Z', '+00:00'))
                date_text = verified_date.strftime("%d/%m/%Y")
            except:
                date_text = "Fecha desconocida"
            
            users_text += f"{status_emoji} **{i}.** {discord_name}\n"
            users_text += f"   🎵 **Genius:** {genius_display_name or genius_username}\n"
            users_text += f"   🏷️ **Roles:** {roles_text}\n"
            users_text += f"   📅 **Verificado:** {date_text}\n\n"
        
        embed.add_field(
            name=f"👥 Usuarios ({start_idx + 1}-{end_idx} de {len(verified_users)})",
            value=users_text or "No hay usuarios para mostrar",
            inline=False
        )
        
        # Agregar información de páginas si hay más de una página
        if total_pages > 1:
            embed.set_footer(text=f"Página {current_page + 1} de {total_pages} • Usa !!verified_list [página] para ver más")
        
        # Agregar estadísticas adicionales
        active_users = sum(1 for user_data in verified_users if ctx.guild.get_member(user_data[0]))
        inactive_users = len(verified_users) - active_users
        
        embed.add_field(
            name="📊 Estadísticas",
            value=f"🟢 **Activos:** {active_users}\n🔴 **Inactivos:** {inactive_users}",
            inline=True
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error en verified_list: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error ejecutando comando: {str(e)}",
            color=0xf04747
        )
        await ctx.send(embed=embed)

@bot.command(name='test_roles')
async def test_roles(ctx, user: discord.Member = None):
    """Prueba la asignación de roles manualmente (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_TEST_ROLES', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    target_user = user or ctx.author

    # Simular roles de Genius para prueba - puedes cambiar estos roles
    test_roles = ["Contributor", "Editor", "Staff", "Verified Artist"]

    discord_roles_to_add = []
    role_mapping = {
        "Contributor": config.get('ROLE_CONTRIBUTOR', ''),
        "Editor": config.get('ROLE_EDITOR', ''),
        "Moderator": config.get('ROLE_MODERATOR', ''),
        "Staff": config.get('ROLE_STAFF', ''),
        "Verified Artist": config.get('ROLE_VERIFIED_ARTIST', ''),
        "Transcriber": config.get('ROLE_TRANSCRIBER', ''),
        "Mediator": config.get('ROLE_MEDIATOR', '')
    }

    embed = discord.Embed(title="🧪 Prueba de Asignación de Roles", color=0x5865f2)

    for genius_role in test_roles:
        role_id = role_mapping.get(genius_role, '')
        if role_id and role_id.isdigit():
            role = ctx.guild.get_role(int(role_id))
            if role:
                discord_roles_to_add.append(role)
                # Mostrar mención del rol en vez de ID
                embed.add_field(name=f"✅ {genius_role}", value=f"→ {role.mention}", inline=False)
            else:
                embed.add_field(name=f"❌ {genius_role}", value=f"Rol no encontrado (ID: {role_id})", inline=False)
        else:
            embed.add_field(name=f"⚠️ {genius_role}", value="No mapeado", inline=False)

    if discord_roles_to_add:
        try:
            await target_user.add_roles(*discord_roles_to_add, reason="Prueba manual de roles")
            embed.add_field(name="Resultado", value=f"✅ Roles asignados a {target_user.mention}", inline=False)
        except Exception as e:
            embed.add_field(name="Error", value=f"❌ {str(e)}", inline=False)
    else:
        embed.add_field(name="Resultado", value="❌ No se encontraron roles para asignar", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='list_roles')
async def list_roles(ctx):
    """Lista todos los roles del servidor con sus IDs (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_LIST_ROLES', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(title="📋 Roles del Servidor", color=0x5865f2)

    roles_info = []
    for role in ctx.guild.roles:
        if role.name != "@everyone":
            roles_info.append(f"**{role.name}** - ID: `{role.id}` (pos: {role.position})")

    # Dividir en chunks si hay muchos roles
    chunk_size = 10
    for i in range(0, len(roles_info), chunk_size):
        chunk = roles_info[i:i+chunk_size]
        embed.add_field(
            name=f"Roles {i+1}-{min(i+chunk_size, len(roles_info))}",
            value="\n".join(chunk),
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command(name='show_config')
async def show_config(ctx):
    """Muestra la configuración actual del bot (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_SHOW_CONFIG', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    logger.info(f"⚙️ [COMANDO] show_config ejecutado por {ctx.author}")
    
    try:
        # Obtener configuración dinámica
        verification_channel_id = config.get('VERIFICATION_CHANNEL_ID', '')
        verified_role_id = config.get('VERIFIED_ROLE_ID', '')
        
        embed = discord.Embed(
            title="⚙️ Configuración Actual del Bot",
            description="Configuración de roles y canales",
            color=0x5865f2
        )
        
        # Mostrar canal de verificación
        if verification_channel_id:
            channel = ctx.guild.get_channel(int(verification_channel_id)) if verification_channel_id.isdigit() else None
            channel_name = channel.name if channel else "Canal no encontrado"
            embed.add_field(
                name="📢 Canal de Verificación",
                value=f"{channel_name} (`{verification_channel_id}`)",
                inline=False
            )
        else:
            embed.add_field(
                name="📢 Canal de Verificación",
                value="❌ No configurado",
                inline=False
            )
        
        # Mostrar rol verificado general
        if verified_role_id:
            role = ctx.guild.get_role(int(verified_role_id)) if verified_role_id.isdigit() else None
            role_name = role.name if role else "Rol no encontrado"
            embed.add_field(
                name="✅ Rol Verificado General",
                value=f"{role_name} (`{verified_role_id}`)",
                inline=False
            )
        else:
            embed.add_field(
                name="✅ Rol Verificado General",
                value="❌ No configurado",
                inline=False
            )
        
        # Mostrar roles de Genius
        roles_info = []
        genius_roles = ['ROLE_CONTRIBUTOR', 'ROLE_EDITOR', 'ROLE_MODERATOR', 'ROLE_STAFF', 'ROLE_VERIFIED_ARTIST', 'ROLE_TRANSCRIBER', 'ROLE_MEDIATOR']
        for genius_role_key in genius_roles:
            role_id = config.get(genius_role_key, '')
            genius_role_name = genius_role_key.replace('ROLE_', '').replace('_', ' ').title()
            if role_id and role_id.isdigit():
                role = ctx.guild.get_role(int(role_id))
                role_name = role.name if role else "Rol no encontrado"
                status = "✅" if role else "⚠️"
                roles_info.append(f"{status} **{genius_role_name}**: {role_name} (`{role_id}`)")
            else:
                roles_info.append(f"❌ **{genius_role_name}**: No configurado")
        
        if roles_info:
            embed.add_field(
                name="🎭 Roles de Genius",
                value="\n".join(roles_info),
                inline=False
            )
        
        embed.add_field(
            name="🔧 Panel de Control",
            value="Configura estos valores desde el panel web en `/panel`",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error en show_config: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error obteniendo configuración: {e}",
            color=0xff0000
        )
        await ctx.send(embed=embed)

@bot.command(name='cleanup_verifications')
async def cleanup_verifications(ctx):
    """Limpia verificaciones de usuarios que ya no están en el servidor (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_CLEANUP_VERIFICATIONS', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    logger.info(f"🧹 [COMANDO] cleanup_verifications ejecutado por {ctx.author}")
    
    try:
        # Obtener todos los usuarios verificados
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as database:
            cursor = await database.execute("""
                SELECT discord_id, genius_username, genius_display_name 
                FROM verifications
            """)
            verified_users = await cursor.fetchall()
        
        if not verified_users:
            embed = discord.Embed(
                title="🧹 Limpieza de Verificaciones",
                description="No hay verificaciones para limpiar",
                color=0xffa500
            )
            await ctx.send(embed=embed)
            return
        
        # Verificar qué usuarios ya no están en el servidor
        users_to_remove = []
        for discord_id, genius_username, genius_display_name in verified_users:
            member = ctx.guild.get_member(discord_id)
            if not member:
                users_to_remove.append((discord_id, genius_username, genius_display_name))
        
        if not users_to_remove:
            embed = discord.Embed(
                title="🧹 Limpieza de Verificaciones",
                description="✅ Todas las verificaciones están actualizadas\nNo se encontraron usuarios inactivos para limpiar",
                color=0x43b581
            )
            await ctx.send(embed=embed)
            return
        
        # Mostrar usuarios que serán eliminados y pedir confirmación
        users_text = ""
        for i, (discord_id, genius_username, genius_display_name) in enumerate(users_to_remove[:10], 1):
            users_text += f"{i}. **{genius_display_name or genius_username}** (ID: {discord_id})\n"
        
        if len(users_to_remove) > 10:
            users_text += f"... y {len(users_to_remove) - 10} más"
        
        embed = discord.Embed(
            title="🧹 Limpieza de Verificaciones",
            description=f"Se encontraron **{len(users_to_remove)}** verificaciones de usuarios que ya no están en el servidor:",
            color=0xffa500
        )
        embed.add_field(
            name="👥 Usuarios a eliminar:",
            value=users_text,
            inline=False
        )
        embed.add_field(
            name="⚠️ Confirmación requerida",
            value="Reacciona con ✅ para confirmar la limpieza o ❌ para cancelar",
            inline=False
        )
        
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        
        def check(reaction, user):
            return (user == ctx.author and 
                   str(reaction.emoji) in ["✅", "❌"] and 
                   reaction.message.id == message.id)
        
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # Proceder con la limpieza
                removed_count = 0
                async with aiosqlite.connect(db.db_path) as database:
                    for discord_id, _, _ in users_to_remove:
                        await database.execute(
                            "DELETE FROM verifications WHERE discord_id = ?",
                            (discord_id,)
                        )
                        removed_count += 1
                    await database.commit()
                
                embed = discord.Embed(
                    title="🧹 Limpieza Completada",
                    description=f"✅ Se eliminaron **{removed_count}** verificaciones obsoletas",
                    color=0x43b581
                )
                embed.add_field(
                    name="📊 Resultado",
                    value=f"• Verificaciones eliminadas: {removed_count}\n• Verificaciones restantes: {len(verified_users) - removed_count}",
                    inline=False
                )
                await message.edit(embed=embed)
                
            else:
                embed = discord.Embed(
                    title="🧹 Limpieza Cancelada",
                    description="❌ La limpieza de verificaciones fue cancelada",
                    color=0xf04747
                )
                await message.edit(embed=embed)
                
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="🧹 Limpieza Expirada",
                description="⏰ La confirmación expiró. La limpieza fue cancelada",
                color=0xffa500
            )
            await message.edit(embed=embed)
        
        # Limpiar reacciones
        try:
            await message.clear_reactions()
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error en cleanup_verifications: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error ejecutando limpieza: {str(e)}",
            color=0xf04747
        )
        await ctx.send(embed=embed)

@bot.command(name='sync', aliases=['sincronizar'])
async def sync_commands(ctx):
    """Sincroniza los comandos slash con Discord (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_SYNC', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    try:
        logger.info(f"🔄 Sincronizando comandos (solicitado por {ctx.author})")
        
        # Enviar mensaje de inicio
        message = await ctx.send("🔄 **Sincronizando comandos...**")
        
        # Sincronizar comandos
        synced = await bot.tree.sync()
        
        # Actualizar mensaje
        if synced:
            command_list = ", ".join([f"`/{cmd.name}`" for cmd in synced])
            await message.edit(content=f"✅ **{len(synced)} comandos sincronizados correctamente**\n\nComandos disponibles:\n{command_list}")
        else:
            await message.edit(content="✅ **Comandos sincronizados correctamente**\nNo se encontraron cambios en los comandos.")
        
        logger.info(f"✅ Comandos sincronizados correctamente: {len(synced)} comandos")
        if synced:
            command_names = [cmd.name for cmd in synced]
            logger.info(f"📋 Comandos slash disponibles: {', '.join(command_names)}")
    except Exception as e:
        logger.error(f"❌ Error sincronizando comandos: {e}")
        await ctx.send(f"❌ **Error sincronizando comandos:** {str(e)}")

@bot.command(name='bot_stats')
async def bot_stats(ctx):
    """Muestra estadísticas completas del bot (solo administradores y staff)"""
    from src.utils.dynamic_config import config
    if not config.get('ENABLE_COMMAND_BOT_STATS', 'true').lower() == 'true':
        return
    
    # Verificar permisos de staff
    if not has_staff_permissions(ctx.author):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await ctx.send(embed=embed)
        return
    logger.info(f"📊 [COMANDO] bot_stats ejecutado por {ctx.author}")
    
    try:
        # Obtener estadísticas de la base de datos
        stats = await db.get_stats()
        
        # Obtener información del bot
        guild_count = len(bot.guilds)
        total_members = sum(guild.member_count for guild in bot.guilds)
        
        # Obtener uptime
        import time
        from datetime import datetime, timedelta
        
        # Calcular uptime (aproximado desde que se inició el proceso)
        uptime_seconds = int(time.time() - server_start_time) if 'server_start_time' in globals() else 0
        uptime_delta = timedelta(seconds=uptime_seconds)
        
        # Obtener información de memoria
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
        except ImportError:
            memory_mb = "N/A"
            cpu_percent = "N/A"
        
        embed = discord.Embed(
            title="📊 Estadísticas del Bot",
            description=f"Estadísticas completas de **{bot.user.name}**",
            color=0x5865f2
        )
        
        # Información básica del bot
        embed.add_field(
            name="🤖 Información del Bot",
            value=f"• **Nombre:** {bot.user.name}\n"
                  f"• **ID:** {bot.user.id}\n"
                  f"• **Instancia:** `{BOT_INSTANCE_ID}`\n"
                  f"• **Latencia:** {round(bot.latency * 1000)}ms",
            inline=True
        )
        
        # Estadísticas de servidores
        embed.add_field(
            name="🏰 Servidores",
            value=f"• **Servidores:** {guild_count}\n"
                  f"• **Miembros totales:** {total_members}\n"
                  f"• **Miembros únicos:** {len(bot.users)}",
            inline=True
        )
        
        # Estadísticas de verificación
        embed.add_field(
            name="✅ Verificaciones",
            value=f"• **Usuarios verificados:** {stats.get('verified_users', 0)}\n"
                  f"• **Verificaciones pendientes:** {stats.get('pending_verifications', 0)}",
            inline=True
        )
        
        # Información del sistema
        embed.add_field(
            name="💻 Sistema",
            value=f"• **Uptime:** {str(uptime_delta).split('.')[0]}\n"
                  f"• **Memoria:** {memory_mb:.1f} MB\n"
                  f"• **CPU:** {cpu_percent}%" if cpu_percent != "N/A" else f"• **CPU:** N/A",
            inline=True
        )
        
        # Información de keep-alive
        if KEEP_ALIVE_ENABLED:
            try:
                ka_stats = get_keep_alive_stats()
                success_rate = ka_stats.get('success_rate', 0)
                embed.add_field(
                    name="🔄 Keep-Alive",
                    value=f"• **Estado:** Activo\n"
                          f"• **Pings enviados:** {ka_stats.get('pings_sent', 0)}\n"
                          f"• **Tasa de éxito:** {success_rate:.1f}%",
                    inline=True
                )
            except:
                embed.add_field(
                    name="🔄 Keep-Alive",
                    value="• **Estado:** Activo\n• **Estadísticas:** No disponibles",
                    inline=True
                )
        else:
            embed.add_field(
                name="🔄 Keep-Alive",
                value="• **Estado:** Deshabilitado",
                inline=True
            )
        
        # Información de configuración
        embed.add_field(
            name="⚙️ Configuración",
            value=f"• **Base URL:** {BASE_URL}\n"
                  f"• **Puerto:** {WEB_SERVER_PORT}\n"
                  f"• **Roles configurados:** {len([r for r in GENIUS_ROLE_IDS.values() if r != 0])}",
            inline=False
        )
        
        embed.set_footer(text=f"Bot iniciado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error en bot_stats: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error obteniendo estadísticas: {str(e)}",
            color=0xf04747
        )
        await ctx.send(embed=embed)

# ==================== VIEWS ADICIONALES ====================
# Vistas para slash commands que requieren confirmación

class CleanupConfirmationView(discord.ui.View):
    def __init__(self, users_to_remove, database):
        super().__init__(timeout=30.0)
        self.users_to_remove = users_to_remove
        self.database = database
    
    @discord.ui.button(label='✅ Confirmar Limpieza', style=discord.ButtonStyle.danger)
    async def confirm_cleanup(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Proceder con la limpieza
            removed_count = 0
            import aiosqlite
            async with aiosqlite.connect(self.database.db_path) as database:
                for discord_id, _, _ in self.users_to_remove:
                    await database.execute(
                        "DELETE FROM verifications WHERE discord_id = ?",
                        (discord_id,)
                    )
                    removed_count += 1
                await database.commit()
            
            embed = discord.Embed(
                title="🧹 Limpieza Completada",
                description=f"✅ Se eliminaron **{removed_count}** verificaciones obsoletas",
                color=0x43b581
            )
            embed.add_field(
                name="📊 Resultado",
                value=f"• Verificaciones eliminadas: {removed_count}\n• Operación completada exitosamente",
                inline=False
            )
            
            # Deshabilitar botones
            for item in self.children:
                item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error en confirmación de limpieza: {e}")
            embed = discord.Embed(
                title="❌ Error en Limpieza",
                description=f"Error ejecutando limpieza: {str(e)}",
                color=0xf04747
            )
            await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label='❌ Cancelar', style=discord.ButtonStyle.secondary)
    async def cancel_cleanup(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🧹 Limpieza Cancelada",
            description="❌ La limpieza de verificaciones fue cancelada",
            color=0xf04747
        )
        
        # Deshabilitar botones
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        # Deshabilitar botones cuando expire el timeout
        for item in self.children:
            item.disabled = True

# ==================== SLASH COMMANDS ====================
# Implementación de slash commands para todos los comandos existentes

@bot.tree.command(name="ping", description="Comando simple para verificar si el bot responde (Solo staff)")
async def slash_ping(interaction: discord.Interaction):
    """Slash command version of ping"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    logger.info(f"🏓 [SLASH] Ping ejecutado por {interaction.user} - ID: {interaction.id} - Instancia: {BOT_INSTANCE_ID}")
    await interaction.response.send_message(f'Pong! 🏓 (Instancia: `{BOT_INSTANCE_ID}`)')

@bot.tree.command(name="help", description="Muestra el menú de ayuda interactivo del bot (Solo staff)")
async def slash_help(interaction: discord.Interaction):
    """Slash command version of help"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    logger.info(f"❓ [SLASH] Help ejecutado por {interaction.user}")
    
    # Verificar si el usuario es administrador o staff
    is_admin = has_staff_permissions(interaction.user)
    
    # Crear vista con paginación
    view = HelpView(is_admin=is_admin)
    view.update_buttons()
    
    # Enviar el primer embed con la vista
    await interaction.response.send_message(embed=view.pages[0], view=view)

@bot.tree.command(name="verify_status", description="Verifica el estado de verificación de un usuario")
@app_commands.describe(user="Usuario del cual verificar el estado (opcional, por defecto tú mismo)")
async def slash_verify_status(interaction: discord.Interaction, user: discord.Member = None):
    """Slash command version of verify_status"""
    # Si el usuario especifica a otro usuario, verificar permisos
    if user and user != interaction.user:
        if not has_staff_permissions(interaction.user):
            embed = discord.Embed(
                title="❌ Sin Permisos",
                description="Solo puedes verificar tu propio estado de verificación. Los administradores y staff pueden verificar el estado de otros usuarios.",
                color=0xf04747
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    target_user = user or interaction.user
    
    verification = await db.get_verification(target_user.id)
    
    if verification:
        embed = discord.Embed(
            title="✅ Usuario Verificado",
            color=0x43b581
        )
        embed.add_field(name="Discord", value=f"{target_user.mention}", inline=True)
        embed.add_field(name="Genius Username", value=verification['genius_username'], inline=True)
        embed.add_field(name="Genius Display Name", value=verification['genius_display_name'], inline=True)
        embed.add_field(name="Roles en Genius", value=verification['genius_roles'] or "Contributor", inline=False)
        embed.add_field(name="Verificado el", value=verification['verified_at'], inline=True)
    else:
        embed = discord.Embed(
            title="❌ Usuario No Verificado",
            description=f"{target_user.mention} no ha verificado su cuenta de Genius.com",
            color=0xf04747
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setup_verification", description="Configura el mensaje de verificación con botón (Solo administradores y staff)")
async def slash_setup_verification(interaction: discord.Interaction):
    """Slash command version of setup_verification"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    try:
        logger.info(f"🔧 [SLASH] setup_verification ejecutado por {interaction.user} en {interaction.guild.name} - Instancia: {BOT_INSTANCE_ID}")
        logger.info(f"🔧 [DEBUG] BASE_URL actual: {BASE_URL}")

        embed = discord.Embed(
            title="🔐 Verificación con Genius",
            description="Verifica tu cuenta de Genius para acceder a las funciones del servidor.",
            color=0x5865f2
        )
        embed.add_field(
            name="¿Por qué verificar?",
            value="• Acceso a canales\n• Roles basados en cuenta de Genius\n• Nickname automático de Genius",
            inline=False
        )
        embed.set_footer(text="Haz clic en el botón de abajo para comenzar")

        view = VerificationView()
        logger.info(f"📤 [SLASH] Enviando embed de verificación...")
        await interaction.response.send_message(embed=embed, view=view)
        logger.info(f"✅ [SLASH] Setup de verificación completado exitosamente")

    except Exception as e:
        logger.error(f"❌ [SLASH] Error en setup_verification: {e}")
        await interaction.response.send_message(f"❌ Error configurando verificación: {str(e)}", ephemeral=True)

@bot.tree.command(name="unverify", description="Desverifica a un usuario y elimina sus roles de Genius (Solo administradores y staff)")
@app_commands.describe(user="Usuario a desverificar")
async def slash_unverify(interaction: discord.Interaction, user: discord.Member):
    """Slash command version of unverify"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if await db.is_verified(user.id):
        # Eliminar de la base de datos
        await db.remove_verification(user.id)

        # Eliminar roles de Genius del usuario
        await remove_genius_roles(user, interaction.guild)

        embed = discord.Embed(
            title="✅ Usuario Desverificado",
            description=f"{user.mention} ha sido desverificado exitosamente",
            color=0x43b581
        )
        embed.add_field(
            name="Acciones realizadas:",
            value="• Eliminado de la base de datos\n• Roles de Genius removidos\n• Nickname restaurado",
            inline=False
        )
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Error",
            description=f"{user.mention} no estaba verificado",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="verified_list", description="Lista todos los usuarios verificados del servidor (Solo administradores y staff)")
async def slash_verified_list(interaction: discord.Interaction):
    """Slash command version of verified_list"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    logger.info(f"📋 [SLASH] verified_list ejecutado por {interaction.user}")
    
    try:
        # Obtener estadísticas de la base de datos
        stats = await db.get_stats()
        verified_count = stats.get("verified_users", 0)
        
        if verified_count == 0:
            embed = discord.Embed(
                title="📋 Lista de Usuarios Verificados",
                description="No hay usuarios verificados en este servidor",
                color=0xffa500
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Obtener todos los usuarios verificados
        try:
            import aiosqlite
            async with aiosqlite.connect(db.db_path) as database:
                cursor = await database.execute("""
                    SELECT discord_id, genius_username, genius_display_name, 
                           genius_roles, verified_at 
                    FROM verifications 
                    ORDER BY verified_at DESC
                """)
                verified_users = await cursor.fetchall()
        except Exception as e:
            logger.error(f"Error obteniendo usuarios verificados: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="Error al obtener la lista de usuarios verificados",
                color=0xf04747
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Crear embed con la lista
        embed = discord.Embed(
            title="📋 Lista de Usuarios Verificados",
            description=f"Total de usuarios verificados: **{verified_count}**",
            color=0x43b581
        )
        
        # Procesar usuarios en grupos de 10 para evitar límites de embed
        users_per_page = 10
        current_page = 0
        total_pages = (len(verified_users) + users_per_page - 1) // users_per_page
        
        start_idx = current_page * users_per_page
        end_idx = min(start_idx + users_per_page, len(verified_users))
        
        users_text = ""
        for i, user_data in enumerate(verified_users[start_idx:end_idx], start_idx + 1):
            discord_id, genius_username, genius_display_name, genius_roles, verified_at = user_data
            
            # Intentar obtener el usuario de Discord
            discord_user = interaction.guild.get_member(discord_id)
            if discord_user:
                discord_name = f"{discord_user.mention}"
                status_emoji = "🟢"
            else:
                discord_name = f"Usuario no encontrado (ID: {discord_id})"
                status_emoji = "🔴"
            
            # Formatear roles
            roles_list = genius_roles.split(',') if genius_roles else ['Contributor']
            roles_text = ', '.join(roles_list)
            
            # Formatear fecha
            try:
                from datetime import datetime
                verified_date = datetime.fromisoformat(verified_at.replace('Z', '+00:00'))
                date_text = verified_date.strftime("%d/%m/%Y")
            except:
                date_text = "Fecha desconocida"
            
            users_text += f"{status_emoji} **{i}.** {discord_name}\n"
            users_text += f"   🎵 **Genius:** {genius_display_name or genius_username}\n"
            users_text += f"   🏷️ **Roles:** {roles_text}\n"
            users_text += f"   📅 **Verificado:** {date_text}\n\n"
        
        embed.add_field(
            name=f"👥 Usuarios ({start_idx + 1}-{end_idx} de {len(verified_users)})",
            value=users_text or "No hay usuarios para mostrar",
            inline=False
        )
        
        # Agregar información de páginas si hay más de una página
        if total_pages > 1:
            embed.set_footer(text=f"Página {current_page + 1} de {total_pages} • Usa /verified_list para ver más")
        
        # Agregar estadísticas adicionales
        active_users = sum(1 for user_data in verified_users if interaction.guild.get_member(user_data[0]))
        inactive_users = len(verified_users) - active_users
        
        embed.add_field(
            name="📊 Estadísticas",
            value=f"🟢 **Activos:** {active_users}\n🔴 **Inactivos:** {inactive_users}",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        logger.error(f"Error en verified_list: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error ejecutando comando: {str(e)}",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="test_roles", description="Prueba la asignación de roles manualmente (Solo administradores y staff)")
@app_commands.describe(user="Usuario para probar roles (opcional, por defecto tú mismo)")
async def slash_test_roles(interaction: discord.Interaction, user: discord.Member = None):
    """Slash command version of test_roles"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    target_user = user or interaction.user

    # Simular roles de Genius para prueba - puedes cambiar estos roles
    test_roles = ["Contributor", "Editor", "Staff", "Verified Artist"]

    from src.utils.dynamic_config import config
    
    discord_roles_to_add = []
    role_mapping = {
        "Contributor": config.get('ROLE_CONTRIBUTOR', ''),
        "Editor": config.get('ROLE_EDITOR', ''),
        "Moderator": config.get('ROLE_MODERATOR', ''),
        "Staff": config.get('ROLE_STAFF', ''),
        "Verified Artist": config.get('ROLE_VERIFIED_ARTIST', ''),
        "Transcriber": config.get('ROLE_TRANSCRIBER', ''),
        "Mediator": config.get('ROLE_MEDIATOR', '')
    }

    embed = discord.Embed(title="🧪 Prueba de Asignación de Roles", color=0x5865f2)

    for genius_role in test_roles:
        role_id = role_mapping.get(genius_role, '')
        if role_id and role_id.isdigit():
            role = interaction.guild.get_role(int(role_id))
            if role:
                discord_roles_to_add.append(role)
                # Mostrar mención del rol en vez de ID
                embed.add_field(name=f"✅ {genius_role}", value=f"→ {role.mention}", inline=False)
            else:
                embed.add_field(name=f"❌ {genius_role}", value=f"Rol no encontrado (ID: {role_id})", inline=False)
        else:
            embed.add_field(name=f"⚠️ {genius_role}", value="No mapeado", inline=False)

    if discord_roles_to_add:
        try:
            await target_user.add_roles(*discord_roles_to_add, reason="Prueba manual de roles")
            embed.add_field(name="Resultado", value=f"✅ Roles asignados a {target_user.mention}", inline=False)
        except Exception as e:
            embed.add_field(name="Error", value=f"❌ {str(e)}", inline=False)
    else:
        embed.add_field(name="Resultado", value="❌ No se encontraron roles para asignar", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list_roles", description="Lista todos los roles del servidor con sus IDs (Solo administradores y staff)")
async def slash_list_roles(interaction: discord.Interaction):
    """Slash command version of list_roles"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(title="📋 Roles del Servidor", color=0x5865f2)

    roles_info = []
    for role in interaction.guild.roles:
        if role.name != "@everyone":
            roles_info.append(f"**{role.name}** - ID: `{role.id}` (pos: {role.position})")

    # Dividir en chunks si hay muchos roles
    chunk_size = 10
    for i in range(0, len(roles_info), chunk_size):
        chunk = roles_info[i:i+chunk_size]
        embed.add_field(
            name=f"Roles {i+1}-{min(i+chunk_size, len(roles_info))}",
            value="\n".join(chunk),
            inline=False
        )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="show_config", description="Muestra la configuración actual del bot (Solo administradores y staff)")
async def slash_show_config(interaction: discord.Interaction):
    """Slash command version of show_config"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    logger.info(f"⚙️ [SLASH] show_config ejecutado por {interaction.user}")
    
    try:
        # Obtener configuración dinámica
        from src.utils.dynamic_config import config
        verification_channel_id = config.get('VERIFICATION_CHANNEL_ID', '')
        verified_role_id = config.get('VERIFIED_ROLE_ID', '')
        
        embed = discord.Embed(
            title="⚙️ Configuración Actual del Bot",
            description="Configuración de roles y canales",
            color=0x5865f2
        )
        
        # Mostrar canal de verificación
        if verification_channel_id:
            channel = interaction.guild.get_channel(int(verification_channel_id)) if verification_channel_id.isdigit() else None
            channel_name = channel.name if channel else "Canal no encontrado"
            embed.add_field(
                name="📢 Canal de Verificación",
                value=f"{channel_name} (`{verification_channel_id}`)",
                inline=False
            )
        else:
            embed.add_field(
                name="📢 Canal de Verificación",
                value="❌ No configurado",
                inline=False
            )
        
        # Mostrar rol verificado general
        if verified_role_id:
            role = interaction.guild.get_role(int(verified_role_id)) if verified_role_id.isdigit() else None
            role_name = role.name if role else "Rol no encontrado"
            embed.add_field(
                name="✅ Rol Verificado General",
                value=f"{role_name} (`{verified_role_id}`)",
                inline=False
            )
        else:
            embed.add_field(
                name="✅ Rol Verificado General",
                value="❌ No configurado",
                inline=False
            )
        
        # Mostrar roles de Genius
        roles_info = []
        genius_roles = ['ROLE_CONTRIBUTOR', 'ROLE_EDITOR', 'ROLE_MODERATOR', 'ROLE_STAFF', 'ROLE_VERIFIED_ARTIST', 'ROLE_TRANSCRIBER', 'ROLE_MEDIATOR']
        for genius_role_key in genius_roles:
            role_id = config.get(genius_role_key, '')
            genius_role_name = genius_role_key.replace('ROLE_', '').replace('_', ' ').title()
            if role_id and role_id.isdigit():
                role = interaction.guild.get_role(int(role_id))
                role_name = role.name if role else "Rol no encontrado"
                status = "✅" if role else "⚠️"
                roles_info.append(f"{status} **{genius_role_name}**: {role_name} (`{role_id}`)")
            else:
                roles_info.append(f"❌ **{genius_role_name}**: No configurado")
        
        if roles_info:
            embed.add_field(
                name="🎭 Roles de Genius",
                value="\n".join(roles_info),
                inline=False
            )
        
        embed.add_field(
            name="🔧 Panel de Control",
            value="Configura estos valores desde el panel web en `/panel`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        logger.error(f"Error en slash_show_config: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error obteniendo configuración: {e}",
            color=0xff0000
        )
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="cleanup_verifications", description="Limpia verificaciones de usuarios que ya no están en el servidor (Solo administradores y staff)")
async def slash_cleanup_verifications(interaction: discord.Interaction):
    """Slash command version of cleanup_verifications"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    logger.info(f"🧹 [SLASH] cleanup_verifications ejecutado por {interaction.user}")
    
    try:
        # Obtener todos los usuarios verificados
        import aiosqlite
        async with aiosqlite.connect(db.db_path) as database:
            cursor = await database.execute("""
                SELECT discord_id, genius_username, genius_display_name 
                FROM verifications
            """)
            verified_users = await cursor.fetchall()
        
        if not verified_users:
            embed = discord.Embed(
                title="🧹 Limpieza de Verificaciones",
                description="No hay verificaciones para limpiar",
                color=0xffa500
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Verificar qué usuarios ya no están en el servidor
        users_to_remove = []
        for discord_id, genius_username, genius_display_name in verified_users:
            member = interaction.guild.get_member(discord_id)
            if not member:
                users_to_remove.append((discord_id, genius_username, genius_display_name))
        
        if not users_to_remove:
            embed = discord.Embed(
                title="🧹 Limpieza de Verificaciones",
                description="✅ Todas las verificaciones están actualizadas\nNo se encontraron usuarios inactivos para limpiar",
                color=0x43b581
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Mostrar usuarios que serán eliminados
        users_text = ""
        for i, (discord_id, genius_username, genius_display_name) in enumerate(users_to_remove[:10], 1):
            users_text += f"{i}. **{genius_display_name or genius_username}** (ID: {discord_id})\n"
        
        if len(users_to_remove) > 10:
            users_text += f"... y {len(users_to_remove) - 10} más"
        
        embed = discord.Embed(
            title="🧹 Limpieza de Verificaciones",
            description=f"Se encontraron **{len(users_to_remove)}** verificaciones de usuarios que ya no están en el servidor:",
            color=0xffa500
        )
        embed.add_field(
            name="👥 Usuarios a eliminar:",
            value=users_text,
            inline=False
        )
        embed.add_field(
            name="⚠️ Confirmación requerida",
            value="Usa los botones de abajo para confirmar o cancelar la limpieza",
            inline=False
        )
        
        # Crear vista con botones de confirmación
        view = CleanupConfirmationView(users_to_remove, db)
        await interaction.response.send_message(embed=embed, view=view)
            
    except Exception as e:
        logger.error(f"Error en cleanup_verifications: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error ejecutando limpieza: {str(e)}",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="bot_stats", description="Muestra estadísticas completas del bot (Solo administradores y staff)")
async def slash_bot_stats(interaction: discord.Interaction):
    """Slash command version of bot_stats"""
    # Verificar permisos de staff
    if not has_staff_permissions(interaction.user):
        embed = discord.Embed(
            title="❌ Sin Permisos",
            description="Este comando solo está disponible para administradores y staff.",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    logger.info(f"📊 [SLASH] bot_stats ejecutado por {interaction.user}")
    
    try:
        # Obtener estadísticas de la base de datos
        stats = await db.get_stats()
        
        # Obtener información del bot
        guild_count = len(bot.guilds)
        total_members = sum(guild.member_count for guild in bot.guilds)
        
        # Obtener uptime
        import time
        from datetime import datetime, timedelta
        
        # Calcular uptime (aproximado desde que se inició el proceso)
        uptime_seconds = int(time.time() - server_start_time) if 'server_start_time' in globals() else 0
        uptime_delta = timedelta(seconds=uptime_seconds)
        
        # Obtener información de memoria
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
        except ImportError:
            memory_mb = "N/A"
            cpu_percent = "N/A"
        
        embed = discord.Embed(
            title="📊 Estadísticas del Bot",
            description=f"Estadísticas completas de **{bot.user.name}**",
            color=0x5865f2
        )
        
        # Información básica del bot
        embed.add_field(
            name="🤖 Información del Bot",
            value=f"• **Nombre:** {bot.user.name}\n"
                  f"• **ID:** {bot.user.id}\n"
                  f"• **Instancia:** `{BOT_INSTANCE_ID}`\n"
                  f"• **Latencia:** {round(bot.latency * 1000)}ms",
            inline=True
        )
        
        # Estadísticas de servidores
        embed.add_field(
            name="🏰 Servidores",
            value=f"• **Servidores:** {guild_count}\n"
                  f"• **Miembros totales:** {total_members}\n"
                  f"• **Miembros únicos:** {len(bot.users)}",
            inline=True
        )
        
        # Estadísticas de verificación
        embed.add_field(
            name="✅ Verificaciones",
            value=f"• **Usuarios verificados:** {stats.get('verified_users', 0)}\n"
                  f"• **Verificaciones pendientes:** {stats.get('pending_verifications', 0)}",
            inline=True
        )
        
        # Información del sistema
        embed.add_field(
            name="💻 Sistema",
            value=f"• **Uptime:** {str(uptime_delta).split('.')[0]}\n"
                  f"• **Memoria:** {memory_mb:.1f} MB\n"
                  f"• **CPU:** {cpu_percent}%" if cpu_percent != "N/A" else f"• **CPU:** N/A",
            inline=True
        )
        
        # Información de keep-alive
        if KEEP_ALIVE_ENABLED:
            try:
                ka_stats = get_keep_alive_stats()
                success_rate = ka_stats.get('success_rate', 0)
                embed.add_field(
                    name="🔄 Keep-Alive",
                    value=f"• **Estado:** Activo\n"
                          f"• **Pings enviados:** {ka_stats.get('pings_sent', 0)}\n"
                          f"• **Tasa de éxito:** {success_rate:.1f}%",
                    inline=True
                )
            except:
                embed.add_field(
                    name="🔄 Keep-Alive",
                    value="• **Estado:** Activo\n• **Estadísticas:** No disponibles",
                    inline=True
                )
        else:
            embed.add_field(
                name="🔄 Keep-Alive",
                value="• **Estado:** Deshabilitado",
                inline=True
            )
        
        # Información de configuración
        embed.add_field(
            name="⚙️ Configuración",
            value=f"• **Base URL:** {BASE_URL}\n"
                  f"• **Puerto:** {WEB_SERVER_PORT}\n"
                  f"• **Roles configurados:** {len([r for r in GENIUS_ROLE_IDS.values() if r != 0])}",
            inline=False
        )
        
        embed.set_footer(text=f"Bot iniciado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        logger.error(f"Error en bot_stats: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Error obteniendo estadísticas: {str(e)}",
            color=0xf04747
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def shutdown_handler():
    """Maneja el cierre limpio del bot"""
    logger.info("🔄 Iniciando cierre limpio...")
    
    try:
        # Detener keep-alive
        if KEEP_ALIVE_ENABLED:
            await stop_keep_alive()
            logger.info("🛑 Keep-alive detenido")
        
        # Cerrar conexión del bot
        if not bot.is_closed():
            await bot.close()
            logger.info("🛑 Bot desconectado")
            
    except Exception as e:
        logger.error(f"Error durante cierre: {e}")
    
    logger.info("✅ Cierre completado")

async def check_for_duplicate_instances():
    """Verifica si hay instancias duplicadas del bot ejecutándose"""
    await asyncio.sleep(10)  # Esperar a que el servidor web esté listo
    
    try:
        logger.info(f"🔍 Verificando duplicación de instancias - Mi ID: {BOT_INSTANCE_ID}")
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            ping_url = f"{BASE_URL}/ping?format=json"
            instance_ids = set()
            
            # Hacer múltiples pings para detectar diferentes instancias
            for i in range(5):
                try:
                    async with session.get(ping_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'instance_id' in data:
                                instance_ids.add(data['instance_id'])
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.debug(f"Error en ping {i+1}: {e}")
            
            if len(instance_ids) > 1:
                logger.warning(f"🚨 MÚLTIPLES INSTANCIAS DETECTADAS: {instance_ids}")
                
                # Determinar cuál instancia debe continuar (la primera alfabéticamente)
                sorted_instances = sorted(instance_ids)
                logger.info(f"📋 Instancias ordenadas: {sorted_instances}")
                
                if BOT_INSTANCE_ID != sorted_instances[0]:
                    logger.warning(f"🛑 CERRANDO INSTANCIA DUPLICADA: {BOT_INSTANCE_ID}")
                    logger.warning(f"✅ INSTANCIA PRINCIPAL CONTINÚA: {sorted_instances[0]}")
                    
                    # Cerrar esta instancia
                    await shutdown_handler()
                    os._exit(1)
                else:
                    logger.info(f"✅ SOY LA INSTANCIA PRINCIPAL: {BOT_INSTANCE_ID}")
                    
                    # Iniciar verificación periódica
                    asyncio.create_task(periodic_duplicate_check())
            else:
                logger.info(f"✅ Instancia única detectada: {BOT_INSTANCE_ID}")
                
                # Iniciar verificación periódica de todas formas
                asyncio.create_task(periodic_duplicate_check())
                
    except Exception as e:
        logger.error(f"Error verificando duplicación: {e}")

async def periodic_duplicate_check():
    """Verificación periódica de duplicación cada 2 minutos"""
    while True:
        try:
            await asyncio.sleep(120)  # Esperar 2 minutos
            logger.info(f"🔍 Verificación periódica de duplicación - Instancia: {BOT_INSTANCE_ID}")
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                ping_url = f"{BASE_URL}/ping?format=json"
                instance_ids = set()
                
                # Hacer 3 pings rápidos
                for i in range(3):
                    try:
                        async with session.get(ping_url) as response:
                            if response.status == 200:
                                data = await response.json()
                                if 'instance_id' in data:
                                    instance_ids.add(data['instance_id'])
                        await asyncio.sleep(1)
                    except:
                        pass
                
                if len(instance_ids) > 1:
                    logger.warning(f"🚨 DUPLICACIÓN DETECTADA EN VERIFICACIÓN PERIÓDICA: {instance_ids}")
                    sorted_instances = sorted(instance_ids)
                    
                    # Si no somos la primera, cerramos inmediatamente
                    if BOT_INSTANCE_ID != sorted_instances[0]:
                        logger.warning(f"🛑 CERRANDO INSTANCIA DUPLICADA: {BOT_INSTANCE_ID}")
                        os._exit(1)
                else:
                    logger.debug(f"✅ Verificación periódica OK - Instancia única: {BOT_INSTANCE_ID}")
                    
        except Exception as e:
            logger.error(f"Error en verificación periódica: {e}")
            await asyncio.sleep(60)  # Esperar 1 minuto antes de reintentar

async def run_bot():
    """Función principal que inicia el bot y el servidor web"""
    try:
        # Inicializar base de datos
        await db.init_db()
        logger.info("✅ Base de datos inicializada")
        
        # Iniciar servidor web en background (legacy Quart) solo si NO estamos en modo unificado
        import os as _os
        server_task = None
        if _os.environ.get("UNIFIED_MODE") != "true":
            from src.web.server import app
            import hypercorn.asyncio
            from hypercorn import Config
            
            config = Config()
            config.bind = [f"{WEB_SERVER_HOST}:{WEB_SERVER_PORT}"]
            config.use_reloader = False
            config.accesslog = "-"  # Log a stdout
            
            logger.info(f"🌐 Iniciando servidor web (legacy) en {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
            
            # Iniciar servidor web como tarea en background
            server_task = asyncio.create_task(
                hypercorn.asyncio.serve(app, config)
            )
        else:
            logger.info("🧩 UNIFIED_MODE activo: se omite servidor web legacy (Quart)")
        
        # Iniciar keep-alive si está habilitado
        if KEEP_ALIVE_ENABLED:
            from src.services.keep_alive import start_keep_alive
            await start_keep_alive()
            logger.info("🔄 Keep-alive iniciado")
        
        # Verificar duplicación de instancias después de un tiempo
        asyncio.create_task(check_for_duplicate_instances())
        
        # Iniciar el bot de Discord
        logger.info(f"🚀 Iniciando bot de Discord - Instancia: {BOT_INSTANCE_ID}")
        try:
            await bot.start(TOKEN)
        except Exception as e:
            logger.error(f"Error iniciando bot de Discord: {e}")
            logger.info("🌐 Servidor web continuará ejecutándose...")
            # Mantener el servidor web ejecutándose
            await server_task
        
    except KeyboardInterrupt:
        logger.info("🔄 Interrupción detectada, cerrando...")
        await shutdown_handler()
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🔄 Interrupción detectada, cerrando...")
    except Exception as e:
        logger.error(f"Error fatal: {e}")
import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import asyncio
import re
from typing import Optional, List

# Configurar logging
logger = logging.getLogger(__name__)

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

def process_mentions(content: str, guild: discord.Guild) -> str:
    """
    Procesa menciones en el texto y las convierte a formato Discord válido.
    Soporta:
    - @usuario o @Usuario#1234 -> <@user_id>
    - #canal -> <#channel_id>
    - @everyone y @here (se mantienen como están)
    - Roles: @rol -> <@&role_id>
    """
    if not content or not guild:
        return content
    
    processed_content = content
    
    # Procesar menciones de usuarios (@usuario o @Usuario#1234)
    # Usar un patrón más específico para evitar conflictos con menciones ya procesadas
    user_pattern = r'(?<!<)@([a-zA-Z0-9_\-\.]+(?:#\d{4})?)(?!>)'
    user_matches = list(re.finditer(user_pattern, processed_content))
    
    # Procesar de atrás hacia adelante para evitar problemas con índices
    for match in reversed(user_matches):
        mention_text = match.group(0)  # @usuario completo
        username_part = match.group(1)  # solo la parte del usuario
        
        # Saltar @everyone y @here
        if username_part.lower() in ['everyone', 'here']:
            continue
            
        # Buscar usuario por nombre o nombre#discriminador
        found_user = None
        
        if '#' in username_part:
            # Formato Usuario#1234
            name, discriminator = username_part.split('#', 1)
            for member in guild.members:
                if member.name.lower() == name.lower() and member.discriminator == discriminator:
                    found_user = member
                    break
        else:
            # Solo nombre de usuario - buscar por display_name o username
            # Priorizar coincidencias exactas
            for member in guild.members:
                if member.display_name.lower() == username_part.lower():
                    found_user = member
                    break
            
            # Si no se encuentra por display_name, buscar por username
            if not found_user:
                for member in guild.members:
                    if member.name.lower() == username_part.lower():
                        found_user = member
                        break
        
        if found_user:
            # Reemplazar usando posiciones específicas para evitar reemplazos múltiples
            start, end = match.span()
            processed_content = processed_content[:start] + f'<@{found_user.id}>' + processed_content[end:]
            logger.info(f"Procesada mención de usuario: {mention_text} -> <@{found_user.id}> ({found_user.display_name})")
    
    # Procesar menciones de canales (#canal)
    # Evitar procesar menciones ya formateadas
    channel_pattern = r'(?<!<)#([a-zA-Z0-9_\-]+)(?!>)'
    channel_matches = list(re.finditer(channel_pattern, processed_content))
    
    # Procesar de atrás hacia adelante
    for match in reversed(channel_matches):
        mention_text = match.group(0)  # #canal completo
        channel_name = match.group(1)  # solo el nombre del canal
        
        # Buscar canal por nombre
        found_channel = None
        for channel in guild.channels:
            if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel, discord.ForumChannel)):
                if channel.name.lower() == channel_name.lower():
                    found_channel = channel
                    break
        
        if found_channel:
            # Reemplazar usando posiciones específicas
            start, end = match.span()
            processed_content = processed_content[:start] + f'<#{found_channel.id}>' + processed_content[end:]
            logger.info(f"Procesada mención de canal: {mention_text} -> <#{found_channel.id}> ({found_channel.name})")
    
    # Procesar menciones de roles (@rol)
    # Solo procesar si no es un usuario ya procesado
    role_pattern = r'(?<!<)@([a-zA-Z0-9_\-\s]+)(?!>)'
    role_matches = list(re.finditer(role_pattern, processed_content))
    
    for match in reversed(role_matches):
        mention_text = match.group(0)  # @rol completo
        role_name = match.group(1).strip()  # solo el nombre del rol
        
        # Saltar @everyone, @here y nombres que parecen usuarios
        if role_name.lower() in ['everyone', 'here'] or '#' in role_name:
            continue
        
        # Buscar rol por nombre
        found_role = None
        for role in guild.roles:
            if role.name.lower() == role_name.lower() and role.name != "@everyone":
                found_role = role
                break
        
        if found_role:
            # Verificar que no sea una mención de usuario ya procesada
            if not re.search(r'<@\d+>', processed_content[match.start():match.end()]):
                start, end = match.span()
                processed_content = processed_content[:start] + f'<@&{found_role.id}>' + processed_content[end:]
                logger.info(f"Procesada mención de rol: {mention_text} -> <@&{found_role.id}> ({found_role.name})")
    
    return processed_content

class SimpleMessageModal(discord.ui.Modal):
    """Modal para enviar un mensaje de texto simple"""
    
    def __init__(self, bot, channel=None):
        super().__init__(title="Mensaje Simple")
        self.bot = bot
        self.target_channel = channel
        
        # Campo para el contenido del mensaje
        self.content_input = discord.ui.TextInput(
            label="Contenido del mensaje",
            placeholder="Escribe aquí el texto de tu mensaje...",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=2000
        )
        self.add_item(self.content_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Procesa el envío del modal"""
        try:
            # Si no hay canal seleccionado, mostrar selector de canal
            if not self.target_channel:
                view = SimpleMessageChannelSelect(self.bot, self.content_input.value)
                await interaction.response.send_message(
                    content="📋 **Selecciona el canal donde enviar el mensaje:**",
                    view=view,
                    ephemeral=True
                )
                return
            
            # Verificar si el canal es válido
            if not isinstance(self.target_channel, discord.TextChannel) and not isinstance(self.target_channel, discord.Thread):
                try:
                    real_channel = interaction.guild.get_channel(self.target_channel.id)
                    if real_channel:
                        self.target_channel = real_channel
                    else:
                        await interaction.response.send_message(
                            content="❌ **Error:** El canal seleccionado no es válido.",
                            ephemeral=True
                        )
                        return
                except Exception as e:
                    logger.error(f"Error obteniendo canal real: {e}")
                    await interaction.response.send_message(
                        content="❌ **Error:** No se pudo acceder al canal seleccionado.",
                        ephemeral=True
                    )
                    return
            
            # Procesar menciones en el contenido
            processed_content = process_mentions(self.content_input.value, interaction.guild)
            
            # Enviar el mensaje simple
            sent_message = await self.target_channel.send(content=processed_content)
            
            # Confirmar al usuario
            await interaction.response.send_message(
                content=f"✅ **Mensaje enviado correctamente al canal {self.target_channel.mention}!**\n[Ir al mensaje]({sent_message.jump_url})",
                ephemeral=True
            )
            
            logger.info(f"Mensaje simple enviado por {interaction.user} al canal {self.target_channel.name} (ID: {sent_message.id})")
            
        except Exception as e:
            logger.error(f"Error enviando mensaje simple: {e}")
            await interaction.response.send_message(
                content=f"❌ **Error al enviar el mensaje:** {str(e)}",
                ephemeral=True
            )

class SimpleMessageChannelSelect(discord.ui.View):
    """Vista para seleccionar un canal para mensaje simple"""
    
    def __init__(self, bot, message_content):
        super().__init__(timeout=60)
        self.bot = bot
        self.message_content = message_content
        
        # Crear selector de canales
        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Selecciona un canal...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news]
        )
        self.channel_select.callback = self.channel_callback
        self.add_item(self.channel_select)
    
    async def channel_callback(self, interaction: discord.Interaction):
        """Callback cuando se selecciona un canal"""
        selected_channel = self.channel_select.values[0]
        
        try:
            # Verificar si el canal es válido
            if not isinstance(selected_channel, discord.TextChannel) and not isinstance(selected_channel, discord.Thread):
                try:
                    real_channel = interaction.guild.get_channel(selected_channel.id)
                    if real_channel:
                        selected_channel = real_channel
                    else:
                        await interaction.response.send_message(
                            content="❌ **Error:** El canal seleccionado no es válido.",
                            ephemeral=True
                        )
                        return
                except Exception as e:
                    logger.error(f"Error obteniendo canal real: {e}")
                    await interaction.response.send_message(
                        content="❌ **Error:** No se pudo acceder al canal seleccionado.",
                        ephemeral=True
                    )
                    return
            
            # Procesar menciones en el contenido
            processed_content = process_mentions(self.message_content, interaction.guild)
            
            # Enviar el mensaje simple
            sent_message = await selected_channel.send(content=processed_content)
            
            # Confirmar al usuario
            await interaction.response.edit_message(
                content=f"✅ **Mensaje enviado correctamente al canal {selected_channel.mention}!**\n[Ir al mensaje]({sent_message.jump_url})",
                view=None
            )
            
            logger.info(f"Mensaje simple enviado por {interaction.user} al canal {selected_channel.name} (ID: {sent_message.id})")
            
        except Exception as e:
            logger.error(f"Error enviando mensaje simple: {e}")
            await interaction.response.send_message(
                content=f"❌ **Error al enviar el mensaje:** {str(e)}",
                ephemeral=True
            )

class MessageTypeSelect(discord.ui.View):
    """Vista para seleccionar el tipo de mensaje"""
    
    def __init__(self, bot, channel=None):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.bot = bot
        self.channel = channel
    
    @discord.ui.button(label="📝 Mensaje Simple", style=discord.ButtonStyle.primary)
    async def simple_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Crea un mensaje de texto simple"""
        modal = SimpleMessageModal(self.bot, self.channel)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🎨 Mensaje con Embed", style=discord.ButtonStyle.success)
    async def editable_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Crea un mensaje con embed que se puede editar después"""
        modal = MessageModal(self.bot, self.channel, is_editable=True)
        await interaction.response.send_modal(modal)

class MessageModal(discord.ui.Modal):
    """Modal para configurar un mensaje personalizado"""
    
    def __init__(self, bot, channel=None, is_editable=False):
        super().__init__(title="Configurar Mensaje")
        self.bot = bot
        self.target_channel = channel
        self.is_editable = is_editable
        
        # Campos del modal
        self.title_input = discord.ui.TextInput(
            label="Título del Embed",
            placeholder="Ingresa el título del mensaje...",
            required=False,
            max_length=256
        )
        self.add_item(self.title_input)
        
        self.description_input = discord.ui.TextInput(
            label="Descripción",
            placeholder="Ingresa la descripción del mensaje...",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=4000
        )
        self.add_item(self.description_input)
        
        self.color_input = discord.ui.TextInput(
            label="Color (hex)",
            placeholder="Ejemplo: #5865F2 o 5865F2",
            required=False,
            max_length=7
        )
        self.add_item(self.color_input)
        
        self.image_url_input = discord.ui.TextInput(
            label="URL de Imagen (opcional)",
            placeholder="https://ejemplo.com/imagen.png",
            required=False
        )
        self.add_item(self.image_url_input)
        
        self.footer_input = discord.ui.TextInput(
            label="Texto de Footer (opcional)",
            placeholder="Texto que aparecerá en el pie del mensaje",
            required=False,
            max_length=2048
        )
        self.add_item(self.footer_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Procesa el envío del modal"""
        try:
            # Crear el embed con los datos proporcionados
            embed = discord.Embed()
            
            # Título (procesar menciones)
            if self.title_input.value:
                embed.title = process_mentions(self.title_input.value, interaction.guild)
            
            # Descripción (procesar menciones)
            if self.description_input.value:
                embed.description = process_mentions(self.description_input.value, interaction.guild)
            
            # Color
            if self.color_input.value:
                color_str = self.color_input.value.strip().replace('#', '')
                try:
                    color_int = int(color_str, 16)
                    embed.color = color_int
                except ValueError:
                    embed.color = 0x5865F2  # Color por defecto (azul Discord)
            else:
                embed.color = 0x5865F2  # Color por defecto
            
            # Imagen
            if self.image_url_input.value:
                embed.set_image(url=self.image_url_input.value)
            
            # Footer (procesar menciones)
            if self.footer_input.value:
                embed.set_footer(text=process_mentions(self.footer_input.value, interaction.guild))
            
            # Mostrar vista previa y opciones adicionales
            view = MessagePreviewView(self.bot, embed, self.target_channel, is_editable=self.is_editable)
            
            # Añadir indicador si es un mensaje editable
            content_text = "✅ **Vista previa del mensaje:**\n*Usa los botones para añadir campos, botones o enviar el mensaje.*"
            if self.is_editable:
                content_text += "\n\n🔄 **Mensaje Editable:** Este mensaje podrá ser editado después de enviarlo."
            
            await interaction.response.send_message(
                content=content_text,
                embed=embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error procesando modal de mensaje: {e}")
            await interaction.response.send_message(
                content=f"❌ **Error al crear el mensaje:** {str(e)}",
                ephemeral=True
            )

class AddFieldModal(discord.ui.Modal):
    """Modal para añadir un campo al embed"""
    
    def __init__(self, parent_view):
        super().__init__(title="Añadir Campo")
        self.parent_view = parent_view
        
        self.field_name = discord.ui.TextInput(
            label="Nombre del Campo",
            placeholder="Título del campo",
            required=True,
            max_length=256
        )
        self.add_item(self.field_name)
        
        self.field_value = discord.ui.TextInput(
            label="Valor del Campo",
            placeholder="Contenido del campo",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1024
        )
        self.add_item(self.field_value)
        
        self.inline = discord.ui.TextInput(
            label="¿Inline? (si/no)",
            placeholder="si o no",
            required=True,
            max_length=3,
            default="si"
        )
        self.add_item(self.inline)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Procesa el envío del modal para añadir un campo"""
        try:
            # Determinar si el campo es inline
            is_inline = self.inline.value.lower() in ["si", "sí", "yes", "y", "true"]
            
            # Procesar menciones en el nombre y valor del campo
            processed_name = process_mentions(self.field_name.value, interaction.guild)
            processed_value = process_mentions(self.field_value.value, interaction.guild)
            
            # Añadir el campo al embed
            self.parent_view.embed.add_field(
                name=processed_name,
                value=processed_value,
                inline=is_inline
            )
            
            # Actualizar la vista previa
            await interaction.response.edit_message(
                content="✅ **Vista previa del mensaje actualizada:**\n*Campo añadido correctamente.*",
                embed=self.parent_view.embed,
                view=self.parent_view
            )
            
        except Exception as e:
            logger.error(f"Error añadiendo campo: {e}")
            await interaction.response.send_message(
                content=f"❌ **Error al añadir el campo:** {str(e)}",
                ephemeral=True
            )

class AddButtonModal(discord.ui.Modal):
    """Modal para añadir un botón al mensaje"""
    
    def __init__(self, parent_view):
        super().__init__(title="Añadir Botón")
        self.parent_view = parent_view
        
        self.button_label = discord.ui.TextInput(
            label="Texto del Botón",
            placeholder="Haz clic aquí",
            required=True,
            max_length=80
        )
        self.add_item(self.button_label)
        
        self.button_url = discord.ui.TextInput(
            label="URL del Botón",
            placeholder="https://ejemplo.com",
            required=True
        )
        self.add_item(self.button_url)
        
        self.button_style = discord.ui.TextInput(
            label="Estilo (1-5)",
            placeholder="1=Azul, 2=Gris, 3=Verde, 4=Rojo, 5=Link",
            required=True,
            max_length=1,
            default="5"
        )
        self.add_item(self.button_style)
        
        self.button_emoji = discord.ui.TextInput(
            label="Emoji (opcional)",
            placeholder="🔗",
            required=False,
            max_length=10
        )
        self.add_item(self.button_emoji)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Procesa el envío del modal para añadir un botón"""
        try:
            # Mapear el estilo del botón
            style_map = {
                "1": discord.ButtonStyle.primary,
                "2": discord.ButtonStyle.secondary,
                "3": discord.ButtonStyle.success,
                "4": discord.ButtonStyle.danger,
                "5": discord.ButtonStyle.link
            }
            
            style = style_map.get(self.button_style.value, discord.ButtonStyle.link)
            
            # Añadir el botón a la lista de botones
            self.parent_view.buttons.append({
                "label": self.button_label.value,
                "url": self.button_url.value,
                "style": style.value,
                "emoji": self.button_emoji.value if self.button_emoji.value else None
            })
            
            # Actualizar la vista previa con los botones
            message_view = MessagePreviewView(
                self.parent_view.bot,
                self.parent_view.embed,
                self.parent_view.target_channel,
                self.parent_view.buttons
            )
            
            await interaction.response.edit_message(
                content="✅ **Vista previa del mensaje actualizada:**\n*Botón añadido correctamente.*",
                embed=self.parent_view.embed,
                view=message_view
            )
            
        except Exception as e:
            logger.error(f"Error añadiendo botón: {e}")
            await interaction.response.send_message(
                content=f"❌ **Error al añadir el botón:** {str(e)}",
                ephemeral=True
            )

class MessagePreviewView(discord.ui.View):
    """Vista para previsualizar y editar el mensaje antes de enviarlo"""
    
    def __init__(self, bot, embed, target_channel=None, buttons=None, is_editable=False):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.bot = bot
        self.embed = embed
        self.target_channel = target_channel
        self.buttons = buttons or []
        self.is_editable = is_editable
        self.message_id = None  # Para guardar el ID del mensaje si es editable
        
        # Añadir botones de la lista a la vista previa
        self._add_message_buttons()
    
    def _add_message_buttons(self):
        """Añade los botones configurados a la vista previa"""
        # Primero eliminar los botones de mensaje existentes (no los de control)
        control_buttons = []
        for item in self.children:
            if isinstance(item, discord.ui.Button) and not item.url:
                control_buttons.append(item)
        
        self.clear_items()
        
        # Añadir los botones de mensaje
        for btn_data in self.buttons:
            style = discord.ButtonStyle(btn_data["style"])
            button = discord.ui.Button(
                style=style,
                label=btn_data["label"],
                url=btn_data["url"],
                emoji=btn_data["emoji"]
            )
            self.add_item(button)
        
        # Volver a añadir los botones de control
        for btn in control_buttons:
            self.add_item(btn)
    
    @discord.ui.button(label="➕ Añadir Campo", style=discord.ButtonStyle.secondary)
    async def add_field_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Abre el modal para añadir un campo al embed"""
        modal = AddFieldModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔗 Añadir Botón", style=discord.ButtonStyle.secondary)
    async def add_button_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Abre el modal para añadir un botón al mensaje"""
        modal = AddButtonModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🗑️ Limpiar Campos", style=discord.ButtonStyle.danger)
    async def clear_fields_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Elimina todos los campos del embed"""
        self.embed.clear_fields()
        await interaction.response.edit_message(
            content="✅ **Vista previa del mensaje actualizada:**\n*Campos eliminados correctamente.*",
            embed=self.embed,
            view=self
        )
    
    @discord.ui.button(label="📝 Editar Mensaje", style=discord.ButtonStyle.primary)
    async def edit_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Vuelve a abrir el modal para editar el mensaje"""
        modal = MessageModal(self.bot, self.target_channel)
        
        # Pre-llenar con los valores actuales
        if self.embed.title:
            modal.title_input.default = self.embed.title
        
        if self.embed.description:
            modal.description_input.default = self.embed.description
        
        if self.embed.color:
            modal.color_input.default = f"{self.embed.color.value:X}"
        
        if self.embed.image and self.embed.image.url:
            modal.image_url_input.default = self.embed.image.url
        
        if self.embed.footer and self.embed.footer.text:
            modal.footer_input.default = self.embed.footer.text
        
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📋 Seleccionar Canal", style=discord.ButtonStyle.primary)
    async def select_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Abre un selector de canal para elegir dónde enviar el mensaje"""
        # Crear una vista con un selector de canal
        view = ChannelSelectView(self)
        await interaction.response.edit_message(
            content="📋 **Selecciona el canal donde enviar el mensaje:**",
            view=view
        )
    
    @discord.ui.button(label="✅ Enviar Mensaje", style=discord.ButtonStyle.success)
    async def send_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Envía el mensaje al canal seleccionado"""
        if not self.target_channel:
            await interaction.response.send_message(
                content="❌ **Error:** Debes seleccionar un canal primero.",
                ephemeral=True
            )
            return
        
        try:
            # Verificar si el canal es un objeto TextChannel válido
            if not isinstance(self.target_channel, discord.TextChannel) and not isinstance(self.target_channel, discord.Thread):
                # Intentar obtener el canal real
                try:
                    real_channel = interaction.guild.get_channel(self.target_channel.id)
                    if real_channel:
                        self.target_channel = real_channel
                    else:
                        await interaction.response.send_message(
                            content=f"❌ **Error:** El canal seleccionado no es válido o no se puede acceder a él.",
                            ephemeral=True
                        )
                        return
                except Exception as e:
                    logger.error(f"Error obteniendo canal real: {e}")
                    await interaction.response.send_message(
                        content=f"❌ **Error:** No se pudo acceder al canal seleccionado. Por favor, selecciona otro canal.",
                        ephemeral=True
                    )
                    return
            
            # Crear una vista con los botones configurados para el mensaje final
            message_buttons = discord.ui.View(timeout=None)
            for btn_data in self.buttons:
                style = discord.ButtonStyle(btn_data["style"])
                button = discord.ui.Button(
                    style=style,
                    label=btn_data["label"],
                    url=btn_data["url"],
                    emoji=btn_data["emoji"]
                )
                message_buttons.add_item(button)
            
            # Si es un mensaje editable, añadir un botón para editar
            if self.is_editable:
                # Guardar los datos del mensaje para edición futura
                message_data = {
                    "embed": self.embed.to_dict(),
                    "buttons": self.buttons,
                    "author_id": interaction.user.id,
                    "is_editable": True
                }
                
                # Crear un ID único para este mensaje
                import uuid
                message_id = str(uuid.uuid4())
                
                # Guardar en la base de datos o en un archivo
                # Por ahora, solo guardamos el ID para demostración
                self.message_id = message_id
                
                # Añadir un botón de edición al mensaje
                edit_button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label="🔄 Editar Mensaje",
                    custom_id=f"edit_message:{message_id}"
                )
                message_buttons.add_item(edit_button)
            
            # Enviar el mensaje al canal
            sent_message = await self.target_channel.send(embed=self.embed, view=message_buttons if (self.buttons or self.is_editable) else None)
            
            # Mensaje de confirmación
            confirmation_content = f"✅ **Mensaje enviado correctamente al canal {self.target_channel.mention}!**\n[Ir al mensaje]({sent_message.jump_url})"
            
            if self.is_editable:
                confirmation_content += f"\n\n🔄 **Mensaje Editable:** Este mensaje puede ser editado usando el botón 'Editar Mensaje'."
                # Aquí se podría guardar la relación entre message_id y sent_message.id en una base de datos
            
            # Confirmar al usuario
            await interaction.response.edit_message(
                content=confirmation_content,
                embed=None,
                view=None
            )
            
            logger.info(f"Mensaje enviado por {interaction.user} al canal {self.target_channel.name} (ID: {sent_message.id}, Editable: {self.is_editable})")
            
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")
            await interaction.response.send_message(
                content=f"❌ **Error al enviar el mensaje:** {str(e)}",
                ephemeral=True
            )

class ChannelSelectView(discord.ui.View):
    """Vista para seleccionar un canal"""
    
    def __init__(self, parent_view):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        
        # Crear selector de canales
        self.channel_select = discord.ui.ChannelSelect(
            placeholder="Selecciona un canal...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news]
        )
        self.channel_select.callback = self.channel_callback
        self.add_item(self.channel_select)
    
    async def channel_callback(self, interaction: discord.Interaction):
        """Callback cuando se selecciona un canal"""
        selected_channel = self.channel_select.values[0]
        self.parent_view.target_channel = selected_channel
        
        # Volver a la vista previa
        await interaction.response.edit_message(
            content=f"✅ **Canal seleccionado:** {selected_channel.mention}\n*Continúa configurando tu mensaje o envíalo.*",
            embed=self.parent_view.embed,
            view=self.parent_view
        )

def setup_message_command(bot):
    """Configura el comando de envío de mensajes"""
    
    @bot.tree.command(
        name="message",
        description="Envía un mensaje personalizado con embeds, botones y más"
    )
    async def message_command(interaction: discord.Interaction, channel: Optional[discord.abc.GuildChannel] = None):
        """Comando para enviar un mensaje personalizado"""
        logger.info(f"📨 [COMANDO] message ejecutado por {interaction.user}")
        
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
            # Mostrar opciones de tipo de mensaje
            embed = discord.Embed(
                title="📨 Crear Mensaje Personalizado",
                description="Selecciona el tipo de mensaje que deseas crear:",
                color=0x5865F2
            )
            
            embed.add_field(
                name="📝 Mensaje Simple",
                value="Un mensaje de texto simple sin formato especial.",
                inline=False
            )
            
            embed.add_field(
                name="🎨 Mensaje con Embed",
                value="Un mensaje con formato enriquecido, campos, colores, imágenes y botón para editarlo después.",
                inline=False
            )
            
            embed.add_field(
                name="🏷️ Menciones Soportadas",
                value="• **Usuarios:** `@usuario` o `@Usuario#1234`\n• **Canales:** `#canal`\n• **Roles:** `@rol`\n• **Especiales:** `@everyone`, `@here`",
                inline=False
            )
            
            embed.set_footer(text="💡 Tip: Puedes usar menciones en cualquier campo de texto del mensaje")
            
            # Crear vista para seleccionar el tipo de mensaje
            view = MessageTypeSelect(bot, channel)
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error en message: {e}")
            await interaction.response.send_message(
                content=f"❌ **Error iniciando el comando:** {str(e)}",
                ephemeral=True
            )
    
    # El comando con prefijo se registra directamente en la función load_commands

class EditMessageView(discord.ui.View):
    """Vista para editar un mensaje existente"""
    
    def __init__(self, bot, message_id, original_message):
        super().__init__(timeout=300)
        self.bot = bot
        self.message_id = message_id
        self.original_message = original_message
    
    @discord.ui.button(label="📝 Editar Contenido", style=discord.ButtonStyle.primary)
    async def edit_content_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Abre el modal para editar el contenido del mensaje"""
        # Aquí se abriría un modal similar al MessageModal pero pre-llenado con los datos actuales
        # Por simplicidad, solo mostraremos un mensaje
        await interaction.response.send_message(
            content="Esta funcionalidad permitiría editar el contenido del mensaje. En una implementación completa, se abriría un modal con los datos actuales.",
            ephemeral=True
        )
    
    @discord.ui.button(label="➕ Añadir Campo", style=discord.ButtonStyle.secondary)
    async def add_field_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Añade un campo al mensaje existente"""
        await interaction.response.send_message(
            content="Esta funcionalidad permitiría añadir un campo al mensaje existente.",
            ephemeral=True
        )
    
    @discord.ui.button(label="🔄 Actualizar Mensaje", style=discord.ButtonStyle.success)
    async def update_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Actualiza el mensaje con los cambios"""
        await interaction.response.send_message(
            content="Esta funcionalidad actualizaría el mensaje con los cambios realizados.",
            ephemeral=True
        )

async def handle_edit_button(bot, interaction):
    """Maneja la interacción con el botón de edición de mensajes"""
    # Extraer el ID del mensaje del custom_id
    custom_id = interaction.data.get("custom_id", "")
    if custom_id.startswith("edit_message:"):
        message_id = custom_id.split(":", 1)[1]
        
        # En una implementación completa, aquí se buscaría el mensaje en la base de datos
        # Por ahora, solo mostraremos una interfaz de edición básica
        
        # Verificar que el usuario sea el autor original o un administrador
        if interaction.user.guild_permissions.administrator:
            # Mostrar opciones de edición
            embed = discord.Embed(
                title="🔄 Editar Mensaje",
                description="Selecciona qué deseas modificar en este mensaje:",
                color=0x5865F2
            )
            
            view = EditMessageView(bot, message_id, interaction.message)
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                content="❌ **Error:** Solo los administradores pueden editar este mensaje.",
                ephemeral=True
            )
        
        return True
    
    return False

def load_commands(bot):
    """Carga todos los comandos de este módulo"""
    # Ejecutar la función de configuración directamente
    setup_message_command(bot)
    
    # Registrar el comando con prefijo directamente
    @bot.command(name='message')
    async def prefix_message(ctx, channel: Optional[discord.TextChannel] = None):
        """Comando con prefijo para enviar un mensaje personalizado"""
        logger.info(f"📨 [PREFIJO] message ejecutado por {ctx.author}")
        
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
            # Responder con instrucciones para usar el slash command
            embed = discord.Embed(
                title="📨 Enviar Mensaje Personalizado",
                description="Este comando funciona mejor como slash command para acceder a todas las funcionalidades.",
                color=0x5865F2
            )
            embed.add_field(
                name="Uso recomendado:",
                value="Usa `/message` para abrir el configurador de mensajes completo.",
                inline=False
            )
            embed.add_field(
                name="Alternativa:",
                value="Selecciona el tipo de mensaje que deseas crear:",
                inline=False
            )
            
            embed.add_field(
                name="📝 Mensaje Simple",
                value="Un mensaje de texto simple sin formato especial.",
                inline=True
            )
            
            embed.add_field(
                name="🎨 Mensaje con Embed",
                value="Un mensaje con formato enriquecido, campos, colores, imágenes y botón para editarlo después.",
                inline=True
            )
            
            embed.add_field(
                name="🏷️ Menciones Soportadas",
                value="• **Usuarios:** `@usuario` o `@Usuario#1234`\n• **Canales:** `#canal`\n• **Roles:** `@rol`\n• **Especiales:** `@everyone`, `@here`",
                inline=False
            )
            
            embed.set_footer(text="💡 Tip: Puedes usar menciones en cualquier campo de texto del mensaje")
            
            # Como no podemos abrir un modal desde un comando con prefijo,
            # creamos botones que el usuario puede presionar
            view = discord.ui.View()
            
            # Botón para mensaje simple
            simple_button = discord.ui.Button(label="📝 Mensaje Simple", style=discord.ButtonStyle.primary)
            
            async def simple_button_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Solo el autor del comando puede usar este botón.", ephemeral=True)
                    return
                
                modal = SimpleMessageModal(bot, channel)
                await interaction.response.send_modal(modal)
            
            simple_button.callback = simple_button_callback
            view.add_item(simple_button)
            
            # Botón para mensaje con embed
            embed_button = discord.ui.Button(label="🎨 Mensaje con Embed", style=discord.ButtonStyle.success)
            
            async def embed_button_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Solo el autor del comando puede usar este botón.", ephemeral=True)
                    return
                
                modal = MessageModal(bot, channel, is_editable=True)
                await interaction.response.send_modal(modal)
            
            embed_button.callback = embed_button_callback
            view.add_item(embed_button)
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            logger.error(f"Error en prefix_message: {e}")
            await ctx.send(f"❌ **Error iniciando el comando:** {str(e)}")
    
    # Añadir listener para botones de edición
    # Nota: No usamos @bot.event para evitar sobrescribir otros listeners
    # En su lugar, añadimos un listener específico
    async def message_interaction_handler(interaction):
        if interaction.type == discord.InteractionType.component:
            # Verificar si es un botón de edición
            try:
                if await handle_edit_button(bot, interaction):
                    return  # Si se manejó como botón de edición, no continuar
            except Exception as e:
                logger.error(f"Error manejando botón de edición: {e}")
    
    # Añadir el listener sin sobrescribir otros
    bot.add_listener(message_interaction_handler, 'on_interaction')
    
    logger.info("✅ Comando message cargado correctamente")
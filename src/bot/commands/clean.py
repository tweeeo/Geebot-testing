import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from typing import Optional

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

def has_manage_messages_or_staff(user: discord.Member) -> bool:
    """
    Verifica si un usuario tiene permisos para gestionar mensajes o es staff
    """
    return user.guild_permissions.manage_messages or has_staff_permissions(user)

class CleanConfirmationView(discord.ui.View):
    """Vista para confirmar la limpieza de mensajes"""
    
    def __init__(self, channel, amount=10):
        super().__init__(timeout=30)  # 30 segundos de timeout
        self.channel = channel
        self.amount = amount
    
    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirma la eliminación de mensajes"""
        try:
            # Verificar permisos
            if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
                await interaction.response.send_message(
                    content="❌ **Error:** No tengo permisos para eliminar mensajes en este canal.",
                    ephemeral=True
                )
                return
            
            # Deshabilitar botones
            for item in self.children:
                item.disabled = True
            
            # Actualizar mensaje con estado "en progreso"
            await interaction.response.edit_message(
                content=f"🧹 **Limpiando mensajes...**\nEliminando {self.amount} mensajes en {self.channel.mention}",
                view=self
            )
            
            # Eliminar mensajes
            deleted = await self.channel.purge(limit=self.amount)
            
            # Enviar confirmación
            await interaction.edit_original_response(
                content=f"✅ **Limpieza completada**\nSe eliminaron {len(deleted)} mensajes en {self.channel.mention}."
            )
            
            logger.info(f"Limpieza completada por {interaction.user} en {self.channel.name}: {len(deleted)} mensajes eliminados")
            
        except discord.Forbidden:
            await interaction.edit_original_response(
                content="❌ **Error:** No tengo permisos para eliminar mensajes en este canal."
            )
        except discord.HTTPException as e:
            await interaction.edit_original_response(
                content=f"❌ **Error:** No se pudieron eliminar algunos mensajes. Error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error en clean: {e}")
            await interaction.edit_original_response(
                content=f"❌ **Error inesperado:** {str(e)}"
            )
    
    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancela la eliminación de mensajes"""
        # Deshabilitar botones
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(
            content="❌ **Operación cancelada**\nNo se eliminó ningún mensaje.",
            view=self
        )
    
    async def on_timeout(self):
        """Maneja el timeout de la vista"""
        # Deshabilitar botones cuando expire el timeout
        for item in self.children:
            item.disabled = True

def setup_clean_command(bot):
    """Configura el comando de limpieza de mensajes"""
    
    @bot.tree.command(
        name="clean",
        description="Elimina los últimos mensajes del canal actual"
    )
    @app_commands.describe(amount="Cantidad de mensajes a eliminar (por defecto: 10, máximo: 100)")
    async def clean_command(interaction: discord.Interaction, amount: Optional[int] = 10):
        """Comando para eliminar mensajes"""
        logger.info(f"🧹 [COMANDO] clean ejecutado por {interaction.user} - Cantidad: {amount}")
        
        # Verificar permisos
        if not has_manage_messages_or_staff(interaction.user):
            embed = discord.Embed(
                title="❌ Sin Permisos",
                description="Este comando requiere permisos para gestionar mensajes o ser administrador/staff.",
                color=0xf04747
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Validar cantidad
            if amount < 1:
                await interaction.response.send_message(
                    content="❌ **Error:** La cantidad debe ser al menos 1.",
                    ephemeral=True
                )
                return
            
            if amount > 100:
                await interaction.response.send_message(
                    content="❌ **Error:** La cantidad máxima es 100 mensajes por operación.",
                    ephemeral=True
                )
                return
            
            # Verificar permisos
            if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
                await interaction.response.send_message(
                    content="❌ **Error:** No tengo permisos para eliminar mensajes en este canal.",
                    ephemeral=True
                )
                return
            
            # Mostrar confirmación
            view = CleanConfirmationView(interaction.channel, amount)
            
            await interaction.response.send_message(
                content=f"⚠️ **Confirmación requerida**\n¿Estás seguro de que quieres eliminar los últimos {amount} mensajes en {interaction.channel.mention}?",
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error en clean: {e}")
            await interaction.response.send_message(
                content=f"❌ **Error iniciando el comando:** {str(e)}",
                ephemeral=True
            )
    
    # El comando con prefijo se registra directamente en la función load_commands

def load_commands(bot):
    """Carga todos los comandos de este módulo"""
    # Ejecutar la función de configuración directamente
    setup_clean_command(bot)
    
    # También registrar el comando con prefijo directamente
    @bot.command(name='clean')
    async def prefix_clean(ctx, amount: int = 10):
        """Comando con prefijo para eliminar mensajes"""
        logger.info(f"🧹 [PREFIJO] clean ejecutado por {ctx.author} - Cantidad: {amount}")
        
        # Verificar permisos
        if not has_manage_messages_or_staff(ctx.author):
            embed = discord.Embed(
                title="❌ Sin Permisos",
                description="Este comando requiere permisos para gestionar mensajes o ser administrador/staff.",
                color=0xf04747
            )
            await ctx.send(embed=embed)
            return
        
        try:
            # Validar cantidad
            if amount < 1:
                await ctx.send("❌ **Error:** La cantidad debe ser al menos 1.")
                return
            
            if amount > 100:
                await ctx.send("❌ **Error:** La cantidad máxima es 100 mensajes por operación.")
                return
            
            # Verificar permisos
            if not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
                await ctx.send("❌ **Error:** No tengo permisos para eliminar mensajes en este canal.")
                return
            
            # Mostrar confirmación
            embed = discord.Embed(
                title="⚠️ Confirmación de Limpieza",
                description=f"¿Estás seguro de que quieres eliminar los últimos {amount} mensajes en {ctx.channel.mention}?",
                color=0xffa500
            )
            
            message = await ctx.send(embed=embed)
            
            # Añadir reacciones para confirmar/cancelar
            await message.add_reaction("✅")
            await message.add_reaction("❌")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == message.id
            
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
                
                if str(reaction.emoji) == "✅":
                    # Eliminar mensaje de confirmación
                    await message.delete()
                    
                    # Eliminar mensajes
                    deleted = await ctx.channel.purge(limit=amount + 1)  # +1 para incluir el comando
                    
                    # Enviar confirmación
                    confirm_msg = await ctx.send(f"✅ **Limpieza completada**\nSe eliminaron {len(deleted) - 1} mensajes.")
                    
                    # Eliminar mensaje de confirmación después de 5 segundos
                    await asyncio.sleep(5)
                    await confirm_msg.delete()
                    
                    logger.info(f"Limpieza completada por {ctx.author} en {ctx.channel.name}: {len(deleted) - 1} mensajes eliminados")
                    
                else:
                    # Cancelar
                    await message.edit(content="❌ **Operación cancelada**\nNo se eliminó ningún mensaje.", embed=None)
                    
            except asyncio.TimeoutError:
                await message.edit(content="⏱️ **Tiempo agotado**\nNo se eliminó ningún mensaje.", embed=None)
                
        except discord.Forbidden:
            await ctx.send("❌ **Error:** No tengo permisos para eliminar mensajes en este canal.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ **Error:** No se pudieron eliminar algunos mensajes. Error: {str(e)}")
        except Exception as e:
            logger.error(f"Error en clean: {e}")
            await ctx.send(f"❌ **Error inesperado:** {str(e)}")
    
    logger.info("✅ Comando clean cargado correctamente")
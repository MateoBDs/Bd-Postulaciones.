import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# --- Configuración del Bot ---
TOKEN = os.getenv("DISCORD_TOKEN")  # Obtener el token de las variables de entorno
APPLICATIONS_CHANNEL_ID = int(os.getenv("APPLICATIONS_CHANNEL_ID"))  # ID del canal donde se publicará el mensaje de postulación (.setup)
CLOSED_APPLICATIONS_REDIRECT_CHANNEL_ID = int(os.getenv("CLOSED_APPLICATIONS_REDIRECT_CHANNEL_ID", "1515360850503012402")) # Canal al que se redirige si están cerradas
STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID")) # ID del rol de Staff que puede ver y cerrar los tickets

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

bot = commands.Bot(command_prefix=".", intents=intents)

# Estado de las postulaciones
applications_open = False
setup_message_id = None

# Preguntas de postulación
APPLICATION_QUESTIONS = [
    "¿Cuál es tu nombre o apodo?", "¿Cuál es tu edad?", "¿Cuál es tu usuario de Discord?",
    "¿Desde qué país eres?", "¿En qué zona horaria te encuentras?", "¿Cuánto tiempo llevas en el servidor?",
    "¿Por qué quieres formar parte del staff?", "¿Qué cargo te gustaría ocupar?",
    "¿Tienes experiencia previa como staff?", "¿En qué servidores has sido staff?",
    "¿Cuántas horas al día puedes dedicar al servidor?", "¿Cuáles son tus puntos fuertes?",
    "¿Cuáles son tus puntos débiles?", "¿Cómo actuarías ante un usuario tóxico?",
    "¿Qué harías si dos usuarios están discutiendo?", "¿Qué harías si un miembro incumple las normas repetidamente?",
    "¿Cómo reaccionarías ante una crítica hacia el staff?", "¿Qué aportarías al equipo que otros no aporten?",
    "¿Sabes utilizar bots de moderación y tickets?", "¿Aceptas seguir las normas y decisiones del equipo?",
    "¿Hay algo más que quieras añadir sobre ti?"
]

# --- Vistas ---

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cerrar Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        # Verificar si el usuario tiene el rol de staff o es admin
        is_staff = any(role.id == STAFF_ROLE_ID for role in interaction.user.roles)
        if not is_staff and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Solo el Staff puede cerrar este ticket.", ephemeral=True)
            return

        await interaction.response.send_message("Cerrando el ticket en 5 segundos...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class ApplicationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Postularse para Staff", style=discord.ButtonStyle.green, custom_id="apply_button")
    async def apply_button_callback(self, interaction: discord.Interaction, button: Button):
        global applications_open

        if not applications_open:
            redirect_channel = bot.get_channel(CLOSED_APPLICATIONS_REDIRECT_CHANNEL_ID)
            mention = redirect_channel.mention if redirect_channel else f"<#{CLOSED_APPLICATIONS_REDIRECT_CHANNEL_ID}>"
            await interaction.response.send_message(f"Las postulaciones están cerradas. Consulta {mention}.", ephemeral=True)
            return

        guild = interaction.guild
        member = interaction.user

        # Evitar duplicados
        channel_name = f'postu-{member.name.lower().replace(" ", "-")}'
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.response.send_message("Ya tienes un canal de postulación abierto.", ephemeral=True)
            return

        # Permisos: El usuario y el Staff ven el canal
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True)
        }
        
        staff_role = guild.get_role(STAFF_ROLE_ID)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)
        await interaction.response.send_message(f"Canal creado: {ticket_channel.mention}", ephemeral=True)

        await ticket_channel.send(f"¡Hola {member.mention}! Responde a las siguientes preguntas para completar tu postulación.")

        answers = {}
        for i, question in enumerate(APPLICATION_QUESTIONS):
            await ticket_channel.send(f"**{i+1}/{len(APPLICATION_QUESTIONS)}:** {question}")
            
            def check(m):
                return m.author == member and m.channel == ticket_channel

            try:
                msg = await bot.wait_for("message", check=check, timeout=600) # 10 min por respuesta
                answers[question] = msg.content
            except asyncio.TimeoutError:
                await ticket_channel.send("Tiempo agotado. El canal se cerrará.")
                await asyncio.sleep(5)
                await ticket_channel.delete()
                return

        # Resumen final en el mismo canal
        embed = discord.Embed(title=f"Resumen de Postulación: {member.display_name}", color=discord.Color.gold())
        for q, a in answers.items():
            # Dividir si la respuesta es muy larga para evitar errores de Discord
            val = (a[:1020] + "...") if len(a) > 1024 else a
            embed.add_field(name=q, value=val, inline=False)

        await ticket_channel.send(embed=embed)
        await ticket_channel.send("✅ **Postulación completada.** El Staff revisará tus respuestas aquí mismo. No cierres este canal.", view=CloseTicketView())

# --- Comandos ---

@bot.event
async def on_ready():
    bot.add_view(ApplicationView())
    bot.add_view(CloseTicketView())
    print(f"Bot listo: {bot.user}")

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    global setup_message_id
    await ctx.message.delete()

   embed = discord.Embed(
    title="📋 POSTULACIÓN OFICIAL",
    description=(
        "**¡Gracias por tu interés en formar parte de nuestro equipo!**\n\n"
        "Antes de comenzar, te recomendamos leer cada pregunta con atención y responder de manera clara, sincera y profesional. "
        "Tu solicitud será evaluada por el equipo administrativo y la decisión se basará en la calidad de tus respuestas, experiencia y compromiso con la comunidad.\n\n"
        "📌 **Requisitos Mínimos**\n\n"
        "• Tener entre **12 y 13 años o más**.\n"
        "• Contar con **micrófono** y dispositivos para realizar grabaciones.\n"
        "• Tener una buena disponibilidad horaria.\n"
        "• Demostrar madurez, humildad y respeto.\n"
        "• Mantener una buena ortografía y redacción.\n"
        "• Ser activo dentro del servidor y de Discord.\n\n"
        "**Buscamos personas responsables, activas y comprometidas**, capaces de contribuir al crecimiento y bienestar de la comunidad."
    ),
    color=discord.Color.blue()
)

    embed.set_footer(
        text="BD Postulaciones • Sistema automático de Staff • Estado: " +
        ("Abiertas" if applications_open else "Cerradas")
    )

    view = ApplicationView()

    if not applications_open:
        view.children[0].disabled = True
        view.children[0].label = "Cerradas"

    msg = await ctx.send(embed=embed, view=view)
    setup_message_id = msg.id

@bot.command(name="abrir-p")
@commands.has_permissions(administrator=True)
async def abrir(ctx):
    global applications_open
    applications_open = True
    await ctx.send("Postulaciones abiertas.", delete_after=5)
    if setup_message_id:
        channel = bot.get_channel(APPLICATIONS_CHANNEL_ID)
        if channel:
            msg = await channel.fetch_message(setup_message_id)
            embed = msg.embeds[0]
            embed.set_footer(text="Estado: Abiertas")
            view = ApplicationView()
            await msg.edit(embed=embed, view=view)

@bot.command(name="cerrar-p")
@commands.has_permissions(administrator=True)
async def cerrar(ctx):
    global applications_open
    applications_open = False
    await ctx.send("Postulaciones cerradas.", delete_after=5)
    if setup_message_id:
        channel = bot.get_channel(APPLICATIONS_CHANNEL_ID)
        if channel:
            msg = await channel.fetch_message(setup_message_id)
            embed = msg.embeds[0]
            embed.set_footer(text="Estado: Cerradas")
            view = ApplicationView()
            view.children[0].disabled = True
            view.children[0].label = "Cerradas"
            await msg.edit(embed=embed, view=view)

# Iniciar el bot
bot.run(TOKEN)

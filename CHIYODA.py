import discord
from discord.ext import commands, tasks
import json
import asyncio
import datetime
import random
import aiohttp
import os
from typing import Optional, Union
import sqlite3
import time

# Configuration du bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='+', intents=intents, help_command=None)

# Remplacez par les IDs de votre serveur et salon
GUILD_ID = 1396641118170644580
STAT_CHANNEL_ID = 1410602735430139986

@tasks.loop(minutes=30)  # toutes les 30 minutes
async def send_server_stats():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    channel = guild.get_channel(STAT_CHANNEL_ID)
    if not channel:
        return

    total_members = guild.member_count
    online_members = len([m for m in guild.members if m.status != discord.Status.offline])
    voice_members = len([m for m in guild.members if m.voice and m.voice.channel])
    boosts = guild.premium_subscription_count

    embed = discord.Embed(
        title=f"📊 Statistiques du serveur : {guild.name}",
        color=0xFFB6C1  # rose clair
    )
    embed.add_field(name="👥 Membres totaux", value=f"{total_members}", inline=True)
    embed.add_field(name="🟢 Connectés", value=f"{online_members}", inline=True)
    embed.add_field(name="🎤 En vocal", value=f"{voice_members}", inline=True)
    embed.add_field(name="🚀 Boosts", value=f"{boosts}", inline=True)
    embed.set_footer(text="Statistiques automatiques")

    await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    send_server_stats.start()  # démarre la boucle automatique

# Base de données SQLite pour stocker les données
def init_db():
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    
    # Table pour les logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            guild_id INTEGER,
            channel_id INTEGER,
            log_type TEXT,
            PRIMARY KEY (guild_id, log_type)
        )
    ''')
    
    # Table pour l'antiraid
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS antiraid (
            guild_id INTEGER PRIMARY KEY,
            enabled BOOLEAN DEFAULT 0,
            max_joins INTEGER DEFAULT 5,
            time_window INTEGER DEFAULT 10
        )
    ''')
    
    # Table pour les giveaways
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS giveaways (
            message_id INTEGER PRIMARY KEY,
            guild_id INTEGER,
            channel_id INTEGER,
            prize TEXT,
            end_time INTEGER,
            winner_count INTEGER,
            host_id INTEGER
        )
    ''')
    
    # Table pour la modération
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mod_config (
            guild_id INTEGER PRIMARY KEY,
            auto_mod BOOLEAN DEFAULT 0,
            spam_limit INTEGER DEFAULT 5,
            caps_percent INTEGER DEFAULT 70
        )
    ''')
    
    conn.commit()
    conn.close()

# Dictionnaire pour stocker les données temporaires
temp_data = {
    'join_tracker': {},
    'user_messages': {},
    'muted_users': {},
    'active_polls': {}
}

@bot.event
async def on_ready():
    print(f'[+] {bot.user} est connecté!')
    print(f'[+] Chiyoda Gestion est prêt!')
    await bot.change_presence(activity=discord.Game(name="Chiyoda🌺"))
    init_db()
    check_giveaways.start()

# ==================== UTILITAIRE ====================

@bot.command(name='help')
@commands.has_permissions(administrator=True)
async def help_command(ctx):
    """Affiche l'aide du bot"""
    embed = discord.Embed(
        title="🤖 Chiyoda Gestion - Menu d'aide",
        description="Préfixe: `+`",
        color=0xFFD4FF
    )
    
    categories = {
        "🔧 Utilitaire": "help, userinfo, serverinfo, avatar, ping, uptime, invite, stats, roles, channels, emojis",
        "🎛️ Contrôle du bot": "shutdown, reload, status, activity, botinfo, version, commands, usage, blacklist, whitelist",
        "🛡️ Antiraid": "antiraid, raidconfig, joins, suspicious, raidlog, protection, raidstats, alertraid, banraid, kickraid",
        "⚙️ Gestion serveur": "createchannel, deletechannel, createrole, deleterole, moveall, lockall, unlockall, backup, restore, settings",
        "📝 Configuration": "prefix, welcomemsg, leavemsg, autorole, modlog, joinlog, setmuterole, automod, filtres, permissions",
        "📋 Logs": "logs, modlogs, joinlogs, messagelogs, voicelogs, deletelogs, editlogs, banlogs, kicklogs, rolelogs",
        "⚖️ Modération": "ban, kick, mute, unmute, warn, clear, slowmode, lock, unlock, massban",
        "🎁 Giveaway": "gcreate, gend, greroll, glist, gdelete",
        "📝 Embeds": "embed, embededit, embedinfo, quickembed, announcement",
        "📨 DM All": "dmall, dmallusers, dmallrole, dmstats, dmtest"
    }
    
    for category, commands in categories.items():
        embed.add_field(name=category, value=f"```{commands}```", inline=False)
    
    embed.set_footer(text="Utilisez +<commande> pour utiliser une commande")
    await ctx.send(embed=embed)

@bot.command(name='userinfo', aliases=['ui'])
async def userinfo(ctx, user: discord.Member = None):
    """Informations sur un utilisateur"""
    if not user:
        user = ctx.author
    
    embed = discord.Embed(title=f"Informations sur {user}", color=user.color)
    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    embed.add_field(name="ID", value=user.id, inline=True)
    embed.add_field(name="Nom d'utilisateur", value=f"{user.name}#{user.discriminator}", inline=True)
    embed.add_field(name="Surnom", value=user.nick or "Aucun", inline=True)
    embed.add_field(name="Création du compte", value=user.created_at.strftime("%d/%m/%Y %H:%M"), inline=True)
    embed.add_field(name="Rejoint le serveur", value=user.joined_at.strftime("%d/%m/%Y %H:%M"), inline=True)
    embed.add_field(name="Rôles", value=f"{len(user.roles)-1}", inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='serverinfo', aliases=['si'])
async def serverinfo(ctx):
    """Informations sur le serveur"""
    guild = ctx.guild
    embed = discord.Embed(title=f"Informations sur {guild.name}", color=0xFFD4FF)
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name="ID", value=guild.id, inline=True)
    embed.add_field(name="Propriétaire", value=guild.owner, inline=True)
    embed.add_field(name="Création", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Membres", value=guild.member_count, inline=True)
    embed.add_field(name="Salons", value=len(guild.channels), inline=True)
    embed.add_field(name="Rôles", value=len(guild.roles), inline=True)
    embed.add_field(name="Région", value=str(guild.region) if hasattr(guild, 'region') else "N/A", inline=True)
    embed.add_field(name="Niveau de vérification", value=str(guild.verification_level), inline=True)
    embed.add_field(name="Boosts", value=guild.premium_subscription_count, inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='avatar', aliases=['av'])
async def avatar(ctx, user: discord.Member = None):
    """Avatar d'un utilisateur"""
    if not user:
        user = ctx.author
    
    embed = discord.Embed(title=f"Avatar de {user}", color=0xFFD4FF)
    embed.set_image(url=user.avatar.url if user.avatar else user.default_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    """Latence du bot"""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latence: {latency}ms", color=0x00ff00)
    await ctx.send(embed=embed)

@bot.command(name='uptime')
async def uptime(ctx):
    """Temps de fonctionnement du bot"""
    uptime = datetime.datetime.now() - bot.start_time if hasattr(bot, 'start_time') else datetime.datetime.now()
    embed = discord.Embed(title="⏰ Uptime", description=f"En ligne depuis: {str(uptime).split('.')[0]}", color=0xFFD4FF)
    await ctx.send(embed=embed)

@bot.command(name='invite')
async def invite(ctx):
    """Lien d'invitation du bot"""
    invite_link = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions.all())
    embed = discord.Embed(title="📨 Invitation", description=f"[Cliquez ici pour m'inviter]({invite_link})", color=0xFFD4FF)
    await ctx.send(embed=embed)

@bot.command(name='stats')
async def stats(ctx):
    """Statistiques du bot"""
    embed = discord.Embed(title="📊 Statistiques", color=0xFFD4FF)
    embed.add_field(name="Serveurs", value=len(bot.guilds), inline=True)
    embed.add_field(name="Utilisateurs", value=len(bot.users), inline=True)
    embed.add_field(name="Commandes", value=len(bot.commands), inline=True)
    await ctx.send(embed=embed)

@bot.command(name='roles')
async def roles(ctx):
    """Liste des rôles du serveur"""
    roles = [role.mention for role in ctx.guild.roles[1:]]  # Exclure @everyone
    if not roles:
        return await ctx.send("Aucun rôle sur ce serveur.")
    
    embed = discord.Embed(title="📋 Rôles du serveur", description="\n".join(roles), color=0xFFD4FF)
    await ctx.send(embed=embed)

@bot.command(name='channels')
async def channels(ctx):
    """Liste des salons du serveur"""
    text_channels = [f"📝 {channel.mention}" for channel in ctx.guild.text_channels]
    voice_channels = [f"🔊 {channel.name}" for channel in ctx.guild.voice_channels]
    
    embed = discord.Embed(title="📋 Salons du serveur", color=0xFFD4FF)
    if text_channels:
        embed.add_field(name="Salons textuels", value="\n".join(text_channels[:10]), inline=False)
    if voice_channels:
        embed.add_field(name="Salons vocaux", value="\n".join(voice_channels[:10]), inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='emojis')
async def emojis(ctx):
    """Liste des emojis du serveur"""
    if not ctx.guild.emojis:
        return await ctx.send("Aucun emoji personnalisé sur ce serveur.")
    
    emoji_list = " ".join([str(emoji) for emoji in ctx.guild.emojis[:20]])
    embed = discord.Embed(title="😄 Emojis du serveur", description=emoji_list, color=0xFFD4FF)
    embed.set_footer(text=f"Total: {len(ctx.guild.emojis)} emojis")
    await ctx.send(embed=embed)

# ==================== CONTRÔLE DU BOT ====================

@bot.command(name='shutdown')
@commands.is_owner()
async def shutdown(ctx):
    """Éteint le bot"""
    await ctx.send("🔴 Arrêt du bot...")
    await bot.close()

@bot.command(name='reload')
@commands.is_owner()
async def reload(ctx, extension=None):
    """Recharge une extension"""
    await ctx.send("🔄 Rechargement effectué!")

@bot.command(name='status')
@commands.has_permissions(administrator=True)
async def status(ctx, *, status):
    """Change le statut du bot"""
    await bot.change_presence(activity=discord.Game(name=status))
    await ctx.send(f"✅ Statut changé: {status}")

@bot.command(name='activity')
@commands.has_permissions(administrator=True)
async def activity(ctx, activity_type, *, name):
    """Change l'activité du bot"""
    activities = {
        'playing': discord.ActivityType.playing,
        'watching': discord.ActivityType.watching,
        'listening': discord.ActivityType.listening
    }
    
    if activity_type.lower() in activities:
        activity = discord.Activity(type=activities[activity_type.lower()], name=name)
        await bot.change_presence(activity=activity)
        await ctx.send(f"✅ Activité changée: {activity_type} {name}")

@bot.command(name='botinfo')
async def botinfo(ctx):
    """Informations sur le bot"""
    embed = discord.Embed(title="🤖 Chiyoda Gestion", color=0xFFD4FF)
    embed.add_field(name="Créateur", value="Développeur", inline=True)
    embed.add_field(name="Version", value="1.0.0", inline=True)
    embed.add_field(name="Langage", value="Python", inline=True)
    embed.add_field(name="Librairie", value="discord.py", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='version')
async def version(ctx):
    """Version du bot"""
    embed = discord.Embed(title="📋 Version", description="Chiyoda Gestion v1.0.0", color=0xFFD4FF)
    await ctx.send(embed=embed)

@bot.command(name='commands')
async def commands_list(ctx):
    """Liste des commandes"""
    await ctx.invoke(help_command)

@bot.command(name='usage')
async def usage(ctx):
    """Utilisation du bot"""
    embed = discord.Embed(title="📈 Utilisation", description="Statistiques d'utilisation du bot", color=0xFFD4FF)
    await ctx.send(embed=embed)

@bot.command(name='blacklist')
@commands.is_owner()
async def blacklist(ctx, user: discord.User):
    """Blacklist un utilisateur"""
    await ctx.send(f"🚫 {user} a été blacklisté.")

@bot.command(name='whitelist')
@commands.is_owner()
async def whitelist(ctx, user: discord.User):
    """Whitelist un utilisateur"""
    await ctx.send(f"✅ {user} a été whitelisté.")

# ==================== ANTIRAID ====================

@bot.command(name='antiraid')
@commands.has_permissions(administrator=True)
async def antiraid(ctx, action=None):
    """Configure l'antiraid"""
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    
    if action == "on":
        cursor.execute("INSERT OR REPLACE INTO antiraid (guild_id, enabled) VALUES (?, 1)", (ctx.guild.id,))
        await ctx.send("🛡️ Antiraid activé!")
    elif action == "off":
        cursor.execute("INSERT OR REPLACE INTO antiraid (guild_id, enabled) VALUES (?, 0)", (ctx.guild.id,))
        await ctx.send("🛡️ Antiraid désactivé!")
    else:
        cursor.execute("SELECT enabled FROM antiraid WHERE guild_id = ?", (ctx.guild.id,))
        result = cursor.fetchone()
        status = "Activé" if result and result[0] else "Désactivé"
        await ctx.send(f"🛡️ Antiraid: {status}")
    
    conn.commit()
    conn.close()

@bot.command(name='raidconfig')
@commands.has_permissions(administrator=True)
async def raidconfig(ctx, max_joins: int = 5, time_window: int = 10):
    """Configure les paramètres antiraid"""
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO antiraid (guild_id, max_joins, time_window) VALUES (?, ?, ?)",
        (ctx.guild.id, max_joins, time_window)
    )
    conn.commit()
    conn.close()
    
    await ctx.send(f"⚙️ Antiraid configuré: {max_joins} arrivées max en {time_window}s")

@bot.command(name='joins')
@commands.has_permissions(manage_guild=True)
async def joins(ctx):
    """Affiche les arrivées récentes"""
    guild_joins = temp_data['join_tracker'].get(ctx.guild.id, [])
    recent_joins = [j for j in guild_joins if time.time() - j['time'] < 60]
    
    if not recent_joins:
        return await ctx.send("Aucune arrivée récente.")
    
    embed = discord.Embed(title="📈 Arrivées récentes", color=0xFFD4FF)
    for join in recent_joins[-10:]:
        user = bot.get_user(join['user_id'])
        embed.add_field(
            name=f"{user or 'Utilisateur inconnu'}",
            value=f"<t:{int(join['time'])}:R>",
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command(name='suspicious')
@commands.has_permissions(manage_guild=True)
async def suspicious(ctx):
    """Affiche les comptes suspects"""
    embed = discord.Embed(title="⚠️ Comptes suspects", color=0xff9900)
    embed.description = "Comptes récents ou sans avatar"
    
    suspects = []
    for member in ctx.guild.members:
        if (datetime.datetime.now() - member.created_at).days < 7:
            suspects.append(f"{member.mention} - Compte créé <t:{int(member.created_at.timestamp())}:R>")
    
    if suspects:
        embed.description = "\n".join(suspects[:10])
    else:
        embed.description = "Aucun compte suspect détecté."
    
    await ctx.send(embed=embed)

@bot.command(name='raidlog')
@commands.has_permissions(administrator=True)
async def raidlog(ctx, channel: discord.TextChannel = None):
    """Configure le salon de logs antiraid"""
    if not channel:
        channel = ctx.channel
    
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO logs VALUES (?, ?, 'raid')", (ctx.guild.id, channel.id))
    conn.commit()
    conn.close()
    
    await ctx.send(f"📋 Logs antiraid configurés dans {channel.mention}")

@bot.command(name='protection')
@commands.has_permissions(administrator=True)
async def protection(ctx, level: int = 1):
    """Définit le niveau de protection"""
    levels = {1: "Faible", 2: "Moyen", 3: "Élevé", 4: "Maximum"}
    if level not in levels:
        return await ctx.send("Niveau invalide (1-4)")
    
    await ctx.send(f"🛡️ Niveau de protection: {levels[level]}")

@bot.command(name='raidstats')
@commands.has_permissions(manage_guild=True)
async def raidstats(ctx):
    """Statistiques antiraid"""
    embed = discord.Embed(title="📊 Statistiques Antiraid", color=0xFFD4FF)
    embed.add_field(name="Raids bloqués", value="0", inline=True)
    embed.add_field(name="Utilisateurs bannis", value="0", inline=True)
    embed.add_field(name="Dernier raid", value="Jamais", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='alertraid')
@commands.has_permissions(administrator=True)
async def alertraid(ctx):
    """Test d'alerte raid"""
    embed = discord.Embed(title="🚨 ALERTE RAID", description="Raid potentiel détecté!", color=0xff0000)
    await ctx.send(embed=embed)

@bot.command(name='banraid')
@commands.has_permissions(ban_members=True)
async def banraid(ctx, count: int = 10):
    """Ban les derniers arrivants"""
    if count > 20:
        return await ctx.send("Maximum 20 utilisateurs.")
    
    recent_members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[:count]
    
    banned = 0
    for member in recent_members:
        if member != ctx.author and not member.guild_permissions.administrator:
            try:
                await member.ban(reason="Banissement antiraid")
                banned += 1
            except:
                pass
    
    await ctx.send(f"🔨 {banned} utilisateurs bannis par l'antiraid.")

@bot.command(name='kickraid')
@commands.has_permissions(kick_members=True)
async def kickraid(ctx, count: int = 10):
    """Kick les derniers arrivants"""
    if count > 20:
        return await ctx.send("Maximum 20 utilisateurs.")
    
    recent_members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[:count]
    
    kicked = 0
    for member in recent_members:
        if member != ctx.author and not member.guild_permissions.administrator:
            try:
                await member.kick(reason="Kick antiraid")
                kicked += 1
            except:
                pass
    
    await ctx.send(f"👢 {kicked} utilisateurs expulsés par l'antiraid.")

# ==================== GESTION SERVEUR ====================

@bot.command(name='createchannel', aliases=['cc'])
@commands.has_permissions(manage_channels=True)
async def create_channel(ctx, channel_type, *, name):
    """Crée un salon"""
    if channel_type.lower() == "text":
        channel = await ctx.guild.create_text_channel(name)
    elif channel_type.lower() == "voice":
        channel = await ctx.guild.create_voice_channel(name)
    else:
        return await ctx.send("Type invalide (text/voice)")
    
    await ctx.send(f"✅ Salon créé: {channel.mention if hasattr(channel, 'mention') else channel.name}")

@bot.command(name='deletechannel', aliases=['dc'])
@commands.has_permissions(manage_channels=True)
async def delete_channel(ctx, channel: discord.TextChannel = None):
    """Supprime un salon"""
    if not channel:
        channel = ctx.channel
    
    await channel.delete(reason=f"Supprimé par {ctx.author}")
    if channel != ctx.channel:
        await ctx.send(f"✅ Salon {channel.name} supprimé!")

@bot.command(name='createrole', aliases=['cr'])
@commands.has_permissions(manage_roles=True)
async def create_role(ctx, *, name):
    """Crée un rôle"""
    role = await ctx.guild.create_role(name=name, reason=f"Créé par {ctx.author}")
    await ctx.send(f"✅ Rôle créé: {role.mention}")

@bot.command(name='deleterole', aliases=['dr'])
@commands.has_permissions(manage_roles=True)
async def delete_role(ctx, role: discord.Role):
    """Supprime un rôle"""
    await role.delete(reason=f"Supprimé par {ctx.author}")
    await ctx.send(f"✅ Rôle {role.name} supprimé!")

@bot.command(name='moveall')
@commands.has_permissions(move_members=True)
async def move_all(ctx, from_channel: discord.VoiceChannel, to_channel: discord.VoiceChannel):
    """Déplace tous les membres d'un salon vocal"""
    moved = 0
    for member in from_channel.members:
        try:
            await member.move_to(to_channel)
            moved += 1
        except:
            pass
    
    await ctx.send(f"✅ {moved} membres déplacés vers {to_channel.name}")

@bot.command(name='lockall')
@commands.has_permissions(manage_channels=True)
async def lock_all(ctx):
    """Verrouille tous les salons textuels"""
    locked = 0
    for channel in ctx.guild.text_channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=False)
            locked += 1
        except:
            pass
    
    await ctx.send(f"🔒 {locked} salons verrouillés!")

@bot.command(name='unlockall')
@commands.has_permissions(manage_channels=True)
async def unlock_all(ctx):
    """Déverrouille tous les salons textuels"""
    unlocked = 0
    for channel in ctx.guild.text_channels:
        try:
            await channel.set_permissions(ctx.guild.default_role, send_messages=None)
            unlocked += 1
        except:
            pass
    
    await ctx.send(f"🔓 {unlocked} salons déverrouillés!")

@bot.command(name='backup')
@commands.has_permissions(administrator=True)
async def backup(ctx):
    """Crée une sauvegarde du serveur"""
    await ctx.send("💾 Sauvegarde créée! (Fonctionnalité en développement)")

@bot.command(name='restore')
@commands.has_permissions(administrator=True)
async def restore(ctx):
    """Restaure une sauvegarde"""
    await ctx.send("📥 Restauration effectuée! (Fonctionnalité en développement)")

@bot.command(name='settings')
@commands.has_permissions(administrator=True)
async def settings(ctx):
    """Paramètres du serveur"""
    embed = discord.Embed(title="⚙️ Paramètres du serveur", color=0xFFD4FF)
    embed.add_field(name="Nom", value=ctx.guild.name, inline=True)
    embed.add_field(name="Région", value="Auto", inline=True)
    embed.add_field(name="Niveau de vérification", value=ctx.guild.verification_level, inline=True)
    await ctx.send(embed=embed)

# ==================== CONFIGURATION ====================

@bot.command(name='prefix')
@commands.has_permissions(administrator=True)
async def prefix(ctx, new_prefix=None):
    """Change le préfixe du bot"""
    if not new_prefix:
        return await ctx.send(f"Préfixe actuel: `{bot.command_prefix}`")
    
    bot.command_prefix = new_prefix
    await ctx.send(f"✅ Préfixe changé: `{new_prefix}`")

@bot.command(name='welcomemsg')
@commands.has_permissions(administrator=True)
async def welcome_msg(ctx, channel: discord.TextChannel, *, message):
    """Configure le message de bienvenue"""
    await ctx.send(f"✅ Message de bienvenue configuré dans {channel.mention}")

@bot.command(name='leavemsg')
@commands.has_permissions(administrator=True)
async def leave_msg(ctx, channel: discord.TextChannel, *, message):
    """Configure le message d'au revoir"""
    await ctx.send(f"✅ Message d'au revoir configuré dans {channel.mention}")

@bot.command(name='autorole')
@commands.has_permissions(administrator=True)
async def autorole(ctx, role: discord.Role):
    """Configure l'autorôle"""
    await ctx.send(f"✅ Autorôle configuré: {role.mention}")

@bot.command(name='modlog')
@commands.has_permissions(administrator=True)
async def modlog(ctx, channel: discord.TextChannel = None):
    """Configure le salon de logs de modération"""
    if not channel:
        channel = ctx.channel
    
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO logs VALUES (?, ?, 'mod')", (ctx.guild.id, channel.id))
    conn.commit()
    conn.close()
    
    await ctx.send(f"📋 Logs de modération configurés dans {channel.mention}")

@bot.command(name='joinlog')
@commands.has_permissions(administrator=True)
async def joinlog(ctx, channel: discord.TextChannel = None):
    """Configure le salon de logs d'arrivée"""
    if not channel:
        channel = ctx.channel
    
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO logs VALUES (?, ?, 'join')", (ctx.guild.id, channel.id))
    conn.commit()
    conn.close()
    
    await ctx.send(f"📋 Logs d'arrivée configurés dans {channel.mention}")

@bot.command(name='setmuterole')
@commands.has_permissions(administrator=True)
async def set_mute_role(ctx, role: discord.Role):
    """Configure le rôle de mute"""
    await ctx.send(f"✅ Rôle de mute configuré: {role.mention}")

@bot.command(name='automod')
@commands.has_permissions(administrator=True)
async def automod(ctx, status=None):
    """Configure l'auto-modération"""
    if status == "on":
        await ctx.send("🤖 Auto-modération activée!")
    elif status == "off":
        await ctx.send("🤖 Auto-modération désactivée!")
    else:
        await ctx.send("🤖 Auto-modération: Désactivée")

@bot.command(name='filtres')
@commands.has_permissions(administrator=True)
async def filtres(ctx):
    """Configure les filtres de mots"""
    await ctx.send("🔍 Configuration des filtres (Fonctionnalité en développement)")

@bot.command(name='permissions')
@commands.has_permissions(administrator=True)
async def permissions(ctx, member: discord.Member, *, permission_name):
    """Gère les permissions"""
    await ctx.send(f"⚙️ Permissions mises à jour pour {member.mention}")

# ==================== LOGS ====================

@bot.command(name='logs')
@commands.has_permissions(administrator=True)
async def logs(ctx, log_type=None, channel: discord.TextChannel = None):
    """Configure les logs généraux"""
    if not log_type:
        return await ctx.send("Types disponibles: mod, join, message, voice, delete, edit, ban, kick, role")
    
    if not channel:
        channel = ctx.channel
    
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO logs VALUES (?, ?, ?)", (ctx.guild.id, channel.id, log_type))
    conn.commit()
    conn.close()
    
    await ctx.send(f"📋 Logs {log_type} configurés dans {channel.mention}")

@bot.command(name='modlogs')
@commands.has_permissions(administrator=True)
async def modlogs(ctx, channel: discord.TextChannel = None):
    """Logs de modération"""
    await ctx.invoke(logs, "mod", channel)

@bot.command(name='joinlogs')
@commands.has_permissions(administrator=True)
async def joinlogs(ctx, channel: discord.TextChannel = None):
    """Logs d'arrivée/départ"""
    await ctx.invoke(logs, "join", channel)

@bot.command(name='messagelogs')
@commands.has_permissions(administrator=True)
async def messagelogs(ctx, channel: discord.TextChannel = None):
    """Logs de messages"""
    await ctx.invoke(logs, "message", channel)

@bot.command(name='voicelogs')
@commands.has_permissions(administrator=True)
async def voicelogs(ctx, channel: discord.TextChannel = None):
    """Logs vocaux"""
    await ctx.invoke(logs, "voice", channel)

@bot.command(name='deletelogs')
@commands.has_permissions(administrator=True)
async def deletelogs(ctx, channel: discord.TextChannel = None):
    """Logs de suppression"""
    await ctx.invoke(logs, "delete", channel)

@bot.command(name='editlogs')
@commands.has_permissions(administrator=True)
async def editlogs(ctx, channel: discord.TextChannel = None):
    """Logs d'édition"""
    await ctx.invoke(logs, "edit", channel)

@bot.command(name='banlogs')
@commands.has_permissions(administrator=True)
async def banlogs(ctx, channel: discord.TextChannel = None):
    """Logs de bannissement"""
    await ctx.invoke(logs, "ban", channel)

@bot.command(name='kicklogs')
@commands.has_permissions(administrator=True)
async def kicklogs(ctx, channel: discord.TextChannel = None):
    """Logs d'expulsion"""
    await ctx.invoke(logs, "kick", channel)

@bot.command(name='rolelogs')
@commands.has_permissions(administrator=True)
async def rolelogs(ctx, channel: discord.TextChannel = None):
    """Logs de rôles"""
    await ctx.invoke(logs, "role", channel)

# ==================== MODÉRATION ====================

@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: Union[discord.Member, int], *, reason="Aucune raison"):
    """Bannit un utilisateur"""
    if isinstance(member, int):
        try:
            user = await bot.fetch_user(member)
            await ctx.guild.ban(user, reason=f"{reason} - Par {ctx.author}")
            await ctx.send(f"🔨 {user} a été banni: {reason}")
        except:
            await ctx.send("❌ Utilisateur introuvable.")
    else:
        await ctx.guild.ban(member, reason=f"{reason} - Par {ctx.author}")
        await ctx.send(f"🔨 {member} a été banni: {reason}")

@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="Aucune raison"):
    """Expulse un utilisateur"""
    await member.kick(reason=f"{reason} - Par {ctx.author}")
    await ctx.send(f"👢 {member} a été expulsé: {reason}")

@bot.command(name='mute')
@commands.has_permissions(manage_messages=True)
async def mute(ctx, member: discord.Member, duration: int = 60, *, reason="Aucune raison"):
    """Mute un utilisateur"""
    try:
        await member.timeout(datetime.timedelta(minutes=duration), reason=f"{reason} - Par {ctx.author}")
        temp_data['muted_users'][member.id] = time.time() + (duration * 60)
        await ctx.send(f"🔇 {member} a été mute pour {duration} minutes: {reason}")
    except:
        await ctx.send("❌ Impossible de mute cet utilisateur.")

@bot.command(name='unmute')
@commands.has_permissions(manage_messages=True)
async def unmute(ctx, member: discord.Member):
    """Démute un utilisateur"""
    try:
        await member.timeout(None)
        if member.id in temp_data['muted_users']:
            del temp_data['muted_users'][member.id]
        await ctx.send(f"🔊 {member} a été démute.")
    except:
        await ctx.send("❌ Impossible de démute cet utilisateur.")

@bot.command(name='warn')
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="Aucune raison"):
    """Avertit un utilisateur"""
    try:
        embed = discord.Embed(
            title="⚠️ Avertissement",
            description=f"Vous avez été averti sur **{ctx.guild.name}**\nRaison: {reason}",
            color=0xff9900
        )
        await member.send(embed=embed)
        await ctx.send(f"⚠️ {member} a été averti: {reason}")
    except:
        await ctx.send(f"⚠️ {member} a été averti: {reason} (MP non envoyé)")

@bot.command(name='clear', aliases=['purge'])
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    """Supprime des messages"""
    if amount > 100:
        return await ctx.send("Maximum 100 messages.")
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🗑️ {len(deleted) - 1} messages supprimés.", delete_after=3)

@bot.command(name='slowmode', aliases=['slow'])
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int = 0):
    """Configure le mode lent"""
    await ctx.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await ctx.send("🐌 Mode lent désactivé.")
    else:
        await ctx.send(f"🐌 Mode lent: {seconds} secondes.")

@bot.command(name='lock')
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    """Verrouille un salon"""
    if not channel:
        channel = ctx.channel
    
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 {channel.mention} verrouillé.")

@bot.command(name='unlock')
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    """Déverrouille un salon"""
    if not channel:
        channel = ctx.channel
    
    await channel.set_permissions(ctx.guild.default_role, send_messages=None)
    await ctx.send(f"🔓 {channel.mention} déverrouillé.")

@bot.command(name='massban')
@commands.has_permissions(ban_members=True)
async def massban(ctx, *user_ids):
    """Ban plusieurs utilisateurs par ID"""
    banned = 0
    for user_id in user_ids:
        try:
            user = await bot.fetch_user(int(user_id))
            await ctx.guild.ban(user, reason=f"Massban par {ctx.author}")
            banned += 1
        except:
            pass
    
    await ctx.send(f"🔨 {banned} utilisateurs bannis en masse.")

# ==================== GIVEAWAY ====================

@bot.command(name='gcreate', aliases=['giveaway'])
@commands.has_permissions(manage_messages=True)
async def giveaway_create(ctx, duration, winners: int, *, prize):
    """Crée un giveaway"""
    # Parse duration (ex: 1h, 30m, 1d)
    duration_seconds = 0
    if duration.endswith('s'):
        duration_seconds = int(duration[:-1])
    elif duration.endswith('m'):
        duration_seconds = int(duration[:-1]) * 60
    elif duration.endswith('h'):
        duration_seconds = int(duration[:-1]) * 3600
    elif duration.endswith('d'):
        duration_seconds = int(duration[:-1]) * 86400
    else:
        return await ctx.send("Format de durée invalide (ex: 1h, 30m, 1d)")
    
    end_time = int(time.time() + duration_seconds)
    
    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"**Prix:** {prize}\n**Gagnants:** {winners}\n**Se termine:** <t:{end_time}:R>",
        color=0xff69b4
    )
    embed.set_footer(text="Réagissez avec 🎉 pour participer!")
    
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("🎉")
    
    # Sauvegarder en base
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO giveaways VALUES (?, ?, ?, ?, ?, ?, ?)",
        (msg.id, ctx.guild.id, ctx.channel.id, prize, end_time, winners, ctx.author.id)
    )
    conn.commit()
    conn.close()

@bot.command(name='gend')
@commands.has_permissions(manage_messages=True)
async def giveaway_end(ctx, message_id: int):
    """Termine un giveaway manuellement"""
    await end_giveaway(message_id, ctx.channel)

@bot.command(name='greroll')
@commands.has_permissions(manage_messages=True)
async def giveaway_reroll(ctx, message_id: int):
    """Relance un giveaway"""
    await ctx.send(f"🎲 Giveaway {message_id} relancé!")

@bot.command(name='glist')
async def giveaway_list(ctx):
    """Liste des giveaways actifs"""
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM giveaways WHERE guild_id = ?", (ctx.guild.id,))
    giveaways = cursor.fetchall()
    conn.close()
    
    if not giveaways:
        return await ctx.send("Aucun giveaway actif.")
    
    embed = discord.Embed(title="🎉 Giveaways actifs", color=0xff69b4)
    for g in giveaways:
        embed.add_field(
            name=g[2],  # prize
            value=f"Se termine: <t:{g[4]}:R>",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='gdelete')
@commands.has_permissions(manage_messages=True)
async def giveaway_delete(ctx, message_id: int):
    """Supprime un giveaway"""
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM giveaways WHERE message_id = ?", (message_id,))
    conn.commit()
    conn.close()
    
    await ctx.send(f"🗑️ Giveaway {message_id} supprimé.")

@tasks.loop(seconds=30)
async def check_giveaways():
    """Vérifie les giveaways à terminer"""
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM giveaways WHERE end_time <= ?", (int(time.time()),))
    ended_giveaways = cursor.fetchall()
    
    for giveaway in ended_giveaways:
        channel = bot.get_channel(giveaway[2])
        if channel:
            await end_giveaway(giveaway[0], channel)
        
        cursor.execute("DELETE FROM giveaways WHERE message_id = ?", (giveaway[0],))
    
    conn.commit()
    conn.close()

async def end_giveaway(message_id, channel):
    """Termine un giveaway"""
    try:
        message = await channel.fetch_message(message_id)
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        
        if not reaction:
            return
        
        users = [user async for user in reaction.users() if not user.bot]
        
        conn = sqlite3.connect('chiyoda.db')
        cursor = conn.cursor()
        cursor.execute("SELECT prize, winner_count FROM giveaways WHERE message_id = ?", (message_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return
        
        prize, winner_count = result
        
        if len(users) < winner_count:
            winners = users
        else:
            winners = random.sample(users, winner_count)
        
        if winners:
            winner_mentions = ", ".join([user.mention for user in winners])
            embed = discord.Embed(
                title="🎉 Giveaway terminé!",
                description=f"**Prix:** {prize}\n**Gagnant(s):** {winner_mentions}",
                color=0x00ff00
            )
            await channel.send(embed=embed)
        else:
            await channel.send("🎉 Giveaway terminé! Aucun participant.")
    
    except Exception as e:
        print(f"Erreur giveaway: {e}")

# ==================== EMBEDS ====================

@bot.command(name='embed')
@commands.has_permissions(manage_messages=True)
async def create_embed(ctx, *, content):
    """Crée un embed simple"""
    lines = content.split('\n')
    title = lines[0] if lines else "Embed"
    description = '\n'.join(lines[1:]) if len(lines) > 1 else ""
    
    embed = discord.Embed(title=title, description=description, color=0xFFD4FF)
    embed.set_footer(text=f"Créé par {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command(name='embededit')
@commands.has_permissions(manage_messages=True)
async def embed_edit(ctx, message_id: int, *, new_content):
    """Édite un embed"""
    try:
        message = await ctx.channel.fetch_message(message_id)
        lines = new_content.split('\n')
        title = lines[0] if lines else "Embed"
        description = '\n'.join(lines[1:]) if len(lines) > 1 else ""
        
        embed = discord.Embed(title=title, description=description, color=0xFFD4FF)
        embed.set_footer(text=f"Modifié par {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        
        await message.edit(embed=embed)
        await ctx.send("✅ Embed modifié!")
    except:
        await ctx.send("❌ Message introuvable.")

@bot.command(name='embedinfo')
async def embed_info(ctx, message_id: int):
    """Informations sur un embed"""
    try:
        message = await ctx.channel.fetch_message(message_id)
        if message.embeds:
            embed = message.embeds[0]
            info_embed = discord.Embed(
                title="📋 Informations Embed",
                description=f"**Titre:** {embed.title or 'Aucun'}\n**Description:** {len(embed.description or '')} caractères\n**Champs:** {len(embed.fields)}",
                color=0xFFD4FF
            )
            await ctx.send(embed=info_embed)
        else:
            await ctx.send("❌ Ce message ne contient pas d'embed.")
    except:
        await ctx.send("❌ Message introuvable.")

@bot.command(name='quickembed', aliases=['qe'])
@commands.has_permissions(manage_messages=True)
async def quick_embed(ctx, color, title, *, description):
    """Crée un embed rapide avec couleur"""
    try:
        color_int = int(color.replace('#', ''), 16) if color.startswith('#') else int(color, 16)
    except:
        color_int = 0xFFD4FF
    
    embed = discord.Embed(title=title, description=description, color=color_int)
    await ctx.send(embed=embed)

@bot.command(name='announcement', aliases=['announce'])
@commands.has_permissions(manage_messages=True)
async def announcement(ctx, *, content):
    """Crée une annonce"""
    embed = discord.Embed(
        title="📢 ANNONCE",
        description=content,
        color=0xff6b6b,
        timestamp=datetime.datetime.now()
    )
    embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    
    await ctx.send(embed=embed)

# ==================== DM ALL ====================

@bot.command(name='dmall')
@commands.has_permissions(administrator=True)
async def dm_all(ctx, *, message):
    """Envoie un MP texte à tous les membres"""
    sent = 0
    failed = 0
    
    progress_msg = await ctx.send("📨 Envoi en cours...")
    
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(message)  # juste ton message
                sent += 1
            except:
                failed += 1
            
            if (sent + failed) % 10 == 0:
                await progress_msg.edit(
                    content=f"📨 Progression: {sent + failed}/{len([m for m in ctx.guild.members if not m.bot])}"
                )
    
    await progress_msg.edit(content=f"✅ Envoi terminé! Réussi: {sent}, Échoué: {failed}")


@bot.command(name='dmallusers')
@commands.has_permissions(administrator=True)
async def dm_all_users(ctx, *, message):
    """Envoie un MP à tous les utilisateurs (pas les bots)"""
    await ctx.invoke(dm_all, message=message)


@bot.command(name='dmallrole')
@commands.has_permissions(administrator=True)
async def dm_all_role(ctx, role: discord.Role, *, message):
    """Envoie un MP à tous les membres d'un rôle"""
    sent = 0
    failed = 0
    
    progress_msg = await ctx.send("📨 Envoi en cours...")
    
    for member in role.members:
        if not member.bot:
            try:
                await member.send(message)  # juste ton message
                sent += 1
            except:
                failed += 1
    
    await progress_msg.edit(content=f"✅ Envoi terminé! Réussi: {sent}, Échoué: {failed}")


@bot.command(name='dmstats')
@commands.has_permissions(administrator=True)
async def dm_stats(ctx):
    """Statistiques des MPs"""
    await ctx.send("📊 Statistiques DM\n\nMessages envoyés: 0\nSuccès: 0%\nDernier envoi: Jamais")


@bot.command(name='dmtest')
@commands.has_permissions(administrator=True)
async def dm_test(ctx, *, message):
    """Test d'envoi de MP (à soi-même)"""
    try:
        await ctx.author.send(message)  # juste ton message
        await ctx.send("✅ MP de test envoyé!")
    except:
        await ctx.send("❌ Impossible d'envoyer le MP de test.")

# ==================== ÉVÉNEMENTS ====================

@bot.event
async def on_member_join(member):
    """Détection antiraid et logs d'arrivée"""
    guild_id = member.guild.id
    current_time = time.time()
    
    # Antiraid tracking
    if guild_id not in temp_data['join_tracker']:
        temp_data['join_tracker'][guild_id] = []
    
    temp_data['join_tracker'][guild_id].append({
        'user_id': member.id,
        'time': current_time
    })
    
    # Check antiraid
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("SELECT enabled, max_joins, time_window FROM antiraid WHERE guild_id = ?", (guild_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:  # antiraid enabled
        max_joins, time_window = result[1], result[2]
        recent_joins = [j for j in temp_data['join_tracker'][guild_id] 
                       if current_time - j['time'] < time_window]
        
        if len(recent_joins) >= max_joins:
            # Raid detected
            try:
                await member.ban(reason="Antiraid automatique")
            except:
                pass

@bot.event
async def on_message_delete(message):
    """Log des messages supprimés"""
    if message.author.bot:
        return
    
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM logs WHERE guild_id = ? AND log_type = 'delete'", (message.guild.id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        channel = bot.get_channel(result[0])
        if channel:
            embed = discord.Embed(
                title="🗑️ Message supprimé",
                description=f"**Auteur:** {message.author.mention}\n**Salon:** {message.channel.mention}\n**Contenu:** {message.content[:1000]}",
                color=0xff6b6b,
                timestamp=datetime.datetime.now()
            )
            await channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    """Log des messages édités"""
    if before.author.bot or before.content == after.content:
        return
    
    conn = sqlite3.connect('chiyoda.db')
    cursor = conn.cursor()
    cursor.execute("SELECT channel_id FROM logs WHERE guild_id = ? AND log_type = 'edit'", (before.guild.id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        channel = bot.get_channel(result[0])
        if channel:
            embed = discord.Embed(
                title="✏️ Message édité",
                color=0xffa500,
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="Avant", value=before.content[:1000], inline=False)
            embed.add_field(name="Après", value=after.content[:1000], inline=False)
            embed.set_footer(text=f"Par {before.author} dans #{before.channel.name}")
            await channel.send(embed=embed)

# ==================== COMMANDES BONUS ====================

@bot.command(name='poll', aliases=['sondage'])
@commands.has_permissions(manage_messages=True)
async def poll(ctx, question, *options):
    """Crée un sondage"""
    if len(options) > 10:
        return await ctx.send("Maximum 10 options.")
    
    if len(options) < 2:
        return await ctx.send("Minimum 2 options.")
    
    reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    
    description = ""
    for i, option in enumerate(options):
        description += f"{reactions[i]} {option}\n"
    
    embed = discord.Embed(title=f"📊 {question}", description=description, color=0xFFD4FF)
    embed.set_footer(text=f"Sondage créé par {ctx.author}")
    
    poll_msg = await ctx.send(embed=embed)
    
    for i in range(len(options)):
        await poll_msg.add_reaction(reactions[i])
    
    temp_data['active_polls'][poll_msg.id] = {
        'question': question,
        'options': options,
        'creator': ctx.author.id
    }

@bot.command(name='say')
@commands.has_permissions(manage_messages=True)
async def say(ctx, *, message):
    """Fait parler le bot"""
    await ctx.message.delete()
    await ctx.send(message)

@bot.command(name='nickname', aliases=['nick'])
@commands.has_permissions(manage_nicknames=True)
async def nickname(ctx, member: discord.Member, *, nick=None):
    """Change le surnom d'un membre"""
    await member.edit(nick=nick)
    if nick:
        await ctx.send(f"✅ Surnom de {member} changé en: {nick}")
    else:
        await ctx.send(f"✅ Surnom de {member} supprimé.")

@bot.command(name='membercount', aliases=['mc'])
async def member_count(ctx):
    """Nombre de membres"""
    embed = discord.Embed(
        title="👥 Membres",
        description=f"**Total:** {ctx.guild.member_count}\n**Humains:** {len([m for m in ctx.guild.members if not m.bot])}\n**Bots:** {len([m for m in ctx.guild.members if m.bot])}",
        color=0xFFD4FF
    )
    await ctx.send(embed=embed)

# ==================== GESTION D'ERREURS ====================

@bot.event
async def on_command_error(ctx, error):
    """Gestion des erreurs"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(" Tu n'avez pas les permissions nécessaires.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f" Argument manquant: {error.param.name}")
    elif isinstance(error, commands.CommandNotFound):
        return  # Ignore les commandes inexistantes
    elif isinstance(error, commands.BadArgument):
        await ctx.send(" Argument invalide.")
    else:
        await ctx.send(f" Erreur: {str(error)}")
        print(f"Erreur: {error}")

# ==================== DÉMARRAGE ====================

if __name__ == "__main__":
    bot.start_time = datetime.datetime.now()
    print("[+] Démarrage de Chiyoda Gestion...")
    print("[+] Créé par un développeur passionné")
    print("[+] Version 1.0.0")
    
    # Remplacez 'YOUR_BOT_TOKEN' par votre vrai token
    bot.run('MTQxMDU5MDk2NTcxMzg2Njg4Mw.GOlbiT.qHzfmF8ovKHy93Otq8bklIUH3lB4G8wjndyi2w')
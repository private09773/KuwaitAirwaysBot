import discord
from discord.ext import commands
import platform
import datetime

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Check bot latency")
    async def ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Latency: `{latency}ms`",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="botinfo", description="Show information about Kuwait Airways PTFS Utils")
    async def botinfo(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Kuwait Airways PTFS Utils",
            color=discord.Color.dark_blue()
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="Bot Name", value=self.bot.user.name, inline=True)
        embed.add_field(name="Bot ID", value=self.bot.user.id, inline=True)
        embed.add_field(name="Python Version", value=platform.python_version(), inline=True)
        embed.add_field(name="Discord.py Version", value=discord.__version__, inline=True)
        embed.add_field(name="Guilds", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="Commands", value=len(self.bot.commands), inline=True)
        embed.add_field(name="Uptime", value=f"<t:{int((discord.utils.utcnow() - datetime.timedelta(seconds=round(discord.utils.utcnow().timestamp() - self.bot.start_time.timestamp()))).timestamp())}:R>", inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="serverinfo", description="Show server information")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        embed = discord.Embed(
            title=f"{guild.name} Server Info",
            color=discord.Color.dark_blue()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Server Name", value=guild.name, inline=True)
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="Created At", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=False)
        embed.add_field(name="Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="serveremojis", description="List all custom emojis in the server")
    async def serveremojis(self, ctx: commands.Context):
        guild = ctx.guild
        emojis = guild.emojis
        
        if not emojis:
            await ctx.send("This server has no custom emojis.")
            return
        
        embed = discord.Embed(
            title=f"{guild.name} Emojis ({len(emojis)})",
            color=discord.Color.dark_blue()
        )
        
        animated = [str(e) for e in emojis if e.animated]
        static = [str(e) for e in emojis if not e.animated]
        
        if static:
            embed.add_field(name=f"Static ({len(static)})", value=" ".join(static[:25]) or "None", inline=False)
        if animated:
            embed.add_field(name=f"Animated ({len(animated)})", value=" ".join(animated[:25]) or "None", inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))

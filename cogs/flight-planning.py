import discord
from discord.ext import commands
import json
import os
import uuid

PLANS_FILE = "flight_plans.json"


class FlightPlanModal(discord.ui.Modal, title="Flight Plan"):
    departure = discord.ui.TextInput(
        label="Departure Airport",
        placeholder="e.g., OKBK, EGLL, KJFK",
        max_length=10,
        required, KJFK",
        max_length=10,
        required=True
    )
    arrival = discord.ui.TextInput(
        label="Arrival Airport",
        placeholder="e.g., OMDB, LFPG, KLAX",
        max_length=10,
        required=True
    )
    plane = discord.ui.TextInput(
        label="Plane",
        placeholder="e.g., A320, B777, C172",
        max_length=50,
        required=True
    )
    description = discord.ui.TextInput(
        label="Flight Description",
        placeholder="e.g., Short hop to Dubai, cargo run",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False
    )

    def __init__(self, bot, user_id):
        super().__init__()
        self.bot = bot
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        plan_id = str(uuid.uuid4())[:8]
        plan = {
            "plan_id": plan_id,
            "user_id": self.user_id,
            "departure": str(self.departure).upper(),
            "arrival": str(self.arrival).upper(),
            "plane": str(self.plane),
            "description": str(self.description) if self.description else "No description",
            "created_at": discord.utils.utcnow().isoformat()
        }

        plans = load_plans()
        plans.append(plan)
        save_plans(plans)

        embed = discord.Embed(
            title="✈️ Flight Plan Created",
            description=f"Plan ID: `{plan_id}`",
            color=discord.Color.green()
        )
        embed.add_field(name="Departure", value=plan["departure"], inline=True)
        embed.add_field(name="Arrival", value=plan["arrival"], inline=True)
        embed.add_field(name="Plane", value=plan["plane"], inline=True)
        embed.add_field(name="Description", value=plan["description"], inline=False)
        embed.set_footer(text=f"Planned by {interaction.user}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


def load_plans():
    if not os.path.exists(PLANS_FILE):
        return []
    with open(PLANS_FILE, "r") as f:
        return json.load(f)


def save_plans(plans):
    with open(PLANS_FILE, "w") as f:
        json.dump(plans, f, indent=2)


class FlightPlanning(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="flight-plan", description="Create a new flight plan")
    async def flight_plan(self, ctx: commands.Context):
        modal = FlightPlanModal(self.bot, ctx.author.id)
        await ctx.interaction.response.send_modal(modal)

    @commands.hybrid_command(name="flight-plan-cancel", description="Cancel your most recent flight plan")
    async def flight_plan_cancel(self, ctx: commands.Context):
        plans = load_plans()
        user_plans = [p for p in plans if p["user_id"] == ctx.author.id]

        if not user_plans:
            await ctx.send("You have no flight plans to cancel.", ephemeral=True)
            return

        most_recent = user_plans[-1]
        plans.remove(most_recent)
        save_plans(plans)

        embed = discord.Embed(
            title="🚫 Flight Plan Cancelled",
            description=f"Cancelled plan `{most_recent['plan_id']}`",
            color=discord.Color.orange()
        )
        embed.add_field(name="Route", value=f"{most_recent['departure']} → {most_recent['arrival']}", inline=True)
        embed.add_field(name="Plane", value=most_recent["plane"], inline=True)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="flight-plan-delete", description="Delete a specific flight plan by ID")
    @discord.app_commands.describe(plan_id="The ID of the flight plan to delete")
    async def flight_plan_delete(self, ctx: commands.Context, plan_id: str):
        plans = load_plans()
        plan = next((p for p in plans if p["plan_id"] == plan_id and p["user_id"] == ctx.author.id), None)

        if not plan:
            await ctx.send(f"No flight plan with ID `{plan_id}` found, or you don't own it.", ephemeral=True)
            return

        plans.remove(plan)
        save_plans(plans)

        embed = discord.Embed(
            title="🗑️ Flight Plan Deleted",
            description=f"Deleted plan `{plan_id}`",
            color=discord.Color.red()
        )
        embed.add_field(name="Route", value=f"{plan['departure']} → {plan['arrival']}", inline=True)
        embed.add_field(name="Plane", value=plan["plane"], inline=True)
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FlightPlanning(bot))

 import discord
from discord.ext import commands
import pymongo
import os
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URI)
db = client["kuwait_airways_ptfs"]
users_collection = db["users"]
inventory_collection = db["inventory"]
shop_collection = db["shop"]
cooldowns_collection = db["cooldowns"]

CURRENCY = "KWD"
CURRENCY_SYMBOL = "د.ك"


def get_user(user_id: int):
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        users_collection.insert_one({
            "user_id": user_id,
            "balance": 100.0,
            "bank": 0.0,
            "created_at": datetime.now(timezone.utc)
        })
        return users_collection.find_one({"user_id": user_id})
    return user


def get_balance(user_id: int) -> float:
    return get_user(user_id).get("balance", 0.0)


def get_bank(user_id: int) -> float:
    return get_user(user_id).get("bank", 0.0)


def update_balance(user_id: int, amount: float):
    get_user(user_id)
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}}
    )


def update_bank(user_id: int, amount: float):
    get_user(user_id)
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"bank": amount}}
    )


def get_cooldown(user_id: int, command: str) -> datetime:
    cd = cooldowns_collection.find_one({"user_id": user_id, "command": command})
    if cd:
        return cd.get("expires_at")
    return None


def set_cooldown(user_id: int, command: str, seconds: int):
    expires = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    cooldowns_collection.update_one(
        {"user_id": user_id, "command": command},
        {"$set": {"expires_at": expires}},
        upsert=True
    )


def get_inventory(user_id: int):
    return list(inventory_collection.find({"user_id": user_id}))


def add_item(user_id: int, item_id: str, quantity: int = 1):
    inventory_collection.update_one(
        {"user_id": user_id, "item_id": item_id},
        {"$inc": {"quantity": quantity}},
        upsert=True
    )


def remove_item(user_id: int, item_id: str, quantity: int = 1):
    inv = inventory_collection.find_one({"user_id": user_id, "item_id": item_id})
    if not inv or inv["quantity"] < quantity:
        return False
    inventory_collection.update_one(
        {"user_id": user_id, "item_id": item_id},
        {"$inc": {"quantity": -quantity}}
    )
    return True


def get_shop_items():
    return list(shop_collection.find())


def get_shop_item(item_id: str):
    return shop_collection.find_one({"item_id": item_id})


def add_shop_item(item_id: str, name: str, price: float, description: str, role_id: int = None):
    shop_collection.update_one(
        {"item_id": item_id},
        {"$set": {
            "name": name,
            "price": price,
            "description": description,
            "role_id": role_id,
            "created_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )


def remove_shop_item(item_id: str):
    shop_collection.delete_one({"item_id": item_id})


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", description="Check your KWD balance")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        bal = get_balance(target.id)
        bank = get_bank(target.id)
        embed = discord.Embed(
            title=f"💰 {target.display_name}'s Balance",
            color=discord.Color.gold()
        )
        embed.add_field(name="Wallet", value=f"{CURRENCY_SYMBOL}{bal:.3f} {CURRENCY}", inline=True)
        embed.add_field(name="Bank", value=f"{CURRENCY_SYMBOL}{bank:.3f} {CURRENCY}", inline=True)
        embed.add_field(name="Total", value=f"{CURRENCY_SYMBOL}{(bal + bank):.3f} {CURRENCY}", inline=True)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="daily", description="Claim your daily KWD reward")
    async def daily(self, ctx: commands.Context):
        cd = get_cooldown(ctx.author.id, "daily")
        if cd and cd > datetime.now(timezone.utc):
            remaining = int((cd - datetime.now(timezone.utc)).total_seconds())
            hours, remainder = divmod(remaining, 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(f"⏰ Daily already claimed! Come back in `{hours}h {minutes}m {seconds}s`.", ephemeral=True)
            return

        reward = random.randint(15, 50)
        update_balance(ctx.author.id, reward)
        set_cooldown(ctx.author.id, "daily", 86400)

        embed = discord.Embed(
            title="📅 Daily Reward",
            description=f"You claimed {CURRENCY_SYMBOL}{reward:.3f} {CURRENCY}!",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"{CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="work", description="Work to earn KWD")
    async def work(self, ctx: commands.Context):
        cd = get_cooldown(ctx.author.id, "work")
        if cd and cd > datetime.now(timezone.utc):
            remaining = int((cd - datetime.now(timezone.utc)).total_seconds())
            minutes, seconds = divmod(remaining, 60)
            await ctx.send(f"⏰ You're tired! Rest for `{minutes}m {seconds}s`.", ephemeral=True)
            return

        jobs = [
            ("Pilot", 20, 60),
            ("Flight Attendant", 15, 45),
            ("Ground Crew", 10, 35),
            ("Air Traffic Controller", 25, 75),
            ("Aircraft Mechanic", 18, 55),
            ("Baggage Handler", 8, 25),
            ("Check-in Agent", 12, 40),
            ("Catering Staff", 10, 30)
        ]
        job, min_pay, max_pay = random.choice(jobs)
        pay = random.randint(min_pay, max_pay)

        update_balance(ctx.author.id, pay)
        set_cooldown(ctx.author.id, "work", 1800)

        embed = discord.Embed(
            title="💼 Work Complete",
            description=f"You worked as a **{job}** and earned {CURRENCY_SYMBOL}{pay:.3f} {CURRENCY}!",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"{CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="rob", description="Rob another user (risky!)")
    async def rob(self, ctx: commands.Context, member: discord.Member):
        if member.id == ctx.author.id:
            await ctx.send("❌ You can't rob yourself!", ephemeral=True)
            return
        if member.bot:
            await ctx.send("❌ You can't rob bots!", ephemeral=True)
            return

        cd = get_cooldown(ctx.author.id, "rob")
        if cd and cd > datetime.now(timezone.utc):
            remaining = int((cd - datetime.now(timezone.utc)).total_seconds())
            minutes, seconds = divmod(remaining, 60)
            await ctx.send(f"⏰ You're being watched by security! Wait `{minutes}m {seconds}s`.", ephemeral=True)
            return

        target_bal = get_balance(member.id)
        if target_bal < 10:
            await ctx.send(f"❌ {member.display_name} is broke! Nothing to steal.", ephemeral=True)
            return

        my_bal = get_balance(ctx.author.id)
        if my_bal < 20:
            await ctx.send(f"❌ You need at least {CURRENCY_SYMBOL}20.000 {CURRENCY} to attempt a robbery!", ephemeral=True)
            return

        success = random.random() < 0.45
        if success:
            stolen = random.randint(5, min(int(target_bal * 0.4), 100))
            update_balance(ctx.author.id, stolen)
            update_balance(member.id, -stolen)
            set_cooldown(ctx.author.id, "rob", 3600)
            embed = discord.Embed(
                title="🦹 Robbery Successful!",
                description=f"You stole {CURRENCY_SYMBOL}{stolen:.3f} {CURRENCY} from {member.mention}!",
                color=discord.Color.green()
            )
        else:
            fine = random.randint(10, 30)
            update_balance(ctx.author.id, -fine)
            set_cooldown(ctx.author.id, "rob", 7200)
            embed = discord.Embed(
                title="🚔 Caught by Security!",
                description=f"You were caught and fined {CURRENCY_SYMBOL}{fine:.3f} {CURRENCY}!",
                color=discord.Color.red()
            )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="bj", description="Play Blackjack with KWD")
    async def bj(self, ctx: commands.Context, bet: float):
        if bet < 5:
            await ctx.send(f"❌ Minimum bet is {CURRENCY_SYMBOL}5.000 {CURRENCY}!", ephemeral=True)
            return
        if get_balance(ctx.author.id) < bet:
            await ctx.send(f"❌ You don't have enough {CURRENCY}!", ephemeral=True)
            return

        def card_value(hand):
            total = 0
            aces = 0
            for card in hand:
                if card in ["J", "Q", "K"]:
                    total += 10
                elif card == "A":
                    total += 11
                    aces += 1
                else:
                    total += card
            while total > 21 and aces > 0:
                total -= 10
                aces -= 1
            return total

        def draw_card():
            cards = ["A", 2, 3, 4, 5, 6, 7, 8, 9, 10, "J", "Q", "K"]
            suits = ["♠", "♥", "♦", "♣"]
            return f"{random.choice(cards)}{random.choice(suits)}"

        def hand_to_str(hand):
            return " ".join(str(c) for c in hand)

        player_hand = [draw_card(), draw_card()]
        dealer_hand = [draw_card(), draw_card()]

        player_val = card_value([c[:-1] for c in player_hand])
        dealer_val = card_value([c[:-1] for c in dealer_hand])

        embed = discord.Embed(
            title="🃏 Blackjack",
            color=discord.Color.dark_blue()
        )
        embed.add_field(name="Your Hand", value=f"{hand_to_str(player_hand)} (Value: {player_val})", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"{dealer_hand[0]} ??", inline=False)

        if player_val == 21:
            winnings = bet * 2.5
            update_balance(ctx.author.id, winnings)
            embed.add_field(name="Result", value=f"🎉 Blackjack! You win {CURRENCY_SYMBOL}{winnings:.3f} {CURRENCY}!", inline=False)
            await ctx.send(embed=embed, ephemeral=True)
            return

        view = discord.ui.View(timeout=60)
        hit_btn = discord.ui.Button(label="Hit", style=discord.ButtonStyle.primary)
        stand_btn = discord.ui.Button(label="Stand", style=discord.ButtonStyle.secondary)

        async def hit_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return
            player_hand.append(draw_card())
            pv = card_value([c[:-1] for c in player_hand])
            embed.set_field_at(0, name="Your Hand", value=f"{hand_to_str(player_hand)} (Value: {pv})", inline=False)
            if pv > 21:
                update_balance(ctx.author.id, -bet)
                embed.add_field(name="Result", value=f"💥 Bust! You lose {CURRENCY_SYMBOL}{bet:.3f} {CURRENCY}!", inline=False)
                for item in view.children:
                    item.disabled = True
                await interaction.response.edit_message(embed=embed, view=view)
                view.stop()
            else:
                await interaction.response.edit_message(embed=embed, view=view)

        async def stand_callback(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                return
            while card_value([c[:-1] for c in dealer_hand]) < 17:
                dealer_hand.append(draw_card())
            dv = card_value([c[:-1] for c in dealer_hand])
            pv = card_value([c[:-1] for c in player_hand])
            embed.set_field_at(1, name="Dealer's Hand", value=f"{hand_to_str(dealer_hand)} (Value: {dv})", inline=False)

            if dv > 21 or pv > dv:
                winnings = bet * 2
                update_balance(ctx.author.id, bet)
                result = f"🎉 You win {CURRENCY_SYMBOL}{bet:.3f} {CURRENCY}!"
            elif pv == dv:
                result = "🤝 Push! Your bet is returned."
            else:
                update_balance(ctx.author.id, -bet)
                result = f"😞 You lose {CURRENCY_SYMBOL}{bet:.3f} {CURRENCY}!"

            embed.add_field(name="Result", value=result, inline=False)
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(embed=embed, view=view)
            view.stop()

        hit_btn.callback = hit_callback
        stand_btn.callback = stand_callback
        view.add_item(hit_btn)
        view.add_item(stand_btn)

        await ctx.send(embed=embed, view=view, ephemeral=True)

    @commands.hybrid_command(name="updown", description="Guess if the number is higher or lower")
    async def updown(self, ctx: commands.Context, bet: float, guess: str):
        guess = guess.lower()
        if guess not in ["up", "down"]:
            await ctx.send("❌ Guess `up` or `down`!", ephemeral=True)
            return
        if bet < 1:
            await ctx.send(f"❌ Minimum bet is {CURRENCY_SYMBOL}1.000 {CURRENCY}!", ephemeral=True)
            return
        if get_balance(ctx.author.id) < bet:
            await ctx.send(f"❌ Insufficient balance!", ephemeral=True)
            return

        current = random.randint(1, 100)
        next_num = random.randint(1, 100)

        won = (guess == "up" and next_num > current) or (guess == "down" and next_num < current)

        embed = discord.Embed(
            title="📈 Up or Down?",
            description=f"Current number: **{current}**\nNext number: **{next_num}**",
            color=discord.Color.dark_blue()
        )

        if won:
            winnings = bet
            update_balance(ctx.author.id, winnings)
            embed.add_field(name="Result", value=f"🎉 Correct! You win {CURRENCY_SYMBOL}{winnings:.3f} {CURRENCY}!", inline=False)
        else:
            update_balance(ctx.author.id, -bet)
            embed.add_field(name="Result", value=f"😞 Wrong! You lose {CURRENCY_SYMBOL}{bet:.3f} {CURRENCY}!", inline=False)

        embed.add_field(name="New Balance", value=f"{CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="deposit", description="Deposit KWD to your bank")
    async def deposit(self, ctx: commands.Context, amount: float):
        bal = get_balance(ctx.author.id)
        if amount > bal:
            await ctx.send(f"❌ You only have {CURRENCY_SYMBOL}{bal:.3f} {CURRENCY} in your wallet!", ephemeral=True)
            return
        if amount <= 0:
            await ctx.send("❌ Invalid amount!", ephemeral=True)
            return

        update_balance(ctx.author.id, -amount)
        update_bank(ctx.author.id, amount)

        embed = discord.Embed(
            title="🏦 Deposit",
            description=f"Deposited {CURRENCY_SYMBOL}{amount:.3f} {CURRENCY} to your bank!",
            color=discord.Color.green()
        )
        embed.add_field(name="Wallet", value=f"{CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}", inline=True)
        embed.add_field(name="Bank", value=f"{CURRENCY_SYMBOL}{get_bank(ctx.author.id):.3f} {CURRENCY}", inline=True)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="withdraw", description="Withdraw KWD from your bank")
    async def withdraw(self, ctx: commands.Context, amount: float):
        bank = get_bank(ctx.author.id)
        if amount > bank:
            await ctx.send(f"❌ You only have {CURRENCY_SYMBOL}{bank:.3f} {CURRENCY} in your bank!", ephemeral=True)
            return
        if amount <= 0:
            await ctx.send("❌ Invalid amount!", ephemeral=True)
            return

        update_bank(ctx.author.id, -amount)
        update_balance(ctx.author.id, amount)

        embed = discord.Embed(
            title="🏧 Withdraw",
            description=f"Withdrew {CURRENCY_SYMBOL}{amount:.3f} {CURRENCY} from your bank!",
            color=discord.Color.green()
        )
        embed.add_field(name="Wallet", value=f"{CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}", inline=True)
        embed.add_field(name="Bank", value=f"{CURRENCY_SYMBOL}{get_bank(ctx.author.id):.3f} {CURRENCY}", inline=True)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="pay", description="Pay KWD to another user")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: float):
        if member.id == ctx.author.id:
            await ctx.send("❌ You can't pay yourself!", ephemeral=True)
            return
        if amount <= 0:
            await ctx.send("❌ Invalid amount!", ephemeral=True)
            return
        if get_balance(ctx.author.id) < amount:
            await ctx.send(f"❌ You don't have enough {CURRENCY}!", ephemeral=True)
            return

        update_balance(ctx.author.id, -amount)
        update_balance(member.id, amount)

        embed = discord.Embed(
            title="💸 Payment Sent",
            description=f"You paid {member.mention} {CURRENCY_SYMBOL}{amount:.3f} {CURRENCY}!",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="slots", description="Play slots with KWD")
    async def slots(self, ctx: commands.Context, bet: float):
        if bet < 1:
            await ctx.send(f"❌ Minimum bet is {CURRENCY_SYMBOL}1.000 {CURRENCY}!", ephemeral=True)
            return
        if get_balance(ctx.author.id) < bet:
            await ctx.send(f"❌ Insufficient balance!", ephemeral=True)
            return

        symbols = ["🍒", "🍋", "🍊", "💎", "✈️", "🛫", "🌙", "7️⃣"]
        reels = [random.choice(symbols) for _ in range(3)]

        embed = discord.Embed(
            title="🎰 Slots",
            description=f"| {reels[0]} | {reels[1]} | {reels[2]} |",
            color=discord.Color.gold()
        )

        if reels[0] == reels[1] == reels[2]:
            multiplier = 10 if reels[0] == "7️⃣" else 5 if reels[0] == "💎" else 3
            winnings = bet * multiplier
            update_balance(ctx.author.id, winnings)
            embed.add_field(name="Result", value=f"🎉 JACKPOT! {multiplier}x! You win {CURRENCY_SYMBOL}{winnings:.3f} {CURRENCY}!", inline=False)
        elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            winnings = bet
            update_balance(ctx.author.id, winnings)
            embed.add_field(name="Result", value=f"✨ Match! You win {CURRENCY_SYMBOL}{winnings:.3f} {CURRENCY}!", inline=False)
        else:
            update_balance(ctx.author.id, -bet)
            embed.add_field(name="Result", value=f"😞 No match! You lose {CURRENCY_SYMBOL}{bet:.3f} {CURRENCY}!", inline=False)

        embed.add_field(name="Balance", value=f"{CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="coinflip", description="Flip a coin with KWD")
    async def coinflip(self, ctx: commands.Context, bet: float, choice: str):
        choice = choice.lower()
        if choice not in ["heads", "tails"]:
            await ctx.send("❌ Choose `heads` or `tails`!", ephemeral=True)
            return
        if bet < 1:
            await ctx.send(f"❌ Minimum bet is {CURRENCY_SYMBOL}1.000 {CURRENCY}!", ephemeral=True)
            return
        if get_balance(ctx.author.id) < bet:
            await ctx.send(f"❌ Insufficient balance!", ephemeral=True)
            return

        result = random.choice(["heads", "tails"])
        won = choice == result

        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"The coin landed on **{result}**!",
            color=discord.Color.gold()
        )

        if won:
            winnings = bet
            update_balance(ctx.author.id, winnings)
            embed.add_field(name="Result", value=f"🎉 You win {CURRENCY_SYMBOL}{winnings:.3f} {CURRENCY}!", inline=False)
        else:
            update_balance(ctx.author.id, -bet)
            embed.add_field(name="Result", value=f"😞 You lose {CURRENCY_SYMBOL}{bet:.3f} {CURRENCY}!", inline=False)

        embed.add_field(name="Balance", value=f"{CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="leaderboard", description="View the richest users")
    async def leaderboard(self, ctx: commands.Context):
        top_users = users_collection.find().sort("balance", -1).limit(10)
        embed = discord.Embed(
            title="🏆 Kuwait Airways Economy Leaderboard",
            color=discord.Color.gold()
        )
        rank = 1
        for user in top_users:
            member = ctx.guild.get_member(user["user_id"])
            name = member.display_name if member else f"User {user['user_id']}"
            total = user.get("balance", 0) + user.get("bank", 0)
            embed.add_field(
                name=f"#{rank} {name}",
                value=f"{CURRENCY_SYMBOL}{total:.3f} {CURRENCY}",
                inline=False
            )
            rank += 1
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="shop", description="View the item shop")
    async def shop(self, ctx: commands.Context):
        items = get_shop_items()
        if not items:
            await ctx.send("🛒 The shop is currently empty.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛒 Kuwait Airways Shop",
            description=f"Your balance: {CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}",
            color=discord.Color.dark_blue()
        )
        for item in items:
            embed.add_field(
                name=f"{item['name']} (`{item['item_id']}`)",
                value=f"Price: {CURRENCY_SYMBOL}{item['price']:.3f} {CURRENCY}\n{item['description']}",
                inline=False
            )
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="buy", description="Buy an item from the shop")
    @discord.app_commands.describe(item_id="The ID of the item to buy", quantity="How many to buy (default: 1)")
    async def buy(self, ctx: commands.Context, item_id: str, quantity: int = 1):
        item = get_shop_item(item_id)
        if not item:
            await ctx.send(f"❌ Item `{item_id}` not found in the shop!", ephemeral=True)
            return

        total = item["price"] * quantity
        if get_balance(ctx.author.id) < total:
            await ctx.send(f"❌ You need {CURRENCY_SYMBOL}{total:.3f} {CURRENCY} but only have {CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}!", ephemeral=True)
            return

        update_balance(ctx.author.id, -total)
        add_item(ctx.author.id, item_id, quantity)

        embed = discord.Embed(
            title="🛒 Purchase Complete",
            description=f"You bought **{quantity}x {item['name']}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Total Paid", value=f"{CURRENCY_SYMBOL}{total:.3f} {CURRENCY}", inline=True)
        embed.add_field(name="New Balance", value=f"{CURRENCY_SYMBOL}{get_balance(ctx.author.id):.3f} {CURRENCY}", inline=True)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="inventory", description="View your inventory")
    async def inventory(self, ctx: commands.Context):
        inv = get_inventory(ctx.author.id)
        if not inv:
            await ctx.send("📭 Your inventory is empty.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎒 {ctx.author.display_name}'s Inventory",
            color=discord.Color.dark_blue()
        )
        for item in inv:
            shop_item = get_shop_item(item["item_id"])
            name = shop_item["name"] if shop_item else item["item_id"]
            embed.add_field(name=f"{name} (x{item['quantity']})", value=f"ID: `{item['item_id']}`", inline=True)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="shop-add", description="[ADMIN] Add an item to the shop")
    @commands.has_permissions(administrator=True)
    async def shop_add(self, ctx: commands.Context, item_id: str, price: float, *, name_and_desc: str):
        parts = name_and_desc.split("|", 1)
        name = parts[0].strip()
        desc = parts[1].strip() if len(parts) > 1 else "No description"
        add_shop_item(item_id, name, price, desc)
        await ctx.send(f"✅ Added `{item_id}` to the shop: **{name}** for {CURRENCY_SYMBOL}{price:.3f} {CURRENCY}!", ephemeral=True)

    @commands.hybrid_command(name="shop-remove", description="[ADMIN] Remove an item from the shop")
    @commands.has_permissions(administrator=True)
    async def shop_remove(self, ctx: commands.Context, item_id: str):
        remove_shop_item(item_id)
        await ctx.send(f"🗑️ Removed `{item_id}` from the shop!", ephemeral=True)

    @commands.hybrid_command(name="give", description="[ADMIN] Give KWD to a user")
    @commands.has_permissions(administrator=True)
    async def give(self, ctx: commands.Context, member: discord.Member, amount: float):
        update_balance(member.id, amount)
        await ctx.send(f"💰 Gave {CURRENCY_SYMBOL}{amount:.3f} {CURRENCY} to {member.mention}!", ephemeral=True)

    @commands.hybrid_command(name="take", description="[ADMIN] Take KWD from a user")
    @commands.has_permissions(administrator=True)
    async def take(self, ctx: commands.Context, member: discord.Member, amount: float):
        update_balance(member.id, -amount)
        await ctx.send(f"💸 Took {CURRENCY_SYMBOL}{amount:.3f} {CURRENCY} from {member.mention}!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Economy(bot))

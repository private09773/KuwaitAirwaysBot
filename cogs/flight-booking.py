import discord
from discord.ext import commands
import pymongo
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = pymongo.MongoClient(MONGO_URI)
db = client["kuwait_airways_ptfs"]
users_collection = db["users"]
flights_collection = db["flights"]
bookings_collection = db["bookings"]

CURRENCY = "KWD"  # Kuwaiti Dinar
CURRENCY_SYMBOL = "د.ك"


def get_user_balance(user_id: int) -> float:
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        users_collection.insert_one({
            "user_id": user_id,
            "balance": 0.0,
            "created_at": datetime.now(timezone.utc)
        })
        return 0.0
    return user.get("balance", 0.0)


def update_balance(user_id: int, amount: float):
    users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"balance": amount}},
        upsert=True
    )


def get_available_flights():
    return list(flights_collection.find({"available_seats": {"$gt": 0}}))


def get_flight(flight_id: str):
    return flights_collection.find_one({"flight_id": flight_id})


def create_booking(user_id: int, flight_id: str, passengers: list) -> dict:
    flight = get_flight(flight_id)
    if not flight or flight["available_seats"] < len(passengers):
        return None

    total_price = flight["price_kwd"] * len(passengers)
    booking = {
        "booking_id": f"BKG-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{user_id}",
        "user_id": user_id,
        "flight_id": flight_id,
        "passengers": passengers,
        "total_price_kwd": total_price,
        "status": "confirmed",
        "booked_at": datetime.now(timezone.utc)
    }

    bookings_collection.insert_one(booking)
    flights_collection.update_one(
        {"flight_id": flight_id},
        {"$inc": {"available_seats": -len(passengers)}}
    )
    update_balance(user_id, -total_price)

    return booking


def cancel_booking(user_id: int, booking_id: str) -> dict:
    booking = bookings_collection.find_one({
        "booking_id": booking_id,
        "user_id": user_id,
        "status": "confirmed"
    })
    if not booking:
        return None

    refund_amount = booking["total_price_kwd"]
    flights_collection.update_one(
        {"flight_id": booking["flight_id"]},
        {"$inc": {"available_seats": len(booking["passengers"])}}
    )
    bookings_collection.update_one(
        {"booking_id": booking_id},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc)}}
    )
    update_balance(user_id, refund_amount)

    return booking


def get_user_bookings(user_id: int):
    return list(bookings_collection.find({
        "user_id": user_id,
        "status": "confirmed"
    }).sort("booked_at", -1))


class BookFlightView(discord.ui.View):
    def __init__(self, flights):
        super().__init__(timeout=120)
        self.flights = flights

        options = []
        for flight in flights[:25]:
            dep = flight["departure_airport"]
            arr = flight["arrival_airport"]
            price = flight["price_kwd"]
            seats = flight["available_seats"]
            options.append(discord.SelectOption(
                label=f"{dep} → {arr} | {CURRENCY_SYMBOL}{price:.3f}",
                description=f"Plane: {flight['plane']} | Seats: {seats}",
                value=flight["flight_id"]
            ))

        if options:
            select = discord.ui.Select(
                placeholder="Select a flight to book...",
                options=options
            )
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        flight_id = interaction.data["values"][0]
        self.selected_flight = flight_id
        await interaction.response.send_message(
            "How many passengers? (Reply with a number, max 5)",
            ephemeral=True
        )
        self.stop()


class PassengerModal(discord.ui.Modal, title="Passenger Details"):
    passenger_1 = discord.ui.TextInput(
        label="Passenger 1 (Full Name)",
        placeholder="e.g., Ahmad Al-Sabah",
        max_length=100,
        required=True
    )
    passenger_2 = discord.ui.TextInput(
        label="Passenger 2 (Optional)",
        placeholder="Leave blank if not needed",
        max_length=100,
        required=False
    )
    passenger_3 = discord.ui.TextInput(
        label="Passenger 3 (Optional)",
        placeholder="Leave blank if not needed",
        max_length=100,
        required=False
    )

    def __init__(self, flight_id: str, user_id: int):
        super().__init__()
        self.flight_id = flight_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        passengers = [str(p) for p in [self.passenger_1, self.passenger_2, self.passenger_3] if p.value.strip()]
        flight = get_flight(self.flight_id)
        total = flight["price_kwd"] * len(passengers)
        balance = get_user_balance(self.user_id)

        if balance < total:
            await interaction.response.send_message(
                f"❌ Insufficient balance! You have {CURRENCY_SYMBOL}{balance:.3f} {CURRENCY}, "
                f"but the total is {CURRENCY_SYMBOL}{total:.3f} {CURRENCY}.",
                ephemeral=True
            )
            return

        booking = create_booking(self.user_id, self.flight_id, passengers)
        if booking:
            embed = discord.Embed(
                title="✅ Flight Booked Successfully",
                color=discord.Color.green()
            )
            embed.add_field(name="Booking ID", value=f"`{booking['booking_id']}`", inline=False)
            embed.add_field(name="Flight", value=f"{flight['departure_airport']} → {flight['arrival_airport']}", inline=True)
            embed.add_field(name="Plane", value=flight["plane"], inline=True)
            embed.add_field(name="Passengers", value="\n".join(f"• {p}" for p in passengers), inline=False)
            embed.add_field(name="Total Paid", value=f"{CURRENCY_SYMBOL}{total:.3f} {CURRENCY}", inline=True)
            embed.add_field(name="Remaining Balance", value=f"{CURRENCY_SYMBOL}{get_user_balance(self.user_id):.3f} {CURRENCY}", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Booking failed. Flight may be full.", ephemeral=True)


class FlightBooking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="book", description="Book a flight using Kuwaiti Dinar (KWD)")
    async def book(self, ctx: commands.Context):
        flights = get_available_flights()
        if not flights:
            await ctx.send("❌ No available flights at the moment.", ephemeral=True)
            return

        embed = discord.Embed(
            title="✈️ Kuwait Airways PTFS — Available Flights",
            description=f"Your balance: {CURRENCY_SYMBOL}{get_user_balance(ctx.author.id):.3f} {CURRENCY}",
            color=discord.Color.dark_blue()
        )
        for flight in flights[:5]:
            embed.add_field(
                name=f"{flight['flight_id']}: {flight['departure_airport']} → {flight['arrival_airport']}",
                value=f"Plane: {flight['plane']} | Price: {CURRENCY_SYMBOL}{flight['price_kwd']:.3f} {CURRENCY} per passenger | Seats: {flight['available_seats']}",
                inline=False
            )

        view = BookFlightView(flights)
        await ctx.send(embed=embed, view=view, ephemeral=True)

        await view.wait()
        if hasattr(view, 'selected_flight'):
            modal = PassengerModal(view.selected_flight, ctx.author.id)
            await ctx.interaction.response.send_modal(modal)

    @commands.hybrid_command(name="cancel", description="Cancel a booking and get refunded in KWD")
    @discord.app_commands.describe(booking_id="Your booking ID to cancel")
    async def cancel(self, ctx: commands.Context, booking_id: str):
        booking = cancel_booking(ctx.author.id, booking_id)
        if not booking:
            await ctx.send(f"❌ Booking `{booking_id}` not found or already cancelled.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔄 Booking Cancelled & Refunded",
            color=discord.Color.orange()
        )
        embed.add_field(name="Booking ID", value=f"`{booking_id}`", inline=False)
        embed.add_field(name="Refund Amount", value=f"{CURRENCY_SYMBOL}{booking['total_price_kwd']:.3f} {CURRENCY}", inline=True)
        embed.add_field(name="New Balance", value=f"{CURRENCY_SYMBOL}{get_user_balance(ctx.author.id):.3f} {CURRENCY}", inline=True)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="myflights", description="View all your confirmed flight bookings")
    async def myflights(self, ctx: commands.Context):
        bookings = get_user_bookings(ctx.author.id)
        if not bookings:
            await ctx.send("📭 You have no active bookings.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎫 Your Kuwait Airways Bookings",
            color=discord.Color.dark_blue()
        )
        for booking in bookings[:10]:
            flight = get_flight(booking["flight_id"])
            route = f"{flight['departure_airport']} → {flight['arrival_airport']}" if flight else "Unknown"
            embed.add_field(
                name=f"`{booking['booking_id']}`",
                value=f"Route: {route}\nPassengers: {len(booking['passengers'])}\nTotal: {CURRENCY_SYMBOL}{booking['total_price_kwd']:.3f} {CURRENCY}\nBooked: <t:{int(booking['booked_at'].timestamp())}:R>",
                inline=False
            )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="passengers", description="View passengers for a specific booking")
    @discord.app_commands.describe(booking_id="Your booking ID")
    async def passengers(self, ctx: commands.Context, booking_id: str):
        booking = bookings_collection.find_one({
            "booking_id": booking_id,
            "user_id": ctx.author.id
        })
        if not booking:
            await ctx.send(f"❌ Booking `{booking_id}` not found.", ephemeral=True)
            return

        flight = get_flight(booking["flight_id"])
        embed = discord.Embed(
            title=f"👥 Passengers — {booking_id}",
            color=discord.Color.dark_blue()
        )
        if flight:
            embed.add_field(name="Flight", value=f"{flight['departure_airport']} → {flight['arrival_airport']}", inline=False)
        embed.add_field(name="Passengers", value="\n".join(f"• {p}" for p in booking["passengers"]), inline=False)
        embed.add_field(name="Status", value=booking["status"].title(), inline=True)
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FlightBooking(bot))

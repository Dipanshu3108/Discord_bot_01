import discord
from discord.ext import commands
import json
from datetime import datetime
from configToken import DISCORD_BOT_TOKEN

bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())

class LeaderboardBot:
    def __init__(self):
        self.scores_file = "scores.json"
        self.auth_file = "authorized_users.json"
        self.scores = self.load_scores()
        self.authorized_users = self.load_authorized_users()
        self.valid_categories = ["spedness", "helpfulness"]

    def load_scores(self):
        try:
            with open(self.scores_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def save_scores(self):
        with open(self.scores_file, "w") as f:
            json.dump(self.scores, f, indent=4)

    def load_authorized_users(self):
        try:
            with open(self.auth_file, "r") as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()

    def save_authorized_users(self):
        with open(self.auth_file, "w") as f:
            json.dump(list(self.authorized_users), f, indent=4)

    def modify_points(self, user_id: str, category: str, increment: bool):
        if user_id not in self.scores:
            self.scores[user_id] = {"categories": {}, "history": []}
        
        if category not in self.scores[user_id]["categories"]:
            self.scores[user_id]["categories"][category] = 0
        
        points_change = 1 if increment else -1
        self.scores[user_id]["categories"][category] += points_change
        
        self.scores[user_id]["history"].append({
            "category": category,
            "points": points_change,
            "timestamp": str(datetime.now())
        })
        
        self.save_scores()
        return self.scores[user_id]["categories"][category]

leaderboard_bot = LeaderboardBot()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

def is_authorized(ctx):
    return ctx.author.id in leaderboard_bot.authorized_users

@bot.command(name="authorize")
async def authorize_user(ctx, member: discord.Member):
    """Authorize a user to use bot commands (Admin only)"""
    if ctx.author.guild_permissions.administrator:
        leaderboard_bot.authorized_users.add(member.id)
        leaderboard_bot.save_authorized_users()
        await ctx.send(f"{member.mention} has been authorized!")
    else:
        await ctx.send("You do not have permission to authorize users!")

@bot.command(name="unauthorize")
async def unauthorize_user(ctx, member: discord.Member):
    """Remove a user's authorization (Admin only)"""
    if ctx.author.guild_permissions.administrator:
        leaderboard_bot.authorized_users.discard(member.id)
        leaderboard_bot.save_authorized_users()
        await ctx.send(f"{member.mention} has been unauthorized!")
    else:
        await ctx.send("You do not have permission to unauthorize users!")

@bot.command(name="add")
async def add_score(ctx, member: discord.Member, category: str):
    """Add one point to a category (Authorized only)"""
    if not is_authorized(ctx):
        await ctx.send("You are not authorized to use this command!")
        return

    category = category.lower()
    if category not in leaderboard_bot.valid_categories:
        await ctx.send(f"Invalid category! Valid categories are: spedness, helpfulness")
        return

    total_points = leaderboard_bot.modify_points(str(member.id), category, True)
    
    embed = discord.Embed(
        title="Point Added!",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Category", value=category.title(), inline=True)
    embed.add_field(name="New Total", value=str(total_points), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="remove")
async def remove_score(ctx, member: discord.Member, category: str):
    """Remove one point from a category (Authorized only)"""
    if not is_authorized(ctx):
        await ctx.send("You are not authorized to use this command!")
        return

    category = category.lower()
    if category not in leaderboard_bot.valid_categories:
        await ctx.send(f"Invalid category! Valid categories are: spedness, helpfulness")
        return

    total_points = leaderboard_bot.modify_points(str(member.id), category, False)
    
    embed = discord.Embed(
        title="Point Removed!",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Category", value=category.title(), inline=True)
    embed.add_field(name="New Total", value=str(total_points), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb"])
async def show_leaderboard(ctx, category: str):
    """Show the server leaderboard for a specific category"""
    if not is_authorized(ctx):
        await ctx.send("You are not authorized to use this command!")
        return

    category = category.lower()
    if category not in leaderboard_bot.valid_categories:
        await ctx.send(f"Invalid category! Valid categories are: spedness, helpfulness")
        return
    
    sorted_scores = []
    for user_id, data in leaderboard_bot.scores.items():
        points = data["categories"].get(category, 0)
        sorted_scores.append((user_id, points))
    
    sorted_scores.sort(key=lambda x: x[1], reverse=True)
    
    embed = discord.Embed(
        title=f"🏆 {category.title()} Leaderboard",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    for rank, (user_id, points) in enumerate(sorted_scores[:10], start=1):
        user = await bot.fetch_user(int(user_id))
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "👑"
        embed.add_field(
            name=f"{medal} Rank #{rank}",
            value=f"{user.mention}\n**Points:** {points}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name="stats")
async def show_stats(ctx, member: discord.Member = None):
    """Show stats for a user"""
    if not is_authorized(ctx):
        await ctx.send("You are not authorized to use this command!")
        return

    if member is None:
        member = ctx.author
    
    user_id = str(member.id)
    if user_id not in leaderboard_bot.scores:
        await ctx.send(f"{member.name} has no points yet!")
        return
    
    data = leaderboard_bot.scores[user_id]
    
    embed = discord.Embed(
        title=f"Stats for {member.name}",
        color=member.color,
        timestamp=datetime.now()
    )
    
    for category in leaderboard_bot.valid_categories:
        points = data["categories"].get(category, 0)
        embed.add_field(name=f"{category.title()}", value=str(points), inline=True)
    
    if data["history"]:
        last_5_changes = data["history"][-5:]
        history_text = "\n".join(
            f"{entry['points']:+d} {entry['category']} on {entry['timestamp'][:16]}"
            for entry in last_5_changes
        )
        embed.add_field(name="Recent Changes", value=history_text, inline=False)
    
    await ctx.send(embed=embed)
    
@bot.command(name="help")
async def help_command(ctx):
    """Displays a list of available commands"""
    embed = discord.Embed(
        title="Help - Available Commands",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="!add @user category",
        value="Adds 1 point to a specified category (e.g., spedness or helpfulness).",
        inline=False
    )
    embed.add_field(
        name="!remove @user category",
        value="Removes 1 point from a specified category (e.g., spedness or helpfulness).",
        inline=False
    )
    embed.add_field(
        name="!stats [@user]",
        value="Displays stats for a specified user. Defaults to the command sender if no user is mentioned.",
        inline=False
    )
    embed.add_field(
        name="!leaderboard category",
        value="Shows the leaderboard for a specific category (e.g., spedness or helpfulness).",
        inline=False
    )
    embed.add_field(
        name="!authorize @user",
        value="Authorizes a user to use bot commands. (Admin only)",
        inline=False
    )
    embed.add_field(
        name="!unauthorize @user",
        value="Revokes a user's authorization to use bot commands. (Admin only)",
        inline=False
    )
    embed.set_footer(
        text="Replace `category` with either `spedness` or `helpfulness` where applicable."
    )
    await ctx.send(embed=embed)


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        raise ValueError("Please set the DISCORD_BOT_TOKEN environment variable")
    bot.run(DISCORD_BOT_TOKEN)

# todo
# assign bot to specific users
# /help for commands

# running
# !add @user spedness - Adds 1 point to spedness
# !remove @user spedness - Removes 1 point from spedness
# !stats [@user] - Shows all categories for a user
# !leaderboard spedness or !leaderboard helpfulness - Shows category-specific leaderboard
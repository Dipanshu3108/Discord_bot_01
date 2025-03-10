import discord
from discord import app_commands
from typing import List
from discord.ext import commands
import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from random_messages import response_handler

# Load environment variables from tokens.env
load_dotenv("tokens.env")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("LeaderboardBot")

# Define intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Create bot with slash commands support
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

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
            logger.info(f"Scores file not found. Creating new scores dictionary.")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Failed to parse {self.scores_file}. Creating backup and new file.")
            # Create a backup of the corrupted file
            if os.path.exists(self.scores_file):
                os.rename(self.scores_file, f"{self.scores_file}.bak.{int(datetime.now().timestamp())}")
            return {}

    def save_scores(self):
        try:
            # Create a temporary file first to prevent data loss if the program crashes during writing
            temp_file = f"{self.scores_file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(self.scores, f, indent=4)
            
            # Replace the original file with the temporary file
            if os.path.exists(temp_file):
                if os.path.exists(self.scores_file):
                    os.remove(self.scores_file)
                os.rename(temp_file, self.scores_file)
                
            logger.info("Scores saved successfully")
        except Exception as e:
            logger.error(f"Error saving scores: {e}")

    def load_authorized_users(self):
        try:
            with open(self.auth_file, "r") as f:
                return set(json.load(f))
        except FileNotFoundError:
            logger.info(f"Auth file not found. Creating new authorized users set.")
            return set()
        except json.JSONDecodeError:
            logger.error(f"Failed to parse {self.auth_file}. Creating backup and new file.")
            # Create a backup of the corrupted file
            if os.path.exists(self.auth_file):
                os.rename(self.auth_file, f"{self.auth_file}.bak.{int(datetime.now().timestamp())}")
            return set()

    def save_authorized_users(self):
        try:
            temp_file = f"{self.auth_file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(list(self.authorized_users), f, indent=4)
            
            if os.path.exists(temp_file):
                if os.path.exists(self.auth_file):
                    os.remove(self.auth_file)
                os.rename(temp_file, self.auth_file)
                
            logger.info("Authorized users saved successfully")
        except Exception as e:
            logger.error(f"Error saving authorized users: {e}")

    def modify_points(self, user_id: str, category: str, increment: bool):
        if user_id not in self.scores:
            self.scores[user_id] = {"categories": {}, "history": []}
        
        if category not in self.scores[user_id]["categories"]:
            self.scores[user_id]["categories"][category] = 0
        
        points_change = 1 if increment else -1
        self.scores[user_id]["categories"][category] += points_change
        
        # Add timestamp in ISO format for better readability and parsing
        timestamp = datetime.now().isoformat(timespec='minutes')
        
        self.scores[user_id]["history"].append({
            "category": category,
            "points": points_change,
            "timestamp": timestamp
        })
        
        self.save_scores()
        return self.scores[user_id]["categories"][category]

    def get_user_rank(self, user_id: str, category: str):
        if category not in self.valid_categories:
            return None
        
        # Build a list of (user_id, points) tuples
        all_scores = []
        for uid, data in self.scores.items():
            points = data["categories"].get(category, 0)
            all_scores.append((uid, points))
        
        # Sort by points (descending)
        all_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Find the user's position
        for rank, (uid, _) in enumerate(all_scores, start=1):
            if uid == user_id:
                return rank
        
        return None  # User not found in rankings
        
    def get_categories(self):
        """Return a list of valid categories for autocomplete"""
        return self.valid_categories

# Create an instance of our bot class
leaderboard_bot = LeaderboardBot()

# Store the tree command globally for use across the bot
command_tree = None

def is_authorized(interaction: discord.Interaction):
    """Check if a user is authorized to use the bot commands"""
    return (interaction.user.guild_permissions.administrator or 
            interaction.user.id in leaderboard_bot.authorized_users)

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    logger.info(f'{bot.user} has connected to Discord!')
    
    # Set bot status to show it's online and listening for commands
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, 
        name="for /commands"
    ))
    
    # Log the invite URL for the bot
    logger.info(f"Invite URL: https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=2147483648&scope=bot%20applications.commands")

# Set up the slash commands
@bot.event
async def setup_hook():
    """This is called before on_ready and is used to set up the bot"""
    global command_tree
    # Set up the app commands tree for the bot
    command_tree = bot.tree
    
    # Sync commands with Discord
    await command_tree.sync()
    logger.info("Slash commands synced with Discord")
    
# Define autocomplete functions for category choices
async def category_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    """Provide autocomplete for category parameters"""
    categories = leaderboard_bot.get_categories()
    return [
        app_commands.Choice(name=category, value=category)
        for category in categories if current.lower() in category.lower()
    ]

async def authorized_check(interaction: discord.Interaction):
    """Check if a user is authorized and respond appropriately"""
    if not is_authorized(interaction):
        # Use random funny response instead of standard message
        response = response_handler.get_random_response()
        await interaction.response.send_message(response)
        return False
    return True

@bot.tree.command(name="authorize", description="Authorize a user to use bot commands (Admin only)")
@app_commands.describe(member="The user to authorize")
async def authorize_user(interaction: discord.Interaction, member: discord.Member):
    """Authorize a user to use bot commands (Admin only)"""
    # Check if the user is an admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You do not have permission to authorize users!", ephemeral=True)
        return

    # Convert member.id to integer to ensure consistency
    leaderboard_bot.authorized_users.add(member.id)
    leaderboard_bot.save_authorized_users()
    
    embed = discord.Embed(
        title="✅ User Authorized",
        description=f"{member.mention} has been authorized to use leaderboard commands!",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    await interaction.response.send_message(embed=embed)
    logger.info(f"{interaction.user} authorized {member} to use commands")

@bot.tree.command(name="unauthorize", description="Remove a user's authorization (Admin only)")
@app_commands.describe(member="The user to unauthorize")
async def unauthorize_user(interaction: discord.Interaction, member: discord.Member):
    """Remove a user's authorization (Admin only)"""
    # Check if the user is an admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You do not have permission to unauthorize users!", ephemeral=True)
        return

    leaderboard_bot.authorized_users.discard(member.id)
    leaderboard_bot.save_authorized_users()
    
    embed = discord.Embed(
        title="🚫 User Unauthorized",
        description=f"{member.mention} has been unauthorized from using leaderboard commands.",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    await interaction.response.send_message(embed=embed)
    logger.info(f"{interaction.user} unauthorized {member} from using commands")

@bot.tree.command(name="add", description="Add one point to a category")
@app_commands.describe(
    member="The user to add points to",
    category="The category to add points to (spedness or helpfulness)"
)
@app_commands.autocomplete(category=category_autocomplete)
async def add_score(interaction: discord.Interaction, member: discord.Member, category: str):
    """Add one point to a category"""
    # Check if the user is authorized
    if not await authorized_check(interaction):
        return

    category = category.lower()
    if category not in leaderboard_bot.valid_categories:
        categories_list = ", ".join(leaderboard_bot.valid_categories)
        await interaction.response.send_message(f"❌ Invalid category! Valid categories are: {categories_list}", ephemeral=True)
        return

    # Check if trying to add points to the bot
    if member.id == bot.user.id:
        if category == "spedness":
            await interaction.response.send_message("Don't take me for a fool, you Nigesh😡🤬")
            return
        elif category == "helpfulness":
            total_points = leaderboard_bot.modify_points(str(member.id), category, True)
            embed = discord.Embed(
                title="Point Added!",
                description="Thank you for recognizing my help! 🤖❤️",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Category", value=category.title(), inline=True)
            embed.add_field(name="New Total", value=str(total_points), inline=True)
            await interaction.response.send_message(embed=embed)
            return

    # Regular point addition for non-bot users
    total_points = leaderboard_bot.modify_points(str(member.id), category, True)
    
    # Get the user's new rank for this category
    rank = leaderboard_bot.get_user_rank(str(member.id), category)
    rank_display = f" (Rank #{rank})" if rank else ""
    
    embed = discord.Embed(
        title="🎉 Point Added!",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Category", value=category.title(), inline=True)
    embed.add_field(name="New Total", value=f"{total_points}{rank_display}", inline=True)
    
    await interaction.response.send_message(embed=embed)
    logger.info(f"{interaction.user} added 1 {category} point to {member}")

@bot.tree.command(name="remove", description="Remove one point from a category")
@app_commands.describe(
    member="The user to remove points from",
    category="The category to remove points from (spedness or helpfulness)"
)
@app_commands.autocomplete(category=category_autocomplete)
async def remove_score(interaction: discord.Interaction, member: discord.Member, category: str):
    """Remove one point from a category"""
    # Check if the user is authorized
    if not await authorized_check(interaction):
        return

    category = category.lower()
    if category not in leaderboard_bot.valid_categories:
        categories_list = ", ".join(leaderboard_bot.valid_categories)
        await interaction.response.send_message(f"❌ Invalid category! Valid categories are: {categories_list}", ephemeral=True)
        return

    total_points = leaderboard_bot.modify_points(str(member.id), category, False)
    
    # Get the user's new rank for this category
    rank = leaderboard_bot.get_user_rank(str(member.id), category)
    rank_display = f" (Rank #{rank})" if rank else ""
    
    embed = discord.Embed(
        title="⬇️ Point Removed!",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Category", value=category.title(), inline=True)
    embed.add_field(name="New Total", value=f"{total_points}{rank_display}", inline=True)
    
    await interaction.response.send_message(embed=embed)
    logger.info(f"{interaction.user} removed 1 {category} point from {member}")

@bot.tree.command(name="leaderboard", description="Show the server leaderboard for a specific category")
@app_commands.describe(category="The category to show the leaderboard for (spedness or helpfulness)")
@app_commands.autocomplete(category=category_autocomplete)
async def show_leaderboard(interaction: discord.Interaction, category: str):
    """Show the server leaderboard for a specific category"""
    # Check if the user is authorized
    if not await authorized_check(interaction):
        return

    category = category.lower()
    if category not in leaderboard_bot.valid_categories:
        categories_list = ", ".join(leaderboard_bot.valid_categories)
        await interaction.response.send_message(f"❌ Invalid category! Valid categories are: {categories_list}", ephemeral=True)
        return
    
    sorted_scores = []
    for user_id, data in leaderboard_bot.scores.items():
        points = data["categories"].get(category, 0)
        # Only include users with points
        if points > 0:
            sorted_scores.append((user_id, points))
    
    sorted_scores.sort(key=lambda x: x[1], reverse=True)
    
    if not sorted_scores:
        await interaction.response.send_message(f"No scores found for category: {category.title()}")
        return
    
    embed = discord.Embed(
        title=f"🏆 {category.title()} Leaderboard",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    
    # Cache users to avoid rate limiting
    user_cache = {}
    
    for rank, (user_id, points) in enumerate(sorted_scores[:10], start=1):
        # Get user from cache or fetch if not in cache
        if user_id not in user_cache:
            try:
                user = await bot.fetch_user(int(user_id))
                user_cache[user_id] = user
            except discord.NotFound:
                user_cache[user_id] = f"Unknown User ({user_id})"
            except Exception as e:
                logger.error(f"Error fetching user {user_id}: {e}")
                user_cache[user_id] = f"User {user_id}"
        
        user = user_cache[user_id]
        
        # Add rank emoji with custom emojis from original code
        medal = "🫂🥇🫂" if rank == 1 else "🫂🥈🫂" if rank == 2 else "🫂🥉🫂" if rank == 3 else "🌱"
        
        # Get user mention or name
        user_display = user.mention if isinstance(user, discord.User) else str(user)
        
        embed.add_field(
            name=f"{medal} Rank #{rank}",
            value=f"{user_display}\n**Points:** {points}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed)
    logger.info(f"{interaction.user} requested {category} leaderboard")

@bot.tree.command(name="stats", description="Show stats for a user")
@app_commands.describe(member="The user to show stats for (defaults to yourself if not specified)")
async def show_stats(interaction: discord.Interaction, member: discord.Member = None):
    """Show stats for a user"""
    # Check if the user is authorized
    if not await authorized_check(interaction):
        return

    if member is None:
        member = interaction.user
    
    user_id = str(member.id)
    if user_id not in leaderboard_bot.scores:
        await interaction.response.send_message(f"{member.name} has no points yet!")
        return
    
    data = leaderboard_bot.scores[user_id]
    
    embed = discord.Embed(
        title=f"📊 Stats for {member.name}",
        color=member.color,
        timestamp=datetime.now()
    )
    
    # Add category stats and rankings
    for category in leaderboard_bot.valid_categories:
        points = data["categories"].get(category, 0)
        rank = leaderboard_bot.get_user_rank(user_id, category)
        rank_display = f" (Rank #{rank})" if rank else ""
        embed.add_field(name=f"{category.title()}", value=f"{points}{rank_display}", inline=True)
    
    # Add history
    if data["history"]:
        last_5_changes = data["history"][-5:]
        history_text = "\n".join(
            f"{entry['points']:+d} {entry['category']} on {entry['timestamp'][:16]}"
            for entry in reversed(last_5_changes)  # Show most recent first
        )
        embed.add_field(name="Recent Changes", value=history_text, inline=False)
    
    await interaction.response.send_message(embed=embed)
    logger.info(f"{interaction.user} requested stats for {member}")
    
@bot.tree.command(name="bothelp", description="Displays a list of available commands")
async def help_command(interaction: discord.Interaction):
    """Displays a list of available commands"""
    embed = discord.Embed(
        title="🔍 Help - Available Commands",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="/add @user category",
        value="Adds 1 point to a specified category (e.g., spedness or helpfulness).",
        inline=False
    )
    embed.add_field(
        name="/remove @user category",
        value="Removes 1 point from a specified category (e.g., spedness or helpfulness).",
        inline=False
    )
    embed.add_field(
        name="/stats [@user]",
        value="Displays stats for a specified user. Defaults to the command sender if no user is mentioned.",
        inline=False
    )
    embed.add_field(
        name="/leaderboard category",
        value="Shows the leaderboard for a specific category (e.g., spedness or helpfulness).",
        inline=False
    )
    embed.add_field(
        name="/authorize @user",
        value="Authorizes a user to use bot commands. (Admin only)",
        inline=False
    )
    embed.add_field(
        name="/unauthorize @user",
        value="Revokes a user's authorization to use bot commands. (Admin only)",
        inline=False
    )
    embed.set_footer(
        text="Use / to see all commands with autocomplete support!"
    )
    await interaction.response.send_message(embed=embed)
    logger.info(f"{interaction.user} requested help")

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    """Global error handler for application commands"""
    if isinstance(error, app_commands.errors.CheckFailure):
        # Already handled by the check
        return
    
    if isinstance(error, app_commands.errors.CommandOnCooldown):
        await interaction.response.send_message(
            f"❌ This command is on cooldown. Try again in {error.retry_after:.2f} seconds.", 
            ephemeral=True
        )
        return
    
    # Log other errors
    logger.error(f"Command error in {interaction.command.name if interaction.command else 'unknown'}: {error}")
    
    try:
        await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)
    except discord.errors.InteractionResponded:
        # If interaction was already responded to
        await interaction.followup.send(f"❌ An error occurred: {error}", ephemeral=True)

def main():
    """Main function to run the bot"""
    if not DISCORD_BOT_TOKEN:
        logger.critical("Please set the DISCORD_BOT_TOKEN environment variable in tokens.env")
        raise ValueError("Please set the DISCORD_BOT_TOKEN environment variable in tokens.env")
    
    try:
        bot.run(DISCORD_BOT_TOKEN)
    except discord.LoginFailure:
        logger.critical("Invalid token provided")
        raise ValueError("Invalid Discord token")
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()
# running
# !add @user spedness - Adds 1 point to spedness
# !remove @user spedness - Removes 1 point from spedness
# !stats [@user] - Shows all categories for a user
# !leaderboard spedness or !leaderboard helpfulness - Shows category-specific leaderboard
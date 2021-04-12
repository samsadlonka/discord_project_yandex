import discord
import dotenv
from discord.ext import commands

TOKEN = dotenv.get_key('.env', 'TOKEN')


class Example(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


if __name__ == '__main__':
    bot = commands.Bot(command_prefix='!')
    #
    bot.add_cog(Example(bot))
    #
    bot.run(TOKEN)

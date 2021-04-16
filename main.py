import discord
import dotenv
import logging

from func import is_message_from_guild

TOKEN = dotenv.get_key('.env', 'TOKEN')
GUILD_ID = 831251799700275231

logging.basicConfig(level=logging.INFO, filename='discord.log',
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')


class Colors:
    DEFAULT = 0
    AQUA = 1752220
    GREEN = 3066993
    BLUE = 3447003
    PURPLE = 10181046
    GOLD = 15844367
    ORANGE = 15105570
    RED = 15158332
    GREY = 9807270
    DARKER_GREY = 8359053
    NAVY = 3426654
    DARK_AQUA = 1146986
    DARK_GREEN = 2067276
    DARK_BLUE = 2123412
    DARK_PURPLE = 7419530
    DARK_GOLD = 12745742
    DARK_ORANGE = 11027200
    DARK_RED = 10038562
    DARK_GREY = 9936031
    LIGHT_GREY = 12370112
    DARK_NAVY = 2899536
    LUMINOUS_VIVID_PINK = 16580705
    DARK_VIVID_PINK = 12320855


class MafiaBotClient(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lobby_n = 1
        self.guild = None

    async def create_lobby_pull(self):
        channels = await self.guild.fetch_channels()
        join_channel = channels[0]  # заглушка
        for channel in channels:
            if channel.name == 'join-lobby':
                join_channel = channel
        embed = discord.Embed(
            title='Title',
            description='description',
            color=Colors.DARK_VIVID_PINK

        )
        message = await join_channel.send(embed=embed)
        await message.add_reaction('1️⃣')

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        for guild in self.guilds:
            print(
                f'{self.user} подключились к чату:\n'
                f'{guild.name}(id: {guild.id}), owner: {guild.owner}')
        self.guild = self.guilds[0]
        logging.info('Create pull')
        await self.create_lobby_pull()
        logging.info('Pull created')

    async def on_message(self, message):
        if is_message_from_guild(message, self.guild):
            if message.author != self.user:
                await message.channel.send('hi')


# это нужно, чтобы получить доступ к пользовательской информации
intents = discord.Intents.default()
intents.members = True

client = MafiaBotClient(intents=intents)
client.run(TOKEN)

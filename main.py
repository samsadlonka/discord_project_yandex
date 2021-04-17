import discord
import dotenv
import logging

from func import is_message_from_guild, is_message_from_channel, Colours

from game import Game

TOKEN = dotenv.get_key('.env', 'TOKEN')
GUILD_ID = 831251799700275231

logging.basicConfig(level=logging.INFO, filename='discord.log',
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')


class MafiaBotClient(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lobby_n = 1
        self.guild = None
        self.game = None

    async def get_channel_by_name(self, channel_name):
        channels = await self.guild.fetch_channels()
        ans_channel = channels[0]  # заглушка
        for channel in channels:
            if channel.name == channel_name:
                ans_channel = channel
        return ans_channel

    async def create_lobby_pull(self):
        channels = await self.guild.fetch_channels()
        join_channel = channels[0]  # заглушка
        for channel in channels:
            if channel.name == 'join-lobby':
                join_channel = channel
        embed = discord.Embed(
            title='Title',
            description='description',
            color=Colours.DARK_VIVID_PINK

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
        # logging.info('Create pull')
        # await self.create_lobby_pull()
        # logging.info('Pull created')

    async def on_message(self, message):
        game_channel = await self.get_channel_by_name('game')
        if is_message_from_guild(message, self.guild) and is_message_from_channel(message, game_channel):
            print(1)
            if message.author != self.user:
                if message.content == '!создать' and self.game is None:
                    self.game = Game(message)
                    await self.game.launch(message)
                else:
                    await self.game.on_message(message)

    async def on_reaction_add(self, message):
        # этой функции в гейме пока нет
        await self.game.on_reaction_add(message)


# это нужно, чтобы получить доступ к пользовательской информации
intents = discord.Intents.default()
intents.members = True

client = MafiaBotClient(intents=intents)
client.run(TOKEN)

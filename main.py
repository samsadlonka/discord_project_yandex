import discord
import dotenv
import logging

from func import is_message_from_channel

from game import Game

TOKEN = dotenv.get_key('.env', 'TOKEN')
GUILD_ID = 831251799700275231

logging.basicConfig(level=logging.INFO, filename='discord.log',
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')


class MafiaBotClient(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.guild = None
        self.owner = None
        self.game = None
        self.waiting_voice = None

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
            self.owner = guild.owner
        self.guild = self.guilds[0]

        self.waiting_voice = self.get_channel(833781149632823297)
        # logging.info('Create pull')
        # await self.create_lobby_pull()
        # logging.info('Pull created')

    async def on_message(self, message):
        game_channel = await self.get_channel_by_name('game')
        if message.author != self.user:
            if message.content == '!create' and self.game is None and is_message_from_channel(message, game_channel) \
                    and (message.author.top_role.name == 'adm' or message.author == self.owner):
                self.game = Game(message, self.waiting_voice)
                await message.channel.send('Игра создана! Чтобы удалить игру, используйте команду !delete')
                await self.game.launch(message)
            elif message.content == '!delete' and self.game and is_message_from_channel(message, game_channel) \
                    and (message.author.top_role.name == 'adm' or message.author == self.owner):
                self.game = None
                await message.channel.send('Игра успешна удалена!')
            elif message.content == '!hard' and self.game:
                if self.game.hard_mode:
                    self.game.hard_mode = False
                    await message.channel.send('Вы выключили хард моД)')
                else:
                    await message.channel.send('Вы включили хард моД!!! Все роли будут скрыты)')
                    self.game.hard_mode = True
            elif self.game:
                await self.game.on_message(message)
            elif not self.game:
                await message.channel.send('Для начала нужно создать игру командой !create (Только для админов)')

    async def on_reaction_add(self, reaction, user):
        if self.game and user.id != self.user.id:
            await self.game.on_reaction_add(reaction, user)

    async def on_reaction_remove(self, user, reaction):
        await self.game.on_reaction_remove(user, reaction)

    async def on_voice_state_update(self, member, before, after):
        if after and after.channel == self.waiting_voice and after.mute:
            await member.edit(mute=False)
        if self.game:
            await self.game.on_voice_state_update(member, before, after)


# это нужно, чтобы получить доступ к пользовательской информации
intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.voice_states = True

client = MafiaBotClient(intents=intents)
client.run(TOKEN)

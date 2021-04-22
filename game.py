import math
import random
from enum import Enum
from collections import Counter
import asyncio

import discord

from func import parseMessage, isDM, Colours, n_from_arg, PICTURES_URLS

commands = ["join", "leave", "start", "choose", "purge", "why", "who"]


class State(Enum):
    START = 1
    ROUNDSLEEP = 2
    ROUNDPURGE = 3
    END = 4


class Win(Enum):
    VILLAGERS = 1
    MAFIA = 2


class Game:
    lock = None
    bot = None
    guild = None
    channel = None

    minPlayers = 5
    maxPlayers = 13

    # Game Object Methods
    def __init__(self, message, waiting_channel):
        self.lock = asyncio.Lock()
        self.maxPlayers = 13

        self.channel = message.channel
        self.guild = message.guild
        self.voice_waiting_channel_id = 833781149632823297
        #self.waiting_channel = waiting_channel

        self.prefix = '!'
        self.start_message_id = None
        self.vote_message_id = None
        self.mafia_vote_message_id = None
        self.doctor_vote_message_id = None
        self.detective_vote_message_id = None
        self.emoji = '0️⃣ 1️⃣ 2️⃣ 3️⃣ 4️⃣ 5️⃣ 6️⃣ 7️⃣ 8️⃣ 9️⃣ 🔟 🅰️ 🅱️'.split(' ')
        self.skip_emoji = '🚫'
        self.dict_emoji_to_user = {}

        random.seed()

        self.setInitialState()

    def setInitialState(self):
        self.mafiaChannel = None
        self.voice_channel = None
        self.players = []
        self.villagers = []
        self.mafia = []
        self.doctor = None
        self.detective = None
        self.round = 1
        self.mafiaChoose = {}
        self.roundKill = None
        self.roundKillSkip = None
        self.roundSave = None
        self.lastRoundSave = None
        self.roundDetect = None
        self.roundPurge = {}
        self.state = State.START

    async def destroy(self):
        await self.remove_mafia_channel()

    async def launch(self, message):
        mess = await message.channel.send(
            embed=discord.Embed(
                title="Mafia :dagger:",
                description="Добро пожаловать в деревню Далёкое обычно этоо спокойное место, но в последнее время "
                            "происходит что-то странное по ночам.\n\n""Чтобы присоединиться к игре напиши '{0}join', "
                            "далее '{0}start', когда будет хотя бы {1} игроков.\n\n"
                            "Чтобы покинуть игру напиши '{0}leave'.".format(self.prefix, self.minPlayers),
                colour=Colours.DARK_RED,
            )
        )
        self.start_message_id = mess.id
        await mess.add_reaction('✅')

    async def on_voice_state_update(self, member, before, after):
        if not after.channel:
            await self.leave_game(member)
        elif before.channel and before.channel.id != self.voice_waiting_channel_id and \
                before.channel.id != after.channel.id:
            await self.leave_game(member)

    async def on_reaction_add(self, reaction, user):
        async with self.lock:
            if reaction.message.id == self.start_message_id and self.state == State.START:
                await self.join_in_game(user)

            elif reaction.message.id == self.vote_message_id and self.state == State.ROUNDPURGE:
                await self.vote_in_purge(user, reaction)

            if self.state == State.ROUNDSLEEP:
                if reaction.message.id == self.mafia_vote_message_id:
                    await self.mafia_choose(reaction=reaction, user=user)

                elif reaction.message.id == self.doctor_vote_message_id:
                    await self.doctor_choose(reaction=reaction, user=user)

                elif reaction.message.id == self.detective_vote_message_id:
                    await self.detective_choose(reaction=reaction, user=user)

                await self.test_round_continue()

    async def on_reaction_remove(self, reaction, user):
        async with self.lock:
            if reaction.message.id == self.start_message_id:
                await self.leave_game(user)

            elif reaction.message.id == self.vote_message_id and self.state == State.ROUNDPURGE:
                await self.remove_vote_in_purge(user, reaction)

    async def join_in_game(self, user):
        if self.user_in_game(user.id):
            await self.channel.send("Вы уже в игре!")

        elif user.voice and user.voice.channel.id == self.voice_waiting_channel_id:
            try:
                embed = discord.Embed(
                    description="Добро пожаловать в деревню Далёкую, надеемся, что это место вам понравится\n\n"
                                "Во время игры я буду отправлять тебе сообщения здесь, если ты хочешь покинуть "
                                "игру напиши '{}leave'в чат игры..".format(self.prefix),
                    colour=Colours.DARK_BLUE,
                )
                await user.send(embed=embed)

                self.players.append(user)
                if len(self.players) < self.minPlayers:
                    l = "{} игроков из {}".format(
                        len(self.players), self.minPlayers
                    )
                else:
                    l = "{} игроков из максимальных{}".format(
                        len(self.players), self.maxPlayers
                    )
                await self.channel.send(
                    "{} присоединился ({})".format(user.mention, l)
                )

            except discord.errors.Forbidden:
                await self.channel.send(
                    "{0.mention} у вас отключены личные сообщения, поэтому я не могу писать вам :cry:".format(
                        user
                    )
                )
        else:
            await self.channel.send('Чтобы зайти в игру, подключитесь к голосовому каналу "Ожидание игры"')

    async def leave_game(self, user):
        if user in self.players:
            await self.channel.send(
                "{} покинул игру".format(user.mention)
            )

            if self.state in [State.ROUNDSLEEP, State.ROUNDPURGE]:
                await self.kill(user)
                win = self.check_win_conditions()

                if win:
                    await self.end_game(win)

            else:
                self.players.remove(user)

    async def vote_in_purge(self, user, reaction):
        if user in self.players:
            if user.id not in self.roundPurge:
                if reaction.emoji == self.skip_emoji:
                    await self.skip_vote(user)
                else:
                    self.roundPurge[user.id] = self.dict_emoji_to_user[reaction.emoji]
                    left = len(self.players) - len(self.roundPurge)
                    await self.channel.send(
                        "{0.mention} проголосовал за {1.display_name} - {2} ещё не проголосовали".format(
                            user, self.dict_emoji_to_user[reaction.emoji], left
                        )
                    )
            else:
                # манипуляция для того, чтобы понять, что удаляется вторая реакция
                self.roundPurge[user.id] = [self.roundPurge[user.id], 2]
                await reaction.remove(user)
                await self.channel.send(
                    "{0.mention} вы уже проголосовали! Сначала уберите реакцию и попробуйте снова".format(
                        user
                    )
                )

            if len(self.roundPurge) == len(self.players):
                await self.purge()

    async def remove_vote_in_purge(self, user, reaction):
        print(self.roundPurge[user.id])
        if user in self.players and self.roundPurge[user.id]:
            if type(self.roundPurge[user.id]) == list:
                self.roundPurge[user.id] = self.roundPurge[user.id][0]
            else:
                del self.roundPurge[user.id]
                await self.channel.send(f"{user.mention} вы успешно забрали свой голос!")

    async def mafia_choose(self, message=None, reaction=None, user=None):
        if message:
            command, args = parseMessage(message, self.prefix)

            choose_n = n_from_arg(args)

            if choose_n is False:
                await message.channel.send(
                    "Не понял твой выбор - {}".format(
                        message.author.mention)
                )

            elif message.author.id not in self.mafiaChoose and choose_n is not False:
                if (choose_n < 0) or (choose_n >= len(self.players)):
                    await self.mafiaChannel.send(
                        "Не понял твой выбор - {}".format(
                            message.author.mention
                        )
                    )
                else:
                    self.mafiaChoose[message.author.id] = self.players[choose_n]
                    await self.mafiaChannel.send(
                        "Выбор принят - {}".format(message.author.mention)
                    )
            elif message.author.id in self.mafiaChoose:
                await self.mafiaChannel.send(
                    "{} Вы уже проголосоваили!".format(message.author.mention)
                )

        elif reaction:
            if user.id not in self.mafiaChoose:
                self.mafiaChoose[user.id] = self.dict_emoji_to_user[reaction.emoji]
                await self.mafiaChannel.send(
                    "Выбор принят - {}".format(user.mention))
            else:
                await self.mafiaChannel.send(
                    "{} Вы уже проголосовали!".format(user.mention))

        await self.all_mafia_voted_check()

    async def all_mafia_voted_check(self):
        if len(self.mafiaChoose) == len(self.mafia):
            chosen_user, count = Counter(self.mafiaChoose.values()).most_common(1)[0]
            if count >= (math.floor(len(self.mafia) / 2) + 1):
                self.roundKill = chosen_user
                await self.mafiaChannel.send(
                    "{} будет убит".format(
                        self.roundKill.display_name
                    )
                )
            else:
                await self.mafiaChannel.send(
                    "Вы не пришли к единому мнению, поэтому никого не убьют в эту ночь."
                )
                self.roundKillSkip = True

    async def doctor_choose(self, message=None, reaction=None, user=None):
        if message:
            command, args = parseMessage(message, self.prefix)
            choose_n = n_from_arg(args)

            if choose_n is not False and ((choose_n >= 0) and (choose_n < len(self.players))):
                save = self.players[choose_n]
                if save != self.lastRoundSave:
                    self.roundSave = save
                    await message.channel.send(
                        "Выбор защитан - {} будет вылечен".format(
                            self.roundSave.display_name
                        )
                    )

                else:
                    await message.channel.send(
                        "Нельзя выбирать одного и того же человека 2 ночи подряд!"
                    )
            else:
                await message.channel.send("Это не корректный выбор!")
        elif reaction:
            save = self.dict_emoji_to_user[reaction.emoji]
            if save != self.lastRoundSave:
                self.roundSave = save
                await user.send(
                    "Выбор защитан - {} будет вылечен".format(
                        self.roundSave.display_name))
            else:
                await user.send("Нельзя выбирать одного и того же человека 2 ночи подряд!")

    async def detective_choose(self, message=None, reaction=None, user=None):
        if message:
            command, args = parseMessage(message, self.prefix)
            choose_n = n_from_arg(args)

            if choose_n is not False and ((choose_n >= 0) and (choose_n < len(self.players))):
                self.roundDetect = self.players[choose_n]
                await message.channel.send(
                    "Выбор защитан - {} будет проверен".format(
                        self.roundDetect.display_name
                    )
                )
            else:
                await message.channel.send("Это некорректный выбор!")
        elif reaction:
            if not self.roundDetect:
                self.roundDetect = self.dict_emoji_to_user[reaction.emoji]
                user.send("Выбор защитан - {} будет проверен".format(
                    self.roundDetect.display_name))
            else:
                await user.send('Вы уже выбрали проверяемого!')

    async def skip_vote(self, user):
        if user in self.players:
            self.roundPurge[user.id] = False

            await self.channel.send(
                "{} воздержался от голосования - {} ещё не проголосовали".format(
                    user.mention, len(self.players) - len(self.roundPurge)
                )
            )

    async def on_message(self, message):
        async with self.lock:
            # TODO: split this into separate functions!
            command, args = parseMessage(message, self.prefix)

            if (
                    command == "join"
                    and message.channel == self.channel
                    and self.state == State.START
            ):
                await self.join_in_game(message.author)

            elif command == "leave" and message.channel == self.channel:
                await self.leave_game(message.author)

            elif (
                    command == "start"
                    and message.channel == self.channel
                    and self.state == State.START
            ):
                if message.author in self.players and message.channel == self.channel:
                    # DEBUG
                    # if len(self.players) < self.minPlayers:
                    #     await self.channel.send(
                    #         "Недостаточно игроков - ({} из необходимых {})".format(
                    #             len(self.players), self.minPlayers
                    #         )
                    #     )
                    #
                    # else:
                    await self.start_game()

            elif command == "choose" and self.state == State.ROUNDSLEEP:
                if message.author in self.mafia and message.channel == self.mafiaChannel:
                    await self.mafia_choose(message=message)

                elif message.author == self.doctor and isDM(message):
                    await self.doctor_choose(message=message)

                elif message.author == self.detective and isDM(message):
                    await self.detective_choose(message=message)

                await self.test_round_continue()

            elif (
                    command == "accuse"
                    and message.channel == self.channel
                    and self.state == State.ROUNDPURGE
            ):
                if message.author in self.players:
                    if message.mentions and (len(message.mentions) == 1):
                        if message.mentions[0] in self.players:
                            self.roundPurge[message.author.id] = message.mentions[0]
                            left = len(self.players) - len(self.roundPurge)
                            await message.channel.send(
                                "{0.mention} accused {1.display_name} - {2} left to decide".format(
                                    message.author, message.mentions[0], left
                                )
                            )

                            if len(self.roundPurge) == len(self.players):
                                await self.purge()

                        else:
                            await self.channel.send(
                                "{0.mention} не в игре!".format(
                                    message.mentions[0]
                                )
                            )
                    else:
                        await self.channel.send(
                            "{0.mention} - это некорректный выбор".format(
                                message.author
                            )
                        )

            elif (
                    command == "skip"
                    and message.channel == self.channel
                    and self.state == State.ROUNDPURGE
            ):
                await self.skip_vote(message.author)

                if len(self.roundPurge) == len(self.players):
                    await self.purge()

            elif command == "restart" and self.state == State.END:
                self.setInitialState()
                await self.launch(message)

            elif command == "why" and message.channel == self.channel:
                if self.state == State.START:
                    if len(self.players) < self.minPlayers:
                        await self.channel.send(
                            embed=discord.Embed(
                                description="Я жду недостающих игроков, напишите `{0}join`, чтобы "
                                            "прсоединиться к игре".format(self.prefix), colour=Colours.BLUE, )
                        )

                    else:
                        await self.channel.send(
                            embed=discord.Embed(
                                description="Я жду пока кто-нибудь начнет игру, напишите `{0}start`, когда будете "
                                            "готовы начать ".format(self.prefix), colour=Colours.BLUE, )
                        )

                elif self.state == State.ROUNDSLEEP:
                    waiting = []

                    if not (self.roundKill or self.roundKillSkip):
                        waiting.append("Мафия")

                    if self.doctor and not self.roundSave:
                        waiting.append("Врач")

                    if self.detective and not self.roundDetect:
                        waiting.append("Детектив")

                    await self.channel.send(
                        embed=discord.Embed(
                            description="Я жду пока сделают свой выбор: {}".format(
                                ", ".join(waiting)
                            ),
                            colour=Colours.BLUE,
                        )
                    )

                elif self.state == State.ROUNDPURGE:
                    remaining = len(self.players) - len(self.roundPurge)
                    players = ", ".join(
                        [
                            "{0.mention}".format(p)
                            for p in self.players
                            if p.id not in self.roundPurge
                        ]
                    )
                    plural = "игроков" if remaining > 1 else "игрок"

                    await self.channel.send(
                        embed=discord.Embed(
                            description="Ещё не проголосовали - {0} {1}, а именно ({2})".format(
                                remaining, plural, players
                            ),
                            colour=Colours.BLUE,
                        )
                    )

                elif self.state == State.END:
                    await self.channel.send(
                        embed=discord.Embed(
                            description="Игра была завершена, напиши `{0}restart` для запуска новой игры".format(
                                self.prefix
                            ),
                            colour=Colours.BLUE,
                        )
                    )

            elif command == "who" and self.state in [
                State.START,
                State.ROUNDSLEEP,
                State.ROUNDPURGE,
            ]:
                if len(self.players) > 0:
                    players = " ".join(["{0.mention}".format(m) for m in self.players])
                    await self.channel.send(
                        embed=discord.Embed(
                            description="{} в игре".format(players),
                            color=Colours.DARK_BLUE,
                        )
                    )

                else:
                    await self.channel.send(
                        embed=discord.Embed(
                            description="Ещё никого нет в игре",
                            color=Colours.DARK_BLUE,
                        )
                    )

    # Game Helpers
    def check_win_conditions(self):
        if len(self.mafia) >= len(self.villagers):
            return Win.MAFIA
        elif len(self.mafia) == 0:
            return Win.VILLAGERS
        else:
            return False

    def user_in_game(self, uID):
        count = len([u for u in self.players if u.id == uID])
        return count > 0

    def allocate_roles(self):

        nMafia = (
            1 if len(self.players) <= 5 else (math.floor(len(self.players) / 5) + 1)
        )

        random.shuffle(self.players)

        self.mafia = self.players[0:nMafia]
        self.villagers = self.players[nMafia:]

        self.doctor = self.villagers[0]
        self.detective = self.villagers[1] if len(self.players) > 5 else None

        random.shuffle(self.players)

    async def make_voice_channel(self):
        if not self.voice_channel:
            try:
                self.voice_channel = await self.channel.category.create_voice_channel("голосовой канал игры")
                return True

            except discord.errors.Forbidden:
                await self.channel.send(
                    "Я не могу продолжить, потому что у меня нет разрешения на создание голосовых каналов"
                    "- вы удалили разрешение?")
                await self.end_game()
                return False

    async def remote_voice_channel(self):
        if self.voice_channel:
            await self.voice_channel.delete()
            self.voice_channel = None

    async def add_voice_channel(self):
        try:
            for x in self.players:
                await x.edit(voice_channel=self.voice_channel, mute=False)
        except Exception as e:
            await self.channel.send(
                "Я не могу продолжить, так как некоторые игроки не присоединились к голосовому каналу")
            await self.end_game()
            return False

   # async def return_to_waiting(self):
    #    print(self.waiting_channel)
    #    for x in self.players:
    #        await x.edit(voice_channel=self.waiting_channel)

    async def night_voice(self):
        for x in self.players:
            await x.edit(mute=True)

    async def day_voice(self):
        for x in self.players:
            await x.edit(mute=False)

    async def make_mafia_channel(self):
        if not self.mafiaChannel:
            mafiaPermissions = discord.PermissionOverwrite(
                read_messages=True, send_messages=True, add_reactions=False
            )

            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(
                    read_messages=False
                ),
                self.guild.me: discord.PermissionOverwrite(
                    manage_channels=True,
                    manage_permissions=True,
                    read_messages=True,
                    send_messages=True,
                    embed_links=True,
                ),
            }

            for m in self.mafia:
                overwrites[m] = mafiaPermissions

            try:
                self.mafiaChannel = await self.channel.category.create_text_channel(
                    "the-mafia", overwrites=overwrites
                )
                # self.bot.mafiaChannels[self.mafiaChannel.id] = self.channel.id
                return True

            except discord.errors.Forbidden:
                await self.channel.send(
                    "Я не могу продолжить, потому что у меня нет разрешения на создание текстовых каналов в этой "
                    "категории каналов - вы удалили разрешение?")
                await self.end_game()
                return False

    async def remove_mafia_channel(self):
        if self.mafiaChannel:
            # del self.bot.mafiaChannels[self.mafiaChannel.id]
            await self.mafiaChannel.delete()
            self.mafiaChannel = None

    async def remove_from_mafia(self, player):
        self.mafia.remove(player)
        permissions = discord.PermissionOverwrite(
            read_messages=False, send_messages=False
        )
        await self.mafiaChannel.set_permissions(player, overwrite=permissions)

    def make_player_list_embed(self):
        # ВАЖНО! Именно тут мы для каждой реакции запоминаем юзера
        for i in range(len(self.players)):
            self.dict_emoji_to_user[self.emoji[i]] = self.players[i]

        return discord.Embed(
            description="\n".join(
                [
                    "{0} - {1}".format(emoji, user.display_name)
                    for emoji, user in zip(self.emoji, self.players)
                ]
            ) + '\nps: 🅰️ = 11, 🅱️ = 12',
            colour=Colours.PURPLE,
        )

    async def kill(self, player, purge=False):
        method = "выбран" if purge else "убит"

        if player in self.mafia:
            role = "мафия"
            await self.remove_from_mafia(player)

        elif player == self.doctor:
            role = "врач"
            self.doctor = None
            self.villagers.remove(player)

        elif player == self.detective:
            role = "детектив"
            self.detective = None
            self.villagers.remove(player)

        elif player in self.villagers:
            role = "мирный житель"
            self.villagers.remove(player)

        else:
            return

        embed = discord.Embed(
            title="{} был {}!".format(player.display_name, method),
            description="Это был {}".format(role),
            colour=Colours.DARK_RED,
        )
        await self.channel.send(embed=embed)

        self.players.remove(player)

        # win = self.check_win_conditions()
        # if win:
        #     await self.end_game()
        # else:
        #     await self.test_round_continue()

    # Game Flow
    async def start_game(self):
        self.allocate_roles()
        created = await self.make_mafia_channel()
        create_voice = await self.make_voice_channel()
        if created and create_voice:
            await self.add_voice_channel()
            await self.send_intros()
            await self.start_round()

    async def continue_game(self):
        self.lastRoundSave = self.roundSave
        self.mafiaChoose = {}
        self.roundKill = None
        self.roundKillSkip = None
        self.roundSave = None
        self.roundDetect = None
        self.roundPurge = {}

        self.round += 1
        await self.start_round()

    async def end_game(self, win=False):
        self.state = State.END
        #await self.return_to_waiting()
        if win == Win.VILLAGERS:
            winners = " ".join(["{0.mention}".format(m) for m in self.villagers])
            embed = discord.Embed(
                description="Мирные жители ({}) победили!\n\n"
                            "Напишите `{}restart`, чтобы сыграть снова".format(winners, self.prefix),
                colour=Colours.DARK_GREEN,
            )

        elif win == Win.MAFIA:
            winners = " ".join(["{0.mention}".format(m) for m in self.mafia])
            embed = discord.Embed(
                description="Мафия ({}) победила!\n\n"
                            "Message `{}restart` to play again".format(
                    winners, self.prefix
                ),
                colour=Colours.DARK_RED,
            )

        else:
            embed = discord.Embed(
                description="Игра прервалась из-за некоторых проблем\n\n"
                            "Напишите `{}restart`, чтобы начать новую игру".format(self.prefix),
                colour=Colours.BLUE,
            )

        await self.remove_mafia_channel()
        await self.remote_voice_channel()
        await self.channel.send(embed=embed)

    # Round Flow
    async def start_round(self):
        embed = discord.Embed(
            title="Ночь {}".format(self.round),
            description="Наступает ночь, мирные жители засыпают",  # make list of these to work through as a story
            colour=Colours.PURPLE,

        )
        embed.set_image(url=PICTURES_URLS['night'])

        await self.night_voice()
        await self.channel.send(embed=embed)
        self.state = State.ROUNDSLEEP
        await self.send_prompts()

    async def send_intros(self):
        mafia = "".join(["{0.mention} ".format(m) for m in self.mafia])
        await self.mafiaChannel.send(
            "{} - вы мафия каждую ночь вы будете выбирать новую жертву!".format(
                mafia
            )
        )

        for v in self.villagers:
            if v in self.mafia:
                await v.send(
                    "Вы мафия и  каждую ночь вы будете выбирать новую жертву. Зайдите в канал "
                    "`#the-mafia`, чтобы сделать свой выбор.")
            elif v == self.doctor:
                await v.send(
                    "Вы врач каждую ночь вы будете выбирать одного жителя, которого хотите вылечить. "
                    "Нельзя лечить одного и того же человека две ночи подряд.")

            elif v == self.detective:
                await v.send(
                    "Вы детектив и каждую ночь вы будете выбирать одного жителя и искать срези них мафию")

            else:
                await v.send(
                    "Вы - мирный житель, сосредоточьтесь, чтобы найти мафию.")

    async def mess_add_all_reactions(self, mess):
        for i in range(len(self.players)):
            await mess.add_reaction(self.emoji[i])

    async def send_prompts(self):
        mafia_prompt = "Напишите '{0}choose number' (например '{0}choose 1') или нажмите на " \
                       "соответсвующие эмодзи из списка ниже" \
                       ", чтобы выбрать игрока, " \
                       "которого вы хотите убить) Вам нужно прийти к соглашению всей группой, если нет четкого выбора," \
                       "никто не будет убит, поэтому вы можете сначала обсудить свой выбор! Отменить выбор нельзя.".format(
            self.prefix
        )
        doctor_prompt = "Напишите`{0}choose number` (например `{0}choose 1`) или нажмите на соответсвующие эмодзи из " \
                        "списка ниже, чтобы выбрать игрока для излечения." \
                        "Отменить выбор нельзя!".format(
            self.prefix
        )
        detective_prompt = "Напишите `{0}choose number` (например `{0}choose 1`) или нажмите на соответсвующие " \
                           "эмодзи из списка ниже, чтобы выбрать игрока " \
                           "для проверки. Отменить выбор нельзя!".format(self.prefix)

        embed = self.make_player_list_embed()
        mafia_mess = await self.mafiaChannel.send(mafia_prompt, embed=embed)
        self.mafia_vote_message_id = mafia_mess.id
        await self.mess_add_all_reactions(mafia_mess)

        if self.doctor:
            doctor_mess = await self.doctor.send(doctor_prompt, embed=embed)
            self.doctor_vote_message_id = doctor_mess.id
            await self.mess_add_all_reactions(doctor_mess)
        else:
            self.doctor_vote_message_id = None

        if self.detective:
            detective_mess = await self.detective.send(detective_prompt, embed=embed)
            self.detective_vote_message_id = detective_mess.id
            await self.mess_add_all_reactions(detective_mess)
        else:
            self.detective_vote_message_id = None

    async def test_round_continue(self):
        if (
                (self.state == State.ROUNDSLEEP)
                and (self.roundKill or self.roundKillSkip)
                and (not self.doctor or self.roundSave)
                and (not self.detective or self.roundDetect)
        ):
            await self.summarise_round()

    async def summarise_round(self):
        # turn on micro
        await self.day_voice()

        summary = discord.Embed(
            title="Просыпаемся",
            description="Теперь, когда жители проснулись узнаем, что же случилось этой ночью",
            colour=Colours.PURPLE,
        )
        kill = None

        if self.roundKillSkip:
            summary.add_field(
                name=":person_shrugging:",
                value="Мафия никого не выбрала",
                inline=False,
            )
            kill = False

        elif self.roundKill:
            summary.add_field(
                name=":dagger:",
                value="Мафия выбрала убить {}".format(self.roundKill.mention),
                inline=False,
            )
            if self.roundSave == self.roundKill:
                summary.add_field(
                    name=":syringe:",
                    value="Врач вылечил игрока вовремя!",
                    inline=False,
                )
                kill = False

            elif self.doctor:
                summary.add_field(
                    name=":skull_crossbones:",
                    value="Врач не смог вылечить его",
                    inline=False,
                )
                kill = True

            else:
                # the doctor has been killed
                kill = True

        if self.detective and self.roundDetect:
            if self.roundDetect in self.mafia:
                summary.add_field(
                    name=":detective:",
                    value="Детектив нашёл мафию",
                    inline=False,
                )
                await self.detective.send(
                    embed=discord.Embed(
                        description="Верно {} - это мафия !".format(
                            self.roundDetect.display_name
                        ),
                        colour=Colours.DARK_RED,
                    )
                )
            else:
                summary.add_field(
                    name=":detective:",
                    value="Детектив не нашёл мафию",
                    inline=False,
                )
                await self.detective.send(
                    embed=discord.Embed(
                        description="Неверно {} не является мафией!".format(
                            self.roundDetect.display_name
                        ),
                        colour=Colours.DARK_GREEN,
                    )
                )

        await self.channel.send(embed=summary)

        if kill:
            await self.kill(self.roundKill)
            win = self.check_win_conditions()

            if win:
                await self.end_game(win)

        if self.state != State.END:
            await self.move_to_purge()

    async def move_to_purge(self):
        self.state = State.ROUNDPURGE

        if self.roundKillSkip:
            text = "Хотя мафия никого не убила прошлой ночью, жители деревни все еще находятся в напряжении, и " \
                   "собираются для обсуждения ..."

        elif self.roundKill == self.roundSave:
            text = "Напряжение накаляется после попытки убийства прошлой ночью, жители деревни собираются, " \
                   "чтобы обсудить ...."

        else:
            text = "В ужасе от убийства прошлой ночи, жители деревни собираются, чтобы обсудить ..."

        left = ["{0.mention}".format(m) for m in self.players]

        embed = discord.Embed(
            description=f"{text}\n\nЕсли вы подозрительно относитесь к игроку, упомяните его, используя cоответствующие эмодзи, "
                        f"чтобы обвинить его в принадлежности к мафии! Используйте '{self.prefix} skip' или 🚫, "
                        f"чтобы молчать(пропустить ход). \n"
                        f"По крайней мере, половина жителей должна кого-то обвинить, чтобы их проверили.\n\n " \
                        + '\n'.join([self.emoji[i] + ' - ' + left[i] for i in range(len(left))]),
            colour=Colours.DARK_ORANGE,
        )

        mess = await self.channel.send(embed=embed)
        self.vote_message_id = mess.id
        for i in range(len(left)):
            await mess.add_reaction(self.emoji[i])
            self.dict_emoji_to_user[self.emoji[i]] = self.players[i]
        await mess.add_reaction(self.skip_emoji)

    async def purge(self):
        most_commons = Counter(self.roundPurge.values()).most_common(len(self.roundPurge))

        if len(most_commons) > 1:
            chosen, count = None, None
        else:
            chosen, count = most_commons[0]

        if chosen and count >= len(self.players) // 2:
            await self.channel.send(
                embed=discord.Embed(
                    description="Жители решили, что {} должен быть проверен".format(
                        chosen.display_name
                    ),
                    colour=Colours.DARK_RED,
                )
            )

            await self.kill(chosen, True)
            win = self.check_win_conditions()
            print(win)
            if win:
                await self.end_game(win)

            else:
                await self.continue_game()
        else:
            await self.channel.send(
                embed=discord.Embed(
                    description="Жители не пришли к согласию, сегодня никто не будет проверен",
                    colour=Colours.DARK_GREEN,
                )
            )

            await self.continue_game()

import math
import random
from enum import Enum
from collections import Counter
import asyncio

import discord

from func import parseMessage, isDM, Colours

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
    maxPlayers = 15

    # Game Object Methods
    def __init__(self, message):
        self.lock = asyncio.Lock()

        self.guild = message.guild
        self.channel = message.channel

        self.prefix = '!'
        self.start_message_id = None

        random.seed()

        self.setInitialState()

    def setInitialState(self):
        self.mafiaChannel = None
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
        await self.removeMafiaChannel()

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

    async def on_reaction_add(self, reaction, user):
        if reaction.message.id == self.start_message_id and self.state == State.START:
            await self.join_in_game(user)

    async def on_reaction_remove(self, reaction, user):
        if reaction.message.id == self.start_message_id:
            await self.leave_game(user)

    async def join_in_game(self, user):
        if self.hasUser(user.id):
            await self.channel.send("You're already in the game!")

        else:
            try:
                embed = discord.Embed(
                    description="Welcome to Upper Lowerstoft, we hope you have a peaceful visit.\n\nDuring the game I will send you messages here, if you need to leave at any point message `{}leave` in the game channel.".format(
                        self.prefix
                    ),
                    colour=Colours.DARK_BLUE,
                )
                await user.send(embed=embed)

                self.players.append(user)
                if len(self.players) < self.minPlayers:
                    l = "{} players of {} needed".format(
                        len(self.players), self.minPlayers
                    )
                else:
                    l = "{} players of maximum {}".format(
                        len(self.players), self.maxPlayers
                    )
                await self.channel.send(
                    "{} joined the game ({})".format(user.mention, l)
                )

            except discord.errors.Forbidden:
                await self.channel.send(
                    "{0.mention} you have your DMs turned off - the game doesn't work if I can't send you messages :cry:".format(
                        user
                    )
                )

    async def leave_game(self, user):
        if user in self.players:
            await self.channel.send(
                "{} left the game".format(user.mention)
            )

            if self.state in [State.ROUNDSLEEP, State.ROUNDPURGE]:
                await self.kill(user)
                win = self.checkWinConditions()

                if win:
                    self.endGame(win)

            else:
                self.players.remove(user)

    async def on_message(self, message):
        async with self.lock:
            # TODO: split this into separate functions!
            command, args = parseMessage(message, self.prefix)

            if (
                    command == "join"
                    and message.channel == self.channel
                    and self.state == State.START
            ):
                if self.hasUser(message.author.id):
                    await message.channel.send("You're already in the game!")
                # delete this shit
                # elif userInActiveGame(message.author.id, self.bot.active):
                #     await message.channel.send("You're already in a game elsewhere!")
                else:
                    try:
                        embed = discord.Embed(
                            description="Добро пожаловать в деревню Далёкую, надеемся, что это место вам понравится\n\n"
                                        "Во время игры я буду отправлять тебе сообщения здесь, если ты хочешь покинуть "
                                        "игру напиши '{}leave'в чат игры.".format(self.prefix),
                            colour=Colours.DARK_BLUE,
                        )
                        await message.author.send(embed=embed)

                        self.players.append(message.author)
                        if len(self.players) < self.minPlayers:
                            l = "{} игроков из {}".format(
                                len(self.players), self.minPlayers
                            )
                        else:
                            l = "{} игроков из максимальных{}".format(
                                len(self.players), self.maxPlayers
                            )
                        await message.channel.send(
                            "{} присоединился ({})".format(message.author.mention, l)
                        )

                    except discord.errors.Forbidden:
                        await self.channel.send(
                            "{0.mention} у вас отключены личные сообщения, поэтому я не могу писать вам".format(
                                message.author
                            )
                        )

            elif command == "leave" and message.channel == self.channel:
                if message.author in self.players:
                    await self.channel.send(
                        "{} покинул игру".format(message.author.mention)
                    )

                    if self.state in [State.ROUNDSLEEP, State.ROUNDPURGE]:
                        await self.kill(message.author)
                        win = self.checkWinConditions()

                        if win:
                            self.endGame(win)

                    else:
                        self.players.remove(message.author)

            elif (
                    command == "start"
                    and message.channel == self.channel
                    and self.state == State.START
            ):
                if message.author in self.players and message.channel == self.channel:
                    if len(self.players) < self.minPlayers:
                        await self.channel.send(
                            "Недостаточно игроков - ({} из необходимых {})".format(
                                len(self.players), self.minPlayers
                            )
                        )

                    else:
                        await self.startGame()

            elif command == "choose" and self.state == State.ROUNDSLEEP:

                def IDFromArg(args):
                    if len(args) > 1:
                        try:
                            return int(args[1])
                        except ValueError:
                            return False

                if (
                        message.author in self.mafia
                        and message.channel == self.mafiaChannel
                ):
                    id = IDFromArg(args)

                    if not message.author.id in self.mafiaChoose and id:
                        if (id < 1) or (id > len(self.players)):
                            await message.channel.send(
                                "Не понял твой выбор - {}".format(
                                    message.author.mention
                                )
                            )
                        else:
                            self.mafiaChoose[message.author.id] = id
                            await message.channel.send(
                                "Выбор принят - {}".format(message.author.mention)
                            )

                            if len(self.mafiaChoose) == len(self.mafia):
                                chosen, count = Counter(
                                    self.mafiaChoose.values()
                                ).most_common(1)[0]
                                if count >= (math.floor(len(self.mafia) / 2) + 1):
                                    self.roundKill = self.players[chosen - 1]
                                    await message.channel.send(
                                        "{} будет убит".format(
                                            self.roundKill.display_name
                                        )
                                    )
                                else:
                                    await message.channel.send(
                                        "Вы не пришли к единому мнению, поэтому никого не убьют в эту ночь."
                                    )
                                    self.roundKillSkip = True

                elif message.author == self.doctor and isDM(message):
                    id = IDFromArg(args)

                    if id and ((id > 0) and (id <= len(self.players))):
                        save = self.players[id - 1]
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

                elif message.author == self.detective and isDM(message):
                    id = IDFromArg(args)

                    if id and ((id > 0) and (id <= len(self.players))):
                        self.roundDetect = self.players[id - 1]
                        await message.channel.send(
                            "Выбор защитан - {} будет проверен".format(
                                self.roundDetect.display_name
                            )
                        )
                    else:
                        await message.channel.send("Это некорректный выбор!")

                await self.testRoundContinue()

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
                if message.author in self.players:
                    self.roundPurge[message.author.id] = False
                    left = len(self.players) - len(self.roundPurge)
                    await message.channel.send(
                        "{} skipped - {} left to decide".format(
                            message.author.mention, left
                        )
                    )

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
                                            "прсоединиться к игре".format(self.prefix), colour=Colours.BLUE,)
                        )

                    else:
                        await self.channel.send(
                            embed=discord.Embed(
                                description="Я жду пока кто-нибудь начнет игру, напишите `{0}start`, когда будете "
                                            "готовы начать ".format(self.prefix),colour=Colours.BLUE,)
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
    def checkWinConditions(self):
        if len(self.mafia) >= len(self.villagers):
            return Win.MAFIA
        elif len(self.mafia) == 0:
            return Win.VILLAGERS
        else:
            return False

    def hasUser(self, uID):
        count = len([u for u in self.players if u.id == uID])
        return count > 0

    def allocateRoles(self):
        nMafia = (
            1 if len(self.players) <= 5 else (math.floor(len(self.players) / 5) + 1)
        )

        random.shuffle(self.players)

        self.mafia = self.players[0:nMafia]
        self.villagers = self.players[nMafia:]

        self.doctor = self.villagers[0]
        self.detective = self.villagers[1] if len(self.players) > 5 else None

        random.shuffle(self.players)

    async def makeMafiaChannel(self):
        if not self.mafiaChannel:
            mafiaPermissions = discord.PermissionOverwrite(
                read_messages=True, send_messages=True
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
                await self.endGame()
                return False

    async def removeMafiaChannel(self):
        if self.mafiaChannel:
            # del self.bot.mafiaChannels[self.mafiaChannel.id]
            await self.mafiaChannel.delete()
            self.mafiaChannel = None

    async def removeFromMafia(self, player):
        self.mafia.remove(player)
        permissions = discord.PermissionOverwrite(
            read_messages=False, send_messages=False
        )
        await self.mafiaChannel.set_permissions(player, overwrite=permissions)

    def makePlayerListEmbed(self):
        return discord.Embed(
            description="\n".join(
                [
                    "{0} - {1}".format((n + 1), v.display_name)
                    for n, v in enumerate(self.players)
                ]
            ),
            colour=Colours.PURPLE,
        )

    async def kill(self, player, purge=False):
        method = "выбран" if purge else "убит"

        if player in self.mafia:
            role = "мафия"
            await self.removeFromMafia(player)

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

        await self.testRoundContinue()

    # Game Flow
    async def startGame(self):
        self.allocateRoles()
        created = await self.makeMafiaChannel()

        if created:
            await self.sendIntros()
            await self.startRound()

    async def continueGame(self):
        self.lastRoundSave = self.roundSave
        self.mafiaChoose = {}
        self.roundKill = None
        self.roundKillSkip = None
        self.roundSave = None
        self.roundDetect = None
        self.roundPurge = {}

        self.round += 1
        await self.startRound()

    async def endGame(self, win=False):
        self.state = State.END

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

        await self.removeMafiaChannel()
        await self.channel.send(embed=embed)

        # if self.settings["winCommand"]:
        #     await self.channel.send(
        #         "{} {}".format(self.settings["winCommand"], winners)
        #     )

    # Round Flow
    async def startRound(self):
        embed = discord.Embed(
            title="Ночь {}".format(self.round),
            description="Наступает ночь, мирные жители засыпают",  # make list of these to work through as a story
            colour=Colours.PURPLE,
        )
        await self.channel.send(embed=embed)
        self.state = State.ROUNDSLEEP
        await self.sendPrompts()

    async def sendIntros(self):
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

    async def sendPrompts(self):
        mafiaPrompt = "Напишите '{0}choose number' (например, '{0}choose number 1'), чтобы выбрать игрока, \n\n" \
                      "которого вы хотите убить - вам нужно прийти к соглашению всей группой, если нет четкого выбора,"\
                      "никто не будет убит, поэтому  вы можете сначала обсудить свой выбор!".format(
            self.prefix
        )
        doctorPrompt = "Напишите`{0}choose number` (например `{0}choose 1`), чтобы выбрать игрока для излечения".format(
            self.prefix
        )
        detectivePrompt = "Напишите `{0}choose number` (например `{0}choose 1`), чтобы выбрать игрока " \
                          "для проверки".format(self.prefix)

        embed = self.makePlayerListEmbed()
        await self.mafiaChannel.send(mafiaPrompt, embed=embed)

        if self.doctor:
            await self.doctor.send(doctorPrompt, embed=embed)

        if self.detective:
            await self.detective.send(detectivePrompt, embed=embed)

    async def testRoundContinue(self):
        if (
                (self.state == State.ROUNDSLEEP)
                and (self.roundKill or self.roundKillSkip)
                and (not self.doctor or self.roundSave)
                and (not self.detective or self.roundDetect)
        ):
            await self.summariseRound()

    async def summariseRound(self):
        summary = discord.Embed(
            title="Просыпаемся",
            description="Теперь, когда жители проснулись узнаем, что же случилось этой ночью",
            colour=Colours.PURPLE,
        )

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
                    value="Врая вылечил игрока вовремя!",
                    inline=False,
                )
                kill = False

            elif self.doctor:
                summary.add_field(
                    name=":skull_crossbones:",
                    value="Врая не смог вылечить его",
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
            win = self.checkWinConditions()

            if win:
                await self.endGame(win)

        if self.state != State.END:
            await self.moveToPurge()

    async def moveToPurge(self):
        self.state = State.ROUNDPURGE

        if self.roundKillSkip:
            text = "Хотя мафия никого не убила прошлой ночью, жители деревни все еще находятся в напряжении, и " \
                   "собираются для обсуждения ..."

        elif self.roundKill == self.roundSave:
            text = "Напряжение накаляется после попытки убийства прошлой ночью, жители деревни собираются, " \
                   "чтобы обсудить ...."

        else:
            text = "В ужасе от убийства прошлой ночи, жители деревни собираются, чтобы обсудить ..."

        left = " ".join(["{0.mention}".format(m) for m in self.players])

        embed = discord.Embed(
            description="{0}\n\nЕсли вы подозрительно относитесь к игроку, упомяните его, используя '{2} acccuse',\n\n "
                        "чтобы обвинить его в принадлежности к мафии, или используйте '{2} skip', чтобы молчать. \n\n"
                        "По крайней мере, половина жителей должна кого-то обвинить, чтобы их проверили.\n\n{1} "
                        "всё ещё в игре".format(text, left, self.prefix),
            colour=Colours.DARK_ORANGE,
        )

        await self.channel.send(embed=embed)

    async def purge(self):
        chosen, count = Counter(self.roundPurge.values()).most_common(1)[0]
        if chosen != False and count >= (math.ceil(len(self.players) / 2)):
            await self.channel.send(
                embed=discord.Embed(
                    description="Жители решили, что {} должен быть проверен".format(
                        chosen.display_name
                    ),
                    colour=Colours.DARK_RED,
                )
            )

            await self.kill(chosen, True)
            win = self.checkWinConditions()

            if win:
                await self.endGame(win)

            else:
                await self.continueGame()
        else:
            await self.channel.send(
                embed=discord.Embed(
                    description="Жители не пришли к согласию, сегодня никто не будет проверен",
                    colour=Colours.DARK_GREEN,
                )
            )

            await self.continueGame()

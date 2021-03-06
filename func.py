import discord


def is_message_from_guild(message, guild):
    return message.guild == guild


def is_message_from_channel(message, channel):
    return message.channel == channel


def isDM(message):
    return (type(message.channel) == discord.DMChannel)


def hasPrefix(message, prefix):
    chars = len(prefix)
    if (chars == 0): return True
    if (message.content[:chars] == prefix): return True
    return False


def canManageGuild(author, guild):
    guildOwner = guild.owner == author
    guildAdmin = author.guild_permissions.administrator
    guildManager = author.guild_permissions.manage_guild

    return guildOwner or guildAdmin or guildManager


def guildsUserCanManage(author, guilds):
    active = [g.id for g in guilds if canManageGuild(author)]
    return active


def parseMessage(message, prefix):
    args = message.content.split(" ")
    args[0] = args[0][len(prefix):]
    command = args[0].lower()

    return command, args


def n_from_arg(args):
    if len(args) > 1:
        try:
            return int(args[1])
        except ValueError:
            return False


class Colours:
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


PICTURES_URLS = {
    'start': ['https://i.imgur.com/ORPwDJY.png'],
    'night': ['https://i.imgur.com/PFX64Ji.png', 'https://i.imgur.com/AQFcBqe.png'],
    'morning': ['https://i.imgur.com/ae5VUur.jpeg'],
    'mafia_kill': ['https://i.imgur.com/SJw2y0M.png', 'https://i.imgur.com/MY7RBuK.png',
                   'https://i.imgur.com/KJH6Bzb.png', 'https://i.imgur.com/qYsc0Ww.png'],
    'city_kill': ['https://i.imgur.com/86Jdiv3.png'],
    'briefing': ['https://i.imgur.com/MriXBpV.png', 'https://i.imgur.com/mjD4F8O.png',
                 'https://i.imgur.com/FSNN3rR.png'],
    'doctor': 'https://i.imgur.com/51951Mr.png',
    'mafia': 'https://i.imgur.com/zBAGbrF.png',
    'detective': 'https://i.imgur.com/rNbzpFr.png',
    'villager': ['https://i.imgur.com/BEOSsct.png', 'https://i.imgur.com/Gs5MNOT.png', 'https://i.imgur.com/W7Kf7ue.png']
}

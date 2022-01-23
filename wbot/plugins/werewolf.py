#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'QAQAutoMaton'


from math import log
from nonebot import on_command, CommandSession, message
from nonebot import on_request, RequestSession
from nonebot import permission as perm
import random
import re
import sqlite3
import nonebot

db = sqlite3.connect('werewolf.db')
c = db.cursor()


def cq_at(uid):
    return f"[CQ:at,qq={uid}]"


def split(text):
    return re.split(",|，", text)


class Game:
    def __init__(self):
        self.player_num = 0
        self.roleid = 0
        self.role = []
        self.player = []
        self.identity = []
        self.alive = []
        self.running = False
        self.online = False
        self.onVote = False
        self.vote = []

    def empty(self, uid=-1):
        for one in self.player:
            if one != 0 and one != uid:
                return False
        return True

    def init(self, role, online=True):
        self.role = c.execute(
            "select name,type from roles_identity where id=?", (role,)).fetchall()
        self.online = online
        self.roleid = role
        self.player_num = len(self.role)
        self.identity = []
        self.alive = [True]*(self.player_num+1)
        self.running = False
        self.player = [0]*(self.player_num+1)
        self.onVote = False

    def sit(self, uid, pos):
        if pos > self.player_num or pos < 0:
            return "位置在[0..人数]之间"
        if uid in self.player:
            return "你已经加入了"
        if self.player[pos] != 0:
            return "这个位置有人了"
        self.player[pos] = uid
        return ""

    def stand(self, uid):
        if uid not in self.player:
            return "你没有加入"
        if self.running:
            return "游戏已经开始"
        self.player[self.player.index(uid)] = 0
        return ""

    def kick(self, pos):
        if pos > self.player_num or pos < 0:
            return (False, "位置在[0..人数]之间")
        if self.running:
            return (False, "游戏已经开始")
        if self.player[pos] == 0:
            return (False, "这个位置没有人")
        uid = self.player[pos]
        self.player[pos] = 0
        return (True, uid)

    def preview(self):
        s = ""
        if self.running:
            s = "游戏已开始，"
        s += "配置为："
        las = ""
        last_cnt = 0
        for i in range(self.player_num):
            if i == 0 or self.role[i][0] != las:
                if last_cnt > 1:
                    s += f"*{last_cnt}"
                if last_cnt > 0:
                    s += "，"
                last_cnt = 1
                las = self.role[i][0]
                s += las
            else:
                last_cnt += 1
        if last_cnt > 1:
            s += f"*{last_cnt}"
        s += "\n"
        s += "人员为：\n"
        for i in range(self.player_num+1):
            s += f"{i}" + ("(法官)" if i == 0 else "") + ": "
            if self.player[i] == 0:
                s += "空"
            else:
                s += cq_at(self.player[i])
            if self.running and not self.alive[i]:
                s += "「已死亡」"
            s += "\n"
        s += "为获取身份，请添加bot为好友。"
        return s

    def generate(self):
        self.identity = list(range(self.player_num))
        random.shuffle(self.identity)
        self.identity = self.identity
        self.running = True


game = {}
in_game = {}


def permission(uid):
    l = c.execute("select permission from permission where qq=?",
                  (uid,)).fetchall()
    if len(l) == 0:
        return 0
    return l[0][0]


async def send_at(session: CommandSession, message):
    await session.send(cq_at(session.event.user_id) + ' ' + message)


async def send_private(uid, message):
    bot = nonebot.get_bot()
    await bot.send_private_msg(user_id=uid, message=message)


async def reply(session: CommandSession, message):
    if not session.event.group_id:
        await send_private(session.event.user_id, message)
    else:
        await send_at(session, message)


async def try_sit(session: CommandSession, pos):
    group_id = session.event.group_id
    user_id = session.event.user_id
    result = game[group_id].sit(user_id, pos)
    if result == "":
        in_game[user_id] = group_id
        return True
    else:
        await send_at(session, result)
        return False


async def send_identity(session: CommandSession):
    group_id = session.event.group_id
    g = game[group_id]
    wolf = []
    if g.online:
        for i in range(g.player_num):
            if g.role[g.identity[i]][1] == 2:
                wolf.append(i+1)
    for i in range(g.player_num):
        s = f"您是{i+1}号，您的身份是{g.role[g.identity[i]][0]}。"
        if g.online and g.role[g.identity[i]][1] == 2:
            s += f"您的狼队友为{wolf}。"
        await send_private(g.player[i+1], s)
    s = "您是法官，\n"
    for i in range(g.player_num):
        s += f"{i+1}号：{g.role[g.identity[i]][0]}\n"
    s = s[:-1]
    await send_private(g.player[0], s)


@on_command('set', aliases=('设置', 'sz'), only_to_me=False, permission=perm.GROUP)
async def setting(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if in_game.get(user_id, False) and in_game[user_id] != group_id:
        await send_at(session, "你已经在某个群加入了,请先退出")
        return False
    if group_id in game:
        if not game[group_id].empty(user_id):
            await send_at(session, '当前桌还有人')
            return
        else:
            in_game[user_id] = False
    else:
        game[group_id] = Game()

    if 'role' not in session.state:
        await send_at(session, "用法：#set 规则名 位置")
        return
    else:
        role = session.state['role']
        try:
            pos = int(session.state['pos'])
        except ValueError:
            await send_at(session, "位置是一个[0..人数]之间的整数")
            return
        role_id = c.execute(
            "select id from roles_alias where name=?", (role,)).fetchall()
        if len(role_id) == 0:
            await send_at(session, "找不到这个规则")
            return
        role_id = role_id[0][0]
        game[group_id].init(role_id)
        if await try_sit(session, pos):
            await send_at(session, "创建成功，"+game[group_id].preview())


@setting.args_parser
async def setting_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 2:
        session.state['role'] = args[0]
        session.state['pos'] = args[1]


@on_command('sit', aliases=('jr', '加入', '坐下'), only_to_me=False, permission=perm.GROUP)
async def sit(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群没有设定板子，请使用set命令设置')
        return
    if in_game.get(user_id, False) and in_game[user_id] != group_id:
        await send_at(session, "你已经在某个群加入了,请先退出")
        return False
    if 'pos' not in session.state:
        await send_at(session, "用法：#sit 位置\n如： #sit 1")
        return
    try:
        pos = int(session.state['pos'])
    except ValueError:
        await send_at(session, "位置为一个[0..人数]之间的整数")
        return

    if await try_sit(session, pos):
        await send_at(session, "加入成功，" + game[group_id].preview())


@sit.args_parser
async def sit_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['pos'] = args[0]


@on_command('stand', aliases=('tc', '退出', '站起'), only_to_me=False, permission=perm.GROUP)
async def stand(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    result = game[group_id].stand(user_id)
    if result == "":
        in_game[user_id] = False
        await send_at(session, "退出成功，" + game[group_id].preview())
    else:
        await send_at(session, result)


@on_command('status', aliases=('zt', '状态'), only_to_me=False, permission=perm.GROUP)
async def status(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    await send_at(session, game[group_id].preview())


@on_command('start', aliases=('ks', '开始'), only_to_me=False, permission=perm.GROUP)
async def start(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    g = game[group_id]
    if user_id not in g.player:
        await send_at(session, "你还没有加入游戏")
        return
    if 0 in g.player:
        await send_at(session, "人数不足，无法开始")
        return
    if g.running:
        await send_at(session, "游戏已经开始")
        return

    g.generate()
    await send_identity(session)


@on_command('resend', aliases=('重发'), only_to_me=False, permission=perm.GROUP)
async def resend(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    g = game[group_id]
    if not g.running:
        await send_at(session, "未开始")
    elif user_id != g.player[0]:
        await send_at(session, "只有法官可以要求重新发牌")
    else:
        await send_identity(session)


@on_command('remake', aliases=('重生成身份'), only_to_me=False, permission=perm.GROUP)
async def remake(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    g = game[group_id]
    if not g.running:
        await send_at(session, "未开始")
    elif user_id != g.player[0]:
        await send_at(session, "只有法官可以要求重新生成身份")
    else:
        g.generate()
        await send_identity(session)


@on_command('stop', aliases=('jieshu', 'js', '结束'), only_to_me=False, permission=perm.GROUP)
async def stop(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    g = game[group_id]
    if g.running:
        if session.state['force']:
            if permission(user_id) == 0:
                await send_at(session, "你没有权限")
                return
        else:
            if user_id != g.player[0]:
                await send_at(session, "你不是法官，无权结束")
                return
        for i in game[group_id].player:
            in_game[i] = False
        s = "游戏已结束，身份为：\n"
        for i in range(g.player_num):
            s += "{}号({})：{}{}\n".format(i + 1, cq_at(
                g.player[i + 1]), g.role[g.identity[i]][0], ("" if g.alive[i+1] else "「已死亡」"))
        g.player = [0] * (g.player_num + 1)
        g.running = False
        g.alive = [True]*(g.player_num+1)
        await send_at(session, s)
        return
    else:
        await send_at(session, "未开始")
        return


@stop.args_parser
async def stop_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1 and args[0] == "--force":
        session.state['force'] = True
    else:
        session.state['force'] = False


@on_command('kick', aliases=('踢人'), only_to_me=False, permission=perm.GROUP)
async def kick(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    if permission(user_id) < 1:
        await send_at(session, "你没有权限踢人")
        return
    if 'pos' not in session.state:
        await send_at(session, "用法：#kick 位置")
        return
    g = game[group_id]
    try:
        pos = int(session.state['pos'])
    except ValueError:
        await send_at(session, "位置为一个[0..人数]之间的整数")
        return
    if not (0 <= pos <= g.player_num):
        await send_at(session, "位置为一个[0..人数]之间的整数")
    elif g.player[pos] == 0:
        await send_at(session, "此位置没有人")
    else:
        qq = g.player[pos]
        result = g.stand(qq)
        if result == "":
            in_game[user_id] = False
            await send_at(session, "踢出{}成功，".format(cq_at(qq)) + g.preview())
        else:
            await send_at(session, result)


@kick.args_parser
async def kick_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['pos'] = args[0]


@on_command('kickall', aliases=('清场', 'qc'), only_to_me=False, permission=perm.GROUP)
async def kickall(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    if permission(user_id) < 1:
        await send_at(session, "你没有权限")
        return

    g = game[group_id]
    if g.running:
        if not session.state['force']:
            await send_at(session, "已经开始")
            return

    for i in game[group_id].player:
        in_game[i] = False
    g.player = [0] * (g.player_num + 1)
    g.running = False
    g.alive = [True]*(g.player_num+1)

    await send_at(session, "已全部踢出")
    return


@kickall.args_parser
async def kickall_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1 and args[0] == "--force":
        session.state['force'] = True
    else:
        session.state['force'] = False


@on_command('kill', aliases=('杀'), only_to_me=False, permission=perm.GROUP)
async def kill(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id not in game:
        await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
        return
    g = game[group_id]
    if g.running:
        if user_id != g.player[0]:
            await send_at(session, "你不是法官，无权操作")
            return
        else:

            if 'pos' not in session.state:
                await send_at(session, "用法：#kill 位置\n如： #kill 1")
                return
            try:
                pos = int(session.state['pos'])
            except ValueError:
                await send_at(session, "位置为一个[1..人数]之间的整数")
                return
            if not (1 <= pos and pos <= g.player_num):
                await send_at(session, "位置为一个[1..人数]之间的整数")
                return
            if not g.alive[pos]:
                await send_at(session, "{}号已经死过了。".format(pos))
                return
            g.alive[pos] = False
            s = "当前还活着的有：\n"

            for i in range(g.player_num):
                if g.alive[i+1]:
                    s += f"{i+1}号：{g.role[g.identity[i]][0]}\n"
            await send_private(g.player[0], s)
            await send_at(session, "{}号 死了。\n".format(pos)+g.preview())
            return
    else:
        await send_at(session, "未开始")
        return


@kill.args_parser
async def kill_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['pos'] = args[0]


@on_command('addrole', aliases=('新建规则'), only_to_me=False, permission=perm.EVERYBODY)
async def addrole(session: CommandSession):
    user_id = session.event.user_id
    if permission(user_id) < 1:
        await reply(session, "您没有权限添加规则")
        return
    if 'args' not in session.state:
        await reply(session, "用法：addrole 规则名 好人阵营的身份列表 狼人阵营(夜里见面)的身份列表 狼人阵营(夜里不见面)的身份列表，其中列表用逗号而非空格隔开，如果没有用单一个逗号即可")
        return
    args = session.state['args']
    name = args[0]
    if len(c.execute("select id from roles_alias where name=?", (name,)).fetchall()) > 0:
        await reply(session, "规则已存在")

    identity = []
    for i in range(1, 4):
        for one in re.split(",|，", args[i]):
            if len(one):
                if one in identity:
                    await reply(session, "同一种身份不能在不同阵营中")
                    return
        for one in re.split(",|，", args[i]):
            if len(one):
                identity.append(one)

    if len(identity) > 20:
        await reply(session, "😅")
        return

    identity = []
    count = []
    for i in range(1, 4):
        for one in re.split(",|，", args[i]):
            if len(one):
                if not one in identity:
                    identity.append(one)
                    count.append([i, 1])
                else:
                    count[identity.index(one)][1] += 1

    c.execute("insert into roles (name) values (?)", (name,))
    _id = c.lastrowid
    c.execute("insert into roles_alias (id,name) values (?,?)", (_id, name))
    message = f"规则 {name} 创建成功，包含"
    for i in range(len(identity)):
        message += identity[i]
        if count[i][1] > 1:
            message += f"*{count[i][1]}"
        message += ','
        for j in range(count[i][1]):
            c.execute("insert into roles_identity (id,name,type) values (?,?,?)",
                      (_id, identity[i], count[i][0]))
    message = message[:-1]
    db.commit()
    await reply(session, message)


@addrole.args_parser
async def addrole_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 4:
        session.state['args'] = args


@on_command('setalias', aliases=('设置规则别名'), only_to_me=False, permission=perm.EVERYBODY)
async def setalias(session: CommandSession):
    user_id = session.event.user_id
    if permission(user_id) < 1:
        await reply(session, "您没有权限设置规则别名")
        return
    if 'name' not in session.state:
        await reply(session, "用法：setalias 规则名 规则的别名 (用逗号分隔开)")
        return
    name = session.state['name']
    aliases = split(session.state['aliases'])
    _id = c.execute("select id from roles_alias where name=?",
                    (name,)).fetchall()
    if len(_id) == 0:
        await reply(session, "找不到规则")
        return
    _id = _id[0][0]
    for i in aliases:
        if len(i):
            sel = c.execute(
                "select id from roles_alias where name=?", (i,)).fetchall()
            if len(sel) != 0 and sel[0][0] != _id:
                await reply(session, "设置的别名不能和其它规则相同")
                return
    c.execute("delete from roles_alias where id=?", (_id,))
    al = [c.execute("select name from roles where id=?",
                    (_id,)).fetchall()[0][0]]
    if al[0] != name:
        al.append(name)
    for i in aliases:
        if len(i):
            if not i in al:
                al.append(i)
    for i in al:
        c.execute("insert into roles_alias (id,name) values (?,?)", [_id, i])
    db.commit()
    await reply(session, f"修改成功：{al[0]} 的别名包含 {al[1:]}")


@setalias.args_parser
async def setalias_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 2:
        session.state['name'] = args[0]
        session.state['aliases'] = args[1]


@on_command('rand', aliases=('随机'), only_to_me=False, permission=perm.EVERYBODY)
async def rand(session: CommandSession):
    if 'n' not in session.state:
        await reply(session, "用法：rand n 表示随机一个1..n内的整数")
        return
    try:
        n = int(session.state['n'])
    except ValueError:
        await send_at(session, "n是一个>0的整数")
        return
    if n <= 0:
        await send_at(session, "n是一个>0的整数")
        return

    if n > 10**100:
        await send_at(session, "😅")
        return
    if n > 10**20:
        a = 46.051701859880914
        b = 230.25850929940457
        if random.random() < (log(n)-a)/(b-a):
            await send_at(session, "😅")
            return

    if not session.event.group_id:
        await session.send(str(random.randint(1, n)))
        return
    await send_at(session, str(random.randint(1, n)))


@rand.args_parser
async def rand_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['n'] = args[0]


vote_usage = """用法：群中#vote start #vote end表示开始投票和结束投票
私聊bot#vote x表示给x号投票(一经投票不能修改)
法官私聊bot#vote x表示删除x号的投票
"""


@on_command('vote', aliases=('投票'), only_to_me=False, permission=perm.EVERYBODY)
async def vote(session: CommandSession):
    if 'text' not in session.state:
        await reply(session, vote_usage)
    text = session.state['text']
    group_id = session.event.group_id
    user_id = session.event.user_id
    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return

    if not group_id:

        text = int(text)
        if not in_game[user_id]:
            await reply(session, "你没有加入游戏")
            return
        group_id = in_game[user_id]
        g = game[group_id]
        if not g.running:
            await reply(session, "游戏未开始")
            return
        pos = g.player.index(user_id)
        try:
            text = int(text)
            if text < 0 or text > g.player_num:
                raise ValueError
        except ValueError:
            await reply(session, vote_usage)
            return
        if pos == 0:
            if not g.alive[text]:
                await reply(session, f"{text}号已经死了")
                return
            if g.vote[text] == -1:
                await reply(session, f"{text}号没有投票")
                return
            g.vote[text] = -1

            await send_private(g.player[text], "您的票被法官删除")
            notvoted = []
            for i in range(1, g.player_num+1):
                if g.alive[i] and g.vote[i] == -1:
                    notvoted.append(i)
            await reply(session, f"{text}号的票已被删除,还有{notvoted}号没投票")
        else:
            if not g.alive[pos]:
                await reply(session, "你已经死了")
                return
            if not g.alive[text] and text > 0:
                await reply(session, f"{text}号已经死了")
                return
            if g.vote[pos] >= 0:
                await reply(session, "你已经投过票了")
                return
            g.vote[pos] = text
            await reply(session, f"{pos}->{text}")
            notvoted = []
            for i in range(1, g.player_num+1):
                if g.alive[i] and g.vote[i] == -1:
                    notvoted.append(i)
            await send_private(g.player[0], f"{pos}号投给{text}号，还有{notvoted}号没有投票")
    else:
        if group_id not in game:
            await send_at(session, '当前群还没有人使用狼人杀功能，请使用set命令开始')
            return
        g = game[group_id]
        if not g.running:
            await reply(session, "未开始")
            return
        if user_id != g.player[0]:
            await reply(session, "只有法官可以使用此命令")
            return
        if text == "start":
            if g.onVote:
                await send_at(session, "上一次投票还没结束")
                return
            g.onVote = True
            g.vote = [-1]*(g.player_num+1)
            await send_at(session, "法官开启了投票，请私聊bot #vote x表示向x号投票(其中vote 0表示弃票，一经投票不能修改)")
        elif text == "end":
            if not g.onVote:
                await send_at(session, "未开启投票")
                return
            g.onVote = False
            vote = [[] for i in range(g.player_num+1)]
            for i in range(1, g.player_num+1):
                if g.alive[i]:
                    vote[max(g.vote[i], 0)].append(i)
            text = "投票结果：\n"
            for i in range(g.player_num+1):
                if len(vote[i]):
                    text += f"{i} <- {vote[i]}\n"
            text = text[:-1]
            await send_at(session, text)
        else:
            await send_at(session, vote_usage)


@vote.args_parser
async def vote_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['text'] = args[0]


@on_request('friend')
async def friend_request(session: RequestSession):
    await session.approve()

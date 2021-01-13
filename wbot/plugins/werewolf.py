#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'QAQAutoMaton'

import nonebot
import random
from config import *
from nonebot import on_command, CommandSession, message

from nonebot import permission as perm

tp = "pwbynls"
Id = {}
for _i in range(len(tp)):
    Id[tp[_i]] = _i


def cq_at(uid):
    return "[CQ:at,qq={}] ".format(uid)


USAGE_TEXT = """用法：#set 配置 位置
如： #set pwbynls 0
其中p是平民，w是狼，b是白狼王，y是预言家，n是女巫，l是猎人，s是守卫
位置为0和人数之间的整数，其中0是法官
"""


class Game:
    def __init__(self):
        self.n = 0
        self.player = []
        self.type = []
        self.Is = []
        self.running = False

    def empty(self, user_id=-1):
        for i in self.player:
            if i != 0 and i != user_id:
                return False
        return True

    def init(self, s, n):
        self.n = n
        self.type = s
        self.player = [0] * (n + 1)
        self.Is = []
        self.running = False

    def sit(self, uid, at):
        if at > self.n or at < 0:
            return 3
        if uid in self.player:
            return 1
        if self.player[at] != 0:
            return 2
        self.player[at] = uid
        return 0

    def stand(self, uid):
        if uid not in self.player:
            return 1
        if self.running:
            return 2
        self.player[self.player.index(uid)] = 0
        return 0

    def kick(self, at):
        if at > self.n or at < 0:
            return -3
        if self.running:
            return -2
        if self.player[at] == 0:
            return -1
        w = self.player[at]
        self.player[at] = 0
        return w

    def preview(self):
        s = ""
        if self.running == 1:
            s = "游戏已开始，"
        s += "配置为："
        for i in range(len(tp)):
            if self.type[i] > 0:
                s += name[i]
                if self.type[i] > 1:
                    s += "*{}".format(self.type[i])
                s += "，"
        s += "人员为："
        for i in range(self.n + 1):
            s += "\n" + str(i) + ("(法官)" if i == 0 else "") + ": "
            if self.player[i] == 0:
                s += "空"
            else:
                s += cq_at(self.player[i])
        s += "\n为获取身份，请添加bot为好友。"
        print(s)
        return s


game = {}
name = ["平民", "狼人", "白狼王", "预言家", "女巫", "猎人", "守卫"]
wolf = [1, 2]


async def send_at(session: CommandSession, s):
    await session.send(cq_at(session.event.user_id) + ' ' + s)


async def send_private(uid, s):
    print(uid, s)
    bot = nonebot.get_bot()
    await bot.send_private_msg(user_id=uid, message=s)


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
    if group_id in game:
        if not game[group_id].empty(user_id):
            await send_at(session, ' 当前桌还有人')
            return
    else:
        game[group_id] = Game()
    if 'type' not in session.state:
        await send_at(session, USAGE_TEXT)
        return
    # 从会话状态（session.state）中获取城市名称（city），如果当前不存在，则询问用户
    else:
        type_ = session.state['type']
        at = session.state['at']
        s = [0] * len(tp)
        for i in type_:
            if i not in tp:
                await send_at(session, "配置不合法")
                return
            s[Id[i]] += 1
        try:
            at = int(at)
        except ValueError:
            await send_at(session, "位置为一个[0..人数]之间的整数")
            return

        if not (0 <= at <= len(type_)):
            await send_at(session, "位置为一个[0..人数]之间的整数")
            return

        game[group_id].init(s, len(type_))
        game[group_id].sit(user_id, at)

        await send_at(session, "创建成功，" + game[group_id].preview())


# weather.args_parser 装饰器将函数声明为 weather 命令的参数解析器
# 命令解析器用于将用户输入的参数解析成命令真正需要的数据
@setting.args_parser
async def setting_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 2:
        session.state['type'] = args[0]
        session.state['at'] = args[1]


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
    if 'at' not in session.state:
        await send_at(session, "用法：#sit 位置\n如： #sit 1")
        return
    try:
        at = int(session.state['at'])
    except ValueError:
        await send_at(session, "位置为一个[0..人数]之间的整数")
        return

    w = game[group_id].sit(user_id, at)

    if w == 3:
        await send_at(session, "位置为一个[0..人数]之间的整数")
        return
    if w == 1:
        await send_at(session, "你已经加入了")
        return
    elif w == 2:
        await send_at(session, "这个位置已经有人了")
        return
    else:
        await send_at(session, "加入成功，" + game[group_id].preview())


@sit.args_parser
async def sit_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['at'] = args[0]


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
    w = game[group_id].stand(user_id)

    if w == 2:
        await send_at(session, "游戏已开始，请等待法官结束")
        return
    if w == 1:
        await send_at(session, "你并没有加入")
        return
    else:
        await send_at(session, "退出成功，" + game[group_id].preview())


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

    g.running = True
    g.Is = []
    for i in range(len(g.type)):
        g.Is += [i] * g.type[i]
    random.shuffle(g.Is)
    s = "您是法官\n"
    wolfs = []
    for i in range(g.n):
        s += "{}号：{}\n".format(i + 1, name[g.Is[i]])
        if g.Is[i] in wolf:
            wolfs.append(i + 1)
    await send_private(g.player[0], s)
    for i in range(g.n):
        s = "您是{}号，您的身份是：{}".format(i + 1, name[g.Is[i]])
        if i + 1 in wolfs:
            s += "\n您的狼队友有{}".format(wolfs)
        await send_private(g.player[i + 1], s)
    await send_at(session, g.preview())


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
        if user_id != g.player[0]:
            await send_at(session, "你不是法官，无权结束")
            return
        else:
            s = "游戏已结束，身份为：\n"
            for i in range(g.n):
                s += "{}号({})：{}\n".format(i + 1, cq_at(g.player[i + 1]), name[g.Is[i]])
            g.player = [0] * (g.n + 1)
            g.Is = []
            g.running = False
            print(s)
            await send_at(session, s)
            return
    else:
        await send_at(session, "未开始")
        return


@on_command('kick', aliases='踢人', only_to_me=False, permission=perm.GROUP)
async def kick(session: CommandSession):
    group_id = session.event.group_id
    user_id = session.event.user_id
    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return
    if user_id not in werewolf_admin:
        await send_at(session, '你没有权限踢人')
        return
    if 'at' not in session.state:
        await send_at(session, "用法：#kick 位置")
        return
    if group_id not in game:
        await send_at(session, '当前群没有人使用过狼人杀功能')
        return
    try:
        at = int(session.state['at'])
    except ValueError:
        await send_at(session, "位置为一个[0..人数]之间的整数")
        return

    w = game[group_id].kick(at)

    if w == -3:
        await send_at(session, "位置为一个[0..人数]之间的整数")
        return
    if w == 2:
        await send_at(session, "游戏已经开始")
        return
    elif w == 1:
        await send_at(session, "此位置没有人")
        return
    else:
        await send_at(session, "踢出{}成功，".format(cq_at(w)) + game[group_id].preview())


@kick.args_parser
async def kick_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['at'] = args[0]


@on_command('resend', aliases='重发', only_to_me=False, permission=perm.GROUP)
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
    if g.running:
        if user_id != g.player[0]:
            await send_at(session, "只有法官可以要求重新发牌")
            return
        else:
            s = "您是法官\n"
            wolfs = []
            for i in range(g.n):
                s += "{}号：{}\n".format(i + 1, name[g.Is[i]])
                if g.Is[i] in wolf:
                    wolfs.append(i + 1)
            await send_private(g.player[0], s)
            for i in range(g.n):
                s = "您是{}号，您的身份是：{}".format(i + 1, name[g.Is[i]])
                if i + 1 in wolfs:
                    s += "\n您的狼队友有{}".format(wolfs)
                await send_private(g.player[i + 1], s)
            await send_at(session, g.preview())
            return
    else:
        await send_at(session, "未开始")
        return


@on_command('wait_resend', aliases='准备重发', only_to_me=False, permission=perm.GROUP)
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
    if g.running:
        if user_id != g.player[0]:
            await send_at(session, "只有法官可以要求重新发牌")
            return
        else:
            for uid in g.player:
                await send_private(uid, "等待重新发牌")
            return
    else:
        await send_at(session, "未开始")
        return

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'QAQAutoMaton'


import asyncio
import random
from enum import Enum

import nonebot
from nonebot import on_command, CommandSession, on_request, RequestSession, permission as perm

from config import *


config_arg = "pwbynls"


def cq_at(uid) -> str:
    return f"[CQ:at,qq={uid}] "


USAGE_TEXT = """用法：#set 配置 位置
如： #set pwbynls 0
其中p是平民，w是狼，b是白狼王，y是预言家，n是女巫，l是猎人，s是守卫
位置为0和人数之间的整数，其中0是法官
"""


class Roles(Enum):
    civilian = '平民'
    werewolf = '狼人'
    witch = '女巫'
    prophet = '预言家'
    hunter = '猎人'
    guard = '守卫'
    white_wolf_king = '白狼王'


class Player:
    class PlayerAlreadyDead(BaseException):
        pass

    def __init__(self, uid: int, role: Roles):
        self.uid = uid
        self.role = role
        self.alive = True

    def briefing(self, show_role: bool = False) -> str:
        return f'{cq_at(self.uid)} {self.role.value if show_role else ""} {"" if self.alive else "[已死亡]"}'

    def set_player_dead(self) -> None:
        if not self.alive:
            raise Player.PlayerAlreadyDead
        self.alive = False


class WerewolfGame:
    ROLE_MAPPING = {
        'p': Roles.civilian,
        'w': Roles.werewolf,
        'b': Roles.white_wolf_king,
        's': Roles.guard,
        'y': Roles.prophet,
        'n': Roles.witch
    }

    class GameException(BaseException):
        pass

    class PlayerFull(GameException):
        pass

    class GameStarted(GameException):
        pass

    class PlayerNotEnough(GameException):
        pass

    class PlayerInReadyPool(GameException):
        pass

    class GameNotStarted(GameException):
        pass

    def __init__(self, role: str):
        self._master: int = 0
        self.player_count: int = len(role)
        self.player_pool: list[int] = []
        self.game_pool: list[Player] = []
        self._lock: asyncio.Lock = asyncio.Lock()
        self.role: str = role
        self.running: bool = False

    @property
    def master(self) -> int:
        return self._master

    @master.setter
    def master(self, value: int) -> None:
        if self.running:
            raise WerewolfGame.GameStarted
        self._master = value

    async def join(self, uid: int) -> None:
        async with self._lock:
            if len(self.player_pool) >= self.player_count:
                raise WerewolfGame.PlayerFull
            if uid in self.player_pool:
                raise WerewolfGame.PlayerInReadyPool
            self.player_pool.append(uid)
            self.player_count += 1

    async def start(self) -> None:
        if self.running:
            raise WerewolfGame.GameStarted
        if self.player_count != len(self.player_pool):
            raise WerewolfGame.PlayerNotEnough
        self.running = True
        random.shuffle(self.player_pool)
        for role_str, role_ in self.ROLE_MAPPING.items():
            for _ in range(self.role.count(role_str)):
                self.game_pool.append(Player(self.player_pool.pop(), role_))
        random.shuffle(self.game_pool)
        await self.notify()

    async def notify_to_master(self) -> None:
        all_roles = '\n'.join([f'{x + 1}: {self.game_pool[x]}'
                               for x in range(self.player_count) if self.game_pool[x].alive])
        await send_private(self._master, f'您是法官\n{all_roles}')

    async def notify(self) -> None:
        if not self.running:
            raise WerewolfGame.GameNotStarted
        werewolf = []
        awaiter = []
        all_roles = []
        for x in range(self.player_count):
            if self.game_pool[x].role == Roles.werewolf:
                werewolf.append(x + 1)
            awaiter.append(send_private(self.game_pool[x].uid,
                                        f'你是 {x + 1} 号, 你的身份是 {self.game_pool[x].role.value}'))
            all_roles.append(f'{x + 1}: {self.game_pool[x]}')
        all_roles = '\n'.join(all_roles)
        awaiter.append(send_private(self._master, f'您是法官\n{all_roles}'))
        await asyncio.gather(*awaiter)
        awaiter.clear()
        for x in werewolf:
            copy = werewolf.copy()
            copy.remove(x)
            awaiter.append(send_private(self.game_pool[x - 1].uid, f'你的狼队友有: {copy}'))
        await asyncio.gather(*awaiter)

    async def kick(self, uid: int) -> int:
        if self.running:
            raise WerewolfGame.GameStarted
        async with self._lock:
            if uid in self.player_pool:
                self.player_pool.remove(uid)
                return uid
            elif 0 < uid <= self.player_count:
                return self.player_pool.pop(uid)
            raise IndexError

    async def stand(self, uid: int) -> bool:
        return bool(await self.kick(uid))

    def stop(self) -> str:
        if not self.running:
            raise WerewolfGame.GameNotStarted
        self.clear()
        return self.game_briefing(show_role=True, header='已经结束')

    def clear(self) -> None:
        self.running = False
        self.game_pool.clear()
        self.player_pool.clear()
        self._master = 0

    def empty(self) -> bool:
        return bool(len(self.player_pool))

    def game_briefing(self, *, show_role: bool = False, header: str = '尚未开始') -> str:
        game_setting = []
        for role_str, role_description in self.ROLE_MAPPING:
            count = self.role.count(role_str)
            if count > 0:
                game_setting.append(f'{role_description}x{count}')
        game_setting = ', '.join(game_setting)
        s = f'游戏{"已经开始" if self.running else header}, 配置为: {game_setting}\n法官: ' \
            f'{cq_at(self.master) if self._master > 0 else "null"}\n玩家列表:'
        player_list = []
        if self.running:
            for x in range(self.player_count):
                player_list.append(f'{x}: {self.game_pool[x].briefing(show_role)}')
            player_list = '\n'.join(player_list)
        else:
            for x in self.player_pool:
                player_list.append(cq_at(x))
            player_list = ','.join(player_list)
        return f'{s}\n{player_list}\n为获取身份，请添加bot为好友。"'

    def kill(self, index: int) -> None:
        if not self.running:
            raise WerewolfGame.GameNotStarted
        self.game_pool[index - 1].set_player_dead()


game: dict[int, WerewolfGame] = {}


async def send_at(session: CommandSession, s):
    await session.send(cq_at(session.event.user_id) + ' ' + s)


async def send_private(uid: int, s: str) -> None:
    bot = nonebot.get_bot()
    await bot.send_private_msg(user_id=uid, message=s)


@on_command('set', aliases=('设置', 'sz'), only_to_me=False, permission=perm.GROUP)
async def setting(session: CommandSession) -> None:
    group_id = session.event.group_id
    user_id = session.event.user_id

    if not group_id:
        await session.send('请在群聊中使用狼人杀功能')
        return

    if user_id == 80000000:
        await session.send('请解除匿名后再使用狼人杀功能')
        return
    if group_id in game:
        if not game[group_id].empty():
            await send_at(session, '当前桌还有人')
            return

    if 'role' not in session.state:
        await send_at(session, USAGE_TEXT)
        return
    else:
        role = session.state['role']
        if not (set(role) & set(config_arg) == set(role)):
            await send_at(session, "配置不合法")
            return

        game[group_id] = WerewolfGame(role)
        await game[group_id].join(user_id)

        await send_at(session, "创建成功，" + game[group_id].game_briefing())


# weather.args_parser 装饰器将函数声明为 weather 命令的参数解析器
# 命令解析器用于将用户输入的参数解析成命令真正需要的数据
@setting.args_parser
async def setting_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['role'] = args[0]


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

    if 'master' in session.state:
        try:
            game[group_id].master = user_id
            await send_at(session, "成为法官成功")
        except WerewolfGame.GameStarted:
            await send_at(session, "游戏已经开始")
        return
    try:
        await game[group_id].join(user_id)
        await send_at(session, "加入成功，" + game[group_id].game_briefing())
    except WerewolfGame.PlayerFull:
        await send_at(session, "人数已满")
    except WerewolfGame.PlayerInReadyPool:
        await send_at(session, "你已经加入了")


@sit.args_parser
async def sit_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1 and args[0] == 'master':
        session.state['master'] = 0


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
    try:
        await game[group_id].stand(user_id)
        await send_at(session, "退出成功，" + game[group_id].game_briefing())
    except WerewolfGame.GameStarted:
        await send_at(session, "游戏已开始，请等待法官结束")
    except IndexError:
        await send_at(session, "你并没有加入")


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
    await send_at(session, game[group_id].game_briefing())


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
    if user_id not in g.player_pool:
        await send_at(session, "你还没有加入游戏")
        return
    try:
        await g.start()
        await send_at(session, g.game_briefing())
    except WerewolfGame.GameStarted:
        await send_at(session, "游戏已经开始")
    except WerewolfGame.PlayerNotEnough:
        await send_at(session, "人数不足，无法开始")


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
    game_instance = game[group_id]
    if user_id != game_instance.master:
        await send_at(session, "你不是法官，无权结束")
    try:
        await send_at(session, game_instance.stop())
    except WerewolfGame.GameNotStarted:
        await send_at(session, '未开始')


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
        await send_at(session, "位置为一个[0..准备人数]之间的整数/QQ号")
        return

    try:
        w = game[group_id].kick(at)
        await send_at(session, "踢出{}成功，".format(cq_at(w)) + game[group_id].game_briefing())
    except WerewolfGame.GameStarted:
        await send_at(session, "游戏已经开始")
    except IndexError:
        await send_at(session, "此位置没有人/玩家不存在")


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
    game_instance = game[group_id]

    if user_id != game_instance.master:
        await send_at(session, "只有法官可以要求重新发牌")
    try:
        await game_instance.notify()
    except WerewolfGame.GameNotStarted:
        await send_at(session, "未开始")


@on_command('kill', aliases='杀', only_to_me=False, permission=perm.GROUP)
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

    if 'id' not in session.state:
        await send_at(session, "用法：#kill 位置\n如： #kill 1")
        return
    try:
        id_ = int(session.state['id'])
    except ValueError:
        await send_at(session, "位置为一个[1..人数]之间的整数")
        return

    try:
        game_instance = game[group_id]
        if user_id != game_instance.master:
            await send_at(session, "你不是法官，无权操作")
            return
        await send_at(session, f"{id_}号 死了。\n" + game_instance.game_briefing())
    except WerewolfGame.GameNotStarted:
        await send_at(session, "未开始")
    except Player.PlayerAlreadyDead:
        await send_at(session, f"{id_}号已经死过了。")
    except IndexError:
        await send_at(session, "位置为一个[1..人数]之间的整数")


@kill.args_parser
async def kill_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['id'] = args[0]


@on_command('rand', aliases='随机', only_to_me=False, permission=perm.EVERYBODY)
async def rand(session: CommandSession):
    if 'n' not in session.state:
        await send_at(session, "用法：#rand n 表示随机一个1..n之间的数")
        return
    try:
        n = int(session.state['n'])
    except ValueError:
        await send_at(session, "n是一个>0的整数")
        return
    if n <= 0:
        await send_at(session, "n是一个>0的整数")
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


@on_request('friend')
async def friend_request(session: RequestSession):
    await session.approve()

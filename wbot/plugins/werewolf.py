#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
__author__ = 'QAQAutoMaton'

import asyncio
import random
from enum import Enum
from typing import Optional

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


class PlayerWithoutRole:
    def __init__(self, uid: int, seat: int):
        self.uid = uid
        self.seat = seat


class Player(PlayerWithoutRole):
    class PlayerAlreadyDead(Exception):
        pass

    def __init__(self, uid: int, role: Roles, seat: int):
        super().__init__(uid, seat)
        self.role = role
        self._alive = True

    @property
    def alive(self) -> bool:
        return self._alive

    def briefing(self, show_role: bool = False) -> str:
        return f'{self.seat}: {cq_at(self.uid)} ' \
               f'{self.role.value if show_role else ""} {"" if self.alive else "[已死亡]"}'

    def set_player_dead(self) -> None:
        if not self._alive:
            raise Player.PlayerAlreadyDead
        self._alive = False

    @classmethod
    def from_player(cls, old_player: PlayerWithoutRole, role: Roles) -> Player:
        return cls(old_player.uid, role, old_player.seat)


class WerewolfGame:
    ROLE_MAPPING = {
        'p': Roles.civilian,
        'w': Roles.werewolf,
        'b': Roles.white_wolf_king,
        's': Roles.guard,
        'y': Roles.prophet,
        'n': Roles.witch
    }

    class BriefingCache:
        def __init__(self, briefing: str, *, changed: bool = False):
            self.briefing = briefing
            self._changed = changed

        def set_changed(self) -> None:
            self._changed = True

        @property
        def is_changed(self) -> bool:
            return self._changed

    class BaseGameException(Exception):
        pass

    class PlayerException(BaseGameException):
        pass

    class GameException(BaseGameException):
        pass

    class PlayerFull(PlayerException):
        pass

    class GameStarted(GameException):
        pass

    class PlayerNotEnough(PlayerException):
        pass

    class PlayerInReadyPool(PlayerException):
        pass

    class GameNotStarted(GameException):
        pass

    class PlayerSeatTaken(PlayerException):
        pass

    class JudgeNotFound(GameException):
        pass

    def __init__(self, role: str):
        self._master: int = 0
        self.player_count: int = len(role)
        self.uid_pool: dict[int, int] = {}
        self.player_pool: list[Optional[PlayerWithoutRole]] = [None] * self.player_count
        self.game_pool: list[Player] = []
        self._lock: asyncio.Lock = asyncio.Lock()
        self.role: str = role
        self.running: bool = False
        self.briefing_cache = self.BriefingCache('', changed=True)

    @property
    def master(self) -> int:
        return self._master

    @master.setter
    def master(self, value: int) -> None:
        if self.running:
            raise WerewolfGame.GameStarted
        self._master = value

    async def join(self, uid: int, seat: int) -> None:
        if seat == 0:
            self.master = uid
            self.briefing_cache.set_changed()
        async with self._lock:
            if len(self.uid_pool) >= self.player_count:
                raise WerewolfGame.PlayerFull
            if uid in self.uid_pool or uid == self._master:
                raise WerewolfGame.PlayerInReadyPool
            if self.player_pool[seat - 1] is not None:
                raise WerewolfGame.PlayerSeatTaken
            self.uid_pool.update({uid: seat})
            self.player_pool[seat - 1] = PlayerWithoutRole(uid, seat)
            self.briefing_cache.set_changed()

    async def start(self) -> None:
        if self.running:
            raise WerewolfGame.GameStarted
        if self.player_count != len(self.uid_pool):
            raise WerewolfGame.PlayerNotEnough
        if self.master == 0:
            raise WerewolfGame.JudgeNotFound
        self.running = True
        random.shuffle(self.player_pool)
        for role_str, role_ in self.ROLE_MAPPING.items():
            for _ in range(self.role.count(role_str)):
                self.game_pool.append(Player.from_player(self.player_pool.pop(), role_))
        self.game_pool.sort(key=lambda x: x.uid)
        for id_ in range(self.player_count):
            assert id_ + 1 == self.game_pool[id_].seat
        self.briefing_cache.set_changed()
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
        for x in self.game_pool:
            if x.role == Roles.werewolf:
                werewolf.append(x.seat)
            awaiter.append(send_private(x.uid, f'你是 {x.seat} 号, 你的身份是 {x.role.value}'))
            all_roles.append(f'{x.seat}: {x.role.value}')
        all_roles = '\n'.join(all_roles)
        awaiter.append(send_private(self._master, f'您是法官\n{all_roles}'))
        await asyncio.gather(*awaiter)
        awaiter.clear()
        for x in werewolf:
            copy = werewolf.copy()
            copy.remove(x)
            awaiter.append(send_private(self.game_pool[x - 1].uid, f'你的狼队友有: {copy}'))
        await asyncio.gather(*awaiter)

    async def kick(self, seat_or_uid: Optional[int]) -> int:
        if self.running:
            raise WerewolfGame.GameStarted
        if self._master == seat_or_uid:
            self._master = 0
            self.briefing_cache.set_changed()
            return seat_or_uid
        async with self._lock:
            if seat_or_uid > 50:
                uid = seat_or_uid
                if uid in self.uid_pool:
                    seat = self.uid_pool.pop(uid)
                    self.player_pool[seat - 1] = None
                    self.briefing_cache.set_changed()
                    return uid
            else:
                seat = seat_or_uid
                if self.player_pool[seat - 1] is not None:
                    uid = self.player_pool[seat - 1].uid
                    self.uid_pool.pop(uid)
                    self.player_pool[seat - 1] = None
                    self.briefing_cache.set_changed()
                    return uid
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
        self.uid_pool = {}
        self.game_pool = []
        self.player_pool = [None] * self.player_count
        self._master = 0
        self.briefing_cache.set_changed()

    def empty(self) -> bool:
        return not self.uid_pool

    def game_briefing(self, *, show_role: bool = False, header: str = '尚未开始') -> str:
        if self.briefing_cache.is_changed:
            self.briefing_cache = self.BriefingCache(self._game_briefing(show_role=show_role, header=header))
        return self.briefing_cache.briefing

    def _game_briefing(self, *, show_role: bool = False, header: str) -> str:
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
            for x in self.game_pool:
                player_list.append(f'{x.seat}: {x.briefing(show_role)}')
        else:
            for x in range(self.player_count):
                element = self.player_pool[x]
                player_list.append(f'{x}: {cq_at(element.uid) if element is not None else "(Empty)"}')
        player_list = '\n'.join(player_list)
        return f'{s}\n{player_list}\n为获取身份，请添加bot为好友。"'

    def kill(self, index: int) -> None:
        if not self.running:
            raise WerewolfGame.GameNotStarted
        self.game_pool[index - 1].set_player_dead()
        self.briefing_cache.set_changed()


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
    if 'seat' not in session.state:
        await send_at(session, "用法：#sit 位置\n如： #sit 1")
        return
    try:
        seat = int(session.state['seat'])
        try:
            await game[group_id].join(user_id, seat)
            await send_at(session, "加入成功，" + game[group_id].game_briefing())
        except WerewolfGame.GameStarted:
            await send_at(session, "游戏已经开始")
        except WerewolfGame.PlayerFull:
            await send_at(session, "人数已满")
        except WerewolfGame.PlayerInReadyPool:
            await send_at(session, "你已经加入了")
    except ValueError:
        await send_at(session, "位置为一个[0..人数]之间的整数")
        return


@sit.args_parser
async def sit_parser(session: CommandSession):
    args = session.current_arg_text.strip().split()
    if len(args) == 1:
        session.state['seat'] = args[0]


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
    except WerewolfGame.JudgeNotFound:
        await send_at(session, "这场游戏还没有法官噢")


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
        await send_at(session, f"踢出{cq_at(w)}成功，\n{game[group_id].game_briefing()}")
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
        await asyncio.gather(send_at(session, f"{id_}号 死了。\n" + game_instance.game_briefing()),
                             game_instance.notify_to_master())
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

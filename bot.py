#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'QAQAutoMaton'

from os import path
import nonebot
import config

if __name__ == '__main__':
    nonebot.init(config)
    #nonebot.load_builtin_plugins()
    nonebot.load_plugins(
        path.join(path.dirname(__file__), 'wbot', 'plugins'),
        'wbot.plugins'
    )
    nonebot.run(host='127.0.0.1', port=8080)

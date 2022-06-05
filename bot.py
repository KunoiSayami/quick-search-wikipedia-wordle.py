#!/usr/bin/env python3
import asyncio
import argparse
import itertools
import json
import pathlib
import re
import os
import sys
import logging
from configparser import ConfigParser

import pypinyin
import aiofiles
import pyrogram
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from libpy3 import aiopgsqldb


config = ConfigParser()
config.read("config.ini")


CJK = re.compile(r"[\u4e00-\u9fff]+")
GOOD_QUERY = re.compile(r"^[\w\d[\u4e00-\u9fff]\s%\$'\"]+")


def generate_query_statement(count: int, args: list[str]) -> str:
    if len(CJK.findall(args[-1])):
        query_chinese = args.pop(-1).replace("?", "%")
    else:
        query_chinese = ""

    if len(args) < count:
        args.extend(itertools.repeat("?", count - len(args)))

    pinyin = " ".join(args).replace("?", "%") + "$"

    final_query = ""
    if len(query_chinese):
        # WARNING: should avoid sqlite injection
        final_query = f"\"context\" LIKE '{query_chinese}' AND "
    final_query += f"\"pinyin\" LIKE '{pinyin}'"
    if GOOD_QUERY.match(final_query) is None:
        print(final_query)
        # raise ValueError
    final_query += f' AND LENGTH("context")={count} LIMIT 10'
    return final_query


class BotController:
    def __init__(self, conn: aiopgsqldb.PgSQLdb):
        self.bot = Client(
            "wordle",
            config.getint("telegram", "api_id"),
            config.get("telegram", "api_hash"),
            bot_token=config.get("telegram", "token"),
        )
        self.bot.add_handler(
            MessageHandler(self.search, filters.command("search") & filters.text)
        )
        self.conn = conn

    async def start(self) -> None:
        await self.bot.start()

    async def stop(self) -> None:
        await self.bot.stop()

    async def search(self, client: Client, msg: Message) -> None:
        if len(msg.command) <= 2:
            await msg.reply("///")
            msg.continue_propagation()
        try:
            count = int(msg.command[1])
        except ValueError:
            await msg.reply("number error")
            return msg.continue_propagation()
        if count <= 2:
            await msg.reply("Num")
        query = generate_query_statement(int(msg.command[1]), msg.command[2:])
        logging.debug("Query => %s", query)
        ret = await self.conn.query("""SELECT * FROM "hanzi_wordle" WHERE """ + query)
        if len(ret) > 1:
            await msg.reply("\n".join(map(lambda x: x['context'], ret)))
        else:
            await msg.reply("not found")


async def main():
    conn = await aiopgsqldb.PgSQLdb.create("localhost", 5432, "postgres", "", "wordle")
    b = BotController(conn)
    await b.start()
    await pyrogram.idle()
    await b.stop()
    await conn.close()


if __name__ == "__main__":
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    try:
        import coloredlogs

        coloredlogs.install(
            logging.DEBUG,
            format="%(asctime)s,%(msecs)03d - %(levelname)s - %(name)s - %(funcName)s - %(lineno)d - %(message)s",
        )
    except ModuleNotFoundError:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(lineno)d - %(message)s",
        )
    asyncio.run(main())

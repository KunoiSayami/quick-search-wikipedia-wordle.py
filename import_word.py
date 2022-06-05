#!/usr/bin/env python3
import asyncio
import argparse
import json
import pathlib
import re
import os
import sys
import logging
from typing import Generator

import pypinyin
import aiofiles
from libpy3 import aiopgsqldb

CJK = re.compile(r"^[\u4e00-\u9fff]+$")


def get_str(long_str: str) -> Generator[dict, None, None]:
    s = ""
    for slice_ in long_str.splitlines():
        s += slice_.strip()
        if s.startswith("{") and s.endswith("}"):
            tmp = json.loads(s)
            s = ""
            yield tmp
    if s != "":
        yield json.loads(s)


async def main(args: argparse.Namespace):
    conn = await aiopgsqldb.PgSQLdb.create("localhost", 5432, "postgres", "", "wordle")
    path = pathlib.Path(args.directory).resolve()
    count = 0
    for root, dirs, files in os.walk(str(path)):
        for file in files:
            file = pathlib.Path(root, file)
            async with aiofiles.open(str(file)) as fin:
                try:
                    for element in get_str(await fin.read()):
                        title = element["title"]
                        if CJK.match(title) is None:
                            continue
                        if False and (
                            await conn.query1(
                                """SELECT 1 FROM "hanzi_wordle" WHERE "context" = $1""",
                                title,
                            )
                            is not None
                        ):
                            continue
                        pinyin = pypinyin.pinyin(title, style=pypinyin.Style.TONE3)
                        pinyin = " ".join(map(lambda x: x[0], pinyin))
                        # print(title, pinyin)
                        await conn.execute(
                            """INSERT INTO "hanzi_wordle" VALUES ($1, $2)""",
                            pinyin + "$",
                            title,
                        )
                        count += 1
                        print(f"\r{count}", end="")
                except json.JSONDecodeError:
                    print(file)
                    continue
    await conn.close()


if __name__ == "__main__":
    parser_ = argparse.ArgumentParser(prog=sys.argv[0])
    parser_.add_argument("directory", help="directory contains pending import file")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(name)s - %(funcName)s - %(lineno)d - %(message)s",
    )
    asyncio.run(main(parser_.parse_args()))

# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import argparse
import asyncio
import logging
import os

from dotenv import load_dotenv

import catbox.static
from catbox.games import ThisOrThisEngine
from catbox.logger import JsonFormatter
from catbox.site import CatBoxApplication, OAuthDetails, PublicEndpoint


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--oauth-client", default=os.environ.get("CATBOX_CLIENT_ID"))
    parser.add_argument("--oauth-secret", default=os.environ.get("CATBOX_SECRET_ID"))
    parser.add_argument("--local", action="store_true", default=False)
    parser.add_argument("--optimize", action="store_true", default=False)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=33333)
    args = parser.parse_args()

    indent = 2 if args.local else None
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(json_indent=indent))  # type: ignore[no-untyped-call]
    handler.setLevel(logging.INFO)
    logging.getLogger("catbox").addHandler(handler)
    logging.getLogger("catbox").setLevel(logging.INFO)

    loop = asyncio.new_event_loop()

    listen = public = PublicEndpoint(args.host, args.port)
    if not args.local:
        public = PublicEndpoint("db.tea-cats.co.uk", 443)
    if args.optimize:
        catbox.static.enable_optimisation(public)

    app = CatBoxApplication(
        loop,
        {"thisorthat": ThisOrThisEngine},
        oauth=OAuthDetails(args.oauth_client, args.oauth_secret),
        listen=listen,
        public=public,
    )

    task = loop.create_task(app.main(), name="catbox-main")
    loop.run_until_complete(task)


if __name__ == "__main__":
    main()

# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from catbox.user import Notification, User
from dom import Document, Element


def notification_page(user: User, notifications: list[Notification]) -> Document:
    return Document(
        f"CatBox - {user.user_name}'s Notifications",
        Element(
            "header",
            Element("h1", f"{user.user_name}'s Notifications"),
            class_="left-slant",
        ),
        Element(
            "main",
            *(
                Element(
                    "article",
                    Element("p", notification.data, class_="usertext"),
                    Element("p", notification.date.isoformat()),
                    class_="panel" + (" read" if notification.is_read else ""),
                )
                for notification in notifications
            ),
        ),
        styles=["/defs.css", "/style.css"],
    )

// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

function notifications() {
    const login = document.getElementById("login");

    if (!login) {
        return;
    }

    fetch("/me").then(r => r.json()).then(r => {
        const user = r.user;

        if (!user) return;

        const notif = document.createElement("a");
        notif.setAttribute("href", "/notifications");
        notif.classList.add("notification-icon");
        notif.classList.toggle("no-unread", r.user.unread_notifications === 0);
        notif.textContent = r.user.unread_notifications.toString();

        login.replaceChildren(
            document.createTextNode("Logged in as "),
            document.createTextNode(user.user_name),
            notif,
        );
    });
}

function roomCode() {
    const input = document.getElementById("roomcode");
    const info = document.getElementById("roominfo");

    if (!input || !info) return;

    console.log("nyaaa");

    input.addEventListener("keyup", e => {
        if (input.value.length !== 4) return;

        fetch("/room/" + input.value, {"method": "PATCH"}).then(r => r.text()).then(r => info.textContent = r);
    });
}

notifications();
roomCode();

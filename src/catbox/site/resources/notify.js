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

        login.replaceChildren(
            document.createTextNode("Logged in as "),
            document.createTextNode(user.user_name),
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

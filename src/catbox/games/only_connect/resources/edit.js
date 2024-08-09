// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {SocketController, cyrb53} from "/socket.js";


class Section
{
    constructor(base_id) {
        this.panel = document.getElementById(base_id);
        this.toggle = this.panel.querySelector("legend input[type=\"checkbox\"]");
    }
}

class OnlyConnectEditor extends SocketController
{
    connections_section;
    completions_section;
    walls_section;
    vowels_section;

    save_timer;
    last_focus;

    constructor() {
        super();

        document.getElementById("main")
            .addEventListener("change", e => this._on_field_change(e));
        document.getElementById("main")
            .addEventListener("keypress", e => this._on_field_change(e, 500));

        document.getElementById("main")
            .addEventListener("focusin", e => this._on_field_focus(e));
        this.last_focus = null;

        this.connections_section = new Section("connections");
        this.connections_section.toggle.addEventListener("change", e => {
            e.stopPropagation();
            this._send({
                "cmd": e.target.checked ? "enable_section" : "disable_section",
                "section": "connections"
            })
        });

        this.completions_section = new Section("completions");
        this.completions_section.toggle.addEventListener("change", e => {
            e.stopPropagation();
            this._send({
                "cmd": e.target.checked ? "enable_section" : "disable_section",
                "section": "completions"
            })
        });

        this.walls_section = new Section("connecting_walls");
        this.walls_section.toggle.addEventListener("change", e => {
            e.stopPropagation();
            this._send({
                "cmd": e.target.checked ? "enable_section" : "disable_section",
                "section": "connecting_walls"
            })
        });
    }

    _on_ws_open() {
        super._on_ws_open();
        this._send({"cmd": "init"});
    }

    /**
     * @param {Event} event
     * @param {Number} timeout
     */
    _on_field_change(event, timeout = null) {
        if (timeout) {
            if (!this.save_timer) {
                this.save_timer = window.setTimeout(() => this._on_field_change(event), timeout);
            }
            return;
        }

        if (this.save_timer) {
            window.clearTimeout(this.save_timer);
            this.save_timer = null;
        }

        const input = event.target;
        const value = input.value;
        const id = input.id;
        input.setAttribute("data-last-hash", cyrb53(value).toString())

        const [section, question, element] = id.split(".");
        this._send({"cmd": "update", "section": section, "question": question, "element": element, "value": value})
    }

    _on_field_focus(event) {
        const input = event.target.closest("input[id],textarea[id]")
        const id = input?.id || null;

        if (this.last_focus === id) {
            return;
        }

        this._send({"cmd": "announce_editing", "element": id});
        this.last_focus = id;
    }

    editing(data) {
        const existing = Object.fromEntries(
            [...document.querySelectorAll("[editor]")].map(elem => [elem.id || elem.querySelector("input[id],textarea[id]").id, elem])
        );

        for (const {session, username, position} of data.positions) {
            let elem = document.getElementById(position);

            if (!elem) {
                continue;
            }

            elem = elem.closest("label") || elem.parentElement;

            if (!elem) {
                continue;
            }

            elem.setAttribute("editor", username);
            elem.setAttribute("style", "--editor: #" + session.substring(0, 6));

            delete existing[position];
        }

        for (const previous of Object.values(existing)) {
            previous.removeAttribute("editor");
        }
    }

    update(data) {
        this._update_connections(data);
        this._update_completions(data);
        this._update_walls(data);
    }

    _update_connections(data) {
        if (data.connections === null) {
            this.connections_section.toggle.checked = false;
            this.connections_section.panel.setAttribute("disabled", true);
            return;
        }

        data.connections.forEach((question, index) => {
            update(`connections.${index}.connection`, question.connection);
            update(`connections.${index}.details`, question.details);
            question.elements.forEach((value, element) => {
                update(`connections.${index}.${element}`, value)
            });
        })

        this.connections_section.toggle.checked = true;
        this.connections_section.panel.removeAttribute("disabled");
    }

    _update_completions(data) {
        if (data.completions === null) {
            this.completions_section.toggle.checked = false;
            this.completions_section.panel.setAttribute("disabled", true);
            return;
        }

        data.completions.forEach((question, index) => {
            update(`completions.${index}.connection`, question.connection);
            update(`completions.${index}.details`, question.details);
            question.elements.forEach((value, element) => {
                update(`completions.${index}.${element}`, value)
            });
        })

        this.completions_section.toggle.checked = true;
        this.completions_section.panel.removeAttribute("disabled");
    }

    _update_walls(data) {
        if (data.connecting_walls === null) {
            this.walls_section.toggle.checked = false;
            this.walls_section.panel.setAttribute("disabled", true);
            return;
        }

        data.connecting_walls[0].forEach((question, index) => {
            update(`wall0.${index}.connection`, question.connection);
            update(`wall0.${index}.details`, question.details);
            question.elements.forEach((value, element) => {
                update(`wall0.${index}.${element}`, value)
            });
        })

        data.connecting_walls[1].forEach((question, index) => {
            update(`wall1.${index}.connection`, question.connection);
            update(`wall1.${index}.details`, question.details);
            question.elements.forEach((value, element) => {
                update(`wall1.${index}.${element}`, value)
            });
        })

        this.walls_section.toggle.checked = true;
        this.walls_section.panel.removeAttribute("disabled");
    }
}

/**
 *
 * @param {HTMLInputElement|string} input
 * @param {string} value
 */
function update(input, value) {
    const hash = cyrb53(value).toString();

    if (!(input instanceof HTMLInputElement)) {
        const _input = document.getElementById(input);
        if (!input) {
            console.error("Missing element", input)
        }
        input = _input;
    }

    if (input.getAttribute("data-last-hash") === hash) {
        return;
    }

    input.setAttribute("data-last-hash", hash);
    input.value = value;
}

new OnlyConnectEditor();

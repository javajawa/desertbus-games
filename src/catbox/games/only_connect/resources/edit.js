// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {SocketController, cyrb53} from "/socket.js";
import {elemGenerator} from "/elems.js";


const fieldset = elemGenerator("fieldset");
const label = elemGenerator("label");
const input = elemGenerator("input");
const span = elemGenerator("span");

class Section
{
    constructor(base_id, sender) {
        this.panel = document.getElementById(base_id);
        this.toggle = this.panel.querySelector("legend input[type=\"checkbox\"]");
        this.toggle.addEventListener("change", e => {
            e.stopPropagation();
            sender({
                "cmd": e.target.checked ? "enable_section" : "disable_section",
                "section": base_id
            })
        });
    }
}

class OnlyConnectEditor extends SocketController
{
    connections_section;
    completions_section;
    walls_section;
    missing_vowels_section;

    save_timer;
    last_focus;

    constructor() {
        super();

        document.getElementById("title").addEventListener("change", e => this._set_meta(e));
        document.getElementById("title").addEventListener("keypress", e => this._set_meta(e, 500));
        document.getElementById("description").addEventListener("change", e => this._set_meta(e));
        document.getElementById("description").addEventListener("keypress", e => this._set_meta(e, 500));
        document.getElementById("submit").addEventListener("click", () => this._send({"cmd": "submit"}));

        document.getElementById("main")
            .addEventListener("change", e => this._on_field_change(e));
        document.getElementById("main")
            .addEventListener("keypress", e => this._on_field_change(e, 500));

        document.getElementById("main")
            .addEventListener("focusin", e => this._on_field_focus(e));
        this.last_focus = null;

        this.connections_section = new Section("connections", this._send.bind(this));
        this.completions_section = new Section("completions", this._send.bind(this));
        this.walls_section = new Section("connecting_walls", this._send.bind(this));
        this.missing_vowels_section = new Section("missing_vowels", this._send.bind(this));

        this.missing_vowels_section.panel.querySelector("button").addEventListener("click", e => {
            e.preventDefault();
            this._send({"cmd": "update", "section": "missing_vowels", "question": "new", "element": "", "value": ""});
        })
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
        const input = event.target;
        const id = input.id;

        if (input.type === "file") {
            return this._on_image_change(input, id);
        }

        if (timeout) {
            if (id.includes(".new")) {
                return;
            }
            if (!this.save_timer) {
                this.save_timer = window.setTimeout(() => this._on_field_change(event), timeout);
            }
            return;
        }

        if (this.save_timer) {
            window.clearTimeout(this.save_timer);
            this.save_timer = null;
        }

        const value = input.type === "checkbox" ? input.checked : input.value;

        if (id.includes(".new")) {
            input.value = "";
        } else {
            input.setAttribute("data-last-hash", cyrb53(value.toString()).toString());
        }

        const [section, question, element] = id.split(".");
        this._send({"cmd": "update", "section": section, "question": question, "element": element, "value": value})
    }

    /**
    *
    * @param {HTMLInputElement} input
    * @param {string} id
    * @private
    */
    _on_image_change(input, id) {
        const [section, question, element] = id.split(".");

        if (input.files.length === 0) {
            return;
        }

        const file = input.files[0];

        // Check if this is a file that is already uploaded.
        const hash = cyrb53(file.name + file.lastModified + file.type + file.size);
        if (hash === input.getAttribute("hash")) {
            return;
        }
        input.setAttribute("hash", hash);


        const upload = new Request("/blob", {"method": "POST", body: file});
        this._log("Starting upload");

        fetch(upload).then(async result => {
            if (result.status !== 201) {
                this._log(await result.text());
                return;
            }

            const data = await result.json();
            this._log("Uploaded as blob", data.id);

            this._send({"cmd": "update", "section": section, "question": question, "element": element.replace("m", ""), "value": "blob::" + data.id});
        });
    }

    _remove_media(input, id) {
        const [section, question, element] = id.split(".");

        this._send({"cmd": "update", "section": section, "question": question, "element": element, "value": null});
    }

    _set_meta(event = null, timeout = null) {
        if (event) event.stopPropagation();
        if (timeout) {
            if (!this.save_timer) {
                this.save_timer = window.setTimeout(() => this._set_meta(), timeout);
            }
            return;
        }

        if (this.save_timer) {
            window.clearTimeout(this.save_timer);
            this.save_timer = null;
        }

        this._send({
            "cmd": "set_meta",
            "title": document.getElementById("title").value,
            "description": document.getElementById("description").value
        });
    }

    _on_field_focus(event) {
        const input = event.target.closest("input[id],textarea[id]")
        const id = (input?.id?.replace(/-prompt$/, "") || null);

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
        this._update_missing_vowels(data);
    }

    _update_connections(data) {
        if (data.connections === null) {
            this.connections_section.toggle.checked = false;
            this.connections_section.panel.setAttribute("disabled", true);
            return;
        }

        this._update_block("connections", data.connections);

        this.connections_section.toggle.checked = true;
        this.connections_section.panel.removeAttribute("disabled");
    }

    _update_completions(data) {
        if (data.completions === null) {
            this.completions_section.toggle.checked = false;
            this.completions_section.panel.setAttribute("disabled", true);
            return;
        }

        this._update_block("completions", data.completions);

        this.completions_section.toggle.checked = true;
        this.completions_section.panel.removeAttribute("disabled");
    }

    _update_block(prefix, data) {
        data.forEach((question, index) => {
            document.getElementById(`${prefix}.${index}`).classList.toggle("type_text", question.question_type === "text");
            document.getElementById(`${prefix}.${index}`).classList.toggle("type_media", question.question_type === "media");

            update_check(`${prefix}.${index}.media`, question.question_type === "media");
            update(`${prefix}.${index}.connection`, question.connection);
            update(`${prefix}.${index}.details`, question.details);
            question.elements.forEach((value, element) => {
                update(`${prefix}.${index}.${element}`, typeof value === "string" ? value : "");
                update(`${prefix}.${index}.${element}-preview`, typeof value === "object" ? value.url : "");
            });
        })

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

    _update_missing_vowels(data) {
        if (data.missing_vowels === null) {
            this.missing_vowels_section.toggle.checked = false;
            this.missing_vowels_section.panel.setAttribute("disabled", true);
            return;
        }

        data.missing_vowels.forEach((group, idx) => {
            const id = "missing_vowels." + idx.toString();
            let currentBlock = document.getElementById(id);

            if (group === null) {
                if (currentBlock) currentBlock.parentElement.removeChild(currentBlock);
                return;
            }

            if (!currentBlock) {
                currentBlock = fieldset(
                    {"id": id},
                    label({"for": id + ".connection"}, "Connection:", input({"id": id + ".connection"})),
                    label({"for": id + ".new.0"}, "New Entry:", input({"id": id + ".new.0"})),
                )
                this.missing_vowels_section.panel.insertBefore(
                    currentBlock,
                    this.missing_vowels_section.panel.querySelector("button"),
                );
            }

            [...currentBlock.querySelectorAll("[row]")].forEach(elem => elem.classList.add("to-delete"));

            group.words.forEach(([idx, answer, prompt, _]) => {
                let elem = currentBlock.querySelector(`[row="${idx}"]`);
                if (!elem) {
                    elem = label(
                        {"row": idx.toString(), "for": `${id}.${idx}.0`},
                        input({"id": `${id}.${idx}-prompt`}),
                        span(" ⇒ "),
                        input({"id": `${id}.${idx}`}),
                    )
                    currentBlock.insertBefore(elem, currentBlock.lastElementChild);
                }
                elem.classList.remove("to-delete");

                update(`${id}.${idx}`, answer);
                update(`${id}.${idx}-prompt`, prompt);
                document.getElementById(`${id}.${idx}-prompt`).setAttribute(
                    "pattern",
                    "^" + answer.toUpperCase().replaceAll(/[ AIEOU]/g, "").split("").join(" ?") + "$"
                );
            });

            [...currentBlock.querySelectorAll("[row].to-delete")].forEach(
                elem => elem.parentElement.removeChild(elem)
            );
        });

        this.missing_vowels_section.toggle.checked = true;
        this.missing_vowels_section.panel.removeAttribute("disabled");
    }
}

/**
 *
 * @param {HTMLInputElement|HTMLImageElement|string} input
 * @param {string} value
 */
function update(input, value) {
    const hash = cyrb53(value).toString();

    if (!(input instanceof HTMLInputElement) && !(input instanceof HTMLImageElement)) {
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
    input.src = value;
    input.value = value;
}

/**
 *
 * @param {string} input
 * @param {boolean} value
 */
function update_check(input, value) {
    const hash = cyrb53(value.toString()).toString();

    const _input = document.getElementById(input);
    if (!input) {
        console.error("Missing element", input)
    }

    if (_input.getAttribute("data-last-hash") === hash) {
        return;
    }

    _input.setAttribute("data-last-hash", hash);
    _input.checked = value;
}

new OnlyConnectEditor();

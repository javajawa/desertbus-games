// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {ThisOrThatSocket} from "./general.js";
import {elemGenerator, documentFragment} from "/elems.js";

const button = elemGenerator("button");
const div = elemGenerator("div");

class ThisOrThatGM extends ThisOrThatSocket {
    constructor() {
        super();
        this._actions = document.getElementById("game-actions");
    }

    setup(data) {
        super.setup(data);

        this._actions.appendChild(documentFragment(
            button("Start The Game", {"class": "button pre-game", "click": () => this._send({"cmd": "start"})}),
            button("Next Question", {"class": "button answer", "click": () => this._send({"cmd": "next_question"})}),
            button("Reveal Answer", {"class": "button question", "click": () => this._send({"cmd": "reveal_answer"})}),
            ...(data.status.teams || []).map(team => div(
                team.name,
                {"class": "panel", "style": "display: inline-block", "id": "actions-" + team.id},
                this._make_buttons(v => this._send({"cmd": "vote", "team": team.id, "vote": v}), "button question")
            ))
        ));
        this._show_question(data.status);
    }

    _show_question(state) {
        super._show_question(state);
        for (const team of state.teams) {
            for (const vote of this._vote_options) {
                this._actions.querySelector(`#actions-${team.id}>.${vote}`)
                    ?.classList?.toggle("active", team.voted === vote);
            }
        }
    }

    state_change(state) {
        for (const check of ["pre-game", "question", "answer", "post-game"]) {
            this._actions.classList.toggle(check, state.state === check);
        }
        super.state_change(state);
    }
}

new ThisOrThatGM();

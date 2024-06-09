// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {ThisOrThatSocket} from "./general.js";
import {documentFragment, elemGenerator} from "/elems.js";

const div = elemGenerator("div");

class ThisOrThatPlayer extends ThisOrThatSocket {
    constructor() {
        super();
        this._actions = document.getElementById("game-actions");
    }

    setup(data) {
        super.setup(data);
        this._my_team = data.status.self;

        while (this._actions.lastChild) {
            this._actions.removeChild(this._actions.lastChild);
        }

        this._headline = div({"id": "pl-headline"}, "Playing for ", this._my_team.name);
        this._actions.appendChild(documentFragment(
            this._headline,
            this._make_buttons(v => this._send({"cmd": "vote", "team": this._my_team.id, "vote": v}), "button button-large question")
        ));
        this._show_question(data.status);
    }

    _show_question(state) {
        super._show_question(state);
        for (const vote of this._vote_options) {
            this._actions.querySelector(`.button.${vote}`)?.classList?.toggle("active", state.self.voted === vote);
        }
    }

    state_change(state) {
        for (const check of ["pre-game", "question", "answer", "post-game"]) {
            this._actions.classList.toggle(check, state.state === check);
        }
        super.state_change(state);
    }
}

new ThisOrThatPlayer();

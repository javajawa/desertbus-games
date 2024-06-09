// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {ThisOrThatSocket} from "./general.js";
import {documentFragment, elemGenerator} from "/elems.js";

const div = elemGenerator("div");

class ThisOrThatAudience extends ThisOrThatSocket {
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

        this._headline = div({"id": "pl-headline"}, "Chat Player");
        this._actions.appendChild(documentFragment(
            this._headline,
            this._make_buttons(v => this._send({"cmd": "vote", "team": null, "vote": v}), "button button-large question")
        ));
        this._show_question(data.status);
    }

    _show_question(state) {
        super._show_question(state);
        if (state.state !== "question") {
            this._my_vote = null;
        }
        this._show_vote();
    }

    _show_vote() {
        for (const vote of this._vote_options) {
            this._actions.querySelector(`.button.${vote}`)
                ?.classList?.toggle("active", this._my_vote === vote);
        }
    }

    state_change(state) {
        for (const check of ["pre-game", "question", "answer", "post-game"]) {
            this._actions.classList.toggle(check, state.state === check);
        }
        super.state_change(state);
    }

    voted(data) {
        this._my_vote = data.vote;
        this._show_vote();
    }
}

new ThisOrThatAudience();

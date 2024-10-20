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
        this._info = div("");
        super.setup(data);
        this._my_team = data.status.self;

        while (this._actions.lastChild) {
            this._actions.removeChild(this._actions.lastChild);
        }

        this._headline = div({"id": "pl-headline"}, "Playing for ", this._my_team.name);
        this._actions.appendChild(documentFragment(
            this._headline,
            this._info,
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
        this._actions.classList.toggle("question", state.state === "question");
        super.state_change(state);

        switch (state.state) {
            case "question": this._info.textContent = ""; break;
            case "answer": this._info.textContent = "The correct answer was " + state.question.headline + ". (waiting for next question)"; break;
            case "pre-game": this._info.textContent = "Waiting for the game to start"; break;
            case "post-game": this._info.textContent = "Thanks for playing!"; break;
        }
    }
}

new ThisOrThatPlayer();

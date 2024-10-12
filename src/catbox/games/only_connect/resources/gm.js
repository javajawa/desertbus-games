// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {OnlyConnectSocket} from "./onlyconnect.js";
import {elemGenerator} from "/elems.js";

const div = elemGenerator("div");
const button = elemGenerator("button");

class OnlyConnectManager extends OnlyConnectSocket {
    constructor() {
        const actions = document.getElementById("game-actions");
        actions.appendChild(div({"id": "scores"}))
        super();
        this._help = document.getElementById("gi-how-to");
        this._actions = actions;
        this._show_details = true;
    }

    /**
     * @param {OnlyConnectSetup} data
     */
    setup(data) {
        const rounds = data.episode.rounds;

        this._actions.appendChild(
            div(
                "Round Actions",
                this._action("NEXT_QUESTION", "Pick Next Question"),
                this._action("NEXT_CLUE", "Show Next Clue"),
                this._action("LOCK_IN", "Lock-In Answer"),
                this._action("REVEAL_FOR_STEAL", "Guess Next Group", {}, {"id": "wall-reveal"}),
            )
        );

        if (data.state.teams.length === 1) {
            this._actions.appendChild(
                div(
                    "Scoring",
                    this._action("SCORE_TEAM1", "Correct: Score"),
                    this._action("SCORE_INCORRECT", "Incorrect: Nil Point"),
                )
            );
        } else {
            this._actions.appendChild(
                div(
                    "Scoring",
                    this._action("SCORE_TEAM1", `Score for ${data.state.teams[0].name}`),
                    this._action("SCORE_TEAM2", `Score for ${data.state.teams[1].name}`),
                    this._action("REVEAL_FOR_STEAL", "Incorrect - Start Steal"),
                    this._action("SCORE_STEAL", "Score stolen answer"),
                    this._action("SCORE_INCORRECT", "No Score"),
                )
            );
        }

        this._actions.appendChild(
            div(
                "Round Selector",
                this._action("START_NEXT_ROUND", "Start Next Round"),
                this._skip(rounds.connections, "⏩ Rd.1: Connections", "CONNECTIONS"),
                this._skip(rounds.completions, "⏩ Rd.2: Sequences", "COMPLETIONS"),
                this._skip(rounds.walls, "⏩ Rd.3: Connecting Wall", "CONNECTING_WALLS"),
                this._skip(rounds.vowels, "⏩ Rd.4: Missing Vowels", "MISSING_VOWELS"),
                this._skip(rounds.vowels, "⏩ End Game Now", "POST_GAME"),
            )
        )

        super.setup(data);

        document.addEventListener("keypress", e => {
            if (e.code !== "Space") return;

            const options = document.querySelectorAll('[data-action]:not([disabled])');

            if (options.length === 1) {
                options[0].click();
            }
        })
    }

    /**
     * @param {OnlyConnectStatus} data
     */
    state_change(data) {
        super.state_change(data);

        const actions = [...data.state.actions || []];

        [...document.querySelectorAll("[data-action]")]
            .map(elem => elem.toggleAttribute("disabled", !actions.includes(elem.getAttribute("data-action"))));
    }

    _set_play_area(round, state, ...elements) {
        this._actions.setAttribute("round", round);

        return super._set_play_area(round, state, ...elements);
    }

    /**
     *
     * @param {!string} ident
     * @param {!string} label
     * @param {?Object} extra
     * @param {Object} props
     * @returns {HTMLElement}
     * @private
     */
    _action(ident, label, extra = {}, props = {}) {
        return button(label, props, {
            "class": "button",
            "data-action": ident,
            "disabled": "disabled",
            "click": () => this._send({...{"cmd": "action", "action": ident}, ...extra})
        });
    }

    _skip(condition, label, round) {
        return condition ? button(
            label,
            {"class": "button", "click": () => this._send({"cmd": "skip", "round_name": round})}
        ) : null;
    }
}



new OnlyConnectManager();

// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {cyrb53, SocketController} from "/socket.js";
import {elemGenerator} from "/elems.js";

const div = elemGenerator("div");
const h1 = elemGenerator("h1");


/**
 * @property {string} title
 * @property {string} author
 * @property {string} description
 * @property {Rounds} rounds
 */
class Episode {}

/**
 * @property {boolean} connections
 * @property {boolean} completions
 * @property {boolean} walls
 * @property {boolean} vowels
 */
class Rounds {}

/**
 * @property {Number!} id
 * @property {Number!} name
 * @property {Number!} score
 */
class Team {}

/**
 * @property {string} round
 * @property {string} state
 * @property {string[]} actions
 * @property {Team[]} teams
 * @property {Team?} active_team
 * @property current
 * @property {string[]?} available
 */
class OnlyConnectState {}

/**
 * @property {OnlyConnectState} state
 */
class OnlyConnectStatus {}

/**
 * @property {Episode} episode
 * @property {OnlyConnectState} state
 */
class OnlyConnectSetup extends OnlyConnectStatus {}

const question_key = {
    "𓇌": "SELECT_TWO_REEDS",
    "𓃭": "SELECT_LION",
    "𓎛": "SELECT_TWISTED_FLAX",
    "𓆑": "SELECT_HORNED_VIPER",
    "𓈗": "SELECT_WATER",
    "𓂀": "SELECT_EYE_OF_HORUS",
}
const wall_question_key = {
    "𓃭": "SELECT_LION",
    "𓈗": "SELECT_WATER",
}

/**
 */
export class OnlyConnectSocket extends SocketController {
    constructor() {
        super();
        this.episode = null;
        this._scores = document.getElementById("scores");
        this._area = document.getElementById("play-area");
        this._show_details = false;
    }

    _on_ws_open() {
        this._send({"cmd": "setup"});
    }

    /**
     * @param {OnlyConnectSetup} data
     */
    setup(data) {
        this.episode = data.episode;
        this.state_change(data);
        this._show_scores(data.state);

        if (document.getElementById("game-info")) {
            document.getElementById("gi-title").textContent = this.episode.title;
            document.getElementById("gi-author").textContent = this.episode.author;
            document.getElementById("gi-description").textContent = this.episode.description;
        }
    }

    /**
     * @param {OnlyConnectStatus} status
     */
    state_change(status) {
        const state = status.state

        this._show_scores(state);

        if (state.state === "post-round") {
            this._show_post_round(state);
            return;
        }

        switch (state.round) {
            case "pre-game": this._show_pregame(); break;
            case "post-game": this._show_post_round(state); break;
            case "connections":
            case "completions":
                this._show_connections(state);
                break;
            case "connecting_walls": this._show_connecting_walls(state); break;
            case "missing_vowels": this._show_missing_vowels(state); break;

            default: console.error("Unknown state", state.round);
        }
    }

    _set_play_area(round, state, ...elements) {
        if (!this._area) return;

        this._area.setAttribute("round", round);
        this._area.setAttribute("state", state);
        this._area.replaceChildren(...elements.flat(3).filter(x => x));
    }

    _show_pregame() {
        this._set_play_area(
            "pre-game",
            "pre-game",
            div(
                h1(this.episode.title, {"class": "gi-title no-overlay"}),
                div(this.episode.author, {"class": "gi-author no-overlay"}),
                div(this.episode.description, {"class": "gi-description usertext no-overlay"}),
                div("Waiting for controller to start game...", {"class": "no-overlay"}),
            ),
        );
    }

    /**
     * @param {OnlyConnectState} state
     */
    _show_post_round(state) {
        const current = (state.round !== "post-game");

        let scoreboard = ""
        if (state.teams) {
            if (state.teams.length > 1) {
                /** @var {([!Number, !string])[]} scores */
                let scores = state.teams.map(team => [team.score, team.name]);
                scores.sort((a, b) => b[0] - a[0]);
                scoreboard = (current ? "Current leader is " : "The winner is ") + scores[0][1] + "\n\nFinal Scores:\n" + scores.map(([score, team], position) => `${position+1}. ${team} (${score})`).join("\n")
            } else {
                scoreboard = `${current ? "Current" : "Final"} Score for ${state.teams[0].team}: ${state.teams[0].score}`;
            }
        }

        this._set_play_area(
            "post-game",
            "post-game",
            div(
                h1(this.episode.title, {"class": "gi-title no-overlay"}),
                div("Contributed by ", this.episode.author, {"class": "gi-author no-overlay"}),
                div(current ? "End of Round": "Thanks for Playing", {"class": "no-overlay"}),
                div(scoreboard, {"class": "usertext no-overlay"}),
            )
        );
    }

    /**
     *
     * @param {OnlyConnectState} state
     * @private
     */
    _show_connections(state) {
        if (state.state === "pre-round") {
            this._set_play_area(
                state.round,
                state.state,
                // FIXME: This currently shows for both Connections and Completions
                h1("Connections Round", {"class": "no-overlay"}),
                div(
                    "Find the connection between 4 things. ",
                    "The active team can ask to see the next clue at any time, ",
                    "but can only buzz in to answer once. The host may ask for ",
                    "more details on an answer or (if incorrect) give the opposing ",
                    "team a chance to steal. ",
                    "Correct answers score fewer points for each clue that was revealed. ",
                    "The opposing team attempting to steal always reveals all clues.",
                    {"class": "no-overlay"}
                )
            );
            return;
        }

        if (state.state === "select") {
            this._set_play_area(
                state.round,
                state.state,
                h1(state.active_team.name, " to pick a question", {"class": "no-overlay"}),

                ...Object.entries(question_key).map(([symbol, selector]) => div(
                    symbol,
                    {
                        "class": "button button-large" + (state.available.includes(selector) ? "" : " button-disabled"),
                        "click": () => this._send({"cmd": "action", "action": selector}),
                    }
                ))
            )
            return;
        }

        // Set up the play area for animations
        if (this._area.getAttribute("round") !== state.round || this._area.getAttribute("state") !== "question") {
             this._set_play_area(
                state.round,
                "question",
                div(state.active_team.name, "'s question", {"class": "no-overlay"}),
                [5, 3, 2, 1].map((points,  idx) => div(
                    {"class": "question-clue", "id": "block" + idx},
                    div({"class": "progress-bar", "id": "overbar" + idx, "data-hidden": true}, points.toString() + " Points"),
                    div({"class": "clue", "id": "clue" + idx, "data-hidden": true})
                )),
                div({"class": "connection", "id": "connection", "data-hidden": true}),
                this._show_details ? div({"class": "details", "id": "details", "data-hidden": true}) : null,
             );

             if (state.round === "completions") {
                 const clue_elem = document.getElementById("clue3");
                 clue_elem.textContent = "?"
                 clue_elem.removeAttribute("data-hidden");
             }
        }

        state.current.elements.map((clue, idx) => {
            const clue_elem = document.getElementById("clue" + idx);

            clue_elem.textContent = clue;
            clue_elem.toggleAttribute("data-hidden", !clue);

            const bar_elem = document.getElementById("overbar" + idx);
            bar_elem.toggleAttribute("data-hidden", idx+1 !== state.current.revealed);
        });

        const connect_elem = document.getElementById("connection");
        connect_elem.textContent = state.current.connection;
        connect_elem.toggleAttribute("data-hidden", !state.current.connection);

        if (this._show_details) {
            const connect_elem = document.getElementById("details");
            connect_elem.textContent = state.current.details;
            connect_elem.toggleAttribute("data-hidden", !state.current.details);
        }
    }

    /**
     * @param {OnlyConnectState} state
     */
    _show_missing_vowels(state) {
        if (state.state === "pre-round") {
            this._set_play_area(
                state.round,
                state.state,
                h1("Missing Vowels", {"class": "no-overlay"}),
                div(
                    "The team(s) will be presented with short phrases with ",
                    "the vowels missing and the spaces moved about (the remaining ",
                    "letter are in the correct order). These phrases are linked by ",
                    "the listed theme. ",
                    "Each team can buzz in once per prompt, and scores one point for ",
                    "a correct answer.",
                    {"class": "no-overlay"},
                )
            );
            return;
        }

        this._set_play_area(
            state.round,
            "vowels",
            div({"class": "no-overlay"}),
            div({"class": "connection"}, state.question.connection),
            div({"class": "question-text"}, state.question.text),
            state.question.answer ? div({"class": "answer"}, state.question.answer) : null,
        )
    }

    /**
     * @param {OnlyConnectState} state
     */
    _show_connecting_walls(state) {
        if (state.state === "pre-round") {
            this._set_play_area(
                state.round,
                state.state,
                h1("Connecting Wall", {"class": "no-overlay"}),
            );
            return;
        }

        if (state.state === "select") {
            this._set_play_area(
                state.round,
                state.state,
                h1(state.active_team.name, " to pick a question", {"class": "no-overlay"}),

                ...Object.entries(wall_question_key).map(([symbol, selector], index) => div(
                    symbol,
                    {
                        "class": "button button-large" + (state.available[index] ? "" : " button-disabled"),
                        "click": () => this._send({"cmd": "action", "action": selector}),
                    }
                ))
            )
            return;
        }

        // Set up the play area for animations
        if (this._area.getAttribute("round") !== state.round || this._area.getAttribute("state") !== "wall") {
            this._set_play_area(
                state.round,
                "wall",
                state.current.grouped.map(clue => div({"id": cyrb53(clue), "class": "button grouped"}, clue)),
                state.current.not_found.map(clue => div({"id": cyrb53(clue), "class": "button error"}, clue)),
                state.current.ungrouped.map(clue => div({
                    "id": cyrb53(clue),
                    "class": "button ungrouped",
                    "click": (e) => {
                        e.target.classList.toggle("selected");
                        window.setTimeout(() => this._send({"cmd": "toggle", "word": clue}), 20);
                    }
                }, clue)),
                div(
                    {"id": "strikes"},
                    div({"class": "strike"}, "⨯"),
                    div({"class": "strike"}, "⨯"),
                    div({"class": "strike"}, "⨯"),
                    div(div({"id": "group_info"}), div({"id": "group_details"})),
                ),
            );
        }

        state.current.grouped.forEach(((clue, idx) => {
            const col = 1 + (idx % 4);
            const row = 1 + ((idx - col + 1) / 4);

            const elem = document.getElementById(cyrb53(clue));

            elem.style.gridArea = `${row} / ${col} / ${row + 1} / ${col + 1}`;
            elem.classList.add("grouped");
            elem.classList.remove("ungrouped");
            elem.classList.remove("selected");
        }));

        state.current.not_found.forEach(((clue, idx) => {
            idx += state.current.grouped.length;
            const col = 1 + (idx % 4);
            const row = 1 + ((idx - col + 1) / 4);

            const elem = document.getElementById(cyrb53(clue));

            elem.style.gridArea = `${row} / ${col} / ${row + 1} / ${col + 1}`;
            elem.classList.add("not_found");
            elem.classList.remove("ungrouped");
            elem.classList.remove("selected");
        }));

        const was_a_group = document.querySelectorAll(".ungrouped.selected").length === 4;

        document.querySelectorAll(".ungrouped").forEach((elem, index) => {
            const was_selected = elem.classList.contains("selected");
            elem.classList.toggle("selected", state.current.selected.includes(index));
            if (was_a_group && was_selected && !state.current.selected.includes(index)) {
                elem.classList.add("error");
                window.setTimeout(() => elem.classList.remove("error"), 1000);
            }
        });

        document.getElementById("group_info").style.display = "none";
        document.getElementById("group_details").style.display = "none";

        if (state.current.confirming) {
            if (state.current.confirming.connection) {
                document.getElementById("group_info").textContent = state.current.confirming.connection;
                document.getElementById("group_info").style.display = "block";
            }
            if (state.current.confirming.details) {
                document.getElementById("group_details").textContent = state.current.confirming.details;
                document.getElementById("group_details").style.display = "block";
            }
            const ids = state.current.confirming.clues.map(cyrb53).map(x=>x.toString());
            this._area.querySelectorAll("div").forEach((elem, idx) => {
                elem.classList.toggle("guessing", ids.includes(elem.id));
            })
        }

        document.querySelectorAll(".strike").forEach((elem, index) => {
            elem.classList.toggle("used", index >= state.current.strikes);
            elem.style.display = state.current.strikes ? "" : "none";
        })
    }

    /**
     * @param {OnlyConnectState} state
     */
    _show_scores(state) {
        if (!this._scores) return;
        if (!state.teams) return;

        for (let team of state.teams) {
            let elem = document.getElementById("score-" + team.id);

            if (!elem) {
                elem = div(
                    {"id": "score-" + team.id, "style": "white-space: nowrap", "class": "scorebox"},
                    div(team.name),
                    div({"class": "score"})
                );
                this._scores.appendChild(elem);
            }

            elem.querySelector(".score").textContent = team.score;
        }
    }
}

if (document.body.hasAttribute("autoconnect")) {
    new OnlyConnectSocket();
}

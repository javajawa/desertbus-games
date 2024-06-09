// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause
// noinspection JSUnusedGlobalSymbols

import {SocketController} from "/socket.js";
import {elemGenerator} from "/elems.js";

const div = elemGenerator("div");
const span = elemGenerator("span");
const button = elemGenerator("button");

/**
 * @property {string} title
 * @property {string} author
 * @property {string} description
 * @property {string} this
 * @property {string} that
 * @property {boolean} has_both
 * @property {boolean} has_neither
 */
class Episode {
}

/**
 * @property {Number!} score
 * @property {Number!} count
 * @property {Number!} votes
 */
class Audience {}

/**
 * @property {Number!} id
 * @property {Number!} name
 * @property {Number!} score
 * @property {Number|String!} voted
 */
class TeamStub {}

/**
 * @property {string!} uuid
 * @property {string?} question_text
 * @property {Blob?} question_media
 * @property {string?} answer_text
 * @property {Blob?} answer_media
 * @property {boolean!} is_this
 * @property {boolean!} is_that
 */
class Question {}

/**
 * @property {string?} headline
 * @property {string?} answer
 * @property {string?} text
 * @property {Blob?} media
 */
class QuestionStub {}

/**
 * @property {string!} blob_id
 * @property {string!} mimetype
 * @property {string!} url
 * @property {Number!} width
 * @property {Number!} height
 */
class Blob {}

/**
 * @property {string} state
 * @property {Audience?} audience
 * @property {TeamStub[]?} teams
 * @property {TeamStub?} self
 * @property {QuestionStub?} question
 * @property {Question?} full_question
 */
class State {}

/**
 * @property {string} state
 * @property {Episode} episode
 * @property {State} status
 */
class Setup {}


/**
 * @property {Episode} episode
 */
export class ThisOrThatSocket extends SocketController {
    constructor() {
        super();
        this.episode = null;
        this._scores = document.getElementById("scores");
        this._headline = document.getElementById("pl-headline");
        this._play_text = document.getElementById("pl-text");
        this._play_media = document.getElementById("pl-media");
        this._play_area = this._headline?.offsetParent || null;
    }


    _on_ws_open() {
        this._send({"cmd": "setup"});
    }

    /**
     * @param {Setup} data
     */
    setup(data) {
        this.episode = data.episode;

        if (document.getElementById("game-info")) {
            document.getElementById("gi-title").textContent = this.episode.title;
            document.getElementById("gi-author").textContent = this.episode.author;
            document.getElementById("gi-description").textContent = this.episode.description;
        }

        this._vote_options = ["this", "that"];
        if (data.episode.has_both) this._vote_options.push("both");
        if (data.episode.has_neither) this._vote_options.push("neither");

        this.state_change(data.status);
        this._show_scores(data.status);
    }

    /**
     * @param {State} state
     */
    state_change(state) {
        switch (state.state) {
            case "pre-game": this._show_pregame(); break;
            case "post-game": this._show_postgame(state); break;
            default: this._show_question(state);
        }
        this._show_scores(state);
    }

    /**
     *
     * @param {string?} headline
     * @param {string?} text
     * @param {Blob?} media
     * @private
     */
    _set_play_area(headline, text, media) {
        if (!this._play_area) return;

        if (headline) {
            this._headline.textContent = headline;
            this._headline.style.display = "";
        } else {
            this._headline.textContent = "";
            this._headline.style.display = "none";
        }

        if (text) {
            this._play_text.textContent = text;
            this._play_text.style.display = "";
        } else {
            this._play_text.textContent = "";
            this._play_text.style.display = "none";
        }

        this._play_area.classList.toggle("no-media", !media);
        if (media) {
            const heightAvailable = this._play_area.offsetHeight - this._play_media.offsetTop;
            const scale = Math.min(heightAvailable / media.height, 4);

            this._play_media.setAttribute("src", media.url);
            this._play_media.setAttribute("width", (scale * media.width).toFixed(0));
            this._play_media.setAttribute("height", (scale * media.height).toFixed(0));
            this._play_media.style.display = "";
        } else {
            this._play_media.textContent = "";
            this._play_media.style.display = "none";
        }
    }

    _show_pregame() {
        this._set_play_area(
            `"${this.episode.title}" by ${this.episode.author}`,
            this.episode.description,
            null
        );
    }

    /**
     * @param {State} state
     */
    _show_postgame(state) {
        let scoreboard = ""
        if (state.teams) {
            /** @var {([!Number, !string])[]} scores */
            let scores = state.teams.map(team => [team.score, team.name]);
            if (state.audience) {
                scores.push([state.audience.score, "Chat"]);
            }
            scores.sort((a, b) => b[0] - a[0]);
            scoreboard = "The winner is: " + scores[0][1] + "\n\nFinal Scores:\n" + scores.map(([score, team], position) => `${position+1}. ${team} (${score})`).join("\n")
        }

        this._set_play_area(
            `"${this.episode.title}" by ${this.episode.author}`,
            "Thank you for playing\n\n" + scoreboard,
            null
        );
    }

    /**
     * @param {State} state
     */
    _show_question(state) {
        this._set_play_area(
            state.question?.headline,
            state.question?.text,
            state.question?.media
        );
    }

    /**
     * @param {State} state
     */
    _show_scores(state) {
        if (!this._scores) return;
        if (!state.teams) return;

        for (let team of state.teams) {
            let elem = document.getElementById("score-" + team.id);

            if (!elem) {
                elem = div(
                    {"id": "score-" + team.id, "style": "white-space: nowrap"},
                    div(team.name),
                    div({"class": "score"})
                );
                this._scores.appendChild(elem);
            }

            elem.querySelector(".score").textContent = team.score;

            const orange = (
                (state.state === "question" && !team.voted)
                || (state.state === "answer" && team.voted !== state.question.answer)
            )
            const green = (
                (state.state === "question" && team.voted)
                || (state.state === "answer" && team.voted === state.question.answer)
            )

            elem.classList.toggle("not-voted", orange);
            elem.classList.toggle("voted", green);
        }

        if (!state.audience) return;

        let elem = document.getElementById("score-audience");

        if (!elem) {
            elem = div(
                {"id": "score-audience"},
                div("Chat ", span(state.audience.room, {"class": "roomcode"}), {"style": "white-space: nowrap; position: relative; z-index: 1"}),
                div({"class": "score", "style": "position: relative; z-index: 1"})
            );
            this._scores.appendChild(elem);
        }

        if (state.state === "question") {
            const voted = state.audience.count ? (100 * state.audience.voted / state.audience.count).toFixed(0) : 0;
            elem.setAttribute("style", "--voted: " + voted + "%");
            elem.classList.toggle("voted", voted > 70);
            elem.classList.toggle("not-voted", voted < 20);
        } else {
            elem.setAttribute("style", "--voted: 0%");
            elem.classList.toggle("voted", false);
            elem.classList.toggle("not-voted", false);
        }

        elem.querySelector(".score").textContent = state.audience.score.toFixed(1);
    }

    _make_buttons(callback, classes = "button") {
        const b = (value, text) => button(text, {"click": e => callback(value, e), "class": classes + " " + value});

        const buttons = [b("this", this.episode.this), b("that", this.episode.that)];
        this.episode.has_both && buttons.push(b("both", "Both"));
        this.episode.has_neither && buttons.push(b("neither", "Neither"));

        return buttons;
    }
}

if (document.body.hasAttribute("autoconnect")) {
    new ThisOrThatSocket();
}

// SPDX-FileCopyrightText: 2023 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

"use strict";


/**
 * @property {!string} id
 * @property {!string} connection
 * @property {!string} credit
 * @property {!Array<string>} clues
 * @property {!boolean} is_sequence
 */
class Question {}

/**
 * @property {!boolean} team_competition
 * @property {!Array<{number, number}>} scores
 *
 * @property {!Number} current_team
 * @property {!Number} current_round
 * @property {?Number} selecting
 * @property {Array<boolean>} available_questions
 *
 * @property {?Question} current_question
 * @property {!Number} revealed_clues
 * @property {!boolean} answer_revealed
 */
class OverallState {}

class Controller {
  constructor() {
    this._log = document.getElementById("log");

    this.init_buttons();
    this.connect();
  }

  init_buttons() {
    document.getElementById("nextClue")
        .addEventListener("click", () => this.socket.send(JSON.stringify({"type": "clue"})));
    document.getElementById("revealAnswer")
        .addEventListener("click", () => this.socket.send(JSON.stringify({"type": "reveal"})));
    document.getElementById("answerGood")
        .addEventListener("click", () => this.socket.send(JSON.stringify({"type": "score"})));
    document.getElementById("answerBad")
        .addEventListener("click", () => this.socket.send(JSON.stringify({"type": "next_question"})));

    [...document.getElementById("selection").querySelectorAll("span")].forEach(
      (e, i) => e.addEventListener("click", () => this.socket.send(JSON.stringify({"type": "select", "index": i})))
    );

    [...document.querySelectorAll("button[data-round]")].forEach(
      (e, i) => e.addEventListener("click", () => this.socket.send(JSON.stringify({"type": "round", "index": i})))
    );
  }

  connect() {
    // Socket location is /game-name/ws, e.g. /ABCD/ws
    const socket_location = new URL("ws", window.location);

    // Socket protocol must match the security of the page
    socket_location.protocol =
        socket_location.protocol === "https:" ? "wss" : "ws";

    this.log("Connecting to server at", socket_location);
    this.socket = new WebSocket(socket_location);
    this.socket.addEventListener("open", (e) => this.open(e), {
      once: true,
      passive: true,
    });
    this.socket.addEventListener("message", (e) => this.message(e), {
      passive: true,
    });
    this.socket.addEventListener("close", (e) => this.close(e), {
      once: true,
      passive: true,
    });
  }

  log(...str) {
    console.log(...str);
    const p = document.createElement("p");
    p.appendChild(document.createTextNode(str.join(" ")));
    this._log.insertBefore(p, this._log.firstChild);
  }

  open() {
    this.log("Connected to socket");
  }

  message(event) {
    /** @type {OverallState} data */
    let data;

    try {
      data = JSON.parse(event.data);
    } catch (e) {
      this.log("Received malformed packet", event.data);
      return;
    }

    if (data.current_question) {
      this.displayQuestion(data);
    } else {
      this.questionSelect(data);
    }
  }

  close() {
    this.log("Disconnect from server");
    this.connect();
  }

  /**
   * @param {!OverallState} data
   */
  questionSelect(data)
  {
    document.getElementById("round-info").textContent = "Round " + (data.current_round + 1);
    document.getElementById("score").textContent = data.scores;
    [...document.getElementById("selection").querySelectorAll("span")].forEach(
        (e, i) => {
          e.classList.toggle("available", data.available_questions[i] || false);
          e.classList.toggle("selected", i === data.selecting);
        }
    );

    document.body.classList.remove("state-question");
    document.body.classList.remove("state-revealed");
    document.body.classList.add("state-selection");
  }

  /**
   * @param {!OverallState} data
   */
  displayQuestion(data)
  {
    const questionBlock = document.getElementById("question");
    const clues = [...questionBlock.querySelectorAll("span")]

    if (questionBlock.getAttribute("data-id") !== data.current_question?.id) {
      clues.forEach((e, i) => {
        e.textContent = data.current_question.clues[i];
        e.setAttribute("data-answer", clues[i].textContent);
      })

      if (data.current_question.is_sequence) {
        clues[clues.length - 1].textContent = "?";
        clues[clues.length - 1].classList.add("revealed");
      }

      document.getElementById("_answer").textContent = data.current_question.connection;
      document.getElementById("credit").textContent = data.current_question.credit;
      questionBlock.querySelector(".connection").textContent = data.current_question.connection;
    }

    clues.forEach((e, i) => {
      e.classList.toggle("active", i === data.revealed_clues);
    })

    if (data.answer_revealed) {
      clues[clues.length - 1].textContent = clues[clues.length - 1].getAttribute("data-answer");
    }

    questionBlock.classList.toggle("answered", data.answer_revealed)
    document.body.classList.toggle("state-revealed", data.answer_revealed);
    document.body.classList.remove("state-selection");
    document.body.classList.add("state-question");
  }
}

new Controller();
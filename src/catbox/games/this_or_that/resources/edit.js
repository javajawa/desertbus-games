// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {elemGenerator} from "/elems.js";

const article = elemGenerator("article");
const input = elemGenerator("input");
const button = elemGenerator("button");
const textarea = elemGenerator("textarea");
const label = elemGenerator("label");
const span = elemGenerator("span");
const fieldset = elemGenerator("fieldset");
const img = elemGenerator("img");

class Controller {
  constructor() {
    this._log = document.getElementById("log") || document.createElement("div");
    this._closed = false;

    this.init_buttons();
    this.connect();
  }

  init_buttons() {
    this._main = document.getElementById("main");
    this._meta = null;
    this._this = input({"id": "this"});
    this._that = input({"id": "that"});

    this._main.appendChild(article(
      button("Add Question", {"click": () => this._new_question(), "class": "button"}),
      button("Submit For Review", {"click": () => this._submit(), "class": "button"}),
    ));

    this._meta = article(
      label("Title: ", input({"id": "title"})),
      label("This Category: ", this._this),
      label("That Category: ", this._that),
      label("Description: ", textarea({"id": "description"})),
      {
        "change": () => this._set_meta(),
        "focusout": () => this._set_meta(),
        "class": "sync saved",
        "focusin": e => this._editing(e),
        "keypress": e => this._editing(e),
        "keyup": e => this._editing(e)
      }
    );
    this._main.appendChild(this._meta);
  }

  connect() {
    // Socket location is /game-name/ws, e.g. /ABCD/ws
    const socket_location = new URL(document.body.getAttribute("socket"));
    this.log("Connecting to server at", socket_location);
    this.socket = new WebSocket(socket_location);
    this.socket.addEventListener("open", (e) => this.open(e), {
      once: true,
      passive: true,
    });
    this.socket.addEventListener("message", (e) => this.message(e), {
      passive: true,
    });
    this.socket.addEventListener("close", (e) => this._close(e), {
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
    this.socket.send(JSON.stringify({"cmd": "get"}));
    document.body.classList.remove("connecting");
  }

  _new_question() {
    this.socket.send(JSON.stringify({"cmd": "new_question"}));
  }

  _submit() {
    this.socket.send(JSON.stringify({"cmd": "submit"}));
  }

  _question_row(uuid) {
    const block = document.getElementById(uuid);

    return block || article(
        {
          "id": uuid,
          "focusin": e => this._editing(e),
          "keypress": e => this._editing(e),
          "keyup": e => this._editing(e),
          "change": () => this._on_question_update(uuid),
          "focusout": () => this._on_question_update(uuid),
          "class": "sync saved"
        },
        span({"class": "button delete", "click": () => this._delete_question(uuid)}, "❌"),
        fieldset(label(
            "Question ",
            input({"type": "file", "class": "question-image", "accept": "image/*", "change": e => this._on_image_change(uuid, e)}),
            span({"class": "remove-media button", "click": e => this._remove_media(uuid, "question", e)}, "❌"),
            img({"class": "preview", "src": ""}),
            textarea({"required": true, "class": "question"})
        )),
        fieldset(
          label(
              span(`Is in '${this._this.value}' category?`, {"class": "this"}),
              input({"type": "checkbox", "class": "this"})
          ),
          label(
              span(`Is in '${this._that.value}' category?`, {"class": "that"}),
              input({"type": "checkbox", "class": "that"})
          ),
        ),
        fieldset(label(
            "Answer Info ",
            input({"type": "file", "class": "answer-image", "accept": "image/*", "change": e => this._on_image_change(uuid, e)}),
            span({"class": "remove-media button", "click": e => this._remove_media(uuid, "answer", e)}, "❌"),
            img({"class": "preview", "src": ""}),
            textarea({"required": true, "class": "answer"}),
        )),
    );
  }

  _editing(e) {
    const list = e.target.closest(".sync").classList;
    list.remove("saved");
    list.remove("saving");
    list.remove("to-upload");
  }

  /**
   *
   * @param {string} uuid
   * @param {Event} event
   * @private
   */
  _on_image_change(uuid, event) {
    event.stopPropagation();

    /** @var {HTMLInputElement} input */
    const input= event.target;
    const preview = input.nextElementSibling;

    if (input.files.length === 0) {
      input.removeAttribute("blob");
      input.removeAttribute("hash");
      preview.removeAttribute("src");
      return;
    }

    const file = input.files[0];
    const hash = cyrb53(file.name + file.lastModified + file.type + file.size);

    if (hash === input.getAttribute("hash")) {
      return;
    }

    input.setAttribute("hash", hash);

    const upload = new Request("/blob", {"method": "POST", body: file});
    this.log("Starting upload");

    fetch(upload).then(async result => {
      if (result.status !== 201) {
        this.log(await result.text());
        return;
      }

      const data = await result.json();
      this.log("Uploaded as blob", data.id);
      input.setAttribute("blob", data.id);
      preview.src = URL.createObjectURL(file);
      this._on_question_update(uuid);
    });
  }

  _remove_media(uuid, type, event) {
    event.preventDefault();
    event.stopPropagation();

    if (type !== "question" && type !== "answer") {
      console.error("Invalid media type", type);
      return
    }

    const row = this._question_row(uuid);

    if (type === "question") {
      row.querySelector(".question-image").removeAttribute("blob");
      row.querySelector(".question-image~.preview").src = "";
    } else {
      row.querySelector(".answer-image").removeAttribute("blob");
      row.querySelector(".answer-image~.preview").src = "";
    }

    this._on_question_update(uuid);
  }

  _on_question_update(uuid) {
    const block = this._question_row(uuid);

    if (block.classList.contains("conflict")) {
      return;
    }
    if (block.classList.contains("to-upload")) {
      return;
    }

    this.log("Adding", uuid, "to upload queue");
    block.classList.add("to-upload");
    window.setTimeout(() => this._upload_question(uuid), 250);
  }

  _delete_question(uuid) {
    if (!confirm("Delete this question?")) {
      return;
    }

    this.log("Deleting question", uuid);
    this.socket.send(JSON.stringify({"cmd": "delete_question", "uuid": uuid}));
  }

  _upload_question(uuid) {
    const block = this._question_row(uuid);

    if (block.classList.contains("conflict")) {
      return;
    }
    if (!block.classList.contains("to-upload")) {
      return;
    }
    this.log("Uploading", uuid);
    block.classList.add("saving");

    this.socket.send(JSON.stringify({
      "cmd": "update",
      "uuid": uuid,
      "question_text": block.querySelector(".question").value,
      "question_media": block.querySelector(".question-image").getAttribute("blob"),
      "answer_text": block.querySelector(".answer").value,
      "answer_media": block.querySelector(".answer-image").getAttribute("blob"),
      "is_this": block.querySelector("input.this").checked,
      "is_that": block.querySelector("input.that").checked,
    }));

    block.classList.remove("to-upload");
  }

  _set_meta() {
    this.socket.send(JSON.stringify({
      "cmd": "set_meta",
      "title": document.getElementById("title").value,
      "description": document.getElementById("description").value,
      "this": this._this.value,
      "that": this._that.value
    }));
    this._meta.classList.add("saved");
  }

  message(event) {
    let data;

    try {
      data = JSON.parse(event.data);
      this[data["cmd"]](data);
    } catch (e) {
      this.log("Received malformed packet", event.data, e);
    }
  }

  update(data) {
    const seen = new Set();

    document.getElementById("title").value = data["title"];
    document.getElementById("description").value = data["description"];
    this._this.value = data["this"];
    this._that.value = data["that"];

    let previous = this._meta;
    for (let question of data["questions"]) {
      seen.add(question["uuid"]);
      const block = this._question_row(question["uuid"]);

      if (!block.classList.contains("saved") && !block.classList.contains("saving")) {
        block.classList.add("conflict");
        continue;
      }

      block.classList.remove("to-upload");
      block.classList.remove("saving");
      block.classList.add("saved");

      block.querySelector(".question").value = question["question_text"];
      this._populateImage(block, ".question-image", question["question_media"]);
      block.querySelector(".answer").value = question["answer_text"];
      this._populateImage(block, ".answer-image", question["answer_media"]);

      block.querySelector("span.this").textContent = `Is in '${data["this"]}' category?`;
      block.querySelector("span.that").textContent = `Is in '${data["that"]}' category?`;
      block.querySelector("input.this").checked = question["is_this"];
      block.querySelector("input.that").checked = question["is_that"];

      if (block.previousElementSibling !== previous) {
        if (block.parentElement) {
          block.parentElement.removeChild(block);
        }
        previous.parentElement.insertBefore(block, previous.nextElementSibling);
      }
      previous = block;
    }

    while (previous.nextElementSibling) {
      previous.parentElement.removeChild(previous.nextElementSibling);
    }
  }

  _populateImage(block, selector, blob) {
    if (blob) {
      block.querySelector(selector).setAttribute("blob", blob.blob_id);
      block.querySelector(selector + "~.preview").src = blob.url;
    } else {
      block.querySelector(selector).removeAttribute("blob");
      block.querySelector(selector + "~.preview").src = "";
    }
  }

  close() {
    document.body.classList.add("closed");
    this._closed = true;
    this.socket.close();
  }

  _close() {
    this.log("Disconnect from server");
    if (this._closed) return;

    document.body.classList.add("connecting");
    this.connect();
  }
}

function cyrb53(str)
{
    let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
    for (let i = 0, ch; i < str.length; i++) {
        ch = str.charCodeAt(i);
        h1 = Math.imul(h1 ^ ch, 2654435761);
        h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1  = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
    h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2  = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
    h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);

    return 4294967296 * (2097151 & h2) + (h1 >>> 0);
}

new Controller();
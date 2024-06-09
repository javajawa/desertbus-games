// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

const _log = document.getElementById("log") || document.createElement("div");


function log(...str) {
  console.log(...str);
  const p = document.createElement("p");
  p.appendChild(document.createTextNode(str.join(" ")));
  _log.insertBefore(p, _log.firstChild);
}


class SocketControllerSingleton {
  _socket;
  _opened;
  _closed;

  constructor() {
    this._socket = null;
    this._closed = false;
    this._opened = false;
  }

  connect(controller) {
    if (this._closed) {
      log("Connect called when socket already closed");
      return;
    }

    if (this._opened) {
      log("Connect called on open socket, returning instantly")
      this._socket.addEventListener("message", e => controller._on_ws_event(e), {passive: true});
      controller._on_ws_open();
      return;
    }

    if (!this._socket) {
      // Socket location is /game-name/ws, e.g. /ABCD/ws
      const socket_location = new URL(document.body.getAttribute("socket"));
      log("Connecting to server at", socket_location);
      this._socket = new WebSocket(socket_location);

      this._socket.addEventListener("open", () => this._on_ws_open(), {once: true, passive: true});
      this._socket.addEventListener("error", e => log(e), {passive: true});
      this._socket.addEventListener("close", e => this._on_ws_close(e), {once: true, passive: true});
    }

    this._socket.addEventListener("open", () => controller._on_ws_open(), {once: true, passive: true});
    this._socket.addEventListener("message", e => controller._on_ws_event(e), {passive: true});
  }

  _on_ws_open() {
    log("Connected to socket");
    this._opened = true;
    document.body.classList.remove("connecting");
  }

  _on_ws_close() {
    this._opened = false;
    this._socket = null;
    log("Disconnect from server");
    if (this._closed) {
      document.body.classList.add("closed");
      return;
    }

    document.body.classList.add("connecting");
    this.connect();
  }
}

const socket = new SocketControllerSingleton();


export class SocketController {

  constructor() {
    socket.connect(this);
  }

  _log(...str) {
    log(...str);
  }

  error(data) {
    log(data);
    return false;
  }

  _on_ws_open() {}

  _on_ws_event(event) {
    let data;

    try {
      data = JSON.parse(event.data);
      if (data["cmd"] === "close") {
        socket._closed = true;
      }
      if (typeof this[data["cmd"]] !== "function") {
        return;
      }
      this[data["cmd"]](data);
    } catch (e) {
      this._log("Received malformed packet", event.data, e);
    }
  }

  _send(data) {
    if (!socket._socket) {
      this._log("Can't send (not connected)", data);
      return;
    }

    this._log("Sending", data);
    socket._socket.send(JSON.stringify(data));
  }
}

export function cyrb53(str)
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

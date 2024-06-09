// SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import {SocketController} from "/socket.js";
import {elemGenerator} from "/elems.js";

const a = elemGenerator("a");
const dl = elemGenerator("dl");
const dt = elemGenerator("dt");
const dd = elemGenerator("dd");
const span = elemGenerator("span");

class GMController extends SocketController {
    _on_ws_open() {
        this._send({"cmd": "endpoints"});
    }

    endpoints(data) {
        const zone = document.getElementById("endpoints");
        if (!zone) return;

        this._log("Updating the endpoint list");
        const buttons = dl(data["endpoints"].map(endpoint =>
            dd(
                dt({"class": "roomcode"}, a({"href": "/room/" + endpoint["room"], "target": "_blank"}, endpoint["room"])),
                " ",
                endpoint["name"]
            )
        ));

        while (zone.lastChild) {
            zone.removeChild(zone.lastChild);
        }
        zone.appendChild(buttons);
        zone.appendChild(span({"class": "button", "click": e => confirm("Close the room and disconnect everyone?") && this._send({"cmd": "close"})}, "Close/Shutdown Room"));
        this._log("Endpoints updated.");
    }
}

new GMController();
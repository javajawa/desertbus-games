<!--
SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>

SPDX-License-Identifier: CC0-1.0
-->

- Refactor the editor to work on the new socket class.
- Question you are editing sometimes disappears in the editor
- Pretty error pages
- Better navigation (ability to go home)
- Room code on home page should make an API to get the room name
- Login button should be replaced with user name
- in game view, when only one line of text, make it centered
- player control buttons don't highlight after disconnect
- Skip to end button (and show the current question number and total on GM screen)

Ideas?
- confirmation / lock-in of the controls
- chat should never win (?)

- Add Only Connect
- Add Jeopardy

Fix proposed
 - s/master/manager/

Fixed
 - the answers are backwards
 - some images are being scaled too large. fixed on refresh. (offsetHeight > maxHeight)
 - audit content button link on game index is wrong
 - audience fill goes the wrong way
 - chat final score is shown to too many places
 - add a non-colour marker for selected options
- player controls -- have some feedback when not in question state (e.g. show what the answer was)

<!--
SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>

SPDX-License-Identifier: CC0-1.0
-->

- Refactor the editor to work on the new socket class.
- Question you are editing sometimes disappears in the editor
- Pretty error pages
- Better navigation (ability to go home)
- Room code box on home page should make an API to get the room name
- Login button should be replaced with user name
- in game view, when only one line of text, make it centered
- player control buttons don't highlight after disconnect
- Skip to end button (and show the current question number and total on GM screen)
- Make branded error pages for all known error states.
- Should warn when attempting to create a non-moderated table
  - include a link to the audit page
  - let the user know if a previous version was approved, and offer a link

General
-------

- [x] Loggers for rooms are not unique and are polluting each others log files


Only Connect
------------

- [ ] End of round screen needs a design pass
- [ ] The sequences pre-round info is missing
- [ ] The connecting wall pre-round info is missing
- [x] When connecting wall is resolved by give up / strike out, cells go green before they go orange
- [ ] Need to show whose wall it is on the wall view
- [x] Buttons on the connecting wall -- "Lock in" should be labelled differently, and "steal" action button shuold be clearer
- [ ] Add 2 bonus points for fully completing and guessing the wall
- [ ] Space key should take sensible default action
- [ ] The connecting wall doesn't lock correctly after three strikes


Ideas?
- confirmation / lock-in of the controls
- chat should never win (?)

- Add Jeopardy

Fixed
 - s/master/manager/
 - the answers are backwards
 - some images are being scaled too large. fixed on refresh. (offsetHeight > maxHeight)
 - audit content button link on game index is wrong
 - audience fill goes the wrong way
 - chat final score is shown to too many places
 - add a non-colour marker for selected options
 - player controls -- have some feedback when not in question state (e.g. show what the answer was)

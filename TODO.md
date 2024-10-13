<!--
SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>

SPDX-License-Identifier: CC0-1.0
-->


# General

- [ ] In /play, there should be a warning when attempting to create a non-moderated table
  - include a link to the audit content page
  - let the user know if a previous version was approved, and offer a link
- [ ] Make branded error pages for all known error states.
- [ ] Room code box on home page should make an API to get the room name
- [ ] Login button should be replaced with username

## Moderation

- [ ] Add a notifications table and code
- [ ] When rejecting during moderation, require a comment. Put this in the notification
- [ ] When approving during moderation, send a notification saying it was approved
- [ ] Add a bug report system that adds notifications to a dedicated bug account

## Infrastructure

- [ ] Set up a VM in the Pacific region
- [ ] Add basic metrics and tracing support

# This or That

## Editor

- [ ] Refactor the editor to work on the new socket class.
- [ ] Question you are editing sometimes disappears in the editor

## Playing

- [ ] GM games action panel needs a design overhaul
- [ ] Confirmation / lock-in on the controls
- [ ] Player control buttons don't highlight after disconnect
- [ ] When only one line of text, make it big and centered

# Only Connect

## Editor

- [ ] Ensure that media questions have 4 media clues (and vice versa)

## Playing - Logic

- [ ] State machine needs actual documentation
- [ ] Add 2 bonus points for fully completing and guessing the wall
- [ ] Space key should take sensible default action

## Playing - Graphical

- [ ] End of round screen needs a design pass
- [ ] Connecting wall is poorly layed out on the overlay

# Other Games

- [ ] Add Jeopardy

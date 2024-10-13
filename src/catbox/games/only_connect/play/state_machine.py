# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Literal

import abc
import enum
import random

from catbox.games.only_connect.episode import SLOTS_PER_CONNECTION

if TYPE_CHECKING:
    from catbox.engine import JSONDict
    from catbox.games.only_connect.episode import (
        ConnectingWall,
        MissingVowelsGroup,
        OnlyConnectQuestion,
        OnlyConnectTextQuestion,
        SixQuestions,
    )

    from . import OnlyConnectRoom


class RoundTracker(enum.StrEnum):
    PRE_GAME = "pre-game"
    CONNECTIONS = "connections"
    COMPLETIONS = "completions"
    CONNECTING_WALLS = "connecting_walls"
    MISSING_VOWELS = "missing_vowels"
    POST_GAME = "post-game"

    def next(self) -> RoundTracker:
        if self == RoundTracker.POST_GAME:
            return RoundTracker.POST_GAME

        members = list(RoundTracker)
        loc = members.index(self)
        return members[loc + 1]  # type: ignore[return-value]


class InRoundState(enum.StrEnum):
    PRE_ROUND = "pre-round"
    QUESTION_SELECTION = "select"
    QUESTION_ACTIVE = "question"
    LOCKED_IN = "locked-in"
    STEALING = "stealing"
    ANSWER_REVEALED = "answer"
    POST_ROUND = "post-round"


class PossibleActions(enum.StrEnum):
    NEXT_QUESTION = "NEXT_QUESTION"
    SELECT_TWO_REEDS = "SELECT_TWO_REEDS"
    SELECT_LION = "SELECT_LION"
    SELECT_TWISTED_FLAX = "SELECT_TWISTED_FLAX"
    SELECT_HORNED_VIPER = "SELECT_HORNED_VIPER"
    SELECT_WATER = "SELECT_WATER"
    SELECT_EYE_OF_HORUS = "SELECT_EYE_OF_HORUS"

    NEXT_CLUE = "NEXT_CLUE"
    LOCK_IN = "LOCK_IN"
    REVEAL_FOR_STEAL = "REVEAL_FOR_STEAL"

    SCORE_TEAM1 = "SCORE_TEAM1"
    SCORE_TEAM2 = "SCORE_TEAM2"
    SCORE_STEAL = "SCORE_STEAL"
    SCORE_INCORRECT = "SCORE_INCORRECT"

    START_NEXT_ROUND = "START_NEXT_ROUND"


class RoundHandler(abc.ABC):
    room: OnlyConnectRoom

    def __init__(self, room: OnlyConnectRoom) -> None:
        self.room = room

    @abc.abstractmethod
    def public_state(self) -> JSONDict | None:
        pass

    def admin_state(self) -> JSONDict | None:
        return self.public_state()

    @abc.abstractmethod
    def possible_actions(self) -> set[PossibleActions]:
        pass

    def next_question(self) -> bool:
        return False

    def select_two_reeds(self) -> bool:
        return False

    def select_lion(self) -> bool:
        return False

    def select_twisted_flax(self) -> bool:
        return False

    def select_horned_viper(self) -> bool:
        return False

    def select_water(self) -> bool:
        return False

    def select_eye_of_horus(self) -> bool:
        return False

    def next_clue(self) -> bool:
        return False

    def lock_in(self) -> bool:
        return False

    def reveal_for_steal(self) -> bool:
        return False

    def score_team1(self) -> bool:
        return False

    def score_team2(self) -> bool:
        return False

    def score_steal(self) -> bool:
        return False

    def score_incorrect(self) -> bool:
        return False

    def do(self, choice: PossibleActions) -> bool:
        actions = {
            PossibleActions.NEXT_QUESTION: self.next_question,
            PossibleActions.SELECT_TWO_REEDS: self.select_two_reeds,
            PossibleActions.SELECT_LION: self.select_lion,
            PossibleActions.SELECT_TWISTED_FLAX: self.select_twisted_flax,
            PossibleActions.SELECT_HORNED_VIPER: self.select_horned_viper,
            PossibleActions.SELECT_WATER: self.select_water,
            PossibleActions.SELECT_EYE_OF_HORUS: self.select_eye_of_horus,
            PossibleActions.NEXT_CLUE: self.next_clue,
            PossibleActions.LOCK_IN: self.lock_in,
            PossibleActions.REVEAL_FOR_STEAL: self.reveal_for_steal,
            PossibleActions.SCORE_TEAM1: self.score_team1,
            PossibleActions.SCORE_TEAM2: self.score_team2,
            PossibleActions.SCORE_STEAL: self.score_steal,
            PossibleActions.SCORE_INCORRECT: self.score_incorrect,
        }

        call = actions.get(choice)

        return call() if call else False


class StandardRoundState(RoundHandler):
    state: InRoundState
    active_team: Literal[0, 1]
    data: SixQuestions
    available: list[PossibleActions | None]
    current_question: OnlyConnectQuestion

    revealed_clues: int
    max_revealed: int

    def __init__(self, room: OnlyConnectRoom, data: SixQuestions) -> None:
        super().__init__(room)

        self.state = InRoundState.PRE_ROUND
        self.data = data
        self.available = [
            PossibleActions.SELECT_TWO_REEDS,
            PossibleActions.SELECT_LION,
            PossibleActions.SELECT_TWISTED_FLAX,
            PossibleActions.SELECT_HORNED_VIPER,
            PossibleActions.SELECT_WATER,
            PossibleActions.SELECT_EYE_OF_HORUS,
        ]
        self.active_team = 0 if len(room.teams) == 1 else 1
        self.current_question = data[0]

        self.revealed_clues = 0
        self.max_revealed = SLOTS_PER_CONNECTION
        if room.current_round == RoundTracker.COMPLETIONS:
            self.max_revealed = SLOTS_PER_CONNECTION - 1
            self.active_team = 0

    def public_state(self) -> JSONDict:
        state: JSONDict = {
            "state": self.state,
            "active_team": self.room.teams[self.active_team].json(),  # type: ignore[misc]
        }

        if self.state in [InRoundState.PRE_ROUND, InRoundState.POST_ROUND]:
            return state

        if self.state == InRoundState.QUESTION_SELECTION:
            state["available"] = list(self.available)  # type: ignore[assignment]
            return state

        if self.state == InRoundState.ANSWER_REVEALED:
            state["current"] = self.current_question.json()
            return state

        if self.state == InRoundState.STEALING and self.max_revealed < len(
            self.current_question.elements,
        ):
            state["current"] = {
                "question_type": self.current_question.question_type,
                "revealed": len(self.current_question.elements),
                "elements": [*self.current_question.elements[0 : self.revealed_clues], "?"],  # type: ignore[dict-item]
            }
        else:
            state["current"] = {
                "question_type": self.current_question.question_type,
                "revealed": self.revealed_clues,
                "elements": self.current_question.elements[0 : self.revealed_clues],  # type: ignore[dict-item]
            }

        return state

    def admin_state(self) -> JSONDict:
        state = self.public_state()

        if isinstance(current := state.get("current"), dict):
            current["connection"] = self.current_question.connection
            current["details"] = self.current_question.details
            if self.max_revealed < SLOTS_PER_CONNECTION:
                current["elements"].extend([""] * (SLOTS_PER_CONNECTION - len(current["elements"])))
                current["elements"][self.max_revealed] = self.current_question.elements[
                    self.max_revealed
                ]

        return state

    def possible_actions(self) -> set[PossibleActions]:  # -- lots of returns...
        mapping: dict[InRoundState, set[PossibleActions]] = {
            InRoundState.PRE_ROUND: {PossibleActions.NEXT_QUESTION},
            InRoundState.QUESTION_SELECTION: set(),
            InRoundState.QUESTION_ACTIVE: {PossibleActions.LOCK_IN, PossibleActions.NEXT_CLUE},
            InRoundState.STEALING: {PossibleActions.SCORE_STEAL, PossibleActions.SCORE_INCORRECT},
            InRoundState.ANSWER_REVEALED: {PossibleActions.NEXT_QUESTION},
            InRoundState.POST_ROUND: {PossibleActions.START_NEXT_ROUND},
        }

        if self.state in mapping:
            return mapping[self.state]

        # LOCKED_IN
        if len(self.room.teams) == 1:
            return {PossibleActions.SCORE_TEAM1, PossibleActions.SCORE_INCORRECT}

        return {
            (PossibleActions.SCORE_TEAM1 if self.active_team == 0 else PossibleActions.SCORE_TEAM2),
            PossibleActions.REVEAL_FOR_STEAL,
        }

    def next_question(self) -> bool:
        if self.state not in [InRoundState.PRE_ROUND, InRoundState.ANSWER_REVEALED]:
            return False

        if not any(self.available):
            self.state = InRoundState.POST_ROUND
            return True

        if len(self.room.teams) != 1:
            self.active_team = 1 if self.active_team == 0 else 0

        self.state = InRoundState.QUESTION_SELECTION
        return True

    def select(self, question: PossibleActions) -> bool:
        if self.state != InRoundState.QUESTION_SELECTION:
            return False
        if question not in self.available:
            return False

        index = self.available.index(question)
        self.state = InRoundState.QUESTION_ACTIVE
        self.current_question = self.data[index]
        self.revealed_clues = 1
        self.available[index] = None

        return True

    def select_two_reeds(self) -> bool:
        return self.select(PossibleActions.SELECT_TWO_REEDS)

    def select_lion(self) -> bool:
        return self.select(PossibleActions.SELECT_LION)

    def select_twisted_flax(self) -> bool:
        return self.select(PossibleActions.SELECT_TWISTED_FLAX)

    def select_horned_viper(self) -> bool:
        return self.select(PossibleActions.SELECT_HORNED_VIPER)

    def select_water(self) -> bool:
        return self.select(PossibleActions.SELECT_WATER)

    def select_eye_of_horus(self) -> bool:
        return self.select(PossibleActions.SELECT_EYE_OF_HORUS)

    def next_clue(self) -> bool:
        if self.state != InRoundState.QUESTION_ACTIVE:
            return False

        if self.revealed_clues >= self.max_revealed:
            return False

        self.revealed_clues += 1

        if self.revealed_clues == self.max_revealed:
            self.state = InRoundState.LOCKED_IN

        return True

    def lock_in(self) -> bool:
        if self.state != InRoundState.QUESTION_ACTIVE:
            return False

        self.state = InRoundState.LOCKED_IN
        return True

    def score_team1(self) -> bool:
        return self.score(0)

    def score_team2(self) -> bool:
        return self.score(1)

    def score(self, team: Literal[0, 1]) -> bool:
        if self.state != InRoundState.LOCKED_IN:
            return False

        self.room.teams[team].score += [0, 5, 3, 2, 1][self.revealed_clues]  # type: ignore[misc]

        self.state = InRoundState.ANSWER_REVEALED
        self.revealed_clues = SLOTS_PER_CONNECTION
        return True

    def score_steal(self) -> bool:
        if self.state != InRoundState.STEALING:
            return False

        self.room.teams[1 - self.active_team].score += 1
        self.state = InRoundState.ANSWER_REVEALED
        self.revealed_clues = SLOTS_PER_CONNECTION
        return True

    def score_incorrect(self) -> bool:
        if self.state not in {InRoundState.LOCKED_IN, InRoundState.STEALING}:
            return False

        self.state = InRoundState.ANSWER_REVEALED
        self.revealed_clues = SLOTS_PER_CONNECTION
        return True

    def reveal_for_steal(self) -> bool:

        self.revealed_clues = self.max_revealed
        self.state = InRoundState.STEALING
        return True


class MissingVowelsState(RoundHandler):
    state: InRoundState

    questions: list[MissingVowelsGroup]
    current_group: list[tuple[str, str]]

    group_index: int = -1
    question_index: int = -1

    def __init__(self, room: OnlyConnectRoom, questions: list[MissingVowelsGroup]) -> None:
        super().__init__(room)

        self.state = InRoundState.PRE_ROUND
        self.questions = [group for group in questions if group.valid_pairs]
        self.current_group = []

    def public_state(self) -> JSONDict:
        return {
            "round": RoundTracker.MISSING_VOWELS,
            "state": self.state,
            "question": self.active_question(),
        }

    def admin_state(self) -> JSONDict | None:
        state = self.public_state()

        if state["question"]:
            state["question"] = {
                "connection": self.questions[self.group_index].connection,
                "text": self.current_group[self.question_index][1],
                "answer": self.current_group[self.question_index][0],
            }

        return state

    def possible_actions(self) -> set[PossibleActions]:
        if self.state == InRoundState.QUESTION_ACTIVE:
            return {
                PossibleActions.SCORE_TEAM1,
                PossibleActions.SCORE_TEAM2,
                PossibleActions.SCORE_INCORRECT,
            }

        if self.state == InRoundState.POST_ROUND:
            return {PossibleActions.START_NEXT_ROUND}

        return {PossibleActions.NEXT_QUESTION}

    def active_question(self) -> JSONDict | None:
        if self.state == InRoundState.QUESTION_ACTIVE:
            return {
                "connection": self.questions[self.group_index].connection,
                "text": self.current_group[self.question_index][1],
            }

        if self.state == InRoundState.ANSWER_REVEALED:
            return {
                "connection": self.questions[self.group_index].connection,
                "text": self.current_group[self.question_index][0],
            }

        return None

    def next_group(self) -> None:
        self.group_index += 1

        if self.group_index >= len(self.questions):
            self.state = InRoundState.POST_ROUND
            return

        self.current_group = list(self.questions[self.group_index].valid_pairs)

        if not self.current_group:
            self.next_group()

        self.question_index = 0
        self.state = InRoundState.QUESTION_ACTIVE

    def next_question(self) -> bool:
        if self.state == InRoundState.PRE_ROUND:
            self.next_group()
            return True

        if self.state != InRoundState.ANSWER_REVEALED:
            return False

        self.question_index += 1
        self.state = InRoundState.QUESTION_ACTIVE
        if self.question_index >= len(self.current_group):
            self.next_group()

        return True

    def score_team1(self) -> bool:
        if self.state != InRoundState.QUESTION_ACTIVE:
            return False

        self.room.teams[0].score += 1
        self.state = InRoundState.ANSWER_REVEALED
        return True

    def score_team2(self) -> bool:
        if self.state != InRoundState.QUESTION_ACTIVE:
            return False

        self.room.teams[1].score += 1  # type: ignore[misc]
        self.state = InRoundState.ANSWER_REVEALED
        return True

    def score_incorrect(self) -> bool:
        if self.state != InRoundState.QUESTION_ACTIVE:
            return False

        self.state = InRoundState.ANSWER_REVEALED
        return True


class ActiveWall:
    wall: ConnectingWall
    grouped: list[str]
    ungrouped: list[str]
    not_found: list[str]
    selected: list[int]
    strikes: int | None
    groups: list[OnlyConnectTextQuestion]
    confirming_group: int | None
    is_group_revealed: bool

    def __init__(self, wall: ConnectingWall) -> None:
        self.wall = wall

        words = list(wall.clues)
        random.shuffle(words)

        self.ungrouped = words
        self.grouped = []
        self.not_found = []
        self.selected = []
        self.strikes = None
        self.groups = []
        self.confirming_group = None
        self.is_group_revealed = True

    def toggle(self, word: str) -> Iterator[None]:
        try:
            index = self.ungrouped.index(word)
        except ValueError:
            return

        if index in self.selected:
            self.selected.remove(index)
            yield None
            return

        self.selected.append(index)
        # Update now to show something became selected
        yield None

        if len(self.selected) != SLOTS_PER_CONNECTION:
            return

        selected_words = [self.ungrouped[index] for index in self.selected]
        self._check_match_group(selected_words)

        self.selected = []
        yield None

    def _check_match_group(self, words: list[str]) -> None:
        for group in self.wall:
            if all(word in group.elements for word in words):
                # Move the selected entries from 'ungrouped' to 'grouped'
                for index in sorted(self.selected, reverse=True):
                    self.ungrouped.pop(index)
                self.grouped.extend(group.elements)
                self.groups.append(group)

                # Start the 3 strikes counter when there are two groups left
                if len(self.ungrouped) == 2 * SLOTS_PER_CONNECTION:
                    self.strikes = 3

                # Stop accepting input if the board is solved
                if len(self.ungrouped) == 0:
                    raise OverflowError

                # Indicate that a group was matched
                break

        else:  # If no group was matched
            # Remove a strike (if they are being counted)
            if self.strikes is not None:
                self.strikes -= 1
                # Stop accepting input if the team is out of strikes
                if self.strikes <= 0:
                    raise OverflowError

    def json(self, *, admin: bool = False) -> JSONDict:
        confirming: JSONDict | None = None
        if self.confirming_group is not None:
            group = self.groups[self.confirming_group]
            confirming = {
                "group_id": self.confirming_group,
                "clues": group.elements,
                "connection": group.connection if admin or self.is_group_revealed else None,
                "details": group.details if admin else None,
            }

        return {
            "grouped": self.grouped,
            "ungrouped": self.ungrouped,
            "not_found": self.not_found,
            "selected": self.selected,  # type: ignore[dict-item]
            "strikes": self.strikes,
            "confirming": confirming,
        }

    def reveal_wall(self) -> None:
        self.strikes = None

        # Unscramble all remaining clues
        while self.ungrouped:
            group_on = self.ungrouped[0]
            for group in self.wall:
                if group_on not in group.elements:
                    continue

                self.not_found.extend(group.elements)
                self.groups.append(group)

                for element in group.elements:
                    self.ungrouped.remove(element)

    def start_confirm_next_group(self) -> None:
        if self.confirming_group is None:
            self.confirming_group = -1

        self.confirming_group += 1
        self.is_group_revealed = False


class ConnectingWallState(RoundHandler):
    state: InRoundState

    available_walls: tuple[ConnectingWall | None, ConnectingWall | None]
    active_team: Literal[0, 1]
    active_wall: ActiveWall | None

    def __init__(self, room: OnlyConnectRoom, walls: tuple[ConnectingWall, ConnectingWall]) -> None:
        super().__init__(room)

        self.state = InRoundState.PRE_ROUND
        self.available_walls = walls
        self.active_wall = None
        self.active_team = 0

        if len(self.room.teams) > 1 and self.room.teams[1].score > self.room.teams[0].score:
            self.active_team = 1

    def public_state(self) -> JSONDict:
        return {
            "round": RoundTracker.CONNECTING_WALLS,
            "state": self.state,
            "active_team": self.room.teams[self.active_team].json(),  # type: ignore[misc]
            "available": [bool(wall) for wall in self.available_walls],  # type: ignore[dict-item]
            "current": self.active_wall.json() if self.active_wall else None,
        }

    def admin_state(self) -> JSONDict:
        return {
            "round": RoundTracker.CONNECTING_WALLS,
            "state": self.state,
            "active_team": self.room.teams[self.active_team].json(),  # type: ignore[misc]
            "available": [bool(wall) for wall in self.available_walls],  # type: ignore[dict-item]
            "current": self.active_wall.json(admin=True) if self.active_wall else None,
        }

    def possible_actions(self) -> set[PossibleActions]:  # -- lots of returns...
        mapping: dict[InRoundState, set[PossibleActions]] = {
            InRoundState.PRE_ROUND: {PossibleActions.NEXT_QUESTION},
            InRoundState.QUESTION_SELECTION: set(),
            InRoundState.POST_ROUND: {PossibleActions.START_NEXT_ROUND},
        }

        if self.state in mapping:
            return mapping[self.state]

        # The players playing a wall can give up at any time.
        if self.state != InRoundState.LOCKED_IN and self.active_wall:
            return {PossibleActions.LOCK_IN}

        # If we have confirmed all groups, move on to the next wall/round
        if (
            self.active_wall
            and self.active_wall.confirming_group == SLOTS_PER_CONNECTION - 1
            and self.active_wall.is_group_revealed
        ):
            return {PossibleActions.NEXT_QUESTION}

        if self.active_wall and self.active_wall.is_group_revealed:
            return {PossibleActions.REVEAL_FOR_STEAL}

        return {
            PossibleActions.SCORE_TEAM1 if self.active_team == 0 else PossibleActions.SCORE_TEAM2,
            PossibleActions.SCORE_INCORRECT,
        }

    def select_lion(self) -> bool:
        if self.state != InRoundState.QUESTION_SELECTION:
            return False

        if not self.available_walls[0]:
            return False

        self.active_wall = ActiveWall(self.available_walls[0])
        self.available_walls = None, self.available_walls[1]
        self.state = InRoundState.QUESTION_ACTIVE
        return True

    def select_water(self) -> bool:
        if self.state != InRoundState.QUESTION_SELECTION:
            return False

        if not self.available_walls[1]:
            return False

        self.active_wall = ActiveWall(self.available_walls[1])
        self.available_walls = self.available_walls[0], None
        self.state = InRoundState.QUESTION_ACTIVE
        return True

    def next_question(self) -> bool:
        if self.state == InRoundState.PRE_ROUND:
            self.state = InRoundState.QUESTION_SELECTION
            return True

        if (
            self.state != InRoundState.LOCKED_IN
            or self.active_wall.confirming_group < SLOTS_PER_CONNECTION - 1  # type: ignore[operator,union-attr]
        ):
            return False

        if len(self.room.teams) == 1 or not any(self.available_walls):
            self.state = InRoundState.POST_ROUND
            return True

        self.state = InRoundState.QUESTION_SELECTION
        self.active_team = 0 if self.active_team else 1
        return True

    def lock_in(self) -> bool:
        if self.state != InRoundState.QUESTION_ACTIVE:
            return False
        if not self.active_wall:
            return False

        score = int(len(self.active_wall.grouped) / 4)
        self.room.teams[self.active_team].score += score  # type: ignore[misc]
        self.active_wall.reveal_wall()
        self.state = InRoundState.LOCKED_IN
        return True

    def toggle(self, word: str) -> Iterator[None]:
        if not self.active_wall:
            return

        try:
            yield from self.active_wall.toggle(word)
        except OverflowError:
            yield None
            self.lock_in()
            yield None

    def reveal_for_steal(self) -> bool:
        if self.state != InRoundState.LOCKED_IN or not self.active_wall:
            return False

        self.active_wall.start_confirm_next_group()
        return True

    def score_team1(self) -> bool:
        if (
            self.state != InRoundState.LOCKED_IN
            or not self.active_wall
            or self.active_wall.confirming_group is None
            or self.active_wall.is_group_revealed
        ):
            return False

        self.room.teams[0].score += 1
        self.active_wall.is_group_revealed = True
        return True

    def score_team2(self) -> bool:
        if (
            self.state != InRoundState.LOCKED_IN
            or not self.active_wall
            or self.active_wall.confirming_group is None
            or self.active_wall.is_group_revealed
        ):
            return False

        self.room.teams[1].score += 1  # type: ignore[misc]
        self.active_wall.is_group_revealed = True
        return True

    def score_incorrect(self) -> bool:
        if (
            self.state != InRoundState.LOCKED_IN
            or not self.active_wall
            or self.active_wall.confirming_group is None
            or self.active_wall.is_group_revealed
        ):
            return False

        self.active_wall.is_group_revealed = True
        return True

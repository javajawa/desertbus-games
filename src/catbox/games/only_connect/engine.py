# SPDX-FileCopyrightText: 2024 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

import json
import pathlib

from catbox.engine import GameEngine, OptionSupport
from catbox.room import Room, RoomOptions

from .cms import OnlyConnectEditRoom, OnlyConnectViewRoom
from .episode import (
    MAX_TEAMS,
    QUESTIONS_PER_ROUND,
    ConnectingWall,
    MissingVowelsGroup,
    OnlyConnectEpisode,
    OnlyConnectQuestion,
    OnlyConnectTextQuestion,
    SixQuestions,
)
from .play import OnlyConnectRoom


class OnlyConnectEngine(GameEngine[OnlyConnectEpisode]):
    @classmethod
    def resources(cls) -> pathlib.Path:
        return (pathlib.Path(__file__).parent / "resources").resolve()

    @property
    def _episode(self) -> type[OnlyConnectEpisode]:
        return OnlyConnectEpisode

    @property
    def name(self) -> str:
        return "Only Connect"

    @property
    def description(self) -> str:
        return """
        The British game show Only Connect.
        Games can include any or all of the four rounds from the show: finding connections,
        completing a sequence, solving the connecting wall (as seen in the NYT Connections game),
        or filling in the missing vowels.
        """

    @property
    def cms_enabled(self) -> bool:
        return True

    def _load_data(self, episode: OnlyConnectEpisode, data: str) -> None:
        try:
            contents = json.loads(data)
        except json.JSONDecodeError:
            contents = {}

        connections = contents.get("connections")
        if isinstance(connections, list):
            connections.extend(
                [OnlyConnectQuestion.default()] * (QUESTIONS_PER_ROUND - len(connections)),
            )
            episode.connections_round = SixQuestions(
                OnlyConnectQuestion(**question) for question in connections
            )

        completions = contents.get("completions")
        if isinstance(completions, list):
            completions.extend(
                [OnlyConnectQuestion.default()] * (QUESTIONS_PER_ROUND - len(completions)),
            )
            episode.completions_round = SixQuestions(
                OnlyConnectQuestion(**question) for question in completions
            )

        walls = contents.get("connecting_walls")
        if isinstance(walls, list):
            episode.connecting_walls = (
                ConnectingWall(OnlyConnectTextQuestion(**question) for question in walls[0]),
                ConnectingWall(OnlyConnectTextQuestion(**question) for question in walls[1]),
            )

        missing_vowels = contents.get("missing_vowels")
        if isinstance(missing_vowels, list):
            episode.missing_vowels = [
                MissingVowelsGroup(**group)
                for group in missing_vowels
                if group is not None and group.get("words")
            ]

    @property
    def scoring_mode(self) -> OptionSupport:
        return OptionSupport.REQUIRED

    @property
    def max_teams(self) -> int:
        return MAX_TEAMS

    @property
    def supports_audience(self) -> OptionSupport:
        return OptionSupport.NOT_SUPPORTED

    def play_episode(self, episode: OnlyConnectEpisode, options: RoomOptions) -> Room:
        return OnlyConnectRoom(self._logger, episode, options)

    def edit_episode(self, episode: OnlyConnectEpisode) -> Room:
        return OnlyConnectEditRoom(self._logger, self, episode)

    def view_episode(self, episode: OnlyConnectEpisode) -> Room:
        return OnlyConnectViewRoom(self._logger, episode)

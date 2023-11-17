from collections.abc import AsyncIterator

import asyncio
import dataclasses
import random
import string
from abc import ABC, abstractmethod
from pathlib import Path

from aiohttp import web

from db_games.abc import Game


@dataclasses.dataclass
class Question:
    # Whether this is a connections round (false), or a complete the sequence round (true)
    is_sequence: bool

    # What the connection between the clues is
    connection: str
    # What the four clues are
    clues: tuple[str, ...]
    credit: str

    id: str

    def __init__(
        self, is_sequence: bool, connection: str, clues: tuple[str, ...], credit: str
    ) -> None:
        self.id = str(id(self))
        self.is_sequence = is_sequence
        self.connection = connection
        self.clues = clues
        self.credit = credit

    @property
    def max_clues(self) -> int:
        return len(self.clues) - 1 - int(self.is_sequence)


@dataclasses.dataclass
class OverallState:
    # Whether the game is running with a single team (false) or two competing teams (true)
    total_teams: int

    # Who is up next, and the current scores
    scores: list[int]

    # Which questions are available for the team(s) to select
    available_questions: list[bool]

    current_team: int = 0
    current_round: int = 0
    current_question: Question | None = None
    selecting: int | None = None

    # How many clues the team has revealed
    revealed_clues: int = 0
    answer_revealed: bool = False

    def __init__(self, total_teams: int) -> None:
        self.total_teams = total_teams
        self.scores = [0] * total_teams
        self.available_questions = []


class OnlyConnectGame(Game, ABC):
    state: OverallState
    rounds: list[tuple[Question, ...]]

    @classmethod
    @abstractmethod
    def possible(cls) -> list[Question]:
        pass

    @classmethod
    async def audit(cls) -> web.Response:
        question_text = [
            (
                f"<tr><td>{question.credit}</td>"
                f"<td>{'sequence' if question.is_sequence else 'connections'}</td>"
                f"<td>{question.connection}</td><td>"
                f"<ul>"
                + "".join([f"<li>{clue}</li>" for clue in question.clues])
                + "</ul></td>"
                "</tr>"
            )
            for question in cls.possible()
        ]

        return web.Response(
            content_type="text/html",
            body=(
                "<!DOCTYPE html><html><head>"
                '<meta charset="utf-8">'
                '<link rel="stylesheet" href="style.css">'
                "</head><body>"
                "<h1>Only Connect</h1>"
                "<p>6 connections and 6 sequences questions will be random selected from:</p>"
                f'<table>{"".join(question_text)}</table>'
                "</body></html>"
            ),
        )

    def __init__(self, total_teams: int) -> None:
        super().__init__()

        self.state = OverallState(total_teams)
        possible = self.possible()

        possible_connections = [x for x in possible if not x.is_sequence]
        possible_sequences = [x for x in possible if x.is_sequence]

        random.shuffle(possible_connections)
        random.shuffle(possible_sequences)

        if len(possible_connections) > 6:
            possible_connections = possible_connections[0:6]
        if len(possible_sequences) > 6:
            possible_sequences = possible_sequences[0:6]

        self.rounds = [tuple(possible_connections), tuple(possible_sequences)]
        self.state.available_questions = [True for _ in self.rounds[0]]
        self.gm_name = "".join(random.choices(string.ascii_uppercase, k=4))  # nosec

    def path(self, name: str) -> Path:
        if name == self.gm_name:
            name = "gm.html"
        if name == "/":
            name = "display.html"

        return Path(__file__).parent / "resources" / name

    def redirect(self) -> str:
        return self.gm_name

    async def round(self, data: dict[str, str | int]) -> bool:
        if self.state.current_question:
            return False

        index = int(data.get("index", -1))

        if index < 0 or index >= len(self.rounds):
            return False

        self.state.current_round = index
        self.state.available_questions = [True for _ in self.rounds[index]]
        return True

    async def select(self, data: dict[str, str | int]) -> AsyncIterator[bool]:
        if self.state.current_question:
            yield False
            return

        index = int(data.get("index", -1))

        if index < 0 or index >= len(self.state.available_questions):
            yield False
            return

        if not self.state.available_questions[index]:
            yield False
            return

        self.state.available_questions[index] = False
        self.state.selecting = index
        yield True

        self.state.selecting = None
        self.state.current_question = self.rounds[self.state.current_round][index]
        await asyncio.sleep(0.5)
        yield True

    async def clue(self, _: dict[str, str | int]) -> bool:
        if not self.state.current_question:
            return False

        if self.state.revealed_clues < self.state.current_question.max_clues:
            self.state.revealed_clues += 1
            return True

        return False

    async def reveal(self, _: dict[str, str | int]) -> bool:
        if not self.state.current_question:
            return False

        self.state.answer_revealed = True
        return True

    async def next_question(self, _: dict[str, str | int]) -> bool:
        if not self.state.current_question:
            return False

        self.state.current_question = None
        self.state.answer_revealed = False
        self.state.revealed_clues = 0
        return True

    async def score(self, _: dict[str, str | int]) -> bool:
        if not self.state.current_question:
            return False

        points = [5, 3, 2, 1]
        score = points[self.state.revealed_clues]

        self.state.scores[self.state.current_team] += score
        self.state.current_question = None
        self.state.answer_revealed = False
        self.state.revealed_clues = 0
        return True


GENERAL_QUESTIONS = [
    Question(
        False,
        "Titles of the full Random Dance Party tracks",
        (
            "A Thousand Miles",
            "In The End",
            "Livin' On A Prayer",
            "We Like to Party! (The Vengabus) [2020 DJ Coriander Remix]",
        ),
        "drFox17 + Kitteh",
    ),
    Question(
        False,
        "Epithets of World of Darkness games (Wraith, Hunter, Mage, Vampire)",
        ("Ascension", "Oblivion", "Reckoning", "Masquerade"),
        "Kitsune",
    ),
    Question(
        False,
        "Forts on Vancouver Island",
        ("Rupert", "San Miguel", "Rodd Hill", "Victoria"),
        "Kitteh",
    ),
    Question(
        False,
        "Mozilla Products",
        ("SeaMonkey", "Thunderbird", "Bugzilla", "FireFox"),
        "Kitteh",
    ),
    Question(
        False,
        "Desert Bus intro parodies",
        ("Cowboy Bebop", "Bob Ross's Joy of Painting", "The Good Place", "Hamilton"),
        "drFox17",
    ),
    # Question(
    #     False,
    #     "Adjectives that prefix Kitteh's Twitch accounts",
    #     ("thirsty_", "Cuddly_", "disaster_", "two_distinct_")
    # )
    Question(
        True,
        "Synonyms for the main Desert Bus shifts, in reverse order",
        (
            "(eg) 6th Star (of a constellation)",
            "(eg) City Guard",
            "(eg) Canadian Superhero Team",
            "(eg) Morning Patrol",
        ),
        "Kitteh",
    ),
    Question(
        True,
        "The latest four Desert Bus locations",
        (
            "Moonbase mk. V (and empty adjacent unit)",
            "Lunar Module Mk IV",
            "Remote Bus / MB V",
            "Moonbase mk. VI",
        ),
        "Kitteh",
    ),
    Question(
        True,
        '"Major" Stops on Greyhound bus from East Tucson to Las Vegas',
        (
            "Phoenix Sky Harbor, Arizona",
            "Kingman, Arizona",
            "Henderson, Nevada",
            "Las Vegas, Nevada",
        ),
        "Kitteh",
    ),
    Question(
        True,
        "Number of times letters appear in Canadian provinces abbreviations",
        ("1: A, E, K, L, M, O, P, Q", "2: C,S", "3: (none)", "4: B, N"),
        "Kitteh (who is truly sorry)",
    ),
    Question(
        True,
        "Titular characters of Tamsyin Muir's The Locked Tomb series",
        ("Gideon", "Harrow", "Nona", "Alecto"),
        "Kitteh",
    ),
    Question(
        True,
        "Greek gods met in Percy Jackson and the Lightning Thief in order of appearance.",
        ("Dionysus", "Ares", "Hades", "Zeus and Poseidon"),
        "WriterRaven",
    ),
    Question(
        True,
        "The first 4 temples in Final Fantasy X",
        ("Island Village", "Port Island", "Mushroom Rock", "Frozen Lake"),
        "Laogeodritt",
    ),
    Question(
        True,
        "Shape at the bottom of the DB shift banners",
        ("Horizontal Line", "Line slanted upwards to the right",
         "Line going up, then back down", "Line going down, then back up"),
        "Kitteh",
    ),

    # Question(
    #     True,
    #     "Highest live-auction amounts for craft-along items",
    #     (
    #         "The Summoner's Shrine (Schala-Kitty)",
    #         "General Leia Cross Stitch (Sarah Overall)",
    #         "Breath of the Wild Cross Stitch (Sarah Overall)",
    #         "Link to the Past Coffee Table (Chris and Emily von Seele)"
    #     ),
    #     "Kitteh"
    # )
]

NIGHTWATCH_QUESTIONS = [
    Question(
        False,
        'Reasons "JULIE!!" was yelled on the first 2023 Night Watch shift',
        (
            "Look, we all make certain realisations at different paces.",
            "I can't stop thinking about her",
            "Can somebody donate exactly $80 so that the overlay reads 'boobs'?",
            "We slapped a pair of big stonkin' tits on it",
        ),
        "Kitteh with help from Julie's discord",
    ),
    Question(
        False,
        "Major memes of past Desert Bus",
        ("VVVVVV", "Patience", "Thwomp", "Belopa"),
        "Kitteh",
    ),
    Question(
        True,
        "Inspiration for the names of the DBZ Ginyu Force members, from shortest to tallest",
        ("yoghurt (~100cm)", "cheese (~170cm)", "cream (~230cm)", "butter (~250cm)"),
        "Laogeodritt",
    ),
    Question(
        True,
        "Characters Graham has portrayed on shift intros by year",
        (
            "2015: Bayley",
            "2016: Bobby Roode",
            "2017: Finn Balor",
            "2018: Sterling Archer",
        ),
        "drFox17",
    ),
]

ALPHAFLIGHT_QUESTIONS = [
    Question(
        False,
        "Readings on Alpha Flight this year",
        (
            "They're Made of Meat",
            "Blobfish Falls In Love With Its Reflection",
            "The Day the Crayons Quit",
            "Fox in Socks",
        ),
        "Kitteh",
    ),
]


class AlphaFlightGame(OnlyConnectGame):
    @classmethod
    def description(cls) -> str:
        return (
            "OnlyConnect for AlphaFlight (General Knowledge with DesertBus sub-theme)"
        )

    @classmethod
    def possible(cls) -> list[Question]:
        return ALPHAFLIGHT_QUESTIONS + GENERAL_QUESTIONS


class NightWatchGame(OnlyConnectGame):
    @classmethod
    def description(cls) -> str:
        return "OnlyConnect for Night Watch (General Knowledge with DesertBus + Night Watch themes)"

    @classmethod
    def possible(cls) -> list[Question]:
        return NIGHTWATCH_QUESTIONS + GENERAL_QUESTIONS


class TestGame(OnlyConnectGame):
    @classmethod
    def description(cls) -> str:
        return "TEST GAME DO NOT USE (If you see this Kitteh forgot to remove it from production)"

    @classmethod
    def possible(cls) -> list[Question]:
        return [

        ]
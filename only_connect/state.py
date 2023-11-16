import dataclasses
import random


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

    def __init__(self, is_sequence: bool, connection: str, clues: tuple[str, ...], credit: str) -> None:
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

    current_team: int = 0
    current_round: int = 0
    current_question: Question | None = None
    selecting: int | None = None

    # How many clues the team has revealed
    revealed_clues: int = 0
    answer_revealed: bool = False

    # Which questions are available for the team(s) to select
    available_questions: list[bool] = ...

    def __init__(self, total_teams: int) -> None:
        self.total_teams = total_teams
        self.scores = [0] * total_teams
        self.available_questions = []


class Game:
    @classmethod
    def description(cls) -> str:
        return str(cls)

    @classmethod
    def possible(cls) -> list[Question]:
        return []

    state: OverallState
    rounds: list[tuple[Question, ...]]

    def __init__(self, total_teams: int) -> None:
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

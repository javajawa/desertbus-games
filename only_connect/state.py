import dataclasses


@dataclasses.dataclass
class Question:
    # Whether this is a connections round (false), or a complete the sequence round (true)
    is_sequence: bool

    # What the connection between the clues is
    connection: str
    # What the four clues are
    clues: tuple[str, ...]

    id: str

    def __init__(self, is_sequence: bool, connection: str, clues: tuple[str, ...]) -> None:
        self.id = str(id(self))
        self.is_sequence = is_sequence
        self.connection = connection
        self.clues = clues

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

    state: OverallState
    rounds: list[tuple[Question, ...]]

    def __init__(self, total_teams: int) -> None:
        self.state = OverallState(total_teams)
        self.state.available_questions = [True for _ in self.rounds[0]]

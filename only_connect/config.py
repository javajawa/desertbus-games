from .state import Game, Question

SEQUENCES = (
    Question(
        True,
        "Synonyms for the main Desert Bus shifts, in reverse order",
        (
            "6th Star (of a constellation)",
            "City Guard",
            "Canadian Superhero Team",
            "(eg) Morning Patrol"
        )
    ),
    Question(
        True,
        "The latest four Desert Bus locations, going backward chronloigcally",
        (
            "Moonbase mk. V (and empty adjacent unit)",
            "Lunar Module Mk IV",
            "Remote Bus / MB V",
            "Moonbase mk. VI"
        )
    ),
    Question(
        True,
        "\"Major\" Stops on Greyhound bus from East Tucson to Las Vegas",
        (
            "Phoenix Sky Harbor, Arizona",
            "Kingman, Arizona",
            "Henderson, Nevada",
            "Las Vegas, Nevada"
        )
    ),
    Question(
        True,
        "Highest live-auction amounts for craft-along items",
        (
            "The Summoner's Shrine (Schala-Kitty)",
            "General Leia Cross Stitch (Sarah Overall)",
            "Breath of the Wild Cross Stitch (Sarah Overall)",
            "Link to the Past Coffee Table (Chris and Emily von Seele)"
        )
    )
)

CONNECTIONS = (
    Question(
        False,
        "Reasons \"JULIE!!\" was yelled on the first 2023 Night Watch shift",
        (
            "Look, we all make certain realisations at different paces.",
            "I can't stop thinking about her",
            "Can somebody donate exactly $80 so that the overlay reads 'boobs'?",
            "We slapped a pair of big stonkin' tits on it"
        )
    ),
    Question(
        False,
        "Major memes of past Desert Bus",
        ("VVVVVV", "Patience", "Thwomp", "Belopa")
    ),
    Question(
        False,
        "Titles of the full Random Dance Party tracks",
        ("A Thousand Miles", "In The End", "Livin' On A Prayer",
         "We Like to Party! (The Vengabus) [2020 DJ Coriander Remix]"),
    ),
    Question(
        False,
        "Adjectives that apply to Kitteh",
        ("thirsty_", "Cuddly_", "disaster_", "two_distinct_")
    )
)


class TestGame(Game):
    @classmethod
    def description(cls) -> str:
        return "Test Only Connect board by Kitteh"

    def __init__(self, total_teams: int) -> None:
        self.rounds = [CONNECTIONS, SEQUENCES]

        super().__init__(total_teams)

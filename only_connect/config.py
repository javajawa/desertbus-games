from .state import Game, Question


GENERAL_QUESTIONS = [
    Question(
        False,
        "Titles of the full Random Dance Party tracks",
        ("A Thousand Miles", "In The End", "Livin' On A Prayer",
         "We Like to Party! (The Vengabus) [2020 DJ Coriander Remix]"),
        "drFox17 + Kitteh"
    ),
    Question(
        False,
        "Epithets of World of Darkness games (Wraith, Hunter, Mage, Vampire)",
        ("Ascension", "Oblivion", "Reckoning", "Masquerade"),
        "Kitsune"
    ),
    Question(
        False,
        "Forts on Vancouver Island",
        ("Rupert", "San Miguel", "Rodd Hill", "Victoria"),
        "Kitteh"
    ),
    Question(
        False,
        "Mozilla Products",
        ("SeaMonkey", "Thunderbird", "Bugzilla", "FireFox"),
        "Kitteh"
    ),
    Question(
        False,
        "Desert Bus intro parodies",
        ("Cowboy Bebop", "Bob Ross's Joy of Painting", "The Good Place", "Hamilton"),
        "drFox17"
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
            "(eg) Morning Patrol"
        ),
        "Kitteh"
    ),
    Question(
        True,
        "The latest four Desert Bus locations",
        (
            "Moonbase mk. V (and empty adjacent unit)",
            "Lunar Module Mk IV",
            "Remote Bus / MB V",
            "Moonbase mk. VI"
        ),
        "Kitteh"
    ),
    Question(
        True,
        "\"Major\" Stops on Greyhound bus from East Tucson to Las Vegas",
        (
            "Phoenix Sky Harbor, Arizona",
            "Kingman, Arizona",
            "Henderson, Nevada",
            "Las Vegas, Nevada"
        ),
        "Kitteh"
    ),
    Question(
        True,
        "Number of times letters appear in Canadian provinces abbreviations",
        ("1: A, E, K, L, M, O, P, Q", "2: C,S", "3: (none)", "4: B, N"),
        "Kitteh (who is truly sorry)"
    ),
    Question(
        True,
        "Titular characters of Tamsyin Muir's The Locked Tomb series",
        ("Gideon", "Harrow", "Nona", "Alecto"),
        "Kitteh"
    ),
    Question(
        True,
        "Greek gods met in Percy Jackson and the Lightning Thief in order of appearance.",
        ("Dionysus", "Ares", "Hades", "Zeus and Poseidon"),
        "WriterRaven"
    ),
    Question(
        True,
        "The first 4 temples in Final Fantasy X",
        ("Island Village", "Port Island", "Mushroom Rock", "Frozen Lake"),
        "Laogeodritt",
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
        "Reasons \"JULIE!!\" was yelled on the first 2023 Night Watch shift",
        (
            "Look, we all make certain realisations at different paces.",
            "I can't stop thinking about her",
            "Can somebody donate exactly $80 so that the overlay reads 'boobs'?",
            "We slapped a pair of big stonkin' tits on it"
        ),
        "Kitteh with help from Julie's discord"
    ),
    Question(
        False,
        "Major memes of past Desert Bus",
        ("VVVVVV", "Patience", "Thwomp", "Belopa"),
        "Kitteh"
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
        ("2015: Bayley", "2016: Bobby Roode", "2017: Finn Balor", "2018: Sterling Archer"),
        "drFox17"
    ),
]

ALPHAFLIGHT_QUESTIONS = [
    Question(
        False,
        "Readings on Alpha Flight this year",
        ("They're Made of Meat", "Blobfish Falls In Love With Its Reflection", "The Day the Crayons Quit", "Fox in Socks"),
        "Kitteh"
    ),
]


class AlphaFlightGame(Game):
    @classmethod
    def description(cls) -> str:
        return "OnlyConnect for AlphaFlight (General Knowledge with DesertBus sub-theme)"

    @classmethod
    def possible(cls) -> list[Question]:
        return ALPHAFLIGHT_QUESTIONS + GENERAL_QUESTIONS

class NightWatchGame(Game):
    @classmethod
    def description(cls) -> str:
        return "OnlyConnect for Night Watch (General Knowledge with DesertBus + Night Watch themes)"

    @classmethod
    def possible(cls) -> list[Question]:
        return NIGHTWATCH_QUESTIONS + GENERAL_QUESTIONS

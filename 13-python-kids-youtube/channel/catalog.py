"""Reviewed episode catalog.

Every line a child might hear is written here. The daily job can render and
schedule these stories, and it stops when the catalog is used up instead of
publishing the same video again.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    about: str
    theme: str
    motif: str
    summary: str
    scenes: tuple[tuple[str, str], ...]


def _t(
    id: str,
    title: str,
    about: str,
    theme: str,
    motif: str,
    summary: str,
    scenes: list[tuple[str, str]],
) -> Topic:
    return Topic(id, title, about, theme, motif, summary, tuple(scenes))


TOPICS: tuple[Topic, ...] = (
    _t(
        "why-bees-buzz",
        "Why Bees Buzz",
        "bees",
        "garden",
        "bee",
        "Bees flap fast wings, and that buzz helps flowers make seeds.",
        [
            ("flower", "Have you ever heard a tiny buzz beside a flower?"),
            ("bee", "That sound is a bee flapping its wings very fast."),
            ("bee", "Fast wings push the air, and our ears hear a buzz."),
            ("flower", "The bee sips nectar, a sweet drink inside the flower."),
            ("flower", "Pollen sticks to the bee and rides to the next flower."),
            ("seed", "Pollen helps the flower make seeds that can grow."),
            ("bee", "Hum softly and flap your arms slowly."),
            ("bee", "Let's say it once more."),
            ("flower", "Bees buzz with fast wings and help flowers make seeds."),
        ],
    ),
    _t(
        "how-flowers-drink",
        "How Flowers Drink",
        "how flowers drink",
        "garden",
        "flower",
        "Flowers drink water that travels from the roots up the stem.",
        [
            ("flower", "A flower drinks water from the ground."),
            ("seed", "The roots take the water in."),
            ("flower", "The water moves up the stem, like a straw."),
            ("leaf", "It reaches the leaves and the petals."),
            ("water", "Sun and water help the flower stay strong."),
            ("flower", "Find a plant and look at its stem."),
            ("flower", "Let's say it once more."),
            ("leaf", "Water goes from the roots, up the stem, to the leaves."),
        ],
    ),
    _t(
        "what-the-sun-does",
        "What the Sun Does",
        "the sun",
        "sky",
        "sun",
        "The sun is a far-away star whose light warms the ground and helps plants grow.",
        [
            ("sun", "The sun is a star very far away."),
            ("sun", "Its light warms the ground."),
            ("leaf", "Plants use the sunlight to grow."),
            ("sun", "Do not look straight at the sun."),
            ("sun", "It is too bright for your eyes."),
            ("sun", "Stand in the sun, then stand in the shade."),
            ("sun", "Notice which place feels warmer."),
            ("sun", "Let's say it once more."),
            ("leaf", "The sun warms the ground and helps plants grow."),
        ],
    ),
    _t(
        "why-the-moon-changes",
        "Why the Moon Changes",
        "the moon",
        "night",
        "moon",
        "The moon looks different because we see a changing bright side.",
        [
            ("moon", "The moon does not make its own light."),
            ("sun", "Sunlight shines on the moon."),
            ("phases", "We see only the bright part."),
            ("phases", "As the moon moves, that part looks different."),
            ("moon", "That is why the shape seems to change."),
            ("moon", "Look for the moon with a grown-up."),
            ("phases", "Let's say it once more."),
            ("moon", "Sunlight lights the moon, and we see the bright part."),
        ],
    ),
    _t(
        "why-rain-falls",
        "Why Rain Falls",
        "rain",
        "sky",
        "rain",
        "Rain is water that rose into a cloud and fell back down.",
        [
            ("sun", "The sun warms water on the ground."),
            ("cloud", "The water rises and makes a cloud."),
            ("rain", "Drops in the cloud grow heavy and fall."),
            ("flower", "Rain gives plants a drink."),
            ("rain", "If you hear thunder, stay inside."),
            ("rain", "Stay with a grown-up when a storm is near."),
            ("cloud", "Let's say it once more."),
            ("rain", "Water rises, makes a cloud, and falls as rain."),
        ],
    ),
    _t(
        "counting-little-stars",
        "Counting Little Stars",
        "counting to five",
        "night",
        "star",
        "Count from one to five with five little stars.",
        [
            ("n1", "One little star."),
            ("n2", "Two little stars."),
            ("n3", "Three little stars."),
            ("n4", "Four little stars."),
            ("n5", "Five little stars."),
            ("star", "Hold up one finger for each star."),
            ("star", "Let's say it once more."),
            ("n5", "One, two, three, four, five."),
        ],
    ),
    _t(
        "colors-in-the-garden",
        "Colors in the Garden",
        "colors",
        "garden",
        "rainbow",
        "Red, yellow, blue, and green are colors you can find nearby.",
        [
            ("apple", "This color is red, like an apple."),
            ("sun", "This color is yellow, like the sun."),
            ("water", "This color is blue, like water."),
            ("leaf", "This color is green, like a leaf."),
            ("rainbow", "Red, yellow, blue, and green can share one garden."),
            ("flower", "Point to something nearby and say its color."),
            ("rainbow", "Let's say it once more."),
            ("flower", "Red, yellow, blue, and green are garden colors."),
        ],
    ),
    _t(
        "how-fish-swim",
        "How Fish Swim",
        "how fish swim",
        "sea",
        "fish",
        "Fish breathe with gills and swim by moving their tails.",
        [
            ("fish", "Fish live in the water."),
            ("fish", "They breathe with gills on their sides."),
            ("fish", "A fish swims by moving its tail."),
            ("water", "Fins help the fish turn and stop."),
            ("fish", "Some fish are tiny, and some are big."),
            ("fish", "Move your hand like a slow fish tail."),
            ("fish", "Let's say it once more."),
            ("water", "Fish use gills to breathe and tails to swim."),
        ],
    ),
    _t(
        "how-birds-nest",
        "How Birds Nest",
        "bird nests",
        "sky",
        "nest",
        "Birds weave a cup of twigs so their eggs can stay warm.",
        [
            ("bird", "A bird builds a nest for its eggs."),
            ("tree", "It gathers twigs and soft grass."),
            ("nest", "The nest is a little cup."),
            ("nest", "The eggs stay warm inside."),
            ("bird", "Watch a nest from far away."),
            ("bird", "A quiet watcher keeps the bird calm."),
            ("nest", "Let's say it once more."),
            ("bird", "Birds weave a cup, and the eggs stay warm inside."),
        ],
    ),
    _t(
        "how-leaves-help",
        "How Leaves Help",
        "how leaves help",
        "garden",
        "leaf",
        "Leaves use sunlight, air, and water to make food for the tree.",
        [
            ("tree", "A leaf is a little kitchen for the tree."),
            ("sun", "The leaf takes in sunlight."),
            ("leaf", "It also takes in air and water."),
            ("leaf", "Then the leaf makes food for the tree."),
            ("tree", "Leaves help make the oxygen we breathe."),
            ("leaf", "Find a leaf and notice its shape."),
            ("leaf", "Let's say it once more."),
            ("tree", "Leaves use light, air, and water, and they help our air."),
        ],
    ),
    _t(
        "how-rockets-lift",
        "How Rockets Lift Off",
        "how rockets lift off",
        "space",
        "rocket",
        "A rocket goes up because it pushes hot gas down.",
        [
            ("rocket", "A rocket is made to go up high."),
            ("rocket", "It burns fuel and pushes hot gas down."),
            ("rocket", "When the gas goes down, the rocket goes up."),
            ("star", "That push is called thrust."),
            ("rocket", "Rockets can carry people and tools."),
            ("rocket", "Crouch down, then jump up gently."),
            ("rocket", "Let's say it once more."),
            ("star", "Gas pushes down, and the rocket goes up."),
        ],
    ),
    _t(
        "why-trains-stay-on-track",
        "Why Trains Stay on the Track",
        "how trains stay on the track",
        "cozy",
        "train",
        "A small lip on each wheel keeps a train on the rails.",
        [
            ("train", "A train rolls on two steel rails."),
            ("train", "Each wheel has a little lip on the inside."),
            ("train", "That lip keeps the wheel on the rail."),
            ("train", "An engine pulls the cars behind it."),
            ("train", "The cars stay in a long line."),
            ("train", "Slide two fingers along the edge of a table."),
            ("train", "Let's say it once more."),
            ("train", "A lip on each wheel keeps the train on the rails."),
        ],
    ),
    _t(
        "how-apples-grow",
        "How Apples Grow",
        "how apples grow",
        "garden",
        "apple",
        "An apple starts as a blossom and grows on the tree.",
        [
            ("flower", "An apple starts as a blossom."),
            ("bee", "A bee may bring pollen to that blossom."),
            ("apple", "The blossom turns into a tiny apple."),
            ("apple", "Sun and rain help the apple grow."),
            ("apple", "Inside are small seeds in a star shape."),
            ("apple", "Share an apple and look for the seeds."),
            ("apple", "Let's say it once more."),
            ("tree", "A blossom becomes an apple with seeds inside."),
        ],
    ),
    _t(
        "how-butterflies-change",
        "How Butterflies Change",
        "how butterflies change",
        "garden",
        "butterfly",
        "A caterpillar makes a chrysalis, then comes out as a butterfly.",
        [
            ("butterfly", "A butterfly starts as a tiny egg."),
            ("leaf", "A caterpillar hatches and eats leaves."),
            ("leaf", "Then it makes a chrysalis."),
            ("butterfly", "Inside, its body changes."),
            ("butterfly", "A butterfly comes out and dries its wings."),
            ("butterfly", "Open and close your hands like slow wings."),
            ("butterfly", "Let's say it once more."),
            ("leaf", "Egg, caterpillar, chrysalis, then butterfly."),
        ],
    ),
    _t(
        "choosing-kindness",
        "Choosing Kindness",
        "kindness",
        "cozy",
        "heart",
        "Kindness is sharing, using a gentle voice, and waiting for a turn.",
        [
            ("heart", "Kindness helps someone feel safe and glad."),
            ("heart", "You can share a toy."),
            ("heart", "You can use a gentle voice."),
            ("heart", "You can wait for a turn."),
            ("balloon", "A kind choice can be small."),
            ("heart", "Pick one kind thing to do today."),
            ("heart", "Let's say it once more."),
            ("heart", "Share a toy, use a gentle voice, and wait for a turn."),
        ],
    ),
    _t(
        "why-turtles-are-slow",
        "Why Turtles Are Slow",
        "turtles",
        "garden",
        "turtle",
        "A turtle's shell is part of its body, so it walks with care.",
        [
            ("turtle", "A turtle carries its shell."),
            ("turtle", "The shell is part of its body."),
            ("turtle", "The shell helps keep the turtle safe."),
            ("turtle", "Many turtles walk slowly."),
            ("water", "Some turtles swim, and some live on land."),
            ("turtle", "Try walking slowly across the room."),
            ("turtle", "Let's say it once more."),
            ("turtle", "The shell stays on, and many turtles walk slowly."),
        ],
    ),
    _t(
        "what-snow-is",
        "What Snow Is",
        "snow",
        "snow",
        "snow",
        "Snow is tiny ice crystals that fall from a cold cloud.",
        [
            ("cloud", "Snow starts high in a cold cloud."),
            ("snow", "Water drops freeze into tiny crystals."),
            ("snow", "The crystals fall and pile up."),
            ("snow", "When the air warms, snow melts to water."),
            ("snow", "Look at a snowflake on a dark sleeve."),
            ("snow", "If there is no snow, you can still picture one."),
            ("snow", "Let's say it once more."),
            ("cloud", "Snow is ice crystals that fall and can melt to water."),
        ],
    ),
    _t(
        "whale-songs",
        "Songs of the Whales",
        "whale songs",
        "sea",
        "whale",
        "Whales breathe air and some of them make deep sounds in the water.",
        [
            ("whale", "Whales are very big animals."),
            ("whale", "They live in the ocean, but they breathe air."),
            ("whale", "A whale breathes through a blowhole on top."),
            ("whale", "Some whales make deep sounds in the water."),
            ("water", "Those sounds can travel a long way."),
            ("whale", "Hum one low, gentle note."),
            ("whale", "Let's say it once more."),
            ("water", "Whales breathe air, and some sing deep sounds."),
        ],
    ),
    _t(
        "how-seeds-sprout",
        "How Seeds Sprout",
        "how seeds sprout",
        "garden",
        "seed",
        "A seed holds a baby plant that grows with water, soil, and sun.",
        [
            ("seed", "A seed holds a baby plant."),
            ("seed", "It also holds a little bit of food."),
            ("water", "Water, soil, and sun wake the seed."),
            ("seed", "A root grows down."),
            ("leaf", "A shoot grows up toward the light."),
            ("seed", "Curl up small, then stretch up tall."),
            ("seed", "Let's say it once more."),
            ("leaf", "A root goes down, and a shoot grows up to the light."),
        ],
    ),
    _t(
        "where-rainbows-come-from",
        "Where Rainbows Come From",
        "rainbows",
        "sky",
        "rainbow",
        "A rainbow appears when sunlight splits inside falling raindrops.",
        [
            ("rain", "A rainbow needs rain and sunlight."),
            ("sun", "Sunlight shines into the water drops."),
            ("rainbow", "The light splits into many colors."),
            ("rainbow", "Red, orange, and yellow are on the outside."),
            ("rainbow", "Green, blue, and violet are on the inside."),
            ("rainbow", "Name the colors you can see."),
            ("rainbow", "Let's say it once more."),
            ("sun", "Sunlight and raindrops can make a rainbow."),
        ],
    ),
    _t(
        "stories-in-books",
        "Stories in Books",
        "books",
        "cozy",
        "book",
        "A book holds words and pictures that tell a story.",
        [
            ("book", "A book holds words and pictures."),
            ("book", "Each page is a new part of the story."),
            ("book", "You can read the words with a grown-up."),
            ("book", "You can also tell the story from the pictures."),
            ("star", "Stories can be funny, quiet, or brave."),
            ("book", "Pick a book and point to one picture."),
            ("book", "Let's say it once more."),
            ("book", "Books hold words and pictures that tell a story."),
        ],
    ),
)


def by_id(topic_id: str) -> Topic:
    for topic in TOPICS:
        if topic.id == topic_id:
            return topic
    known = ", ".join(topic.id for topic in TOPICS)
    raise KeyError(f"Unknown episode {topic_id}. Known episodes: {known}")


def validate(motifs: set[str], themes: set[str]) -> None:
    seen: set[str] = set()
    for topic in TOPICS:
        if topic.id in seen:
            raise ValueError(f"Duplicate episode id {topic.id}")
        seen.add(topic.id)
        if topic.theme not in themes:
            raise ValueError(f"{topic.id} uses unknown theme {topic.theme}")
        if topic.motif not in motifs:
            raise ValueError(f"{topic.id} uses unknown motif {topic.motif}")
        for motif, _line in topic.scenes:
            if motif not in motifs:
                raise ValueError(f"{topic.id} uses unknown motif {motif}")
        if not topic.scenes:
            raise ValueError(f"{topic.id} has no scenes")

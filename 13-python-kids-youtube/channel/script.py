"""Turn a catalog topic into the spoken scenes of one episode."""

from __future__ import annotations

from dataclasses import dataclass

from channel.catalog import Topic


@dataclass(frozen=True)
class Scene:
    kind: str
    motif: str
    narration: str
    caption: str
    theme: str


@dataclass(frozen=True)
class EpisodeScript:
    topic_id: str
    title: str
    summary: str
    theme: str
    motif: str
    scenes: tuple[Scene, ...]

    @property
    def narrations(self) -> list[str]:
        return [scene.narration for scene in self.scenes]

    @property
    def captions(self) -> list[str]:
        return [scene.caption for scene in self.scenes]


def build(topic: Topic) -> EpisodeScript:
    hello = (
        f"Hello, little friend. I am Luma. Today we learn about {topic.about}."
    )
    goodbye = "I am glad we learned together. We can learn again tomorrow. Bye for now."
    scenes = [
        Scene("title", topic.motif, hello, topic.title, topic.theme),
    ]
    for motif, line in topic.scenes:
        scenes.append(Scene("teach", motif, line, line, topic.theme))
    scenes.append(Scene("bye", "lantern", goodbye, goodbye, topic.theme))
    return EpisodeScript(
        topic_id=topic.id,
        title=topic.title,
        summary=topic.summary,
        theme=topic.theme,
        motif=topic.motif,
        scenes=tuple(scenes),
    )

"""WorldGraph: the political graph of the world.

Holds the extracted characters, titles, dynasties, and wars, and provides
queries over the liege/vassal hierarchy reconstructed from ``de_facto_liege``.
"""

from __future__ import annotations

from .extract import Character, Dynasty, SaveReader, Title, War


class WorldGraph:
    def __init__(
        self,
        characters: dict[int, Character],
        titles: dict[int, Title],
        dynasties: dict[int, Dynasty],
        wars: dict[int, War],
    ):
        self.characters = characters
        self.titles = titles
        self.dynasties = dynasties
        self.wars = wars
        # liege title id -> list of vassal title ids (for fast realm traversal)
        self._vassal_titles: dict[int, list[int]] = {}
        # holder id -> list of held title ids (for fast primary-title lookup)
        self._titles_by_holder: dict[int, list[int]] = {}
        for t in titles.values():
            if t.de_facto_liege is not None:
                self._vassal_titles.setdefault(t.de_facto_liege, []).append(t.id)
            if t.holder is not None:
                self._titles_by_holder.setdefault(t.holder, []).append(t.id)

    @classmethod
    def from_save(cls, reader: SaveReader) -> WorldGraph:
        characters = {c.id: c for c in reader.characters()}
        titles = {t.id: t for t in reader.titles()}
        dynasties = {d.id: d for d in reader.dynasties()}
        wars = {w.id: w for w in reader.wars()}
        # resolve modded title prefixes (e.g. x_mc_0) to their tier
        templates = reader.dynamic_templates()
        for t in titles.values():
            if t.key in templates:
                t.tier = templates[t.key]
        return cls(characters, titles, dynasties, wars)

    def get_ruler(self, char_id: int) -> Character | None:
        return self.characters.get(char_id)

    def primary_title(self, char_id: int) -> Title | None:
        """Highest-rank title held by the character."""
        held_ids = self._titles_by_holder.get(char_id)
        if not held_ids:
            return None
        return max((self.titles[tid] for tid in held_ids), key=lambda t: t.rank)

    def get_realm_titles(self, char_id: int) -> list[Title]:
        """All titles whose ``de_facto_liege`` chain reaches the primary title."""
        primary = self.primary_title(char_id)
        if primary is None:
            return []
        realm_ids = {primary.id}
        frontier = [primary.id]
        while frontier:
            tid = frontier.pop()
            for vassal_id in self._vassal_titles.get(tid, []):
                if vassal_id not in realm_ids:
                    realm_ids.add(vassal_id)
                    frontier.append(vassal_id)
        return [self.titles[tid] for tid in realm_ids]

    def get_vassals(self, char_id: int) -> list[Character]:
        """Distinct holders of the realm's titles, excluding the ruler."""
        holders = {t.holder for t in self.get_realm_titles(char_id)}
        holders.discard(char_id)
        holders.discard(None)
        return [self.characters[h] for h in holders if h in self.characters]

    def get_liege(self, char_id: int) -> Character | None:
        """The holder of the primary title's ``de_facto_liege``."""
        primary = self.primary_title(char_id)
        if primary is None or primary.de_facto_liege is None:
            return None
        liege_title = self.titles.get(primary.de_facto_liege)
        if liege_title is None or liege_title.holder is None:
            return None
        return self.characters.get(liege_title.holder)

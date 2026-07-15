"""Single source of truth for BAT (Biodiversity Analysis Tool) definitions."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Directory holding the long-form BAT descriptions markdown files.
BAT_ABOUT_DIR = Path(__file__).parent / "about"


class EcosystemCategory(Enum):
    """Ecosystem categories to which BATs get assigned.

    Each member carries 2 values:
    * label: display label.
    * icon: the "Material icon" to be used as icon for the category. This
      value must match an existing name from the Material Icons font
      (see https://fonts.google.com/icons).
    """

    TERRESTRIAL = ("Terrestrial Ecosystems", "forest")
    FRESHWATER = ("Freshwater Ecosystems", "water")
    MARINE = ("Marine Ecosystems", "anchor")

    def __init__(self, label: str, icon: str) -> None:
        self.label = label
        self.icon = icon

    @property
    def slug(self) -> str:
        """URL slug for the category, i.e. the name of the category as it
        appears in a URL
        """
        return self.name.lower()


@dataclass(frozen=True, slots=True)
class Bat:
    """Biodiversity Analysis Tool (BAT) data used to build the UI "card"
    for a given BAT.
    """

    # Name must match the python module name of the BAT.
    name: str
    category: EcosystemCategory
    label: str
    # Short one-line description.
    description: str
    # Material icon name for the card
    icon: str

    @property
    def about_md(self) -> str:
        """Long-form description, read from a markdown file."""
        return (BAT_ABOUT_DIR / f"{self.name}.md").read_text(encoding="utf-8")

    @property
    def module_path(self) -> str:
        """Import path of the module file for the BAT."""
        return f"bats.{self.name}"

    @property
    def slug(self) -> str:
        """Slug name to use in page URL. This is the BAT name, minus the
        leading ecosystem category prefix, if any.
        """
        return self.name.removeprefix(f"{self.category.slug}_")

    @property
    def route(self) -> str:
        """Derived page route, e.g. /bat/terrestrial/sdm."""
        return f"/bat/{self.category.slug}/{self.slug}"


BAT_REGISTRY: tuple[Bat, ...] = (
    Bat(
        name="terrestrial_sdm",
        category=EcosystemCategory.TERRESTRIAL,
        label="Species Distribution Modeling",
        description="Predict suitable habitats for terrestrial species",
        icon="pin_drop",
    ),
    Bat(
        name="terrestrial_captain",
        category=EcosystemCategory.TERRESTRIAL,
        label="CAPTAIN",
        description="Prioritize conservation areas",
        icon="hub",
    ),
)


def bats_by_category(category: EcosystemCategory) -> list[Bat]:
    """Return the BATs belonging to a category, in registry order."""
    return [bat for bat in BAT_REGISTRY if bat.category is category]


def get_bat_by_name(name: str) -> Bat:
    """Return the BAT with the given name. Raises a `KeyError` if the BAT is
    not in the registry.
    """
    for bat in BAT_REGISTRY:
        if bat.name == name:
            return bat
    raise KeyError(name)

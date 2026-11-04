from ._anvil_designer import AutocompleteChipsTemplate
from anvil.js import get_dom_node
from anvil_extras.Autocomplete import Autocomplete
from anvil_extras.Chip import Chip

# Colour pairs: (border/text colour, light background tint)
_PALETTE = [
    ('#1565c0', 'rgba(21,101,192,0.09)'),    # blue
    ('#6a1b9a', 'rgba(106,27,154,0.09)'),    # purple
    ('#00695c', 'rgba(0,105,92,0.09)'),      # teal
    ('#e65100', 'rgba(230,81,0,0.09)'),      # orange
    ('#c62828', 'rgba(198,40,40,0.09)'),     # red
    ('#2e7d32', 'rgba(46,125,50,0.09)'),     # green
    ('#4527a0', 'rgba(69,39,160,0.09)'),     # deep purple
    ('#00838f', 'rgba(0,131,143,0.09)'),     # cyan
]


class AutocompleteChips(AutocompleteChipsTemplate):
    def __init__(self, **properties):
        self._chips = []
        self._suggestions = []
        self._placeholder = "Type to search..."
        self._autocomplete = None

        # init_components must run first — it initialises the FlowPanel and
        # calls property setters, which accumulate state in _suggestions/_placeholder.
        self.init_components(**properties)

        # Build Autocomplete with whatever suggestions/placeholder were set above.
        self._autocomplete = Autocomplete(
            suggestions=self._suggestions,
            placeholder=self._placeholder,
            suggest_if_empty=False,
            filter_mode="contains",
            spacing_above="none",
            spacing_below="none",
        )
        self._autocomplete.set_event_handler("suggestion_clicked", self._on_suggestion_clicked)
        self.add_component(self._autocomplete)

        get_dom_node(self).classList.add("aac-wrapper")

    # --- suggestions ---

    @property
    def suggestions(self):
        return list(self._suggestions)

    @suggestions.setter
    def suggestions(self, value):
        self._suggestions = list(value or [])
        if self._autocomplete is not None:
            self._autocomplete.suggestions = self._suggestions

    # --- placeholder ---

    @property
    def placeholder(self):
        return self._placeholder

    @placeholder.setter
    def placeholder(self, value):
        self._placeholder = value or "Type to search..."
        if self._autocomplete is not None:
            self._autocomplete.placeholder = self._placeholder

    # --- chips ---

    @property
    def chips(self):
        return list(self._chips)

    @chips.setter
    def chips(self, value):
        for component in list(self.get_components()):
            if isinstance(component, Chip):
                component.remove_from_parent()
        self._chips = []
        for item in (value or []):
            if item and item not in self._chips:
                self._add_chip(item)

    # --- private helpers ---

    def _add_chip(self, text):
        color, bg = _PALETTE[len(self._chips) % len(_PALETTE)]
        chip = Chip(
            text=text,
            background=bg,
            foreground=color,
            spacing_above="none",
            spacing_below="none",
        )
        get_dom_node(chip).style.border = f"1.5px solid {color}"
        chip.set_event_handler("close_click", self._on_chip_close)
        self.add_component(chip, index=len(self._chips))
        self._chips.append(text)

    def _on_suggestion_clicked(self, **event_args):
        text = self._autocomplete.text
        if text and text in self._suggestions and text not in self._chips:
            self._add_chip(text)
            self.raise_event("chips_changed", chips=self.chips)
        self._autocomplete.text = ""

    def _on_chip_close(self, sender, **event_args):
        chip_text = sender.text
        if chip_text in self._chips:
            self._chips.remove(chip_text)
        sender.remove_from_parent()
        self.raise_event("chips_changed", chips=self.chips)

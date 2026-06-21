"""Deterministic, offline catalog for development and interface testing."""

from __future__ import annotations


_FOODS = (
    ("baby-spinach", "Baby spinach", "bag", "g"), ("romaine", "Romaine lettuce", "head", "each"),
    ("broccoli", "Broccoli", "crown", "each"), ("carrots", "Carrots", "bag", "g"),
    ("red-onion", "Red onion", "each", "each"), ("garlic", "Garlic", "bulb", "each"),
    ("russet-potatoes", "Russet potatoes", "bag", "kg"), ("avocado", "Avocado", "each", "each"),
    ("bananas", "Bananas", "bunch", "each"), ("blueberries", "Blueberries", "clamshell", "g"),
    ("strawberries", "Strawberries", "clamshell", "g"), ("lemons", "Lemons", "bag", "each"),
    ("chicken-thighs", "Chicken thighs", "tray", "g"), ("ground-beef", "Ground beef", "pack", "g"),
    ("salmon", "Salmon fillet", "fillet", "g"), ("bacon", "Bacon", "pack", "g"),
    ("eggs", "Eggs", "dozen", "each"), ("whole-milk", "Whole milk", "carton", "ml"),
    ("greek-yogurt", "Greek yogurt", "tub", "g"), ("cheddar", "Cheddar cheese", "block", "g"),
    ("butter", "Salted butter", "block", "g"), ("sourdough", "Sourdough bread", "loaf", "each"),
    ("basmati-rice", "Basmati rice", "bag", "g"), ("spaghetti", "Spaghetti", "box", "g"),
    ("black-beans", "Black beans", "can", "g"), ("chickpeas", "Chickpeas", "can", "g"),
    ("crushed-tomatoes", "Crushed tomatoes", "can", "ml"), ("coconut-milk", "Coconut milk", "can", "ml"),
    ("vegetable-stock", "Vegetable stock", "carton", "ml"), ("olive-oil", "Extra-virgin olive oil", "bottle", "ml"),
    ("soy-sauce", "Soy sauce", "bottle", "ml"), ("peanut-butter", "Peanut butter", "jar", "g"),
    ("rolled-oats", "Rolled oats", "canister", "g"), ("all-purpose-flour", "All-purpose flour", "bag", "g"),
    ("granulated-sugar", "Granulated sugar", "bag", "g"), ("coffee", "Coffee beans", "bag", "g"),
    ("frozen-peas", "Frozen peas", "bag", "g"), ("frozen-corn", "Frozen corn", "bag", "g"),
    ("vanilla-ice-cream", "Vanilla ice cream", "tub", "ml"), ("dark-chocolate", "Dark chocolate", "bar", "g"),
)

MOCKED_FOODS = [
    {"id": f"mocked:{food_id}", "label": label, "format": package, "unit": unit}
    for food_id, label, package, unit in _FOODS
]

MOCKED_STOCK = [
    {"id": "mocked:baby-spinach", "quantity": 180},
    {"id": "mocked:eggs", "quantity": 2},
    {"id": "mocked:whole-milk", "quantity": 0},
    {"id": "mocked:basmati-rice", "quantity": 1200},
    {"id": "mocked:coffee", "quantity": 350},
    {"id": "mocked:frozen-peas", "quantity": 600},
    # Newly bought products for the Needs Attention review flow.
    {"id": "mocked:dark-chocolate", "quantity": 2},
    {"id": "mocked:coconut-milk", "quantity": 3},
    {"id": "mocked:salmon", "quantity": 450},
    {"id": "mocked:avocado", "quantity": 4},
    {"id": "mocked:olive-oil", "quantity": 750.5},
    {"id": "mocked:soy-sauce", "quantity": 125},
    {"id": "mocked:bananas", "quantity": 6},
]

MOCKED_STORAGE_LOCATIONS = [
    {"id": "mocked:fridge", "name": "Fridge", "provider": "mocked", "active": True, "location_type": "fridge", "sublocations": ["Top shelf", "Bottom drawer", "Door bin"]},
    {"id": "mocked:freezer", "name": "Freezer", "provider": "mocked", "active": True, "location_type": "freezer", "sublocations": ["Top shelf", "Door bin"]},
    {"id": "mocked:pantry", "name": "Pantry", "provider": "mocked", "active": True, "location_type": "pantry", "sublocations": ["Dry goods", "Coffee shelf"]},
]


_PROTEIN_RECIPES = (
    ("chicken-thighs", "Chicken thighs", "poultry", "chicken"),
    ("ground-beef", "Ground beef", "red-meat", "beef"),
    ("salmon", "Salmon fillet", "fish", "salmon"),
    ("eggs", "Eggs", "vegetarian", "egg"),
    ("black-beans", "Black beans", "vegetarian", "beans"),
    ("chickpeas", "Chickpeas", "vegetarian", "chickpeas"),
)

_VEGETABLE_RECIPES = (
    ("baby-spinach", "Baby spinach", "leafy_green", "spinach"),
    ("broccoli", "Broccoli", "cruciferous", "broccoli"),
    ("carrots", "Carrots", "root_vegetable", "carrots"),
    ("frozen-peas", "Frozen peas", "legume", "peas"),
    ("frozen-corn", "Frozen corn", "corn", "corn"),
    ("romaine", "Romaine lettuce", "leafy_green", "romaine"),
)

_STARCH_RECIPES = (
    ("basmati-rice", "Basmati rice", "rice", "basmati-rice"),
    ("russet-potatoes", "Russet potatoes", "potato", "russet-potatoes"),
    ("spaghetti", "Spaghetti", "noodle", "spaghetti"),
    ("rolled-oats", "Rolled oats", "grain", "oats"),
    ("sourdough", "Sourdough bread", "bread", "sourdough"),
    ("all-purpose-flour", "All-purpose flour", "baked", "flour"),
)

_SUPPORTING_INGREDIENTS = (
    ("garlic", "Garlic", 2, "each"),
    ("red-onion", "Red onion", 1, "each"),
    ("lemons", "Lemons", 1, "each"),
    ("olive-oil", "Extra-virgin olive oil", 30, "ml"),
    ("soy-sauce", "Soy sauce", 15, "ml"),
    ("butter", "Salted butter", 20, "g"),
    ("vegetable-stock", "Vegetable stock", 250, "ml"),
    ("crushed-tomatoes", "Crushed tomatoes", 200, "ml"),
    ("coconut-milk", "Coconut milk", 200, "ml"),
    ("greek-yogurt", "Greek yogurt", 100, "g"),
)

_MEALIE_STYLES = (
    ("Sheet-pan", "Batch-friendly sheet-pan prep"),
    ("Braised", "Slow braise for portioned prep"),
    ("Skillet", "Weeknight skillet batch"),
    ("Roasted", "Roasted meal-prep component"),
    ("Stewed", "Freezer-friendly stew"),
    ("Grain bowl", "Bowl-ready prep component"),
    ("Lemon herb", "Bright prep component"),
    ("Tomato garlic", "Saucy prep component"),
    ("Coconut", "Coconut-rich prep component"),
    ("Soy ginger", "Savory prep component"),
)


def _mocked_recipe_ingredient(food_id: str, label: str, quantity: int | float, unit: str) -> dict[str, object]:
    """Return one Mealie-style ingredient row for the offline catalog."""
    return {
        "food_id": f"mocked:{food_id}",
        "label": label,
        "quantity": quantity,
        "unit": unit,
        "original": f"{quantity:g} {unit} {label}".strip(),
    }


def _generated_mealie_recipe(index: int) -> dict[str, object]:
    """Return a stable Mealie-style mocked recipe."""
    style, format_text = _MEALIE_STYLES[(index - 1) % len(_MEALIE_STYLES)]
    role = (index - 1) % 3
    support = _SUPPORTING_INGREDIENTS[(index * 2) % len(_SUPPORTING_INGREDIENTS)]
    second_support = _SUPPORTING_INGREDIENTS[(index * 2 + 3) % len(_SUPPORTING_INGREDIENTS)]
    if role == 0:
        food_id, label, family, detail = _PROTEIN_RECIPES[(index - 1) % len(_PROTEIN_RECIPES)]
        recipe_id = f"mocked:recipe:mealie-protein-{index:03d}"
        return {
            "id": recipe_id,
            "label": f"{style} {label}",
            "format": format_text,
            "unit": "portions",
            "ingredients": [
                _mocked_recipe_ingredient(food_id, label, 450, "g"),
                _mocked_recipe_ingredient(*support),
                _mocked_recipe_ingredient(*second_support),
            ],
            "tags": [
                "mpa:component:protein",
                f"mpa:primary-protein:{family}",
                f"mpa:protein-detail:{detail}",
            ],
            "categories": ["Mealie demo", "Dinner"],
        }
    if role == 1:
        food_id, label, family, detail = _VEGETABLE_RECIPES[(index - 1) % len(_VEGETABLE_RECIPES)]
        recipe_id = f"mocked:recipe:mealie-vegetable-{index:03d}"
        return {
            "id": recipe_id,
            "label": f"{style} {label}",
            "format": format_text,
            "unit": "portions",
            "ingredients": [
                _mocked_recipe_ingredient(food_id, label, 350, "g"),
                _mocked_recipe_ingredient(*support),
                _mocked_recipe_ingredient(*second_support),
            ],
            "tags": [
                "mpa:component:vegetable",
                f"mpa:component-family:{family}",
                f"mpa:component-detail:{detail}",
            ],
            "categories": ["Mealie demo", "Side"],
        }
    food_id, label, family, detail = _STARCH_RECIPES[(index - 1) % len(_STARCH_RECIPES)]
    recipe_id = f"mocked:recipe:mealie-starch-{index:03d}"
    return {
        "id": recipe_id,
        "label": f"{style} {label}",
        "format": format_text,
        "unit": "portions",
        "ingredients": [
            _mocked_recipe_ingredient(food_id, label, 400, "g"),
            _mocked_recipe_ingredient(*support),
            _mocked_recipe_ingredient(*second_support),
        ],
        "tags": [
            "mpa:component:starch",
            f"mpa:component-family:{family}",
            f"mpa:component-detail:{detail}",
        ],
        "categories": ["Mealie demo", "Side"],
    }


_GENERATED_MEALIE_RECIPES = [_generated_mealie_recipe(index) for index in range(1, 201)]


# Keep the offline provider useful for the prepared-meal workflow too.
MOCKED_RECIPES = [
    {"id": "mocked:recipe:chicken-curry", "label": "Chicken curry", "format": "Batch-friendly curry", "unit": "portions", "ingredients": [{"label": "Chicken thighs", "food_id": "mocked:chicken-thighs"}, {"label": "Coconut milk", "food_id": "mocked:coconut-milk"}, {"label": "Basmati rice", "food_id": "mocked:basmati-rice"}], "tags": ["mpa:component:protein", "mpa:primary-protein:poultry", "mpa:protein-detail:chicken"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:roast-chicken", "label": "Roast chicken", "format": "Portioned roast chicken", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:poultry", "mpa:protein-detail:chicken"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:turkey-meatballs", "label": "Turkey meatballs", "format": "Portioned turkey meatballs", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:poultry", "mpa:protein-detail:turkey"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:beef-stew", "label": "Beef stew", "format": "Portioned braise", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:red-meat", "mpa:protein-detail:beef"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:salmon", "label": "Salmon portions", "format": "Ready fish portions", "unit": "portions", "ingredients": [{"label": "Salmon fillet", "food_id": "mocked:salmon"}, {"label": "Lemons", "food_id": "mocked:lemons"}, {"label": "Extra-virgin olive oil", "food_id": "mocked:olive-oil"}], "tags": ["mpa:component:protein", "mpa:primary-protein:fish", "mpa:protein-detail:salmon"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:lentil-loaf", "label": "Lentil loaf", "format": "Vegetarian protein", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:vegetarian", "mpa:protein-detail:lentil"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:tofu-squares", "label": "Tofu squares", "format": "Ready tofu protein", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:vegetarian", "mpa:protein-detail:tofu"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:roast-vegetables", "label": "Roast vegetables", "format": "Ready vegetable side", "unit": "portions", "tags": ["mpa:component:vegetable", "mpa:component-family:mixed_vegetable", "mpa:component-detail:roast-vegetables"], "categories": ["Side"]},
    {"id": "mocked:recipe:broccoli", "label": "Roasted broccoli", "format": "Ready cruciferous side", "unit": "portions", "tags": ["mpa:component:vegetable", "mpa:component-family:cruciferous", "mpa:component-detail:broccoli"], "categories": ["Side"]},
    {"id": "mocked:recipe:braised-greens", "label": "Braised greens", "format": "Ready leafy greens", "unit": "portions", "tags": ["mpa:component:vegetable", "mpa:component-family:leafy_green", "mpa:component-detail:greens"], "categories": ["Side"]},
    {"id": "mocked:recipe:carrots", "label": "Roasted carrots", "format": "Ready root vegetable side", "unit": "portions", "tags": ["mpa:component:vegetable", "mpa:component-family:root", "mpa:component-detail:carrots"], "categories": ["Side"]},
    {"id": "mocked:recipe:peas", "label": "Buttered peas", "format": "Ready legume vegetable side", "unit": "portions", "tags": ["mpa:component:vegetable", "mpa:component-family:legume", "mpa:component-detail:peas"], "categories": ["Side"]},
    {"id": "mocked:recipe:rice", "label": "Cooked basmati rice", "format": "Ready starch", "unit": "portions", "ingredients": [{"label": "Basmati rice", "food_id": "mocked:basmati-rice"}], "tags": ["mpa:component:starch", "mpa:component-family:rice", "mpa:component-detail:basmati-rice"], "categories": ["Side"]},
    {"id": "mocked:recipe:sweet-potatoes", "label": "Roasted sweet potatoes", "format": "Ready root starch", "unit": "portions", "tags": ["mpa:component:starch", "mpa:component-family:potato", "mpa:component-detail:sweet-potato"], "categories": ["Side"]},
    {"id": "mocked:recipe:noodles", "label": "Sesame noodles", "format": "Ready noodle starch", "unit": "portions", "ingredients": [{"label": "Spaghetti", "food_id": "mocked:spaghetti"}, {"label": "Soy sauce", "food_id": "mocked:soy-sauce"}, {"label": "Peanut butter", "food_id": "mocked:peanut-butter"}], "tags": ["mpa:component:starch", "mpa:component-family:noodle", "mpa:component-detail:sesame-noodles"], "categories": ["Side"]},
    *_GENERATED_MEALIE_RECIPES,
]

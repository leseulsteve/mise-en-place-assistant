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
    {"id": "mocked:fridge", "name": "Fridge", "provider": "mocked", "active": True, "sublocations": ["Top shelf", "Bottom drawer", "Door bin"]},
    {"id": "mocked:freezer", "name": "Freezer", "provider": "mocked", "active": True, "sublocations": ["Top shelf", "Door bin"]},
    {"id": "mocked:pantry", "name": "Pantry", "provider": "mocked", "active": True, "sublocations": ["Dry goods", "Coffee shelf"]},
]

# Keep the offline provider useful for the prepared-meal workflow too.
MOCKED_RECIPES = [
    {"id": "mocked:recipe:chicken-curry", "label": "Chicken curry", "format": "Batch-friendly curry", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:poultry", "mpa:protein-detail:chicken"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:roast-chicken", "label": "Roast chicken", "format": "Portioned roast chicken", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:poultry", "mpa:protein-detail:chicken"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:turkey-meatballs", "label": "Turkey meatballs", "format": "Portioned turkey meatballs", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:poultry", "mpa:protein-detail:turkey"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:beef-stew", "label": "Beef stew", "format": "Portioned braise", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:red-meat", "mpa:protein-detail:beef"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:salmon", "label": "Salmon portions", "format": "Ready fish portions", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:fish", "mpa:protein-detail:salmon"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:lentil-loaf", "label": "Lentil loaf", "format": "Vegetarian protein", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:vegetarian", "mpa:protein-detail:lentil"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:tofu-squares", "label": "Tofu squares", "format": "Ready tofu protein", "unit": "portions", "tags": ["mpa:component:protein", "mpa:primary-protein:vegetarian", "mpa:protein-detail:tofu"], "categories": ["Dinner"]},
    {"id": "mocked:recipe:roast-vegetables", "label": "Roast vegetables", "format": "Ready vegetable side", "unit": "portions", "tags": ["mpa:component:vegetable", "mpa:component-family:mixed_vegetable", "mpa:component-detail:roast-vegetables"], "categories": ["Side"]},
    {"id": "mocked:recipe:broccoli", "label": "Roasted broccoli", "format": "Ready cruciferous side", "unit": "portions", "tags": ["mpa:component:vegetable", "mpa:component-family:cruciferous", "mpa:component-detail:broccoli"], "categories": ["Side"]},
    {"id": "mocked:recipe:braised-greens", "label": "Braised greens", "format": "Ready leafy greens", "unit": "portions", "tags": ["mpa:component:vegetable", "mpa:component-family:leafy_green", "mpa:component-detail:greens"], "categories": ["Side"]},
    {"id": "mocked:recipe:rice", "label": "Cooked basmati rice", "format": "Ready starch", "unit": "portions", "tags": ["mpa:component:starch", "mpa:component-family:rice", "mpa:component-detail:basmati-rice"], "categories": ["Side"]},
    {"id": "mocked:recipe:sweet-potatoes", "label": "Roasted sweet potatoes", "format": "Ready root starch", "unit": "portions", "tags": ["mpa:component:starch", "mpa:component-family:potato", "mpa:component-detail:sweet-potato"], "categories": ["Side"]},
    {"id": "mocked:recipe:noodles", "label": "Sesame noodles", "format": "Ready noodle starch", "unit": "portions", "tags": ["mpa:component:starch", "mpa:component-family:noodle", "mpa:component-detail:sesame-noodles"], "categories": ["Side"]},
]

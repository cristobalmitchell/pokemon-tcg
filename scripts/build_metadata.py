"""Write dataset-metadata.json (Kaggle) with a description of every column of every CSV.

Usage:
    python scripts/build_metadata.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
I, N, S, B = 'integer', 'number', 'string', 'boolean'
MULTI = ' Several values are separated by "|".'
LEGAL = ' True/False for international TCG cards at the time of the build; blank for Pocket and Asian cards.'
MARKET = ' Blank when the source has none.'

COMMON = {
    'card_id': ('Card id: <set_id>-<number> (e.g. "sv03.5-025", "A1-001"). The TCGdex id; joins to cards.csv.', S),
    'set_id': ('Set id (e.g. "base1", "sv03.5", "me06", "A1"). The TCGdex id; joins to sets.csv.', S),
    'deck_id': ('Theme deck id. Joins to decks.csv.', S),
    'national_number': ('National Pokédex number. Joins to The Complete Pokédex Dataset (pokemon_utf8.csv).', I),
    'language': ('Language code: en, fr, de, es, es-mx, it, pt, pt-br, ja, ko, zh-tw, zh-cn, th, id.', S),
    'ptcgio_id': ('Card id on pokemontcg.io / PokemonTCG/pokemon-tcg-data (e.g. "sv3pt5-25"); version 1 of this dataset used it.', S),
    'tcgplayer_product_id': ('TCGplayer product id.' + MARKET, I),
    'cardmarket_product_id': ('Cardmarket product id.' + MARKET, I),
    'cardtrader_id': ('CardTrader blueprint id.' + MARKET, I),
    'source': ('Where the row comes from: "tcgdex" or "pocket-database" (Pokémon TCG Pocket cards TCGdex does not have yet).', S),
}
DOCS = {
    'sets.csv': {
        'name': ('Set name, in English when it exists (e.g. "Base Set", "151", "Genetic Apex").', S),
        'series_id': ('Series id (e.g. "base", "swsh", "sv", "me", "tcgp").', S),
        'series': ('Series / era (e.g. "Base", "Sword & Shield", "Scarlet & Violet", "Pokémon TCG Pocket").', S),
        'region': ('"international" (English and European languages, and Pocket) or "asia" (Japanese, Chinese, Korean, Thai, Indonesian).', S),
        'game': ('"tcg" for the physical card game, "pocket" for the Pokémon TCG Pocket app.', S),
        'languages': ('Languages the set name is recorded in.' + MULTI, S),
        'release_date': ('Release date (YYYY-MM-DD).', S),
        'official_card_count': ('Set size printed on the cards (excludes secret rares).', I),
        'card_count': ('Cards of the set in cards.csv (includes secret rares).', I),
        'abbreviation': ('Official set abbreviation (e.g. "MEW" for 151).', S),
        'tcg_online_code': ('Set code in Pokémon TCG Online / Live.', S),
        'legal_standard': ('Set legal in the Standard format.' + LEGAL, B),
        'legal_expanded': ('Set legal in the Expanded format.' + LEGAL, B),
        'tcgplayer_group_id': ('TCGplayer group (set) id.' + MARKET, I),
        'cardmarket_expansion_id': ('Cardmarket expansion id.' + MARKET, I),
        'ptcgio_set_id': ('Set id on pokemontcg.io (e.g. "sv3pt5"); version 1 of this dataset used it.', S),
        'logo_url': ('URL of the set logo (TCGdex image host).', S),
        'symbol_url': ('URL of the set symbol (TCGdex image host).', S),
    },
    'set_names.csv': {'name': ('Set name in that language.', S)},
    'cards.csv': {
        'set_name': ('Set name.', S),
        'series': ('Series / era of the set.', S),
        'region': ('"international" or "asia" (see sets.csv).', S),
        'game': ('"tcg" or "pocket" (Pokémon TCG Pocket).', S),
        'release_date': ('Release date of the set (YYYY-MM-DD).', S),
        'number': ('Collector number within the set (text: some are like "TG05", "SV001", "GG70").', S),
        'name': ('Card name in text_language (e.g. "Charizard ex", "Professor\'s Research"). Other languages: card_names.csv.', S),
        'text_language': ('Language of name, evolves_from, flavor_text, effect and of the attack and ability text: English when the card has it, else the card\'s own language.', S),
        'supertype': ('Pokémon, Trainer or Energy.', S),
        'stage': ('Pokémon stage: Basic, Stage 1, Stage 2, VMAX, VSTAR, MEGA, BREAK, LEVEL-UP, Baby, V-UNION, RESTORED.', S),
        'suffix': ('Rule-box suffix: ex, EX, GX, TAG TEAM-GX, V, Prime, Legend, SP.', S),
        'trainer_type': ('Trainer cards: Item, Supporter, Tool, Stadium, Technical Machine, Rocket\'s Secret Machine.', S),
        'energy_type': ('Energy cards: Normal (basic Energy) or Special.', S),
        'hp': ('Hit points (Pokémon cards; also Fossils and dolls played as Pokémon).', I),
        'types': ('Energy types of the Pokémon (Grass, Fire, Water, Lightning, Psychic, Fighting, Darkness, Metal, '
                  'Fairy, Dragon, Colorless).' + MULTI, S),
        'primary_type': ('First type of the Pokémon.', S),
        'evolves_from': ('Name of the card it evolves from.', S),
        'evolves_to': ('Names of the cards (same game and language) that evolve from this card\'s name. Derived.' + MULTI, S),
        'attack_count': ('Number of attacks (rows in card_attacks.csv). Blank for the pocket-database cards, which have no attack data.', I),
        'ability_count': ('Number of abilities (rows in card_abilities.csv). Blank for the pocket-database cards.', I),
        'weakness_type': ('Weakness type.' + MULTI, S),
        'weakness_value': ('Weakness modifier (e.g. "×2", "+20").' + MULTI, S),
        'resistance_type': ('Resistance type.' + MULTI, S),
        'resistance_value': ('Resistance modifier (e.g. "-30").' + MULTI, S),
        'retreat_cost': ('Number of Energy needed to retreat.', I),
        'regulation_mark': ('Regulation mark (D, E, F, G, H, I, J) used for Standard rotation.', S),
        'rarity': ('Rarity (e.g. Common, Rare, Illustration rare, Special illustration rare, Hyper rare; Pocket: One Diamond ... Crown).', S),
        'artist': ('Illustrator.', S),
        'flavor_text': ('Pokédex-style flavor text printed on the card.', S),
        'effect': ('Rules text of Trainer and Energy cards.', S),
        'national_numbers': ('National Pokédex numbers of the Pokémon on the card (several for TAG TEAM cards).' + MULTI, S),
        'legal_standard': ('Legal in the Standard format (regulation marks H, I, J).' + LEGAL, B),
        'legal_expanded': ('Legal in the Expanded format (Black & White onwards, minus the ban list).' + LEGAL, B),
        'image_url': ('URL of the high-resolution card image (TCGdex image host; Pocket thumbnails for pocket-database cards). Blank when no image exists.', S),
    },
    'card_names.csv': {'name': ('Card name in that language.', S)},
    'card_attacks.csv': {
        'attack_index': ('Position of the attack on the card (1 = first).', I),
        'name': ('Attack name (in the card\'s text_language).', S),
        'cost': ('Energy symbols in the attack cost.' + MULTI, S),
        'converted_energy_cost': ('Number of Energy symbols in the cost.', I),
        'damage': ('Damage as printed (e.g. "120", "30+", "10×"; blank for no damage).', S),
        'base_damage': ('Numeric part of the damage.', I),
        'damage_modifier': ('+ (can do more), × (multiplied) or - (can do less); blank for fixed damage.', S),
        'text': ('Attack effect text (in the card\'s text_language).', S),
    },
    'card_abilities.csv': {
        'ability_index': ('Position of the ability on the card.', I),
        'name': ('Ability name.', S),
        'type': ('Ability, Poké-Power, Poké-Body, Pokémon Power or Ancient Trait.', S),
        'text': ('Ability text.', S),
    },
    'card_pokemon.csv': {
        'role': ('"featured" for the Pokémon the card is, "cameo" for Pokémon that also appear in the artwork.', S),
    },
    'card_variants.csv': {
        'variant_index': ('Position of the variant in the source.', I),
        'type': ('Finish: normal, holo, reverse (reverse holo), lenticular or metal.', S),
        'subtype': ('Print run, where it matters (e.g. "unlimited", "shadowless").', S),
        'size': ('Card size when not standard (e.g. "jumbo").', S),
        'stamps': ('Stamps on the card (e.g. 1st-edition, set-logo, staff, pre-release, pokemon-center).' + MULTI, S),
        'foil': ('Foil pattern (e.g. "cosmos", "cracked-ice").', S),
        'languages': ('Languages the variant was printed in, where the source restricts it.' + MULTI, S),
    },
    'card_boosters.csv': {
        'booster': ('Booster pack the card can be pulled from (e.g. "Mewtwo", "Charizard" for Genetic Apex).', S),
    },
    'id_crosswalk.csv': {},
    'price_history.csv': {
        'variant': ('Finish the sales are for: normal, reverse or holo.', S),
        'condition': ('Card condition: nearmint, good, played, used or poor.', S),
        'month': ('Month of the sales (YYYY-MM), November 2022 to September 2024.', S),
        'avg_price_usd': ('Sale-weighted average sale price in US dollars.', N),
        'min_price_usd': ('Lowest sale price in the month (USD).', N),
        'max_price_usd': ('Highest sale price in the month (USD).', N),
        'sales': ('Number of sales recorded in the month.', I),
        'days_with_sales': ('Days in the month with at least one recorded sale.', I),
    },
    'pocket_pull_rates.csv': {
        'pack_type': ('"Regular Pack", "Regular Pack +1" (a pack with a bonus sixth card), "Rare Pack" (the rare "god pack") or "Themed Rare Pack".', S),
        'pack_rate_pct': ('Chance of opening this pack type (%).', N),
        'cards_per_pack': ('Cards in the pack (4 in deluxe packs, 5, or 6 with the bonus card).', I),
        'slot': ('Position in the pack (1-6).', I),
        'rarity_code': ('Rarity code: C, U, R, RR, AR, SR, SAR, IM, UR, S, SSR; CF, UF, RF are foil Common, Uncommon and Rare slots in deluxe packs.', S),
        'rarity': ('Rarity as in cards.csv (One Diamond ... Four Diamond, One Star ... Three Star, Crown, One Shiny, Two Shiny).', S),
        'rarity_label': ('Rarity name (Common, Uncommon, Rare, Double Rare, Art Rare, Super Rare, Special Art Rare, Immersive Rare, Crown Rare, Shiny, Shiny Super Rare).', S),
        'rate_pct': ('Chance that this slot holds a card of this rarity (%).', N),
    },
    'decks.csv': {
        'name': ('Theme deck name.', S),
        'types': ('Energy types of the deck.' + MULTI, S),
        'card_count': ('Cards in the deck (normally 60).', I),
    },
    'deck_cards.csv': {
        'card_id': ('TCGdex card id. Joins to cards.csv; blank for the few deck cards with no TCGdex match.', S),
        'card_name': ('Card name.', S),
        'rarity': ('Rarity of the printing in the deck.', S),
        'count': ('Copies in the deck.', I),
    },
}
RESOURCES = {
    'sets.csv': 'One row per set (582): 209 international TCG sets from Base Set (1999) to Delta Reign (November 2026), 27 Pokémon TCG Pocket sets and 346 Asian sets.',
    'set_names.csv': 'Set names in every language the source has.',
    'cards.csv': 'One row per card (44,778): 21,541 international TCG cards, 4,577 Pokémon TCG Pocket cards and 18,660 Asian cards, with stats, rarity, artist, legality, cross-reference ids and image links.',
    'card_names.csv': 'Card names in up to 14 languages.',
    'card_attacks.csv': 'One row per attack: cost, damage (as printed and numeric) and effect text.',
    'card_abilities.csv': 'One row per Ability / Poké-Power / Poké-Body / Ancient Trait on a card.',
    'card_pokemon.csv': 'Bridge from cards to National Pokédex numbers (featured and cameo Pokémon); joins to The Complete Pokédex Dataset.',
    'card_variants.csv': 'One row per printed variant: finish, stamps, foil and its marketplace ids.',
    'card_boosters.csv': 'Which booster packs a card can be pulled from (mostly Pokémon TCG Pocket).',
    'id_crosswalk.csv': 'TCGdex card id to pokemontcg.io, TCGplayer, Cardmarket and CardTrader ids.',
    'price_history.csv': 'Monthly TCGplayer sale prices per card, finish and condition, November 2022 to September 2024 (historical; the source stopped collecting).',
    'pocket_pull_rates.csv': 'Pokémon TCG Pocket pull rates per set, pack type, slot and rarity.',
    'decks.csv': 'One row per theme deck.',
    'deck_cards.csv': 'Card lists of the theme decks.',
}


def main():
    path = ROOT / 'dataset-metadata.json'
    resources = []
    for name, desc in RESOURCES.items():
        cols = list(pd.read_csv(DATA / name, nrows=0).columns)
        fields = []
        for c in cols:
            d = DOCS[name].get(c) or COMMON.get(c)
            if d is None:
                raise SystemExit(f'{name}: column {c} is not documented')
            fields.append({'name': c, 'description': d[0], 'type': d[1]})
        # Kaggle layout: the data files sit at the dataset root
        resources.append({'path': name, 'description': desc, 'schema': {'fields': fields}})
    resources.append({'path': 'tcg.sqlite', 'description': 'All tables in one SQLite database with keys.'})
    meta = {
        'title': 'The Complete Pokémon TCG Dataset',
        'subtitle': '44,778 Pokémon cards 1999–2026: TCG, Pocket & Japanese, with prices',
        'description': (ROOT / 'docs' / 'kaggle_description.md').read_text(),
        'id': 'cristobalmitchell/pokemon-tcg',
        'licenses': [{'name': 'other'}],
        'keywords': ['games', 'card games', 'pokemon', 'tabular', 'beginner', 'data visualization', 'nlp'],
        'expectedUpdateFrequency': 'quarterly',
        'userSpecifiedSources': (
            'Cards and sets: TCGdex (https://github.com/tcgdex/cards-database, MIT). Price history: '
            'tcgdex/price-history (MIT), TCGplayer sales 2022-2024. Pokémon TCG Pocket packs, pull rates and newest '
            'sets: flibustier/pokemon-tcg-pocket-database (MIT). pokemontcg.io ids and theme decks: '
            'PokemonTCG/pokemon-tcg-data. Card names, text and images are © The Pokémon Company, Nintendo, '
            'Creatures and GAME FREAK.'),
        'resources': resources,
    }
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n')
    print(f'{len(resources)} resources, subtitle {len(meta["subtitle"])} chars')


if __name__ == '__main__':
    main()

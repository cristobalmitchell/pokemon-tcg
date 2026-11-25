"""Integrity checks for The Complete Pokémon TCG Dataset. Run before every Kaggle upload:

    python scripts/validate.py
"""

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
ENERGY = {'Colorless', 'Darkness', 'Dragon', 'Fairy', 'Fighting', 'Fire', 'Grass', 'Lightning', 'Metal',
          'Psychic', 'Water'}
SOURCE_QUIRKS = {'Void'}  # one Japanese attack cost in TCGdex (M1L-023), kept as published
failures = []


def check(ok, message):
    if not ok:
        failures.append(message)


def read(name):
    return pd.read_csv(DATA / f'{name}.csv', low_memory=False)


def refs(df, col, parent, name):
    check(df[col].dropna().isin(parent).all(), f'{name}: unknown {col}')


def main():
    t = {p.stem: read(p.stem) for p in sorted(DATA.glob('*.csv'))}
    sets, cards, attacks, abilities = t['sets'], t['cards'], t['card_attacks'], t['card_abilities']

    # sets
    check(sets.set_id.is_unique and sets.name.notna().all(), 'sets: set_id not unique or name missing')
    check(pd.to_datetime(sets.release_date, errors='coerce').notna().all(), 'sets: bad release_date')
    check((sets.card_count == cards.groupby('set_id').size().reindex(sets.set_id).fillna(0).values).all(),
          'sets: card_count disagrees with cards')
    check(sets.region.isin(['international', 'asia']).all() and sets.game.isin(['tcg', 'pocket']).all(),
          'sets: unknown region or game')

    # cards
    check(cards.card_id.is_unique, 'cards: card_id not unique')
    refs(cards, 'set_id', sets.set_id, 'cards')
    check(cards[['set_name', 'series', 'release_date', 'name', 'text_language']].notna().all().all(),
          'cards: a set, name or language column is empty')
    check(cards.supertype.isin(['Pokémon', 'Trainer', 'Energy']).all(), 'cards: unknown supertype')
    poke = cards[cards.supertype == 'Pokémon']
    check(poke.hp.isna().sum() <= 1, 'cards: Pokémon cards without HP')  # one Japanese promo has none
    check(poke.hp.dropna().between(10, 400).all(), 'cards: Pokémon card with odd HP')
    # Trainer cards can have HP (Fossils and dolls are played as Pokémon); Energy cards cannot.
    check(cards[cards.supertype == 'Energy'].hp.isna().all(), 'cards: HP on an Energy card')
    types = set(cards.types.dropna().str.split('|').explode())
    check(types <= ENERGY, f'cards: unknown type {types - ENERGY}')
    check(cards.regulation_mark.dropna().str.fullmatch(r'[A-Z]').all(), 'cards: bad regulation_mark')
    intl_tcg = (cards.region == 'international') & (cards.game == 'tcg')
    for col in ('legal_standard', 'legal_expanded'):
        check(cards.loc[intl_tcg, col].notna().all() and cards.loc[~intl_tcg, col].isna().all(),
              f'cards: {col} should be set exactly for international TCG cards')
    counted = cards.attack_count.notna()
    check((cards.loc[counted, 'attack_count']
           == attacks.groupby('card_id').size().reindex(cards.loc[counted, 'card_id']).fillna(0).values).all(),
          'cards: attack_count disagrees with card_attacks')
    check((cards.loc[counted, 'ability_count']
           == abilities.groupby('card_id').size().reindex(cards.loc[counted, 'card_id']).fillna(0).values).all(),
          'cards: ability_count disagrees with card_abilities')
    check(cards.loc[cards.source == 'pocket-database', 'attack_count'].isna().all(),
          'cards: pocket-database cards should have a blank attack_count')
    check(cards.ptcgio_id.dropna().is_unique, 'cards: ptcgio_id not unique')
    check(cards.image_url.dropna().str.startswith('https://').all(), 'cards: bad image_url')
    check(intl_tcg[cards.ptcgio_id.notna()].all(), 'cards: ptcgio_id on a non-international card')

    # child tables
    for name in ('card_names', 'card_attacks', 'card_abilities', 'card_pokemon', 'card_variants', 'card_boosters',
                 'id_crosswalk', 'price_history'):
        refs(t[name], 'card_id', cards.card_id, name)
    refs(t['set_names'], 'set_id', sets.set_id, 'set_names')
    refs(t['pocket_pull_rates'], 'set_id', sets.set_id, 'pocket_pull_rates')
    check(t['card_names'].groupby('card_id').size().reindex(cards.card_id).notna().all(),
          'card_names: a card has no names')
    check(not attacks.duplicated(['card_id', 'attack_index']).any(), 'card_attacks: duplicate attack_index')
    costs = set(attacks.cost.dropna().str.split('|').explode())
    check(costs <= ENERGY | SOURCE_QUIRKS, f'card_attacks: unknown energy {costs - ENERGY - SOURCE_QUIRKS}')
    priced = attacks[attacks.cost.notna()]
    check((priced.cost.str.split('|').map(len) == priced.converted_energy_cost).all(),
          'card_attacks: converted_energy_cost != number of energy symbols')
    check(attacks.base_damage.dropna().between(0, 2000).all(), 'card_attacks: base_damage out of range')
    pokemon = t['card_pokemon']
    check(pokemon.national_number.between(1, 1025).all(), 'card_pokemon: national_number outside 1..1025')
    check(not pokemon.duplicated().any() and pokemon.role.isin(['featured', 'cameo']).all(),
          'card_pokemon: duplicate rows or unknown role')
    variants = t['card_variants']
    check(not variants.duplicated(['card_id', 'variant_index']).any(), 'card_variants: duplicate variant_index')
    check(variants.type.isin(['normal', 'holo', 'reverse', 'lenticular', 'metal']).all(),
          'card_variants: unknown type')
    xw = t['id_crosswalk']
    check(xw.card_id.is_unique and xw.ptcgio_id.dropna().is_unique, 'id_crosswalk: duplicate ids')
    check((xw.set_index('card_id').ptcgio_id.reindex(cards.card_id).fillna('')
           == cards.set_index('card_id').ptcgio_id.fillna('')).all(), 'id_crosswalk: ptcgio_id disagrees with cards')

    # prices
    prices = t['price_history']
    check(not prices.duplicated(['card_id', 'variant', 'condition', 'month']).any(), 'price_history: duplicate rows')
    check(prices.variant.isin(['normal', 'reverse', 'holo']).all(), 'price_history: unknown variant')
    check(prices.condition.isin(['nearmint', 'good', 'played', 'used', 'poor']).all(),
          'price_history: unknown condition')
    check(((prices.min_price_usd <= prices.max_price_usd) & (prices.min_price_usd > 0)).all(),
          'price_history: min > max or non-positive price')
    check(prices.avg_price_usd.dropna().between(0.01, 100_000).all(), 'price_history: implausible price')
    check(prices.month.str.fullmatch(r'20(22|23|24)-\d\d').all(), 'price_history: month outside 2022-2024')

    # Pocket
    pulls = t['pocket_pull_rates']
    check(pulls.rarity.notna().all() and pulls.rarity_label.notna().all(), 'pocket_pull_rates: unmapped rarity')
    slot_total = pulls.groupby(['set_id', 'pack_type', 'slot']).rate_pct.sum()
    check(slot_total.between(99, 101).all(), f'pocket_pull_rates: {(~slot_total.between(99, 101)).sum()} slots '
                                             'whose rates do not sum to 100%')
    pocket_rarities = set(cards.loc[cards.game == 'pocket', 'rarity'].dropna())
    check(set(pulls.rarity) <= pocket_rarities, 'pocket_pull_rates: rarity not used by any Pocket card')

    # decks
    decks, deck_cards = t['decks'], t['deck_cards']
    check(decks.deck_id.is_unique, 'decks: duplicate deck_id')
    refs(decks, 'set_id', sets.set_id, 'decks')
    refs(deck_cards, 'deck_id', decks.deck_id, 'deck_cards')
    refs(deck_cards, 'card_id', cards.card_id, 'deck_cards')
    check(deck_cards.card_id.notna().mean() > 0.98, 'deck_cards: too many cards without a TCGdex match')
    check((decks.card_count == deck_cards.groupby('deck_id')['count'].sum().reindex(decks.deck_id).values).all(),
          'decks: card_count disagrees with deck_cards')

    # SQLite mirrors the CSVs
    con = sqlite3.connect(DATA / 'tcg.sqlite')
    for name, df in t.items():
        n = con.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
        check(n == len(df), f'tcg.sqlite: {name} has {n} rows, CSV has {len(df)}')
    fk = con.execute('PRAGMA foreign_key_check').fetchall()
    check(not fk, f'tcg.sqlite: {len(fk)} foreign key violations')
    con.close()

    # Kaggle metadata documents every column, in order
    meta = json.loads((ROOT / 'dataset-metadata.json').read_text())
    check(6 <= len(meta['title']) <= 50 and 20 <= len(meta['subtitle']) <= 80, 'metadata: title/subtitle length')
    documented = {r['path']: [f['name'] for f in r.get('schema', {}).get('fields', [])] for r in meta['resources']}
    for p in sorted(DATA.glob('*.csv')):
        cols = list(pd.read_csv(p, nrows=0).columns)
        check(documented.get(p.name) == cols, f'metadata: {p.name} columns not documented in order')

    if failures:
        print(f'FAILED {len(failures)} check(s):')
        for f in failures:
            print('  -', f)
        sys.exit(1)
    print(f'OK: {len(sets)} sets, {len(cards):,} cards, {len(attacks):,} attacks, {len(abilities):,} abilities, '
          f'{len(variants):,} variants, {len(prices):,} monthly prices, {len(t["card_names"]):,} names, '
          f'{len(decks)} decks')


if __name__ == '__main__':
    main()

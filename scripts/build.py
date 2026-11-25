"""Build The Complete Pokémon TCG Dataset (v2) from TCGdex and four companion sources.

    data/sets.csv              one row per set (expansion), international, Asian and Pokémon TCG Pocket
    data/set_names.csv         one row per set and language
    data/cards.csv             one row per card
    data/card_names.csv        one row per card and language
    data/card_attacks.csv      one row per attack on a card
    data/card_abilities.csv    one row per ability (Ability, Poké-Power, Poké-Body, Ancient Trait, ...) on a card
    data/card_pokemon.csv      card -> National Pokédex number (joins to The Complete Pokédex Dataset)
    data/card_variants.csv     one row per printed variant (normal, reverse holo, 1st edition, stamped, ...)
    data/card_boosters.csv     card -> booster pack it can be pulled from
    data/id_crosswalk.csv      TCGdex id <-> pokemontcg.io id <-> TCGplayer / Cardmarket / CardTrader ids
    data/price_history.csv     monthly TCGplayer sale prices, Nov 2022 - Sep 2024 (historical)
    data/pocket_pull_rates.csv Pokémon TCG Pocket pull rates per pack slot and rarity
    data/decks.csv             one row per theme deck
    data/deck_cards.csv        one row per card line in a theme deck
    data/tcg.sqlite            all of the above in one SQLite database

Sources (clone each; scripts/fetch_sources.sh does it):
    cards-database    https://github.com/tcgdex/cards-database             MIT   cards, sets, variants, ids
    datas.json        https://assets.tcgdex.net/datas.json                       index of the card images that exist
    pokemon-tcg-data  https://github.com/PokemonTCG/pokemon-tcg-data             pokemontcg.io ids, theme decks
    price-history     https://github.com/tcgdex/price-history              MIT   TCGplayer sales history
    pocket-database   https://github.com/flibustier/pokemon-tcg-pocket-database  MIT   Pocket packs and pull rates

Usage:
    bash scripts/fetch_sources.sh            # clones into .cache/
    python scripts/build.py .cache
"""

import json
import re
import unicodedata
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
SEP = '|'  # separator for multi-valued cells (types, energy costs, stamps, ...)
ASSETS = 'https://assets.tcgdex.net'

# Language preference for the text columns. International cards use English when it exists.
INTL_LANGS = ['en', 'fr', 'de', 'es', 'it', 'pt', 'es-mx', 'pt-br', 'ko', 'ja']
ASIA_LANGS = ['ja', 'zh-tw', 'zh-cn', 'ko', 'th', 'id', 'en']


# ---------------------------------------------------------------------------------------------
# Reading TCGdex: every card, set and series is a TypeScript file holding one object literal.
# They are plain data, so a small tokenizer turns them into JSON without needing Node.
# ---------------------------------------------------------------------------------------------
TOKEN = re.compile(r'''
    (?P<dq>"(?:[^"\\\n]|\\.)*")
  | (?P<sq>'(?:[^'\\\n]|\\.)*')
  | (?P<lc>//[^\n]*)
  | (?P<bc>/\*.*?\*/)
  | (?P<id>[A-Za-z_$][\w$]*)(?P<colon>\s*:)?
''', re.X | re.S)


def _token(m):
    if m.group('dq'):
        return m.group('dq').replace("\\'", "'")
    if m.group('sq'):
        body = m.group('sq')[1:-1].replace("\\'", "'")
        return '"' + re.sub(r'(?<!\\)"', r'\\"', body) + '"'
    if m.group('lc') or m.group('bc'):
        return ''
    word = m.group('id')
    if m.group('colon'):
        return f'"{word}":'
    # References to imported objects (set: Set, serie: Serie) become null; the folder layout gives them.
    return word if word in ('true', 'false', 'null') else 'null'


def ts_object(src):
    body = TOKEN.sub(_token, src)
    body = re.sub(r'"\s*\+\s*"', '', body)       # "a" + "b" -> "ab"
    body = re.sub(r',(\s*[}\]])', r'\1', body)   # trailing commas
    return json.loads(body, strict=False)        # a few strings hold literal tabs


def read_ts(path):
    src = Path(path).read_text(encoding='utf-8')
    return ts_object(src[src.index('= {') + 2:src.rindex('}') + 1])


def read_legals(path):
    """meta/legals.ts holds `export const standard: Filter = {...}` and the same for expanded."""
    src = Path(path).read_text(encoding='utf-8')
    out = {}
    for m in re.finditer(r'export const (\w+)\s*:\s*\w+\s*=\s*\{', src):
        depth, i = 0, m.end() - 1
        for j in range(i, len(src)):
            depth += {'{': 1, '}': -1}.get(src[j], 0)
            if depth == 0:
                out[m.group(1)] = ts_object(src[i:j + 1])
                break
    return out


def pick(texts, order):
    """First available (language, text) from a {lang: text} dict, in order of preference."""
    if not isinstance(texts, dict) or not texts:
        return None, None
    for lang in order:
        if texts.get(lang):
            return lang, texts[lang]
    lang = next(iter(texts))
    return lang, texts[lang]


def joined(values):
    values = [str(v) for v in values or [] if v is not None]
    return SEP.join(values) if values else None


def number_key(local):
    """'001' -> '1', 'TG01' -> 'tg1', 'SWSH050' -> 'swsh50': normalise card numbers across sources."""
    return re.sub(r'(?<![0-9])0+(?=[0-9])', '', str(local).lower())


def damage_parts(text):
    """'120+' -> (120, '+'); '30×' -> (30, '×'); '' -> (None, None)."""
    m = re.match(r'^(\d+)\s*([+×x\-]?)$', (str(text) if text is not None else '').strip())
    if not m:
        return None, None
    return int(m.group(1)), (m.group(2).replace('x', '×') or None)


def stamp_slug(stamp):
    """'1st Edition' / '1st edition' / '1st-edition' -> '1st-edition'."""
    return re.sub(r'[\s_]+', '-', str(stamp).strip().lower())


def regulation_mark(mark):
    """A single letter; the source has a lowercase 'j' and two 'none' strings."""
    mark = str(mark or '').strip().upper()
    return mark if re.fullmatch(r'[A-Z]', mark) else None


def as_int(v):
    return int(v) if str(v).strip().isdigit() else None


# ---------------------------------------------------------------------------------------------
# TCGdex -> sets and cards
# ---------------------------------------------------------------------------------------------
def load_tcgdex(src):
    sets, cards = [], []
    for region, folder in (('international', 'data'), ('asia', 'data-asia')):
        for serie_file in sorted((src / folder).glob('*.ts')):
            serie = read_ts(serie_file)
            for set_file in sorted(serie_file.with_suffix('').glob('*.ts')):
                s = read_ts(set_file)
                s.update(_region=region, _serie=serie, _stem=set_file.stem)
                sets.append(s)
                for card_file in sorted(set_file.with_suffix('').glob('*.ts')):
                    c = read_ts(card_file)
                    c.update(_local=card_file.stem, _set=s)
                    cards.append(c)
    return sets, cards


def assign_set_ids(sets):
    """TCGdex ids are unique per language, not globally. Four Japanese Neo sets and a Japanese promo
    reuse an international id: they get an '-asia' suffix (neo1 -> neo1-asia). A few Asian sets
    share an id with a sibling set: they take their file name instead (AC3b, AS5b, CBB1C, ...)."""
    intl = {s['id'] for s in sets if s['_region'] == 'international'}
    asia = Counter(s['id'] for s in sets if s['_region'] == 'asia')
    for s in sets:
        sid = s['id']
        if s['_region'] == 'asia':
            if sid in intl:
                sid = f'{sid}-asia'
            elif asia[sid] > 1 and s['_stem'] != sid:
                sid = s['_stem']
        s['_id'] = sid
    ids = Counter(s['_id'] for s in sets)
    assert not [k for k, n in ids.items() if n > 1], [k for k, n in ids.items() if n > 1]


def release_date(s, lang):
    d = s.get('releaseDate')
    return pick(d, [lang] + INTL_LANGS + ASIA_LANGS)[1] if isinstance(d, dict) else d


def is_legal(rules, fmt, serie_id, set_id, local, card=None):
    """Mirror of TCGdex's cardIsLegal / setIsLegal (server/compiler/utils/util.ts)."""
    rule = rules[fmt]
    inc, exc = rule['includes'], rule['excludes']
    if card is None:
        return (serie_id in inc['series'] or set_id in inc['sets']) and set_id not in exc['sets']
    if (serie_id in inc['series'] or set_id in inc['sets'] or card.get('energyType') == 'Normal'
            or (card.get('regulationMark') and card['regulationMark'] in inc['regulationMark'])):
        return not (set_id in exc['sets'] or (fmt == 'standard' and 'Fairy' in (card.get('types') or []))
                    or f'{set_id}-{local}' in exc['cards'])
    return False


def image_url(index, langs, serie_id, set_id, local):
    for lang in langs:
        if index.get(lang, {}).get(serie_id, {}).get(set_id, {}).get(local):
            return f'{ASSETS}/{lang}/{serie_id}/{set_id}/{local}/high.png'
    return None


def build_sets(sets, cards, rules, index):
    per_set = Counter(c['_set']['_id'] for c in cards)
    rows, names = [], []
    for s in sets:
        order = INTL_LANGS if s['_region'] == 'international' else ASIA_LANGS
        lang, name = pick(s['name'], order)
        serie_id = s['_serie']['id']
        game = 'pocket' if serie_id == 'tcgp' else 'tcg'
        intl_tcg = s['_region'] == 'international' and game == 'tcg'
        logo = next((f'{ASSETS}/{l}/{serie_id}/{s["id"]}/logo.png' for l in [lang] + order
                     if index.get(l, {}).get(serie_id, {}).get(s['id'], {}).get('logo')), None)
        symbol = index.get('univ', {}).get(serie_id, {}).get(s['id'], {}).get('symbol')
        rows.append({
            'set_id': s['_id'],
            'name': name,
            'series_id': serie_id,
            'series': pick(s['_serie']['name'], [lang] + order)[1],
            'region': s['_region'],
            'game': game,
            'languages': joined(sorted(s['name'])),
            'release_date': release_date(s, lang),
            'official_card_count': (s.get('cardCount') or {}).get('official'),
            'card_count': per_set.get(s['_id'], 0),
            'abbreviation': (s.get('abbreviations') or {}).get('official'),
            'tcg_online_code': s.get('tcgOnline'),
            'legal_standard': is_legal(rules, 'standard', serie_id, s['id'], None) if intl_tcg else None,
            'legal_expanded': is_legal(rules, 'expanded', serie_id, s['id'], None) if intl_tcg else None,
            'tcgplayer_group_id': (s.get('thirdParty') or {}).get('tcgplayer'),
            'cardmarket_expansion_id': (s.get('thirdParty') or {}).get('cardmarket'),
            'ptcgio_set_id': None,  # filled by the crosswalk
            'logo_url': logo,
            'symbol_url': f'{ASSETS}/univ/{serie_id}/{s["id"]}/symbol.png' if symbol else None,
        })
        names += [{'set_id': s['_id'], 'language': l, 'name': n} for l, n in s['name'].items() if n]
    df = pd.DataFrame(rows)
    for col in ('official_card_count', 'tcgplayer_group_id', 'cardmarket_expansion_id'):
        df[col] = df[col].astype('Int64')
    for col in ('legal_standard', 'legal_expanded'):
        df[col] = df[col].astype('boolean')
    df = df.sort_values(['region', 'game', 'release_date', 'set_id'], ascending=[False, False, True, True])
    return df.reset_index(drop=True), pd.DataFrame(names)


ABILITY_TYPES = {'Poke-BODY': 'Poké-Body', 'Poke-POWER': 'Poké-Power', 'Pokemon Power': 'Pokémon Power'}
STAGES = {'Stage1': 'Stage 1', 'Stage2': 'Stage 2'}


def build_cards(cards, rules, index):
    rows, names, attacks, abilities, pokemon, variants, boosters, market = [], [], [], [], [], [], [], []
    for c in cards:
        s, local = c['_set'], c['_local']
        serie_id = s['_serie']['id']
        set_id = s['_id']
        card_id = f'{set_id}-{local}'
        region = s['_region']
        pocket = serie_id == 'tcgp'
        order = INTL_LANGS if region == 'international' else ASIA_LANGS
        lang, name = pick(c['name'], order)
        texts = [lang] + order

        def text(d):
            return pick(d, texts)[1]

        weak, res = c.get('weaknesses') or [], c.get('resistances') or []
        types = c.get('types') or []
        intl_tcg = region == 'international' and not pocket
        img_langs = [lang] + [l for l in order if l in c['name']] + order
        rows.append({
            'card_id': card_id,
            'set_id': set_id,
            'set_name': pick(s['name'], texts)[1],
            'series': pick(s['_serie']['name'], texts)[1],
            'region': region,
            'game': 'pocket' if pocket else 'tcg',
            'release_date': release_date(s, lang),
            'number': local,
            'name': name,
            'text_language': lang,
            'supertype': {'Pokemon': 'Pokémon'}.get(c.get('category'), c.get('category')),
            'stage': STAGES.get(c.get('stage'), c.get('stage')),
            'suffix': c.get('suffix'),
            'trainer_type': c.get('trainerType'),
            'energy_type': c.get('energyType'),
            'hp': as_int(c.get('hp')) or None,  # a few Energy cards carry HP 0 in the source
            'types': joined(types),
            'primary_type': types[0] if types else None,
            'evolves_from': text(c.get('evolveFrom')),
            'evolves_to': None,  # filled in main() once every card is known
            'attack_count': len(c.get('attacks') or []),
            'ability_count': len(c.get('abilities') or []),
            'weakness_type': joined([w.get('type') for w in weak]),
            'weakness_value': joined([w.get('value') for w in weak]),
            'resistance_type': joined([r.get('type') for r in res]),
            'resistance_value': joined([r.get('value') for r in res]),
            'retreat_cost': as_int(c.get('retreat')),
            'regulation_mark': regulation_mark(c.get('regulationMark')),
            'rarity': c.get('rarity'),
            'artist': c.get('illustrator'),
            'flavor_text': text(c.get('description')),
            'effect': text(c.get('effect')),
            'national_numbers': joined(c.get('dexId')),
            'legal_standard': is_legal(rules, 'standard', serie_id, s['id'], local, c) if intl_tcg else None,
            'legal_expanded': is_legal(rules, 'expanded', serie_id, s['id'], local, c) if intl_tcg else None,
            'ptcgio_id': None,  # filled by the crosswalk
            'image_url': image_url(index, img_langs, serie_id, s['id'], local),
        })
        names += [{'card_id': card_id, 'language': l, 'name': n} for l, n in c['name'].items() if n]
        for i, a in enumerate(c.get('attacks') or [], 1):
            cost = a.get('cost') or []
            dmg, mod = damage_parts(a.get('damage'))
            attacks.append({
                'card_id': card_id, 'attack_index': i, 'name': text(a.get('name')), 'cost': joined(cost),
                'converted_energy_cost': len([e for e in cost if e != 'Free']),
                'damage': str(a['damage']) if a.get('damage') not in (None, '') else None,
                'base_damage': dmg, 'damage_modifier': mod, 'text': text(a.get('effect')),
            })
        for i, a in enumerate(c.get('abilities') or [], 1):
            abilities.append({'card_id': card_id, 'ability_index': i, 'name': text(a.get('name')),
                              'type': ABILITY_TYPES.get(a.get('type'), a.get('type')), 'text': text(a.get('effect'))})
        pokemon += [{'card_id': card_id, 'national_number': n, 'role': 'featured'} for n in c.get('dexId') or []]
        pokemon += [{'card_id': card_id, 'national_number': n, 'role': 'cameo'} for n in c.get('cameoDexIds') or []]

        v = c.get('variants')
        if isinstance(v, dict):
            v = [{'type': k} for k, on in v.items() if on]
        for i, x in enumerate(v or [], 1):
            tp = x.get('thirdParty') or {}
            stamp = x.get('stamp')
            variants.append({
                'card_id': card_id, 'variant_index': i, 'type': x.get('type'), 'subtype': x.get('subtype'),
                'size': x.get('size'), 'stamps': joined(stamp_slug(t) for t in (stamp if isinstance(stamp, list) else [stamp]) if t),
                'foil': x.get('foil'), 'languages': joined(x.get('languages')),
                'tcgplayer_product_id': tp.get('tcgplayer'), 'cardmarket_product_id': tp.get('cardmarket'),
                'cardtrader_id': tp.get('cardtrader'),
            })
        # Marketplace ids for the crosswalk: the card's own, else its first variant that has them.
        tp = c.get('thirdParty') or next((x.get('thirdParty') for x in v or [] if x.get('thirdParty')), {}) or {}
        market.append({'card_id': card_id, 'tcgplayer_product_id': tp.get('tcgplayer'),
                       'cardmarket_product_id': tp.get('cardmarket'), 'cardtrader_id': tp.get('cardtrader')})
        for key in c.get('boosters') or []:
            b = (s.get('boosters') or {}).get(key) or {}
            boosters.append({'card_id': card_id, 'booster': pick(b.get('name'), INTL_LANGS)[1] or key,
                             'source': 'tcgdex'})

    cards_df = pd.DataFrame(rows)
    for col in ('hp', 'retreat_cost'):
        cards_df[col] = cards_df[col].astype('Int64')
    for col in ('legal_standard', 'legal_expanded'):
        cards_df[col] = cards_df[col].astype('boolean')
    attacks = pd.DataFrame(attacks)
    attacks['base_damage'] = attacks['base_damage'].astype('Int64')
    variants = pd.DataFrame(variants)
    market = pd.DataFrame(market)
    for df in (variants, market):
        for col in ('tcgplayer_product_id', 'cardmarket_product_id', 'cardtrader_id'):
            df[col] = df[col].astype('Int64')
    return (cards_df, pd.DataFrame(names), attacks, pd.DataFrame(abilities),
            pd.DataFrame(pokemon).drop_duplicates(), variants, pd.DataFrame(boosters), market)


def sort_cards(cards, sets):
    order = sets[['set_id']].reset_index().rename(columns={'index': '_s'})
    cards = cards.merge(order, on='set_id')
    cards['_n'] = cards.number.str.extract(r'(\d+)', expand=False).astype(float)
    return cards.sort_values(['_s', '_n', 'number']).drop(columns=['_s', '_n']).reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# pokemontcg.io (pokemon-tcg-data) crosswalk and theme decks
# ---------------------------------------------------------------------------------------------
def norm_set_id(sid):
    """TCGdex 'sv03.5' / 'me05' -> pokemontcg.io style 'sv3pt5' / 'me5'."""
    return re.sub(r'(?<=[a-z])0+(?=\d)', '', sid.lower().replace('.', 'pt'))


def norm_name(name):
    name = str(name).replace('♀', ' f').replace('♂', ' m').replace('★', ' star').replace('Imposter', 'Impostor')
    name = unicodedata.normalize('NFKD', name)
    return re.sub(r'[^a-z0-9]', '', ''.join(ch for ch in name if not unicodedata.combining(ch)).lower().replace('&', 'and'))


def same_card(a, b):
    """Names agree once naming conventions are set aside: 'Darkrai LV.X' = 'Darkrai',
    'Basic Fire Energy' = 'Fire Energy', "Boss's Orders (Giovanni)" = "Boss's Orders"."""
    def clean(n):
        n = re.sub(r'\s*\(.*?\)\s*$', '', str(n))
        n = re.sub(r'^basic\s+', '', n, flags=re.I)
        return norm_name(re.sub(r'\s+lv\.?\s*x$', '', n, flags=re.I))
    return clean(a) == clean(b) or norm_name(a) == norm_name(b)


# pokemontcg.io set ids that differ from TCGdex's beyond the 'sv03.5' -> 'sv3pt5' pattern.
PTCGIO_SET_ALIASES = {'swsh45sv': 'swsh4.5sv', 'cel25c': 'cel25cc', 'zsv10pt5': 'sv10.5b', 'rsv10pt5': 'sv10.5w',
                      'fut20': 'fut2020', 'me55c': '30th-c'}


def crosswalk(ptcgio, sets, cards):
    p_sets = json.loads((ptcgio / 'sets' / 'en.json').read_text())
    p_cards = []
    for path in sorted((ptcgio / 'cards' / 'en').glob('*.json')):
        p_cards += json.loads(path.read_text())
    intl = sets[(sets.region == 'international') & (sets.game == 'tcg')]
    by_norm = {norm_set_id(s): s for s in intl.set_id}
    by_name = defaultdict(list)
    for s in intl.itertuples():
        by_name[(norm_name(s.name), s.release_date)].append(s.set_id)
        by_name[(norm_name(s.name), None)].append(s.set_id)

    set_map = {}
    for p in p_sets:
        pid = p['id']
        target = PTCGIO_SET_ALIASES.get(pid) or by_norm.get(pid.lower())
        if target is None:
            date = p['releaseDate'].replace('/', '-')
            hits = by_name.get((norm_name(p['name']), date)) or by_name.get((norm_name(p['name']), None)) or []
            target = hits[0] if len(hits) == 1 else None
        set_map[pid] = target

    key = {(r.set_id, number_key(r.number)): r.card_id for r in cards[cards.region == 'international'].itertuples()}
    name_of = dict(zip(cards.card_id, cards.name))
    # Fallback for sets numbered differently (the Classic Collections reuse the original card numbers
    # on pokemontcg.io): a name that occurs once in the TCGdex set identifies the card.
    by_name_in_set = defaultdict(list)
    for r in cards[cards.region == 'international'].itertuples():
        by_name_in_set[(r.set_id, norm_name(r.name))].append(r.card_id)
    rows, outcome = [], Counter()
    for c in p_cards:
        pset, suffix = c['id'].rsplit('-', 1)
        tset = set_map.get(pset)
        cid, why = None, 'set not in TCGdex' if tset is None else 'number not in TCGdex'
        # the id suffix is the printed number; the number field disagrees with it on a few cards
        for number in dict.fromkeys([suffix, c['number']]):
            hit = key.get((tset, number_key(number)))
            if hit and same_card(name_of[hit], c['name']):
                cid = hit
                break
            if hit:
                why = 'name differs'
        if cid is None and tset:
            same = by_name_in_set.get((tset, norm_name(c['name'])), [])
            if len(same) == 1:
                cid = same[0]
        outcome['matched' if cid else why] += 1
        rows.append({'ptcgio_id': c['id'], 'card_id': cid, 'ptcgio_set_id': pset, 'name': c['name']})
    return set_map, pd.DataFrame(rows), outcome


def build_decks(ptcgio, links, set_map):
    to_tcgdex = dict(zip(links.ptcgio_id, links.card_id))
    deck_rows, lines = [], []
    for path in sorted((ptcgio / 'decks' / 'en').glob('*.json')):
        for d in json.loads(path.read_text()):
            pset = d['id'][2:].rsplit('-', 1)[0]
            deck_rows.append({'deck_id': d['id'], 'name': d['name'], 'types': joined(d.get('types')),
                              'set_id': set_map.get(pset), 'card_count': sum(c['count'] for c in d['cards'])})
            for c in d['cards']:
                lines.append({'deck_id': d['id'], 'card_id': to_tcgdex.get(c['id']), 'ptcgio_id': c['id'],
                              'card_name': c['name'], 'rarity': c.get('rarity'), 'count': c['count']})
    return pd.DataFrame(deck_rows), pd.DataFrame(lines)


# ---------------------------------------------------------------------------------------------
# Prices (tcgdex/price-history) and Pocket packs (flibustier/pokemon-tcg-pocket-database)
# ---------------------------------------------------------------------------------------------
def build_prices(prices, cards):
    ids = {(r.set_id, number_key(r.number)): r.card_id for r in cards[cards.region == 'international'].itertuples()}
    acc = defaultdict(lambda: [0, 0.0, 0, None, None])  # sales, weighted sum, days, min, max
    missing = set()
    for path in sorted((prices / 'en').glob('*/*.tcgplayer.json')):
        local = path.name.split('.')[0]
        card_id = ids.get((path.parent.name, number_key(local)))
        if card_id is None:
            missing.add(f'{path.parent.name}-{local}')
            continue
        for key, block in (json.loads(path.read_text()).get('data') or {}).items():
            variant, _, condition = key.rpartition('-')
            for day, p in (block.get('history') or {}).items():
                a = acc[(card_id, variant, condition, day[:7])]
                n = p.get('count') or 0
                lo, hi = p.get('min', p['avg']), p.get('max', p['avg'])
                a[0] += n
                a[1] += p['avg'] * n
                a[2] += 1
                a[3] = lo if a[3] is None else min(a[3], lo)
                a[4] = hi if a[4] is None else max(a[4], hi)
    rows = [{'card_id': k[0], 'variant': k[1], 'condition': k[2], 'month': k[3],
             'avg_price_usd': round(a[1] / a[0] / 100, 2) if a[0] else None,
             'min_price_usd': a[3] / 100, 'max_price_usd': a[4] / 100, 'sales': a[0], 'days_with_sales': a[2]}
            for k, a in acc.items()]
    df = pd.DataFrame(rows).sort_values(['card_id', 'variant', 'condition', 'month']).reset_index(drop=True)
    return df, sorted(missing)


POCKET_COUNT = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four'}
POCKET_LANGS = {'pt': 'pt-br', 'zh': 'zh-tw'}  # the Pocket database's language codes -> TCGdex's
# Thumbnails published by the Pocket database's author (one per card, checked Nov 2026).
POCKET_IMAGES = 'https://raw.githubusercontent.com/flibustier/pokemon-tcg-exchange/main/public/images/thumbnails'


def pocket_set_id(code):
    return re.sub(r'^PROMO-', 'P-', code)  # 'PROMO-A' -> TCGdex's 'P-A'


def pocket_rarity(code, rarities):
    """Pocket database codes -> TCGdex rarity names: 'C' -> 'One Diamond', 'SAR' -> 'Two Star', 'UR' -> 'Crown'.
    Foil slots in deluxe packs use the base code plus 'F' ('CF' = foil Common)."""
    if code not in rarities and code.endswith('F') and code[:-1] in rarities:
        code = code[:-1]
    r = rarities.get(code) or {}
    group, count = r.get('group'), r.get('count')
    if group in ('Diamond', 'Star', 'Shiny') and count in POCKET_COUNT:
        return f'{POCKET_COUNT[count]} {group}'
    return group or r.get('label')


def pocket_label(code, rarities):
    if code not in rarities and code.endswith('F') and code[:-1] in rarities:
        return f"{rarities[code[:-1]]['label']} (foil)"
    return (rarities.get(code) or {}).get('label')


def pocket_supplement(pocket, sets, cards):
    """TCGdex trails the Pokémon TCG Pocket release schedule. Add the Pocket sets and cards it does
    not have yet from the Pocket database. That source has no attack or ability text, so those
    columns are left empty (attack_count is null, not 0) for these cards."""
    dist = pocket / 'dist'
    rarities = json.loads((dist / 'rarities.json').read_text())
    known_sets = set(sets.set_id)
    new_sets, set_names = [], []
    for group in json.loads((dist / 'sets.json').read_text()).values():
        for x in group:
            sid = pocket_set_id(x['code'])
            if sid in known_sets:
                continue
            names = {POCKET_LANGS.get(l, l): n for l, n in (x.get('name') or {}).items() if n}
            new_sets.append({'set_id': sid, 'name': names.get('en') or x['code'], 'series_id': 'tcgp',
                             'series': 'Pokémon TCG Pocket', 'region': 'international', 'game': 'pocket',
                             'languages': joined(sorted(names)), 'release_date': x.get('releaseDate'),
                             'official_card_count': x.get('count'), 'source': 'pocket-database'})
            set_names += [{'set_id': sid, 'language': l, 'name': n} for l, n in names.items()]

    translations = defaultdict(dict)
    for path in dist.glob('cards.*.json'):
        lang = path.name.split('.')[1]
        if len(lang) == 2 and lang != 'en':
            for c in json.loads(path.read_text()):
                translations[(c['set'], c['number'])][POCKET_LANGS.get(lang, lang)] = c['name']

    have = {(r.set_id, number_key(r.number)) for r in cards[cards.game == 'pocket'].itertuples()}
    rows, names = [], []
    for c in json.loads((dist / 'cards.extra.json').read_text()):
        sid, number = pocket_set_id(c['set']), f"{int(c['number']):03d}"
        if (sid, number_key(number)) in have:
            continue
        kind = (c.get('type') or '').lower()
        pokemon = kind == 'pokemon'
        card_id = f'{sid}-{number}'
        rows.append({
            'card_id': card_id, 'set_id': sid, 'number': number, 'name': c['name'], 'text_language': 'en',
            'region': 'international', 'game': 'pocket',
            'supertype': 'Pokémon' if pokemon else 'Trainer',
            'stage': {'basic': 'Basic', 1: 'Stage 1', 2: 'Stage 2'}.get(c.get('stage')) if pokemon else None,
            'trainer_type': None if pokemon else {'fossil': 'Item'}.get(kind, kind.title() or None),
            'hp': c.get('health'), 'types': (c.get('element') or '').title() or None,
            'primary_type': (c.get('element') or '').title() or None, 'evolves_from': c.get('evolvesFrom'),
            'weakness_type': (c.get('weakness') or '').title() or None,
            'weakness_value': '+20' if c.get('weakness') else None, 'retreat_cost': c.get('retreatCost'),
            'rarity': pocket_rarity(c.get('rarity'), rarities),
            'image_url': f"{POCKET_IMAGES}/{c['set']}/{c['number']}.webp",
            'source': 'pocket-database',
        })
        names.append({'card_id': card_id, 'language': 'en', 'name': c['name']})
        names += [{'card_id': card_id, 'language': l, 'name': n}
                  for l, n in translations.get((c['set'], c['number']), {}).items() if n]
    return pd.DataFrame(new_sets), pd.DataFrame(set_names), pd.DataFrame(rows), pd.DataFrame(names)


def build_pocket(pocket, cards, boosters):
    dist = pocket / 'dist'
    rarities = json.loads((dist / 'rarities.json').read_text())
    pulls = json.loads((dist / 'pullRates.json').read_text())
    rows = []
    for code, packs in pulls.items():
        for pack_type, p in packs.items():
            for slot, rates in (p.get('slots') or {}).items():
                for rcode, pct in rates.items():
                    rows.append({'set_id': pocket_set_id(code), 'pack_type': pack_type,
                                 'pack_rate_pct': p.get('appearance_rate'), 'cards_per_pack': p.get('cards'),
                                 'slot': int(slot), 'rarity_code': rcode, 'rarity': pocket_rarity(rcode, rarities),
                                 'rarity_label': pocket_label(rcode, rarities), 'rate_pct': pct})
    pull_rates = pd.DataFrame(rows)

    # Packs per card: TCGdex lists them for some Pocket cards; the Pocket database lists them for all.
    have = set(boosters.card_id) if len(boosters) else set()
    key = {(r.set_id, number_key(r.number)): r.card_id for r in cards[cards.game == 'pocket'].itertuples()}
    extra = []
    for c in json.loads((dist / 'cards.json').read_text()):
        cid = key.get((pocket_set_id(c['set']), number_key(c['number'])))
        if cid and cid not in have:
            extra += [{'card_id': cid, 'booster': pack, 'source': 'pocket-database'} for pack in c.get('packs') or []]
    boosters = pd.concat([boosters, pd.DataFrame(extra)], ignore_index=True).drop_duplicates(['card_id', 'booster'])
    return pull_rates, boosters.reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------------------------
PK = {'sets': 'set_id', 'cards': 'card_id', 'decks': 'deck_id', 'id_crosswalk': 'card_id'}
FK = {'cards': [('set_id', 'sets')], 'set_names': [('set_id', 'sets')], 'card_names': [('card_id', 'cards')],
      'card_attacks': [('card_id', 'cards')], 'card_abilities': [('card_id', 'cards')],
      'card_pokemon': [('card_id', 'cards')], 'card_variants': [('card_id', 'cards')],
      'card_boosters': [('card_id', 'cards')], 'id_crosswalk': [('card_id', 'cards')],
      'price_history': [('card_id', 'cards')], 'pocket_pull_rates': [('set_id', 'sets')],
      'decks': [('set_id', 'sets')], 'deck_cards': [('deck_id', 'decks')]}
INDEXES = ['cards(set_id)', 'card_names(card_id)', 'card_attacks(card_id)', 'card_abilities(card_id)',
           'card_pokemon(card_id)', 'card_pokemon(national_number)', 'card_variants(card_id)',
           'card_boosters(card_id)', 'id_crosswalk(ptcgio_id)', 'price_history(card_id)', 'deck_cards(card_id)']


def write_sqlite(tables):
    path = DATA / 'tcg.sqlite'
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    for name, df in tables.items():
        cols = []
        for c in df.columns:
            dt = df[c].dtype
            t = ('INTEGER' if pd.api.types.is_integer_dtype(dt) or pd.api.types.is_bool_dtype(dt)
                 else 'REAL' if pd.api.types.is_float_dtype(dt) else 'TEXT')
            cols.append(f'"{c}" {t}' + (' PRIMARY KEY' if PK.get(name) == c else ''))
        for col, ref in FK.get(name, []):
            cols.append(f'FOREIGN KEY ("{col}") REFERENCES {ref}("{col}")')
        con.execute(f'CREATE TABLE {name} ({", ".join(cols)})')
        values = df.astype(object).where(df.notna(), None)
        con.executemany(f'INSERT INTO {name} VALUES ({", ".join("?" * len(df.columns))})',
                        values.itertuples(index=False, name=None))
    for i, spec in enumerate(INDEXES):
        con.execute(f'CREATE INDEX ix_{i} ON {spec}')
    con.commit()
    con.execute('VACUUM')
    con.close()


def main(cache):
    cache = Path(cache)
    src, ptcgio, pocket = cache / 'cards-database', cache / 'pokemon-tcg-data', cache / 'pokemon-tcg-pocket-database'
    rules = read_legals(src / 'meta' / 'legals.ts')
    index = json.loads((cache / 'datas.json').read_text())

    raw_sets, raw_cards = load_tcgdex(src)
    assign_set_ids(raw_sets)
    sets, set_names = build_sets(raw_sets, raw_cards, rules, index)
    cards, card_names, attacks, abilities, pokemon, variants, boosters, market = build_cards(raw_cards, rules, index)
    sets['source'] = cards['source'] = 'tcgdex'

    p_sets, p_set_names, p_cards, p_card_names = pocket_supplement(pocket, sets, cards)
    print(f'Pocket database adds {len(p_sets)} sets and {len(p_cards)} cards TCGdex does not have yet')
    sets = pd.concat([sets, p_sets], ignore_index=True)
    set_names = pd.concat([set_names, p_set_names], ignore_index=True)
    cards = pd.concat([cards, p_cards.reindex(columns=cards.columns)], ignore_index=True)
    card_names = pd.concat([card_names, p_card_names], ignore_index=True)
    for col, dtype in [('hp', 'Int64'), ('retreat_cost', 'Int64'), ('attack_count', 'Int64'), ('ability_count', 'Int64'),
                       ('official_card_count', 'Int64'), ('card_count', 'Int64')]:
        for df in (cards, sets):
            if col in df:
                df[col] = df[col].astype(dtype)
    sets['card_count'] = sets.set_id.map(cards.set_id.value_counts()).fillna(0).astype('Int64')
    info = sets.set_index('set_id')
    for col, src_col in (('set_name', 'name'), ('series', 'series'), ('release_date', 'release_date')):
        cards[col] = cards[col].fillna(cards.set_id.map(info[src_col]))
    # evolves_to: invert evolves_from by name, within one game and text language
    evo = (cards.dropna(subset=['evolves_from']).groupby(['game', 'text_language', 'evolves_from']).name
           .agg(lambda names: SEP.join(sorted(set(names)))))
    cards['evolves_to'] = [evo.get((g, l, n)) for g, l, n in zip(cards.game, cards.text_language, cards.name)]
    for df in (sets, cards):
        for col in ('legal_standard', 'legal_expanded'):
            df[col] = df[col].astype('boolean')
    sets = sets.sort_values(['region', 'game', 'release_date', 'set_id'],
                            ascending=[False, False, True, True]).reset_index(drop=True)
    cards = sort_cards(cards, sets)

    set_map, links, outcome = crosswalk(ptcgio, sets, cards)
    print('pokemontcg.io sets without a TCGdex match:', sorted(k for k, v in set_map.items() if v is None))
    print('pokemontcg.io cards:', dict(outcome))
    ptcgio_of = links.dropna(subset=['card_id']).drop_duplicates('card_id').set_index('card_id').ptcgio_id
    cards['ptcgio_id'] = cards.card_id.map(ptcgio_of)
    first_ptcgio_set = {}
    for pid, sid in set_map.items():
        first_ptcgio_set.setdefault(sid, pid)
    sets['ptcgio_set_id'] = sets.set_id.map(first_ptcgio_set)
    id_crosswalk = cards[['card_id', 'ptcgio_id']].merge(market, on='card_id', how='left')
    id_crosswalk = id_crosswalk[id_crosswalk.drop(columns='card_id').notna().any(axis=1)].reset_index(drop=True)

    decks, deck_cards = build_decks(ptcgio, links, set_map)
    prices, missing = build_prices(cache / 'price-history', cards)
    print(f'price history: {len(prices):,} rows; {len(missing)} files without a TCGdex card: {missing[:8]}')
    pull_rates, boosters = build_pocket(pocket, cards, boosters)
    unknown = sorted(set(pull_rates.set_id) - set(sets.set_id))
    assert not unknown, unknown

    tables = {'sets': sets, 'set_names': set_names, 'cards': cards, 'card_names': card_names,
              'card_attacks': attacks, 'card_abilities': abilities, 'card_pokemon': pokemon,
              'card_variants': variants, 'card_boosters': boosters, 'id_crosswalk': id_crosswalk,
              'price_history': prices, 'pocket_pull_rates': pull_rates, 'decks': decks, 'deck_cards': deck_cards}
    DATA.mkdir(exist_ok=True)
    for name, df in tables.items():
        df.to_csv(DATA / f'{name}.csv', index=False)
    write_sqlite(tables)
    print(', '.join(f'{k} {v.shape}' for k, v in tables.items()))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.cache')

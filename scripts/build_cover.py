"""Render dataset-cover-image.png (1280 x 640), the Kaggle cover of The Complete Pokémon TCG Dataset.

Same visual system as The Complete Pokédex Dataset cover (navy gradient, title, accent underline),
with the dataset's headline finding as the hero: median attack damage per Energy by release year.
No card images are used.

Usage (needs Pillow and matplotlib):
    python scripts/build_cover.py
"""

import io
from pathlib import Path

import matplotlib
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W, H = 1280, 640
TOP, BOTTOM = (12, 14, 30), (29, 19, 53)                 # navy gradient, as on the Pokédex cover
INK, SUBTLE, ACCENT = (255, 255, 255), (220, 224, 235), (57, 135, 229)
SERIES = '#338ced'       # validated on this surface (dark mode, contrast >= 3:1)
MUTED = '#9c9fb8'        # axis text on navy
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def gradient():
    col = Image.new('RGB', (1, H))
    for y in range(H):
        t = y / (H - 1)
        col.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)))
    return col.resize((W, H)).convert('RGBA')


def card_grid(base, cw=54, ch=75, gap=18, alpha=11):
    """Faint outlines of trading cards (63 x 88 mm proportions) as texture."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for row, y in enumerate(range(-ch // 2, H, ch + gap)):
        for x in range(-cw + (row % 2) * (cw + gap) // 2, W, cw + gap):
            d.rounded_rectangle((x, y, x + cw, y + ch), radius=6, outline=(255, 255, 255, alpha), width=2)
    base.alpha_composite(layer)


def damage_per_energy():
    cards = pd.read_csv(ROOT / 'data' / 'cards.csv', low_memory=False)
    attacks = pd.read_csv(ROOT / 'data' / 'card_attacks.csv')
    a = attacks.merge(cards[['card_id', 'release_date']], on='card_id')
    a = a[(a.converted_energy_cost > 0) & a.base_damage.notna()]
    year = a.release_date.str[:4].astype(int)
    return (a.base_damage / a.converted_energy_cost).groupby(year).median()


def chart(series, width=1120, height=250):
    """Transparent line chart: one series, recessive baseline, labelled endpoints."""
    dpi = 100
    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_axes([0.02, 0.16, 0.96, 0.66])
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    x, y = series.index.values, series.values
    ax.fill_between(x, 0, y, color=SERIES, alpha=0.16, linewidth=0)
    ax.plot(x, y, color=SERIES, linewidth=3, solid_capstyle='round')
    for xi, yi in ((x[0], y[0]), (x[-1], y[-1])):
        ax.plot([xi], [yi], 'o', ms=9, color=SERIES, mec='#1a1533', mew=2.5)
    ax.annotate(f'{y[0]:.0f} damage per Energy', (x[0], y[0]), xytext=(4, 14), textcoords='offset points',
                color='#dce0eb', fontsize=15, fontweight='bold')
    ax.annotate(f'{y[-1]:.0f}', (x[-1], y[-1]), xytext=(-8, 14), textcoords='offset points', ha='right',
                color='#dce0eb', fontsize=15, fontweight='bold')
    ax.set_xlim(x[0] - 0.4, x[-1] + 0.4)
    ax.set_ylim(0, max(y) * 1.25)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.spines['bottom'].set_color('#3a3560')
    ax.set_yticks([])
    ticks = [t for t in (1999, 2005, 2010, 2015, 2020, 2026) if x[0] <= t <= x[-1]]
    ax.set_xticks(ticks)
    ax.tick_params(axis='x', colors=MUTED, labelsize=13, length=0, pad=6)
    fig.text(0.02, 0.92, 'Median attack damage per Energy, by release year', color=MUTED, fontsize=13)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', transparent=True, dpi=dpi)
    plt.close(fig)
    return Image.open(io.BytesIO(buf.getvalue())).convert('RGBA')


def fit_font(path, text, width, start):
    size = start
    while size > 10 and ImageFont.truetype(path, size).getlength(text) > width:
        size -= 2
    return ImageFont.truetype(path, size)


def main():
    cards = pd.read_csv(ROOT / 'data' / 'cards.csv', low_memory=False, usecols=['card_id', 'release_date'])
    sets = pd.read_csv(ROOT / 'data' / 'sets.csv')
    first, last = cards.release_date.min()[:4], cards.release_date.max()[:4]
    subtitle = f'{len(cards):,} cards  ·  {len(sets)} sets  ·  {first}–{last}  ·  attacks & decks'

    im = gradient()
    card_grid(im)
    im.alpha_composite(chart(damage_per_energy()), (80, 370))
    d = ImageDraw.Draw(im)
    title = fit_font(BOLD, 'The Complete Pokémon', 1130, 96)
    for text, y in (('The Complete Pokémon', 52), ('TCG Dataset', 142)):
        d.text(((W - title.getlength(text)) / 2, y), text, font=title, fill=INK)
    w = title.getlength('TCG Dataset')
    d.rounded_rectangle(((W - w) / 2 + 40, 234, (W + w) / 2 - 40, 240), radius=3, fill=ACCENT)
    sub = fit_font(REGULAR, subtitle, 1080, 36)
    d.text(((W - sub.getlength(subtitle)) / 2, 268), subtitle, font=sub, fill=SUBTLE)
    im.convert('RGB').save(ROOT / 'dataset-cover-image.png', optimize=True)
    print('dataset-cover-image.png:', subtitle)


if __name__ == '__main__':
    main()

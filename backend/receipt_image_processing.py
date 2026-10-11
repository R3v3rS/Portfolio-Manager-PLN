"""Bounded, local image preparation and reconstruction of receipt rows."""
import math
from statistics import median


def reconstruct_text(result):
    pages = result.get('pages') or []
    texts = []
    for page in pages:
        words = page.get('words') or []
        angle = float(page.get('angle') or 0)
        slope = math.tan(math.radians(angle)) if abs(angle) < 15 else 0

        def center(word):
            return word['y']+word['height']/2-slope*(word['x']+word['width']/2)

        rows = []
        for word in sorted(words, key=center):
            row = next((r for r in reversed(rows[-3:]) if abs(center(word)-median(center(w) for w in r))
                        < .72*min(word['height'], median(w['height'] for w in r))), None)
            if row is None:
                rows.append([word])
            else:
                row.append(word)
        texts.append('\n'.join(' '.join(w['text'] for w in sorted(row, key=lambda w: w['x'])) for row in rows))
    return '\n'.join(texts) if texts else str(result.get('text') or '')


def prepare_images(path, folder):
    from PIL import Image, ImageFilter, ImageOps

    with Image.open(path) as source:
        if source.width*source.height > 25_000_000:
            raise ValueError('Receipt image is too large to prepare safely')
        image = ImageOps.exif_transpose(source).convert('RGB')
    variants = []
    for edge, stretch, mode in ((1600, 1, 'color'), (1200, 1.5, 'color'),
                                 (1600, 1.5, 'color'), (1600, 2, 'gray'), (1600, 1.5, 'flat')):
        small = image.copy()
        small.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        if mode != 'color':
            small = ImageOps.grayscale(small)
            if mode == 'flat':
                background = small.filter(ImageFilter.GaussianBlur(25))
                small = Image.frombytes('L', small.size, bytes(min(255, round(p*235/max(b, 20)))
                    for p, b in zip(small.tobytes(), background.tobytes())))
            small = ImageOps.autocontrast(small, cutoff=1)
        if stretch != 1:
            small = small.resize((round(small.width*stretch), small.height), Image.Resampling.LANCZOS)
        target = folder/f'{len(variants)}.png'
        small.save(target)
        variants.append(target)
    return variants


def recognition_score(text):
    from budget_import_parser import parse_receipt

    parsed, warnings = parse_receipt(text)
    amount = parsed['amount']
    lines = parsed['lines']
    balanced = bool(amount and lines and sum(round(p['amount']*100) for p in lines) == round(amount*100))
    return (amount is not None, balanced, bool(parsed['date']), bool(parsed['merchant']), len(lines), -len(warnings))

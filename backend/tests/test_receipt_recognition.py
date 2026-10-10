import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from budget_import_parser import parse_receipt
from receipt_image_processing import prepare_images, recognition_score, reconstruct_text
from receipt_ocr_service import extract


# Observed OCR rows from a photographed Polish receipt, without customer details.
DINO_TEXT = '''Dino Polska SA.
PARAGON FISKALNY
REKLAHOUKA 351 A 1 xo.65 0,65A
BULKA 806 C 6 6.84C
SER TARTY goz 5006 C 1 13.99C
SER CAMEMBERT 1206 C 1 x3,99 3.99C
JOG GREC MLEK C 1 „2.99 2.99C
CHORIZO EXTR IOOG C 1 *8.49 8.49€--
PIUO HIL HATC O.SC C x3.49 3,49C
SPRZEDA? OPODATKOWANA A 0.65
SPRZEDA? C 39.79
PTU 0.12
PTU 1.89
PTU 2.01
SUMA PLN 40,44
OPAKOUANIA ZUROTNE
DO ZAPŁATY 41.44 PLN
INNA Karta Pł. 41.44 PLN
2026-10-03 19:33'''


class ReceiptRecognitionTest(unittest.TestCase):
    def test_real_ocr_rows_preserve_eight_amounts_including_deposit(self):
        data, warnings = parse_receipt(DINO_TEXT)
        self.assertEqual((data['merchant'], data['date'], data['amount']), ('Dino Polska SA.', '2026-10-03', 41.44))
        self.assertEqual([line['amount'] for line in data['lines']], [.65, 6.84, 13.99, 3.99, 2.99, 8.49, 3.49, 1])
        self.assertEqual(data['lines'][4]['label'], 'JOG GREC MLEK')
        self.assertIn('kaucji', warnings[0])

    def test_explicit_deposit_and_split_total_are_not_counted_twice(self):
        data, warnings = parse_receipt('Dino\nPARAGON FISKALNY\nChleb C 1 x5,00 5,00C\nSUMA PLN\n5,00\nKAUCJA 1 x1,00 1,00\nOPAKOWANIA ZWROTNE SUMA 1,00\nDO ZAPŁATY PLN\n6,00\n2026-10-03')
        self.assertEqual(data['amount'], 6)
        self.assertEqual([p['amount'] for p in data['lines']], [5, 1])
        self.assertEqual(warnings, [])

    def test_capacity_and_unit_price_without_line_total_are_not_expenses(self):
        data, warnings = parse_receipt('Dino\nPARAGON FISKALNY\nPIWO 0,5L C\nBUŁKA 80G C 6 x1,14\nDO ZAPŁATY 10,00\n2026-10-03')
        self.assertEqual(data['lines'], [])
        self.assertTrue(warnings)

    def test_conflicting_payment_totals_require_manual_review(self):
        data, warnings = parse_receipt('Dino\nDO ZAPŁATY 10,00\nDO ZAPŁATY 12,00\n2026-10-03')
        self.assertIsNone(data['amount'])
        self.assertTrue(any('różne kwoty' in w for w in warnings))

    def test_address_is_not_a_merchant_and_tax_totals_are_not_purchase_totals(self):
        data, _ = parse_receipt('ul. Kamienna 15, 66-100 Sulechów\nNIP 1234567890\nPTU 0,12\nSUMA PTU 2,01')
        self.assertEqual(data['merchant'], '')
        self.assertIsNone(data['amount'])
        self.assertEqual(data['lines'], [])

    def test_column_blocks_are_reconstructed_into_rows_without_merging_products(self):
        def word(text, x, y):
            return dict(text=text, x=x, y=y, width=80, height=20)
        result = {'pages': [{'words': [word('Chleb', 0, 0), word('Mleko', 0, 35), word('5,00C', 300, 2), word('2,99C', 300, 36)], 'angle': 0}]}
        self.assertEqual(reconstruct_text(result), 'Chleb 5,00C\nMleko 2,99C')
        result['pages'].append(result['pages'][0])
        self.assertEqual(reconstruct_text(result).count('Chleb 5,00C'), 2)

    def test_preparing_variants_respects_orientation_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); photo = folder/'original.jpg'
            image = Image.new('RGB', (120, 80), 'white')
            exif = image.getexif(); exif[274] = 6
            image.save(photo, exif=exif)
            before = hashlib.sha256(photo.read_bytes()).hexdigest()
            variants = prepare_images(photo, folder)
            with Image.open(variants[0]) as first:
                self.assertEqual(first.size, (80, 120))
            self.assertEqual(hashlib.sha256(photo.read_bytes()).hexdigest(), before)
            self.assertEqual(len(variants), 5)

    def test_complete_readout_is_preferred_to_a_fragment(self):
        self.assertGreater(recognition_score(DINO_TEXT), recognition_score('Dino\nPIWO 0.51 C'))

    def test_one_failed_variant_does_not_discard_a_successful_readout(self):
        with patch('receipt_ocr_service.available', return_value=True), \
             patch('receipt_ocr_service.prepare_images', return_value=[Path('one.png'), Path('two.png')]), \
             patch('receipt_ocr_service.subprocess.run', side_effect=[subprocess.TimeoutExpired('ocr', 1),
                 subprocess.CompletedProcess('ocr', 0, json.dumps({'text': DINO_TEXT}), '')]):
            text, warnings = extract(Path('photo.jpg'))
            self.assertEqual(text, DINO_TEXT)
            self.assertEqual(warnings, [])


if __name__ == '__main__':
    unittest.main()

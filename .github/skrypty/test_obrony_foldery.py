"""Testy skryptu obrony_foldery.py (na tymczasowym repozytorium git).  python3 .github/skrypty/test_obrony_foldery.py"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from obrony_foldery import FOLDER, WPISY, folder_osoby, uporzadkuj  # noqa: E402

WPIS = '''---
kandydat: {kandydat}
tytul_rozprawy: Tytuł
zawiadomienie: {zaw}
rozprawa: "https://im-uwr.github.io/Obrony-Archiwum/2026-01-01-x/doktorat.pdf"
recenzje:
  - recenzent: prof. A
    plik: "{rec}"
    pozycja: false
---
Treść z linkiem [plik](/pliki/aktualnosci/obrony/inny.pdf).
'''


def git(kat, *a):
    return subprocess.run(['git', *a], cwd=kat, check=True, capture_output=True, text=True).stdout.strip()


class Obrony(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kat = self.tmp.name
        git(self.kat, 'init', '-q')
        git(self.kat, 'config', 'user.email', 't@t')
        git(self.kat, 'config', 'user.name', 't')
        git(self.kat, 'config', 'core.autocrlf', 'false')
        os.makedirs(os.path.join(self.kat, WPISY))
        os.makedirs(os.path.join(self.kat, FOLDER))

    def tearDown(self):
        self.tmp.cleanup()

    def plik(self, rel, tresc=b'%PDF'):
        p = os.path.join(self.kat, FOLDER, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as f:
            f.write(tresc)

    def wpis(self, nazwa, **pola):
        with open(os.path.join(self.kat, WPISY, nazwa), 'w', encoding='utf-8', newline='') as f:
            f.write(WPIS.format(**pola))

    def czytaj(self, nazwa):
        return open(os.path.join(self.kat, WPISY, nazwa), encoding='utf-8').read()

    def jest(self, rel):
        return os.path.isfile(os.path.join(self.kat, FOLDER, rel))

    def zatwierdz(self):
        git(self.kat, 'add', '-A')
        git(self.kat, 'commit', '-q', '-m', 'x')
        return git(self.kat, 'rev-parse', 'HEAD')

    def test_nazwa_folderu(self):
        self.assertEqual(folder_osoby('Malwina Mrowińska'), 'MalwinaMrowinska')
        self.assertEqual(folder_osoby('Łukasz Wojciechowski'), 'LukaszWojciechowski')
        self.assertEqual(folder_osoby('Adrián Portillo-Fernández'), 'AdrianPortillo-Fernandez')

    def test_nowa_obrona_pliki_do_folderu(self):
        self.plik('zawiadomienie.pdf')
        self.plik('recenzja-a.pdf')
        self.wpis('2026-12-01-jan-nowak.md', kandydat='Jan Nowak', zaw='/pliki/aktualnosci/obrony/zawiadomienie.pdf',
                  rec='/pliki/aktualnosci/obrony/recenzja-a.pdf')
        zmiany = uporzadkuj(self.kat)
        self.assertEqual(len(zmiany), 2)
        t = self.czytaj('2026-12-01-jan-nowak.md')
        self.assertIn('zawiadomienie: /pliki/aktualnosci/obrony/JanNowak/zawiadomienie.pdf\n', t)
        self.assertIn('    plik: "/pliki/aktualnosci/obrony/JanNowak/recenzja-a.pdf"\n', t)
        self.assertIn('Obrony-Archiwum/2026-01-01-x/doktorat.pdf', t)  # adres spoza Media bez zmian
        self.assertIn('(/pliki/aktualnosci/obrony/inny.pdf)', t)  # treść wpisu bez zmian
        self.assertTrue(self.jest('JanNowak/zawiadomienie.pdf'))
        self.assertFalse(self.jest('zawiadomienie.pdf'))
        self.assertEqual(uporzadkuj(self.kat), [])  # drugi przebieg nic nie zmienia

    def test_zmiana_nazwiska_i_usuniecie(self):
        self.plik('JanNowak/zaw.pdf')
        self.plik('JanNowak/rec.pdf')
        self.wpis('a.md', kandydat='Jan Nowak', zaw='/pliki/aktualnosci/obrony/JanNowak/zaw.pdf',
                  rec='/pliki/aktualnosci/obrony/JanNowak/rec.pdf')
        przed = self.zatwierdz()
        self.wpis('a.md', kandydat='"Jan Nowak-Kowalski"', zaw='/pliki/aktualnosci/obrony/JanNowak/zaw.pdf',
                  rec='/pliki/aktualnosci/obrony/JanNowak/rec.pdf')
        uporzadkuj(self.kat)
        self.assertTrue(self.jest('JanNowak-Kowalski/zaw.pdf'))
        self.assertFalse(os.path.isdir(os.path.join(self.kat, FOLDER, 'JanNowak')))
        przed = self.zatwierdz()
        os.remove(os.path.join(self.kat, WPISY, 'a.md'))
        self.plik('AnnaZ/zostaje.pdf')  # folder bez obrony, ale nieusuwanej w tej zmianie: zostaje
        self.zatwierdz()
        zmiany = uporzadkuj(self.kat, przed)
        self.assertEqual(len(zmiany), 1)
        self.assertFalse(os.path.isdir(os.path.join(self.kat, FOLDER, 'JanNowak-Kowalski')))
        self.assertTrue(self.jest('AnnaZ/zostaje.pdf'))

    def test_plik_wspolny_i_zajeta_nazwa(self):
        self.plik('wspolny.pdf', b'A')
        self.plik('JanNowak/wspolny.pdf', b'B')  # inna treść pod tą samą nazwą
        self.wpis('a.md', kandydat='Jan Nowak', zaw='/pliki/aktualnosci/obrony/wspolny.pdf', rec='/pliki/aktualnosci/obrony/brak.pdf')
        self.wpis('b.md', kandydat='Ewa Lis', zaw='/pliki/aktualnosci/obrony/wspolny.pdf', rec='/pliki/aktualnosci/obrony/brak.pdf')
        uporzadkuj(self.kat)
        self.assertIn('/pliki/aktualnosci/obrony/JanNowak/wspolny-1.pdf', self.czytaj('a.md'))
        self.assertIn('/pliki/aktualnosci/obrony/EwaLis/wspolny.pdf', self.czytaj('b.md'))
        self.assertTrue(self.jest('JanNowak/wspolny.pdf') and self.jest('JanNowak/wspolny-1.pdf') and self.jest('EwaLis/wspolny.pdf'))
        self.assertFalse(self.jest('wspolny.pdf'))
        self.assertIn('/pliki/aktualnosci/obrony/brak.pdf', self.czytaj('a.md'))  # brak pliku: adres bez zmian


if __name__ == '__main__':
    unittest.main()

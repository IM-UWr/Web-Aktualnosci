"""Pliki obron doktorskich w folderach ImieNazwisko: Media → obrony → MalwinaMrowinska.

Uruchamiany przez .github/workflows/obrony-pliki.yml po każdej zmianie obron na main.
- Pages CMS wgrywa pliki z formularza obrony zawsze do public/pliki/aktualnosci/obrony/ (folder pola jest stały).
  Skrypt przenosi każdy plik wskazany we wpisie (zawiadomienie, rozprawa, streszczenia, recenzje) do
  obrony/<ImieNazwisko kandydata>/ i poprawia adres we wpisie. Plik używany też przez inną obronę jest kopiowany.
- Po zmianie imienia lub nazwiska kandydata pliki przechodzą do nowego folderu.
- Usunięcie obrony (wpis usunięty między <sha przed> a HEAD) usuwa jej folder, chyba że inna obrona go używa.
  Usunięte pliki zostają w historii repozytorium.
- Adresy spoza Media (np. https://im-uwr.github.io/Obrony-Archiwum/…) zostają bez zmian.

Uruchomienie:  python3 .github/skrypty/obrony_foldery.py [<sha przed zmianą>]   (bez sha: bez usuwania folderów)
Test:          python3 .github/skrypty/test_obrony_foldery.py
"""
import filecmp
import os
import re
import shutil
import subprocess
import sys
import unicodedata

WPISY = 'src/content/obrony'
FOLDER = 'public/pliki/aktualnosci/obrony'
ADRES = '/pliki/aktualnosci/obrony/'
FRONT = re.compile(r'^---\r?\n(.*?\r?\n)---', re.S)
KANDYDAT = re.compile(r'^kandydat:[ \t]*(["\']?)(.*?)\1[ \t]*\r?$', re.M)
POLE = re.compile(r'^([ \t]*(?:-[ \t]+)?(?:zawiadomienie|rozprawa|streszczenie_pl|streszczenie_en|plik):[ \t]*)(["\']?)'
                  + re.escape(ADRES) + r'([^"\'\r\n]+?)\2([ \t]*\r?)$', re.M)


def folder_osoby(kandydat):
    """„Malwina Mrowińska” → „MalwinaMrowinska”; „Maria Kamińska-Zabierowska” → „MariaKaminska-Zabierowska”."""
    t = unicodedata.normalize('NFKD', kandydat.replace('ł', 'l').replace('Ł', 'L'))
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'[^A-Za-z0-9-]+', '', t)


def osoba(tekst):
    front = FRONT.match(tekst)
    m = front and KANDYDAT.search(front.group(1))
    return folder_osoby(m.group(2)) if m else ''


def czytaj(p):
    with open(p, encoding='utf-8', newline='') as f:
        return f.read()


def wolna_nazwa(korzen, folder, nazwa, zrodlo):
    """Nazwa w folderze docelowym: ta sama, gdy wolna albo z tym samym plikiem; inaczej z -1, -2…"""
    baza, roz = os.path.splitext(nazwa)
    kandydaci = [nazwa] + [f'{baza}-{i}{roz}' for i in range(1, 100)]
    for k in kandydaci:
        cel = os.path.join(korzen, FOLDER, folder, k)
        if not os.path.exists(cel) or filecmp.cmp(zrodlo, cel, shallow=False):
            return k
    raise SystemExit(f'Za dużo plików {nazwa} w {folder}')


def uporzadkuj(korzen, przed=None):
    """Przenosi pliki i usuwa foldery usuniętych obron; zwraca listę zmian (zdania do dziennika)."""
    zmiany = []
    katalog = os.path.join(korzen, WPISY)
    wpisy = {n: czytaj(os.path.join(katalog, n)) for n in sorted(os.listdir(katalog)) if n.endswith('.md')} \
        if os.path.isdir(katalog) else {}
    uzycia = {}  # plik względem obrony/ -> zbiór wpisów
    for n, t in wpisy.items():
        front = FRONT.match(t)
        for m in POLE.finditer(front.group(1) if front else ''):
            uzycia.setdefault(m.group(3), set()).add(n)

    for n, t in wpisy.items():
        folder = osoba(t)
        front = FRONT.match(t)
        if not folder or not front:
            continue
        nowe = {}
        for m in POLE.finditer(front.group(1)):
            rel = m.group(3)
            if rel.startswith(folder + '/') or rel in nowe:
                continue
            zrodlo = os.path.join(korzen, FOLDER, rel)
            if not os.path.isfile(zrodlo):
                print(f'::warning title=Plik obrony::{n}: nie ma pliku {ADRES}{rel} w Media; adres zostaje bez zmian.')
                continue
            nazwa = wolna_nazwa(korzen, folder, os.path.basename(rel), zrodlo)
            cel = os.path.join(korzen, FOLDER, folder, nazwa)
            os.makedirs(os.path.dirname(cel), exist_ok=True)
            uzycia[rel].discard(n)
            if os.path.exists(cel):
                if not uzycia[rel]:
                    os.remove(zrodlo)
            elif uzycia[rel]:
                shutil.copy2(zrodlo, cel)
            else:
                shutil.move(zrodlo, cel)
            stary = os.path.dirname(zrodlo)  # pusty folder po przeniesieniu (np. po zmianie nazwiska)
            if os.path.normpath(stary) != os.path.normpath(os.path.join(korzen, FOLDER)) and not os.listdir(stary):
                os.rmdir(stary)
            uzycia.setdefault(f'{folder}/{nazwa}', set()).add(n)
            nowe[rel] = f'{folder}/{nazwa}'
            zmiany.append(f'{n}: {ADRES}{rel} → {ADRES}{folder}/{nazwa}')
        if nowe:
            naglowek = POLE.sub(lambda m: m.group(1) + m.group(2) + ADRES + nowe.get(m.group(3), m.group(3)) + m.group(2)
                                + m.group(4), front.group(1))
            with open(os.path.join(katalog, n), 'w', encoding='utf-8', newline='') as f:
                f.write(t[:front.start(1)] + naglowek + t[front.end(1):])

    if przed and set(przed) != {'0'} and subprocess.run(['git', 'cat-file', '-e', przed + '^{commit}'], cwd=korzen,
                                                        capture_output=True).returncode == 0:
        usuniete = subprocess.run(['git', 'diff', '--name-only', '--diff-filter=D', przed, 'HEAD', '--', WPISY], cwd=korzen,
                                  check=True, capture_output=True, text=True).stdout.split()
        zywe = {osoba(t) for t in wpisy.values()} | {rel.split('/')[0] for rel, w in uzycia.items() if w and '/' in rel}
        for p in usuniete:
            stary = subprocess.run(['git', 'show', f'{przed}:{p}'], cwd=korzen, check=True, capture_output=True).stdout
            folder = osoba(stary.decode('utf-8', 'replace'))
            sciezka = os.path.join(korzen, FOLDER, folder)
            if folder and folder not in zywe and os.path.isdir(sciezka):
                shutil.rmtree(sciezka)
                zmiany.append(f'{os.path.basename(p)} usunięta: usunięto folder {ADRES}{folder}/')
    return zmiany


if __name__ == '__main__':
    for z in uporzadkuj(os.getcwd(), sys.argv[1] if len(sys.argv) > 1 else None):
        print(z)

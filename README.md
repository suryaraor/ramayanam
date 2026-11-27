# శ్రీమద్రామాయణము · Srimad Ramayanam

Srimad Ramayanam in Telugu prose, kanda by kanda, published at **https://suryarao.in/ramayanam/**.
It uses the same reader as the [magazine](https://suryarao.in/magazine/) site: tap a part to read it
full screen with page turns, download it, or share a link.

| # | Part | File |
|---|---|---|
| 1 | బాల కాండము (Bala Kanda) | `data/01-bala-kanda.pdf` |
| 2 | అయోధ్య కాండము · ప్రథమ భాగము (Ayodhya Kanda, Part 1) | `data/02-ayodhya-kanda-part-1.pdf` |
| 3 | అయోధ్య కాండము · ద్వితీయ భాగము (Ayodhya Kanda, Part 2) | `data/03-ayodhya-kanda-part-2.pdf` |
| 4 | అరణ్య · కిష్కింధ · సుందర కాండములు (Aranya, Kishkindha and Sundara Kanda) | `data/04-aranya-kishkindha-sundara-kanda.pdf` |
| 5 | యుద్ధ కాండము · ప్రథమ భాగము (Yuddha Kanda, Part 1) | `data/05-yuddha-kanda-part-1.pdf` |
| 6 | యుద్ధ కాండము · ద్వితీయ భాగము (Yuddha Kanda, Part 2) | `data/06-yuddha-kanda-part-2.pdf` |

The original Word files are in `sources/`. The PDFs are made from them for easy reading on a phone:
book-sized (A5) pages, a large Telugu font with roomy line spacing, verses set apart, page numbers,
and a cover for each part. `sources/ayodhya-kanda-earlier-draft.docx` is an earlier draft of the
Ayodhya Kanda kept for reference; parts 2 and 3 above are the final text.

## Adding or updating a part

1. Put the Word file in `sources/` with a number first, for example `07-uttara-kanda.docx`.
2. Add its Telugu and English names to `js/books.js`.
3. Make the PDF (needs Python 3 and Google Chrome or Microsoft Edge):
   ```
   python tools/build-pdfs.py                  # every part
   python tools/build-pdfs.py 07-uttara-kanda  # just one
   ```
4. Rebuild the list of parts with `node tools/build-manifest.mjs`, then commit (including
   `magazines.json`) and push to `gh-pages`. GitHub Pages serves the branch directly; the new
   part is live in a minute or two.

## What readers can do

| Where | Action |
|---|---|
| Home | Tap a cover or **చదవండి** (Read) to open the part full screen |
| Home / reader | **డౌన్‌లోడ్** saves the PDF; **షేర్** opens the phone's share sheet (or copies a link) |
| Reader | Tap the **right side** for the next page, **left side** for the previous one |
| Reader | **Swipe right-to-left** to go back to the list of parts |
| Reader | Tap the **middle** to show or hide the toolbar |
| Desktop | ← / → turn pages, Esc goes back, Ctrl+L switches between fit-to-page and fit-to-width |

Parts open offline once they have been read while connected.

## Local preview

```
node tools/build-manifest.mjs
python -m http.server 8000
```
Then open http://localhost:8000.

## Layout

```
index.html                 home page + reader
css/style.css
js/app.js                  catalog, PDF rendering, page turns, gestures
js/books.js                Telugu and English name of each part
sw.js                      offline reading
vendor/pdfjs/              PDF.js 4.10.38 legacy build (Mozilla, Apache-2.0); works on older iPads and iPhones
tools/build-pdfs.py        Word files in sources/ -> PDFs in data/
tools/build-manifest.mjs   writes magazines.json from data/*.pdf
magazines.json             the list of parts shown on the home page
sources/                   original Word files
data/                      the PDFs readers see
```

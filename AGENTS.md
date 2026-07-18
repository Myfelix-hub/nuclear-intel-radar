# Nuclear Intel Radar — Agent Notes

## Scope

This repo powers the public Nuclear Intel Radar static site, a zero-server
pipeline that aggregates global nuclear energy industry intelligence
(IAEA, NRC, SMR developers, fusion, fuel cycle, operational events, policy).

## Working Rules

- Keep changes small and reviewable.
- Search the repo before changing source fetchers or output schemas. The
  source list, fetcher functions, and scoring weights live in
  `scripts/update_news.py` and `scripts/nuclear_keywords.py`.
- Do not commit private feeds, secrets, tokens, cookies, browser exports,
  OPML files, or `.env` values.
- Do not hand-edit files under `data/` — they are regenerated every 30
  minutes by `.github/workflows/update-news.yml`.
- Prefer stable public RSS/Atom feeds and first-party sources. Use Jina
  Reader as fallback for sources without RSS. Custom scrapers only when
  the source is high-signal and the markup is stable.

## Source Strategy

Before adding or removing a source, check `data/source-status.json` for
the last run's reachability and item count.

When adding a source:
1. Register the fetcher in `scripts/update_news.py`.
2. Assign a source tier in `scripts/nuclear_keywords.py`.
3. Add section classification rules if the source should force a section
   (e.g., arXiv → research, Reddit → community).
4. Add/update tests in `tests/test_section_classification.py`.

Default source priority:

1. Official RSS/Atom feeds from industry bodies (IAEA, NRC, NucNet, WNN,
   ANS Newswire, EUROfusion, DOE-NE).
2. Vendor / OEM newsrooms with stable RSS (NuScale, TerraPower, X-energy,
   Kairos, Oklo, BWXT, Rolls-Royce SMR, Holtec, AtkinsRéalis).
3. National labs, regulators, and government agencies (CNNC, EDF, CGN,
   Rosatom, JAEA, etc.) via RSS or official news pages.
4. Trade media (POWER Magazine, Neutron Bytes, Nuclear Engineering Int'l).
5. Community signals (HN Algolia, Reddit r/nuclear) — high noise, treat
   with a stricter nuclear-relevance bar.
6. Aggregators and Jina-based fallbacks for sources without RSS.

Avoid sources that require login, cookies, CAPTCHA, or paid API keys for
the public deployment. If a source is blocked by Cloudflare/GFW from
mainland China, confirm it is reachable from the GitHub Actions runner
before relying on it.

## Common Commands

```bash
python -m py_compile scripts/update_news.py
python -m pytest tests/ -q
python -m pytest tests/test_section_classification.py -q
python scripts/update_news.py --output-dir data --window-hours 72 --archive-days 21
python -m http.server 8080   # then open http://localhost:8080
```
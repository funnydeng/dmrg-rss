# DMRG-RSS

RSS feed and HTML pages for DMRG cond-mat articles.

**Articles are aggregated from:** [http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html](http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html)

## 🌐 Access the Papers

- **📖 Web Interface**: [https://funnydeng.github.io/dmrg-rss/](https://funnydeng.github.io/dmrg-rss/)
- **📡 RSS Feed**: [https://funnydeng.github.io/dmrg-rss/condmat.xml](https://funnydeng.github.io/dmrg-rss/condmat.xml)

## 📋 Features

- **Automated Updates**: Syncs every 12 hours via GitHub Actions
- **Rich Content**: Includes paper titles, authors, abstracts, and arXiv links
- **Dual Output**: Both RSS feed and HTML webpage generated simultaneously
- **Clean Interface**: User-friendly web interface for browsing papers
- **Data Consistency**: Uses JSON cache to ensure complete data in both RSS and HTML

## 🔧 Technical Details

The script `generate_rss.py` fetches papers from the DMRG cond-mat page, enriches them with metadata from arXiv API, and generates both:
- `docs/condmat.xml` - RSS 2.0 feed with paper metadata (published canonical copy of the latest versioned file)
- `docs/condmat.html` - Responsive HTML webpage with paper listings (published canonical copy of the latest versioned file)
- `docs/condmat{YY}.xml/html` - Per-year archives (e.g. `condmat25.html`), linked from each page's "Archive" row
- `docs/entries{YY}.json` - Cached metadata for incremental updates (append-only per year)

The archive year is taken from the arXiv IDs listed on the source page, not from the clock: the
source page keeps showing last year's papers for a few days into January, and those papers belong
to last year's archive.

To regenerate every year's XML/HTML from the JSON caches without fetching anything:

```bash
python generate_rss.py --rebuild
```

Both files are automatically deployed to GitHub Pages for easy access.
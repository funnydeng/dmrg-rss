# DMRG-RSS

RSS feed and HTML pages for DMRG cond-mat articles.

**Articles are aggregated from:** [http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html](http://quattro.phys.sci.kobe-u.ac.jp/dmrg/condmat.html)

## 🌐 Access the Papers

- **📖 Web Interface**: [https://funnydeng.github.io/dmrg-rss/](https://funnydeng.github.io/dmrg-rss/)
- **📡 RSS Feed**: [https://funnydeng.github.io/dmrg-rss/rss.xml](https://funnydeng.github.io/dmrg-rss/rss.xml)

## 📋 Features

- **Automated Updates**: Syncs every 12 hours via GitHub Actions
- **Rich Content**: Includes paper titles, authors, abstracts, and arXiv links
- **Dual Output**: Both RSS feed and HTML webpage generated simultaneously
- **Clean Interface**: User-friendly web interface for browsing papers
- **Data Consistency**: Uses JSON cache to ensure complete data in both RSS and HTML

## 🔧 Technical Details

The script `generate_rss.py` fetches papers from the DMRG cond-mat page, enriches them with metadata from arXiv API, and generates both:
- `docs/rss.xml` - RSS 2.0 feed with DC creator metadata
- `docs/rss.html` - Responsive HTML webpage with paper listings

Both files are automatically deployed to GitHub Pages for easy access.
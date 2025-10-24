#!/usr/bin/env python3
"""
HTML generator module for creating mobile-responsive paper listings.
"""
import os
import logging
from datetime import datetime
from html import escape

from .latex_renderer import LaTeXRenderer
from ..utils.text_utils import is_entry_complete, latex_to_unicode
from ..config import HTML_TITLE, HTML_DESCRIPTION


class HTMLGenerator:
    """Generator for mobile-responsive HTML paper listings."""
    
    def __init__(self, output_path, skip_numeric_prices=False, rss_path=None):
        """
        Initialize HTML generator.
        
        Args:
            output_path (str): Path where HTML file will be saved
            rss_path (str): Path to corresponding RSS file (if None, auto-derived from output_path)
        """
        self.output_path = output_path
        
        # Auto-derive RSS path if not provided
        if rss_path is None:
            # Replace .html with .xml in the same directory
            self.rss_path = output_path.rsplit('.', 1)[0] + '.xml' if '.' in output_path else output_path + '.xml'
        else:
            self.rss_path = rss_path
        
        # Extract just the filename for the HTML link (e.g., "condmat.xml" from "docs/condmat.xml")
        self.rss_filename = self.rss_path.split('/')[-1]
        
        # Pass configuration into LaTeXRenderer
        self.latex_renderer = LaTeXRenderer()
        # Honor caller preference for skipping numeric/price-like $...$
        self.latex_renderer.skip_numeric_prices = skip_numeric_prices
    
    def get_css_styles(self):
        """
        Get CSS styles for mobile-responsive design.
        
        Returns:
            str: CSS stylesheet content
        """
        return """
        body { 
            font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; 
            line-height: 1.6; 
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }
        
        h1 { 
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            font-size: 2.2em;
        }
        
        h2 { 
            color: #34495e;
            border-bottom: 1px solid #bdc3c7;
            padding-bottom: 5px;
            font-size: 1.5em;
        }
        
        h3 { 
            color: #2980b9;
            margin-bottom: 0.5em;
            font-size: 1.2em;
        }
        
        .paper-entry { 
            margin-bottom: 2em;
            padding: 1em;
            background-color: #f8f9fa;
            border-radius: 5px;
        }
        
        .meta { 
            color: #7f8c8d;
            font-size: 0.9em;
            margin: 0.5em 0;
        }
        
        .abstract { 
            margin-top: 1em;
            text-align: justify;
        }
        
        a { 
            color: #3498db;
            text-decoration: none;
            word-break: break-word;
        }
        
        a:hover { 
            text-decoration: underline;
        }
        
        hr { 
            border: 0;
            border-top: 1px solid #ecf0f1;
            margin: 2em 0;
        }
        
        /* KaTeX styles */
        .katex-display { 
            margin: 1.5em 0 !important;
            text-align: center !important;
            overflow-x: auto;
        }
        
        .katex-inline {
            /* Inline math formulas */
        }
        
        .katex {
            font-size: 1.1em;
        }
        
        /* Mobile responsiveness - Phones */
        @media screen and (max-width: 600px) {
            body {
                padding: 12px;
                max-width: 100%;
                font-size: 14px;
            }
            
            h1 {
                font-size: 1.6em;
                text-align: center;
                margin-bottom: 1em;
            }
            
            h2 {
                font-size: 1.2em;
            }
            
            h3 {
                font-size: 1.0em;
                line-height: 1.3;
                word-break: break-word;
            }
            
            .paper-entry {
                padding: 0.7em;
                margin-bottom: 1.2em;
                border-radius: 3px;
            }
            
            .meta {
                font-size: 0.8em;
                line-height: 1.3;
                margin: 0.3em 0;
            }
            
            .abstract {
                text-align: left;
                font-size: 0.9em;
                line-height: 1.4;
            }
            
            .katex {
                font-size: 0.9em;
            }
            
            .katex-display {
                overflow-x: auto;
                overflow-y: hidden;
                font-size: 0.85em;
            }
            
            a {
                word-break: break-all;
            }
        }
        
        /* Tablets */
        @media screen and (min-width: 601px) and (max-width: 768px) {
            body {
                padding: 15px;
                max-width: 100%;
                font-size: 15px;
            }
            
            h1 {
                font-size: 1.9em;
                text-align: center;
            }
            
            h2 {
                font-size: 1.4em;
            }
            
            h3 {
                font-size: 1.1em;
                line-height: 1.4;
            }
            
            .paper-entry {
                padding: 0.8em;
                margin-bottom: 1.5em;
            }
            
            .meta {
                font-size: 0.85em;
                line-height: 1.4;
            }
            
            .abstract {
                text-align: justify;
                font-size: 0.95em;
            }
            
            .katex {
                font-size: 1em;
            }
            
            .katex-display {
                overflow-x: auto;
                overflow-y: hidden;
            }
        }
        
        /* Large tablets/small desktops */
        @media screen and (min-width: 769px) and (max-width: 1024px) {
            body {
                padding: 18px;
                max-width: 95%;
            }
            
            h1 {
                font-size: 2em;
            }
        }
        
        @media print {
            body { 
                max-width: none;
                margin: 0;
                padding: 15mm;
            }
        }
        
        /* Header styles */
        .header {
            text-align: center;
            margin-bottom: 2em;
            padding-bottom: 1em;
            border-bottom: 2px solid #ecf0f1;
        }
        
        .header h1 {
            margin-bottom: 0.5em;
        }
        
        .header .description {
            color: #7f8c8d;
            font-size: 1.1em;
            margin-bottom: 1em;
        }
        
        .header .nav-links {
            display: flex;
            justify-content: center;
            gap: 2em;
            flex-wrap: wrap;
        }
        
        .header .nav-links a {
            color: #3498db;
            text-decoration: none;
            font-weight: 500;
            padding: 0.5em 1em;
            border: 1px solid #3498db;
            border-radius: 5px;
            transition: all 0.3s ease;
        }
        
        .header .nav-links a:hover {
            background-color: #3498db;
            color: white;
        }
        
        /* Footer styles */
        .footer {
            margin-top: 3em;
            padding-top: 2em;
            border-top: 2px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
        }
        
        .footer a {
            color: #3498db;
        }
        
        /* Mobile adjustments for header/footer */
        @media screen and (max-width: 600px) {
            .header .nav-links {
                flex-direction: column;
                gap: 1em;
            }
            
            .header .nav-links a {
                width: 80%;
                text-align: center;
            }
        }
        
        /* Dark mode support - Manual class-based theme + system preference fallback */
        /* Default: Light theme */
        body {
            color: #333;
            background-color: #ffffff;
        }
        
        h1 {
            color: #0066cc;
            border-bottom-color: #0052a3;
        }
        
        h2 {
            color: #0052a3;
            border-bottom-color: #ddd;
        }
        
        h3 {
            color: #0066cc;
        }
        
        .paper-entry {
            background-color: #f9f9f9;
            border: 1px solid #ddd;
        }
        
        .meta {
            color: #666;
        }
        
        a {
            color: #0066cc;
        }
        
        a:hover {
            color: #0052a3;
        }
        
        hr {
            border-top-color: #ddd;
        }
        
        .header {
            border-bottom-color: #ddd;
        }
        
        .header .description {
            color: #666;
        }
        
        .header .nav-links a {
            color: #0066cc;
            border-color: #0066cc;
            background-color: transparent;
        }
        
        .header .nav-links a:hover {
            background-color: #0066cc;
            color: #ffffff;
        }
        
        /* Light theme KaTeX colors */
        .katex {
            color: #000000 !important;
        }
        
        .katex-html {
            color: #000000 !important;
        }
        
        .katex .mord,
        .katex .mop,
        .katex .mbin,
        .katex .mrel,
        .katex .mopen,
        .katex .mclose,
        .katex .mpunct {
            color: #000000 !important;
        }
        
        /* Dark theme class - explicitly set when dark mode is enabled */
        html.dark-theme body {
            color: #e0e0e0;
            background-color: #1a1a1a;
        }
        
        html.dark-theme h1 {
            color: #64b5f6;
            border-bottom-color: #42a5f5;
        }
        
        html.dark-theme h2 {
            color: #90caf9;
            border-bottom-color: #424242;
        }
        
        html.dark-theme h3 {
            color: #64b5f6;
        }
        
        html.dark-theme .paper-entry {
            background-color: #262626;
            border: 1px solid #404040;
        }
        
        html.dark-theme .meta {
            color: #b0b0b0;
        }
        
        html.dark-theme a {
            color: #64b5f6;
        }
        
        html.dark-theme a:hover {
            color: #90caf9;
        }
        
        html.dark-theme hr {
            border-top-color: #404040;
        }
        
        html.dark-theme .header {
            border-bottom-color: #404040;
        }
        
        html.dark-theme .header .description {
            color: #b0b0b0;
        }
        
        html.dark-theme .header .nav-links a {
            color: #64b5f6;
            border-color: #64b5f6;
            background-color: transparent;
        }
        
        html.dark-theme .header .nav-links a:hover {
            background-color: #64b5f6;
            color: #1a1a1a;
        }
        
        /* KaTeX in dark theme */
        html.dark-theme .katex {
            color: #e0e0e0 !important;
        }
        
        html.dark-theme .katex-html {
            color: #e0e0e0 !important;
        }
        
        html.dark-theme .katex .mord,
        html.dark-theme .katex .mop,
        html.dark-theme .katex .mbin,
        html.dark-theme .katex .mrel,
        html.dark-theme .katex .mopen,
        html.dark-theme .katex .mclose,
        html.dark-theme .katex .mpunct {
            color: #e0e0e0 !important;
        }
        
        /* Fallback for system preference if no stored theme */
        @media (prefers-color-scheme: dark) {
            html:not(.light-theme) body {
                color: #e0e0e0;
                background-color: #1a1a1a;
            }
            
            html:not(.light-theme) .katex {
                color: #e0e0e0;
            }
            
            .katex-html {
                color: #e0e0e0;
            }
        }
        
        /* Theme toggle button */
        .theme-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: #f0f0f0;
            border: 2px solid #3498db;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            z-index: 1000;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .theme-toggle:hover {
            transform: scale(1.1);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        
        /* Dark theme button styling */
        html.dark-theme .theme-toggle {
            background-color: #333;
            border-color: #64b5f6;
            box-shadow: 0 2px 8px rgba(100,181,246,0.3);
        }
        
        html.dark-theme .theme-toggle:hover {
            box-shadow: 0 4px 12px rgba(100,181,246,0.5);
        }
        
        @media screen and (max-width: 600px) {
            .theme-toggle {
                width: 45px;
                height: 45px;
                top: 15px;
                right: 15px;
                font-size: 20px;
            }
        }
        """
    
    def generate_html(self, entries):
        """
        Generate HTML file with mobile-responsive design and LaTeX rendering.
        
        Args:
            entries (list): List of entry dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        logging.info(f"Generating HTML with {len(entries)} entries")
        
        # Filter complete entries
        complete_entries = [e for e in entries if is_entry_complete(e)]
        incomplete_entries = [e for e in entries if not is_entry_complete(e)]
        
        if incomplete_entries:
            logging.warning(f"HTML generation using {len(complete_entries)} complete entries, skipping {len(incomplete_entries)} incomplete entries")
        
        # Start building HTML content
        html_content = []
        
        # Add generation info (header with title is now in template)
        html_content.append(f"<p><em>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>")
        html_content.append(f"<p>Total papers: {len(complete_entries)}")
        if incomplete_entries:
            html_content.append(f" ({len(incomplete_entries)} entries with incomplete data not shown)")
        html_content.append("</p>")
        
        # Add entry list
        html_content.append("<h2>Recent Papers</h2>")
        
        # Sort entries by publication date (newest first) for better HTML presentation
        def get_sort_date(entry):
            pubdate = entry.get("pubdate", "")
            if not pubdate:
                return datetime.min
            try:
                if 'T' in pubdate and pubdate.endswith('Z'):
                    return datetime.strptime(pubdate, "%Y-%m-%dT%H:%M:%SZ")
                else:
                    from email.utils import parsedate_to_datetime
                    return parsedate_to_datetime(pubdate)
            except:
                return datetime.min
        
        sorted_entries = sorted(complete_entries, key=get_sort_date, reverse=True)
        logging.info(f"Sorted {len(sorted_entries)} entries by publication date for HTML display")
        
        # Process each entry
        for entry in sorted_entries:
            try:
                title = entry.get("title", "Untitled")
                authors = entry.get("authors", "Unknown")
                link = entry.get("link", "#")
                abstract = entry.get("abstract", "No abstract available")
                arxiv_id = link.rsplit("/", 1)[-1] if "/" in link else "unknown"
                
                # Format publication date for display
                pubdate = entry.get("pubdate", "")
                display_date = "Unknown date"
                if pubdate:
                    try:
                        if 'T' in pubdate and pubdate.endswith('Z'):
                            dt = datetime.strptime(pubdate, "%Y-%m-%dT%H:%M:%SZ")
                        else:
                            from email.utils import parsedate_to_datetime
                            dt = parsedate_to_datetime(pubdate)
                        display_date = dt.strftime("%Y-%m-%d")
                    except:
                        display_date = str(pubdate)
                
                # Convert LaTeX accents to Unicode and render LaTeX formulas
                title = latex_to_unicode(title)
                abstract = latex_to_unicode(abstract)
                authors = latex_to_unicode(authors)
                
                title_with_latex = self.latex_renderer.render_in_html(title)
                abstract_with_latex = self.latex_renderer.render_in_html(abstract)
                
                # Create entry HTML
                entry_html = f"""
                <article class='paper-entry'>
                    <h3><a href='{escape(link)}'>{title_with_latex}</a></h3>
                    <p class='meta'><strong>Authors:</strong> {escape(authors)}</p>
                    <p class='meta'><strong>arXiv ID:</strong> {arxiv_id} | <strong>Date:</strong> {display_date}</p>
                    <div class='abstract'>
                        <strong>Abstract:</strong> {abstract_with_latex}
                    </div>
                </article>
                <hr>
                """
                html_content.append(entry_html)
                
            except Exception as e:
                logging.error(f"Failed to add HTML entry {entry.get('link', 'unknown')}: {e}")
        
        # Create complete HTML document
        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{HTML_TITLE}</title>
    <link rel="icon" sizes="192x192" href="images/ITensorMan_square_alpha.png" type="image/png"/>
    <link rel="shortcut icon" href="images/ITensorMan_square_alpha.png" type="image/png"/>
    <link rel="apple-touch-icon" href="images/ITensorMan_square_alpha.png" type="image/png"/>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        {self.get_css_styles()}
    </style>
    <script>
        // Initialize theme from system preference or stored preference
        (function() {{
            const storedTheme = localStorage.getItem('theme-preference');
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const theme = storedTheme || (prefersDark ? 'dark' : 'light');
            
            if (theme === 'dark') {{
                document.documentElement.classList.add('dark-theme');
                document.documentElement.classList.remove('light-theme');
            }} else {{
                document.documentElement.classList.add('light-theme');
                document.documentElement.classList.remove('dark-theme');
            }}
        }})();
    </script>
</head>
<body>
    <!-- Theme toggle button -->
    <button class="theme-toggle" id="themeToggle" title="Toggle dark/light mode" aria-label="Toggle dark/light mode">
        <span id="themeIcon"><i class="fa-solid fa-circle-half-stroke"></i></span>
    </button>
    <div class="header">
        <h1><img src="images/ITensorMan_square_alpha.png" alt="DMRG" style="height: 40px; vertical-align: middle; margin-right: 10px;"> {HTML_TITLE}</h1>
        <p class="description">
            {HTML_DESCRIPTION}
        </p>
        <div class="nav-links">
            <a href="index.html"><i class="fa-solid fa-house"></i> Home</a>
            <a href="{self.rss_filename}"><i class="fas fa-rss"></i> RSS Feed</a>
            <a href="https://github.com/funnydeng/dmrg-rss"><i class="fa-brands fa-github"></i> GitHub</a>
        </div>
    </div>
    
{chr(10).join(html_content)}

    <div class="footer">
        <p>
            <!-- Updated automatically every 12 hours via GitHub Actions<br> -->
            <a href="https://github.com/funnydeng/dmrg-rss"><i class="fa-brands fa-github"></i> View Source Code on GitHub</a>
        </p>
    </div>
    
    <script>
        // Theme toggle functionality
        const themeToggle = document.getElementById('themeToggle');
        const themeIcon = document.getElementById('themeIcon');
        const htmlElement = document.documentElement;
        
        function updateThemeIcon() {{
            const isDark = htmlElement.classList.contains('dark-theme');
            themeIcon.innerHTML = isDark ? '<i class="fa-solid fa-circle-half-stroke"></i>' : '<i class="fa-solid fa-circle-half-stroke"></i>';
        }}
        
        function toggleTheme() {{
            const isDark = htmlElement.classList.contains('dark-theme');
            if (isDark) {{
                htmlElement.classList.remove('dark-theme');
                htmlElement.classList.add('light-theme');
                localStorage.setItem('theme-preference', 'light');
            }} else {{
                htmlElement.classList.add('dark-theme');
                htmlElement.classList.remove('light-theme');
                localStorage.setItem('theme-preference', 'dark');
            }}
            updateThemeIcon();
        }}
        
        themeToggle.addEventListener('click', toggleTheme);
        
        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {{
            if (!localStorage.getItem('theme-preference')) {{
                if (e.matches) {{
                    htmlElement.classList.add('dark-theme');
                    htmlElement.classList.remove('light-theme');
                }} else {{
                    htmlElement.classList.remove('dark-theme');
                    htmlElement.classList.add('light-theme');
                }}
                updateThemeIcon();
            }}
        }});
        
        // Initialize icon on page load
        updateThemeIcon();
    </script>
</body>
</html>"""
        
        # Write HTML file
        try:
            os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write(html_template)
            
            if os.path.exists(self.output_path):
                file_size = os.path.getsize(self.output_path)
                logging.info(f"HTML successfully written to {self.output_path}")
                logging.info(f"HTML file size: {file_size} bytes")
                logging.info(f"HTML entries processed: {len(sorted_entries)} (with LaTeX rendering)")
                return True
            else:
                logging.error(f"Failed to create HTML file at {self.output_path}")
                return False
        
        except Exception as e:
            logging.error(f"Error writing HTML file: {e}")
            return False

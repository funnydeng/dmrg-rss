#!/usr/bin/env python3
"""
LaTeX rendering module using KaTeX CLI.
Handles preprocessing and safe rendering of LaTeX formulas.
"""
import os
import re
import json
import shutil
import subprocess
import logging


class LaTeXRenderer:
    """Handler for LaTeX formula rendering using KaTeX CLI."""
    
    def __init__(self, timeout=10):
        """
        Initialize LaTeX renderer.
        
        Args:
            timeout (int): Timeout for KaTeX rendering in seconds
        """
        self.timeout = timeout
        # If True, skip rendering of pure-numeric/price-like $...$ expressions
        # (e.g. $99.99, $2) because these are usually not math to render.
        # Set to False to attempt to render all $...$ content.
        self.skip_numeric_prices = False
        # Rendered output per (formula, display_mode); each KaTeX call spawns a node process
        self._cache = {}
    
    def preprocess_formula(self, formula):
        """
        Preprocess LaTeX formula to handle KaTeX unsupported commands.
        Convert non-standard LaTeX to standard KaTeX-compatible commands.
        
        Args:
            formula (str): Raw LaTeX formula
            
        Returns:
            str: Preprocessed formula with KaTeX-compatible commands
        """
        if not formula:
            return formula
        
        processed = formula
        
        # Convert non-standard commands to standard LaTeX equivalents
        # \unicode{x2014} (em dash) and \unicode{x2013} (en dash) -> hyphen
        processed = re.sub(r'\\unicode\{x201[34]\}', '-', processed)
        # Remove other unicode commands
        processed = re.sub(r'\\unicode\{[^}]+\}', '', processed)
        
        # \cross -> \times (vector cross product, case-insensitive)
        processed = re.sub(r'\\[Cc]ross\b', r'\\times', processed)
        
        # \vector{x} -> \vec{x} (vector notation)
        processed = re.sub(r'\\vector\{([^}]+)\}', r'\\vec{\1}', processed)
        
        # \mbox{...} -> \text{...} (text in math mode)
        processed = re.sub(r'\\mbox\{([^}]*)\}', r'\\text{\1}', processed)
        
        return processed
    
    def render_formula(self, formula, display_mode=False, output="html"):
        """
        Render one formula (cached). Returns KaTeX markup, or the original
        $...$ / $$...$$ text if it cannot be rendered.
        """
        self.prerender([(formula, display_mode)], output)
        return self._cache[(formula, display_mode, output)]

    def prerender(self, formulas, output="html"):
        """
        Render all given (formula, display_mode) pairs that are not cached yet,
        in as few node processes as possible.
        """
        pending = {}
        for formula, display_mode in formulas:
            key = (formula, display_mode, output)
            if key in self._cache or key in pending:
                continue
            fallback = f"$${formula}$$" if display_mode else f"${formula}$"
            if not formula or (self.skip_numeric_prices and len(formula.strip()) <= 10
                               and re.match(r'^[\d.,\s]+$', formula.strip())):
                # Empty, or price-like ($99.99) when configured to skip those
                self._cache[key] = fallback
                continue
            pending[key] = {"tex": self.preprocess_formula(formula).strip(), "macros": {}, "fallback": fallback}

        # Formulas using an author's own macros (\order, \ZZ, ...) fail with
        # "Undefined control sequence"; define the macro and try again.
        for _ in range(MAX_MACRO_ROUNDS):
            if not pending:
                break
            keys = list(pending)
            results = self._katex_many(
                [(pending[k]["tex"], k[1], KATEX_FORMATS[output], pending[k]["macros"]) for k in keys])
            retry = {}
            for key, (ok, result) in zip(keys, results):
                item = pending[key]
                if ok and result and ('<span' in result or '<math' in result):
                    self._cache[key] = self._postprocess(result, output)
                    continue
                match = re.search(r'Undefined control sequence: (\\[A-Za-z]+)', result or "")
                if match and match.group(1) not in item["macros"]:
                    item["macros"][match.group(1)] = fallback_macro(match.group(1))
                    retry[key] = item
                else:
                    logging.warning(f"[KaTeX Error] Failed to render formula: {key[0]} ({(result or '').splitlines()[0] if result else 'no output'})")
                    self._cache[key] = item["fallback"]
            pending = retry
        for key, item in pending.items():
            logging.warning(f"[KaTeX Error] Too many undefined macros in formula: {key[0]}")
            self._cache[key] = item["fallback"]

    @staticmethod
    def _postprocess(rendered, output):
        if output == "mathml":
            # Drop the TeX source annotation: feed readers that strip <math>
            # tags would otherwise show every formula twice.
            rendered = re.sub(r'<annotation encoding="application/x-tex">.*?</annotation>', '', rendered, flags=re.S)
        return rendered

    def _katex_many(self, items):
        """
        Render [(tex, display_mode, output, macros)] with KaTeX.

        Returns:
            list: [(ok, html_or_error_message)]
        """
        katex_dir = _katex_package_dir()
        if katex_dir:
            try:
                result = subprocess.run(
                    ["node", BATCH_SCRIPT, katex_dir],
                    input=json.dumps(items).encode("utf-8"),
                    capture_output=True, check=True,
                    timeout=self.timeout * len(items) + 60,
                )
                return [(r["ok"], r["html"] if r["ok"] else r["error"]) for r in json.loads(result.stdout)]
            except Exception as e:
                logging.warning(f"[KaTeX] Batch rendering failed ({e}); rendering one formula at a time")
        return [self._katex_cli(*item) for item in items]

    def _katex_cli(self, tex, display_mode, output, macros):
        """Render one formula with the katex CLI. Returns (ok, html_or_error)."""
        cmd = ["katex", "--format", output]
        if display_mode:
            cmd.append("--display-mode")
        for name, expansion in macros.items():
            cmd += ["--macro", f"{name}:{expansion}"]
        try:
            result = subprocess.run(cmd, input=tex.encode("utf-8"), capture_output=True,
                                    check=True, timeout=self.timeout)
            return True, result.stdout.decode("utf-8").strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.decode("utf-8", "replace") if e.stderr else str(e)
        except FileNotFoundError:
            return False, "KaTeX CLI not found"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def split_math(text):
        """
        Split text into ("text" | "inline" | "display", content) segments.

        Scans left to right so adjacent formulas such as $\\sim$$10^{22}$ are
        read as two inline formulas rather than around a "$$".
        """
        segments = []
        plain = []
        i, n = 0, len(text)
        while i < n:
            if text.startswith("$$", i):
                end = text.find("$$", i + 2)
                content = text[i + 2:end]
                if end != -1 and content and "$" not in content:
                    segments.append(("text", "".join(plain))); plain = []
                    segments.append(("display", content))
                    i = end + 2
                    continue
            if text[i] == "$":
                end = text.find("$", i + 1)
                content = text[i + 1:end]
                if end != -1 and content and "\n" not in content:
                    segments.append(("text", "".join(plain))); plain = []
                    segments.append(("inline", content))
                    i = end + 1
                    continue
            plain.append(text[i])
            i += 1
        segments.append(("text", "".join(plain)))
        return [s for s in segments if s[0] != "text" or s[1]]

    def prerender_texts(self, texts, output="html"):
        """Render every formula appearing in texts in one batch."""
        self.prerender([(content, kind == "display")
                        for text in texts if text
                        for kind, content in self.split_math(text) if kind != "text"], output)

    def render_in_html(self, html_content, output="html"):
        """
        Render LaTeX formulas in HTML content using KaTeX.
        
        Args:
            html_content (str): HTML content containing LaTeX formulas
            output (str): "html" (needs the KaTeX stylesheet) or "mathml" (for feeds)
            
        Returns:
            str: HTML content with rendered LaTeX formulas
        """
        if not html_content:
            return html_content

        parts = []
        for kind, content in self.split_math(html_content):
            if kind == "text":
                parts.append(content)
            elif kind == "display":
                rendered = self.render_formula(content, display_mode=True, output=output)
                if output == "html":
                    rendered = f'<div class="katex-display" style="margin: 1.5em 0; text-align: center;">{rendered}</div>'
                parts.append(rendered)
            else:
                rendered = self.render_formula(content, display_mode=False, output=output)
                if output == "html" and '<span' in rendered:
                    rendered = f'<span class="katex-inline">{rendered}</span>'
                parts.append(rendered)
        return "".join(parts)


# Commonly used author macros; anything else unknown falls back to upright text
KNOWN_MACROS = {
    "\\order": "\\mathcal{O}\\left(#1\\right)",
    "\\ZZ": "\\mathbb{Z}",
    "\\RR": "\\mathbb{R}",
    "\\CC": "\\mathbb{C}",
    "\\NN": "\\mathbb{N}",
    "\\QQ": "\\mathbb{Q}",
}
# KaTeX output formats: pages keep the CLI default (visible HTML + hidden MathML
# for screen readers and copy/paste); feeds get MathML only
KATEX_FORMATS = {"html": "htmlAndMathml", "mathml": "mathml"}
MAX_MACRO_ROUNDS = 5
BATCH_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "katex_batch.js")


def fallback_macro(name):
    """Expansion used for an undefined control sequence such as \\Var."""
    return KNOWN_MACROS.get(name, "\\mathrm{" + name[1:] + "}")


def _katex_package_dir():
    """Directory of the installed katex package (found via the katex CLI), or None."""
    cli = shutil.which("katex")
    if not cli or not shutil.which("node"):
        return None
    package_dir = os.path.dirname(os.path.realpath(cli))
    return package_dir if os.path.exists(os.path.join(package_dir, "package.json")) else None

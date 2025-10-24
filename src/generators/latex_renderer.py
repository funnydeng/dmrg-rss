#!/usr/bin/env python3
"""
LaTeX rendering module using KaTeX CLI.
Handles preprocessing and safe rendering of LaTeX formulas.
"""
import re
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
    
    def render_formula(self, formula, display_mode=False):
        """
        Safely render a single LaTeX formula using KaTeX CLI.
        
        Args:
            formula (str): LaTeX formula to render
            display_mode (bool): Whether to render in display mode
            
        Returns:
            str: Rendered HTML or fallback LaTeX string
        """
        try:
            # Skip empty formulas
            if not formula:
                return f"${formula}$" if not display_mode else f"$${formula}$$"
            
            # Optionally skip price-like patterns (e.g., $99.99, $10)
            # Only skip if skip_numeric_prices is True
            if self.skip_numeric_prices:
                formula_stripped = formula.strip()
                if len(formula_stripped) <= 10 and re.match(r'^[\d.,\s]+$', formula_stripped):
                    # This looks like a price, not a formula
                    return f"${formula}$" if not display_mode else f"$${formula}$$"
            
            # Preprocess formula (now just returns original)
            processed_formula = self.preprocess_formula(formula)
            
            cmd = ["katex"]
            if display_mode:
                cmd.append("--display-mode")
            
            result = subprocess.run(
                cmd,
                input=processed_formula.strip().encode("utf-8"),
                capture_output=True,
                check=True,
                timeout=self.timeout
            )
            
            rendered = result.stdout.decode("utf-8").strip()
            
            if rendered and ('<span' in rendered or '<div' in rendered):
                return rendered
            else:
                logging.warning(f"[KaTeX Warning] Unexpected output for formula: {formula}")
                return f"${formula}$" if not display_mode else f"$${formula}$$"
                
        except subprocess.TimeoutExpired:
            logging.warning(f"[KaTeX Error] Timeout rendering formula: {formula}")
            return f"${formula}$" if not display_mode else f"$${formula}$$"
        except subprocess.CalledProcessError as e:
            logging.warning(f"[KaTeX Error] Failed to render formula: {formula}")
            if e.stderr:
                error_msg = e.stderr.decode('utf-8')
                logging.warning(f"Error details: {error_msg}")
            # Try to provide a fallback with plain text representation
            fallback = self.preprocess_formula(formula)
            if fallback != formula:
                logging.info(f"[KaTeX Fallback] Falling back to plain text: {fallback}")
            return f"${formula}$" if not display_mode else f"$${formula}$$"
        except FileNotFoundError:
            # KaTeX CLI not available, return original formula
            logging.info("KaTeX CLI not found, LaTeX formulas will not be rendered")
            return f"${formula}$" if not display_mode else f"$${formula}$$"
        except Exception as e:
            logging.warning(f"[KaTeX Error] Unexpected error rendering formula: {formula}")
            logging.warning(f"Error: {str(e)}")
            return f"${formula}$" if not display_mode else f"$${formula}$$"
    
    def render_in_html(self, html_content):
        """
        Render LaTeX formulas in HTML content using KaTeX.
        
        Args:
            html_content (str): HTML content containing LaTeX formulas
            
        Returns:
            str: HTML content with rendered LaTeX formulas
        """
        if not html_content:
            return html_content
        
        processed_formulas = {}
        placeholder_counter = 0
        
        def create_placeholder():
            nonlocal placeholder_counter
            placeholder = f"__KATEX_PLACEHOLDER_{placeholder_counter}__"
            placeholder_counter += 1
            return placeholder
        
        def process_display_math(match):
            formula = match.group(1)
            placeholder = create_placeholder()
            rendered = self.render_formula(formula, display_mode=True)
            # Check if rendering was successful (contains KaTeX HTML) or is fallback
            if '<span' in rendered or '<div' in rendered:
                processed_formulas[placeholder] = f'<div class="katex-display" style="margin: 1.5em 0; text-align: center;">{rendered}</div>'
            else:
                # Fallback case, rendered is already in $$formula$$ format
                processed_formulas[placeholder] = f'<div class="katex-display" style="margin: 1.5em 0; text-align: center;">{rendered}</div>'
            return placeholder
        
        def process_inline_math(match):
            formula = match.group(1)
            if '$$' in match.group(0):
                return match.group(0)
            placeholder = create_placeholder()
            rendered = self.render_formula(formula, display_mode=False)
            # Check if rendering was successful (contains KaTeX HTML) or is fallback
            if '<span' in rendered or '<div' in rendered:
                # Successfully rendered, wrap in katex-inline
                processed_formulas[placeholder] = f'<span class="katex-inline">{rendered}</span>'
            else:
                # Fallback case, rendered is already in $formula$ format, don't double-wrap
                processed_formulas[placeholder] = rendered
            return placeholder
        
        # Process display math formulas $$...$$
        html_content = re.sub(r'\$\$([^$]+?)\$\$', process_display_math, html_content, flags=re.DOTALL)
        
        # Process inline math formulas $...$
        html_content = re.sub(r'(?<!\$)\$([^$\n]+?)\$(?!\$)', process_inline_math, html_content)
        
        # Replace all placeholders
        for placeholder, rendered in processed_formulas.items():
            html_content = html_content.replace(placeholder, rendered)
        
        return html_content

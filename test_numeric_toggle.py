#!/usr/bin/env python3
import sys
sys.path.append('/home/fenglindeng/bin/dmrg-rss')
from latex_renderer import LaTeXRenderer

r1 = LaTeXRenderer()
print('Default skip_numeric_prices:', r1.skip_numeric_prices)
print(r1.render_in_html('Price $99.99 is high.'))

r2 = LaTeXRenderer()
r2.skip_numeric_prices = False
print('\nskip_numeric_prices=False:')
print(r2.render_in_html('Price $99.99 is high.'))

r3 = LaTeXRenderer()
print('\nSingle letter test with skip enabled (default):')
print(r3.render_in_html('Variable $U$ here.'))

r4 = LaTeXRenderer()
r4.skip_numeric_prices = False
print('\nSingle letter test with skip disabled:')
print(r4.render_in_html('Variable $U$ here.'))

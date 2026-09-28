#!/usr/bin/env node
// Render many formulas in one node process (the katex CLI starts node once per formula).
// Usage: node katex_batch.js <path to katex package>
// stdin:  JSON [[tex, displayMode, output, macros], ...]
// stdout: JSON [{ok: true, html} | {ok: false, error}, ...]
const katex = require(process.argv[2] || "katex");

let input = "";
process.stdin.on("data", (chunk) => { input += chunk; });
process.stdin.on("end", () => {
    const results = JSON.parse(input).map(([tex, displayMode, output, macros]) => {
        try {
            // Same options the katex CLI passes (it throws on parse errors by default)
            const html = katex.renderToString(tex, {displayMode, output, macros: macros || {}, throwOnError: true});
            return {ok: true, html};
        } catch (e) {
            return {ok: false, error: String(e.message || e)};
        }
    });
    process.stdout.write(JSON.stringify(results));
});

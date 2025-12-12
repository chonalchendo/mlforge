Refer to the Documentation section in CLAUDE.md for style guidelines.

Review all Python files in src/mlforge/ and update documentation:

1. Ensure every public function, class, and method has a Google-style docstring
2. Verify docstrings accurately reflect current code behavior
3. Add missing Args, Returns, Raises, Example sections where applicable
4. Keep one-line summaries under 80 characters
5. Don't document private methods unless complex

After updating, run `just check` to verify changes pass all checks.
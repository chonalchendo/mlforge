# preview docs
[group('docs')]
docs-serve:
    uv run mkdocs serve
    
# build docs
[group('docs')]
docs-build:
    uv run mkdocs build

# deploy docs
[group('docs')]
docs-deploy:
    uv run mkdocs gh-deploy --force
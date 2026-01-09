FROM ghcr.io/astral-sh/uv:python3.13-bookworm
COPY dist/*.whl .
RUN uv pip install --system *.whl
CMD ["mlforge", "--help"]

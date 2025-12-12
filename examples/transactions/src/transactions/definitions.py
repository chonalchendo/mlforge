from pathlib import Path

from mlforge import Definitions, LocalStore
from transactions import features

defs = Definitions(
    name="Transactions features.",
    features=[features],
    offline_store=LocalStore(path=Path("./feature_store")),
)

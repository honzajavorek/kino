import json
from operator import itemgetter
from pathlib import Path


def format_json(path: Path):
    # see https://github.com/apify/crawlee-python/issues/526
    data = json.loads(path.read_text())
    data = sorted(data, key=itemgetter("starts_at"))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

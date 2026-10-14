"""Check every database and report which ones are reachable."""
from sqlalchemy import text

from .common import DatabaseConnectionError


def _pg():
    from .postgres import get_engine
    with get_engine().connect() as c:
        c.execute(text("SELECT 1"))


def _mongo():
    from .mongo import get_mongo_client
    get_mongo_client().admin.command("ping")


def _redis():
    from .redis_client import get_redis
    get_redis().ping()


def _es():
    from .elastic import get_elasticsearch
    if not get_elasticsearch().ping():
        raise DatabaseConnectionError("ping failed")


def _neo4j():
    from .neo4j_client import get_neo4j_driver
    get_neo4j_driver().verify_connectivity()


CHECKS = {
    "relational": _pg,
    "mongodb": _mongo,
    "redis": _redis,
    "elasticsearch": _es,
    "neo4j": _neo4j,
}


def check_all() -> dict[str, dict]:
    """Returns {name: {"ok": bool, "error": str | None}} - never raises."""
    result = {}
    for name, fn in CHECKS.items():
        try:
            fn()
            result[name] = {"ok": True, "error": None}
        except Exception as exc:
            result[name] = {"ok": False, "error": str(exc)[:200]}
    return result


if __name__ == "__main__":
    import json
    print(json.dumps(check_all(), indent=2))

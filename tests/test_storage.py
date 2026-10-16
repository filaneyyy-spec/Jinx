import asyncio

from jinx_bot.storage import Database


async def test_registration_persists_across_restart_and_updates_without_duplicate(tmp_path):
    path = tmp_path / "nested" / "bot.sqlite3"
    db = Database(path)
    await db.initialize()
    await db.upsert_user(42, "old_name", "First")
    first = await db.get_user(42)
    assert first is not None
    await db.close()

    reopened = Database(path)
    await reopened.initialize()
    await reopened.upsert_user(42, None, "Updated")
    updated = await reopened.get_user(42)
    assert updated.telegram_id == 42
    assert updated.username is None
    assert updated.full_name == "Updated"
    assert updated.created_at == first.created_at
    assert updated.updated_at >= first.updated_at
    assert await reopened.get_user(999) is None
    await reopened.close()


async def test_concurrent_first_visits_are_safe(tmp_path):
    db = Database(tmp_path / "bot.sqlite3")
    await db.initialize()
    await asyncio.gather(*(db.upsert_user(42, "alice", "Alice") for _ in range(12)))
    user = await db.get_user(42)
    assert user is not None
    assert user.full_name == "Alice"
    import sqlite3

    with sqlite3.connect(tmp_path / "bot.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    await db.close()

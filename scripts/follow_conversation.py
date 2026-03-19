#!/usr/bin/env python3
import argparse
import sqlite3
import time
from pathlib import Path


def db_path(raw: str) -> str:
    if raw.startswith('sqlite:///'):
        return raw.replace('sqlite:///', '', 1)
    return raw


def latest_call_sid(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT call_sid FROM live_transcripts WHERE call_sid IS NOT NULL AND call_sid != '' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def run(database: str, call_sid: str | None, watch: bool, interval: float) -> None:
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row

    sid = call_sid or latest_call_sid(conn)
    if not sid:
        print('Aucun call_sid detecte dans live_transcripts.')
        return

    print(f'Suivi conversation call_sid={sid}')
    last_id = 0

    while True:
        rows = conn.execute(
            """
            SELECT id, speaker, text, created_at
            FROM live_transcripts
            WHERE call_sid = ? AND speaker IN ('user','agent') AND id > ?
            ORDER BY id ASC
            """,
            (sid, last_id),
        ).fetchall()

        for row in rows:
            last_id = max(last_id, int(row['id']))
            speaker = (row['speaker'] or '').lower()
            tag = 'USER' if speaker == 'user' else 'AGENT'
            print(f"[{row['created_at']}] {tag}: {row['text']}")

        if not watch:
            break

        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description='Afficher uniquement la conversation agent/user.')
    parser.add_argument('--db', default='hotel_stock.db', help='Chemin DB sqlite (defaut: hotel_stock.db)')
    parser.add_argument('--call-sid', default=None, help='Call SID specifique (defaut: plus recent)')
    parser.add_argument('--watch', action='store_true', help='Mode suivi en temps reel')
    parser.add_argument('--interval', type=float, default=1.0, help='Intervalle watch en secondes')
    args = parser.parse_args()

    db = db_path(args.db)
    if not Path(db).exists():
        print(f'DB introuvable: {db}')
        return

    run(database=db, call_sid=args.call_sid, watch=args.watch, interval=max(0.2, args.interval))


if __name__ == '__main__':
    main()

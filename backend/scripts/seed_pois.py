"""Seed script to populate a venue with POIs from a JSON or CSV file.

Usage:
    python scripts/seed_pois.py --venue sample_lab
    python scripts/seed_pois.py --venue sample_lab --file data/venues/sample_lab/pois.json
    python scripts/seed_pois.py --venue sample_lab --file data/venues/sample_lab/pois.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# Ensure backend root is on Python path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.session import SessionLocal, init_db
from app.services.poi_service import poi_service
from app.services.venue_service import venue_service


def parse_args():
    parser = argparse.ArgumentParser(description="Bulk seed POIs for an indoor venue.")
    parser.add_argument(
        "--venue",
        type=str,
        default="sample_lab",
        help="Venue ID to seed POIs for (default: 'sample_lab')",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to JSON or CSV file. Defaults to data/venues/<venue>/pois.json or .csv",
    )
    return parser.parse_args()


def load_file_data(file_path: Path):
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif suffix == ".csv":
        items = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append(dict(row))
        return items
    else:
        raise ValueError(f"Unsupported file format '{suffix}'. Use .json or .csv.")


def seed_venue_pois(venue_id: str, file_path_str: str = None):
    init_db()
    venue_service.load_all_venues()

    if file_path_str:
        file_path = Path(file_path_str)
    else:
        venue_dir = venue_service.get_venue_dir(venue_id)
        json_candidate = venue_dir / "pois.json"
        csv_candidate = venue_dir / "pois.csv"
        if json_candidate.exists():
            file_path = json_candidate
        elif csv_candidate.exists():
            file_path = csv_candidate
        else:
            raise FileNotFoundError(
                f"No default POI file found for venue '{venue_id}' at {json_candidate} or {csv_candidate}"
            )

    print(f"Loading POIs for venue '{venue_id}' from: {file_path}")
    raw_data = load_file_data(file_path)
    if not isinstance(raw_data, list):
        raise ValueError("Data file must contain a JSON list or CSV rows of POI objects.")

    db = SessionLocal()
    try:
        count, errors = poi_service.bulk_import(db, venue_id, raw_data)
        print(f"Successfully imported/updated {count} POIs for venue '{venue_id}'.")
        if errors:
            print(f"Encountered {len(errors)} errors:")
            for err in errors:
                print(f"  - {err}")
    finally:
        db.close()


if __name__ == "__main__":
    args = parse_args()
    seed_venue_pois(args.venue, args.file)

"""Verify Python packages, project paths and the supplied Alpine dataset."""
from __future__ import annotations

from pathlib import Path
import platform
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import duckdb
import numpy
import pandas
import pyarrow

from compass.loader import DATA_ROOT, load_products, validate_dataset


def main() -> None:
    print("COMPASS P1 SETUP CHECK")
    print("=" * 60)
    print(f"Python:      {sys.version.split()[0]}")
    print(f"Platform:    {platform.platform()}")
    print(f"Project:     {PROJECT_ROOT}")
    print(f"Dataset:     {DATA_ROOT}")
    print(f"pandas:      {pandas.__version__}")
    print(f"pyarrow:     {pyarrow.__version__}")
    print(f"duckdb:      {duckdb.__version__}")
    print(f"numpy:       {numpy.__version__}")
    print()

    manifest = validate_dataset()
    products = load_products(columns=["product_id", "category", "business_unit"])

    print(f"Registered dataset files: {len(manifest)}")
    print(f"Products loaded:          {len(products):,}")
    print("Example product:")
    print(products.head(1).to_string(index=False))
    print()
    print("PASS: Environment and exact Alpine dataset are ready.")


if __name__ == "__main__":
    main()

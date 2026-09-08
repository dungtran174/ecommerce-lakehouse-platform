"""Clickstream user activity logs generator for E-Commerce Lakehouse.

Generates semi-structured web/mobile clickstream interaction sessions formatted as
Newline Delimited JSON (NDJSON) with:
- Session context (session_id, user_id, user_segment, timestamp ISO 8601 UTC)
- Device telemetry (type, os, browser, version)
- Geo location (city, country VN, coordinates lat/lon)
- Traffic attribution & marketing campaigns (referrer, source, UTM campaign)
- Fine-grained actions array (view, search, add_to_cart, checkout_view, purchase)
- Calculated session metrics (duration_seconds, page_views, actions_count, revenue)
- A/B testing and locale properties

Outputs partitioned files: /logs/ingest_date=YYYY-MM-DD/part_{xxxx}.ndjson
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Sequence

from data_generators.generate_products_customers import VIETNAMESE_PROVINCES

logger = logging.getLogger(__name__)

# Device configurations
DEVICE_TYPES = ["mobile", "desktop", "tablet"]
DEVICE_TYPE_WEIGHTS = [0.65, 0.28, 0.07]

OS_BY_DEVICE = {
    "mobile": [("ios", 0.45), ("android", 0.55)],
    "tablet": [("ios", 0.70), ("android", 0.30)],
    "desktop": [("windows", 0.75), ("macos", 0.20), ("linux", 0.05)],
}

BROWSERS_BY_OS = {
    "ios": [("Safari", 0.85), ("Chrome", 0.15)],
    "android": [("Chrome", 0.90), ("Samsung Internet", 0.10)],
    "windows": [("Chrome", 0.65), ("Edge", 0.25), ("Firefox", 0.10)],
    "macos": [("Safari", 0.55), ("Chrome", 0.40), ("Firefox", 0.05)],
    "linux": [("Chrome", 0.60), ("Firefox", 0.40)],
}

# Geo Coordinates mapping for major Vietnamese cities/provinces
GEO_COORDINATES: dict[str, tuple[float, float]] = {
    "Hà Nội": (21.0285, 105.8542),
    "TP Hồ Chí Minh": (10.8231, 106.6297),
    "Đà Nẵng": (16.0544, 108.2022),
    "Hải Phòng": (20.8449, 106.6881),
    "Cần Thơ": (10.0452, 105.7469),
    "Thừa Thiên Huế": (16.4637, 107.5909),
    "Khánh Hòa": (12.2388, 109.1967),
    "Quảng Ninh": (20.9505, 107.0734),
    "Bình Dương": (11.1667, 106.6667),
    "Đồng Nai": (11.0500, 107.0000),
}

TRAFFIC_SOURCES = [
    ("https://www.google.com.vn", "search_engine", "organic", None),
    ("https://facebook.com", "social_media", "social", "facebook_feed"),
    ("https://instagram.com", "social_media", "social", "insta_story"),
    ("https://tiktok.com", "social_media", "social", "tiktok_influencer"),
    ("direct", "direct", "direct", None),
    ("email", "email", "crm", "weekly_deals"),
    ("https://googleads.g.doubleclick.net", "paid", "cpc", "google_search_ad"),
]
TRAFFIC_WEIGHTS = [0.30, 0.25, 0.15, 0.12, 0.10, 0.05, 0.03]

MARKETING_CAMPAIGNS = [
    "flash_sale_99",
    "back_to_school",
    "payday_megasale",
    "mid_year_festival",
    "weekend_vibes",
    None,
]

USER_SEGMENTS = ["new", "returning", "loyal", "churn_risk"]
USER_SEGMENT_WEIGHTS = [0.45, 0.35, 0.15, 0.05]

SEARCH_KEYWORDS = [
    "laptop văn phòng",
    "áo sơ mi nữ",
    "giày sneaker",
    "nồi chiên không dầu",
    "tai nghe bluetooth",
    "váy dạ hội",
    "bàn phím cơ",
    "kem chống nắng",
    "điện thoại samsung",
    "đồng hồ thông minh",
]


class ClickstreamGenerator:
    """Generates semi-structured clickstream user session logs."""

    def __init__(self, seed: int = 42) -> None:
        """Initialize generator with reproducible seed."""
        self.seed = seed
        self.rng = random.Random(seed)

    def _weighted_choice(
        self, choices_with_weights: Sequence[tuple[Any, float]]
    ) -> Any:
        """Helper to pick an item from (item, weight) tuples."""
        items = [c[0] for c in choices_with_weights]
        weights = [c[1] for c in choices_with_weights]
        return self.rng.choices(items, weights=weights, k=1)[0]

    def generate_session(
        self,
        timestamp: datetime,
        user_id: int | None = None,
        products: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Generate a complete user session with nested telemetry and actions.

        Args:
            timestamp: Start timestamp of the session.
            user_id: Optional registered user primary key.
            products: Optional list of product dicts for realistic interaction.

        Returns:
            Dictionary formatted according to Clickstream NDJSON specifications.
        """
        session_id = f"sess-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:14]}"
        user_segment = self.rng.choices(
            USER_SEGMENTS, weights=USER_SEGMENT_WEIGHTS, k=1
        )[0]

        # Device selection
        device_type = self.rng.choices(DEVICE_TYPES, weights=DEVICE_TYPE_WEIGHTS, k=1)[
            0
        ]
        os_name = self._weighted_choice(OS_BY_DEVICE[device_type])
        browser_name = self._weighted_choice(BROWSERS_BY_OS[os_name])
        version = (
            f"{self.rng.randint(14, 17)}.0"
            if "ios" in os_name
            else f"{self.rng.randint(110, 125)}.0"
        )

        device = {
            "type": device_type,
            "os": os_name,
            "browser": browser_name,
            "version": version,
        }

        # Location selection
        city = self.rng.choice(VIETNAMESE_PROVINCES)
        coords = GEO_COORDINATES.get(
            city,
            (
                round(self.rng.uniform(9.0, 22.0), 4),
                round(self.rng.uniform(103.0, 109.0), 4),
            ),
        )
        location = {
            "city": city,
            "country": "VN",
            "coordinates": {"lat": coords[0], "lon": coords[1]},
        }

        # Attribution & Campaign
        ref, ref_type, source, campaign_name = self.rng.choices(
            TRAFFIC_SOURCES, weights=TRAFFIC_WEIGHTS, k=1
        )[0]
        campaign = (
            campaign_name or self.rng.choice(MARKETING_CAMPAIGNS)
            if self.rng.random() < 0.4
            else None
        )

        # Generate Action Sequence
        actions: list[dict[str, Any]] = []
        action_count = self.rng.randint(2, 10)
        current_time_offset = self.rng.randint(2, 15)
        has_purchase = False
        session_revenue = 0.0
        page_views = 0

        # Available product pool
        prod_pool = list(products) if products else []

        for _ in range(action_count):
            act_type = self.rng.choices(
                [
                    "view",
                    "click",
                    "search",
                    "add_to_cart",
                    "wishlist",
                    "checkout_view",
                    "purchase",
                ],
                weights=[0.45, 0.20, 0.12, 0.10, 0.05, 0.05, 0.03],
                k=1,
            )[0]

            act: dict[str, Any] = {
                "type": act_type,
                "time_offset": current_time_offset,
            }

            if act_type == "search":
                keyword = self.rng.choice(SEARCH_KEYWORDS)
                act["page"] = f"/search?q={keyword.replace(' ', '+')}"
                act["search_term"] = keyword
                page_views += 1

            elif act_type in (
                "view",
                "click",
                "add_to_cart",
                "wishlist",
                "checkout_view",
                "purchase",
            ):
                if prod_pool:
                    prod = self.rng.choice(prod_pool)
                    act["product_id"] = prod["product_id"]
                    act["product_name"] = prod.get("product_name", "Sản phẩm")
                    act["category"] = prod.get("category_id", 1)
                    act["price"] = float(prod.get("price", 100.0))
                else:
                    fake_p_id = self.rng.randint(1, 1000)
                    act["product_id"] = fake_p_id
                    act["product_name"] = f"Sản phẩm {fake_p_id}"
                    act["price"] = round(self.rng.uniform(100.0, 5000.0), 2)

                if act_type == "view":
                    act["page"] = f"/product/{act['product_id']}"
                    page_views += 1
                elif act_type == "checkout_view":
                    act["page"] = "/checkout"
                    page_views += 1
                elif act_type == "purchase":
                    act["page"] = "/checkout/success"
                    act["order_id"] = self.rng.randint(100000, 999999)
                    has_purchase = True
                    session_revenue += float(act.get("price", 0.0))
                    page_views += 1
                else:
                    act["page"] = f"/product/{act['product_id']}"

            actions.append(act)
            current_time_offset += self.rng.randint(5, 45)

        total_duration = current_time_offset + self.rng.randint(3, 30)

        session_metrics = {
            "duration_seconds": total_duration,
            "page_views": max(1, page_views),
            "actions_count": len(actions),
            "has_purchase": has_purchase,
            "revenue": round(session_revenue, 2),
        }

        properties = {
            "ab_test": self.rng.choice(["A", "B"]),
            "language": self.rng.choice(["vi-VN", "en-US"]),
            "currency": "VND",
            "is_mobile": (device_type == "mobile"),
        }

        timestamp_iso = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        return {
            "event_id": f"evt-{uuid.UUID(int=self.rng.getrandbits(128)).hex[:16]}",
            "session_id": session_id,
            "timestamp": timestamp_iso,
            "user_id": user_id,
            "user_segment": user_segment,
            "device": device,
            "location": location,
            "referrer": ref,
            "referrer_type": ref_type,
            "source": source,
            "campaign": campaign,
            "actions": actions,
            "session_metrics": session_metrics,
            "properties": properties,
        }

    def generate_daily_logs(
        self,
        date: datetime,
        session_count: int,
        output_dir: str,
        products: Sequence[dict[str, Any]] | None = None,
        user_ids: Sequence[int] | None = None,
        parts: int = 1,
    ) -> list[str]:
        """Generate partitioned NDJSON files for a specific calendar date.

        Args:
            date: Target date.
            session_count: Number of sessions on this date.
            output_dir: Base directory for log partitions.
            products: Pool of products.
            user_ids: Pool of registered user IDs.
            parts: Number of split part files to write.

        Returns:
            List of written NDJSON file paths.
        """
        date_str = date.strftime("%Y-%m-%d")
        partition_dir = os.path.join(output_dir, f"ingest_date={date_str}")
        os.makedirs(partition_dir, exist_ok=True)

        sessions_per_part = session_count // parts
        remainder = session_count % parts
        file_paths: list[str] = []

        for part_idx in range(parts):
            count = sessions_per_part + (remainder if part_idx == parts - 1 else 0)
            part_filename = f"part_{part_idx:04d}.ndjson"
            part_path = os.path.join(partition_dir, part_filename)

            with open(part_path, "w", encoding="utf-8") as f:
                for _ in range(count):
                    session_time = date + timedelta(
                        seconds=self.rng.randint(0, 86399),
                        microseconds=self.rng.randint(0, 999999),
                    )

                    # 60% of sessions belong to registered users
                    u_id = (
                        self.rng.choice(user_ids)
                        if (user_ids and self.rng.random() < 0.60)
                        else None
                    )

                    session = self.generate_session(
                        timestamp=session_time,
                        user_id=u_id,
                        products=products,
                    )
                    f.write(json.dumps(session, ensure_ascii=False) + "\n")

            file_paths.append(part_path)

        logger.info(
            "Wrote %d sessions across %d parts to %s",
            session_count,
            parts,
            partition_dir,
        )
        return file_paths

    def generate_multi_day_logs(
        self,
        start_date: datetime,
        days: int = 7,
        sessions_per_day: int = 1000,
        output_dir: str = "data_generators/output/clickstream",
        products: Sequence[dict[str, Any]] | None = None,
        user_ids: Sequence[int] | None = None,
        parts_per_day: int = 2,
    ) -> dict[str, list[str]]:
        """Generate partitioned logs across multiple sequential days.

        Args:
            start_date: Starting day.
            days: Number of days.
            sessions_per_day: Sessions per day.
            output_dir: Base directory.
            products: Product pool.
            user_ids: Customer user ID pool.
            parts_per_day: Part files per day folder.

        Returns:
            Dictionary mapping date strings to file lists.
        """
        all_files: dict[str, list[str]] = {}
        for d in range(days):
            current_date = start_date + timedelta(days=d)
            date_key = current_date.strftime("%Y-%m-%d")
            files = self.generate_daily_logs(
                date=current_date,
                session_count=sessions_per_day,
                output_dir=output_dir,
                products=products,
                user_ids=user_ids,
                parts=parts_per_day,
            )
            all_files[date_key] = files

        return all_files


def main() -> None:
    """CLI execution for clickstream logs generator."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Generate NDJSON Clickstream Activity Logs for E-Commerce Platform"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data_generators/output/clickstream",
        help="Base directory for partitioned log files",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to generate (default: 7)",
    )
    parser.add_argument(
        "--sessions-per-day",
        type=int,
        default=1000,
        help="Number of sessions per day (default: 1000)",
    )
    parser.add_argument(
        "--parts-per-day",
        type=int,
        default=2,
        help="Part files per day partition (default: 2)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2026-09-01",
        help="Start date YYYY-MM-DD (default: 2026-09-01)",
    )

    args = parser.parse_args()
    start_dt = datetime.strptime(args.start_date, "%Y-%m-%d")

    generator = ClickstreamGenerator()
    result = generator.generate_multi_day_logs(
        start_date=start_dt,
        days=args.days,
        sessions_per_day=args.sessions_per_day,
        output_dir=args.output_dir,
        parts_per_day=args.parts_per_day,
    )

    total_files = sum(len(f) for f in result.values())
    print(
        f"Generated {total_files} partitioned NDJSON log files across {len(result)} days in {args.output_dir}"
    )


if __name__ == "__main__":
    main()

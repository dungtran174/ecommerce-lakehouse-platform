"""Master entities generator for E-Commerce OLTP.

Generates realistic master datasets for:
- Brands (2,000 records with commercial names, origins, and unique IDs)
- Category (20 e-commerce product categories with Vietnamese descriptions)
- Payment Methods (15 payment methods spanning e-wallets, cards, and bank transfer)

Supports exporting to Bronze CSV landing files and direct seeding via DatabaseConnector.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import random
from typing import Any

from data_generators.db_connector import DatabaseConnector

logger = logging.getLogger(__name__)

# Predefined categories mapping 1-to-1 with the platform specifications
PREDEFINED_CATEGORIES: list[dict[str, Any]] = [
    {
        "category_id": 1,
        "category_display_name": "Nội thất & Trang trí",
        "category_description": (
            "Bàn ghế, giường, tủ và các vật dụng trang trí nội thất."
        ),
    },
    {
        "category_id": 2,
        "category_display_name": "Thời trang nữ",
        "category_description": (
            "Quần áo, váy, túi xách, giày và phụ kiện thời trang cho nữ."
        ),
    },
    {
        "category_id": 3,
        "category_display_name": "Công cụ & Dụng cụ",
        "category_description": ("Dụng cụ sửa chữa, máy khoan, thiết bị kỹ thuật."),
    },
    {
        "category_id": 4,
        "category_display_name": "Thiết bị giáo dục",
        "category_description": (
            "Máy chiếu, bảng thông minh, và các thiết bị hỗ trợ giảng dạy."
        ),
    },
    {
        "category_id": 5,
        "category_display_name": "Game & Giải trí",
        "category_description": ("Máy chơi game, đĩa game, phụ kiện và đồ sưu tầm."),
    },
    {
        "category_id": 6,
        "category_display_name": "Thời trang nam",
        "category_description": (
            "Quần áo, giày dép, phụ kiện thời trang dành cho nam giới."
        ),
    },
    {
        "category_id": 7,
        "category_display_name": "Thể thao & Dã ngoại",
        "category_description": (
            "Đồ thể thao, dụng cụ tập luyện, du lịch và dã ngoại."
        ),
    },
    {
        "category_id": 8,
        "category_display_name": "Sách & Văn phòng phẩm",
        "category_description": ("Sách học, truyện, dụng cụ học tập và đồ văn phòng."),
    },
    {
        "category_id": 9,
        "category_display_name": "Đồ gia dụng",
        "category_description": (
            "Nồi cơm điện, máy xay, nồi chiên không dầu, và các thiết bị nhà bếp."
        ),
    },
    {
        "category_id": 10,
        "category_display_name": "Laptop & Máy tính",
        "category_description": (
            "Bao gồm laptop, PC, linh kiện máy tính và phụ kiện công nghệ."
        ),
    },
    {
        "category_id": 11,
        "category_display_name": "Thực phẩm & Đồ uống",
        "category_description": ("Đồ ăn đóng gói, đồ uống, thực phẩm khô và tươi."),
    },
    {
        "category_id": 12,
        "category_display_name": "Xe cộ & Phụ kiện",
        "category_description": ("Xe máy, xe hơi, và phụ tùng – phụ kiện đi kèm."),
    },
    {
        "category_id": 13,
        "category_display_name": "Điện thoại & Máy tính bảng",
        "category_description": (
            "Các sản phẩm điện thoại thông minh, máy tính bảng và phụ kiện liên quan."
        ),
    },
    {
        "category_id": 14,
        "category_display_name": "Vật nuôi & Thú cưng",
        "category_description": ("Đồ ăn, phụ kiện và sản phẩm chăm sóc thú cưng."),
    },
    {
        "category_id": 15,
        "category_display_name": "Điện tử gia dụng",
        "category_description": (
            "Tivi, loa, máy lạnh, tủ lạnh, và thiết bị điện tử trong gia đình."
        ),
    },
    {
        "category_id": 16,
        "category_display_name": "Trang sức & Đồng hồ",
        "category_description": "Nhẫn, vòng tay, đồng hồ, và phụ kiện cao cấp.",
    },
    {
        "category_id": 17,
        "category_display_name": "Đồ chơi & Mẹ bé",
        "category_description": ("Đồ chơi trẻ em, tã bỉm, sản phẩm chăm sóc mẹ và bé."),
    },
    {
        "category_id": 18,
        "category_display_name": "Y tế & Sức khỏe",
        "category_description": (
            "Sản phẩm y tế, thực phẩm chức năng, dụng cụ chăm sóc sức khỏe."
        ),
    },
    {
        "category_id": 19,
        "category_display_name": "Mỹ phẩm & Làm đẹp",
        "category_description": (
            "Sản phẩm chăm sóc da, trang điểm, nước hoa, và các dụng cụ làm đẹp."
        ),
    },
    {
        "category_id": 20,
        "category_display_name": "Dịch vụ số & Gói đăng ký",
        "category_description": (
            "Các dịch vụ trực tuyến, tài khoản phần mềm và gói đăng ký kỹ thuật số."
        ),
    },
]

# Predefined payment methods mapping 1-to-1 with the platform specifications
PREDEFINED_PAYMENT_METHODS: list[dict[str, Any]] = [
    {
        "payment_method_id": 1,
        "display_name": "Momo",
        "type": "E-Wallet",
        "provider": "M_Service",
    },
    {
        "payment_method_id": 2,
        "display_name": "ZaloPay",
        "type": "E-Wallet",
        "provider": "VNG",
    },
    {
        "payment_method_id": 3,
        "display_name": "ShopeePay",
        "type": "E-Wallet",
        "provider": "Sea Group",
    },
    {
        "payment_method_id": 4,
        "display_name": "VNPay",
        "type": "E-Wallet",
        "provider": "VNPay JSC",
    },
    {
        "payment_method_id": 5,
        "display_name": "Apple Pay",
        "type": "E-Wallet",
        "provider": "Apple",
    },
    {
        "payment_method_id": 6,
        "display_name": "Google Pay",
        "type": "E-Wallet",
        "provider": "Google",
    },
    {
        "payment_method_id": 7,
        "display_name": "Visa",
        "type": "Credit/Debit Card",
        "provider": "Visa Inc.",
    },
    {
        "payment_method_id": 8,
        "display_name": "Mastercard",
        "type": "Credit/Debit Card",
        "provider": "Mastercard Worldwide",
    },
    {
        "payment_method_id": 9,
        "display_name": "JCB",
        "type": "Credit/Debit Card",
        "provider": "JCB International",
    },
    {
        "payment_method_id": 10,
        "display_name": "NAPAS",
        "type": "Domestic Card",
        "provider": "NAPAS",
    },
    {
        "payment_method_id": 11,
        "display_name": "PayPal",
        "type": "Online Payment",
        "provider": "PayPal Holdings",
    },
    {
        "payment_method_id": 12,
        "display_name": "Stripe",
        "type": "Online Payment",
        "provider": "Stripe Inc.",
    },
    {
        "payment_method_id": 13,
        "display_name": "Amazon Pay",
        "type": "Online Payment",
        "provider": "Amazon",
    },
    {
        "payment_method_id": 14,
        "display_name": "COD",
        "type": "Cash",
        "provider": "N/A",
    },
    {
        "payment_method_id": 15,
        "display_name": "Bank Transfer",
        "type": "Bank Transfer",
        "provider": "Various Banks",
    },
]

BRAND_NAME_PREFIXES = [
    "Smart",
    "Eco",
    "Global",
    "Prime",
    "Nova",
    "Apex",
    "Zenith",
    "Aura",
    "Vina",
    "Alpha",
    "Omega",
    "Hyper",
    "Ultra",
    "Pro",
    "Urban",
    "Next",
    "Royal",
    "Pure",
    "Core",
    "Peak",
    "Elite",
    "True",
    "Vital",
    "Modern",
    "Bright",
    "Sunny",
    "Orient",
    "Crown",
    "Star",
    "Swift",
]

BRAND_NAME_ROOTS = [
    "Tech",
    "Life",
    "Wear",
    "Phone",
    "Home",
    "Food",
    "Pharma",
    "Drive",
    "Sound",
    "Craft",
    "Style",
    "Care",
    "Mart",
    "Play",
    "Link",
    "Sense",
    "Trend",
    "Vision",
    "Lab",
    "Sport",
    "Auto",
    "Beauty",
    "Power",
    "Gear",
    "Nature",
]

COUNTRIES_OF_ORIGIN = [
    "Việt Nam",
    "Hàn Quốc",
    "Nhật Bản",
    "Mỹ",
    "Đức",
    "Anh",
    "Thụy Sĩ",
    "Singapore",
    "Thái Lan",
    "Canada",
    "Úc",
    "Pháp",
    "Ý",
    "Trung Quốc",
]


class MasterDataGenerator:
    """Generates and persists master reference entities."""

    def __init__(self, seed: int = 42) -> None:
        """Initialize generator with random seed for reproducibility."""
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_categories(self) -> list[dict[str, Any]]:
        """Return the 20 standard product category records."""
        return list(PREDEFINED_CATEGORIES)

    def generate_payment_methods(self) -> list[dict[str, Any]]:
        """Return the 15 standard payment method records."""
        return list(PREDEFINED_PAYMENT_METHODS)

    def generate_brands(self, count: int = 2000) -> list[dict[str, Any]]:
        """Generate specified count of unique brands.

        Args:
            count: Number of brand entities to generate (default: 2000).

        Returns:
            List of dictionaries with keys: brand_id, brand_name, brand_origin.
        """
        brands: list[dict[str, Any]] = []
        generated_ids: set[str] = set()

        prefix_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        for i in range(count):
            # Generate deterministic unique brand ID like AEL19310
            while True:
                p1 = self.rng.choice(prefix_letters)
                p2 = self.rng.choice(prefix_letters)
                p3 = self.rng.choice(prefix_letters)
                num = (i * 37 + 19310 + self.rng.randint(100, 999)) % 90000 + 10000
                brand_id = f"{p1}{p2}{p3}{num}"
                if brand_id not in generated_ids:
                    generated_ids.add(brand_id)
                    break

            prefix = self.rng.choice(BRAND_NAME_PREFIXES)
            root = self.rng.choice(BRAND_NAME_ROOTS)
            brand_name = f"{prefix} {root}"

            origin = self.rng.choice(COUNTRIES_OF_ORIGIN)

            brands.append(
                {
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "brand_origin": origin,
                }
            )

        return brands

    def export_to_csv(self, output_dir: str, brand_count: int = 2000) -> dict[str, str]:
        """Export generated master data into Bronze CSV snapshot files.

        Args:
            output_dir: Directory where CSV files will be saved.
            brand_count: Number of brands to generate.

        Returns:
            Dictionary mapping table names to generated CSV filepaths.
        """
        os.makedirs(output_dir, exist_ok=True)
        file_paths = {}

        # 1. Export brands
        brands = self.generate_brands(count=brand_count)
        brands_path = os.path.join(output_dir, "brands_snapshot.csv")
        with open(brands_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["brand_id", "brand_name", "brand_origin"]
            )
            writer.writeheader()
            writer.writerows(brands)
        file_paths["brands"] = brands_path
        logger.info("Exported %d brands to %s", len(brands), brands_path)

        # 2. Export category
        categories = self.generate_categories()
        category_path = os.path.join(output_dir, "category_snapshot.csv")
        with open(category_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "category_id",
                    "category_display_name",
                    "category_description",
                ],
            )
            writer.writeheader()
            writer.writerows(categories)
        file_paths["category"] = category_path
        logger.info("Exported %d categories to %s", len(categories), category_path)

        # 3. Export payment_method
        payments = self.generate_payment_methods()
        payments_path = os.path.join(output_dir, "payment_method_snapshot.csv")
        with open(payments_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "payment_method_id",
                    "display_name",
                    "type",
                    "provider",
                ],
            )
            writer.writeheader()
            writer.writerows(payments)
        file_paths["payment_method"] = payments_path
        logger.info("Exported %d payment methods to %s", len(payments), payments_path)

        return file_paths

    def seed_to_database(
        self, connector: DatabaseConnector, brand_count: int = 2000
    ) -> dict[str, int]:
        """Insert master entities directly into the relational database.

        Args:
            connector: Active DatabaseConnector instance.
            brand_count: Number of brands to generate and insert.

        Returns:
            Dictionary with inserted counts per table.
        """
        connector.init_schema()

        # Seed categories
        categories = self.generate_categories()
        cat_rows = [
            (
                c["category_id"],
                c["category_display_name"],
                c["category_description"],
            )
            for c in categories
        ]
        inserted_cat = connector.bulk_insert(
            table="category",
            columns=[
                "category_id",
                "category_display_name",
                "category_description",
            ],
            records=cat_rows,
        )

        # Seed payment methods
        payments = self.generate_payment_methods()
        pay_rows = [
            (
                p["payment_method_id"],
                p["display_name"],
                p["type"],
                p["provider"],
            )
            for p in payments
        ]
        inserted_pay = connector.bulk_insert(
            table="payment_method",
            columns=["payment_method_id", "display_name", "type", "provider"],
            records=pay_rows,
        )

        # Seed brands
        brands = self.generate_brands(count=brand_count)
        brand_rows = [
            (b["brand_id"], b["brand_name"], b["brand_origin"]) for b in brands
        ]
        inserted_brands = connector.bulk_insert(
            table="brands",
            columns=["brand_id", "brand_name", "brand_origin"],
            records=brand_rows,
        )

        return {
            "category": inserted_cat,
            "payment_method": inserted_pay,
            "brands": inserted_brands,
        }


def main() -> None:
    """CLI execution for generating master datasets."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Generate master entities for E-Commerce Lakehouse Platform"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data_generators/output",
        help="Directory to save snapshot CSV files",
    )
    parser.add_argument(
        "--brand-count",
        type=int,
        default=2000,
        help="Total brands to generate (default: 2000)",
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Whether to insert records directly into database",
    )

    args = parser.parse_args()
    generator = MasterDataGenerator()

    paths = generator.export_to_csv(
        output_dir=args.output_dir, brand_count=args.brand_count
    )
    for name, path in paths.items():
        print(f"Created {name}: {path}")

    if args.seed_db:
        connector = DatabaseConnector()
        with connector:
            stats = generator.seed_to_database(
                connector=connector, brand_count=args.brand_count
            )
            print(f"Database seeded successfully: {stats}")


if __name__ == "__main__":
    main()

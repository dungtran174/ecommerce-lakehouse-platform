"""Product catalog and customer profile generator for E-Commerce OLTP.

Generates realistic entities:
- Products: 1,000 records categorized across 20 industries with foreign keys
  to brands and categories.
- Customers: 100,000 customer profiles with realistic Vietnamese names,
  phone numbers, emails, loyalty tiers, and geographic provinces.

Supports exporting to Bronze CSV snapshots and database seeding via DatabaseConnector.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any, Sequence

from data_generators.db_connector import DatabaseConnector
from data_generators.generate_master_data import (
    PREDEFINED_CATEGORIES,
    MasterDataGenerator,
)

logger = logging.getLogger(__name__)

# Vietnamese naming components
VIETNAMESE_LAST_NAMES = [
    "Nguyễn",
    "Trần",
    "Lê",
    "Phạm",
    "Hoàng",
    "Huỳnh",
    "Phan",
    "Vũ",
    "Võ",
    "Đặng",
    "Bùi",
    "Đỗ",
    "Hồ",
    "Ngô",
    "Dương",
    "Lý",
    "Đinh",
    "Đoàn",
    "Lâm",
    "Trịnh",
    "Mai",
    "Đào",
    "Cao",
    "Hà",
    "Lương",
]

VIETNAMESE_MALE_FIRST_NAMES = [
    "Hùng",
    "Huy",
    "Quang",
    "Trọng",
    "Dũng",
    "Nam",
    "Minh",
    "Tuấn",
    "Đạt",
    "Hiếu",
    "Sơn",
    "Tùng",
    "Long",
    "Bảo",
    "Phúc",
    "Hải",
    "Thành",
    "Việt",
    "Trung",
    "Phong",
]

VIETNAMESE_FEMALE_FIRST_NAMES = [
    "Yến",
    "Lan",
    "Hồng",
    "Vi",
    "Mai",
    "Trang",
    "Phương",
    "Hương",
    "Linh",
    "Thảo",
    "Hà",
    "Ngọc",
    "Tuyết",
    "Quỳnh",
    "Vy",
    "Oanh",
    "Thủy",
    "Giang",
    "Nga",
    "Duyên",
]

CUSTOMER_TIERS = ["Bronze", "Silver", "Gold", "Platinum"]
CUSTOMER_TIER_WEIGHTS = [0.60, 0.25, 0.12, 0.03]

# 63 Provinces and Cities of Vietnam
VIETNAMESE_PROVINCES = [
    "Hà Nội",
    "TP Hồ Chí Minh",
    "Đà Nẵng",
    "Hải Phòng",
    "Cần Thơ",
    "An Giang",
    "Bà Rịa - Vũng Tàu",
    "Bắc Giang",
    "Bắc Kạn",
    "Bạc Liêu",
    "Bắc Ninh",
    "Bến Tre",
    "Bình Định",
    "Bình Dương",
    "Bình Phước",
    "Bình Thuận",
    "Cà Mau",
    "Cao Bằng",
    "Đắk Lắk",
    "Đắk Nông",
    "Điện Biên",
    "Đồng Nai",
    "Đồng Tháp",
    "Gia Lai",
    "Hà Giang",
    "Hà Nam",
    "Hà Tĩnh",
    "Hải Dương",
    "Hậu Giang",
    "Hòa Bình",
    "Hưng Yên",
    "Khánh Hòa",
    "Kiên Giang",
    "Kon Tum",
    "Lai Châu",
    "Lâm Đồng",
    "Lạng Sơn",
    "Lào Cai",
    "Long An",
    "Nam Định",
    "Nghệ An",
    "Ninh Bình",
    "Ninh Thuận",
    "Phú Thọ",
    "Phú Yên",
    "Quảng Bình",
    "Quảng Nam",
    "Quảng Ngãi",
    "Quảng Ninh",
    "Quảng Trị",
    "Sóc Trăng",
    "Sơn La",
    "Tây Ninh",
    "Thái Bình",
    "Thái Nguyên",
    "Thanh Hóa",
    "Thừa Thiên Huế",
    "Tiền Giang",
    "Trà Vinh",
    "Tuyên Quang",
    "Vĩnh Long",
    "Vĩnh Phúc",
    "Yên Bái",
]

# Product name templates per category ID
PRODUCT_TEMPLATES: dict[int, list[str]] = {
    1: [
        "Bàn ăn gỗ sồi",
        "Ghế sofa da cao cấp",
        "Đèn chùm pha lê",
        "Kệ sách hiện đại",
        "Tủ quần áo thông minh",
    ],
    2: [
        "Đầm dạ hội lụa",
        "Áo sơ mi công sở",
        "Túi xách nữ thời thượng",
        "Giày cao gót thanh lịch",
        "Chân váy chữ A",
    ],
    3: [
        "Máy khoan pin đa năng",
        "Bộ cờ lê lục giác",
        "Tua vít đa năng",
        "Thước cuộn laser",
        "Máy cưa cầm tay",
    ],
    4: [
        "Máy chiếu tương tác",
        "Bảng thông minh cảm ứng",
        "Bút thuyết trình không dây",
        "Kính hiển vi quang học",
        "Kệ đồ dùng học tập",
    ],
    5: [
        "Tay cầm chơi game không dây",
        "Máy chơi game Console",
        "Bàn phím cơ RGB",
        "Tai nghe Gaming vòm 7.1",
        "Ghế gaming công thái học",
    ],
    6: [
        "Áo polo nam thoáng khí",
        "Quần tây công sở",
        "Áo khoác gió thể thao",
        "Ví da nam cao cấp",
        "Thắt lưng da bò",
    ],
    7: [
        "Lều cắm trại chống nước",
        "Vợt cầu lông Pro",
        "Giày chạy bộ êm ái",
        "Thảm tập yoga chống trượt",
        "Balo du lịch dã ngoại",
    ],
    8: [
        "Sổ tay bìa da cao cấp",
        "Bút ký kim loại",
        "Bút chì định vị công nghệ",
        "Bộ dụng cụ vẽ mỹ thuật",
        "Bìa tài liệu hồ sơ",
    ],
    9: [
        "Nồi chiên không dầu điện tử",
        "Nồi cơm điện cao tần",
        "Máy xay sinh tố đa năng",
        "Bếp từ đôi thông minh",
        "Ấm siêu tốc giữ nhiệt",
    ],
    10: [
        "MSI Stealth 14 Studio",
        "MacBook Pro M2 Max",
        "Màn hình đồ họa 4K",
        "Ổ cứng di động SSD 1TB",
        "Chuột không dây công thái học",
    ],
    11: [
        "Bánh Oreo Socola Pie",
        "Hạt điều sấy nguyên vị",
        "Cà phê phin nguyên chất",
        "Mật ong rừng tự nhiên",
        "Trà ô long thượng hạng",
    ],
    12: [
        "Mũ bảo hiểm fullface",
        "Dầu nhớt tổng hợp cao cấp",
        "Găng tay đi xe chống nước",
        "Bơm lốp mini tự động",
        "Bạt phủ xe chuyên dụng",
    ],
    13: [
        "Điện thoại thông minh Pro Max",
        "Máy tính bảng Retina",
        "Sạc dự phòng sạc nhanh 65W",
        "Ốp lưng chống sốc",
        "Kính cường lực kháng va đập",
    ],
    14: [
        "Hạt dinh dưỡng cho mèo",
        "Nhà cây cho mèo cào móng",
        "Dây dắt trợ lực cho chó",
        "Sữa tắm dưỡng lông thú cưng",
        "Khay vệ sinh thông minh",
    ],
    15: [
        "Smart TV OLED 65 inch",
        "Loa thanh Soundbar Dolby Atmos",
        "Điều hòa Inverter tiết kiệm điện",
        "Máy giặt sấy tự động",
        "Tủ lạnh Side by Side",
    ],
    16: [
        "Đồng hồ Thụy Sĩ sang trọng",
        "Nhẫn kim cương nhân tạo",
        "Dây chuyền bạc đính đá",
        "Lắc tay thời trang",
        "Bông tai ngọc trai",
    ],
    17: [
        "Ghế ăn dặm trẻ em",
        "Bộ đồ chơi xếp hình thông minh",
        "Xe đẩy gấp gọn siêu nhẹ",
        "Máy hâm sữa tiệt trùng",
        "Tã bỉm organic thấm hút",
    ],
    18: [
        "Máy đo huyết áp điện tử",
        "Viên uống Vitamin C tăng đề kháng",
        "Nhiệt kế hồng ngoại đo trán",
        "Máy xông khí dung gia đình",
        "Khẩu trang y tế 4 lớp",
    ],
    19: [
        "Serum dưỡng sáng mờ thâm",
        "Kem chống nắng phổ rộng SPF50",
        "Son lì mịn môi không lem",
        "Nước tẩy trang dịu nhẹ",
        "Mặt nạ phục hồi da cấp ẩm",
    ],
    20: [
        "Gói bản quyền phần mềm 1 năm",
        "Thẻ nạp dịch vụ xem phim",
        "Gói lưu trữ đám mây 2TB",
        "Khóa học trực tuyến chuyên sâu",
        "Gói bảo hành điện tử mở rộng",
    ],
}


class ProductCustomerGenerator:
    """Generates synthetic products and customer profiles for the OLTP system."""

    def __init__(self, seed: int = 42) -> None:
        """Initialize generator with reproducible seed."""
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_products(
        self,
        brand_ids: Sequence[str],
        category_ids: Sequence[int] | None = None,
        count: int = 1000,
    ) -> list[dict[str, Any]]:
        """Generate specified number of products with valid foreign keys.

        Args:
            brand_ids: List of existing brand identifiers.
            category_ids: List of existing category IDs (default: 1..20).
            count: Total products to generate (default: 1000).

        Returns:
            List of product records.
        """
        if not brand_ids:
            raise ValueError("brand_ids must not be empty.")

        cats = (
            list(category_ids)
            if category_ids
            else [c["category_id"] for c in PREDEFINED_CATEGORIES]
        )

        products: list[dict[str, Any]] = []
        base_date = datetime(2023, 1, 1)

        for i in range(1, count + 1):
            category_id = self.rng.choice(cats)
            brand_id = self.rng.choice(brand_ids)

            templates = PRODUCT_TEMPLATES.get(
                category_id, ["Sản phẩm tiêu dùng cao cấp"]
            )
            base_name = self.rng.choice(templates)
            suffix_num = self.rng.randint(10, 990)
            product_name = f"{base_name} {suffix_num}"

            desc = f"{product_name} chính hãng, bảo hành toàn quốc."

            # Generate price range between 50,000 VND and 45,000,000 VND
            # Represented as formatted decimal values (e.g. 350.00 to 45000.00)
            price_val = round(self.rng.uniform(150.0, 35000.0), 2)

            created_delta = timedelta(days=self.rng.randint(0, 700))
            created_at = base_date + created_delta
            updated_at = created_at + timedelta(days=self.rng.randint(0, 60))

            products.append(
                {
                    "product_id": i,
                    "product_name": product_name,
                    "product_description": desc,
                    "price": price_val,
                    "category_id": category_id,
                    "brand_id": brand_id,
                    "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        logger.info("Generated %d product records.", len(products))
        return products

    def generate_customers(
        self,
        count: int = 100000,
        start_id: int = 100000,
    ) -> list[dict[str, Any]]:
        """Generate realistic Vietnamese customer profiles.

        Args:
            count: Number of customer profiles to generate (default: 100,000).
            start_id: Starting primary key index (default: 100,000).

        Returns:
            List of customer profile records.
        """
        customers: list[dict[str, Any]] = []
        base_date = datetime(2023, 1, 1)

        for i in range(count):
            customer_id = start_id + i

            is_male = self.rng.random() < 0.5
            gender = "Nam" if is_male else "Nữ"

            last_name = self.rng.choice(VIETNAMESE_LAST_NAMES)
            first_name = self.rng.choice(
                VIETNAMESE_MALE_FIRST_NAMES
                if is_male
                else VIETNAMESE_FEMALE_FIRST_NAMES
            )

            # Generate realistic email
            clean_first = first_name.lower().replace(" ", "")
            email_domains = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com"]
            domain = self.rng.choice(email_domains)
            email_num = self.rng.randint(100, 9999)
            email = f"{clean_first}{customer_id % 10000}{email_num}@{domain}"

            # Generate phone number (09xx, 08xx, 07xx, 03xx)
            prefixes = ["090", "091", "098", "086", "088", "077", "038", "039"]
            prefix = self.rng.choice(prefixes)
            phone_num = f"{prefix}{self.rng.randint(1000000, 9999999)}"

            # Loyalty tier selection according to probability weights
            tier = self.rng.choices(
                CUSTOMER_TIERS, weights=CUSTOMER_TIER_WEIGHTS, k=1
            )[0]

            address = self.rng.choice(VIETNAMESE_PROVINCES)

            created_delta = timedelta(days=self.rng.randint(0, 750))
            created_at = base_date + created_delta
            updated_at = created_at + timedelta(days=self.rng.randint(0, 90))

            customers.append(
                {
                    "customer_id": customer_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone_number": phone_num,
                    "gender": gender,
                    "tire": tier,
                    "address": address,
                    "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

        logger.info("Generated %d customer profiles.", len(customers))
        return customers

    def export_to_csv(
        self,
        output_dir: str,
        brand_ids: Sequence[str],
        product_count: int = 1000,
        customer_count: int = 100000,
        customer_chunk_size: int = 25000,
    ) -> dict[str, str]:
        """Export products and customers to Bronze snapshot CSV files.

        Args:
            output_dir: Destination folder.
            brand_ids: List of available brand IDs.
            product_count: Total products.
            customer_count: Total customers.
            customer_chunk_size: Chunk size to stream customers without high memory usage.

        Returns:
            Dictionary of exported file paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        file_paths = {}

        # 1. Export Products
        products = self.generate_products(brand_ids=brand_ids, count=product_count)
        products_path = os.path.join(output_dir, "products_snapshot.csv")
        with open(products_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "product_id",
                    "product_name",
                    "product_description",
                    "price",
                    "category_id",
                    "brand_id",
                    "created_at",
                    "updated_at",
                ],
            )
            writer.writeheader()
            writer.writerows(products)
        file_paths["products"] = products_path
        logger.info("Exported %d products to %s", len(products), products_path)

        # 2. Export Customers in chunks to keep memory usage minimal
        customers_path = os.path.join(output_dir, "customers_snapshot.csv")
        with open(customers_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "customer_id",
                    "first_name",
                    "last_name",
                    "email",
                    "phone_number",
                    "gender",
                    "tire",
                    "address",
                    "created_at",
                    "updated_at",
                ],
            )
            writer.writeheader()

            total_written = 0
            for start_idx in range(0, customer_count, customer_chunk_size):
                chunk_len = min(customer_chunk_size, customer_count - start_idx)
                chunk_customers = self.generate_customers(
                    count=chunk_len, start_id=100000 + start_idx
                )
                writer.writerows(chunk_customers)
                total_written += chunk_len

        file_paths["customers"] = customers_path
        logger.info(
            "Exported %d customers to %s", total_written, customers_path
        )

        return file_paths

    def seed_to_database(
        self,
        connector: DatabaseConnector,
        brand_ids: Sequence[str],
        product_count: int = 1000,
        customer_count: int = 5000,
    ) -> dict[str, int]:
        """Directly insert products and customers into the database.

        Args:
            connector: Active DatabaseConnector instance.
            brand_ids: List of available brand IDs.
            product_count: Number of products to seed.
            customer_count: Number of customers to seed.

        Returns:
            Dictionary with counts of inserted rows.
        """
        # Ensure schema is ready
        connector.init_schema()

        # Seed products
        products = self.generate_products(brand_ids=brand_ids, count=product_count)
        prod_rows = [
            (
                p["product_id"],
                p["product_name"],
                p["product_description"],
                p["price"],
                p["category_id"],
                p["brand_id"],
                p["created_at"],
                p["updated_at"],
            )
            for p in products
        ]
        inserted_prods = connector.bulk_insert(
            table="products",
            columns=[
                "product_id",
                "product_name",
                "product_description",
                "price",
                "category_id",
                "brand_id",
                "created_at",
                "updated_at",
            ],
            records=prod_rows,
        )

        # Seed customers
        customers = self.generate_customers(count=customer_count)
        cust_rows = [
            (
                c["customer_id"],
                c["first_name"],
                c["last_name"],
                c["email"],
                c["phone_number"],
                c["gender"],
                c["tire"],
                c["address"],
                c["created_at"],
                c["updated_at"],
            )
            for c in customers
        ]
        inserted_custs = connector.bulk_insert(
            table="customers",
            columns=[
                "customer_id",
                "first_name",
                "last_name",
                "email",
                "phone_number",
                "gender",
                "tire",
                "address",
                "created_at",
                "updated_at",
            ],
            records=cust_rows,
        )

        return {"products": inserted_prods, "customers": inserted_custs}


def main() -> None:
    """CLI execution for products and customers generator."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Generate products and customers for E-Commerce Platform"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data_generators/output",
        help="Directory to save snapshot CSV files",
    )
    parser.add_argument(
        "--product-count",
        type=int,
        default=1000,
        help="Number of products to generate (default: 1000)",
    )
    parser.add_argument(
        "--customer-count",
        type=int,
        default=100000,
        help="Number of customers to generate (default: 100000)",
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Whether to seed into the relational database",
    )

    args = parser.parse_args()

    # Generate or obtain brands first for FK reference
    master_gen = MasterDataGenerator()
    brands = master_gen.generate_brands(count=2000)
    brand_ids = [b["brand_id"] for b in brands]

    prod_cust_gen = ProductCustomerGenerator()
    paths = prod_cust_gen.export_to_csv(
        output_dir=args.output_dir,
        brand_ids=brand_ids,
        product_count=args.product_count,
        customer_count=args.customer_count,
    )
    for name, path in paths.items():
        print(f"Created {name}: {path}")

    if args.seed_db:
        connector = DatabaseConnector()
        with connector:
            master_gen.seed_to_database(connector=connector, brand_count=2000)
            stats = prod_cust_gen.seed_to_database(
                connector=connector,
                brand_ids=brand_ids,
                product_count=args.product_count,
                customer_count=min(args.customer_count, 10000),
            )
            print(f"Database seeded successfully: {stats}")


if __name__ == "__main__":
    main()

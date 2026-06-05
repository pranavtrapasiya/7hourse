"""
Generate dummy test data: 10 categories, 50 subcategories, 50 products,
50 inventory entries with images and videos.
"""
import os
import random
import shutil
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.files import File

from aps.models import (
    Category, SubCategory, Product,
    WarehouseInventory, CartonImage, InventoryProductImage, InventoryVideo,
)

# ── Test data ─────────────────────────────────────────────────────────────────

CATEGORIES = {
    "Construction Materials": ["Cement", "Sand", "Bricks", "Steel Rods", "Tiles"],
    "Electrical Components": ["Wires", "Switches", "Circuit Breakers", "LED Lights", "Panels"],
    "Plumbing Supplies": ["Pipes", "Valves", "Fittings", "Water Tanks", "Drainage Systems"],
    "Industrial Machinery": ["Compressors", "Generators", "Motors", "Pumps", "Conveyors"],
    "Safety Equipment": ["Helmets", "Gloves", "Safety Shoes", "Harnesses", "Safety Glasses"],
    "Agriculture Equipment": ["Tractors", "Seed Drills", "Sprayers", "Harvesters", "Cultivators"],
    "Automotive Parts": ["Batteries", "Tyres", "Brake Systems", "Filters", "Suspension Parts"],
    "HVAC Systems": ["Air Conditioners", "Ventilation Fans", "Ducting", "Chillers", "Cooling Towers"],
    "Furniture Products": ["Office Chairs", "Work Tables", "Storage Cabinets", "Conference Tables", "Shelving Units"],
    "Packaging Materials": ["Carton Boxes", "Plastic Wrap", "Pallets", "Labels", "Packaging Tape"],
}

LOCATIONS = [
    "Warehouse A - Surat",
    "Warehouse B - Ahmedabad",
    "Warehouse C - Vadodara",
    "Warehouse D - Rajkot",
    "Warehouse E - Mumbai",
]

PRODUCT_TEMPLATES = {
    "Cement": ("Premium Portland Cement 50kg", "High-grade OPC cement for structural work"),
    "Sand": ("River Sand Fine Grade", "Washed fine sand for plastering and masonry"),
    "Bricks": ("AAC Lightweight Bricks", "Autoclaved aerated concrete blocks"),
    "Steel Rods": ("TMT Steel Bar 12mm", "Fe-500 grade TMT reinforcement bars"),
    "Tiles": ("Vitrified Floor Tiles 600x600", "Glossy double-charge vitrified tiles"),
    "Wires": ("Copper Electrical Wire 2.5mm", "PVC insulated copper conductor"),
    "Switches": ("Modular Switch 16A", "Heavy duty modular switch with indicator"),
    "Circuit Breakers": ("MCB 32A Triple Pole", "Miniature circuit breaker TP"),
    "LED Lights": ("LED Panel Light 40W", "Slim square panel 2x2 feet"),
    "Panels": ("Distribution Board 8-Way", "MCB enclosure with busbar"),
    "Pipes": ("CPVC Pipe 1 inch", "Hot & cold water supply pipe"),
    "Valves": ("Ball Valve Brass 1 inch", "Full bore brass ball valve"),
    "Fittings": ("CPVC Elbow 1 inch", "90-degree elbow fitting"),
    "Water Tanks": ("Plastic Water Tank 1000L", "Triple layer UV protected tank"),
    "Drainage Systems": ("PVC Drainage Pipe 4 inch", "SWR pipe for waste water"),
    "Compressors": ("Air Compressor 5HP", "Reciprocating piston compressor"),
    "Generators": ("Diesel Generator 15KVA", "Silent canopy DG set"),
    "Motors": ("Electric Motor 3HP", "Three phase induction motor"),
    "Pumps": ("Centrifugal Pump 2HP", "Self priming water pump"),
    "Conveyors": ("Belt Conveyor 10ft", "PVC flat belt conveyor system"),
    "Helmets": ("Industrial Safety Helmet", "HDPE shell with ratchet adjustment"),
    "Gloves": ("Cut Resistant Gloves", "Level 5 HPPE liner nitrile coated"),
    "Safety Shoes": ("Steel Toe Safety Boot", "Oil resistant PU sole boots"),
    "Harnesses": ("Full Body Harness", "5-point harness with lanyard"),
    "Safety Glasses": ("Anti-Fog Safety Goggles", "Polycarbonate UV400 lens"),
    "Tractors": ("Mini Tractor 24HP", "4WD compact utility tractor"),
    "Seed Drills": ("Multi-Crop Seed Drill", "9 tyne automatic seed drill"),
    "Sprayers": ("Battery Sprayer 16L", "Rechargeable knapsack sprayer"),
    "Harvesters": ("Mini Rice Harvester", "Walk-behind combine harvester"),
    "Cultivators": ("Power Weeder 5HP", "Petrol engine rotary cultivator"),
    "Batteries": ("Car Battery 65Ah", "Maintenance free lead acid"),
    "Tyres": ("Radial Tyre 185/65R15", "Tubeless all season tyre"),
    "Brake Systems": ("Disc Brake Pad Set", "Semi-metallic front brake pads"),
    "Filters": ("Engine Oil Filter", "Spin-on canister type filter"),
    "Suspension Parts": ("Shock Absorber Front", "Gas charged twin tube damper"),
    "Air Conditioners": ("Split AC 1.5 Ton 5 Star", "Inverter split air conditioner"),
    "Ventilation Fans": ("Industrial Exhaust Fan 18in", "Heavy duty wall mount exhaust"),
    "Ducting": ("GI Duct 12x8 inch", "Galvanized iron rectangular duct"),
    "Chillers": ("Water Chiller 5TR", "Scroll compressor water chiller"),
    "Cooling Towers": ("FRP Cooling Tower 10TR", "Counter flow induced draft tower"),
    "Office Chairs": ("Ergonomic Mesh Chair", "High back with lumbar support"),
    "Work Tables": ("Steel Work Table 4x2ft", "Heavy gauge powder coated table"),
    "Storage Cabinets": ("Metal Storage Cupboard", "4-shelf lockable steel almirah"),
    "Conference Tables": ("Boardroom Table 8 Seater", "Laminated MDF conference table"),
    "Shelving Units": ("Slotted Angle Rack 5 Tier", "Adjustable boltless shelving"),
    "Carton Boxes": ("Corrugated Box 18x12x12", "5-ply heavy duty carton"),
    "Plastic Wrap": ("Stretch Wrap Film 18in", "23 micron hand grade pallet wrap"),
    "Pallets": ("Wooden Pallet 48x40", "4-way entry heat treated pallet"),
    "Labels": ("Thermal Barcode Labels 4x6", "Direct thermal shipping labels"),
    "Packaging Tape": ("BOPP Tape 2in Brown", "Acrylic adhesive packaging tape"),
}

MEDIA_DIR = r"D:\downloads\Aps\Test"


class Command(BaseCommand):
    help = "Generate 10 categories, 50 subcategories, 50 products with inventory + media"

    def handle(self, *args, **options):
        # ── Collect media files ──────────────────────────────
        images = sorted([
            os.path.join(MEDIA_DIR, f) for f in os.listdir(MEDIA_DIR)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
        ])
        videos = sorted([
            os.path.join(MEDIA_DIR, f) for f in os.listdir(MEDIA_DIR)
            if f.lower().endswith(('.mp4', '.mov', '.webm'))
        ])

        if not images:
            self.stderr.write("No images found in Test folder!")
            return
        if not videos:
            self.stderr.write("No videos found in Test folder!")
            return

        self.stdout.write(f"Found {len(images)} image(s), {len(videos)} video(s)")

        stats = {
            'categories_created': 0, 'categories_skipped': 0,
            'subcategories_created': 0, 'subcategories_skipped': 0,
            'products_created': 0, 'products_skipped': 0,
            'locations_created': 0,
            'images_assigned': 0, 'videos_assigned': 0,
        }

        product_index = 0

        for cat_name, subcats in CATEGORIES.items():
            # ── Category ──
            cat, created = Category.objects.get_or_create(name=cat_name)
            if created:
                stats['categories_created'] += 1
                self.stdout.write(self.style.SUCCESS(f"  + Category: {cat_name}"))
            else:
                stats['categories_skipped'] += 1
                self.stdout.write(f"  = Category exists: {cat_name}")

            for sub_name in subcats:
                # ── Subcategory ──
                sub, created = SubCategory.objects.get_or_create(
                    name=sub_name, category=cat
                )
                if created:
                    stats['subcategories_created'] += 1
                    self.stdout.write(self.style.SUCCESS(f"    + Subcategory: {sub_name}"))
                else:
                    stats['subcategories_skipped'] += 1
                    self.stdout.write(f"    = Subcategory exists: {sub_name}")

                # ── Product ──
                template = PRODUCT_TEMPLATES.get(sub_name)
                prod_name = template[0] if template else f"{sub_name} Product"
                prod_desc = template[1] if template else f"Standard {sub_name.lower()} product"

                existing = Product.objects.filter(
                    product_name=prod_name, category=cat, subcategory=sub
                ).first()

                if existing:
                    stats['products_skipped'] += 1
                    self.stdout.write(f"      = Product exists: {prod_name}")
                    product_index += 1
                    continue

                # Assign image (cycle through available)
                img_path = images[product_index % len(images)]

                product = Product(
                    product_name=prod_name,
                    sh_code=f"SH{random.randint(1000, 9999)}",
                    category=cat,
                    subcategory=sub,
                )
                # Attach main image
                with open(img_path, 'rb') as f:
                    fname = f"product_{product_index}_{os.path.basename(img_path)}"
                    product.main_image.save(fname, File(f), save=False)

                product.save()  # triggers auto asin_code sequence
                stats['products_created'] += 1
                stats['images_assigned'] += 1
                self.stdout.write(self.style.SUCCESS(
                    f"      + Product: {prod_name} [{product.asin_code}]"
                ))

                # ── Inventory Entry ──
                location = random.choice(LOCATIONS)
                price = Decimal(str(round(random.uniform(50, 15000), 2)))
                carton_pcs = random.randint(1, 500)
                cbm = Decimal(str(round(random.uniform(0.01, 50), 4)))

                inv = WarehouseInventory.objects.create(
                    product=product,
                    location_number=location,
                    price=price,
                    carton_piece=carton_pcs,
                    cbm=cbm,
                    remark=f"{prod_desc}. Stored at {location}.",
                )
                stats['locations_created'] += 1
                self.stdout.write(f"        + Location: {location}")

                # Carton image (1)
                ci_path = images[(product_index + 1) % len(images)]
                with open(ci_path, 'rb') as f:
                    ci = CartonImage(inventory=inv)
                    ci.image.save(f"carton_{product_index}.png", File(f), save=True)

                # Product images (2)
                for pi_offset in range(2):
                    pi_path = images[(product_index + pi_offset + 2) % len(images)]
                    with open(pi_path, 'rb') as f:
                        pi = InventoryProductImage(inventory=inv)
                        pi.image.save(f"prodimg_{product_index}_{pi_offset}.png", File(f), save=True)

                # Video (1)
                vid_path = videos[product_index % len(videos)]
                with open(vid_path, 'rb') as f:
                    iv = InventoryVideo(inventory=inv)
                    iv.video.save(f"video_{product_index}.mp4", File(f), save=True)
                stats['videos_assigned'] += 1

                product_index += 1

        # ── Final Report ─────────────────────────────────────
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("SEED DATA COMPLETE"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"  Categories created:     {stats['categories_created']}")
        self.stdout.write(f"  Categories skipped:     {stats['categories_skipped']}")
        self.stdout.write(f"  Subcategories created:  {stats['subcategories_created']}")
        self.stdout.write(f"  Subcategories skipped:  {stats['subcategories_skipped']}")
        self.stdout.write(f"  Products created:       {stats['products_created']}")
        self.stdout.write(f"  Products skipped:       {stats['products_skipped']}")
        self.stdout.write(f"  Images assigned:        {stats['images_assigned']}")
        self.stdout.write(f"  Videos assigned:        {stats['videos_assigned']}")
        self.stdout.write(f"  Locations assigned:     {stats['locations_created']}")
        self.stdout.write("=" * 60)

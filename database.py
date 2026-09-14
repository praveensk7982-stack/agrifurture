import os
import uuid
import sqlite3
import datetime
from config import Config

# Supabase imports
try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False

class Database:
    def __init__(self):
        self.client = None
        self.use_supabase = False
        
        # Try Supabase initialization
        if HAS_SUPABASE_LIB and Config.SUPABASE_URL and Config.SUPABASE_KEY:
            try:
                self.client: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
                # Test connectivity
                res = self.client.table("platform_settings").select("*").limit(1).execute()
                if res and hasattr(res, 'data'):
                    self.use_supabase = True
                    print("[DATABASE] Successfully connected to live Supabase PostgreSQL project!")
            except Exception as e:
                print(f"[DATABASE] Supabase direct connection warning: {e}. Utilizing embedded resilient engine with schema parity.")
                self.use_supabase = False
        
        # Initialize SQLite fallback / mirror
        self.db_path = Config.SQLITE_PATH
        self._init_sqlite()

    def _get_sqlite_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self):
        conn = self._get_sqlite_conn()
        cur = conn.cursor()
        
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL CHECK (role IN ('customer', 'farmer', 'machinery_seller', 'super_admin')),
            status TEXT NOT NULL DEFAULT 'active',
            location TEXT,
            avatar_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS platform_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            produce_commission_percent REAL NOT NULL DEFAULT 5.00,
            machinery_commission_percent REAL NOT NULL DEFAULT 10.00,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        INSERT OR IGNORE INTO platform_settings (id, produce_commission_percent, machinery_commission_percent)
        VALUES (1, 5.00, 10.00);

        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            farmer_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('fruits', 'vegetables', 'greens')),
            variety TEXT,
            description TEXT,
            price_per_unit REAL NOT NULL,
            unit TEXT NOT NULL DEFAULT 'kg',
            stock_quantity REAL NOT NULL DEFAULT 0,
            is_organic INTEGER DEFAULT 0,
            image_url TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            order_number TEXT UNIQUE NOT NULL,
            customer_id TEXT REFERENCES profiles(id) ON DELETE SET NULL,
            total_amount REAL NOT NULL,
            total_commission REAL NOT NULL DEFAULT 0,
            total_farmer_payout REAL NOT NULL DEFAULT 0,
            shipping_address TEXT NOT NULL,
            contact_phone TEXT NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'cod',
            payment_status TEXT NOT NULL DEFAULT 'pending',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id TEXT PRIMARY KEY,
            order_id TEXT REFERENCES orders(id) ON DELETE CASCADE,
            product_id TEXT REFERENCES products(id) ON DELETE SET NULL,
            farmer_id TEXT REFERENCES profiles(id) ON DELETE SET NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            subtotal REAL NOT NULL,
            commission_amount REAL NOT NULL DEFAULT 0,
            farmer_earnings REAL NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS machinery (
            id TEXT PRIMARY KEY,
            seller_id TEXT REFERENCES profiles(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('tractor', 'harvester', 'water_pump', 'bulldozer', 'power_tiller', 'sprayer')),
            model_info TEXT,
            specifications TEXT,
            hourly_rate REAL NOT NULL,
            daily_rate REAL NOT NULL,
            location TEXT,
            includes_operator INTEGER DEFAULT 0,
            operator_charge_per_hour REAL DEFAULT 0.00,
            image_url TEXT,
            is_available INTEGER DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS rental_bookings (
            id TEXT PRIMARY KEY,
            booking_number TEXT UNIQUE NOT NULL,
            customer_id TEXT REFERENCES profiles(id) ON DELETE SET NULL,
            machinery_id TEXT REFERENCES machinery(id) ON DELETE SET NULL,
            seller_id TEXT REFERENCES profiles(id) ON DELETE SET NULL,
            rental_type TEXT NOT NULL CHECK (rental_type IN ('hourly', 'daily')),
            start_datetime TEXT NOT NULL,
            end_datetime TEXT NOT NULL,
            duration_units REAL NOT NULL,
            rate_applied REAL NOT NULL,
            with_operator INTEGER DEFAULT 0,
            operator_fee REAL DEFAULT 0.00,
            total_amount REAL NOT NULL,
            commission_amount REAL NOT NULL DEFAULT 0,
            seller_payout REAL NOT NULL DEFAULT 0,
            delivery_location TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            payment_status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # Check if profiles table is empty in SQLite; seed if so
        cur.execute("SELECT COUNT(*) FROM profiles")
        if cur.fetchone()[0] == 0:
            self._seed_sqlite(cur)

        conn.commit()
        conn.close()

    def _seed_sqlite(self, cur):
        # Demo Users
        users = [
            ('11111111-1111-1111-1111-111111111111', 'admin@agrofuture.com', 'pbkdf2:sha256:260000$adminhash$demo', 'Vikramaditya Rao (Super Admin)', '+91 98765 00001', 'super_admin', 'active', 'Bangalore, Karnataka', 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150'),
            ('22222222-2222-2222-2222-222222222222', 'farmer.rajesh@agrofuture.com', 'pbkdf2:sha256:260000$farmerhash$demo', 'Rajesh Patel (Greenfields Organics)', '+91 98765 00002', 'farmer', 'active', 'Nashik, Maharashtra', 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150'),
            ('33333333-3333-3333-3333-333333333333', 'seller.kumar@agrofuture.com', 'pbkdf2:sha256:260000$sellerhash$demo', 'Suresh Kumar (AgroTech Equipment)', '+91 98765 00003', 'machinery_seller', 'active', 'Coimbatore, Tamil Nadu', 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150'),
            ('44444444-4444-4444-4444-444444444444', 'customer.anita@agrofuture.com', 'pbkdf2:sha256:260000$customerhash$demo', 'Anita Sharma (Agri Buyer & Farm Owner)', '+91 98765 00004', 'customer', 'active', 'Pune, Maharashtra', 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150')
        ]
        cur.executemany("INSERT INTO profiles (id, email, password_hash, full_name, phone, role, status, location, avatar_url) VALUES (?,?,?,?,?,?,?,?,?)", users)

        # Demo Products
        products = [
            ('a1111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'Alphonso Ratnagiri Mangoes', 'fruits', 'Hapus A-Grade', 'GI-tagged naturally ripened sweet Alphonso mangoes fresh from Konkan coast orchards. Chemical-free.', 450.0, 'box', 85, 1, 'https://images.unsplash.com/photo-1553279768-865429fa0078?w=600', 'active'),
            ('a2222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 'Kinnow Nagpur Oranges', 'fruits', 'Juicy Sweet Citrus', 'Sweet, juicy fresh harvest oranges rich in Vitamin C, picked directly from farm orchards this morning.', 80.0, 'kg', 240, 0, 'https://images.unsplash.com/photo-1611080626919-7cf5a9dbab5b?w=600', 'active'),
            ('a3333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', 'Royal Delicious Shimla Apples', 'fruits', 'Himachal Crisp Red', 'Crisp mountain grown apples with vibrant natural red skin and high sweetness index. Unwaxed.', 160.0, 'kg', 150, 1, 'https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6?w=600', 'active'),
            ('b1111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'Hydroponic Vine Tomatoes', 'vegetables', 'Roma Plum Special', 'Plump, firm, pesticide-free red tomatoes grown with controlled drip irrigation. Excellent shelf life.', 45.0, 'kg', 350, 1, 'https://images.unsplash.com/photo-1592924357228-91a4daadcfea?w=600', 'active'),
            ('b2222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 'Ooty Sweet Crunchy Carrots', 'vegetables', 'English Deep Orange', 'Crisp hill-station carrots, washed and graded. Great for fresh salads, juices, and daily cooking.', 55.0, 'kg', 210, 1, 'https://images.unsplash.com/photo-1598170845058-32b9d6a5c317?w=600', 'active'),
            ('b3333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', 'Nasik Red Globe Onions', 'vegetables', 'Pusa Red', 'Medium-to-large high pungency cooking onions harvested and cured with traditional dry racks.', 38.0, 'kg', 500, 0, 'https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=600', 'active'),
            ('c1111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 'Organic Spinach (Desi Palak)', 'greens', 'Broadleaf Organic', 'Tender iron-rich dark green spinach freshly harvested at dawn. Certified organic farm.', 25.0, 'bunch', 120, 1, 'https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=600', 'active'),
            ('c2222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222222', 'Fresh Coriander (Cilantro)', 'greens', 'Aromatic Country Green', 'Vibrant fragrant coriander bunches with roots intact for extended freshness in your kitchen.', 18.0, 'bunch', 180, 0, 'https://images.unsplash.com/photo-1599940824399-b87987ceb72a?w=600', 'active'),
            ('c3333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', 'Kasuri Methi (Fenugreek Leaves)', 'greens', 'Organic Country Methi', 'Small leaf tender fenugreek greens, packed with micro-nutrients. Great for methi parathas and dals.', 22.0, 'bunch', 140, 1, 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=600', 'active')
        ]
        cur.executemany("INSERT INTO products (id, farmer_id, title, category, variety, description, price_per_unit, unit, stock_quantity, is_organic, image_url, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", products)

        # Demo Machinery
        machinery = [
            ('f1111111-1111-1111-1111-111111111111', '33333333-3333-3333-3333-333333333333', 'Mahindra 575 DI Heavy Tractor (45 HP)', 'tractor', '2023 Model, 4-Cylinder DI Engine', '45 HP, Dual Clutch, Hydrostatic Power Steering, Rotavator & Plough attachment ready. Fuel efficient.', 650.0, 4200.0, 'Coimbatore Agri Zone', 1, 150.0, 'https://images.unsplash.com/photo-1592878904946-b3cd8ae243d0?w=600', 1, 'active'),
            ('f2222222-2222-2222-2222-222222222222', '33333333-3333-3333-3333-333333333333', 'Kubota DC-68G Paddy Combine Harvester', 'harvester', 'Track Type High Speed Harvester', '68 HP turbo diesel, 2.0 meter cutter bar, grain tank 1200L, rubber crawlers for wet wetland paddies.', 1800.0, 12500.0, 'Thanjavur Delta Hub', 1, 250.0, 'https://images.unsplash.com/photo-1595838742456-424a73740263?w=600', 1, 'active'),
            ('f3333333-3333-3333-3333-333333333333', '33333333-3333-3333-3333-333333333333', 'Kirloskar 10HP High Flow Diesel Water Pump', 'water_pump', 'Heavy Duty Dewatering / Irrigation Pump', '10 HP Diesel, 1200 LPM discharge rate, 30m head, includes 100m delivery hoses and foot valve.', 250.0, 1600.0, 'Salem Farming District', 0, 0.0, 'https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=600', 1, 'active'),
            ('f4444444-4444-4444-4444-444444444444', '33333333-3333-3333-3333-333333333333', 'CAT D3 Compact Crawler Farm Bulldozer', 'bulldozer', 'CAT Hydrostatic Track Dozer', '80 HP, 6-way variable blade for land leveling, farm clearing, pond digging, and bund construction.', 2400.0, 17500.0, 'Madurai Machinery Depot', 1, 300.0, 'https://images.unsplash.com/photo-1578632767115-351597cf2477?w=600', 1, 'active'),
            ('f5555555-5555-5555-5555-555555555555', '33333333-3333-3333-3333-333333333333', 'VST Shakti 130 DI Power Tiller', 'power_tiller', '13 HP Multi-Speed Rotary Tiller', '13 HP diesel, ideal for wet puddling, dry land weeding, horticulture tilling, and inter-crop furrowing.', 350.0, 2200.0, 'Erode Agro Park', 1, 100.0, 'https://images.unsplash.com/photo-1530267981375-f0de937f5f13?w=600', 1, 'active'),
            ('f6666666-6666-6666-6666-666666666666', '33333333-3333-3333-3333-333333333333', 'AgriPro 4-Stroke 25L Knapsack Power Sprayer', 'sprayer', 'High-Pressure Orchard Sprayer', '25-liter tank, brass pump unit, adjustable triple nozzle lance for rapid orchard and crop protection.', 120.0, 750.0, 'Trichy Agro Center', 0, 0.0, 'https://images.unsplash.com/photo-1589923188900-85dae523342b?w=600', 1, 'active')
        ]
        cur.executemany("INSERT INTO machinery (id, seller_id, title, category, model_info, specifications, hourly_rate, daily_rate, location, includes_operator, operator_charge_per_hour, image_url, is_available, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", machinery)

        # Demo Order
        cur.execute("""
        INSERT INTO orders (id, order_number, customer_id, total_amount, total_commission, total_farmer_payout, shipping_address, contact_phone, payment_method, payment_status, status)
        VALUES ('01111111-1111-1111-1111-111111111111', 'ORD-2026-901', '44444444-4444-4444-4444-444444444444', 990.00, 49.50, 940.50, 'Green Valley Farmhouse, Sector 4, Pune 411045', '+91 98765 00004', 'upi', 'paid', 'confirmed')
        """)
        cur.execute("""
        INSERT INTO order_items (id, order_id, product_id, farmer_id, quantity, unit_price, subtotal, commission_amount, farmer_earnings)
        VALUES 
        ('0a111111-1111-1111-1111-111111111111', '01111111-1111-1111-1111-111111111111', 'a1111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 2.0, 450.00, 900.00, 45.00, 855.00),
        ('0a222222-2222-2222-2222-222222222222', '01111111-1111-1111-1111-111111111111', 'b1111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222', 2.0, 45.00, 90.00, 4.50, 85.50)
        """)

        # Demo Rental Booking
        cur.execute("""
        INSERT INTO rental_bookings (id, booking_number, customer_id, machinery_id, seller_id, rental_type, start_datetime, end_datetime, duration_units, rate_applied, with_operator, operator_fee, total_amount, commission_amount, seller_payout, delivery_location, notes, status, payment_status)
        VALUES ('0b111111-1111-1111-1111-111111111111', 'RN-2026-701', '44444444-4444-4444-4444-444444444444', 'f1111111-1111-1111-1111-111111111111', '33333333-3333-3333-3333-333333333333', 'hourly', '2026-09-12 09:00:00', '2026-09-12 14:00:00', 5.0, 650.00, 1, 750.00, 4000.00, 400.00, 3600.00, 'Survey Plot 88, Khed Shivapur, Pune', 'Need tractor for pre-monsoon rotavator ploughing.', 'approved', 'paid')
        """)

    # ------------------ Profiles / Users ------------------
    def get_user_by_email(self, email):
        if self.use_supabase:
            try:
                res = self.client.table("profiles").select("*").eq("email", email).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                print(f"[DB] Supabase error in get_user_by_email: {e}")
        
        conn = self._get_sqlite_conn()
        user = conn.execute("SELECT * FROM profiles WHERE email = ?", (email,)).fetchone()
        conn.close()
        return dict(user) if user else None

    def get_user_by_id(self, user_id):
        if self.use_supabase:
            try:
                res = self.client.table("profiles").select("*").eq("id", user_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                print(f"[DB] Supabase error in get_user_by_id: {e}")

        conn = self._get_sqlite_conn()
        user = conn.execute("SELECT * FROM profiles WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(user) if user else None

    def create_user(self, user_data):
        if "id" not in user_data:
            user_data["id"] = str(uuid.uuid4())
        
        if self.use_supabase:
            try:
                self.client.table("profiles").insert(user_data).execute()
            except Exception as e:
                print(f"[DB] Supabase insert user: {e}")

        conn = self._get_sqlite_conn()
        keys = list(user_data.keys())
        placeholders = ",".join(["?"] * len(keys))
        columns = ",".join(keys)
        conn.execute(f"INSERT INTO profiles ({columns}) VALUES ({placeholders})", [user_data[k] for k in keys])
        conn.commit()
        conn.close()
        return user_data

    def get_all_users(self, role=None):
        if self.use_supabase:
            try:
                query = self.client.table("profiles").select("*")
                if role:
                    query = query.eq("role", role)
                res = query.order("created_at", desc=True).execute()
                return res.data
            except Exception as e:
                print(f"[DB] Supabase get_all_users: {e}")

        conn = self._get_sqlite_conn()
        if role:
            rows = conn.execute("SELECT * FROM profiles WHERE role = ? ORDER BY created_at DESC", (role,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM profiles ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_user_status(self, user_id, status):
        if self.use_supabase:
            try:
                self.client.table("profiles").update({"status": status}).eq("id", user_id).execute()
            except Exception as e:
                print(f"[DB] Supabase update user status: {e}")

        conn = self._get_sqlite_conn()
        conn.execute("UPDATE profiles SET status = ? WHERE id = ?", (status, user_id))
        conn.commit()
        conn.close()
        return True

    # ------------------ Platform Settings ------------------
    def get_platform_settings(self):
        if self.use_supabase:
            try:
                res = self.client.table("platform_settings").select("*").eq("id", 1).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                print(f"[DB] Supabase get_platform_settings: {e}")

        conn = self._get_sqlite_conn()
        row = conn.execute("SELECT * FROM platform_settings WHERE id = 1").fetchone()
        conn.close()
        if row:
            return dict(row)
        return {
            "id": 1,
            "produce_commission_percent": Config.DEFAULT_PRODUCE_COMMISSION,
            "machinery_commission_percent": Config.DEFAULT_MACHINERY_COMMISSION
        }

    def update_platform_settings(self, produce_comm, machinery_comm):
        now = datetime.datetime.utcnow().isoformat()
        if self.use_supabase:
            try:
                self.client.table("platform_settings").upsert({
                    "id": 1,
                    "produce_commission_percent": produce_comm,
                    "machinery_commission_percent": machinery_comm,
                    "updated_at": now
                }).execute()
            except Exception as e:
                print(f"[DB] Supabase update settings: {e}")

        conn = self._get_sqlite_conn()
        conn.execute("""
            UPDATE platform_settings 
            SET produce_commission_percent = ?, machinery_commission_percent = ?, updated_at = ?
            WHERE id = 1
        """, (produce_comm, machinery_comm, now))
        conn.commit()
        conn.close()
        return self.get_platform_settings()

    # ------------------ Products (Produce) ------------------
    def get_products(self, category=None, farmer_id=None, search=None, status=None):
        if self.use_supabase:
            try:
                query = self.client.table("products").select("*, profiles:farmer_id(full_name, phone, location)")
                if category and category != 'all':
                    query = query.eq("category", category)
                if farmer_id:
                    query = query.eq("farmer_id", farmer_id)
                if status:
                    query = query.eq("status", status)
                res = query.order("created_at", desc=True).execute()
                
                # Transform joined profiles
                items = []
                for item in res.data:
                    if "profiles" in item and item["profiles"]:
                        item["farmer_name"] = item["profiles"].get("full_name", "")
                        item["farmer_location"] = item["profiles"].get("location", "")
                    items.append(item)
                
                if search:
                    items = [i for i in items if search.lower() in i["title"].lower() or search.lower() in (i.get("description") or "").lower()]
                return items
            except Exception as e:
                print(f"[DB] Supabase get_products: {e}")

        conn = self._get_sqlite_conn()
        sql = """
            SELECT p.*, prof.full_name as farmer_name, prof.location as farmer_location 
            FROM products p
            LEFT JOIN profiles prof ON p.farmer_id = prof.id
            WHERE 1=1
        """
        params = []
        if category and category != 'all':
            sql += " AND p.category = ?"
            params.append(category)
        if farmer_id:
            sql += " AND p.farmer_id = ?"
            params.append(farmer_id)
        if status:
            sql += " AND p.status = ?"
            params.append(status)
        if search:
            sql += " AND (p.title LIKE ? OR p.description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        sql += " ORDER BY p.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_product_by_id(self, product_id):
        if self.use_supabase:
            try:
                res = self.client.table("products").select("*, profiles:farmer_id(full_name, phone, location)").eq("id", product_id).execute()
                if res.data:
                    item = res.data[0]
                    if "profiles" in item and item["profiles"]:
                        item["farmer_name"] = item["profiles"].get("full_name", "")
                    return item
            except Exception as e:
                print(f"[DB] Supabase get_product_by_id: {e}")

        conn = self._get_sqlite_conn()
        row = conn.execute("""
            SELECT p.*, prof.full_name as farmer_name, prof.location as farmer_location 
            FROM products p
            LEFT JOIN profiles prof ON p.farmer_id = prof.id
            WHERE p.id = ?
        """, (product_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def create_product(self, product_data):
        if "id" not in product_data:
            product_data["id"] = str(uuid.uuid4())
        
        if self.use_supabase:
            try:
                self.client.table("products").insert(product_data).execute()
            except Exception as e:
                print(f"[DB] Supabase insert product: {e}")

        conn = self._get_sqlite_conn()
        keys = list(product_data.keys())
        placeholders = ",".join(["?"] * len(keys))
        columns = ",".join(keys)
        conn.execute(f"INSERT INTO products ({columns}) VALUES ({placeholders})", [product_data[k] for k in keys])
        conn.commit()
        conn.close()
        return product_data

    def update_product(self, product_id, updates):
        if self.use_supabase:
            try:
                self.client.table("products").update(updates).eq("id", product_id).execute()
            except Exception as e:
                print(f"[DB] Supabase update product: {e}")

        conn = self._get_sqlite_conn()
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [product_id]
        conn.execute(f"UPDATE products SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True

    def delete_product(self, product_id):
        if self.use_supabase:
            try:
                self.client.table("products").delete().eq("id", product_id).execute()
            except Exception as e:
                print(f"[DB] Supabase delete product: {e}")

        conn = self._get_sqlite_conn()
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        return True

    # ------------------ Machinery Fleet ------------------
    def get_machinery(self, category=None, seller_id=None, search=None, available_only=False):
        if self.use_supabase:
            try:
                query = self.client.table("machinery").select("*, profiles:seller_id(full_name, phone, location)")
                if category and category != 'all':
                    query = query.eq("category", category)
                if seller_id:
                    query = query.eq("seller_id", seller_id)
                if available_only:
                    query = query.eq("is_available", True)
                res = query.order("created_at", desc=True).execute()

                items = []
                for item in res.data:
                    if "profiles" in item and item["profiles"]:
                        item["seller_name"] = item["profiles"].get("full_name", "")
                        item["seller_phone"] = item["profiles"].get("phone", "")
                    items.append(item)

                if search:
                    items = [i for i in items if search.lower() in i["title"].lower() or search.lower() in (i.get("model_info") or "").lower()]
                return items
            except Exception as e:
                print(f"[DB] Supabase get_machinery: {e}")

        conn = self._get_sqlite_conn()
        sql = """
            SELECT m.*, prof.full_name as seller_name, prof.phone as seller_phone 
            FROM machinery m
            LEFT JOIN profiles prof ON m.seller_id = prof.id
            WHERE 1=1
        """
        params = []
        if category and category != 'all':
            sql += " AND m.category = ?"
            params.append(category)
        if seller_id:
            sql += " AND m.seller_id = ?"
            params.append(seller_id)
        if available_only:
            sql += " AND m.is_available = 1"
        if search:
            sql += " AND (m.title LIKE ? OR m.model_info LIKE ? OR m.specifications LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        sql += " ORDER BY m.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_machinery_by_id(self, machinery_id):
        if self.use_supabase:
            try:
                res = self.client.table("machinery").select("*, profiles:seller_id(full_name, phone, location)").eq("id", machinery_id).execute()
                if res.data:
                    item = res.data[0]
                    if "profiles" in item and item["profiles"]:
                        item["seller_name"] = item["profiles"].get("full_name", "")
                        item["seller_phone"] = item["profiles"].get("phone", "")
                    return item
            except Exception as e:
                print(f"[DB] Supabase get_machinery_by_id: {e}")

        conn = self._get_sqlite_conn()
        row = conn.execute("""
            SELECT m.*, prof.full_name as seller_name, prof.phone as seller_phone 
            FROM machinery m
            LEFT JOIN profiles prof ON m.seller_id = prof.id
            WHERE m.id = ?
        """, (machinery_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def create_machinery(self, machinery_data):
        if "id" not in machinery_data:
            machinery_data["id"] = str(uuid.uuid4())

        if self.use_supabase:
            try:
                self.client.table("machinery").insert(machinery_data).execute()
            except Exception as e:
                print(f"[DB] Supabase insert machinery: {e}")

        conn = self._get_sqlite_conn()
        keys = list(machinery_data.keys())
        placeholders = ",".join(["?"] * len(keys))
        columns = ",".join(keys)
        conn.execute(f"INSERT INTO machinery ({columns}) VALUES ({placeholders})", [machinery_data[k] for k in keys])
        conn.commit()
        conn.close()
        return machinery_data

    def update_machinery(self, machinery_id, updates):
        if self.use_supabase:
            try:
                self.client.table("machinery").update(updates).eq("id", machinery_id).execute()
            except Exception as e:
                print(f"[DB] Supabase update machinery: {e}")

        conn = self._get_sqlite_conn()
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [machinery_id]
        conn.execute(f"UPDATE machinery SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()
        return True

    def delete_machinery(self, machinery_id):
        if self.use_supabase:
            try:
                self.client.table("machinery").delete().eq("id", machinery_id).execute()
            except Exception as e:
                print(f"[DB] Supabase delete machinery: {e}")

        conn = self._get_sqlite_conn()
        conn.execute("DELETE FROM machinery WHERE id = ?", (machinery_id,))
        conn.commit()
        conn.close()
        return True

    # ------------------ Orders (Produce Purchasing) ------------------
    def create_order(self, order_data, items):
        order_id = order_data.get("id") or str(uuid.uuid4())
        order_data["id"] = order_id
        
        # Insert order
        if self.use_supabase:
            try:
                self.client.table("orders").insert(order_data).execute()
                for it in items:
                    it["order_id"] = order_id
                    if "id" not in it:
                        it["id"] = str(uuid.uuid4())
                    self.client.table("order_items").insert(it).execute()
                    # Decrement product stock
                    prod = self.client.table("products").select("stock_quantity").eq("id", it["product_id"]).execute()
                    if prod.data:
                        new_stock = max(0, float(prod.data[0]["stock_quantity"]) - float(it["quantity"]))
                        self.client.table("products").update({"stock_quantity": new_stock}).eq("id", it["product_id"]).execute()
            except Exception as e:
                print(f"[DB] Supabase create_order: {e}")

        conn = self._get_sqlite_conn()
        cur = conn.cursor()
        keys = list(order_data.keys())
        placeholders = ",".join(["?"] * len(keys))
        columns = ",".join(keys)
        cur.execute(f"INSERT INTO orders ({columns}) VALUES ({placeholders})", [order_data[k] for k in keys])

        for it in items:
            it["order_id"] = order_id
            if "id" not in it:
                it["id"] = str(uuid.uuid4())
            ikeys = list(it.keys())
            iplaceholders = ",".join(["?"] * len(ikeys))
            icolumns = ",".join(ikeys)
            cur.execute(f"INSERT INTO order_items ({icolumns}) VALUES ({iplaceholders})", [it[k] for k in ikeys])
            cur.execute("UPDATE products SET stock_quantity = MAX(0, stock_quantity - ?) WHERE id = ?", (it["quantity"], it["product_id"]))

        conn.commit()
        conn.close()
        return order_data

    def get_orders(self, customer_id=None, farmer_id=None):
        if self.use_supabase:
            try:
                query = self.client.table("orders").select("*, profiles:customer_id(full_name, phone, email)")
                if customer_id:
                    query = query.eq("customer_id", customer_id)
                res = query.order("created_at", desc=True).execute()

                orders = []
                for o in res.data:
                    if "profiles" in o and o["profiles"]:
                        o["customer_name"] = o["profiles"].get("full_name", "")
                        o["customer_phone"] = o["profiles"].get("phone", "")
                    
                    # Fetch items
                    items_res = self.client.table("order_items").select("*, products:product_id(title, unit, image_url)").eq("order_id", o["id"]).execute()
                    o_items = []
                    for it in items_res.data:
                        if "products" in it and it["products"]:
                            it["product_title"] = it["products"].get("title", "")
                            it["product_image"] = it["products"].get("image_url", "")
                            it["unit"] = it["products"].get("unit", "kg")
                        o_items.append(it)

                    # If filtering by farmer_id, only keep if farmer has an item in this order
                    if farmer_id:
                        farmer_items = [it for it in o_items if it.get("farmer_id") == farmer_id]
                        if not farmer_items:
                            continue
                        o["farmer_items"] = farmer_items
                        o["farmer_total_earnings"] = sum(it.get("farmer_earnings", 0) for it in farmer_items)

                    o["items"] = o_items
                    orders.append(o)
                return orders
            except Exception as e:
                print(f"[DB] Supabase get_orders: {e}")

        conn = self._get_sqlite_conn()
        sql = """
            SELECT o.*, c.full_name as customer_name, c.phone as customer_phone, c.email as customer_email
            FROM orders o
            LEFT JOIN profiles c ON o.customer_id = c.id
            WHERE 1=1
        """
        params = []
        if customer_id:
            sql += " AND o.customer_id = ?"
            params.append(customer_id)

        sql += " ORDER BY o.created_at DESC"
        order_rows = conn.execute(sql, params).fetchall()

        orders = []
        for orow in order_rows:
            o = dict(orow)
            item_rows = conn.execute("""
                SELECT oi.*, p.title as product_title, p.unit, p.image_url as product_image
                FROM order_items oi
                LEFT JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ?
            """, (o["id"],)).fetchall()
            items = [dict(it) for it in item_rows]

            if farmer_id:
                farmer_items = [it for it in items if it.get("farmer_id") == farmer_id]
                if not farmer_items:
                    continue
                o["farmer_items"] = farmer_items
                o["farmer_total_earnings"] = sum(it.get("farmer_earnings", 0) for it in farmer_items)

            o["items"] = items
            orders.append(o)

        conn.close()
        return orders

    def update_order_status(self, order_id, status):
        if self.use_supabase:
            try:
                self.client.table("orders").update({"status": status}).eq("id", order_id).execute()
            except Exception as e:
                print(f"[DB] Supabase update order status: {e}")

        conn = self._get_sqlite_conn()
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()
        conn.close()
        return True

    # ------------------ Machinery Rental Bookings ------------------
    def create_booking(self, booking_data):
        if "id" not in booking_data:
            booking_data["id"] = str(uuid.uuid4())

        if self.use_supabase:
            try:
                self.client.table("rental_bookings").insert(booking_data).execute()
            except Exception as e:
                print(f"[DB] Supabase insert booking: {e}")

        conn = self._get_sqlite_conn()
        keys = list(booking_data.keys())
        placeholders = ",".join(["?"] * len(keys))
        columns = ",".join(keys)
        conn.execute(f"INSERT INTO rental_bookings ({columns}) VALUES ({placeholders})", [booking_data[k] for k in keys])
        conn.commit()
        conn.close()
        return booking_data

    def get_bookings(self, customer_id=None, seller_id=None):
        if self.use_supabase:
            try:
                query = self.client.table("rental_bookings").select("*, profiles:customer_id(full_name, phone), machinery:machinery_id(title, category, image_url, hourly_rate, daily_rate)")
                if customer_id:
                    query = query.eq("customer_id", customer_id)
                if seller_id:
                    query = query.eq("seller_id", seller_id)
                res = query.order("created_at", desc=True).execute()

                items = []
                for b in res.data:
                    if "profiles" in b and b["profiles"]:
                        b["customer_name"] = b["profiles"].get("full_name", "")
                        b["customer_phone"] = b["profiles"].get("phone", "")
                    if "machinery" in b and b["machinery"]:
                        b["machinery_title"] = b["machinery"].get("title", "")
                        b["machinery_category"] = b["machinery"].get("category", "")
                        b["machinery_image"] = b["machinery"].get("image_url", "")
                    items.append(b)
                return items
            except Exception as e:
                print(f"[DB] Supabase get_bookings: {e}")

        conn = self._get_sqlite_conn()
        sql = """
            SELECT rb.*, 
                   c.full_name as customer_name, c.phone as customer_phone,
                   m.title as machinery_title, m.category as machinery_category, m.image_url as machinery_image,
                   s.full_name as seller_name, s.phone as seller_phone
            FROM rental_bookings rb
            LEFT JOIN profiles c ON rb.customer_id = c.id
            LEFT JOIN machinery m ON rb.machinery_id = m.id
            LEFT JOIN profiles s ON rb.seller_id = s.id
            WHERE 1=1
        """
        params = []
        if customer_id:
            sql += " AND rb.customer_id = ?"
            params.append(customer_id)
        if seller_id:
            sql += " AND rb.seller_id = ?"
            params.append(seller_id)

        sql += " ORDER BY rb.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_booking_status(self, booking_id, status):
        if self.use_supabase:
            try:
                self.client.table("rental_bookings").update({"status": status}).eq("id", booking_id).execute()
            except Exception as e:
                print(f"[DB] Supabase update booking status: {e}")

        conn = self._get_sqlite_conn()
        conn.execute("UPDATE rental_bookings SET status = ? WHERE id = ?", (status, booking_id))
        conn.commit()
        conn.close()
        return True

    # ------------------ Super Admin Metrics & Ledger ------------------
    def get_admin_metrics(self):
        conn = self._get_sqlite_conn()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM profiles WHERE role = 'customer'")
        total_customers = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM profiles WHERE role = 'farmer'")
        total_farmers = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM profiles WHERE role = 'machinery_seller'")
        total_sellers = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM products")
        total_products = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM machinery")
        total_machinery = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0), COALESCE(SUM(total_commission), 0) FROM orders")
        order_stats = cur.fetchone()
        total_orders = order_stats[0]
        produce_sales_volume = float(order_stats[1])
        produce_commission_earned = float(order_stats[2])

        cur.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0), COALESCE(SUM(commission_amount), 0) FROM rental_bookings")
        booking_stats = cur.fetchone()
        total_bookings = booking_stats[0]
        machinery_rental_volume = float(booking_stats[1])
        machinery_commission_earned = float(booking_stats[2])

        total_platform_turnover = produce_sales_volume + machinery_rental_volume
        total_admin_commission = produce_commission_earned + machinery_commission_earned

        conn.close()

        return {
            "total_platform_turnover": round(total_platform_turnover, 2),
            "total_admin_commission": round(total_admin_commission, 2),
            "produce_sales_volume": round(produce_sales_volume, 2),
            "produce_commission_earned": round(produce_commission_earned, 2),
            "machinery_rental_volume": round(machinery_rental_volume, 2),
            "machinery_commission_earned": round(machinery_commission_earned, 2),
            "total_customers": total_customers,
            "total_farmers": total_farmers,
            "total_sellers": total_sellers,
            "total_users": total_customers + total_farmers + total_sellers + 1,
            "total_products": total_products,
            "total_machinery": total_machinery,
            "total_orders": total_orders,
            "total_bookings": total_bookings
        }

db = Database()

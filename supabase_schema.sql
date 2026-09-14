-- =================================================================
-- AGRO FUTURE - Full Database Schema (Supabase PostgreSQL)
-- Multi-Role Agricultural Marketplace & Machinery Rental Platform
-- =================================================================

-- 1. Profiles / Users Table
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    phone VARCHAR(30),
    role VARCHAR(30) NOT NULL CHECK (role IN ('customer', 'farmer', 'machinery_seller', 'super_admin')),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'pending_verification', 'suspended')),
    location VARCHAR(255),
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Platform Commission & Financial Settings
CREATE TABLE IF NOT EXISTS platform_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    produce_commission_percent NUMERIC(5, 2) NOT NULL DEFAULT 5.00,
    machinery_commission_percent NUMERIC(5, 2) NOT NULL DEFAULT 10.00,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO platform_settings (id, produce_commission_percent, machinery_commission_percent)
VALUES (1, 5.00, 10.00)
ON CONFLICT (id) DO NOTHING;

-- 3. Products (Farmer Produce Listings: Fruits, Vegetables, Greens)
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('fruits', 'vegetables', 'greens')),
    variety VARCHAR(100),
    description TEXT,
    price_per_unit NUMERIC(10, 2) NOT NULL,
    unit VARCHAR(20) NOT NULL DEFAULT 'kg',
    stock_quantity NUMERIC(10, 2) NOT NULL DEFAULT 0,
    is_organic BOOLEAN DEFAULT FALSE,
    image_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'out_of_stock', 'archived')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Customer Produce Orders
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    total_amount NUMERIC(10, 2) NOT NULL,
    total_commission NUMERIC(10, 2) NOT NULL DEFAULT 0,
    total_farmer_payout NUMERIC(10, 2) NOT NULL DEFAULT 0,
    shipping_address TEXT NOT NULL,
    contact_phone VARCHAR(30) NOT NULL,
    payment_method VARCHAR(30) NOT NULL DEFAULT 'cod',
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    status VARCHAR(30) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Produce Order Line Items
CREATE TABLE IF NOT EXISTS order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    farmer_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    quantity NUMERIC(10, 2) NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    subtotal NUMERIC(10, 2) NOT NULL,
    commission_amount NUMERIC(10, 2) NOT NULL DEFAULT 0,
    farmer_earnings NUMERIC(10, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Machinery Fleet (Tractors, Harvesters, Water Pumps, Bulldozers, etc.)
CREATE TABLE IF NOT EXISTS machinery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL CHECK (category IN ('tractor', 'harvester', 'water_pump', 'bulldozer', 'power_tiller', 'sprayer')),
    model_info VARCHAR(100),
    specifications TEXT,
    hourly_rate NUMERIC(10, 2) NOT NULL,
    daily_rate NUMERIC(10, 2) NOT NULL,
    location VARCHAR(255),
    includes_operator BOOLEAN DEFAULT FALSE,
    operator_charge_per_hour NUMERIC(10, 2) DEFAULT 0.00,
    image_url TEXT,
    is_available BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'maintenance', 'archived')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Machinery Rental Bookings
CREATE TABLE IF NOT EXISTS rental_bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    machinery_id UUID REFERENCES machinery(id) ON DELETE SET NULL,
    seller_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    rental_type VARCHAR(20) NOT NULL CHECK (rental_type IN ('hourly', 'daily')),
    start_datetime TIMESTAMPTZ NOT NULL,
    end_datetime TIMESTAMPTZ NOT NULL,
    duration_units NUMERIC(6, 1) NOT NULL,
    rate_applied NUMERIC(10, 2) NOT NULL,
    with_operator BOOLEAN DEFAULT FALSE,
    operator_fee NUMERIC(10, 2) DEFAULT 0.00,
    total_amount NUMERIC(10, 2) NOT NULL,
    commission_amount NUMERIC(10, 2) NOT NULL DEFAULT 0,
    seller_payout NUMERIC(10, 2) NOT NULL DEFAULT 0,
    delivery_location TEXT NOT NULL,
    notes TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'in_progress', 'completed', 'rejected', 'cancelled')),
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

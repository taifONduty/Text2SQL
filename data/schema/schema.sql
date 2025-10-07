-- Northwind Database Schema (PostgreSQL)
-- Normalized to 3NF with proper constraints and indexes

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS order_details CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS suppliers CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS shippers CASCADE;
DROP TABLE IF EXISTS territories CASCADE;
DROP TABLE IF EXISTS employee_territories CASCADE;
DROP TABLE IF EXISTS region CASCADE;

-- Categories Table
CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Suppliers Table
CREATE TABLE suppliers (
    supplier_id SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL,
    contact_name VARCHAR(100),
    contact_title VARCHAR(100),
    address VARCHAR(200),
    city VARCHAR(100),
    region VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    phone VARCHAR(50),
    fax VARCHAR(50),
    homepage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products Table
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(200) NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE SET NULL,
    category_id INTEGER REFERENCES categories(category_id) ON DELETE SET NULL,
    quantity_per_unit VARCHAR(100),
    unit_price DECIMAL(10, 2) DEFAULT 0 CHECK (unit_price >= 0),
    units_in_stock INTEGER DEFAULT 0 CHECK (units_in_stock >= 0),
    units_on_order INTEGER DEFAULT 0 CHECK (units_on_order >= 0),
    reorder_level INTEGER DEFAULT 0 CHECK (reorder_level >= 0),
    discontinued BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customers Table
CREATE TABLE customers (
    customer_id VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL,
    contact_name VARCHAR(100),
    contact_title VARCHAR(100),
    address VARCHAR(200),
    city VARCHAR(100),
    region VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    phone VARCHAR(50),
    fax VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Employees Table
CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    title VARCHAR(100),
    title_of_courtesy VARCHAR(50),
    birth_date DATE,
    hire_date DATE,
    address VARCHAR(200),
    city VARCHAR(100),
    region VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    home_phone VARCHAR(50),
    extension VARCHAR(10),
    notes TEXT,
    reports_to INTEGER REFERENCES employees(employee_id) ON DELETE SET NULL,
    photo_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shippers Table
CREATE TABLE shippers (
    shipper_id SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL UNIQUE,
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Orders Table
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id VARCHAR(10) REFERENCES customers(customer_id) ON DELETE SET NULL,
    employee_id INTEGER REFERENCES employees(employee_id) ON DELETE SET NULL,
    order_date DATE,
    required_date DATE,
    shipped_date DATE,
    ship_via INTEGER REFERENCES shippers(shipper_id) ON DELETE SET NULL,
    freight DECIMAL(10, 2) DEFAULT 0 CHECK (freight >= 0),
    ship_name VARCHAR(200),
    ship_address VARCHAR(200),
    ship_city VARCHAR(100),
    ship_region VARCHAR(100),
    ship_postal_code VARCHAR(20),
    ship_country VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (shipped_date >= order_date OR shipped_date IS NULL)
);

-- Order Details Table (Junction table with additional attributes)
CREATE TABLE order_details (
    order_id INTEGER REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    discount DECIMAL(3, 2) DEFAULT 0 CHECK (discount >= 0 AND discount <= 1),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order_id, product_id)
);

-- Region Table
CREATE TABLE region (
    region_id SERIAL PRIMARY KEY,
    region_description VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Territories Table
CREATE TABLE territories (
    territory_id VARCHAR(20) PRIMARY KEY,
    territory_description VARCHAR(100) NOT NULL,
    region_id INTEGER REFERENCES region(region_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Employee Territories Table (Many-to-Many relationship)
CREATE TABLE employee_territories (
    employee_id INTEGER REFERENCES employees(employee_id) ON DELETE CASCADE,
    territory_id VARCHAR(20) REFERENCES territories(territory_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (employee_id, territory_id)
);

-- Indexes for query optimization

-- Products indexes
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_supplier ON products(supplier_id);
CREATE INDEX idx_products_discontinued ON products(discontinued);
CREATE INDEX idx_products_name ON products(product_name);

-- Orders indexes
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_employee ON orders(employee_id);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_orders_shipped_date ON orders(shipped_date);
CREATE INDEX idx_orders_shipper ON orders(ship_via);

-- Order Details indexes
CREATE INDEX idx_order_details_product ON order_details(product_id);

-- Customers indexes
CREATE INDEX idx_customers_country ON customers(country);
CREATE INDEX idx_customers_city ON customers(city);
CREATE INDEX idx_customers_company ON customers(company_name);

-- Employees indexes
CREATE INDEX idx_employees_reports_to ON employees(reports_to);
CREATE INDEX idx_employees_hire_date ON employees(hire_date);

-- Composite indexes for common queries
CREATE INDEX idx_orders_customer_date ON orders(customer_id, order_date);
CREATE INDEX idx_products_category_discontinued ON products(category_id, discontinued);

-- Create read-only database user
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'northwind_readonly') THEN
        CREATE USER northwind_readonly WITH PASSWORD 'readonly_password';
    END IF;
END
$$;

-- Grant SELECT privileges only
GRANT CONNECT ON DATABASE northwind TO northwind_readonly;
GRANT USAGE ON SCHEMA public TO northwind_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO northwind_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO northwind_readonly;

-- Revoke all other privileges
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM northwind_readonly;

-- Views for common analytics queries (optional optimization)

CREATE OR REPLACE VIEW order_summaries AS
SELECT 
    o.order_id,
    o.customer_id,
    c.company_name as customer_name,
    o.employee_id,
    e.first_name || ' ' || e.last_name as employee_name,
    o.order_date,
    o.shipped_date,
    s.company_name as shipper_name,
    COUNT(od.product_id) as product_count,
    SUM(od.unit_price * od.quantity * (1 - od.discount)) as total_amount
FROM orders o
LEFT JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN employees e ON o.employee_id = e.employee_id
LEFT JOIN shippers s ON o.ship_via = s.shipper_id
LEFT JOIN order_details od ON o.order_id = od.order_id
GROUP BY o.order_id, c.company_name, e.first_name, e.last_name, s.company_name;

GRANT SELECT ON order_summaries TO northwind_readonly;

COMMENT ON TABLE categories IS 'Product categories';
COMMENT ON TABLE suppliers IS 'Product suppliers';
COMMENT ON TABLE products IS 'Products available for sale';
COMMENT ON TABLE customers IS 'Customer information';
COMMENT ON TABLE employees IS 'Employee records';
COMMENT ON TABLE shippers IS 'Shipping companies';
COMMENT ON TABLE orders IS 'Customer orders';
COMMENT ON TABLE order_details IS 'Line items for each order';
COMMENT ON TABLE region IS 'Sales regions';
COMMENT ON TABLE territories IS 'Sales territories within regions';
COMMENT ON TABLE employee_territories IS 'Employee territory assignments';


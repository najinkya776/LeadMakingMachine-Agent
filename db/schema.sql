-- Website Pitcher Database Schema
-- PostgreSQL schema for lead management

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- LEADS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    address TEXT,
    phone VARCHAR(50),
    email VARCHAR(255),
    website_url TEXT,
    google_rating DECIMAL(2,1),
    review_count INTEGER DEFAULT 0,
    photos_count INTEGER DEFAULT 0,
    business_hours TEXT,
    social_handles JSONB,
    source VARCHAR(50) DEFAULT 'google_maps',
    status VARCHAR(20) DEFAULT 'raw',
    lead_type VARCHAR(20),
    reachability_score INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for leads
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_lead_type ON leads(lead_type);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);
CREATE INDEX IF NOT EXISTS idx_leads_website ON leads(website_url);
CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category);
CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);

-- ============================================================================
-- AUDITS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS audits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    website_url TEXT NOT NULL,

    -- Core metrics
    page_speed_score INTEGER,
    mobile_score INTEGER,
    https_enabled BOOLEAN DEFAULT FALSE,

    -- SEO metrics
    seo_score INTEGER,
    has_sitemap BOOLEAN DEFAULT FALSE,
    has_robots_txt BOOLEAN DEFAULT FALSE,
    meta_tags_complete BOOLEAN DEFAULT FALSE,

    -- Technical issues
    broken_links_count INTEGER DEFAULT 0,
    missing_images_count INTEGER DEFAULT 0,

    -- Tech stack detection
    tech_stack VARCHAR(100),
    cms_type VARCHAR(50),
    is_wordpress BOOLEAN DEFAULT FALSE,
    is_wix BOOLEAN DEFAULT FALSE,
    is_shopify BOOLEAN DEFAULT FALSE,

    -- Content assessment
    design_quality VARCHAR(20),
    has_contact_form BOOLEAN DEFAULT FALSE,
    has_cta BOOLEAN DEFAULT FALSE,
    has_whatsapp BOOLEAN DEFAULT FALSE,
    last_updated VARCHAR(50),

    -- Detailed audit data
    audit_data JSONB,
    screenshots JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(lead_id)
);

-- Indexes for audits
CREATE INDEX IF NOT EXISTS idx_audits_lead_id ON audits(lead_id);
CREATE INDEX IF NOT EXISTS idx_audits_page_speed ON audits(page_speed_score);
CREATE INDEX IF NOT EXISTS idx_audits_seo_score ON audits(seo_score);

-- ============================================================================
-- REPORTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,

    -- Opportunity scoring
    opportunity_score INTEGER,
    classification VARCHAR(20),
    lead_type VARCHAR(20),

    -- Pitch content
    pitch_type VARCHAR(20),
    pitch_content TEXT,
    executive_summary TEXT,

    -- Outreach messages
    email_subject VARCHAR(255),
    email_body TEXT,
    whatsapp_message TEXT,

    -- PDF
    pdf_path TEXT,
    pdf_generated BOOLEAN DEFAULT FALSE,

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP,

    -- Pricing
    pricing_tier VARCHAR(20),
    pricing_estimate VARCHAR(100),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(lead_id)
);

-- Indexes for reports
CREATE INDEX IF NOT EXISTS idx_reports_lead_id ON reports(lead_id);
CREATE INDEX IF NOT EXISTS idx_reports_score ON reports(opportunity_score);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_classification ON reports(classification);

-- ============================================================================
-- SCRAPE_LOG TABLE (Audit trail for scraping operations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS scrape_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(50) NOT NULL,
    location VARCHAR(255),
    categories JSONB,
    leads_count INTEGER,
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scrape_log_source ON scrape_log(source);
CREATE INDEX IF NOT EXISTS idx_scrape_log_started ON scrape_log(started_at DESC);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to leads table
DROP TRIGGER IF EXISTS update_leads_updated_at ON leads;
CREATE TRIGGER update_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to reports table
DROP TRIGGER IF EXISTS update_reports_updated_at ON reports;
CREATE TRIGGER update_reports_updated_at
    BEFORE UPDATE ON reports
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View for high-priority leads (ready for outreach)
CREATE OR REPLACE VIEW high_priority_leads AS
SELECT
    l.id,
    l.business_name,
    l.category,
    l.phone,
    l.email,
    l.website_url,
    l.google_rating,
    l.review_count,
    r.opportunity_score,
    r.classification,
    r.status as report_status
FROM leads l
JOIN reports r ON l.id = r.lead_id
WHERE r.classification = 'high'
AND r.status = 'completed'
AND r.email_sent = FALSE
ORDER BY r.opportunity_score DESC;

-- View for leads by status
CREATE OR REPLACE VIEW leads_summary AS
SELECT
    status,
    COUNT(*) as count,
    AVG(google_rating) as avg_rating,
    AVG(review_count) as avg_reviews
FROM leads
GROUP BY status;

-- View for audit statistics
CREATE OR REPLACE VIEW audit_stats AS
SELECT
    COUNT(*) as total_audits,
    AVG(page_speed_score) as avg_page_speed,
    AVG(mobile_score) as avg_mobile_score,
    AVG(seo_score) as avg_seo_score,
    SUM(broken_links_count) as total_broken_links,
    COUNT(*) FILTER (WHERE design_quality = 'poor' OR design_quality = 'very_poor') as poor_design_count
FROM audits;
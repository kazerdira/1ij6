-- TranslateAPI Database Schema
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/ipyepuvljbniljjizimm/sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- USERS PROFILE TABLE
-- ============================================
CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    email TEXT NOT NULL,
    full_name TEXT,
    tier TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'enterprise')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users can read/update their own profile
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- ============================================
-- API KEYS TABLE
-- ============================================
CREATE TABLE public.api_keys (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL, -- First 8 chars for display (e.g., "sk_live_a1b2...")
    name TEXT DEFAULT 'Default',
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

-- Users can manage their own API keys
CREATE POLICY "Users can view own API keys" ON public.api_keys
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own API keys" ON public.api_keys
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own API keys" ON public.api_keys
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own API keys" ON public.api_keys
    FOR DELETE USING (auth.uid() = user_id);

-- ============================================
-- USAGE TRACKING TABLE
-- ============================================
CREATE TABLE public.usage (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    api_key_id UUID REFERENCES public.api_keys(id) ON DELETE SET NULL,
    endpoint TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    characters_translated INTEGER DEFAULT 0,
    audio_seconds NUMERIC(10,2) DEFAULT 0,
    response_time_ms INTEGER,
    status_code INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.usage ENABLE ROW LEVEL SECURITY;

-- Users can view their own usage
CREATE POLICY "Users can view own usage" ON public.usage
    FOR SELECT USING (auth.uid() = user_id);

-- Index for fast queries
CREATE INDEX idx_usage_user_created ON public.usage(user_id, created_at DESC);
CREATE INDEX idx_usage_api_key ON public.usage(api_key_id);

-- ============================================
-- MONTHLY USAGE SUMMARY (Materialized View)
-- ============================================
CREATE TABLE public.usage_monthly (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
    month DATE NOT NULL,
    request_count INTEGER DEFAULT 0,
    characters_total BIGINT DEFAULT 0,
    audio_seconds_total NUMERIC(10,2) DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, month)
);

-- Enable RLS
ALTER TABLE public.usage_monthly ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own monthly usage" ON public.usage_monthly
    FOR SELECT USING (auth.uid() = user_id);

-- ============================================
-- TIER LIMITS
-- ============================================
CREATE TABLE public.tier_limits (
    tier TEXT PRIMARY KEY,
    requests_per_month INTEGER NOT NULL,
    requests_per_minute INTEGER NOT NULL,
    max_characters_per_request INTEGER NOT NULL,
    max_audio_seconds_per_request INTEGER NOT NULL,
    features JSONB DEFAULT '{}'
);

-- Insert tier limits
INSERT INTO public.tier_limits (tier, requests_per_month, requests_per_minute, max_characters_per_request, max_audio_seconds_per_request, features) VALUES
('free', 1000, 10, 1000, 30, '{"text_translation": true, "audio_translation": false}'),
('pro', 50000, 60, 5000, 300, '{"text_translation": true, "audio_translation": true}'),
('enterprise', 200000, 200, 10000, 600, '{"text_translation": true, "audio_translation": true, "priority_support": true}');

-- Public read access to tier limits
ALTER TABLE public.tier_limits ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anyone can view tier limits" ON public.tier_limits FOR SELECT USING (true);

-- ============================================
-- FUNCTIONS
-- ============================================

-- Function to create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for new user signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Function to generate API key (returns plain key, stores hash)
CREATE OR REPLACE FUNCTION public.generate_api_key(key_name TEXT DEFAULT 'Default')
RETURNS TABLE(api_key TEXT, key_id UUID) AS $$
DECLARE
    plain_key TEXT;
    hashed_key TEXT;
    new_key_id UUID;
    key_pre TEXT;
BEGIN
    -- Generate random key: sk_live_ + 32 random chars
    plain_key := 'sk_live_' || encode(gen_random_bytes(24), 'base64');
    plain_key := replace(replace(replace(plain_key, '/', ''), '+', ''), '=', '');
    
    -- Hash for storage
    hashed_key := encode(sha256(plain_key::bytea), 'hex');
    
    -- Prefix for display
    key_pre := substring(plain_key, 1, 16) || '...';
    
    -- Insert
    INSERT INTO public.api_keys (user_id, key_hash, key_prefix, name)
    VALUES (auth.uid(), hashed_key, key_pre, key_name)
    RETURNING id INTO new_key_id;
    
    RETURN QUERY SELECT plain_key, new_key_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to validate API key (for Edge Function use)
CREATE OR REPLACE FUNCTION public.validate_api_key(plain_key TEXT)
RETURNS TABLE(
    user_id UUID,
    tier TEXT,
    is_valid BOOLEAN,
    requests_per_month INTEGER,
    requests_per_minute INTEGER,
    current_month_usage INTEGER
) AS $$
DECLARE
    hashed_key TEXT;
    found_user_id UUID;
    found_tier TEXT;
    month_start DATE;
    current_usage INTEGER;
BEGIN
    -- Hash the incoming key
    hashed_key := encode(sha256(plain_key::bytea), 'hex');
    
    -- Find user
    SELECT ak.user_id, p.tier INTO found_user_id, found_tier
    FROM public.api_keys ak
    JOIN public.profiles p ON p.id = ak.user_id
    WHERE ak.key_hash = hashed_key AND ak.is_active = true;
    
    IF found_user_id IS NULL THEN
        RETURN QUERY SELECT NULL::UUID, NULL::TEXT, false, 0, 0, 0;
        RETURN;
    END IF;
    
    -- Update last used
    UPDATE public.api_keys SET last_used_at = NOW() WHERE key_hash = hashed_key;
    
    -- Get current month usage
    month_start := date_trunc('month', NOW())::DATE;
    SELECT COALESCE(request_count, 0) INTO current_usage
    FROM public.usage_monthly
    WHERE usage_monthly.user_id = found_user_id AND month = month_start;
    
    -- Return with tier limits
    RETURN QUERY
    SELECT 
        found_user_id,
        found_tier,
        true,
        tl.requests_per_month,
        tl.requests_per_minute,
        COALESCE(current_usage, 0)
    FROM public.tier_limits tl
    WHERE tl.tier = found_tier;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record usage
CREATE OR REPLACE FUNCTION public.record_usage(
    p_user_id UUID,
    p_api_key_id UUID,
    p_endpoint TEXT,
    p_characters INTEGER DEFAULT 0,
    p_audio_seconds NUMERIC DEFAULT 0,
    p_response_time_ms INTEGER DEFAULT 0,
    p_status_code INTEGER DEFAULT 200
)
RETURNS VOID AS $$
DECLARE
    month_start DATE;
BEGIN
    -- Insert usage record
    INSERT INTO public.usage (user_id, api_key_id, endpoint, characters_translated, audio_seconds, response_time_ms, status_code)
    VALUES (p_user_id, p_api_key_id, p_endpoint, p_characters, p_audio_seconds, p_response_time_ms, p_status_code);
    
    -- Update monthly summary
    month_start := date_trunc('month', NOW())::DATE;
    
    INSERT INTO public.usage_monthly (user_id, month, request_count, characters_total, audio_seconds_total)
    VALUES (p_user_id, month_start, 1, p_characters, p_audio_seconds)
    ON CONFLICT (user_id, month)
    DO UPDATE SET
        request_count = public.usage_monthly.request_count + 1,
        characters_total = public.usage_monthly.characters_total + p_characters,
        audio_seconds_total = public.usage_monthly.audio_seconds_total + p_audio_seconds,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- GRANT PERMISSIONS FOR SERVICE ROLE
-- ============================================
-- These allow the Edge Functions (service role) to validate keys and record usage

GRANT USAGE ON SCHEMA public TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;

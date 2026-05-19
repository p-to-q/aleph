import { NextResponse } from 'next/server'

const HOSTED_PRIMARY_MODEL = 'deepseek-v4-pro'
const HOSTED_FALLBACK_MODEL = 'qwen3.6-27b-nothinking'

export function GET() {
  const hostedConfigured = Boolean(
    process.env.ALEPH_CUSTOM_API_KEY || process.env.ALEPH_OPENAI_API_KEY,
  )
  const fallbackConfigured = Boolean(process.env.ALEPH_CUSTOM_API_FALLBACK_KEY)

  return NextResponse.json({
    status: 'ok',
    version: '1.0.2',
    modes: hostedConfigured ? ['fixture', 'hosted_black_box'] : ['fixture', 'mock'],
    search_modes: hostedConfigured ? ['fixture', 'hosted_black_box'] : ['fixture', 'mock'],
    default_model: hostedConfigured
      ? process.env.ALEPH_CUSTOM_API_MODEL || process.env.ALEPH_OPENAI_MODEL || HOSTED_PRIMARY_MODEL
      : 'mock',
    hosted_primary_model: process.env.ALEPH_CUSTOM_API_MODEL || process.env.ALEPH_OPENAI_MODEL || HOSTED_PRIMARY_MODEL,
    hosted_black_box_configured: hostedConfigured,
    hosted_fallback_model: process.env.ALEPH_CUSTOM_API_FALLBACK_MODEL || HOSTED_FALLBACK_MODEL,
    hosted_fallback_configured: fallbackConfigured,
  })
}

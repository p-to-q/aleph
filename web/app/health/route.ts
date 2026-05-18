import { NextResponse } from 'next/server'

export function GET() {
  return NextResponse.json({
    status: 'ok',
    version: '0.1.0',
    modes: ['mock'],
    search_modes: ['mock'],
    default_model: 'mock',
  })
}


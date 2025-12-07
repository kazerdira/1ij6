import { createClient } from '@supabase/supabase-js'
import { NextRequest, NextResponse } from 'next/server'

const RUNPOD_ENDPOINT = 'https://api.runpod.ai/v2/99ki8de9ykt9m4/runsync'
const RUNPOD_API_KEY = process.env.RUNPOD_API_KEY!

const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)

interface ValidationResult {
  user_id: string
  tier: string
  is_valid: boolean
  requests_per_month: number
  requests_per_minute: number
  current_month_usage: number
}

async function validateApiKey(apiKey: string): Promise<ValidationResult | null> {
  const { data, error } = await supabaseAdmin.rpc('validate_api_key', {
    plain_key: apiKey,
  })

  if (error || !data || !data[0] || !data[0].is_valid) {
    return null
  }

  return data[0]
}

async function recordUsage(
  userId: string,
  endpoint: string,
  characters: number,
  responseTimeMs: number,
  statusCode: number
) {
  await supabaseAdmin.rpc('record_usage', {
    p_user_id: userId,
    p_api_key_id: null,
    p_endpoint: endpoint,
    p_characters: characters,
    p_audio_seconds: 0,
    p_response_time_ms: responseTimeMs,
    p_status_code: statusCode,
  })
}

export async function POST(request: NextRequest) {
  const startTime = Date.now()

  // Get API key from header
  const authHeader = request.headers.get('Authorization')
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return NextResponse.json(
      { error: { code: 'UNAUTHORIZED', message: 'Missing or invalid Authorization header' } },
      { status: 401 }
    )
  }

  const apiKey = authHeader.replace('Bearer ', '')

  // Validate API key
  const validation = await validateApiKey(apiKey)
  if (!validation) {
    return NextResponse.json(
      { error: { code: 'INVALID_API_KEY', message: 'Invalid API key' } },
      { status: 401 }
    )
  }

  // Check rate limits
  if (validation.current_month_usage >= validation.requests_per_month) {
    return NextResponse.json(
      {
        error: {
          code: 'QUOTA_EXCEEDED',
          message: `Monthly quota exceeded. Used ${validation.current_month_usage}/${validation.requests_per_month} requests.`,
        },
      },
      { status: 429 }
    )
  }

  // Parse request body
  let body: any
  try {
    body = await request.json()
  } catch {
    return NextResponse.json(
      { error: { code: 'INVALID_JSON', message: 'Invalid JSON in request body' } },
      { status: 400 }
    )
  }

  const { text, source_lang, target_lang } = body

  // Validate required fields
  if (!text || !source_lang || !target_lang) {
    return NextResponse.json(
      {
        error: {
          code: 'MISSING_FIELDS',
          message: 'Missing required fields: text, source_lang, target_lang',
        },
      },
      { status: 400 }
    )
  }

  // Check character limits based on tier
  const maxChars =
    validation.tier === 'enterprise' ? 10000 : validation.tier === 'pro' ? 5000 : 1000

  if (text.length > maxChars) {
    return NextResponse.json(
      {
        error: {
          code: 'TEXT_TOO_LONG',
          message: `Text exceeds ${maxChars} character limit for ${validation.tier} tier`,
        },
      },
      { status: 400 }
    )
  }

  // Call RunPod
  try {
    const runpodResponse = await fetch(RUNPOD_ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RUNPOD_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        input: {
          action: 'translate',
          text,
          source_lang,
          target_lang,
        },
      }),
    })

    const runpodData = await runpodResponse.json()
    const responseTime = Date.now() - startTime

    if (runpodData.status === 'COMPLETED' && runpodData.output) {
      // Record successful usage
      await recordUsage(
        validation.user_id,
        '/v1/translate',
        text.length,
        responseTime,
        200
      )

      return NextResponse.json({
        translated_text: runpodData.output.translated || runpodData.output.translated_text,
        original_text: runpodData.output.original || text,
        source_lang,
        target_lang,
        processing_time_ms: responseTime,
      })
    } else {
      // Record failed usage
      await recordUsage(validation.user_id, '/v1/translate', text.length, responseTime, 500)

      return NextResponse.json(
        {
          error: {
            code: 'TRANSLATION_FAILED',
            message: runpodData.output?.error || 'Translation failed',
          },
        },
        { status: 500 }
      )
    }
  } catch (error) {
    const responseTime = Date.now() - startTime
    await recordUsage(validation.user_id, '/v1/translate', text.length, responseTime, 500)

    return NextResponse.json(
      { error: { code: 'SERVICE_ERROR', message: 'Translation service unavailable' } },
      { status: 503 }
    )
  }
}

import { createClient } from '@supabase/supabase-js'
import { NextRequest, NextResponse } from 'next/server'

const RUNPOD_ENDPOINT = 'https://api.runpod.ai/v2/99ki8de9ykt9m4/runsync'
const RUNPOD_API_KEY = process.env.RUNPOD_API_KEY!

const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
)

async function validateApiKey(apiKey: string) {
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
  audioSeconds: number,
  characters: number,
  responseTimeMs: number,
  statusCode: number
) {
  await supabaseAdmin.rpc('record_usage', {
    p_user_id: userId,
    p_api_key_id: null,
    p_endpoint: endpoint,
    p_characters: characters,
    p_audio_seconds: audioSeconds,
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

  // Check if tier allows audio
  if (validation.tier === 'free') {
    return NextResponse.json(
      {
        error: {
          code: 'TIER_NOT_ALLOWED',
          message: 'Audio transcription requires Pro or Enterprise tier',
        },
      },
      { status: 403 }
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

  const { audio_base64, target_lang, source_lang } = body

  // Validate required fields
  if (!audio_base64) {
    return NextResponse.json(
      { error: { code: 'MISSING_FIELDS', message: 'Missing required field: audio_base64' } },
      { status: 400 }
    )
  }

  // Call RunPod
  try {
    const runpodPayload: any = {
      input: {
        action: target_lang ? 'transcribe' : 'transcribe_only',
        audio_base64,
      },
    }

    if (target_lang) {
      runpodPayload.input.target_lang = target_lang
    }
    if (source_lang) {
      runpodPayload.input.source_lang = source_lang
    }

    const runpodResponse = await fetch(RUNPOD_ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RUNPOD_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(runpodPayload),
    })

    const runpodData = await runpodResponse.json()
    const responseTime = Date.now() - startTime

    if (runpodData.status === 'COMPLETED' && runpodData.output) {
      const output = runpodData.output
      const audioSeconds = output.audio_duration || 0
      const characters = (output.transcription?.length || 0) + (output.translated_text?.length || 0)

      // Record successful usage
      await recordUsage(
        validation.user_id,
        target_lang ? '/v1/transcribe' : '/v1/transcribe-only',
        audioSeconds,
        characters,
        responseTime,
        200
      )

      const response: any = {
        transcription: output.transcription,
        detected_language: output.detected_language,
        processing_time_ms: responseTime,
      }

      if (output.translated_text) {
        response.translated_text = output.translated_text
        response.target_lang = target_lang
      }

      return NextResponse.json(response)
    } else {
      await recordUsage(validation.user_id, '/v1/transcribe', 0, 0, responseTime, 500)

      return NextResponse.json(
        {
          error: {
            code: 'TRANSCRIPTION_FAILED',
            message: runpodData.output?.error || 'Transcription failed',
          },
        },
        { status: 500 }
      )
    }
  } catch (error) {
    const responseTime = Date.now() - startTime
    await recordUsage(validation.user_id, '/v1/transcribe', 0, 0, responseTime, 500)

    return NextResponse.json(
      { error: { code: 'SERVICE_ERROR', message: 'Transcription service unavailable' } },
      { status: 503 }
    )
  }
}

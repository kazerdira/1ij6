import { NextResponse } from 'next/server'

const RUNPOD_ENDPOINT = 'https://api.runpod.ai/v2/99ki8de9ykt9m4/runsync'
const RUNPOD_API_KEY = process.env.RUNPOD_API_KEY!

export async function GET() {
  try {
    const response = await fetch(RUNPOD_ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RUNPOD_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        input: { action: 'health' },
      }),
    })

    const data = await response.json()

    if (data.status === 'COMPLETED' && data.output) {
      return NextResponse.json({
        status: 'healthy',
        api_version: 'v1',
        gpu: data.output.gpu_available ? data.output.gpu_name : 'CPU only',
        models: data.output.models_loaded,
      })
    }

    return NextResponse.json(
      { status: 'degraded', message: 'Backend service not fully operational' },
      { status: 503 }
    )
  } catch (error) {
    return NextResponse.json(
      { status: 'unhealthy', message: 'Cannot reach backend service' },
      { status: 503 }
    )
  }
}

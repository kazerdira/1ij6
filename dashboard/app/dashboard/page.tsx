import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import DashboardClient from './DashboardClient'

export default async function DashboardPage() {
  const supabase = createClient()
  
  const { data: { user } } = await supabase.auth.getUser()
  
  if (!user) {
    redirect('/login')
  }

  // Fetch profile
  const { data: profile } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single()

  // Fetch API keys
  const { data: apiKeys } = await supabase
    .from('api_keys')
    .select('*')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })

  // Fetch current month usage
  const monthStart = new Date()
  monthStart.setDate(1)
  monthStart.setHours(0, 0, 0, 0)
  
  const { data: monthlyUsage } = await supabase
    .from('usage_monthly')
    .select('*')
    .eq('user_id', user.id)
    .eq('month', monthStart.toISOString().split('T')[0])
    .single()

  // Fetch tier limits
  const { data: tierLimits } = await supabase
    .from('tier_limits')
    .select('*')
    .eq('tier', profile?.tier || 'free')
    .single()

  // Fetch recent usage
  const { data: recentUsage } = await supabase
    .from('usage')
    .select('*')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false })
    .limit(10)

  return (
    <DashboardClient
      user={user}
      profile={profile}
      apiKeys={apiKeys || []}
      monthlyUsage={monthlyUsage}
      tierLimits={tierLimits}
      recentUsage={recentUsage || []}
    />
  )
}

import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { 
  Lock, 
  Eye, 
  EyeOff, 
  AlertCircle, 
  Loader2,
  KeyRound,
  CheckCircle,
  Shield
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface SetupPageProps {
  onSetupComplete: () => void
}

type SetupStep = 'password' | 'pin' | 'confirm'

export function SetupPage({ onSetupComplete }: SetupPageProps) {
  const [step, setStep] = useState<SetupStep>('password')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [pin, setPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [skipPin, setSkipPin] = useState(false)
  const [error, setError] = useState('')
  
  const passwordRef = useRef<HTMLInputElement>(null)
  const pinRefs = useRef<(HTMLInputElement | null)[]>([])
  const confirmPinRefs = useRef<(HTMLInputElement | null)[]>([])
  
  // Focus password input on mount
  useEffect(() => {
    passwordRef.current?.focus()
  }, [])
  
  // Focus PIN input when entering PIN step
  useEffect(() => {
    if (step === 'pin') {
      pinRefs.current[0]?.focus()
    }
  }, [step])
  
  // Setup mutation
  const setupMutation = useMutation({
    mutationFn: (data: { password: string; pin?: string }) =>
      fetch('/api/auth/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }).then(res => res.json()),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error)
        return
      }
      
      onSetupComplete()
    },
    onError: (err: Error) => {
      setError(err.message || 'Setup failed')
    },
  })
  
  const validatePassword = (): boolean => {
    if (password.length < 8) {
      setError('Password must be at least 8 characters')
      return false
    }
    
    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return false
    }
    
    return true
  }
  
  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    if (!validatePassword()) return
    
    if (skipPin) {
      // Submit without PIN
      setupMutation.mutate({ password })
    } else {
      // Move to PIN step
      setStep('pin')
    }
  }
  
  const handlePinChange = (
    index: number, 
    value: string, 
    isConfirm: boolean = false
  ) => {
    // Only allow digits
    if (value && !/^\d$/.test(value)) return
    
    const currentPin = isConfirm ? confirmPin : pin
    const newPin = currentPin.split('')
    newPin[index] = value
    const updatedPin = newPin.join('')
    
    if (isConfirm) {
      setConfirmPin(updatedPin)
    } else {
      setPin(updatedPin)
    }
    
    const refs = isConfirm ? confirmPinRefs : pinRefs
    
    // Auto-focus next input
    if (value && index < 5) {
      refs.current[index + 1]?.focus()
    }
    
    // Auto-advance to confirm when PIN complete
    if (!isConfirm && updatedPin.length === 6 && !updatedPin.includes('')) {
      setStep('confirm')
      setTimeout(() => confirmPinRefs.current[0]?.focus(), 100)
    }
    
    // Auto-submit when confirm PIN is complete
    if (isConfirm && updatedPin.length === 6 && !updatedPin.includes('')) {
      if (updatedPin === pin) {
        setError('')
        setupMutation.mutate({ password, pin: updatedPin })
      } else {
        setError('PINs do not match')
        setConfirmPin('')
        confirmPinRefs.current[0]?.focus()
      }
    }
  }
  
  const handlePinKeyDown = (
    index: number, 
    e: React.KeyboardEvent, 
    isConfirm: boolean = false
  ) => {
    const currentPin = isConfirm ? confirmPin : pin
    const refs = isConfirm ? confirmPinRefs : pinRefs
    
    if (e.key === 'Backspace' && !currentPin[index] && index > 0) {
      refs.current[index - 1]?.focus()
    }
  }
  
  const passwordStrength = (): { strength: number; label: string; color: string } => {
    const len = password.length
    if (len === 0) return { strength: 0, label: '', color: '' }
    if (len < 8) return { strength: 1, label: 'Too short', color: 'bg-giga-error' }
    if (len < 12) return { strength: 2, label: 'Fair', color: 'bg-giga-warning' }
    if (len < 16) return { strength: 3, label: 'Good', color: 'bg-giga-accent' }
    return { strength: 4, label: 'Strong', color: 'bg-giga-success' }
  }
  
  const { strength, label, color } = passwordStrength()
  const isLoading = setupMutation.isPending

  return (
    <div className="min-h-screen bg-giga-dark flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-giga-accent rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Shield size={32} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Secure Your Dashboard</h1>
          <p className="text-gray-500 mt-1">Set up password and optional PIN</p>
        </div>
        
        {/* Progress Steps */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className={cn(
            'w-3 h-3 rounded-full transition-colors',
            step === 'password' ? 'bg-giga-accent' : 'bg-giga-accent/30'
          )} />
          <div className={cn(
            'w-12 h-0.5',
            step !== 'password' ? 'bg-giga-accent' : 'bg-giga-accent/30'
          )} />
          <div className={cn(
            'w-3 h-3 rounded-full transition-colors',
            step === 'pin' ? 'bg-giga-accent' : 
            step === 'confirm' ? 'bg-giga-accent/30' : 'bg-giga-accent/30'
          )} />
          <div className={cn(
            'w-12 h-0.5',
            step === 'confirm' ? 'bg-giga-accent' : 'bg-giga-accent/30'
          )} />
          <div className={cn(
            'w-3 h-3 rounded-full transition-colors',
            step === 'confirm' ? 'bg-giga-accent' : 'bg-giga-accent/30'
          )} />
        </div>
        
        {/* Setup Card */}
        <div className="bg-giga-card border border-sidebar-border rounded-2xl p-6">
          {step === 'password' && (
            <form onSubmit={handlePasswordSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  <Lock size={14} className="inline mr-2" />
                  Create Password
                </label>
                <div className="relative">
                  <input
                    ref={passwordRef}
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter a strong password"
                    className="input w-full pr-12"
                    disabled={isLoading}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white transition-colors"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                
                {/* Password strength indicator */}
                {password && (
                  <div className="mt-2">
                    <div className="flex gap-1 mb-1">
                      {[1, 2, 3, 4].map((i) => (
                        <div
                          key={i}
                          className={cn(
                            'h-1 flex-1 rounded-full transition-colors',
                            i <= strength ? color : 'bg-giga-hover'
                          )}
                        />
                      ))}
                    </div>
                    <p className={cn('text-xs', color.replace('bg-', 'text-'))}>
                      {label}
                    </p>
                  </div>
                )}
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Confirm Password
                </label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  className="input w-full"
                  disabled={isLoading}
                  autoComplete="new-password"
                />
                {confirmPassword && password === confirmPassword && (
                  <p className="text-xs text-giga-success mt-1 flex items-center gap-1">
                    <CheckCircle size={12} />
                    Passwords match
                  </p>
                )}
              </div>
              
              {/* Skip PIN option */}
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={skipPin}
                  onChange={(e) => setSkipPin(e.target.checked)}
                  className="rounded border-gray-600 bg-giga-card text-giga-accent"
                />
                <span className="text-sm text-gray-400">
                  Skip PIN setup (less secure)
                </span>
              </label>
              
              {error && (
                <div className="flex items-center gap-2 p-3 bg-giga-error/10 border border-giga-error/20 rounded-lg text-giga-error text-sm">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}
              
              <button
                type="submit"
                disabled={isLoading || password.length < 8}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Setting up...
                  </>
                ) : skipPin ? (
                  'Complete Setup'
                ) : (
                  'Continue to PIN'
                )}
              </button>
            </form>
          )}
          
          {step === 'pin' && (
            <div className="space-y-6">
              <div className="text-center">
                <div className="w-12 h-12 bg-giga-accent/20 rounded-full flex items-center justify-center mx-auto mb-3">
                  <KeyRound size={24} className="text-giga-accent" />
                </div>
                <h2 className="text-lg font-semibold text-white">Create PIN</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Enter a 6-digit PIN for quick access
                </p>
              </div>
              
              {/* PIN Input */}
              <div className="flex justify-center gap-2">
                {[0, 1, 2, 3, 4, 5].map((index) => (
                  <input
                    key={index}
                    ref={(el) => (pinRefs.current[index] = el)}
                    type="password"
                    inputMode="numeric"
                    maxLength={1}
                    value={pin[index] || ''}
                    onChange={(e) => handlePinChange(index, e.target.value)}
                    onKeyDown={(e) => handlePinKeyDown(index, e)}
                    disabled={isLoading}
                    className={cn(
                      'w-12 h-14 text-center text-xl font-bold rounded-lg',
                      'bg-giga-hover border-2 border-sidebar-border text-white',
                      'focus:border-giga-accent focus:outline-none transition-colors',
                      'disabled:opacity-50'
                    )}
                  />
                ))}
              </div>
              
              <button
                type="button"
                onClick={() => {
                  setStep('password')
                  setPin('')
                  setError('')
                }}
                className="w-full text-sm text-gray-400 hover:text-white transition-colors"
              >
                ← Back to password
              </button>
            </div>
          )}
          
          {step === 'confirm' && (
            <div className="space-y-6">
              <div className="text-center">
                <div className="w-12 h-12 bg-giga-accent/20 rounded-full flex items-center justify-center mx-auto mb-3">
                  <CheckCircle size={24} className="text-giga-accent" />
                </div>
                <h2 className="text-lg font-semibold text-white">Confirm PIN</h2>
                <p className="text-sm text-gray-500 mt-1">
                  Re-enter your PIN to confirm
                </p>
              </div>
              
              {/* Confirm PIN Input */}
              <div className="flex justify-center gap-2">
                {[0, 1, 2, 3, 4, 5].map((index) => (
                  <input
                    key={index}
                    ref={(el) => (confirmPinRefs.current[index] = el)}
                    type="password"
                    inputMode="numeric"
                    maxLength={1}
                    value={confirmPin[index] || ''}
                    onChange={(e) => handlePinChange(index, e.target.value, true)}
                    onKeyDown={(e) => handlePinKeyDown(index, e, true)}
                    disabled={isLoading}
                    className={cn(
                      'w-12 h-14 text-center text-xl font-bold rounded-lg',
                      'bg-giga-hover border-2 border-sidebar-border text-white',
                      'focus:border-giga-accent focus:outline-none transition-colors',
                      'disabled:opacity-50'
                    )}
                  />
                ))}
              </div>
              
              {error && (
                <div className="flex items-center justify-center gap-2 p-3 bg-giga-error/10 border border-giga-error/20 rounded-lg text-giga-error text-sm">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}
              
              {isLoading && (
                <div className="flex items-center justify-center gap-2 text-gray-400">
                  <Loader2 size={18} className="animate-spin" />
                  Setting up authentication...
                </div>
              )}
              
              <button
                type="button"
                onClick={() => {
                  setStep('pin')
                  setConfirmPin('')
                  setError('')
                  setTimeout(() => pinRefs.current[0]?.focus(), 100)
                }}
                className="w-full text-sm text-gray-400 hover:text-white transition-colors"
              >
                ← Back to enter PIN
              </button>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <p className="text-center text-xs text-gray-600 mt-6">
          Your credentials are securely hashed and stored locally
        </p>
      </div>
    </div>
  )
}

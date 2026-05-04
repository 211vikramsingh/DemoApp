// Central TypeScript types for the trading bot frontend

export type UserRole = 'admin' | 'user';
export type WalletType = 'real' | 'paper';
export type AutomationMode = 'auto' | 'semi_auto' | 'manual';
export type PositionSizingMethod = 'fixed' | 'kelly' | 'half_kelly';
export type KillScope = 'global' | 'instrument' | 'trade';

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Strategy {
  id: string;
  name: string;
  config: Record<string, unknown>;
  automation_mode: AutomationMode;
  wallet_type: WalletType;
  position_sizing_method: PositionSizingMethod;
  is_active: boolean;
  user_id: string;
}

export interface Trade {
  id: string;
  strategy_id: string;
  instrument: string;
  direction: 'long' | 'short';
  entry_price: number;
  exit_price: number | null;
  quantity: number;
  pnl: number | null;
  status: string;
  opened_at: string;
  closed_at: string | null;
}

export interface Signal {
  id: string;
  strategy_id: string;
  instrument: string;
  direction: 'long' | 'short';
  entry_price: number;
  stop_loss: number;
  target: number;
  rr_ratio: number;
  status: 'pending' | 'approved' | 'rejected' | 'executed';
  block_reason: string | null;
  created_at: string;
}

export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  iv: number;
  intrinsic_value: number;
  time_value: number;
}

export interface KillRequest {
  scope: KillScope;
  instrument?: string;
  trade_id?: string;
}

export interface KillResponse {
  scope: KillScope;
  positions_closed: number;
  orders_cancelled: number;
  timestamp: string;
  instrument: string | null;
  trade_id: string | null;
}

export interface WSMessage {
  channel: string;
  data: string;
}

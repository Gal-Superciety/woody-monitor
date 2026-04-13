//! Pseudo-interface for Woody Clash Arena treasury split logic on MultiversX.
//! This file is intentionally implementation-agnostic and documents the
//! expected endpoints/events/state needed by backend + frontend.

/// Basis points helper (10_000 = 100%).
pub type Bps = u16;

/// Payment source type for accounting and analytics.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SourceType {
    RankedEntry,
    RetryTicket,
    PremiumQuest,
    ManualTopUp,
}

/// Fee split configuration in basis points.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FeeConfig {
    pub to_reward_vault_bps: Bps,
    pub to_treasury_bps: Bps,
    pub to_burn_bps: Bps,
}

/// Core treasury behavior.
pub trait ArenaTreasuryInterface {
    /// Configure split for a source type.
    /// Access: owner/multisig + timelock.
    fn set_fee_config(&self, source: SourceType, cfg: FeeConfig);

    /// Receives WOODY fee payment and performs split:
    /// reward vault / treasury / burn address.
    fn deposit_fees(&self, source: SourceType, amount: u128);

    /// Pause all deposits in emergencies.
    fn pause_deposits(&self);

    /// Resume deposits.
    fn unpause_deposits(&self);

    /// Reads current fee configuration.
    fn get_fee_config(&self, source: SourceType) -> FeeConfig;

    /// Returns cumulative accounting for audits.
    fn get_totals_by_source(&self, source: SourceType) -> (u128, u128, u128);
}

/// Emitted after each successful split.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FeesSplitEvent {
    pub source: SourceType,
    pub gross_amount: u128,
    pub to_reward_vault: u128,
    pub to_treasury: u128,
    pub to_burn: u128,
}

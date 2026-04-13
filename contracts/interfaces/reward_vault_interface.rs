//! Pseudo-interface for weekly rewards distribution using Merkle claims.

pub type EpochId = u64;

/// Reward pool metadata for one distribution epoch.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EpochPool {
    pub epoch_id: EpochId,
    pub total_amount: u128,
    pub merkle_root: [u8; 32],
    pub claim_deadline_unix: u64,
    pub is_finalized: bool,
}

pub trait RewardVaultInterface {
    /// Creates and funds an epoch pool.
    /// Access: owner/multisig.
    fn create_epoch_pool(&self, epoch_id: EpochId, total_amount: u128, claim_deadline_unix: u64);

    /// Sets merkle root once weekly off-chain computation is finalized.
    /// Access: owner/multisig.
    fn set_merkle_root(&self, epoch_id: EpochId, merkle_root: [u8; 32]);

    /// Claim user rewards with merkle proof.
    fn claim(&self, epoch_id: EpochId, amount: u128, proof: Vec<[u8; 32]>);

    /// Returns true if wallet already claimed for epoch.
    fn is_claimed(&self, epoch_id: EpochId, wallet: [u8; 32]) -> bool;

    /// Move unclaimed remainder after deadline based on policy.
    /// Example: 50% rollover, 50% treasury.
    fn sweep_unclaimed(&self, epoch_id: EpochId);

    /// Pause claims (emergency circuit breaker).
    fn pause_claims(&self);

    /// Resume claims.
    fn unpause_claims(&self);

    /// Read epoch metadata.
    fn get_epoch_pool(&self, epoch_id: EpochId) -> EpochPool;
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ClaimedEvent {
    pub epoch_id: EpochId,
    pub wallet: [u8; 32],
    pub amount: u128,
}

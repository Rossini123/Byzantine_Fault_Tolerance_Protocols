"""
BFT-SH-DID: Byzantine Fault Tolerant Self-Healing DID Recovery
Experimental evaluation: Gas costs and end-to-end latency
"""

import time
import random
from dataclasses import dataclass
from typing import List, Dict, Optional
import json


@dataclass
class RecoveryPhase:
    """Timing for each phase of recovery"""
    detection_time: float = 0.0
    proposal_time: float = 0.0
    endorsement_time: float = 0.0
    commit_time: float = 0.0
    finalization_time: float = 0.0


@dataclass
class RecoveryResult:
    """Results from a recovery experiment"""
    quorum_size: int
    n_watchers: int
    f_byzantine: int
    gas_used: int
    total_latency: float
    phases: RecoveryPhase
    success: bool
    byzantine_behavior: str  # "none", "delay", "refuse"


class BFTSHDIDExperiment:
    """
    Simulates BFT-SH-DID recovery protocol
    Measures gas costs and end-to-end latency
    """
    
    def __init__(self, contract_abi: Optional[Dict] = None):
        """
        Initialize experiment framework
        
        Args:
            contract_abi: ABI of deployed contract (optional for simulation)
        """
        self.contract_abi = contract_abi
        self.results: List[RecoveryResult] = []
        
        # Gas cost estimates (based on contract complexity)
        self.base_gas = 50000  # Base transaction cost
        self.signature_verification_gas = 6000  # Per ECDSA signature
        self.storage_write_gas = 20000  # Update DID record
        
        # Timing parameters (in seconds)
        self.detection_delay = (0.1, 0.5)  # Time to detect compromise
        self.proposal_delay = (0.05, 0.2)  # Time to create proposal
        self.endorsement_delay_honest = (0.1, 0.3)  # Per honest watcher
        self.endorsement_delay_byzantine = (2.0, 10.0)  # Byzantine may delay
        self.block_time = 12.0  # Ethereum block time
        self.finality_time = 13 * 60  # 13 minutes average finality
    
    def estimate_gas(self, quorum_size: int) -> int:
        """
        Estimate gas cost for commitRecovery transaction
        
        Args:
            quorum_size: Number of signatures (2f+1)
        
        Returns:
            Estimated gas units
        """
        gas = (
            self.base_gas +
            self.signature_verification_gas * quorum_size +
            self.storage_write_gas
        )
        return gas
    
    def simulate_detection(self) -> float:
        """Simulate compromise detection time"""
        return random.uniform(*self.detection_delay)
    
    def simulate_proposal(self) -> float:
        """Simulate recovery proposal creation time"""
        return random.uniform(*self.proposal_delay)
    
    def simulate_endorsement_collection(
        self,
        n_watchers: int,
        f_byzantine: int,
        quorum_size: int,
        byzantine_behavior: str = "none"
    ) -> float:
        """
        Simulate collecting 2f+1 endorsements
        
        Args:
            n_watchers: Total watchers
            f_byzantine: Number of Byzantine watchers
            quorum_size: Required endorsements (2f+1)
            byzantine_behavior: "none", "delay", or "refuse"
        
        Returns:
            Time to collect quorum
        """
        honest_watchers = n_watchers - f_byzantine
        
        if byzantine_behavior == "refuse":
            # Byzantine watchers refuse to sign
            if honest_watchers < quorum_size:
                # Cannot reach quorum with honest watchers alone
                return float('inf')
        
        # Collect endorsements in parallel (simulate concurrent responses)
        endorsement_times = []
        
        for i in range(quorum_size):
            if i < honest_watchers:
                # Honest watcher
                t = random.uniform(*self.endorsement_delay_honest)
            else:
                # Need Byzantine signatures
                if byzantine_behavior == "delay":
                    t = random.uniform(*self.endorsement_delay_byzantine)
                else:
                    t = random.uniform(*self.endorsement_delay_honest)
            endorsement_times.append(t)
        
        # Time is max (waiting for slowest of the quorum)
        return max(endorsement_times)
    
    def simulate_commit_and_finalization(self) -> tuple:
        """
        Simulate on-chain commit and finalization
        
        Returns:
            (commit_time, finalization_time)
        """
        # Time for transaction to be included in block
        commit_time = random.uniform(0, 2 * self.block_time)
        
        # Time for finality (2 epochs on Ethereum)
        finalization_time = self.finality_time + random.uniform(-60, 60)
        
        return commit_time, finalization_time
    
    def run_recovery_experiment(
        self,
        n_watchers: int,
        f_byzantine: int,
        byzantine_behavior: str = "none"
    ) -> RecoveryResult:
        """
        Run a single recovery experiment
        
        Args:
            n_watchers: Total number of watchers (must be >= 3f+1)
            f_byzantine: Number of Byzantine watchers
            byzantine_behavior: Adversarial behavior pattern
        
        Returns:
            RecoveryResult with measurements
        """
        assert n_watchers >= 3 * f_byzantine + 1, "Need n >= 3f+1"
        
        quorum_size = 2 * f_byzantine + 1
        
        # Phase 1: Detection
        t_detection = self.simulate_detection()
        
        # Phase 2: Proposal
        t_proposal = self.simulate_proposal()
        
        # Phase 3: Endorsement collection
        t_endorsement = self.simulate_endorsement_collection(
            n_watchers, f_byzantine, quorum_size, byzantine_behavior
        )
        
        success = t_endorsement != float('inf')
        
        if not success:
            return RecoveryResult(
                quorum_size=quorum_size,
                n_watchers=n_watchers,
                f_byzantine=f_byzantine,
                gas_used=0,
                total_latency=float('inf'),
                phases=RecoveryPhase(),
                success=False,
                byzantine_behavior=byzantine_behavior
            )
        
        # Phase 4: Commit and finalization
        t_commit, t_finalization = self.simulate_commit_and_finalization()
        
        # Total latency
        total_latency = (
            t_detection + t_proposal + t_endorsement + 
            t_commit + t_finalization
        )
        
        # Gas cost
        gas_used = self.estimate_gas(quorum_size)
        
        phases = RecoveryPhase(
            detection_time=t_detection,
            proposal_time=t_proposal,
            endorsement_time=t_endorsement,
            commit_time=t_commit,
            finalization_time=t_finalization
        )
        
        result = RecoveryResult(
            quorum_size=quorum_size,
            n_watchers=n_watchers,
            f_byzantine=f_byzantine,
            gas_used=gas_used,
            total_latency=total_latency,
            phases=phases,
            success=True,
            byzantine_behavior=byzantine_behavior
        )
        
        self.results.append(result)
        return result
    
    def run_gas_cost_analysis(
        self,
        f_values: List[int],
        trials: int = 20
    ) -> List[Dict]:
        """
        Experiment 1: Gas cost vs. quorum size
        
        Args:
            f_values: List of f values to test (e.g., [1, 2, 3, 5, 10])
            trials: Number of trials per configuration
        
        Returns:
            List of result dictionaries
        """
        results = []
        
        for f in f_values:
            n = 3 * f + 1
            quorum_size = 2 * f + 1
            
            print(f"Testing f={f}, n={n}, quorum={quorum_size}")
            
            trial_results = []
            for trial in range(trials):
                result = self.run_recovery_experiment(
                    n_watchers=n,
                    f_byzantine=f,
                    byzantine_behavior="none"
                )
                trial_results.append(result)
            
            avg_gas = sum(r.gas_used for r in trial_results) / trials
            avg_latency = sum(r.total_latency for r in trial_results) / trials
            
            results.append({
                'f': f,
                'n': n,
                'quorum_size': quorum_size,
                'avg_gas': avg_gas,
                'avg_latency_seconds': avg_latency,
                'success_rate': sum(r.success for r in trial_results) / trials,
                'trials': trial_results
            })
        
        return results
    
    def run_latency_analysis(
        self,
        n_watchers: int,
        f_byzantine: int,
        behaviors: List[str] = ["none", "delay"],
        trials: int = 30
    ) -> List[Dict]:
        """
        Experiment 2: End-to-end latency under adversarial conditions
        
        Args:
            n_watchers: Network size
            f_byzantine: Number of Byzantine watchers
            behaviors: List of behaviors to test
            trials: Number of trials per behavior
        
        Returns:
            List of result dictionaries
        """
        results = []
        
        for behavior in behaviors:
            print(f"Testing behavior: {behavior}")
            
            trial_results = []
            for trial in range(trials):
                result = self.run_recovery_experiment(
                    n_watchers=n_watchers,
                    f_byzantine=f_byzantine,
                    byzantine_behavior=behavior
                )
                trial_results.append(result)
            
            successful_trials = [r for r in trial_results if r.success]
            
            if successful_trials:
                avg_latency = sum(r.total_latency for r in successful_trials) / len(successful_trials)
                
                # Phase breakdown
                avg_detection = sum(r.phases.detection_time for r in successful_trials) / len(successful_trials)
                avg_proposal = sum(r.phases.proposal_time for r in successful_trials) / len(successful_trials)
                avg_endorsement = sum(r.phases.endorsement_time for r in successful_trials) / len(successful_trials)
                avg_commit = sum(r.phases.commit_time for r in successful_trials) / len(successful_trials)
                avg_finalization = sum(r.phases.finalization_time for r in successful_trials) / len(successful_trials)
            else:
                avg_latency = float('inf')
                avg_detection = avg_proposal = avg_endorsement = avg_commit = avg_finalization = 0
            
            results.append({
                'behavior': behavior,
                'n_watchers': n_watchers,
                'f_byzantine': f_byzantine,
                'success_rate': len(successful_trials) / trials,
                'avg_total_latency': avg_latency,
                'avg_detection_time': avg_detection,
                'avg_proposal_time': avg_proposal,
                'avg_endorsement_time': avg_endorsement,
                'avg_commit_time': avg_commit,
                'avg_finalization_time': avg_finalization,
                'trials': trial_results
            })
        
        return results


def run_comparison_with_baselines():
    """
    Compare with Gnosis Safe and Argent Wallet
    (Based on reported gas costs from Etherscan)
    """
    # Baseline data from related work / Etherscan
    baselines = {
        'Gnosis_Safe_3of5': {
            'name': 'Gnosis Safe (3-of-5)',
            'gas': 85000,  # Approximate from Etherscan
            'latency': 12.0 + 13*60,  # Block time + finality
            'bft_guarantees': False
        },
        'Argent_Guardian_2of3': {
            'name': 'Argent (2-of-3 Guardians)',
            'gas': 120000,  # Approximate
            'latency': 24*3600,  # 24-hour delay for security
            'bft_guarantees': False
        }
    }
    
    # Our protocol
    experiment = BFTSHDIDExperiment()
    
    # Test with f=2 (3-of-5 quorum, comparable to Gnosis)
    our_result = experiment.run_recovery_experiment(
        n_watchers=7,  # 3*2+1
        f_byzantine=2,
        byzantine_behavior="none"
    )
    
    comparison = {
        'baselines': baselines,
        'bft_sh_did': {
            'name': 'BFT-SH-DID (5-of-7)',
            'gas': our_result.gas_used,
            'latency': our_result.total_latency,
            'bft_guarantees': True
        }
    }
    
    return comparison


if __name__ == "__main__":
    print("BFT-SH-DID Recovery Protocol Evaluation")
    print("=" * 50)
    
    experiment = BFTSHDIDExperiment()
    
    # Quick test
    print("\nQuick Test: Single Recovery")
    result = experiment.run_recovery_experiment(
        n_watchers=7,
        f_byzantine=2,
        byzantine_behavior="none"
    )
    
    print(f"Quorum size: {result.quorum_size}")
    print(f"Gas used: {result.gas_used:,}")
    print(f"Total latency: {result.total_latency:.2f}s ({result.total_latency/60:.1f} minutes)")
    print(f"  Detection: {result.phases.detection_time:.2f}s")
    print(f"  Proposal: {result.phases.proposal_time:.2f}s")
    print(f"  Endorsement: {result.phases.endorsement_time:.2f}s")
    print(f"  Commit: {result.phases.commit_time:.2f}s")
    print(f"  Finalization: {result.phases.finalization_time:.0f}s")
    print(f"Success: {result.success}")
